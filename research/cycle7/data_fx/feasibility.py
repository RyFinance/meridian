"""Cycle-7 FX feasibility counts from DATA AVAILABILITY ONLY (mirrors research/cycle6/feasibility_counts.py).

Counts, per FX spec, the months at which >= 4 PASS instruments are eligible after the spec's warm-up, using only
non-missing masks of the built (already §3-masked) eval files. No return/signal value enters any decision.
  XSMOM : months t-11..t-1 all have a return
  VAL-FX: spot and foreign CPI at t and t-66..t-54, US CPI likewise
  CARRY : foreign rate at t and US rate at t
  SEAS  : >= 1 same-calendar-month return among lags 12k-1 (k=1..20), >= 12 returns in the trailing 36 months,
          class-vol: >= 12 earlier held months in the last 120
FX-EM window: all months. FX-DEEP window: 1973-03 <= t < spec's cycle-6 first defined month (FRAMEWORK §2).
Feasible iff defined months >= 24 (cycle-7 FRAMEWORK §2).
Run: PYTHONPATH=. .venv/bin/python -m research.cycle7.data_fx.feasibility
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from research.cycle6 import feasibility_counts as F
from research.cycle6.engine import io as eio

ROOT = Path(__file__).resolve().parents[3] / "data" / "cycle7" / "fx"
DEEP_END = {"XSMOM-FX": "1975-08", "VAL-FX": "1980-03", "CARRY-FX": "1974-09", "SEAS-FX": "1976-08"}


def run(sub: str) -> dict:
    root = ROOT / sub
    cands = pd.read_csv(root / "candidate_list.csv")
    ids = eio.universe(cands, "FX")
    rd = lambda rel: eio.long_to_wide(eio.read_long(root, rel, ids), ids)  # noqa: E731
    d = rd("panels/daily_excess_FX.parquet").dropna(how="all")
    mh = F.month_has(d)
    months = mh.index
    out = {}
    n = F.all_true(mh, range(1, 12)).sum(axis=1)
    out["XSMOM-FX"] = n
    cntm = sum(mh.shift(12 * k - 1, fill_value=False).astype(int) for k in range(1, 21))
    svol = mh.astype(int).rolling(36, min_periods=1).sum() >= 12
    n = ((cntm >= 1) & svol).sum(axis=1)
    held = (n >= 4).shift(1, fill_value=False).astype(int)
    n = n.where(held.rolling(120, min_periods=1).sum() >= 12, 0)
    out["SEAS-FX"] = n
    spot = F.to_month(rd("signals/fx_spot_monthly.parquet"), months).reindex(columns=ids, fill_value=False)
    cpi = F.to_month(rd("signals/fx_cpi_pit_monthly.parquet"), months).reindex(columns=ids, fill_value=False)
    cus = eio.read_long(root, "series/cpi_us_pit_monthly.parquet").dropna()
    cus_m = pd.Series(True, index=cus.date.dt.to_period("M")).groupby(level=0).any().reindex(months, fill_value=False)
    ok = spot & cpi & pd.DataFrame({c: cus_m for c in ids})
    out["VAL-FX"] = (ok & F.all_true(ok, range(54, 67))).sum(axis=1)
    fr = F.to_month(rd("signals/fx_foreign_rate_monthly.parquet"), months).reindex(columns=ids, fill_value=False)
    us = eio.read_long(root, "series/usd_rate_3m_monthly.parquet").dropna()
    us_m = pd.Series(True, index=us.date.dt.to_period("M")).groupby(level=0).any().reindex(months, fill_value=False)
    out["CARRY-FX"] = fr.mul(us_m, axis=0).astype(bool).sum(axis=1)
    res = {}
    for k, n in out.items():
        n = n[n.index >= pd.Period("1973-03", "M")]
        if sub == "eval_deep":
            n = n[n.index < pd.Period(DEEP_END[k], "M")]
        s = F.summary(n, 4)
        s["feasible"] = s["defined_months"] >= 24
        s["n_pass_instruments"] = len(ids)
        res[k] = s
    return res


if __name__ == "__main__":
    allr = {"FX-EM": run("eval"), "FX-DEEP": run("eval_deep")}
    (ROOT / "feasibility_counts.json").write_text(json.dumps(allr, indent=1, sort_keys=True))
    for s, r in allr.items():
        for k, v in r.items():
            print(s, k, json.dumps(v))
