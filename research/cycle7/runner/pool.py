"""FRAMEWORK §5 pooling and the NEW-SAMPLE POSITIVE rule, per spec, over its run outputs.

  python -m research.cycle7.runner.pool --runs-root reports/cycle7_new_samples/runs \
      --out reports/cycle7_new_samples/pooled.json

Inputs per sample i (a run directory holding metrics.json + active.csv with an 'ok' trial-ledger row for the same
sample hash and a metrics n >= 24): S_i, SE_i = the A4 influence-function monthly Sharpe and SE (metrics
active.se_if), p_i(seed) = calibrated p per seed offset, the window active series and its cost-multiplied twin.
- w_i = 1/SE_i^2; pooled S = sum w_i S_i / sum w_i (monthly; x sqrt 12 annualised). se_pool_indep = 1/sqrt(sum w).
- z_i = Phi^-1(1 - p_i), p_i clipped to [1/(B+1), B/(B+1)] (the attainable calibrated-p range; p = 1 would be
  -inf). c_i = 1/SE_i; R_ij = Pearson correlation of the active series on common months if >= 24 common months,
  else 0; R_ii = 1. Z = sum c_i z_i / sqrt(c' R c); p_pool = 1 - Phi(Z). One sample: p_pool = p_1 exactly.
- pooled series (month t): sum_{i present at t} w_i a_{i,t} / sum_{i present at t} w_i.
- POSITIVE iff p_pool < 0.05/k for EVERY seed AND mean(pooled cost-multiplied active) > 0 AND best-year share of
  positive P&L of the pooled active series <= 0.40. Crash-declared specs: flag if any sample with n < 120 has a
  95% calibrated Sharpe CI containing 0 (disclosure only). k: the single Kind='k' row of the cycle-7 ledger.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from research.cycle6.engine.component import _clean

from . import common
from .common import GuardError
from .evaluate import best_year_share

MIN_COMMON = 24


def pooled_estimate(S, SE) -> dict:
    S, SE = np.asarray(S, float), np.asarray(SE, float)
    if (SE <= 0).any() or not np.isfinite(SE).all():
        raise ValueError("SE_i must be positive and finite")
    w = 1.0 / SE ** 2
    est = float((w * S).sum() / w.sum())
    return {"sharpe_m": est, "sharpe_ann": est * math.sqrt(12), "weights": (w / w.sum()).tolist(),
            "se_pool_indep_m": float(1.0 / math.sqrt(w.sum()))}


def corr_matrix(series: list[pd.Series], min_common: int = MIN_COMMON) -> np.ndarray:
    k = len(series)
    R = np.eye(k)
    for i in range(k):
        for j in range(i + 1, k):
            d = pd.concat([series[i].rename("a"), series[j].rename("b")], axis=1).dropna()
            r = float(d["a"].corr(d["b"])) if len(d) >= min_common else 0.0
            R[i, j] = R[j, i] = 0.0 if not np.isfinite(r) else r
    return R


def stouffer(p, SE, R, B=None) -> dict:
    p = np.asarray(p, float)
    SE = np.asarray(SE, float)
    if len(p) == 1:
        return {"p_pool": float(p[0]), "Z": float(stats.norm.isf(p[0])), "single": True}
    if B is not None:
        B = np.asarray(B, float)
        p = np.clip(p, 1.0 / (B + 1.0), B / (B + 1.0))
    z = stats.norm.isf(p)
    c = 1.0 / SE
    q = float(c @ np.asarray(R, float) @ c)
    if q <= 0:
        return {"p_pool": None, "Z": None, "note": "c'Rc <= 0 (R not PSD on these overlaps)"}
    Z = float((c * z).sum() / math.sqrt(q))
    return {"p_pool": float(stats.norm.sf(Z)), "Z": Z, "z": z.tolist(), "cRc": q}


def pooled_series(series: list[pd.Series], w) -> pd.Series:
    df = pd.concat([s.rename(i) for i, s in enumerate(series)], axis=1).sort_index()
    W = pd.DataFrame(np.broadcast_to(np.asarray(w, float), df.shape), index=df.index, columns=df.columns)
    W = W.where(df.notna())
    return (df.fillna(0.0) * W.fillna(0.0)).sum(axis=1) / W.sum(axis=1)


def _read_active(d: Path) -> pd.DataFrame:
    a = pd.read_csv(d / "active.csv", index_col=0)
    a.index = pd.PeriodIndex(a.index.astype(str), freq="M")
    return a


def load_runs(runs_root: Path) -> tuple[dict, list]:
    trials = common.read_trials()
    by_spec, skipped = {}, []
    for mp in sorted(Path(runs_root).glob("*/metrics.json")):
        m = json.loads(mp.read_text())
        run = m.get("run", {})
        ok = [t for t in trials if t.get("status") == "ok" and t.get("sample_sha256") == run.get("sample_sha256")
              and t.get("spec_id") == m.get("spec_id") and t.get("sample_id") == m.get("sample_id")]
        if not ok:
            skipped.append({"dir": mp.parent.name, "reason": "no ok trial-ledger row for this sample hash"})
            continue
        if not m.get("feasible_min24"):
            skipped.append({"dir": mp.parent.name, "reason": "fewer than 24 months (infeasible)"})
            continue
        by_spec.setdefault(m["spec_id"], []).append({"metrics": m, "active": _read_active(mp.parent),
                                                     "dir": mp.parent.name})
    return by_spec, skipped


def pool_spec(runs: list[dict], k: int) -> dict:
    S = [r["metrics"]["active"]["se_if"]["sharpe_m"] for r in runs]
    SE = [r["metrics"]["active"]["se_if"]["se_sharpe_m"] for r in runs]
    est = pooled_estimate(S, SE)
    act = [r["active"]["active"].dropna() for r in runs]
    ccol = [c for c in runs[0]["active"].columns if c.startswith("active_cost")]
    if len(ccol) != 1 or any(ccol[0] not in r["active"].columns for r in runs):
        raise ValueError("cost-sensitivity column missing or inconsistent across samples")
    act_c = [r["active"][ccol[0]].dropna() for r in runs]
    R = corr_matrix(act)
    offsets = [s["offset"] for s in runs[0]["metrics"]["seeds"]]
    per_seed = []
    for j, off in enumerate(offsets):
        ps, Bs = [], []
        for r in runs:
            sd = r["metrics"]["seeds"][j]
            if sd["offset"] != off:
                raise ValueError("seed offsets differ across samples")
            ps.append(sd["p"]["p"])
            Bs.append(sd["p"]["B"])
        st = stouffer(ps, SE, R, Bs)
        per_seed.append({"offset": off, "p_i": ps, **st})
    w = 1.0 / np.asarray(SE, float) ** 2
    pa = pooled_series(act, w)
    pc = pooled_series(act_c, w)
    by = best_year_share(pa)
    alpha = 0.05 / k
    crash = any(r["metrics"].get("crash_declared") for r in runs)
    flags = []
    if crash:
        for r in runs:
            m = r["metrics"]
            ci95 = m["active"].get("ci_95", {}).get("sharpe_ann")
            if m["n_months"] < 120 and ci95 and ci95["lo"] <= 0 <= ci95["hi"]:
                flags.append(r["dir"])
    gate_i = all(x.get("p_pool") is not None and x["p_pool"] < alpha for x in per_seed)
    gate_ii = bool(len(pc) and pc.mean() > 0)
    gate_iii = by.get("share") is not None and by["share"] <= 0.40
    return {"samples": [r["dir"] for r in runs], "n_months": [r["metrics"]["n_months"] for r in runs],
            "S_i_m": S, "SE_i_m": SE, "pooled": est, "R": R.tolist(), "per_seed": per_seed,
            "pooled_active": {"n": int(pa.notna().sum()), "mean_m": float(pa.mean()) if len(pa) else None,
                              "best_year_share_positive_pnl": by},
            "pooled_active_cost": {"column": ccol[0], "mean_m": float(pc.mean()) if len(pc) else None},
            "k": k, "alpha": alpha, "gates": {"i_all_seeds_p_below_alpha": gate_i, "ii_cost_mean_positive": gate_ii,
                                               "iii_best_year_share_le_0.40": gate_iii},
            "crash_declared": crash, "crash_short_ci95_includes_zero": flags,
            "crash_flag": bool(flags), "positive": bool(gate_i and gate_ii and gate_iii)}


def pool_all(runs_root, k: int | None = None) -> dict:
    k = common.ledger_k() if k is None else k
    by_spec, skipped = load_runs(Path(runs_root))
    return _clean({"schema": "cycle7-pool-v1", "k": k, "skipped": skipped,
                   "specs": {sid: pool_spec(runs, k) for sid, runs in sorted(by_spec.items())}})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="cycle-7 pooling (FRAMEWORK §5)")
    ap.add_argument("--runs-root", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if out.exists():
        raise GuardError(f"{out} exists; pooled output is written once")
    res = pool_all(a.runs_root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
