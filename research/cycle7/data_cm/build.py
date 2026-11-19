"""Cycle-7 CM data build: CM-NEW and CM-DEEP daily excess-return panels (DATA ONLY; FRAMEWORK §1-2, cycle-6 §3).

No signal-conditioned, strategy, control or portfolio return is computed. Outputs are per-instrument daily excess
returns, instrument-level QA (construction error vs a traded proxy, gaps, stale runs, point-in-time) and
data-availability eligibility counts.

Declared rules (fixed before any QA number or return was looked at; instrument level only):
  1. Constructions (cycle-6 FRAMEWORK §3, cycle-6 research/cycle6/data_rates/build.py reused unchanged):
     * fund line: Yahoo Adj Close simple return - USD cash (cycle-6 short_rates_daily USD, as known that day)
       x calendar days/365. ETNs and collateralised ETCs (WisdomTree, single Bloomberg/Solactive sub-index TR) are
       treated as ETN-class "single-commodity ETN total return" (declared; sensitivity count without ETCs reported).
     * EUR Borsa Italiana line (only when a market has no USD line with history): P_EUR x ECB EUR/USD reference
       rate of the same date (asof) -> USD, then as above. Validated against the USD LSE line of the same product
       where both exist (monthly TE/sigma; construction FAILs for all EUR lines if any validation pair > 0.60).
     * EIA NYMEX splice: held-contract return, C1_t/C1_prev - 1, and C1_t/C2_prev - 1 on the first C1 row after
       each expiry (director correction). Expiry on the sheet's own trading calendar (all rows, incl. rows with a
       missing C1): HO/HU/RB = last business day of the month before delivery -> roll on the first trading row of
       each month; propane (NYMEX PN) = same rule (verified by the switch diagnostic below, not by returns).
       A roll-day return with a missing C2_prev is NaN (cycle-6 convention). The segment starts at the first date
       Contract 2 is published (before it the roll return cannot be formed: INFEASIBLE, missing field C2).
       Futures return = excess return (no cash). A market with an ETF uses the ETF from its first full month and
       the splice before it (cycle-6 §3). Gasoline (cycle-6 CM_GASOLINE, deep extension): EIA NYH regular
       (HU/RFG) splice until 2006-01-02, EIA RBOB splice from 2006-01-03 (first roll day of 2006) to UGA's first
       full month.
  2. One instrument per economic market: the USD line with the longest retained history after rule 3's
     truncation; ties -> US-listed. EUR lines only if no USD line exists. Aliases and baskets excluded.
  3. History-start truncation (ADDENDUM-1 item 1, extended to vendor price discontinuities): a series starts after
     its last unexplained gap > 10 business days, its last flat run of the price spanning >= 10 business days,
     and its last unexplained price discontinuity: a bad print (|r_t| > 15% with the next close back within 25%
     of the log move of the pre-print close) or a unit break (|r_t| > 50%). Explained: LME nickel squeeze
     2022-03-07/08 (LME suspended trading). QA (b)(c) then apply to the retained window.
  4. QA FAIL if (a) monthly TE/sigma_proxy > 0.60 on >= 36 overlapping months vs a traded proxy, where a free
     proxy series exists; (b) gap > 10bd; (c) flat run >= 10bd; (d) not PIT; (e) < 2 retained daily observations.
Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.cycle7.data_cm.build
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.cycle6.data_rates.build import flat_runs, gap_scan, monthly_compound, te_ratio

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "cycle7" / "cm" / "raw"
OUT = ROOT / "data" / "cycle7" / "cm"
C6 = ROOT / "data" / "cycle6" / "snapshot_store" / "versions" / "cycle6_eval_v1" / "view" / "eval"
DEEP_END_MONTH = "2007-11"          # months before 2007-12 (FRAMEWORK §2)
DEEP_PANEL_END = "2007-12-31"       # returns needed to hold the last deep month (one-session lag)
EXPLAINED_BREAKS = {"NICK": [("2022-03-07", "2022-03-08", "LME nickel short squeeze; LME suspended nickel 2022-03-08")]}

# economic market -> candidate lines (ticker, kind, product root for alias/validation, roll/index doc)
MARKETS = {
    "CM_SUGAR": [("CANE", "US ETF", "Teucrium: 35% 2nd / 30% 3rd / 35% next-March ICE No.11 futures"),
                 ("SUGA.L", "ETC USD", "WisdomTree: Bloomberg Sugar Subindex TR (BCOM roll, 5 bd from 6th bd)")],
    "CM_COFFEE": [("COFF.L", "ETC USD", "WisdomTree: Bloomberg Coffee Subindex TR")],
    "CM_COCOA": [("COCO.L", "ETC USD", "WisdomTree: Bloomberg Cocoa Subindex 4W TR (BCOMCC4T)")],
    "CM_COTTON": [("COTN.L", "ETC USD", "WisdomTree: Bloomberg Cotton Subindex TR")],
    "CM_NICKEL": [("NICK.L", "ETC USD", "WisdomTree: Bloomberg Nickel Subindex TR (LME)")],
    "CM_ALUMINIUM": [("ALUM.L", "ETC USD", "WisdomTree: Bloomberg Aluminum Subindex TR (LME)")],
    "CM_ZINC": [("ZINC.L", "ETC USD", "WisdomTree: Bloomberg Zinc Subindex TR (LME)")],
    "CM_LEANHOGS": [("HOGS.L", "ETC USD", "WisdomTree: Bloomberg Lean Hogs Subindex TR (CME)")],
    "CM_LIVECATTLE": [("CATL.L", "ETC USD", "WisdomTree: Bloomberg Live Cattle Subindex TR (CME)")],
    "CM_TIN": [("TINM.MI", "ETC EUR", "WisdomTree: Bloomberg Tin Subindex TR (LME); EUR Milan line x ECB")],
    "CM_LEAD": [("LEAD.MI", "ETC EUR", "WisdomTree: Bloomberg Lead Subindex TR (LME); EUR Milan line x ECB")],
    "CM_SOYBEANOIL": [("SOYO.MI", "ETC EUR", "WisdomTree: Bloomberg Soybean Oil Subindex TR (CBOT); EUR x ECB")],
    "CM_CARBON_EUA": [("GRN", "US ETN", "iPath Series B: Barclays Global Carbon II TR (EU ETS >99.9%, CDM <0.1%)"),
                      ("CARB.L", "ETC USD", "WisdomTree: Solactive Carbon Emission Allowances Rolling Futures TR (ICE EUA)")],
    "CM_CARBON_CCA": [("KCCA", "US ETF", "KraneShares: IHS Markit Carbon CCA Index (Dec CCA futures, roll last day of Nov)")],
}
EIA_NEW = {  # market -> (sheet, name, first-date rule, roll-calendar kind)
    "CM_HEATINGOIL": ("Data 4", "NYH No.2 heating oil (NYMEX HO; ULSD spec from 2013-05)"),
    "CM_PROPANE": ("Data 5", "Mont Belvieu propane (NYMEX PN)"),
}
EUR_VALIDATION = ["NICK", "ALUM", "ZINC", "COFF", "COTN", "SUGA", "HOGS", "COCO"]
NOT_CANDIDATE = {
    "KRBN": "basket (EUA+CCA+RGGI+UKA)", "UGAS.L": "alias CM_GASOLINE", "DBA/DBC/GSG/DBB/DBE/COW/LSTK/JJG": "basket",
    "OATS/USD, RICE/USD, OJ/USD, LUMBER/USD, IRON/USD, SUGAR/USD, ... (LSE Terminal)": "CFD price, undocumented "
    "roll (e.g. OATS/USD +27% jump 2026-07-06 after a 9-day flat run), no financing, history from 2025-12 only",
    "OJ=F, ZO=F, ZR=F, HE=F, LE=F, GF=F, KC=F, SB=F, CC=F, CT=F, HO=F, KE=F (Yahoo)": "unrolled front-month "
    "continuation (no C2, roll gaps in the price) -> not a held-contract return",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------------------------------------------ inputs
def usd_rf():
    s = pd.read_parquet(ROOT / "data" / "cycle6" / "rates" / "short_rates_daily.parquet")
    u = s[s.ccy == "USD"].copy()
    u["date"] = pd.to_datetime(u["date"])
    return u.set_index("date").sort_index()["rf_pct"]


def ecb_eurusd():
    e = pd.read_csv(RAW / "ecb_eurusd_daily.csv", usecols=["TIME_PERIOD", "OBS_VALUE"])
    e["date"] = pd.to_datetime(e.TIME_PERIOD)
    return e.set_index("date").sort_index()["OBS_VALUE"].astype(float).dropna()


def yahoo(t):
    p = pd.read_parquet(RAW / "yahoo" / f"{t}.parquet")
    p["date"] = pd.to_datetime(p["Date"].str[:10])
    p = p.set_index("date").sort_index()
    return p[~p.index.duplicated()]


def eia_sheet(sheet):
    d = pd.read_excel(RAW / "eia" / "PET_PRI_FUT_S1_D.xls", sheet_name=sheet, header=2)
    d.columns = ["date", "c1", "c2", "c3", "c4"]
    d["date"] = pd.to_datetime(d["date"])
    return d.set_index("date").sort_index()


# ------------------------------------------------------------------ QA helpers
def discontinuities(close: pd.Series, root: str):
    lr = np.log(close / close.shift(1))
    nxt = np.log(close.shift(-1) / close.shift(1))
    out = []
    expl = EXPLAINED_BREAKS.get(root, [])
    for d, x in lr.items():
        if not np.isfinite(x):
            continue
        a = abs(np.expm1(x))
        bad = (a > 0.15 and np.isfinite(nxt[d]) and abs(nxt[d]) < 0.25 * abs(x)) or a > 0.50
        if bad and not any(pd.Timestamp(s) <= d <= pd.Timestamp(e) for s, e, _ in expl):
            out.append({"date": str(d.date()), "ret": round(float(np.expm1(x)), 3)})
    return out


def truncation_start(close: pd.Series, root: str, breaks=True):
    """Observation date after the last gap > 10bd, the end of the last flat run >= 10bd, and the last break."""
    dates = close.index.to_series().reset_index(drop=True)
    cands, why = [close.index.min()], []
    for g in gap_scan(dates):
        cands.append(pd.Timestamp(g["to"]))  # the first obs after the gap starts the series (no return spans it)
        why.append(f"gap {g['from']}..{g['to']}")
    for f in flat_runs(dates, close.reset_index(drop=True)):
        nx = close.index[close.index > pd.Timestamp(f["to"])]
        cands.append(nx[0] if len(nx) else close.index.max())
        why.append(f"flat {f['from']}..{f['to']}")
    for b in (discontinuities(close, root) if breaks else []):
        nx = close.index[close.index > pd.Timestamp(b["date"])]
        cands.append(nx[0] if len(nx) else close.index.max())
        why.append(f"break {b['date']} {b['ret']:+.0%}")
    st = max(cands)
    # the first return is on the obs after the start obs
    return st, why


# ------------------------------------------------------------------ constructions
def fund_excess(t, rf, fx=None):
    p = yahoo(t)
    px = p["Adj_Close"].astype(float)
    if fx is not None:
        px = px * fx.reindex(px.index, method="ffill")
    root = t.split(".")[0]
    st, why = truncation_start(p["Close"].astype(float), root)
    px = px[px.index >= st]
    r = px.pct_change()
    dt_ = px.index.to_series().diff().dt.days / 365.0
    rfv = rf.reindex(px.index, method="ffill")
    ex = (r - rfv / 100 * dt_).iloc[1:]
    return ex, p, st, why


def eia_roll_days(cal: pd.DatetimeIndex):
    """Roll = first trading row of each month (expiry = last business day of the prior month)."""
    s = cal.to_series()
    first = s.groupby(cal.to_period("M")).min()
    return pd.DatetimeIndex(first.values[1:])


def eia_splice(e: pd.DataFrame, roll_mode="first_of_month"):
    cal = e.index
    if roll_mode == "first_of_month":
        rolls = eia_roll_days(cal)
    else:  # second-to-last business day expiry -> roll on the last trading row of the month
        s = cal.to_series()
        rolls = pd.DatetimeIndex(s.groupby(cal.to_period("M")).max().values)
    v = e[e.c1.notna()]
    prev = v.index.to_series().shift(1)
    ret = v.c1 / v.c1.shift(1) - 1
    # a roll occurs between prev (exclusive) and t (inclusive)
    rpos = np.searchsorted(rolls.values, v.index.values, side="right")
    ppos = np.searchsorted(rolls.values, prev.values.astype("datetime64[ns]"), side="right")
    is_roll = pd.Series(rpos > ppos, index=v.index)
    is_roll.iloc[0] = False
    rr = v.c1 / v.c2.shift(1) - 1
    ret[is_roll] = rr[is_roll]
    bad = (v.c1 <= 0) | (v.c1.shift(1) <= 0) | (is_roll & (v.c2.shift(1) <= 0))
    ret[bad] = np.nan
    return ret.iloc[1:], is_roll.iloc[1:], v


def switch_diagnostic(e: pd.DataFrame, roll_mode):
    """Roll-calendar check on price LEVELS only: share of declared roll days on which the curve 'shifts' (C1_t, C2_t
    closer to C2_{t-1}, C3_{t-1} than to C1_{t-1}, C2_{t-1}); same share on all other days."""
    v = e[e.c1.notna() & e.c2.notna() & e.c3.notna()]
    _, is_roll, _ = eia_splice(e, roll_mode)
    d1 = np.log(v.c1 / v.c2.shift(1)).abs() + np.log(v.c2 / v.c3.shift(1)).abs()
    d0 = np.log(v.c1 / v.c1.shift(1)).abs() + np.log(v.c2 / v.c2.shift(1)).abs()
    ok = d1.notna() & d0.notna()
    closer = (d1 < d0)[ok]
    rr = is_roll.reindex(closer.index).astype("boolean").fillna(False).astype(bool)
    return {"roll_days": int(rr.sum()), "share_shift_on_roll_days": round(float(closer[rr].mean()), 3),
            "share_shift_on_other_days": round(float(closer[~rr].mean()), 3)}


def eia_market(sheet, start_rule="c2_first"):
    e = eia_sheet(sheet)
    c2_first = e.c2.first_valid_index()
    ret, is_roll, v = eia_splice(e)
    ret = ret[ret.index > c2_first]
    is_roll = is_roll[is_roll.index > c2_first]
    c1 = v.c1[v.index >= c2_first]
    st, why = truncation_start(c1, "EIA", breaks=False)  # C1 level jumps at rolls are genuine curve gaps
    ret = ret[ret.index > st]
    return {"e": e, "ret": ret, "is_roll": is_roll[is_roll.index > st], "start_obs": st, "why": why,
            "c2_first": c2_first, "nan_roll": int((is_roll[is_roll.index > st] & ret.reindex(is_roll[is_roll.index > st].index).isna()).sum())}


# ------------------------------------------------------------------ main
def main():
    rf = usd_rf()
    fx = ecb_eurusd()
    log = {"rules": __doc__.split("Declared rules")[1].split("Run:")[0].strip(), "markets": {}, "eia": {}}
    rows, cands = [], []

    # --- EUR conversion validation (instrument level, before any selection)
    val = {}
    for root in EUR_VALIDATION:
        a, *_ = fund_excess(f"{root}.MI", rf, fx)
        b, *_ = fund_excess(f"{root}.L", rf)
        te, n, rho = te_ratio(a, b)
        val[root] = {"te_over_sigma": None if te is None else round(te, 3), "months": n, "rho": None if rho is None else round(rho, 3)}
    eur_ok = all(v["te_over_sigma"] is not None and (v["months"] < 36 or v["te_over_sigma"] <= 0.60) for v in val.values())
    log["eur_conversion_validation"] = {"pairs": val, "pass": eur_ok}

    # --- fund / ETN / ETC markets
    for mid, lines in MARKETS.items():
        opts = []
        for t, kind, doc in lines:
            ex, p, st, why = fund_excess(t, rf, fx if kind == "ETC EUR" else None)
            opts.append({"t": t, "kind": kind, "doc": doc, "ex": ex, "p": p, "st": st, "why": why,
                         "n": int(ex.notna().sum())})
        opts.sort(key=lambda o: (-o["n"], 0 if o["kind"].startswith("US") else 1))
        o = opts[0]
        ex = o["ex"]
        reasons, notes = [], []
        if o["n"] < 2:
            reasons.append("(e) no retained history after truncation")
        if o["kind"] == "ETC EUR" and not eur_ok:
            reasons.append("(a) EUR-line conversion validation TE/sigma > 0.60")
        # QA (b)(c) on the retained window (none by construction of the start rule)
        ret_p = o["p"]["Close"][o["p"].index >= o["st"]]
        g = gap_scan(ret_p.index.to_series().reset_index(drop=True))
        fr = flat_runs(ret_p.index.to_series().reset_index(drop=True), ret_p.reset_index(drop=True))
        if g:
            reasons.append(f"(b) gaps {g[:2]}")
        if fr:
            reasons.append(f"(c) flat runs {fr[:2]}")
        pr = o["p"]
        notes.append(f"{o['kind']} {o['t']} ({doc_short(o['doc'])}); yahoo raw {pr.index.min().date()}..{pr.index.max().date()}; "
                     f"retained from {o['st'].date()}" + (f" after {len(o['why'])} truncation events, last: {o['why'][-1]}" if o["why"] else ""))
        notes.append("instrument is the traded fund/note itself (TE vs itself = 0); Adj Close vendor-adjusted")
        if o["kind"].startswith("ETC"):
            notes.append("collateralised ETC (Jersey debt security) treated as ETN-class; LSE/Milan close timing")
        for alt in opts[1:]:
            notes.append(f"alternative line {alt['t']} not used ({alt['n']} retained obs vs {o['n']})")
        first_full = ex.index.min()
        seg = pd.DataFrame({"date": ex.index, "excess_ret": ex.values, "segment": f"{o['kind']}:{o['t']}", "market_id": mid})
        rows.append(seg)
        cands.append(cand_row(mid, economic(mid), f"{o['kind']} total return - USD cash", f"yfinance Adj Close {o['t']}",
                              seg, reasons, notes, o["kind"]))
        log["markets"][mid] = {"chosen": o["t"], "options": [{k: (str(v) if k == "st" else v) for k, v in x.items()
                                                                if k in ("t", "kind", "n", "st", "why")} for x in opts]}

    # --- EIA new markets
    for mid, (sheet, name) in EIA_NEW.items():
        m = eia_market(sheet)
        diag = {mode: switch_diagnostic(m["e"], mode) for mode in ("first_of_month", "last_of_month")}
        reasons, notes = [], []
        ret = m["ret"].dropna()
        ef = flat_runs(m["e"].c1.dropna()[m["e"].c1.dropna().index >= m["start_obs"]].index.to_series().reset_index(drop=True),
                       m["e"].c1.dropna()[m["e"].c1.dropna().index >= m["start_obs"]].reset_index(drop=True))
        if ef:
            reasons.append(f"(c) flat runs {ef[:2]}")
        proxy = "none free (UHN delisted 2018, no free history: Yahoo empty, stooq bot-wall, LSE MCP none)" \
            if mid == "CM_HEATINGOIL" else "none exists (no propane fund)"
        notes.append(f"EIA NYMEX C1/C2 {name} roll-spliced (C1_t/C2_prev-1 on first row of each month; "
                     f"{int(m['is_roll'].sum())} roll days, {m['nan_roll']} NaN for missing C2_prev); C2 first published "
                     f"{m['c2_first'].date()} (earlier rows INFEASIBLE: missing C2); retained from {m['start_obs'].date()}"
                     + (f" (last truncation: {m['why'][-1]})" if m["why"] else ""))
        notes.append(f"traded proxy: {proxy} -> QA (a) not assessable; method validated on RBOB vs UGA (this pass) and WTI vs USO (cycle 6)")
        notes.append("futures return = excess (no cash); EIA stopped publishing 2024-04-05; EIA publication lag unknown")
        seg = pd.DataFrame({"date": ret.index, "excess_ret": ret.values, "segment": "eia_c1_rollspliced", "market_id": mid})
        rows.append(seg)
        cands.append(cand_row(mid, name, "EIA C1 roll-spliced futures (excess)", f"EIA PET_PRI_FUT_S1_D {sheet}",
                              seg, reasons, notes, "EIA"))
        log["eia"][mid] = {"switch_diagnostic": diag, "c2_first": str(m["c2_first"].date()), "start_obs": str(m["start_obs"].date()),
                           "truncation": m["why"], "nan_roll_days": m["nan_roll"],
                           "c1_rows": int(m["e"].c1.notna().sum()), "rows": len(m["e"])}

    new = pd.concat(rows, ignore_index=True)
    new_c = pd.DataFrame(cands)

    # --- gasoline deep extension (cycle-6 market CM_GASOLINE)
    hu, rb = eia_market("Data 2"), eia_market("Data 3")
    sw = pd.Timestamp("2006-01-03")
    uga_ex, uga_p, uga_st, _ = fund_excess("UGA", rf)
    uga_first_full = (uga_p.index.min() + pd.offsets.MonthBegin(1)).normalize()
    te_rb, n_rb, rho_rb = te_ratio(rb["ret"], uga_ex)
    te_hr, n_hr, rho_hr = te_ratio(hu["ret"][hu["ret"].index >= "2005-11-01"].dropna(), rb["ret"].dropna())
    gas_eia = pd.concat([hu["ret"][hu["ret"].index < sw], rb["ret"][(rb["ret"].index >= sw) & (rb["ret"].index < uga_first_full)]]).dropna()
    log["eia"]["CM_GASOLINE_deep"] = {
        "hu": {"c2_first": str(hu["c2_first"].date()), "start_obs": str(hu["start_obs"].date()), "truncation": hu["why"],
               "nan_roll_days": hu["nan_roll"], "switch_diagnostic": switch_diagnostic(hu["e"], "first_of_month")},
        "rbob": {"start_obs": str(rb["start_obs"].date()), "truncation": rb["why"], "nan_roll_days": rb["nan_roll"],
                 "switch_diagnostic": switch_diagnostic(rb["e"], "first_of_month")},
        "rbob_splice_vs_UGA": {"te_over_sigma": te_rb, "months": n_rb, "rho": rho_rb},
        "hu_vs_rbob_overlap": {"te_over_sigma": te_hr, "months": n_hr, "rho": rho_hr}}
    # --- CM-DEEP: cycle-6 CM panel (PASS rows, already truncated) + gasoline extension + new markets, <= 2007-12-31
    c6 = pd.read_parquet(C6 / "panels" / "daily_excess_CM.parquet")
    c6c = pd.read_csv(C6 / "candidate_list.csv")
    c6c = c6c[c6c["class"] == "CM"].drop_duplicates("market_id")
    gas = pd.DataFrame({"date": gas_eia.index, "market_id": "CM_GASOLINE", "value": gas_eia.values})
    deep = pd.concat([c6[["date", "market_id", "value"]], gas,
                      new.rename(columns={"excess_ret": "value"})[["date", "market_id", "value"]]], ignore_index=True)
    deep = deep[deep.date <= DEEP_PANEL_END].dropna(subset=["value"])
    deep = deep.drop_duplicates(["date", "market_id"]).sort_values(["market_id", "date"]).reset_index(drop=True)
    gas_reasons = []
    if te_rb is not None and n_rb >= 36 and te_rb > 0.60:
        gas_reasons.append(f"(a) RBOB splice TE/sigma {te_rb:.2f} > 0.60 vs UGA")
    deep_c = []
    for _, r in c6c.iterrows():
        sub = deep[deep.market_id == r.market_id]
        if not len(sub):
            continue
        row = {"class": "CM", "market_id": r.market_id, "qa_status": r.qa_status, "source_class": "CM", "tenor": "",
               "economic_market": r.economic_market, "construction": r.construction, "source": r.source,
               "first_date": str(sub.date.min().date()), "last_date": str(sub.date.max().date()),
               "n_months": int(sub.date.dt.to_period("M").nunique()), "alias_of": "", "use_note": "cycle-6 PASS row, unchanged",
               "source_file": "data/cycle6/snapshot_store/versions/cycle6_eval_v1/view/eval/candidate_list.csv", "qa_reasons": ""}
        if r.market_id == "CM_GASOLINE":
            row.update({"construction": "EIA NYH regular (HU) C1 roll-spliced to 2006-01-02, EIA RBOB C1 roll-spliced to UGA first "
                        "full month (2008-03-01), then UGA TR - USD cash (cycle-6 row)",
                        "source": "EIA PET_PRI_FUT_S1_D Data 2 + Data 3 + cycle-6 UGA",
                        "qa_status": "FAIL" if gas_reasons else "PASS", "qa_reasons": "; ".join(gas_reasons),
                        "use_note": f"deep extension; RBOB splice vs UGA TE/sigma={round(te_rb, 3)} on {n_rb} months rho={round(rho_rb, 3)}; "
                                    f"HU vs RBOB overlap TE/sigma={None if te_hr is None else round(te_hr, 3)} on {n_hr} months; "
                                    f"HU C2 first {hu['c2_first'].date()} (earlier INFEASIBLE: missing C2)"})
        deep_c.append(row)
    for _, r in new_c.iterrows():
        sub = deep[deep.market_id == r.market_id]
        if len(sub):
            d = r.to_dict()
            d.update({"first_date": str(sub.date.min().date()), "last_date": str(sub.date.max().date()),
                      "n_months": int(sub.date.dt.to_period("M").nunique())})
            deep_c.append(d)
    deep_c = pd.DataFrame(deep_c)

    # PASS-only panels (ADDENDUM-1 item 4); instrument rows kept within first..last
    newp = new.rename(columns={"excess_ret": "value"})[["date", "market_id", "value"]].dropna()
    pass_new = set(new_c.loc[new_c.qa_status == "PASS", "market_id"])
    pass_deep = set(deep_c.loc[deep_c.qa_status == "PASS", "market_id"])
    write_eval(OUT / "eval_new", newp[newp.market_id.isin(pass_new)], new_c, "CM-NEW", log)
    write_eval(OUT / "eval_deep", deep[deep.market_id.isin(pass_deep)], deep_c, "CM-DEEP", log)

    # --- feasibility (data availability only)
    feas = {}
    etc_ids = set(new_c.loc[new_c.construction.str.startswith("ETC"), "market_id"])
    feas["CM-NEW"] = eligibility(newp[newp.market_id.isin(pass_new)])
    cane, *_ = fund_excess("CANE", rf)  # sugar via the US fund when ETCs are excluded
    no_etc = pd.concat([newp[newp.market_id.isin(pass_new - etc_ids)],
                        pd.DataFrame({"date": cane.index, "market_id": "CM_SUGAR", "value": cane.values}).dropna()])
    feas["CM-NEW_without_ETC(sugar=CANE)"] = eligibility(no_etc)
    dp = deep[deep.market_id.isin(pass_deep)]
    feas["CM-DEEP_signal_months_le_2007-11"] = eligibility(dp, end=DEEP_END_MONTH)
    feas["CM-DEEP_signal_months_le_2007-10"] = eligibility(dp, end="2007-10")
    feas["CM-DEEP_cycle6_markets_only"] = eligibility(dp[dp.market_id.isin(set(c6c.market_id))], end=DEEP_END_MONTH)
    log["feasibility"] = feas
    log["not_candidate"] = NOT_CANDIDATE
    (OUT / "build_log.json").write_text(json.dumps(log, indent=1, sort_keys=True, default=str))
    print(new_c[["market_id", "source", "first_date", "last_date", "n_months", "qa_status", "qa_reasons"]].to_string())
    print(deep_c[["market_id", "first_date", "last_date", "n_months", "qa_status"]].to_string())
    print(json.dumps({k: {kk: v[kk] for kk in ("defined_months", "first_defined", "last_defined", "max_eligible")} for k, v in feas.items()}, indent=1))
    print(json.dumps(log["eia"], indent=1, default=str)[:4000])
    print(json.dumps(log["eur_conversion_validation"], indent=1))


def doc_short(s):
    return s.split(":")[1].strip() if ":" in s else s


def economic(mid):
    return mid[3:].lower().replace("_", " ")


def cand_row(mid, econ, construction, source, seg, reasons, notes, kind):
    s = seg.dropna(subset=["excess_ret"])
    return {"class": "CM", "market_id": mid, "qa_status": "FAIL" if reasons else "PASS", "source_class": "CM", "tenor": "",
            "economic_market": econ, "construction": construction, "source": source,
            "first_date": str(s.date.min().date()) if len(s) else "", "last_date": str(s.date.max().date()) if len(s) else "",
            "n_months": int(s.date.dt.to_period("M").nunique()), "alias_of": "", "use_note": "; ".join(notes),
            "source_file": "data/cycle7/cm/raw (manifest.json)", "qa_reasons": "; ".join(reasons)}


def eligibility(long: pd.DataFrame, end: str | None = None):
    """TSMOM eligibility (cycle-6 feasibility_counts logic): >= 756 valid daily obs through month-end t and a
    return in each of months t-11..t; class defined iff >= 3 eligible."""
    if not len(long):
        return {"defined_months": 0, "first_defined": None, "last_defined": None, "max_eligible": 0, "feasible": False}
    w = long.pivot_table(index="date", columns="market_id", values="value").sort_index()
    per = w.index.to_period("M")
    months = pd.period_range(per.min(), per.max(), freq="M")
    mh = w.notna().groupby(per).any().reindex(months, fill_value=False)
    cnt = w.notna().cumsum().groupby(per).max().reindex(months).ffill().fillna(0)
    ok12 = mh.copy()
    for L in range(1, 12):
        ok12 &= mh.shift(L, fill_value=False)
    n = (ok12 & (cnt >= 756)).sum(axis=1)
    if end:
        n = n[n.index <= pd.Period(end, "M")]
    okm = n >= 3
    return {"defined_months": int(okm.sum()), "first_defined": str(n.index[okm.argmax()]) if okm.any() else None,
            "last_defined": str(n.index[::-1][okm[::-1].argmax()]) if okm.any() else None,
            "max_eligible": int(n.max()) if len(n) else 0, "feasible": bool(okm.sum() >= 24),
            "eligible_count_by_year_end": {str(k): int(v) for k, v in n[n.index.month == 12].items() if v > 0}}


def write_eval(root: Path, panel: pd.DataFrame, cands: pd.DataFrame, sample: str, log):
    (root / "panels").mkdir(parents=True, exist_ok=True)
    panel = panel.sort_values(["market_id", "date"]).reset_index(drop=True)
    panel["date"] = pd.to_datetime(panel["date"])
    panel.to_parquet(root / "panels" / "daily_excess_CM.parquet", index=False)
    cols = ["class", "market_id", "qa_status", "source_class", "tenor", "economic_market", "construction", "source",
            "first_date", "last_date", "n_months", "alias_of", "use_note", "source_file", "qa_reasons"]
    cands[cols].sort_values("market_id").to_csv(root / "candidate_list.csv", index=False)
    comp = {"sample": sample, "written_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "scope": "cycle-7 CM data agent; instrument-level only; not frozen (no snapshot)",
            "long_format": "date, market_id, value (decimal daily excess return; cycle-6 engine io.py)",
            "panel_rows": len(panel), "markets_pass": sorted(panel.market_id.unique().tolist()),
            "markets_fail": cands.loc[cands.qa_status == "FAIL", ["market_id", "qa_reasons"]].to_dict("records"),
            "per_market": {m: {"first": str(g.date.min().date()), "last": str(g.date.max().date()), "obs": len(g)}
                           for m, g in panel.groupby("market_id")},
            "raw_manifest_sha256": sha(RAW / "manifest.json"),
            "code_sha256": {"research/cycle7/data_cm/build.py": sha(Path(__file__)),
                            "research/cycle7/data_cm/fetch.py": sha(Path(__file__).with_name("fetch.py"))},
            "panel_sha256": sha(root / "panels" / "daily_excess_CM.parquet"),
            "not_candidate": NOT_CANDIDATE,
            "no_returns_computed": "instrument-level transforms and QA only; no signal/strategy/control/portfolio return"}
    if sample == "CM-DEEP":
        comp["window"] = f"sample months <= {DEEP_END_MONTH}; panel rows <= {DEEP_PANEL_END} (warm-up included, "
        comp["window"] += "last rows cover the one-session-lag holding of the last month)"
    (root / "completeness.json").write_text(json.dumps(comp, indent=1, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
