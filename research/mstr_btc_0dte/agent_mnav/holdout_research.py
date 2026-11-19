#!/usr/bin/env python3
"""Sealed validation of the frozen gross-BTC mNAV trend rules (M1/M2/M3).

Gate specification and window: HOLDOUT_PLAN.md (registered before the first run of this file).
Writes HOLDOUT_RESULTS.json (all numbers) and HOLDOUT_RESULTS_TABLE.txt (compact table).
Never submits orders; research only.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from mnav_core import (
    ROOT,
    build_panel,
    metrics,
    observations_from_filings,
    premium_trend_signal,
    simulate_long_only,
)

DEV_MANIFEST = ROOT / "sec_source" / "dev_filings" / "MANIFEST.json"
HOLDOUT_MANIFEST = ROOT / "sec_source" / "holdout_filings" / "MANIFEST.json"
WARMUP_START = "2022-01-03"
SEALED_START = "2023-01-03"
SEALED_END = "2026-08-10"
BASE = dict(slippage_bps_each_side=3.0, commission_per_actual_share=0.005)
STRESS = dict(slippage_bps_each_side=6.0, commission_per_actual_share=0.01)
SEED = 20260817
DRAWS = 2000
BLOCK = 21.0


def stationary_bootstrap_indices(n: int, size: int, p: float, rng: np.random.Generator) -> np.ndarray:
    idx = np.empty(size, dtype=int)
    i = int(rng.integers(0, n))
    for t in range(size):
        idx[t] = i
        i = int(rng.integers(0, n)) if rng.random() < p else (i + 1) % n
    return idx


def sharpe_ann(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    s = x.std(ddof=1)
    return float(np.sqrt(252.0) * x.mean() / s) if s > 0 else float("nan")


def bootstrap_prob(rs: np.ndarray, rb: np.ndarray, rng: np.random.Generator, draws: int = DRAWS) -> dict:
    n = len(rs)
    p = 1.0 / BLOCK
    wins = 0
    diffs = np.empty(draws)
    for b in range(draws):
        idx = stationary_bootstrap_indices(n, n, p, rng)
        d = sharpe_ann(rs[idx]) - sharpe_ann(rb[idx])
        diffs[b] = d
        wins += int(d > 0)
    return {
        "draws": draws,
        "block_sessions": BLOCK,
        "seed": SEED,
        "p_diff_gt_0": wins / draws,
        "q05": float(np.quantile(diffs, 0.05)),
        "q50": float(np.quantile(diffs, 0.50)),
        "q95": float(np.quantile(diffs, 0.95)),
        "point_sr_diff": float(sharpe_ann(rs) - sharpe_ann(rb)),
    }


def per_year_net(equity: pd.Series) -> dict:
    r = equity.pct_change().dropna()
    out = {}
    for year, g in r.groupby(r.index.year):
        out[str(int(year))] = float((1.0 + g).prod() - 1.0)
    return out


def main() -> None:
    frozen = json.loads((ROOT / "FROZEN_RULES.json").read_text())
    rules = frozen["rules"]

    obs = observations_from_filings(DEV_MANIFEST) + observations_from_filings(HOLDOUT_MANIFEST)
    obs = sorted(obs, key=lambda o: o.filing_date)
    panel = build_panel(obs, start=WARMUP_START, end=SEALED_END)
    holdout = panel.loc[SEALED_START:SEALED_END].copy()
    if len(holdout) == 0:
        raise SystemExit("empty sealed window")

    results: dict = {
        "window": [str(holdout.index[0].date()), str(holdout.index[-1].date())],
        "sessions": int(len(holdout)),
        "btc_gap_sessions": int(holdout["btc_close_4pm_et"].isna().sum()),
        "costs": {"base": BASE, "stress": STRESS},
        "rules": {},
        "benchmark": {},
        "gates": {},
        "pass": False,
    }

    # Benchmark: MSTR buy-and-hold, same window/execution/cost model.
    bench_signal = pd.Series(True, index=holdout.index)
    eq_b, tr_b = simulate_long_only(holdout, bench_signal, start_long=True, **BASE)
    eq_bs, tr_bs = simulate_long_only(holdout, bench_signal, start_long=True, **STRESS)
    st_b, st_bs = metrics(eq_b, tr_b), metrics(eq_bs, tr_bs)
    st_b["per_year_net"], st_bs["per_year_net"] = per_year_net(eq_b), per_year_net(eq_bs)
    st_b["time_long"] = st_bs["time_long"] = 1.0
    results["benchmark"] = {"base": st_b, "stress": st_bs}
    rb = eq_b.pct_change().dropna().to_numpy()
    rbs = eq_bs.pct_change().dropna().to_numpy()

    rng = np.random.default_rng(SEED)
    for spec in rules:
        name = spec["id"]
        mom_key = "premium_momentum_days_L" if "premium_momentum_days_L" in spec else "premium_momentum_days"
        sma_key = "premium_sma_days_S" if "premium_sma_days_S" in spec else "premium_sma_days"
        signal = premium_trend_signal(
            panel,
            premium_momentum_days=spec[mom_key],
            premium_sma_days=spec[sma_key],
            btc_momentum_days=spec["btc_momentum_days"],
        ).reindex(holdout.index)
        eq, tr = simulate_long_only(holdout, signal, **BASE)
        eqs, trs = simulate_long_only(holdout, signal, **STRESS)
        st, sts = metrics(eq, tr), metrics(eqs, trs)
        st["per_year_net"], sts["per_year_net"] = per_year_net(eq), per_year_net(eqs)
        st["time_long"] = sts["time_long"] = float(signal.shift(1).fillna(False).mean())
        st["signal_days_true"] = int(signal.sum())
        rs = eq.pct_change().dropna().to_numpy()
        rss = eqs.pct_change().dropna().to_numpy()
        boot_base = bootstrap_prob(rs, rb, rng)
        boot_stress = bootstrap_prob(rss, rbs, rng)
        results["rules"][name] = {
            "name": spec["name"],
            "params": {k: spec[k] for k in (mom_key, sma_key, "btc_momentum_days")},
            "base": st, "stress": sts,
            "bootstrap_base": boot_base, "bootstrap_stress": boot_stress,
        }
        print(f"{name}: base SR {st['annualized_sharpe']:.2f} mean-day {st['cagr']*100:+.1f}% CAGR "
              f"maxDD {st['max_drawdown']*100:.0f}% | stress SR {sts['annualized_sharpe']:.2f} | "
              f"P_base {boot_base['p_diff_gt_0']:.3f} P_stress {boot_stress['p_diff_gt_0']:.3f}", flush=True)

    m1 = results["rules"]["M1"]
    results["gates"] = {
        "G1_base_sharpe_gt_bench_and_p95": bool(
            m1["base"]["annualized_sharpe"] > st_b["annualized_sharpe"] and m1["bootstrap_base"]["p_diff_gt_0"] >= 0.95),
        "G2_stress_sharpe_gt_bench_and_p90": bool(
            m1["stress"]["annualized_sharpe"] > st_bs["annualized_sharpe"] and m1["bootstrap_stress"]["p_diff_gt_0"] >= 0.90),
        "G3_m1_total_return_positive": bool(m1["base"]["total_return"] > 0),
    }
    results["pass"] = bool(all(results["gates"].values()))

    (ROOT / "HOLDOUT_RESULTS.json").write_text(json.dumps(results, indent=2) + "\n")

    lines = []
    lines.append(f"window {results['window'][0]} .. {results['window'][1]} sessions {results['sessions']} "
                 f"btc_gap_sessions {results['btc_gap_sessions']}")
    for name in ("M1", "M2", "M3"):
        r = results["rules"][name]
        lines.append(
            f"{name}: base SR {r['base']['annualized_sharpe']:.3f} tot {r['base']['total_return']*100:+.1f}% "
            f"maxDD {r['base']['max_drawdown']*100:.1f}% time_long {r['base']['time_long']:.2f} "
            f"P {r['bootstrap_base']['p_diff_gt_0']:.3f} | stress SR {r['stress']['annualized_sharpe']:.3f} "
            f"P {r['bootstrap_stress']['p_diff_gt_0']:.3f} | years {r['base']['per_year_net']}")
    lines.append(f"BENCH: base SR {st_b['annualized_sharpe']:.3f} tot {st_b['total_return']*100:+.1f}% "
                 f"maxDD {st_b['max_drawdown']*100:.1f}% years {st_b['per_year_net']} | "
                 f"stress SR {st_bs['annualized_sharpe']:.3f} tot {st_bs['total_return']*100:+.1f}%")
    lines.append(f"gates {results['gates']} -> PASS={results['pass']}")
    table = "\n".join(lines)
    (ROOT / "HOLDOUT_RESULTS_TABLE.txt").write_text(table + "\n")
    print("\n" + table)


if __name__ == "__main__":
    main()
