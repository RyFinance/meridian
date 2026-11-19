#!/usr/bin/env python3
"""One-shot runner: MSTR-vs-IBIT IV-spread long/cash rule (agent_ivspread).

Spec and gates: PREREGISTRATION.md (registered before any IV/return was
computed).  Research only; never submits orders.  Book mechanics are imported
from agent_mnav/mnav_core.py so execution is the family's frozen one (NAV
marked at each session's open; forced final liquidation).

Outputs: ivspread_results.json, ivspread_series.csv, ivspread_table.txt.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "agent_mnav"))
from mnav_core import metrics, simulate_long_only  # noqa: E402

from iv_core import (  # noqa: E402
    IBIT_DAILY, IBIT_OPTIONS, MSTR_DAILY, MSTR_OPTIONS, WINDOW_END, WINDOW_START,
    Z_ENTRY, session_iv_series, spread_and_z,
)

BASE = dict(slippage_bps_each_side=3.0, commission_per_actual_share=0.005)
STRESS = dict(slippage_bps_each_side=6.0, commission_per_actual_share=0.01)
SEED = 20260817
DRAWS = 2000
BLOCK = 21.0


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def bootstrap_prob(rs: np.ndarray, rb: np.ndarray, rng: np.random.Generator) -> dict:
    n = len(rs)
    p = 1.0 / BLOCK
    wins = 0
    diffs = np.empty(DRAWS)
    for b in range(DRAWS):
        idx = stationary_bootstrap_indices(n, n, p, rng)
        d = sharpe_ann(rs[idx]) - sharpe_ann(rb[idx])
        diffs[b] = d
        wins += int(d > 0)
    return {
        "draws": DRAWS, "block_sessions": BLOCK, "seed": SEED,
        "p_diff_gt_0": wins / DRAWS,
        "q05": float(np.quantile(diffs, 0.05)), "q50": float(np.quantile(diffs, 0.50)),
        "q95": float(np.quantile(diffs, 0.95)),
        "point_sr_diff": float(sharpe_ann(rs) - sharpe_ann(rb)),
    }


def half_year_net(equity: pd.Series) -> dict:
    r = equity.pct_change().dropna()
    out = {}
    for (year, half), g in r.groupby([r.index.year, np.where(r.index.month <= 6, "H1", "H2")]):
        out[f"{year}{half}"] = float((1.0 + g).prod() - 1.0)
    return out


def main() -> None:
    mstr_daily = pd.read_parquet(MSTR_DAILY).sort_index()
    mstr_daily.index = pd.DatetimeIndex(mstr_daily.index).normalize()
    ibit_daily = pd.read_parquet(IBIT_DAILY)
    ibit_close = ibit_daily["Close"]
    if isinstance(ibit_close, pd.DataFrame):
        ibit_close = ibit_close.iloc[:, 0]

    sessions = mstr_daily.loc[str(WINDOW_START):str(WINDOW_END)].index
    iv_mstr = session_iv_series(MSTR_OPTIONS, mstr_daily["Close"]).reindex(sessions)["iv"]
    iv_ibit = session_iv_series(IBIT_OPTIONS, ibit_close).reindex(sessions)["iv"]
    frame = spread_and_z(iv_mstr, iv_ibit)

    stance = ((frame["z"] <= Z_ENTRY).where(frame["z"].notna())).ffill().fillna(False).astype(bool)
    frame["stance"] = stance

    first_valid = frame["z"].first_valid_index()
    eval_frame = frame.loc[first_valid:]
    eval_sessions = eval_frame.index
    panel = pd.DataFrame({
        "mstr_open": mstr_daily.loc[eval_sessions, "Open"].astype(float),
        "mstr_close": mstr_daily.loc[eval_sessions, "Close"].astype(float),
    })
    signal = eval_frame["stance"]

    eq_rule, tr_rule = simulate_long_only(panel, signal, **BASE)
    eq_bench, tr_bench = simulate_long_only(panel, pd.Series(True, index=eval_sessions), start_long=True, **BASE)
    eq_rule_s, tr_rule_s = simulate_long_only(panel, signal, **STRESS)
    eq_bench_s, tr_bench_s = simulate_long_only(panel, pd.Series(True, index=eval_sessions), start_long=True, **STRESS)

    st_rule, st_bench = metrics(eq_rule, tr_rule), metrics(eq_bench, tr_bench)
    st_rule_s, st_bench_s = metrics(eq_rule_s, tr_rule_s), metrics(eq_bench_s, tr_bench_s)
    st_rule["time_long"] = float(signal.shift(1, fill_value=False).mean())
    st_rule_s["time_long"] = st_rule["time_long"]
    st_bench["time_long"] = st_bench_s["time_long"] = 1.0
    st_rule["per_half"] = half_year_net(eq_rule)
    st_bench["per_half"] = half_year_net(eq_bench)

    rng = np.random.default_rng(SEED)
    rs, rb = eq_rule.pct_change().dropna().to_numpy(), eq_bench.pct_change().dropna().to_numpy()
    rss, rbs = eq_rule_s.pct_change().dropna().to_numpy(), eq_bench_s.pct_change().dropna().to_numpy()
    boot_base = bootstrap_prob(rs, rb, rng)
    boot_stress = bootstrap_prob(rss, rbs, rng)

    gates = {
        "G1_base_sr_gt_bench_and_p95": bool(
            st_rule["annualized_sharpe"] > st_bench["annualized_sharpe"] and boot_base["p_diff_gt_0"] >= 0.95),
        "G2_stress_sr_gt_bench_and_p90": bool(
            st_rule_s["annualized_sharpe"] > st_bench_s["annualized_sharpe"] and boot_stress["p_diff_gt_0"] >= 0.90),
        "G3_rule_net_total_positive": bool(st_rule["total_return"] > 0),
    }
    passed = bool(all(gates.values()))

    # descriptive z bucket table (reported only)
    nxt = mstr_daily["Close"].pct_change().shift(-1).reindex(eval_sessions)
    valid = eval_frame["z"].notna()
    buckets = pd.qcut(eval_frame.loc[valid, "z"], 5, labels=[f"q{i}" for i in range(1, 6)])
    z_table = nxt.loc[valid].groupby(buckets, observed=True).agg(["count", "mean"]).round(5).to_dict()

    results = {
        "window": [str(eval_sessions[0]), str(eval_sessions[-1])],
        "sessions_full": int(len(frame)), "sessions_eval": int(len(eval_sessions)),
        "iv_available": {"mstr": int(frame.iv_mstr.notna().sum()), "ibit": int(frame.iv_ibit.notna().sum())},
        "z_entry": Z_ENTRY,
        "stance_long_sessions": int(signal.sum()),
        "spread_stats_full_window": {
            "mean": float(frame.spread.mean()), "median": float(frame.spread.median()),
            "min": float(frame.spread.min()), "max": float(frame.spread.max()),
        },
        "base_rule": st_rule, "base_bench": st_bench,
        "stress_rule": st_rule_s, "stress_bench": st_bench_s,
        "bootstrap_base": boot_base, "bootstrap_stress": boot_stress,
        "gates": gates, "pass": passed,
        "z_quintile_next_close_return": z_table,
        "code_sha256": {
            "research/mstr_btc_0dte/agent_ivspread/iv_core.py": sha(HERE / "iv_core.py"),
            "research/mstr_btc_0dte/agent_ivspread/ivspread_study.py": sha(HERE / "ivspread_study.py"),
            "research/mstr_btc_0dte/agent_mnav/mnav_core.py": sha(HERE.parent / "agent_mnav" / "mnav_core.py"),
        },
        "input_sha256": {
            "data/ibit_daily_yf.parquet": sha(IBIT_DAILY),
            "data/lse/options_mstr/MSTR.parquet": sha(MSTR_OPTIONS),
            "data/lse/options_ibit_1d/IBIT.parquet": sha(IBIT_OPTIONS),
        },
    }
    (HERE / "ivspread_results.json").write_text(json.dumps(results, indent=2, default=str) + "\n")

    series = frame.join(pd.DataFrame({"nav": eq_rule, "bench_nav": eq_bench}))
    series.to_csv(HERE / "ivspread_series.csv")

    lines = [
        f"window {results['window'][0]}..{results['window'][1]} eval sessions {results['sessions_eval']} "
        f"(full {results['sessions_full']}) stance long {results['stance_long_sessions']}",
        f"spread pts: mean {frame.spread.mean():.2f} median {frame.spread.median():.2f} "
        f"min {frame.spread.min():.2f} max {frame.spread.max():.2f}",
        f"RULE  base SR {st_rule['annualized_sharpe']:.3f} tot {st_rule['total_return']*100:+.1f}% "
        f"maxDD {st_rule['max_drawdown']*100:.1f}% time_long {st_rule['time_long']:.2f} | "
        f"stress SR {st_rule_s['annualized_sharpe']:.3f}",
        f"BENCH base SR {st_bench['annualized_sharpe']:.3f} tot {st_bench['total_return']*100:+.1f}% "
        f"maxDD {st_bench['max_drawdown']*100:.1f}%",
        f"boot base: P {boot_base['p_diff_gt_0']:.3f} point {boot_base['point_sr_diff']:+.3f} "
        f"[{boot_base['q05']:+.3f},{boot_base['q95']:+.3f}] | stress P {boot_stress['p_diff_gt_0']:.3f}",
        f"gates {gates} -> PASS={passed}",
        f"rule halves {st_rule['per_half']}",
        f"bench halves {st_bench['per_half']}",
    ]
    (HERE / "ivspread_table.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
