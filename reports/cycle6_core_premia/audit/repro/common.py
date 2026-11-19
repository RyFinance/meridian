"""Independent re-implementation (audit) -- shared data access and accounting.

Written from the cycle-6 spec text only (FRAMEWORK.md, ADDENDUM-1, specs/*.md, A5-C1). Does NOT import any builder
module (research/cycle6/engine/*). Reads the frozen snapshot view directly with pandas.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/rytty/CCP/quant_v7")
SNAP = ROOT / "data/cycle6/snapshot_store/versions/cycle6_eval_v1"
VIEW = SNAP / "view"
OUT = ROOT / "reports/cycle6_core_premia/audit/repro"
BUILDER = ROOT / "reports/cycle6_core_premia"
MANIFEST_SHA = "ba67379be094135e32557468710a078ea9ac6f0d87516fef331e7788b22d29be"


def verify_snapshot() -> dict:
    m = json.loads((SNAP / "manifest.json").read_text())
    canon = hashlib.sha256(json.dumps(m["payload"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    file_sha = hashlib.sha256((SNAP / "manifest.json").read_bytes()).hexdigest()
    bad = []
    for r in m["payload"]["records"]:
        h = hashlib.sha256((VIEW / r["key"]).read_bytes()).hexdigest()
        if h != r["sha256"]:
            bad.append(r["key"])
    return {"embedded_manifest_sha256": m["manifest_sha256"], "canonical_payload_sha256": canon,
            "manifest_file_sha256": file_sha, "ledger_sha256": MANIFEST_SHA,
            "n_records": len(m["payload"]["records"]), "bad_files": bad}


def read_long(rel: str) -> pd.DataFrame:
    d = pd.read_parquet(VIEW / rel)
    d["date"] = pd.to_datetime(d["date"])
    return d


def wide(rel: str, ids=None) -> pd.DataFrame:
    d = read_long(rel)
    if ids is not None:
        d = d[d.market_id.isin(ids)]
    return d.pivot(index="date", columns="market_id", values="value").sort_index()


def monthly_signal(rel: str, ids=None) -> pd.DataFrame:
    """Monthly signal panel indexed by calendar month period (obs date -> its month)."""
    d = read_long(rel)
    if ids is not None:
        d = d[d.market_id.isin(ids)]
    d["month"] = d.date.dt.to_period("M")
    if d.duplicated(["month", "market_id"]).any():
        raise ValueError(rel + " duplicate (month, market)")
    return d.pivot(index="month", columns="market_id", values="value").sort_index()


def universe(cls: str) -> list[str]:
    c = pd.read_csv(VIEW / "eval/candidate_list.csv")
    c = c[(c["class"] == cls) & (c.qa_status == "PASS")]
    c = c[c.alias_of.isna()]
    return sorted(c.market_id.tolist())


def calendar_monthly(daily: pd.DataFrame) -> pd.DataFrame:
    """Calendar-month compounded excess return; NaN if no valid day in the month."""
    g = (1 + daily).groupby(daily.index.to_period("M"))
    prod = g.prod(min_count=1)
    return prod - 1


def net_period_returns(daily: pd.DataFrame) -> pd.DataFrame:
    """R[m, i] = return from close of i's first trading day of month m to close of i's first trading day of m+1.
    If m+1 has no data for i (end of sample / gap), use the last valid close available before the first day
    of m+2 (partial period). NaN if i has no trading day in m."""
    out = {}
    for c in daily.columns:
        s = daily[c].dropna()
        if s.empty:
            continue
        W = (1 + s).cumprod()
        per = s.index.to_period("M")
        first = pd.Series(s.index, index=s.index).groupby(per).min()
        res = {}
        months = first.index
        for m in months:
            f0 = first[m]
            nxt = m + 1
            if nxt in first.index:
                f1 = first[nxt]
            else:
                # no trading day in m+1: hold to last valid close before month m+2
                end = (m + 2).start_time
                cand = s.index[s.index < end]
                f1 = cand[-1]
            res[m] = W[f1] / W[f0] - 1
        out[c] = pd.Series(res)
    return pd.DataFrame(out).sort_index()


def run_book(weights: dict, cal_ret: pd.DataFrame, per_ret: pd.DataFrame, bp: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """weights: {signal_month Period: Series(market->weight)}. Gross: hold calendar month t+1 (no cost).
    Net: hold net period t+1 (first trading day t+1 -> first trading day t+2), cost bp per side on
    sum |w_new - w_drifted|."""
    gross_rows, net_rows = [], []
    prev_drift = pd.Series(dtype=float)
    last_m = None
    for t in sorted(weights):
        w = weights[t].astype(float)
        h = t + 1
        # gross
        rc = cal_ret.reindex(index=[h], columns=w.index).iloc[0] if h in cal_ret.index else pd.Series(np.nan, index=w.index)
        unp_g = int(rc.isna().sum())
        gross_rows.append({"month": str(h), "ret": float((w * rc.fillna(0)).sum()), "n_held": int((w != 0).sum() if True else 0),
                           "unpriced": unp_g})
        # net
        rp = per_ret.reindex(index=[h], columns=w.index).iloc[0] if h in per_ret.index else pd.Series(np.nan, index=w.index)
        unp = int(rp.isna().sum())
        rp0 = rp.fillna(0.0)
        if last_m is not None and last_m != t - 0 and last_m != t:
            pass
        idx = w.index.union(prev_drift.index)
        turnover = float((w.reindex(idx, fill_value=0) - prev_drift.reindex(idx, fill_value=0)).abs().sum())
        cost = bp * 1e-4 * turnover
        rb = float((w * rp0).sum())
        net_rows.append({"month": str(h), "ret": rb - cost, "ret_before_cost": rb, "cost": cost, "turnover": turnover,
                         "net_exposure": float(w.sum()), "gross_exposure": float(w.abs().sum()),
                         "n_held": int(len(w)), "unpriced": unp})
        prev_drift = w * (1 + rp0) / (1 + rb)
        last_m = t
    return pd.DataFrame(gross_rows), pd.DataFrame(net_rows)


def avg_rank_weights(sig: pd.Series) -> pd.Series:
    """AMP Eq.1 / KMVP Eq.19: c(rank - mean rank), average ranks for ties, $1 long / $1 short."""
    r = sig.rank(method="average")
    x = r - r.mean()
    s = x.abs().sum()
    if s == 0:
        return x * 0.0
    return x * 2.0 / s
