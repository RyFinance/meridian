"""Cycle-6 rates / FX / commodity data build (DATA ONLY; FRAMEWORK §3).

Nothing here computes a signal, sorts, or forms a strategy/control/portfolio. Outputs are per-instrument daily
excess returns, per-instrument month-end carry INPUT levels, and instrument-level QA (construction error vs a real
traded proxy, gaps, stale runs, point-in-time) with PASS/FAIL.

Declared rules (fixed before any QA number was computed):
  * FI construction: one per (country, tenor). Official daily constant-maturity / par / benchmark yield if an official
    daily series with >= 120 months exists (Fed H.15, Bundesbank, MOF Japan, BoE, BoC, Riksbank); otherwise the LSE
    vendor daily yield ('lse_vendor'). Return: y_{t-1}dt - D dy + 0.5 C dy^2 - rf_{t-1}dt with the par-bond D, C of
    research/core_premia_data/rates_fx_eq/synthetic.py (annual coupon for DE/FR/IT/ES/CH/SE/NO, semiannual else).
  * History start: the observation after the LAST unexplained gap > 10 business days in the chosen yield (FX: spot)
    series and after the end of the LAST flat run spanning >= 10 business days (earlier data are not used; recorded,
    with the STRICT full-history QA status in the notes). Explained gaps (whitelist) do not truncate; no return spans
    them. DISCLOSURE: the flat-run half of this rule, the monthly-comparability rule in te_ratio (a month is compared
    only if the synthetic return is defined on every one of its rows) and the DE proxy remap (EXHB.DE is the eb.rexx
    1.5-2.5y ETF -> DE 2y, not 5y) were added after a first pass that showed QA status only (no strategy returns).
  * QA FAIL if (a) monthly TE/sigma_proxy > 0.60 on >= 36 overlapping months vs the pre-declared proxy (PROXY maps
    below, fixed before computing), (b) any unexplained gap > 10 business days in the used window (none by
    construction of the start rule, reported anyway), (c) a flat run spanning >= 10 business days in the used
    window, (d) not point-in-time.
  * Short rate (percent p.a., known at t): official daily (lag 1 obs) > LSE daily 3M-ish (lag 1 obs) > OECD monthly
    IR3TIB/IRSTCI of the previous month; EUR members use EUR rates.
  * FX: H.10 spot, excess = S_t/S_{t-1}-1 + (rf_ccy - rf_usd)_{t-1} dt. G10 only.
  * CM: single-commodity ETFs (adjusted close) minus USD cash; WTI and natgas use the EIA C1 roll-spliced futures
    return (director correction: roll day return C1_t / C2_{t-1} - 1) before the ETF's first full month. Baskets
    (DBC, GSG, DBA, DBB, DBE), leveraged (UCO, SCO), and strips/duplicates (USL, UNL, DBO, SIVR) are aliases or
    non-single markets and are not candidates.
Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.cycle6.data_rates.build
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from research.core_premia_data.rates_fx_eq import synthetic as old
from research.cycle6.data_rates.common import COMM, META, OLD, OUT, RAW, utc_now, write_json

BD = pd.offsets.BDay()
ANNUAL = {"DE", "FR", "IT", "ES", "CH", "SE", "NO", "NL", "BE", "AT"}
CCY = {"US": "USD", "DE": "EUR", "FR": "EUR", "IT": "EUR", "ES": "EUR", "NL": "EUR", "BE": "EUR", "AT": "EUR",
       "JP": "JPY", "UK": "GBP", "CA": "CAD", "SE": "SEK", "NO": "NOK", "CH": "CHF", "AU": "AUD", "NZ": "NZD",
       "DK": "DKK"}
# (country, tenor) -> official (source, series_id) ; vendor LSE symbol
OFFICIAL = {
    ("US", 2): ("fed_h15", "RIFLGFCY02_N.B"), ("US", 5): ("fed_h15", "RIFLGFCY05_N.B"),
    ("US", 10): ("fed_h15", "RIFLGFCY10_N.B"), ("US", 30): ("fed_h15", "RIFLGFCY30_N.B"),
    ("DE", 2): ("bundesbank", "BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R02XX.R.A.A._Z._Z.A"),
    ("DE", 5): ("bundesbank", "BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R05XX.R.A.A._Z._Z.A"),
    ("DE", 10): ("bundesbank", "BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A"),
    ("DE", 30): ("bundesbank", "BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R30XX.R.A.A._Z._Z.A"),
    ("JP", 2): ("mof_japan", "JGB_2Y"), ("JP", 5): ("mof_japan", "JGB_5Y"), ("JP", 10): ("mof_japan", "JGB_10Y"),
    ("JP", 30): ("mof_japan", "JGB_30Y"),
    ("UK", 5): ("boe_iadb", "IUDSNPY"), ("UK", 10): ("boe_iadb", "IUDMNPY"), ("UK", 20): ("boe_iadb", "IUDLNPY"),
    ("CA", 2): ("boc_valet", "BD.CDN.2YR.DQ.YLD"), ("CA", 5): ("boc_valet", "BD.CDN.5YR.DQ.YLD"),
    ("CA", 10): ("boc_valet", "BD.CDN.10YR.DQ.YLD"), ("CA", 30): ("boc_valet", "BD.CDN.LONG.DQ.YLD"),
    ("SE", 2): ("riksbank", "SEGVB2YC"), ("SE", 5): ("riksbank", "SEGVB5YC"), ("SE", 10): ("riksbank", "SEGVB10YC"),
    ("NO", 5): ("norges_bank", "GOVT_GENERIC_RATES.B.5Y.GBON"), ("NO", 10): ("norges_bank", "GOVT_GENERIC_RATES.B.10Y.GBON"),
}
VENDOR = {  # LSE macro 'bonds' symbols (daily, catalog first date < 2020)
    ("UK", 2): "UK2Y", ("UK", 30): "UK30Y", ("NO", 10): "NO10Y",
    ("AU", 2): "AU2Y", ("AU", 5): "AU5Y", ("AU", 10): "AU10Y",
    ("FR", 2): "FR2Y", ("FR", 5): "FR5Y", ("FR", 10): "FR10Y",
    ("IT", 2): "IT2Y", ("IT", 5): "IT5Y", ("IT", 10): "IT10Y", ("IT", 30): "IT30Y",
    ("CH", 2): "CH2Y", ("CH", 10): "CH10Y", ("NZ", 2): "NZ2Y", ("NZ", 5): "NZ5Y", ("NZ", 10): "NZ10Y",
    ("ES", 5): "ES5Y", ("ES", 10): "ES10Y",
    # vendor alternatives to official series (used only if the official one has < 120 months)
    ("US", 2): "US2Y", ("US", 5): "US5Y", ("US", 10): "US10Y", ("US", 30): "US30Y",
    ("DE", 2): "DE2Y", ("DE", 5): "DE5Y", ("DE", 10): "DE10Y", ("DE", 30): "DE30Y",
    ("JP", 2): "JP2Y", ("JP", 5): "JP5Y", ("JP", 10): "JP10Y", ("JP", 30): "JP30Y",
    ("UK", 5): "UK5Y", ("UK", 10): "UK10Y", ("CA", 2): "CA2Y", ("CA", 5): "CA5Y", ("CA", 10): "CA10Y",
    ("CA", 30): "CA30Y", ("SE", 10): "SE10Y",
}
NO_DATA_FI = {"NL": "LSE: NL2Y from 2025-07 only, no 5y/10y", "BE": "LSE: BE2Y from 2025-07 only",
              "AT": "LSE: AT1Y only", "DK": "LSE: DK2Y from 2025-07 only"}
EXPLAINED_GAPS = {("US", 30): [("2002-02-15", "2006-02-10", "US Treasury suspended 30y issuance; H.15 30y CMT not published")]}
# Pre-declared traded proxies (fixed before computing TE): (ticker, currency)
PROXY_FI = {("US", 2): "SHY", ("US", 5): "IEI", ("US", 10): "IEF", ("US", 30): "TLT", ("DE", 2): "EXHB.DE",
            ("DE", 10): "EXHD.DE", ("UK", 10): "IGLT.L", ("CA", 10): "XGB.TO", ("CA", 30): "ZFL.TO",
            ("JP", 10): "2561.T", ("AU", 10): "IGB.AX", ("CH", 10): "CSBGC0.SW"}
PROXY_FX = {"AUD": ("FXA", "etf"), "CAD": ("FXC", "etf"), "CHF": ("FXF", "etf"), "EUR": ("FXE", "etf"),
            "GBP": ("FXB", "etf"), "JPY": ("FXY", "etf"), "NZD": ("6N=F", "future")}
G10 = ["AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "NOK", "NZD", "SEK"]
LSE_SHORT = {"JPY": "bonds/JP3M", "AUD": "economics/ausbbsr", "CHF": "bonds/CH3M",
             "NZD": "economics/newzealanintrat", "NOK": "economics/norwayintrat"}
CM = {  # market_id -> (ETF, economic market, EIA splice file or None)
    "CM_WTI": ("USO", "WTI crude oil", "crude_oil_wti_cushing"),
    "CM_NATGAS": ("UNG", "Henry Hub natural gas", "natural_gas_henry_hub_futures"),
    "CM_BRENT": ("BNO", "Brent crude oil", None), "CM_GASOLINE": ("UGA", "RBOB gasoline", None),
    "CM_GOLD": ("GLD", "gold", None), "CM_SILVER": ("SLV", "silver", None),
    "CM_PLATINUM": ("PPLT", "platinum", None), "CM_PALLADIUM": ("PALL", "palladium", None),
    "CM_COPPER": ("CPER", "copper", None), "CM_CORN": ("CORN", "corn", None),
    "CM_WHEAT": ("WEAT", "wheat", None), "CM_SOYBEANS": ("SOYB", "soybeans", None),
}
NOT_CANDIDATE_CM = {"DBC": "basket", "GSG": "basket", "DBA": "basket", "DBB": "basket", "DBE": "basket",
                    "UCO": "leveraged 2x", "SCO": "leveraged -2x", "USL": "alias WTI (12m strip)",
                    "UNL": "alias natgas (12m strip)", "DBO": "alias WTI (optimum yield)", "SIVR": "alias silver",
                    "JO_ipath": "1 stale row only"}


# ---------------------------------------------------------------- helpers
def bdays_between(a: pd.Series) -> pd.Series:
    """Business days strictly between consecutive dates."""
    d = pd.DatetimeIndex(a)
    out = np.r_[np.nan, np.busday_count(d[:-1].values.astype("datetime64[D]"), d[1:].values.astype("datetime64[D]")) - 1]
    return pd.Series(out, index=a.index)


def gap_scan(dates: pd.Series, explained=()):
    gb = bdays_between(dates)
    rows = []
    for i in np.where(gb > 10)[0]:
        a, b = dates.iloc[i - 1], dates.iloc[i]
        why = next((w for s, e, w in explained if a <= pd.Timestamp(e) and b >= pd.Timestamp(s)), None)
        rows.append({"from": str(a.date()), "to": str(b.date()), "bdays": int(gb.iloc[i]), "explained": why})
    return rows


def flat_runs(dates: pd.Series, vals: pd.Series, min_bd=10):
    v = vals.values
    runs, i, n = [], 0, len(v)
    while i < n:
        j = i
        while j + 1 < n and v[j + 1] == v[i]:
            j += 1
        if j > i:
            span = np.busday_count(np.datetime64(dates.iloc[i].date()), np.datetime64(dates.iloc[j].date()))
            if span >= min_bd:
                runs.append({"from": str(dates.iloc[i].date()), "to": str(dates.iloc[j].date()), "bdays": int(span)})
        i = j + 1
    return runs


def monthly_compound(s: pd.Series) -> pd.Series:
    return (1 + s.dropna()).groupby(pd.Grouper(freq="ME")).prod() - 1


def te_ratio(a: pd.Series, b: pd.Series):
    """Monthly TE/sigma_proxy of synthetic a vs proxy b (daily excess returns)."""
    ma, mb = monthly_compound(a), monthly_compound(b)
    # only months where both have data in (almost) the whole month
    ca, cb = a.dropna().groupby(pd.Grouper(freq="ME")).size(), b.dropna().groupby(pd.Grouper(freq="ME")).size()
    call = a.groupby(pd.Grouper(freq="ME")).size()
    ok = (ca.reindex(ma.index) >= 15) & (cb.reindex(ma.index).fillna(0) >= 15) & (ca.reindex(ma.index) == call.reindex(ma.index))
    j = pd.concat([ma[ok], mb], axis=1, join="inner").dropna()
    if len(j) < 2:
        return None, len(j), None
    d = j.iloc[:, 0] - j.iloc[:, 1]
    return float(d.std() / j.iloc[:, 1].std()), len(j), float(j.corr().iloc[0, 1])


# ---------------------------------------------------------------- inputs
def load_lse():
    D = json.loads((RAW / "lse_series_combined.json").read_text())
    pull = json.loads((META / "lse_pull.json").read_text())
    fetched = {}
    for c in pull["calls"]:
        if c.get("fetched_at_utc"):
            fetched.setdefault(f"{c['dataset']}/{c['symbol']}", []).append(c["fetched_at_utc"])
    out = {}
    for k, v in D.items():
        df = pd.DataFrame(v["rows"])
        if df.empty:
            continue
        df["date"] = pd.to_datetime(df["date"])
        s = df.drop_duplicates("date").set_index("date")["value"].astype(float).sort_index()
        out[k] = s
    return out, fetched


def short_rates(yold, o, lse):
    idx = pd.bdate_range("1960-01-01", "2026-09-30")
    rf = {}
    for c in ["USD", "EUR", "JPY", "GBP", "CAD", "SEK", "NOK", "CHF", "AUD", "NZD", "DKK"]:
        base = old.short_rate(c, yold, o, idx)
        if c in LSE_SHORT and LSE_SHORT[c] in lse:
            s = lse[LSE_SHORT[c]].shift(1)
            last = s.index.max()
            s = s.reindex(idx.union(s.index)).ffill(limit=10).reindex(idx)
            s[idx > last + pd.Timedelta(days=10)] = np.nan
            src = base["rf_source"].fillna("")
            m = s.notna() & ~src.str.contains(":")
            base.loc[m, "rf_pct"] = s[m]
            base.loc[m, "rf_source"] = f"lse:{LSE_SHORT[c]}_lag1"
        rf[c] = base
    return rf


# ---------------------------------------------------------------- bonds
def build_bonds(yold, lse, lse_fetch, rf):
    long_rows = []
    # yields_daily_long: every official + LSE vendor yield held
    for (src, sid), g in yold.groupby(["source", "series_id"]):
        if src.startswith("lse_vault"):
            continue
        long_rows.append(pd.DataFrame({"country": g["country"].values, "tenor": g["tenor_y"].values, "date": g["date"].values,
                                       "yield": g["value_pct"].values, "source": src, "series_id": sid}))
    for k, s in lse.items():
        ds, sym = k.split("/")
        if ds != "bonds":
            continue
        ctry = sym[:2]
        t = sym[2:]
        if not t[-1] in "YM" or not t[:-1].isdigit():
            continue
        ten = float(t[:-1]) / (12 if t[-1] == "M" else 1)
        long_rows.append(pd.DataFrame({"country": ctry, "tenor": ten, "date": s.index, "yield": s.values,
                                       "source": "lse_vendor", "series_id": k}))
    ylong = pd.concat(long_rows, ignore_index=True)
    ylong["date"] = pd.to_datetime(ylong["date"])

    rows, cands, comp = [], [], {}
    keys = sorted(set(OFFICIAL) | {k for k in VENDOR if k not in OFFICIAL})
    for (ctry, T) in keys:
        choice = None
        if (ctry, T) in OFFICIAL:
            src, sid = OFFICIAL[(ctry, T)]
            s = yold[(yold.source == src) & (yold.series_id == sid)].set_index("date")["value_pct"].sort_index()
            months = s.index.to_period("M").nunique()
            if months >= 120:
                choice = (src, sid, s, "official")
            else:
                comp[f"FI_{ctry}_{T}Y_official_rejected"] = f"{src}:{sid} only {months} months (<120); vendor used"
        if choice is None and (ctry, T) in VENDOR and f"bonds/{VENDOR[(ctry, T)]}" in lse:
            k = f"bonds/{VENDOR[(ctry, T)]}"
            choice = ("lse_vendor", k, lse[k], "vendor")
        if choice is None:
            continue
        src, sid, s, kind = choice
        s = s.dropna()
        s = s[~s.index.duplicated()]
        dts = s.index.to_series().reset_index(drop=True)
        gaps = gap_scan(dts, [(a, b, w) for a, b, w in EXPLAINED_GAPS.get((ctry, T), [])])
        unexpl = [g for g in gaps if not g["explained"]]
        flat_all = flat_runs(dts, s.reset_index(drop=True))
        strict = []
        if unexpl:
            strict.append(f"(b) {len(unexpl)} unexplained gaps")
        if flat_all:
            strict.append(f"(c) {len(flat_all)} flat runs")
        start = s.index.min()
        if unexpl:
            start = max(start, pd.Timestamp(unexpl[-1]["to"]))
        if flat_all:
            nxt = s.index[s.index > pd.Timestamp(flat_all[-1]["to"])]
            start = max(start, nxt[0] if len(nxt) else s.index.max())
        su = s[s.index >= start]
        # construction
        df = old.bond_excess(su, float(T), "par", "DE" if ctry in ANNUAL else "US", rf[CCY[ctry]])
        # first return after the start point already excluded by bond_excess (iloc[1:]); null out returns across
        # explained gaps (> 10 bdays)
        gb = np.r_[np.nan, np.busday_count(su.index[:-1].values.astype("datetime64[D]"),
                                           su.index[1:].values.astype("datetime64[D]")) - 1][1:]
        df.loc[gb > 10, ["excess_ret", "total_ret"]] = np.nan
        df = df.reset_index(names="date")
        mid = f"FI_{ctry}_{T}Y"
        df["market_id"], df["country"], df["tenor"], df["source"], df["series_id"] = mid, ctry, T, src, sid
        rows.append(df[["date", "market_id", "country", "tenor", "source", "series_id", "y", "dy", "dt", "dur", "conv",
                        "carry_income", "price_ret", "total_ret", "rf_pct", "rf_source", "excess_ret"]])
        # QA
        dts_u = su.index.to_series().reset_index(drop=True)
        g_used = [g for g in gap_scan(dts_u, [(a, b, w) for a, b, w in EXPLAINED_GAPS.get((ctry, T), [])]) if not g["explained"]]
        fr = flat_runs(dts_u, su.reset_index(drop=True))
        reasons, notes = [], []
        te = n_te = rho = None
        if (ctry, T) in PROXY_FI:
            tk = PROXY_FI[(ctry, T)]
            px = PROXIES.get(tk)
            if px is not None:
                pr = px["adjclose"].pct_change()
                dt_ = px.index.to_series().diff().dt.days / 365.0
                cur = CCY[ctry]
                prf = rf[cur]["rf_pct"].reindex(px.index)
                pex = pr - prf / 100 * dt_
                te, n_te, rho = te_ratio(df.set_index("date")["excess_ret"], pex)
                notes.append(f"proxy {tk}: TE/sigma={te if te is None else round(te, 3)} on {n_te} months, rho={rho if rho is None else round(rho, 3)}")
                if te is not None and n_te >= 36 and te > 0.60:
                    reasons.append(f"(a) TE/sigma_proxy {te:.2f} > 0.60 vs {tk} ({n_te} months)")
        else:
            notes.append("no single-country traded proxy held: (a) not applicable")
        if g_used:
            reasons.append(f"(b) {len(g_used)} unexplained gaps >10bd")
        if fr:
            reasons.append(f"(c) {len(fr)} flat runs >=10bd, first {fr[0]}")
        if unexpl or flat_all:
            notes.append(f"history truncated to {start.date()} (after last unexplained gap>10bd {unexpl[-1] if unexpl else None} "
                         f"/ last flat run>=10bd {flat_all[-1] if flat_all else None}); STRICT full-history status would be "
                         f"FAIL: {', '.join(strict)}")
        if kind == "vendor":
            d_ = su.diff()
            spikes = int(((d_.abs() > 0.25) & (d_.shift(-1).abs() > 0.25) & (d_ * d_.shift(-1) < 0)).sum())
            notes.append("LSE vendor yield (no vintages; snapshot time not documented - euro-area vendor yields co-move "
                         "with the NEXT Bundesbank fix, consistent with a late-day/US-close snapshot, not look-ahead); "
                         f"official daily source not available/too short; reversing spikes >25bp in used window: {spikes}")
        else:
            notes.append("official daily yield; no vintages")
        if src == "fed_h15":
            notes.append("H.15 value for day t published t+1 ~16:15 ET")
        rfsrc = df["rf_source"].fillna("NONE").str.split(":").str[0].str.split("_").str[:2].str.join("_").value_counts().to_dict()
        notes.append(f"rf sources {rfsrc}; rf missing rows {int(df.rf_pct.isna().sum())}")
        ex = df.dropna(subset=["excess_ret"])
        cands.append({"class": "FI", "market_id": mid, "economic_market": f"{ctry} government bond {T}y",
                      "construction": "yield->y*dt - D*dy + 0.5*C*dy^2 - local cash (par bond D,C; "
                                      f"{'annual' if ctry in ANNUAL else 'semiannual'} coupon)",
                      "source": f"{src}:{sid}", "first_date": str(ex.date.min().date()), "last_date": str(ex.date.max().date()),
                      "n_months": int(ex.date.dt.to_period("M").nunique()),
                      "qa_status": "FAIL" if reasons else "PASS", "qa_reasons": "; ".join(reasons),
                      "tenor": T, "notes": "; ".join(notes),
                      "_te": te, "_gaps": gaps, "_flat": fr})
    for c, why in NO_DATA_FI.items():
        cands.append({"class": "FI", "market_id": f"FI_{c}_10Y", "economic_market": f"{c} government bond 10y",
                      "construction": "none", "source": "none", "first_date": "", "last_date": "", "n_months": 0,
                      "qa_status": "FAIL", "qa_reasons": "no free daily yield >= 2y with history (" + why + ")",
                      "tenor": 10, "notes": "OECD monthly long-term average only; not daily"})
    b = pd.concat(rows, ignore_index=True)
    return b, ylong, cands, comp


def carry_inputs_fi(b, ylong, rf):
    """Month-end carry inputs per bond instrument (KMVP): yield, local short rate, slope, roll-down, carry."""
    pri = {"fed_h15": 0, "bundesbank": 0, "mof_japan": 0, "boe_iadb": 0, "boc_valet": 0, "riksbank": 0,
           "norges_bank": 0, "lse_vendor": 1, "ecb": 2, "snb": 3}
    yl = ylong[ylong.source != "snb"].copy()
    yl = yl[yl.country.isin(b.country.unique())]
    yl = yl[yl.tenor >= 1.0]  # curve points for roll-down (short end uses the local short rate)
    yl["pri"] = yl.source.map(pri).fillna(5)
    yl["m"] = yl.date.dt.to_period("M")
    # month-end observation per (country, tenor, source): last date in month
    me = yl.sort_values("date").groupby(["country", "tenor", "source", "m"]).tail(1)
    me = me.sort_values("pri").groupby(["country", "tenor", "m"]).head(1)
    out = []
    for mid, g in b.groupby("market_id"):
        g = g.dropna(subset=["y"]).copy()
        g["m"] = g.date.dt.to_period("M")
        last = g.sort_values("date").groupby("m").tail(1)
        ctry, T = g.country.iloc[0], float(g.tenor.iloc[0])
        cur = rf[CCY[ctry]]
        for _, r in last.iterrows():
            # curve at the same month-end
            cv = me[(me.country == ctry) & (me.m == r.m) & (me.tenor < T) & ((me.date - r.date).abs() <= pd.Timedelta(days=5))]
            rf_t = cur["rf_pct"].asof(r.date) if r.date >= cur.index[0] else np.nan
            same = cv[cv.source == g.source.iloc[0]]
            if len(same):
                cv = same  # prefer the instrument's own source for the neighbour tenor
            if len(cv):
                nb = cv.sort_values("tenor").iloc[-1]
                t_n, y_n, nb_src = float(nb.tenor), float(nb["yield"]), f"{nb.source}:{nb.tenor}y"
            elif pd.notna(rf_t):
                t_n, y_n, nb_src = 0.25, float(rf_t), "local_short_rate_0.25y"
            else:
                t_n, y_n, nb_src = np.nan, np.nan, None
            y = r.y * 100
            D = float(old.par_dur_conv(np.array([r.y]), T, 1 if ctry in ANNUAL else 2)[0][0])
            slope_pp_per_y = (y - y_n) / (T - t_n) if pd.notna(y_n) else np.nan
            rolldown = D * slope_pp_per_y if pd.notna(slope_pp_per_y) else np.nan  # pp/yr, linear-interp roll-down
            out.append({"market_id": mid, "country": ctry, "tenor": T, "month": r.m.to_timestamp("M"), "obs_date": r.date,
                        "yield_pct": y, "short_rate_pct": rf_t, "slope_vs_short_pct": y - rf_t if pd.notna(rf_t) else np.nan,
                        "neighbor_tenor": t_n, "neighbor_yield_pct": y_n, "neighbor_source": nb_src,
                        "mod_duration": D, "rolldown_pct_pa": rolldown,
                        "carry_pct_pa": (y - rf_t + rolldown) if pd.notna(rf_t) and pd.notna(rolldown) else np.nan,
                        "rf_source": cur["rf_source"].asof(r.date) if r.date >= cur.index[0] else None})
    return pd.DataFrame(out)


# ---------------------------------------------------------------- FX
def build_fx(fx, rf):
    usd = rf["USD"]
    rows, cands, carry = [], [], []
    for ccy in G10:
        g = fx[(fx.source == "fed_h10") & (fx.ccy == ccy)]
        s = g.set_index("date")["usd_per_ccy"].sort_index()
        s = s[~s.index.duplicated()].dropna()
        df = pd.DataFrame({"S": s})
        df["spot_ret"] = df.S.pct_change()
        df["dt"] = df.index.to_series().diff().dt.days / 365.0
        rc = rf[ccy].reindex(df.index)
        df["rf_ccy_pct"], df["rf_ccy_source"] = rc["rf_pct"], rc["rf_source"]
        df["rf_usd_pct"] = usd["rf_pct"].reindex(df.index)
        df["carry_diff_pct"] = df.rf_ccy_pct - df.rf_usd_pct
        df["excess_ret"] = df.spot_ret + df.carry_diff_pct / 100 * df.dt
        # no return across a gap > 10 bdays
        gb = np.r_[np.nan, np.busday_count(df.index[:-1].values.astype("datetime64[D]"),
                                           df.index[1:].values.astype("datetime64[D]")) - 1]
        df.loc[gb > 10, "excess_ret"] = np.nan
        df = df.iloc[1:].reset_index(names="date")
        mid = f"FX_{ccy}"
        df["market_id"], df["ccy"], df["source"] = mid, ccy, "fed_h10"
        rows.append(df)
        ex = df.dropna(subset=["excess_ret"])
        dts = s.index.to_series().reset_index(drop=True)
        gaps = gap_scan(dts)
        flat_all = flat_runs(dts, s.reset_index(drop=True))
        start = ex.date.min()
        if gaps:
            start = max(start, pd.Timestamp(gaps[-1]["to"]))
        if flat_all:
            nxt = s.index[s.index > pd.Timestamp(flat_all[-1]["to"])]
            start = max(start, nxt[0])
        exu = ex[ex.date > start] if start > ex.date.min() else ex
        fr = flat_runs(s[s.index >= start].index.to_series().reset_index(drop=True), s[s.index >= start].reset_index(drop=True))
        reasons, notes = [], []
        if ccy in PROXY_FX:
            tk, kind = PROXY_FX[ccy]
            px = PROXIES.get(tk)
            if px is not None:
                col = "adjclose" if kind == "etf" else "close"
                pr = px[col].pct_change()
                if kind == "etf":
                    pex = pr - usd["rf_pct"].reindex(px.index) / 100 * px.index.to_series().diff().dt.days / 365.0
                else:
                    pex = pr  # continuous future (unadjusted roll gaps; quarterly)
                te, n, rho = te_ratio(exu.set_index("date")["excess_ret"], pex)
                notes.append(f"proxy {tk}: TE/sigma={te if te is None else round(te, 3)} on {n} months, rho={rho if rho is None else round(rho, 3)}")
                if te is not None and n >= 36 and te > 0.60:
                    reasons.append(f"(a) TE/sigma_proxy {te:.2f} > 0.60 vs {tk}")
        else:
            notes.append("no USD-listed traded proxy held (forward-point check in core_premia report): (a) not applicable")
        if fr:
            reasons.append(f"(c) {len(fr)} flat spot runs >=10bd, first {fr[0]}")
        if gaps or flat_all:
            notes.append(f"history truncated to {start.date()} (after last gap>10bd {gaps[-1] if gaps else None} / last flat "
                         f"spot run>=10bd {flat_all[-1] if flat_all else None}, pre-float pegs); STRICT full-history status "
                         f"would be FAIL ({len(gaps)} gaps, {len(flat_all)} flat runs)")
        notes.append("H.10 noon NY buying rates, weekly release (Monday) of prior week: value for t known <= t+7 days; "
                     "short-rate differential lagged 1 obs; OECD monthly averages lagged 1 month where no daily rate")
        rfsrc = exu.rf_ccy_source.fillna("NONE").str.split(":").str[0].str.split("_").str[:2].str.join("_").value_counts().to_dict()
        notes.append(f"rf_ccy sources {rfsrc}; carry missing rows {int(exu.carry_diff_pct.isna().sum())}")
        rows[-1] = df[df.date > start].reset_index(drop=True) if start > df.date.min() else df
        cands.append({"class": "FX", "market_id": mid, "economic_market": f"{ccy}/USD",
                      "construction": "H.10 spot + lagged short-rate differential", "source": "fed_h10 + short rates",
                      "first_date": str(exu.date.min().date()), "last_date": str(exu.date.max().date()),
                      "n_months": int(exu.date.dt.to_period("M").nunique()),
                      "qa_status": "FAIL" if reasons else "PASS", "qa_reasons": "; ".join(reasons), "tenor": "",
                      "notes": "; ".join(notes)})
        last = df.assign(m=df.date.dt.to_period("M")).groupby("m").tail(1)
        for _, r in last.iterrows():
            carry.append({"market_id": mid, "ccy": ccy, "month": r.date.to_period("M").to_timestamp("M"),
                          "obs_date": r.date, "spot_usd_per_ccy": r.S,
                          "rf_ccy_pct": rf[ccy]["rf_pct"].asof(r.date), "rf_usd_pct": usd["rf_pct"].asof(r.date),
                          "rf_ccy_source": rf[ccy]["rf_source"].asof(r.date)})
    c = pd.DataFrame(carry)
    c["rate_diff_pct"] = c.rf_ccy_pct - c.rf_usd_pct
    return pd.concat(rows, ignore_index=True), c, cands


# ---------------------------------------------------------------- commodities
def cl_expiries(dates: pd.DatetimeIndex, kind: str):
    """Expiry dates on the series' own trading calendar."""
    trade = pd.DatetimeIndex(sorted(dates))
    out = []
    for m in pd.period_range(trade.min().to_period("M"), trade.max().to_period("M"), freq="M"):
        if kind == "crude":  # 3 business days before the 25th (or the preceding business day if 25th not one)
            d25 = pd.Timestamp(m.year, m.month, 25)
            prior = trade[trade <= d25]
            if len(prior) < 4:
                continue
            anchor = d25 if d25 in trade else prior[-1]
            i = trade.get_loc(anchor)
            out.append(trade[i - 3])
        else:  # natgas: 3 business days before the first calendar day of the delivery month (next month)
            first_next = (m + 1).to_timestamp()
            prior = trade[trade < first_next]
            if len(prior) < 3:
                continue
            out.append(prior[-3])
    return pd.DatetimeIndex(out)


def eia_splice(fname, kind):
    e = pd.read_parquet(COMM / "eia_audit" / f"{fname}.parquet").rename(columns={"Date": "date"})
    e["date"] = pd.to_datetime(e["date"])
    e = e.set_index("date").sort_index()
    e = e[e.c1.notna()]
    exp = cl_expiries(e.index, kind)
    ret = e.c1 / e.c1.shift(1) - 1
    roll_day = pd.Series(False, index=e.index)
    for x in exp:
        nxt = e.index[e.index > x]
        if len(nxt):
            roll_day[nxt[0]] = True
    rr = e.c1 / e.c2.shift(1) - 1
    ret[roll_day] = rr[roll_day]
    # prices <= 0 (WTI 2020-04-20) make simple returns undefined
    bad = (e.c1 <= 0) | (e.c1.shift(1) <= 0) | (roll_day & (e.c2.shift(1) <= 0))
    ret[bad] = np.nan
    return e, ret.iloc[1:], roll_day, exp


def build_cm(rf):
    usd = rf["USD"]
    rows, cands, carry, qa_extra = [], [], [], {}
    etf = {}
    for mid, (tk, name, eia) in CM.items():
        p = pd.read_parquet(COMM / "etf" / f"{tk}.parquet")
        p["date"] = pd.to_datetime(p["Date"].astype(str).str[:10])
        p = p.set_index("date").sort_index()
        p = p[~p.index.duplicated()]
        r = p["Adj_Close"].pct_change()
        dt_ = p.index.to_series().diff().dt.days / 365.0
        ex = (r - usd["rf_pct"].reindex(p.index) / 100 * dt_).iloc[1:]
        etf[mid] = ex
        first_full = (p.index.min() + pd.offsets.MonthBegin(1)).normalize()
        if p.index.min().day == 1:
            first_full = p.index.min()
        seg_etf = ex[ex.index >= first_full]
        parts = [pd.DataFrame({"date": seg_etf.index, "excess_ret": seg_etf.values, "segment": f"etf:{tk}"})]
        notes, reasons = [], []
        src = f"yfinance adjusted close {tk}"
        first = seg_etf.index.min()
        if eia:
            e, er, roll, exp = eia_splice(eia, "crude" if "crude" in eia else "natgas")
            seg_e = er[er.index < first_full].dropna()
            parts.insert(0, pd.DataFrame({"date": seg_e.index, "excess_ret": seg_e.values, "segment": "eia_c1_rollspliced"}))
            te, n, rho = te_ratio(er, ex)
            qa_extra[mid] = {"eia_vs_etf_TE_over_sigma": te, "months": n, "rho": rho, "roll_days": int(roll.sum()),
                             "eia_last": str(e.index.max().date())}
            notes.append(f"EIA C1 roll-spliced (C1_t/C2_(t-1)-1 day after expiry; {int(roll.sum())} roll days) before "
                         f"{first_full.date()}, {tk} after; splice vs {tk} monthly TE/sigma={te if te is None else round(te, 3)} "
                         f"on {n} months rho={rho if rho is None else round(rho, 3)}; futures return = excess (no cash)")
            if te is not None and n >= 36 and te > 0.60:
                reasons.append(f"(a) EIA splice TE/sigma {te:.2f} > 0.60 vs {tk}")
            src = f"EIA NYMEX C1/C2 ({eia}) + {src}"
            first = seg_e.index.min()
            eg = gap_scan(e.index.to_series().reset_index(drop=True))
            eg_used = [g for g in eg if pd.Timestamp(g["to"]) < first_full]
            if eg_used:
                reasons.append(f"(b) EIA gaps >10bd in used segment: {eg_used[:3]}")
            ef = flat_runs(e.index.to_series()[e.index < first_full].reset_index(drop=True), e.c1[e.index < first_full].reset_index(drop=True))
            if ef:
                reasons.append(f"(c) EIA flat runs: {ef[:2]}")
            notes.append("EIA publication lag unknown (static archive); 14:30 ET settlement")
            # energy carry inputs (month-end, EIA curve C1..C4)
            me = e.assign(m=e.index.to_period("M")).groupby("m").tail(1)
            for d, rr_ in me.iterrows():
                carry.append({"market_id": mid, "month": d.to_period("M").to_timestamp("M"), "obs_date": d,
                              "c1": rr_.c1, "c2": rr_.c2, "c3": rr_.c3, "c4": rr_.c4,
                              "ln_c1_c2_ann": np.log(rr_.c1 / rr_.c2) * 12 if rr_.c1 > 0 and rr_.c2 > 0 else np.nan,
                              "ln_c1_c4_ann": np.log(rr_.c1 / rr_.c4) * 4 if rr_.c1 > 0 and rr_.c4 > 0 else np.nan,
                              "ln_c2_c4_ann": np.log(rr_.c2 / rr_.c4) * 6 if rr_.c2 > 0 and rr_.c4 > 0 else np.nan,
                              "days_to_c1_expiry": int(((exp[exp >= d].min() - d).days) if (exp >= d).any() else -1),
                              "source": f"EIA {eia}"})
        # ETF QA
        dts = p.index.to_series().reset_index(drop=True)
        g = gap_scan(dts)
        if g:
            reasons.append(f"(b) ETF gaps >10bd: {g[:3]}")
        fr = flat_runs(dts, p["Close"].reset_index(drop=True))
        if fr:
            reasons.append(f"(c) ETF flat runs: {fr[:2]}")
        notes.append("instrument is the traded ETF itself (TE vs itself = 0); adjusted close is vendor back-adjusted for "
                     "distributions/splits (returns PIT-valid, levels not)")
        seg = pd.concat(parts, ignore_index=True)
        seg["market_id"], seg["etf"] = mid, tk
        rows.append(seg)
        cands.append({"class": "CM", "market_id": mid, "economic_market": name,
                      "construction": ("EIA C1 roll-spliced futures to ETF first full month, then ETF TR - USD cash"
                                       if eia else "ETF total return - USD cash"),
                      "source": src, "first_date": str(first.date()), "last_date": str(seg.date.max().date()),
                      "n_months": int(seg.date.dt.to_period("M").nunique()),
                      "qa_status": "FAIL" if reasons else "PASS", "qa_reasons": "; ".join(reasons), "tenor": "",
                      "notes": "; ".join(notes)})
    return pd.concat(rows, ignore_index=True), pd.DataFrame(carry), cands, qa_extra


# ---------------------------------------------------------------- main
PROXIES: dict = {}
FX_START: dict = {}


def main():
    yold = pd.read_parquet(OLD / "processed" / "yields_daily.parquet")
    yold["date"] = pd.to_datetime(yold["date"])
    o = pd.read_parquet(OLD / "processed" / "oecd_monthly.parquet")
    fx = pd.read_parquet(OLD / "processed" / "fx_spot_daily.parquet")
    fx["date"] = pd.to_datetime(fx["date"])
    m = pd.read_parquet(OLD / "processed" / "market_daily.parquet")
    m["date"] = pd.to_datetime(m["date"])
    for t, g in m.groupby("ticker"):
        PROXIES[t] = g.set_index("date").sort_index()[~g.set_index("date").index.duplicated()]
    lse, lse_fetch = load_lse()
    rf = short_rates(yold, o, lse)

    srows = []
    for c, d in rf.items():
        dd = d.dropna(subset=["rf_pct"]).reset_index(names="date")
        dd["ccy"] = c
        srows.append(dd)
    sr = pd.concat(srows, ignore_index=True)
    sr.to_parquet(OUT / "short_rates_daily.parquet", index=False)

    b, ylong, fi_c, fi_comp = build_bonds(yold, lse, lse_fetch, rf)
    b.to_parquet(OUT / "bond_excess_daily.parquet", index=False)
    ylong.to_parquet(OUT / "yields_daily_long.parquet", index=False)
    ci = carry_inputs_fi(b, ylong, rf)
    ci.to_parquet(OUT / "bond_carry_inputs_monthly.parquet", index=False)

    f, fc, fx_c = build_fx(fx, rf)
    f.to_parquet(OUT / "fx_excess_daily.parquet", index=False)
    fc.to_parquet(OUT / "fx_carry_inputs_monthly.parquet", index=False)

    c, ec, cm_c, cm_qa = build_cm(rf)
    c.to_parquet(OUT / "commodity_excess_daily.parquet", index=False)
    ec.to_parquet(OUT / "energy_carry_inputs_monthly.parquet", index=False)

    # vendor-vs-official level check (instrument-level data QA, overlapping dates)
    vv = {}
    for (ctry, T), (src, sid) in OFFICIAL.items():
        k = f"bonds/{VENDOR.get((ctry, T), '')}"
        if k in lse:
            a = yold[(yold.source == src) & (yold.series_id == sid)].set_index("date")["value_pct"]
            j = pd.concat([a, lse[k]], axis=1, join="inner").dropna()
            if len(j):
                d = j.iloc[:, 1] - j.iloc[:, 0]
                vv[f"{ctry}_{T}y"] = {"n": len(j), "mean_diff_bp": round(d.mean() * 100, 2),
                                      "p95_abs_diff_bp": round(d.abs().quantile(.95) * 100, 2),
                                      "corr_daily_change": round(float(j.diff().corr().iloc[0, 1]), 3)}

    cands = fi_c + fx_c + cm_c
    cd = pd.DataFrame(cands)
    cols = ["class", "market_id", "economic_market", "construction", "source", "first_date", "last_date", "n_months",
            "qa_status", "qa_reasons", "tenor", "notes"]
    cd[cols].to_csv(OUT / "candidates.csv", index=False)
    qa_detail = {r["market_id"]: {k: r.get(k) for k in ("_te", "_gaps", "_flat")} for r in cands if "_gaps" in r}
    write_json(META / "build_record.json", {"built_at_utc": utc_now().isoformat(), "fi_official_rejected": fi_comp,
                                            "vendor_vs_official": vv, "cm_eia_qa": cm_qa, "fi_qa_detail": qa_detail,
                                            "not_candidate_cm": NOT_CANDIDATE_CM,
                                            "rows": {"bond": len(b), "ylong": len(ylong), "fx": len(f), "cm": len(c),
                                                     "short": len(sr), "bond_carry": len(ci), "fx_carry": len(fc),
                                                     "energy_carry": len(ec)}})
    print(cd[["class", "market_id", "first_date", "last_date", "n_months", "qa_status", "qa_reasons"]].to_string())


if __name__ == "__main__":
    main()
