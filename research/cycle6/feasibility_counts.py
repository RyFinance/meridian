"""Cycle-6 feasibility counts from DATA AVAILABILITY ONLY (FRAMEWORK §1).

Reads the frozen snapshot view and counts, per menu component, the months at which at least 3 (TSMOM) or
4 (rank styles) instruments are eligible after that style's warm-up. Only non-missing masks and observation
counts are used; no return value, signal value, vol value or beta value enters any decision (BAB's beta > 0
condition is therefore not evaluated). Mirrors the engine's eligibility logic:
  TSMOM  : >= 756 valid daily obs through month-end t (vol min_obs) AND months t-11..t all have a return
  XSMOM  : months t-11..t-1 all have a return (12/1)
  VAL rev: cumulative excess-return level exists at t-66 (engine level_from_returns + 54..66 window)
  VAL-FX : spot and foreign CPI at t and t-66..t-54, US CPI likewise
  VAL-FI : 10y yield at t and t-60
  CARRY  : carry input(s) at t
  SEAS   : BSV construction: >= 1 same-calendar-month return among lags 12k-1 (k=1..20), >= 12 returns in the
           trailing 36 months (sizing vol), and >= 12 earlier held class months in the last 120 (class vol)
  BAB-FI : FP monthly: 12 of 12 months (vol) and >= 36 of 60 months paired with the EW universe (corr)
  BAB-EQ : >= 120 valid daily obs in the last 252 union-index rows AND >= 750 valid overlapping 3-day pairs
           with the benchmark in the last 1260 rows, on some day of month t
Usage: python -m research.cycle6.feasibility_counts <snapshot_view_root> [out.json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from research.cycle6.engine import io as eio

FLOOR = 120


def wide(root, rel, ids=None):
    return eio.read_wide(root, rel, ids)


def month_has(daily: pd.DataFrame) -> pd.DataFrame:
    per = daily.index.to_period("M")
    m = daily.notna().groupby(per).any()
    return m.reindex(pd.period_range(per.min(), per.max(), freq="M"), fill_value=False)


def to_month(df: pd.DataFrame, months) -> pd.DataFrame:
    per = df.index.to_period("M")
    return df.notna().groupby(per).any().reindex(months, fill_value=False)


def all_true(mask: pd.DataFrame, lags) -> pd.DataFrame:
    out = None
    for L in lags:
        s = mask.shift(L, fill_value=False)
        out = s if out is None else (out & s)
    return out


def summary(n: pd.Series, k: int, cutoff: str | None = None) -> dict:
    ok = n >= k
    d = {"threshold": k, "defined_months": int(ok.sum()),
         "first_defined": str(n.index[ok.argmax()]) if ok.any() else None,
         "last_defined": str(n.index[::-1][ok[::-1].argmax()]) if ok.any() else None,
         "max_eligible": int(n.max()) if len(n) else 0}
    if cutoff:
        d["defined_months_post_pub"] = int(ok[n.index >= pd.Period(cutoff, "M")].sum())
    return d


def coverage(n: pd.Series, k: int, start: str, end: str) -> dict:
    """Months of the paper sample on which the class portfolio would hold positions (signal defined at t-1)."""
    ok = (n >= k).shift(1, fill_value=False)
    rng = pd.period_range(start, end, freq="M")
    got = int(ok.reindex(rng, fill_value=False).sum())
    return {"paper_sample": f"{start}..{end}", "paper_months": len(rng), "held_months": got,
            "coverage": round(got / len(rng), 3)}


def bench_overlap(n: pd.Series, k: int, bench: pd.Series) -> int:
    ok = (n >= k).shift(1, fill_value=False)
    b = bench.dropna()
    bm = set(b.index)
    return int(sum(1 for m in ok.index[ok.to_numpy()] if m in bm))


def main(root: str) -> dict:
    root = Path(root)
    cands = eio.load_candidates(root, root / "eval" / "candidate_list.csv")
    P = {"EQ": "eval/panels/daily_excess_EQ.parquet", "FI": "eval/panels/daily_excess_FI10.parquet",
         "FI_UST": "eval/panels/daily_excess_FI_UST.parquet", "FX": "eval/panels/daily_excess_FX.parquet",
         "CM": "eval/panels/daily_excess_CM.parquet"}
    daily = {c: wide(root, p, eio.universe(cands, c)).dropna(how="all") for c, p in P.items()}
    aqr_t = eio.read_long(root, "eval/series/aqr_tsmom_monthly.parquet")
    aqr_v = eio.read_long(root, "eval/series/aqr_vme_monthly.parquet")
    aqr_c = eio.read_long(root, "eval/series/aqr_century_monthly.parquet")

    def ser(df, mid):
        s = df[df.market_id == mid].set_index("date")["value"]
        s.index = s.index.to_period("M")
        return s

    out = {}
    cut = {"TSMOM": "2011-01", "XSMOM": "2009-04", "VAL": "2009-04", "CARRY": "2013-09", "BAB": "2011-01"}
    seas_cut = {"EQ": "2015-01", "CM": "2015-01", "FI": "2019-02", "FX": "2019-02"}
    tsm_col = {"EQ": "TSMOM^EQ", "FI": "TSMOM^FI", "FX": "TSMOM^FX", "CM": "TSMOM^CM"}
    vme = {"EQ": "EQ", "FI": "FI", "FX": "FX", "CM": "COM"}
    for cls in ("EQ", "FI", "FX", "CM"):
        d = daily[cls]
        mh = month_has(d)
        months = mh.index
        # TSMOM
        cnt = d.notna().cumsum().where(d.notna())
        vol_ok = to_month((cnt >= 756).where(d.notna()).replace(False, np.nan), months)
        n = (all_true(mh, range(0, 12)) & vol_ok).sum(axis=1)
        r = summary(n, 3, cut["TSMOM"])
        r["aqr_overlap_months"] = bench_overlap(n, 3, ser(aqr_t, tsm_col[cls]))
        out[f"TSMOM-{cls}"] = r
        # XSMOM
        n = all_true(mh, range(1, 12)).sum(axis=1)
        r = summary(n, 4, cut["XSMOM"])
        r["aqr_overlap_months"] = bench_overlap(n, 4, ser(aqr_v, f"MOMLS_VME_{vme[cls]}"))
        out[f"XSMOM-{cls}"] = r
        # SEAS, BSV construction: >= 1 same-month obs in 20y, sizing vol needs >= 12 returns in the last 36
        # months, class vol target (strategy_realised) needs >= 12 earlier held months within the last 120
        cntm = sum(mh.shift(12 * k - 1, fill_value=False).astype(int) for k in range(1, 21))
        svol = mh.astype(int).rolling(36, min_periods=1).sum() >= 12
        n = ((cntm >= 1) & svol).sum(axis=1)
        held = (n >= 4).shift(1, fill_value=False).astype(int)
        cls_ok = held.rolling(120, min_periods=1).sum() >= 12
        n = n.where(cls_ok, 0)
        r = summary(n, 4, seas_cut[cls])
        r["bsv_table2"] = coverage(n, 4, "1981-01", "2011-12")
        out[f"SEAS-{cls}"] = r
    # VAL
    for cls in ("EQ", "CM"):
        mh = month_has(daily[cls])
        started = mh.cummax()
        n = started.shift(66, fill_value=False).sum(axis=1)
        r = summary(n, 4, cut["VAL"])
        r["aqr_overlap_months"] = bench_overlap(n, 4, ser(aqr_v, f"VALLS_VME_{vme[cls]}"))
        out[f"VAL-{cls}"] = r
    months = month_has(daily["FX"]).index
    ids = eio.universe(cands, "FX")
    spot = to_month(wide(root, "eval/signals/fx_spot_monthly.parquet", ids), months).reindex(columns=ids,
                                                                                            fill_value=False)
    cpi = to_month(wide(root, "eval/signals/fx_cpi_pit_monthly.parquet", ids), months).reindex(columns=ids,
                                                                                              fill_value=False)
    cus = eio.read_series(root, {"path": "eval/series/cpi_us_pit_monthly.parquet", "market_id": "US_CPI"})
    cus_m = pd.Series(True, index=cus.dropna().index.to_period("M")).reindex(months, fill_value=False)
    cus_df = pd.DataFrame({c: cus_m for c in ids})
    ok = spot & cpi & cus_df
    n = (ok & all_true(ok, range(54, 67))).sum(axis=1)
    r = summary(n, 4, cut["VAL"])
    r["aqr_overlap_months"] = bench_overlap(n, 4, ser(aqr_v, "VALLS_VME_FX"))
    out["VAL-FX"] = r
    months = month_has(daily["FI"]).index
    ids = eio.universe(cands, "FI")
    y = to_month(wide(root, "eval/signals/fi10_yield_monthly.parquet", ids), months).reindex(columns=ids,
                                                                                             fill_value=False)
    n = (y & y.shift(60, fill_value=False)).sum(axis=1)
    r = summary(n, 4, cut["VAL"])
    r["aqr_overlap_months"] = bench_overlap(n, 4, ser(aqr_v, "VALLS_VME_FI"))
    out["VAL-FI"] = r
    # CARRY
    cy = to_month(wide(root, "eval/signals/fi10_carry_monthly.parquet", ids), months).reindex(columns=ids,
                                                                                              fill_value=False)
    n = cy.sum(axis=1)
    r = summary(n, 4, cut["CARRY"])
    r["kmvp_table2"] = coverage(n, 4, "1983-11", "2012-09")
    r["century_overlap_months"] = bench_overlap(n, 4, ser(aqr_c, "Fixed income Carry"))
    out["CARRY-FI"] = r
    months = month_has(daily["FX"]).index
    ids = eio.universe(cands, "FX")
    fr = to_month(wide(root, "eval/signals/fx_foreign_rate_monthly.parquet", ids), months).reindex(
        columns=ids, fill_value=False)
    us = eio.read_series(root, {"path": "eval/series/usd_rate_3m_monthly.parquet", "market_id": "USD_RF_3M"})
    us_m = pd.Series(True, index=us.dropna().index.to_period("M")).reindex(months, fill_value=False)
    n = fr.mul(us_m, axis=0).astype(bool).sum(axis=1)
    r = summary(n, 4, cut["CARRY"])
    r["kmvp_table2"] = coverage(n, 4, "1983-11", "2012-09")
    r["century_overlap_months"] = bench_overlap(n, 4, ser(aqr_c, "Currencies Carry"))
    out["CARRY-FX"] = r
    out["CARRY-CM"] = {"threshold": 4, "defined_months": 0, "max_eligible": 2,
                       "note": "energy-only universe (CM_WTI, CM_NATGAS) < 4 assets; ADDENDUM-1 item 6"}
    # BAB
    bench = eio.read_long(root, "eval/series/bab_benchmarks_daily.parquet")
    for cls, bid, dkey in (("EQ", "BAB_BENCH_EQ_EW", "EQ"),):
        d = daily[dkey]
        b = bench[bench.market_id == bid].set_index("date")["value"].reindex(d.index)
        v = d.notna()
        bv = b.notna()
        sd_ok = v.rolling(252, min_periods=1).sum() >= 120
        sdm_ok = bv.rolling(252, min_periods=1).sum() >= 120
        r3 = v.rolling(3, min_periods=1).sum() == 3
        b3 = bv.rolling(3, min_periods=1).sum() == 3
        pairs = r3.mul(b3, axis=0).rolling(1260, min_periods=1).sum() >= 750
        ok = sd_ok & pairs
        ok = ok.mul(sdm_ok, axis=0).astype(bool)
        months = month_has(d).index
        n = to_month(ok.replace(False, np.nan), months).sum(axis=1)
        r = summary(n, 4, cut["BAB"])
        if cls == "EQ":
            r["aqr_overlap_months"] = bench_overlap(n, 4, ser(aqr_c, "Equity indices Defensive"))
        else:
            r["fp_table6"] = coverage(n, 4, "1952-01", "2012-03")
        out[f"BAB-{cls}"] = r
    # BAB-FI: FP monthly method (12m vol >= 12 obs, 60m corr >= 36 obs, EW universe benchmark)
    mh = month_has(daily["FI_UST"])
    bm = mh.any(axis=1)
    vol_ok = mh.astype(int).rolling(12, min_periods=1).sum() >= 12
    bvol_ok = bm.astype(int).rolling(12, min_periods=1).sum() >= 12
    pairs = mh.mul(bm, axis=0).astype(int).rolling(60, min_periods=1).sum() >= 36
    n = (vol_ok & pairs).mul(bvol_ok, axis=0).astype(bool).sum(axis=1)
    r = summary(n, 4, cut["BAB"])
    r["fp_table6"] = coverage(n, 4, "1952-01", "2012-03")
    out["BAB-FI"] = r
    for k, r in out.items():
        r["feasible"] = r["defined_months"] >= FLOOR
    return out


if __name__ == "__main__":
    res = main(sys.argv[1])
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(json.dumps(res, indent=1, sort_keys=True))
    for k, v in sorted(res.items()):
        print(k, json.dumps(v))
