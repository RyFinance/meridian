"""Summarise the null-world grid, confront the project record, derive gate recommendations.

    PYTHONPATH=. .venv/bin/python -m research.null_lab.analyze

Reads reports/null_lab/worlds/*.{json,npz} (from run_lab) and writes, in reports/null_lab/:
  calibration.csv        per config: null Sharpe distribution, P(pass dev), P(pass both), family rates
  best_of_n.csv          distribution of the best development Sharpe among N null candidates
  horizon_thresholds.csv null Sharpe quantiles by window length (1..10 years)
  record_candidates.csv  the project's gated candidates with null centres, z-scores, P(pass | null)
  record_tests.json      formal all-null tests (dev pass count, validation, shrinkage, edge variance)
  summary.json           headline numbers used in REPORT.md
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from research.null_lab import record as rc

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "null_lab"
W = OUT / "worlds"
NS = (1, 4, 20, 111)
BETA_CONTAMINATED = ("spy_cash",)          # raw long-only timing: Sharpe gate measures the market


def load() -> dict:
    out = {}
    for j in sorted(W.glob("*.json")):
        res = json.loads(j.read_text())
        arr = dict(np.load(j.with_suffix(".npz")))
        out[res["config"]] = (res, arr)
    return out


def calibration(worlds: dict) -> pd.DataFrame:
    rows = []
    for cid, (r, a) in worlds.items():
        c, f = r["candidate"], r["family"]
        pd_, pv = c["p_pass_dev"], c["p_pass_val_gate"]
        rows.append({
            "config": cid, "engine": r["engine_key"], "signal": r["signal_key"], "path": r["path_key"],
            "signal_desc": r["signal"], "worlds": r["n_worlds"], "years_dev": round(r["years_dev"], 2),
            "years_val": round(r["years_val"], 2),
            "sr_dev_mean": c["sr_dev"]["mean"], "sr_dev_sd": c["sr_dev"]["sd"],
            "kappa_dev": c["sr_dev"]["sd_x_sqrt_years"], "sr_dev_q95": c["sr_dev"]["q95"],
            "sr_val_mean": c["sr_val"]["mean"], "sr_val_sd": c["sr_val"]["sd"], "kappa_val": c["sr_val"]["sd_x_sqrt_years"],
            "corr_dev_val": c["corr_dev_val"],
            "p_sr_dev_ge_050": c["p_sharpe_dev_ge_gate"]["p"],
            "p_pass_dev": pd_["p"], "p_pass_dev_se": pd_["se"],
            "p_pass_dev_pooled": r["pooled_independent"]["p_pass_dev"]["p"],
            "p_pass_dev_pooled_se": r["pooled_independent"]["p_pass_dev"]["se"],
            "p_val_gate": pv["p"], "p_val_gate_se": pv["se"],
            "p_pass_both": c["p_pass_both"]["p"], "p_pass_both_se": c["p_pass_both"]["se"],
            "p_pass_both_pooled": r["pooled_independent"]["p_pass_both"]["p"],
            "p_pass_both_product": pd_["p"] * pv["p"],
            "mean_val_sr_given_dev_pass": c["mean_val_sr_given_dev_pass"],
            "family_p_any_dev": f["p_any_pass_dev"]["p"], "family_p_any_dev_se": f["p_any_pass_dev"]["se"],
            "family_p_any_both": f["p_any_pass_both"]["p"], "family_p_any_both_se": f["p_any_pass_both"]["se"],
            "composite_p_pass_dev": r.get("composite", {}).get("p_pass_dev", {}).get("p"),
        })
    return pd.DataFrame(rows)


def best_of_n(worlds: dict, reps: int = 20000, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    pools = {}
    for cid, (r, a) in worlds.items():
        if r["path_key"] != "real":
            continue
        x = a["sr_dev"][:, :3].ravel()          # independent candidates only (composite excluded)
        x = x[np.isfinite(x)]
        pools[cid] = x
        for N in NS:
            m = rng.choice(x, size=(reps, N)).max(axis=1)
            mu, sd = x.mean(), x.std(ddof=1)
            rows.append({"config": cid, "engine": r["engine_key"], "N": N, "mean": m.mean(),
                         "q50": np.quantile(m, 0.5), "q95": np.quantile(m, 0.95),
                         "gauss_expected_max": mu + sd * _expected_max_z(N)})
    # project-like mix: every draw from a random market-neutral real-path config (no raw long-only timing)
    keys = [k for k in pools if worlds[k][0]["engine_key"] not in BETA_CONTAMINATED]
    for N in NS:
        pick = rng.integers(0, len(keys), size=(reps, N))
        vals = np.empty((reps, N))
        for j, k in enumerate(keys):
            m = pick == j
            vals[m] = rng.choice(pools[k], size=m.sum())
        mx = vals.max(axis=1)
        rows.append({"config": "MIX_market_neutral", "engine": "+".join(sorted({worlds[k][0]['engine_key'] for k in keys})),
                     "N": N, "mean": mx.mean(), "q50": np.quantile(mx, 0.5), "q95": np.quantile(mx, 0.95),
                     "gauss_expected_max": None})
    return pd.DataFrame(rows)


def _expected_max_z(N: int) -> float:
    if N == 1:
        return 0.0
    g = 0.5772156649015329
    return (1 - g) * norm.ppf(1 - 1 / N) + g * norm.ppf(1 - 1 / (N * np.e))


def horizons(worlds: dict) -> pd.DataFrame:
    rows = []
    for cid, (r, a) in worlds.items():
        for wn, hz in r["horizons"].items():
            for h, d in hz.items():
                rows.append({"config": cid, "engine": r["engine_key"], "path": r["path_key"], "window": wn,
                             "years": float(h), "mean": d["mean"], "sd": d["sd"], "kappa": d["sd_x_sqrt_years"],
                             "q95": d["q95"], "q99": d["q99"], "p_dev_gate_050": d["p_dev_gate"],
                             "p_sr_ge_050": d["p_sr_ge_dev_gate"]})
        for wn in ("dev", "val"):
            d = r["candidate"][f"sr_{wn}"]
            rows.append({"config": cid, "engine": r["engine_key"], "path": r["path_key"], "window": wn,
                         "years": round(r[f"years_{wn}"], 2), "mean": d["mean"], "sd": d["sd"],
                         "kappa": d["sd_x_sqrt_years"], "q95": d["q95"], "q99": d["q99"],
                         "p_dev_gate_050": r["candidate"]["p_pass_dev"]["p"] if wn == "dev" else None,
                         "p_sr_ge_050": None})
    return pd.DataFrame(rows)


def recommended_gates(hz: pd.DataFrame) -> dict:
    """Net-Sharpe threshold that holds P(pass | null) <= 5% per candidate (and 5%/4 for each member of
    a 4-candidate family) as a function of window length T, for a null with ZERO mean (i.e. no credit
    for the cost drag that pushes most real null means below zero) and dispersion kappa / sqrt(T).
    kappa is taken from the lab: median, 90th percentile and maximum of (null Sharpe sd x sqrt(T))
    over all market-neutral configs and horizons. Also reports the false-pass probability that the
    current 0.5 gate implies under the same null."""
    mn = hz[~hz.engine.isin(BETA_CONTAMINATED)]
    ks = {"median": float(mn.kappa.median()), "q90": float(mn.kappa.quantile(0.9)), "max": float(mn.kappa.max())}
    out = {"kappa": ks, "rows": []}
    for T in (1, 2, 3, 4, 5, 5.7, 7, 8, 10, 12):
        row = {"years": T}
        for name, k in ks.items():
            se = k / np.sqrt(T)
            row[f"gate_candidate_5pct_k{name}"] = float(norm.ppf(0.95) * se)
            row[f"gate_family4_5pct_k{name}"] = float(norm.ppf(1 - 0.05 / 4) * se)
            row[f"false_pass_of_0.5_gate_k{name}"] = float(1 - norm.cdf(0.5 / se))
            row[f"false_pass_of_0.75_gate_k{name}"] = float(1 - norm.cdf(0.75 / se))
        out["rows"].append(row)
    return out


def null_slope_benchmark(worlds: dict, n_pairs: int = 30, reps: int = 5000, seed: int = 5) -> dict:
    """Distribution of the dev->val WLS slope for `n_pairs` null candidates drawn across
    heterogeneous real-path market-neutral configs (different costs, turnover, tilts): the slope an
    all-null project would show when net Sharpes are compared against a zero centre."""
    rng = np.random.default_rng(seed)
    keys = [k for k, (r, a) in worlds.items() if r["path_key"] == "real" and r["engine_key"] not in BETA_CONTAMINATED]
    pools = [(worlds[k][1]["sr_dev"][:, 0], worlds[k][1]["sr_val"][:, 0], worlds[k][0]["years_val"]) for k in keys]
    slopes = []
    for _ in range(reps):
        cfg = rng.integers(0, len(pools), size=n_pairs)
        x, y, w = np.empty(n_pairs), np.empty(n_pairs), np.empty(n_pairs)
        for i, c in enumerate(cfg):
            d, v, yv = pools[c]
            j = rng.integers(0, len(d))
            x[i], y[i], w[i] = d[j], v[j], yv
        X = np.column_stack([np.ones(n_pairs), x])
        b = np.linalg.solve(X.T @ (w[:, None] * X), X.T @ (w * y))
        slopes.append(b[1])
    s = np.array(slopes)
    return {"configs": keys, "n_pairs": n_pairs, "mean": float(s.mean()), "q05": float(np.quantile(s, 0.05)),
            "q50": float(np.median(s)), "q95": float(np.quantile(s, 0.95))}


def kappa_from_lab(cal: pd.DataFrame) -> dict:
    mn = cal[(cal.path == "real") & (~cal.engine.isin(BETA_CONTAMINATED))]
    k = pd.concat([mn.kappa_dev, mn.kappa_val])
    return {"median": float(k.median()), "min": float(k.min()), "max": float(k.max())}


def main():
    worlds = load()
    cal = calibration(worlds)
    cal.to_csv(OUT / "calibration.csv", index=False, float_format="%.5f")
    bon = best_of_n(worlds)
    bon.to_csv(OUT / "best_of_n.csv", index=False, float_format="%.4f")
    hz = horizons(worlds)
    hz.to_csv(OUT / "horizon_thresholds.csv", index=False, float_format="%.4f")
    gates = recommended_gates(hz)
    kap = kappa_from_lab(cal)
    tests = {}
    for label, kappa in (("kappa_1.0", 1.0), ("kappa_1.3", 1.3)):
        dv = rc.dev_stage(kappa)
        tests[label] = {"dev_stage": dv["summary"], "val_stage": rc.val_stage(kappa),
                        "shrinkage_core": rc.shrinkage(kappa, extended=False),
                        "shrinkage_core_gross": rc.shrinkage(kappa, extended=False, gross=True),
                        "shrinkage_extended": rc.shrinkage(kappa, extended=True),
                        "edge_variance": rc.edge_variance(kappa)}
        if label == "kappa_1.0":
            dv["per_candidate"].merge(rc.table()[["id", "family", "dev_gross", "dev_pass", "val_sr", "val_years",
                                                  "c_val", "val_p_edge", "source"]], on="id") \
                .to_csv(OUT / "record_candidates.csv", index=False, float_format="%.4f")
    tests["null_slope_benchmark"] = null_slope_benchmark(worlds)
    tests["kappa_lab"] = kap
    tests["record_verify_mismatches"] = rc.verify()
    (OUT / "record_tests.json").write_text(json.dumps(tests, indent=1, default=float))
    pd.DataFrame(gates["rows"]).to_csv(OUT / "recommended_gates.csv", index=False, float_format="%.3f")
    (OUT / "summary.json").write_text(json.dumps({"recommended_gates": gates, "kappa_lab": kap}, indent=1, default=float))
    with pd.option_context("display.width", 250, "display.max_columns", 40):
        print(cal[["config", "engine", "signal", "path", "sr_dev_mean", "sr_dev_sd", "kappa_dev", "p_pass_dev",
                   "p_pass_dev_se", "p_val_gate", "p_pass_both", "p_pass_both_se", "family_p_any_dev",
                   "family_p_any_both", "corr_dev_val"]].round(4).to_string(index=False))
        print(bon.round(3).to_string(index=False))
    print(json.dumps(gates, indent=1, default=float))
    print(json.dumps(tests, indent=1, default=float)[:6000])


if __name__ == "__main__":
    main()
