"""Cycle-7 FX data build: samples FX-EM and FX-DEEP (cycle-7 FRAMEWORK §§1-3 + cycle-7 ADDENDUM-1 masking).

DATA ONLY. Outputs per-instrument daily excess returns, month-end signal INPUT levels (spot, foreign short rate,
PIT CPI), the regime table and instrument QA. No signal, sort, strategy, control or portfolio return is computed.

Construction = cycle-6 research/cycle6/data_rates/build.py::build_fx, unchanged:
  excess_t = S_t/S_{t-1} - 1 + (rf_ccy - rf_usd)_{t-1-known} * dt,  S = USD per unit of currency, dt = days/365,
  no return across a gap > 10 business days; history start after the LAST gap > 10 bd and the LAST flat spot run
  spanning >= 10 bd (ADDENDUM-1 truncation); QA FAIL on gaps/flat runs in the used window.
Spot source per currency (declared before any QA number):
  * Fed H.10 daily noon NY (same processed file as cycle 6) for non-NDF H.10 currencies (DKK HKD LKR MXN SGD
    THB VEB ZAR).
  * NDF currencies (FRAMEWORK §3(b)): onshore central-bank rate from BIS WS_XRU daily (national sources).
  * Non-H.10 currencies: BIS WS_XRU daily (currency per USD, inverted).
  * Legacy DEM FRF ITL NLG BEF ESP: Fed H.10 historical pages (dat89_*, dat96_*), 1971-01-04..1998-12-31.
Short rate (percent p.a., known at t), same priority logic as cycle 6:
  OECD monthly IRSTCI < IR3TIB of the PREVIOUS month (value for M usable from M+1 day 1, ffill <= 62 days past the
  last value) < LSE daily interbank rate (LSE MCP macro_series; lag 1 obs, ffill <= 10 obs) where held.
  Added fallback (declared): BIS WS_CBPOL daily central-bank policy rate, lag 1 obs, ffill <= 10 obs, used ONLY on
  days where neither of the cycle-6 sources has a value. USD: cycle-6 data/cycle6/rates/short_rates_daily.parquet.
CPI: cycle-6 data/cycle6/equity/cpi_monthly_pit.parquet (OECD SDMX / LSE; default_2m availability, latest vintage,
  NOT first release; ALFRED holds US vintages only). PIT rule = cycle-6 build_eval.pit_cpi_monthly.
Masking (cycle-7 ADDENDUM-1, director ruling): for every excluded currency-month (regimes.py), ALL inputs of that
  currency in that month are removed: daily excess returns dated in the month and the month's fx_foreign_rate,
  fx_spot and fx_cpi_pit rows. Currencies excluded for their whole used history are FAIL.
FX-DEEP: cycle-6 G10 rows (cycle-6 eval panel values, unchanged) + legacy currencies. Both samples: dates
  >= 1973-03-01 only (FRAMEWORK §1: FX before 1973 infeasible); §3 masking applied to all.
Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.cycle7.data_fx.build
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from research.cycle6.build_eval import long_frame, pit_cpi_monthly
from research.cycle6.data_rates.build import flat_runs, gap_scan
from research.cycle7.data_fx import regimes as R

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data" / "cycle7" / "fx"
RAW = OUT / "raw"
C6V = REPO / "data" / "cycle6" / "snapshot_store" / "versions" / "cycle6_eval_v1" / "view" / "eval"
OLD = REPO / "data" / "core_premia" / "rates_fx_eq" / "processed"
G10 = ["AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "NOK", "NZD", "SEK"]
EM = ["MXN", "BRL", "CLP", "COP", "PEN", "ARS", "ZAR", "TRY", "PLN", "HUF", "CZK", "RUB", "ILS", "INR", "IDR",
      "KRW", "TWD", "PHP", "THB", "MYR", "SGD", "HKD", "CNY", "DKK", "ISK", "LKR", "VEB"]
LEGACY = ["DEM", "FRF", "ITL", "NLG", "BEF", "ESP"]
H10 = {"DKK", "HKD", "LKR", "MXN", "SGD", "THB", "VEB", "ZAR", "MYR"}  # used from H.10 (non-NDF or no BIS)
BIS_ISO2 = {"MXN": "MX", "BRL": "BR", "CLP": "CL", "COP": "CO", "PEN": "PE", "ARS": "AR", "ZAR": "ZA", "TRY": "TR",
            "PLN": "PL", "HUF": "HU", "CZK": "CZ", "RUB": "RU", "ILS": "IL", "INR": "IN", "IDR": "ID", "KRW": "KR",
            "TWD": "TW", "PHP": "PH", "THB": "TH", "MYR": "MY", "SGD": "SG", "HKD": "HK", "CNY": "CN", "DKK": "DK",
            "ISK": "IS", "LKR": "LK", "VEB": "VE", "DEM": "DE", "FRF": "FR", "ITL": "IT", "NLG": "NL", "BEF": "BE",
            "ESP": "ES"}
OECD_AREA = {"MXN": "MEX", "BRL": "BRA", "CLP": "CHL", "COP": "COL", "ZAR": "ZAF", "TRY": "TUR", "PLN": "POL",
             "HUF": "HUN", "CZK": "CZE", "RUB": "RUS", "ILS": "ISR", "INR": "IND", "IDR": "IDN", "KRW": "KOR",
             "CNY": "CHN", "DKK": "DNK", "ISK": "ISL", "DEM": "DEU", "FRF": "FRA", "ITL": "ITA", "NLG": "NLD",
             "BEF": "BEL", "ESP": "ESP"}
LSE_RATE = {"PLN": "polandintrat", "HUF": "hungaryintrat", "IDR": "indonesiaintrat", "INR": "indiaintrat",
            "ISK": "icelandintrat", "COP": "colombiaintrat", "CLP": "chileintrat", "KRW": "southkoreintrat",
            "THB": "thailandintrat", "TWD": "taiwanintrat", "CNY": "chinaintrat", "ZAR": "southafriintrat",
            "SGD": "sibcon"}
# hongkongintrat not used: month-end sampled before 2014 (393 gaps > 12 days), not a daily series.
BIS_POL = {c: BIS_ISO2[c] for c in EM if c not in ("SGD", "LKR", "VEB", "TWD")}  # files held (TW empty)
CPI_CTRY = {"MXN": "MX", "BRL": "BR", "CLP": "CL", "COP": "CO", "ZAR": "ZA", "TRY": "TR", "PLN": "PL", "HUF": "HU",
            "CZK": "CZ", "RUB": "RU", "ILS": "IL", "INR": "IN", "IDR": "ID", "KRW": "KR", "TWD": "TW", "THB": "TH",
            "MYR": "MY", "SGD": "SG", "HKD": "HK", "CNY": "CN", "DKK": "DK", "ISK": "IS", "DEM": "DE", "FRF": "FR",
            "ITL": "IT", "NLG": "NL", "BEF": "BE", "ESP": "ES"}
H10_HIST = {"DEM": "ge", "FRF": "fr", "ITL": "it", "NLG": "ne", "BEF": "be", "ESP": "sp"}
IDX = pd.bdate_range("1960-01-01", "2026-09-30")
DEEP_START = pd.Timestamp("1973-03-01")


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def mtime(p: Path) -> str:
    return dt.datetime.fromtimestamp(Path(p).stat().st_mtime, dt.timezone.utc).isoformat()


# ------------------------------------------------------------------ spot
def bis_fx(ccy: str) -> pd.Series:
    d = pd.read_csv(RAW / "bis_xru_d" / f"D_{BIS_ISO2[ccy]}.csv")
    d = d[d["COLLECTION"] == "A"]
    s = pd.Series(pd.to_numeric(d["OBS_VALUE"], errors="coerce").to_numpy(), index=pd.to_datetime(d["TIME_PERIOD"]))
    s = s[s > 0].sort_index()
    s = s[~s.index.duplicated()]
    s = s[s.index.dayofweek < 5]
    return 1.0 / s  # USD per unit of currency


def h10_hist(ccy: str) -> pd.Series:
    vals = {}
    for p in ("dat89", "dat96"):
        t = (RAW / "fed_h10_hist" / f"{p}_{H10_HIST[ccy]}.htm").read_text(errors="ignore")
        t = re.sub(r"<[^>]*>", " ", t).replace("&nbsp;", " ")
        for dd, mm, yy, v in re.findall(r"(\d{1,2})-\s*([A-Z][a-z]{2})-\s*(\d{2})\s+([0-9.]+)\s", t):
            ts = pd.to_datetime(f"{dd}-{mm}-{yy}", format="%d-%b-%y")
            if ts.year > 2030:
                ts = ts - pd.DateOffset(years=100)
            vals[ts] = 1.0 / float(v)
    return pd.Series(vals).sort_index()


def spots(h10: pd.DataFrame) -> dict:
    out = {}
    for c in EM:
        if c in H10 and c not in R.NDF_ONLY:
            g = h10[(h10.source == "fed_h10") & (h10.ccy == c)].set_index("date")["usd_per_ccy"].sort_index()
            out[c] = (g[~g.index.duplicated()].dropna(), "fed_h10 (noon NY buying rate)")
        else:
            out[c] = (bis_fx(c), "BIS WS_XRU daily (national central-bank source), inverted")
    for c in LEGACY:
        out[c] = (h10_hist(c), "Fed H.10 historical pages (noon NY), inverted")
    return out


# ------------------------------------------------------------------ rates
def lagged_daily(s: pd.Series) -> pd.Series:
    s = s.sort_index()
    s = s[~s.index.duplicated()].shift(1)
    last = s.index.max()
    r = s.reindex(IDX.union(s.index)).ffill(limit=10).reindex(IDX)
    r[IDX > last + pd.Timedelta(days=10)] = np.nan
    return r


def short_rate(c: str, o: pd.DataFrame, lse: dict, bis_pol: dict) -> pd.DataFrame:
    out = pd.DataFrame(index=IDX)
    out["rf_pct"], out["rf_source"] = np.nan, None
    area = OECD_AREA.get(c)
    if area:
        for meas in ("IRSTCI", "IR3TIB"):  # IR3TIB overrides IRSTCI (cycle-6 synthetic.short_rate)
            g = o[(o.ref_area == area) & (o.measure == meas)]
            s = g.set_index("month")["value_pct"].sort_index()
            if s.empty:
                continue
            s.index = s.index + pd.Timedelta(days=1)
            s = s.reindex(IDX.union(s.index)).ffill().reindex(IDX)
            s[IDX > g["month"].max() + pd.Timedelta(days=62)] = np.nan
            m = s.notna()
            out.loc[m, "rf_pct"] = s[m]
            out.loc[m, "rf_source"] = f"oecd_{meas}_{area}_prev_month_avg"
    if c in LSE_RATE and LSE_RATE[c] in lse:
        s = lagged_daily(lse[LSE_RATE[c]])
        m = s.notna()
        out.loc[m, "rf_pct"] = s[m]
        out.loc[m, "rf_source"] = f"lse:economics/{LSE_RATE[c]}_lag1"
    if c in bis_pol:
        s = lagged_daily(bis_pol[c])
        m = s.notna() & out["rf_pct"].isna()
        out.loc[m, "rf_pct"] = s[m]
        out.loc[m, "rf_source"] = f"bis_cbpol:D.{BIS_POL[c]}_lag1_fallback"
    return out


def load_rates():
    o = pd.read_parquet(OLD / "oecd_monthly.parquet")
    o["month"] = pd.to_datetime(o["month"])
    lj = json.loads((RAW / "lse_mcp" / "lse_macro_series.json").read_text())
    lse = {}
    for k, v in lj.items():
        d = pd.DataFrame(v["rows"])
        lse[k] = pd.Series(d["value"].astype(float).to_numpy(), index=pd.to_datetime(d["date"]))
    bp = {}
    for c, iso in BIS_POL.items():
        f = RAW / "bis_cbpol" / f"D_{iso}.csv"
        d = pd.read_csv(f)
        if "OBS_VALUE" not in d.columns or d.empty:
            continue
        s = pd.Series(pd.to_numeric(d["OBS_VALUE"], errors="coerce").to_numpy(),
                      index=pd.to_datetime(d["TIME_PERIOD"])).dropna()
        bp[c] = s[s.index.dayofweek < 5]
    usd = pd.read_parquet(REPO / "data" / "cycle6" / "rates" / "short_rates_daily.parquet")
    usd = usd[usd.ccy == "USD"].set_index("date")[["rf_pct", "rf_source"]].sort_index()
    return o, lse, bp, usd


# ------------------------------------------------------------------ FX construction (cycle-6 build_fx logic)
def build_one(c, s, src, rf_c, usd):
    s = s.dropna()
    s = s[~s.index.duplicated()].sort_index()
    df = pd.DataFrame({"S": s})
    df["spot_ret"] = df.S.pct_change()
    df["dt"] = df.index.to_series().diff().dt.days / 365.0
    rc = rf_c.reindex(df.index)
    df["rf_ccy_pct"], df["rf_ccy_source"] = rc["rf_pct"], rc["rf_source"]
    df["rf_usd_pct"] = usd["rf_pct"].reindex(df.index)
    df["carry_diff_pct"] = df.rf_ccy_pct - df.rf_usd_pct
    df["excess_ret"] = df.spot_ret + df.carry_diff_pct / 100 * df.dt
    gb = np.r_[np.nan, np.busday_count(df.index[:-1].values.astype("datetime64[D]"),
                                       df.index[1:].values.astype("datetime64[D]")) - 1]
    df.loc[gb > 10, "excess_ret"] = np.nan
    df = df.iloc[1:].reset_index(names="date")
    dts = s.index.to_series().reset_index(drop=True)
    gaps = gap_scan(dts)
    flat_all = flat_runs(dts, s.reset_index(drop=True))
    start = df.date.min()
    if gaps:
        start = max(start, pd.Timestamp(gaps[-1]["to"]))
    if flat_all:
        nxt = s.index[s.index > pd.Timestamp(flat_all[-1]["to"])]
        start = max(start, nxt[0] if len(nxt) else s.index.max())
    used = df[df.date > start] if start > df.date.min() else df
    su = s[s.index >= start]
    fr = flat_runs(su.index.to_series().reset_index(drop=True), su.reset_index(drop=True))
    reasons, notes = [], []
    if fr:
        reasons.append(f"(c) {len(fr)} flat spot runs >=10bd, first {fr[0]}")
    if gaps or flat_all:
        notes.append(f"history truncated to {start.date()} (after last gap>10bd {gaps[-1] if gaps else None} / last "
                     f"flat spot run>=10bd {flat_all[-1] if flat_all else None}); STRICT full-history status would be "
                     f"FAIL ({len(gaps)} gaps, {len(flat_all)} flat runs)")
    ex = used.dropna(subset=["excess_ret"])
    notes.append(f"spot {src}; short-rate differential lagged 1 obs (daily) / previous-month OECD average")
    rfsrc = ex.rf_ccy_source.fillna("NONE").str.split(":").str[0].str.split("_").str[:2].str.join("_") \
        .value_counts().to_dict()
    notes.append(f"rf_ccy sources {rfsrc}; rows without rf (no excess return) {int(used.excess_ret.isna().sum())}")
    if len(ex):
        notes.append(f"max |daily spot ret| in used window {used.spot_ret.abs().max():.3f} on "
                     f"{used.loc[used.spot_ret.abs().idxmax(), 'date'].date()}")
    return used, ex, reasons, notes, start


def main():
    run_utc = dt.datetime.now(dt.timezone.utc).isoformat()
    h10 = pd.read_parquet(OLD / "fx_spot_daily.parquet")
    h10["date"] = pd.to_datetime(h10["date"])
    sp = spots(h10)
    o, lse, bp, usd = load_rates()
    reg, coarse_mm = R.build(EM + LEGACY + G10)
    reg.to_csv(OUT / "fx_regimes.csv", index=False)
    excl = {(r.ccy, r.month.to_period("M")) for r in reg[reg.exclude].itertuples()}
    cpi = pd.read_parquet(REPO / "data" / "cycle6" / "equity" / "cpi_monthly_pit.parquet")
    months_all = pd.date_range("1955-01-31", "2026-09-30", freq="ME")

    # cross-source check (disclosure only): H.10 vs BIS monthly spot returns where both exist
    xchk = {}
    for c in EM + LEGACY:
        a = bis_fx(c) if c in BIS_ISO2 else None
        b = h10[(h10.source == "fed_h10") & (h10.ccy == c)].set_index("date")["usd_per_ccy"] if c in EM else h10_hist(c)
        if a is None or len(b) == 0:
            continue
        b = b[~b.index.duplicated()]
        ma = a.resample("ME").last().pct_change(fill_method=None)
        mb = b.resample("ME").last().pct_change(fill_method=None)
        j = pd.concat([ma, mb], axis=1, join="inner").dropna()
        j = j[j.index >= DEEP_START]
        if len(j) > 12:
            xchk[c] = {"months": len(j), "rho": round(float(j.corr().iloc[0, 1]), 4),
                       "te_over_sigma_h10": round(float((j.iloc[:, 0] - j.iloc[:, 1]).std() / j.iloc[:, 1].std()), 4)}

    built = {}
    for c in EM + LEGACY:
        s, src = sp[c]
        rf_c = short_rate(c, o, lse, bp)
        used, ex, reasons, notes, start = build_one(c, s, src, rf_c, usd)
        built[c] = (used, ex, reasons, notes, start, src, rf_c)

    def assemble(ccys, deep: bool):
        rows, sig_fr, sig_sp, sig_cpi, cands = [], [], [], [], []
        for c in ccys:
            used, ex, reasons, notes, start, src, rf_c = built[c]
            mid = f"FX_{c}"
            e = ex[ex.date >= DEEP_START].copy()  # FRAMEWORK §1: FX before 1973 infeasible (both samples)
            per = e.date.dt.to_period("M")
            mask = np.array([(c, p) in excl for p in per], dtype=bool)
            n_masked_m = int(per[mask].nunique())
            e_in = e[~mask]
            # month-end signal rows from the construction (cycle-6 fx_carry_inputs_monthly logic)
            u = used[used.date >= DEEP_START]
            last = u.assign(m=u.date.dt.to_period("M")).groupby("m").tail(1)
            last = last[[(c, m) not in excl for m in last.date.dt.to_period("M")]]
            r = dict(qa=[], notes=list(notes))
            reasons2 = list(reasons)
            if e.empty:
                reasons2.append("no excess return (no spot and/or no point-in-time short rate in window)")
            elif e_in.empty:
                reasons2.append("excluded by cycle-7 FRAMEWORK §3 for the whole used history")
            status = "FAIL" if reasons2 else "PASS"
            if status == "PASS":
                lo, hi = e_in.date.min(), e_in.date.max()
                rows.append(e_in.assign(market_id=mid))
                l2 = last[(last.date >= lo) & (last.date <= hi)]
                sig_fr.append(pd.DataFrame({"date": l2.date, "market_id": mid,
                                            "v": [rf_c["rf_pct"].asof(d) / 100.0 for d in l2.date]}))
                sig_sp.append(pd.DataFrame({"date": l2.date, "market_id": mid, "v": l2.S.to_numpy()}))
                if c in CPI_CTRY and (cpi.country == CPI_CTRY[c]).any():
                    cs = pit_cpi_monthly(cpi, CPI_CTRY[c], months_all)
                    cs = cs[(cs.index >= l2.date.min() - pd.offsets.MonthEnd(0)) &
                            (cs.index <= l2.date.max() + pd.offsets.MonthEnd(0))]
                    cs = cs[[(c, m) not in excl for m in cs.index.to_period("M")]]
                    sig_cpi.append(pd.DataFrame({"date": cs.index, "market_id": mid, "v": cs.to_numpy()}))
            else:
                lo = hi = None
            cands.append({"class": "FX", "market_id": mid, "qa_status": status, "source_class": "FX", "tenor": "",
                          "economic_market": f"{c}/USD",
                          "construction": "daily spot + lagged short-rate differential (cycle-6 build_fx)",
                          "source": f"{src} + short rates", "first_date": str(lo.date()) if lo is not None else "",
                          "last_date": str(hi.date()) if hi is not None else "",
                          "n_months": int(e_in.date.dt.to_period("M").nunique()), "alias_of": "",
                          "use_note": ("FX-DEEP (>= 1973-03)" if deep else "FX-EM"),
                          "qa_reasons": "; ".join(reasons2),
                          "regime_masked_months_in_window": n_masked_m,
                          "ndf_only": c in R.NDF_ONLY,
                          "cpi_available": c in CPI_CTRY and (cpi.country == CPI_CTRY[c]).any(),
                          "spot_first_raw": str(sp[c][0].index.min().date()), "used_start": str(start.date()),
                          "notes": "; ".join(notes), "source_file": "research/cycle7/data_fx/build.py"})
        return rows, sig_fr, sig_sp, sig_cpi, pd.DataFrame(cands)

    record = {"built_at_utc": run_utc, "code_sha256": {p.name: sha(p) for p in Path(__file__).parent.glob("*.py")},
              "irr_coarse_sheet_mismatch_vs_fine_derived": coarse_mm, "h10_vs_bis_monthly_spot_check": xchk}
    for name, ccys, deep in (("eval", EM, False), ("eval_deep", LEGACY, True)):
        root = OUT / name
        for sub in ("panels", "signals", "series"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        rows, sfr, ssp, scpi, cands = assemble(ccys, deep)
        panel = long_frame(pd.concat(rows), "date", "market_id", "excess_ret")
        fr = long_frame(pd.concat(sfr), "date", "market_id", "v")
        spt = long_frame(pd.concat(ssp), "date", "market_id", "v")
        cp = long_frame(pd.concat(scpi), "date", "market_id", "v")
        if deep:  # cycle-6 G10 rows (cycle-6 eval values unchanged), >= 1973-03, §3 masked
            g = []
            for f, dst in (("panels/daily_excess_FX.parquet", "panel"),
                           ("signals/fx_foreign_rate_monthly.parquet", "fr"),
                           ("signals/fx_spot_monthly.parquet", "sp"), ("signals/fx_cpi_pit_monthly.parquet", "cpi")):
                x = pd.read_parquet(C6V / f)
                x = x[x.date >= DEEP_START]
                cc = x.market_id.str[3:]
                keep = [(a, b) not in excl for a, b in zip(cc, x.date.dt.to_period("M"))]
                g.append((dst, x[keep]))
            gd = dict(g)
            c6 = pd.read_csv(C6V / "candidate_list.csv")
            c6 = c6[c6["class"] == "FX"].copy()
            add = []
            for rr in c6.itertuples():
                p = gd["panel"][gd["panel"].market_id == rr.market_id]
                st = "PASS" if len(p) else "FAIL"
                add.append({"class": "FX", "market_id": rr.market_id, "qa_status": st, "source_class": "FX",
                            "tenor": "", "economic_market": rr.economic_market, "construction": rr.construction,
                            "source": rr.source + " (cycle-6 eval values)",
                            "first_date": str(p.date.min().date()) if len(p) else "",
                            "last_date": str(p.date.max().date()) if len(p) else "",
                            "n_months": int(p.date.dt.to_period("M").nunique()), "alias_of": "",
                            "use_note": "FX-DEEP cycle-6 G10 (>= 1973-03)",
                            "qa_reasons": "" if len(p) else "no unmasked cycle-6 rows >= 1973-03",
                            "regime_masked_months_in_window": None, "ndf_only": False, "cpi_available": True,
                            "spot_first_raw": "", "used_start": rr.first_date, "notes": "cycle-6 PASS row",
                            "source_file": "data/cycle6/.../cycle6_eval_v1/view/eval/candidate_list.csv"})
            cands = pd.concat([cands, pd.DataFrame(add)], ignore_index=True)
            panel = pd.concat([panel, gd["panel"]]).sort_values(["market_id", "date"]).reset_index(drop=True)
            fr = pd.concat([fr, gd["fr"]]).sort_values(["market_id", "date"]).reset_index(drop=True)
            spt = pd.concat([spt, gd["sp"]]).sort_values(["market_id", "date"]).reset_index(drop=True)
            cp = pd.concat([cp, gd["cpi"]]).sort_values(["market_id", "date"]).reset_index(drop=True)
        panel.to_parquet(root / "panels" / "daily_excess_FX.parquet", index=False)
        fr.to_parquet(root / "signals" / "fx_foreign_rate_monthly.parquet", index=False)
        spt.to_parquet(root / "signals" / "fx_spot_monthly.parquet", index=False)
        cp.to_parquet(root / "signals" / "fx_cpi_pit_monthly.parquet", index=False)
        for f in ("usd_rate_3m_monthly.parquet", "cpi_us_pit_monthly.parquet"):
            shutil.copyfile(C6V / "series" / f, root / "series" / f)  # cycle-6 bytes
        cands = cands.sort_values("market_id").reset_index(drop=True)
        cands.to_csv(root / "candidate_list.csv", index=False)
        record[name] = {"files": {str(p.relative_to(root)): {"sha256": sha(p)} for p in sorted(root.rglob("*"))
                                  if p.is_file() and p.suffix in (".parquet", ".csv")},
                        "candidates": cands[["market_id", "qa_status", "first_date", "last_date", "n_months",
                                             "qa_reasons"]].to_dict("records")}
        print(name)
        print(cands[["market_id", "qa_status", "first_date", "last_date", "n_months",
                     "regime_masked_months_in_window", "cpi_available", "qa_reasons"]].to_string())
    completeness(record, run_utc)
    return record


def completeness(record, run_utc):
    ep = {}
    for f in sorted((RAW / "bis_xru_d").glob("*.csv")):
        d = pd.read_csv(f, usecols=["TIME_PERIOD"])
        ep[f"bis_xru_d/{f.name}"] = {"url": f"https://stats.bis.org/api/v1/data/WS_XRU/D.{f.stem[2:]}..A/all?format=csv",
                                     "retrieved_at_utc": mtime(f), "sha256": sha(f), "rows": len(d),
                                     "first": d.TIME_PERIOD.min(), "last": d.TIME_PERIOD.max()}
    for f in sorted((RAW / "bis_cbpol").glob("*.csv")):
        d = pd.read_csv(f)
        ep[f"bis_cbpol/{f.name}"] = {"url": f"https://stats.bis.org/api/v1/data/WS_CBPOL/D.{f.stem[2:]}/all?format=csv",
                                     "retrieved_at_utc": mtime(f), "sha256": sha(f), "rows": len(d),
                                     "first": d.TIME_PERIOD.min() if "TIME_PERIOD" in d else None,
                                     "last": d.TIME_PERIOD.max() if "TIME_PERIOD" in d else None}
    for f in sorted((RAW / "fed_h10_hist").glob("*.htm")):
        ep[f"fed_h10_hist/{f.name}"] = {"url": f"https://www.federalreserve.gov/releases/h10/hist/{f.name}",
                                        "retrieved_at_utc": mtime(f), "sha256": sha(f)}
    for f in sorted((RAW / "irr").glob("*.xlsx")) + sorted((RAW / "areaer").glob("*.pdf")):
        ep[str(f.relative_to(RAW))] = {"url": {"irr": "https://www.ilzetzki.com/irr-data (linked xlsx)",
                                               "areaer": "https://www.elibrary.imf.org/fileasset/downloads/"
                                                         + f.name}[f.parent.name],
                                       "retrieved_at_utc": mtime(f), "sha256": sha(f)}
    lr = json.loads((RAW / "lse_mcp" / "lse_pull_record.json").read_text())
    ep["lse_mcp/lse_macro_series.json"] = {"tool": lr["tool"], "retrieved_at_utc": lr["collected_utc"],
                                           "sha256": sha(RAW / "lse_mcp" / "lse_macro_series.json"),
                                           "coverage": lr["coverage"]}
    for f in ("fx_spot_daily.parquet", "oecd_monthly.parquet"):
        ep[f"core_premia processed/{f}"] = {"path": str((OLD / f).relative_to(REPO)), "sha256": sha(OLD / f),
                                            "note": "same file cycle 6 used (fetched 2026-09-26; raw manifests "
                                                    "data/core_premia/rates_fx_eq/raw/{fed_h10,oecd_sdmx})"}
    for f in ("data/cycle6/equity/cpi_monthly_pit.parquet", "data/cycle6/rates/short_rates_daily.parquet"):
        ep[f] = {"sha256": sha(REPO / f), "note": "cycle-6 data pass output reused unchanged"}
    ep["blocked_or_unavailable"] = {
        "data-api.ecb.europa.eu": "connection refused by sandbox proxy (needs owner); not required (BIS used)",
        "api.imf.org / elibrary-areaer.imf.org": "unreachable (needs owner); AREAER 2023 overview PDF used instead",
        "www.imf.org AREAER page": "HTTP 403",
        "AREAER overview PDFs 2020-2022, 2024, 2025 at elibrary.imf.org/fileasset/downloads/AEIEA{y}001-S001.pdf":
            "not found (HTML stub)",
        "fred.stlouisfed.org DEX{GE,FR,IT,NE,BE,SP}US": "no daily legacy series (monthly EX*US only); H.10 hist used",
        "BIS WS_CBPOL D.TW": "no data", "ALFRED": "reachable, but only US vintages; foreign CPI first releases "
                                                 "unavailable free -> latest vintage + default_2m (cycle-6 rule)"}
    for name in ("eval", "eval_deep"):
        (OUT / name / "completeness.json").write_text(json.dumps(
            {"written_utc": run_utc, "endpoints": ep, "build": record.get(name, {}),
             "record": {k: v for k, v in record.items() if k not in ("eval", "eval_deep")}},
            indent=1, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
