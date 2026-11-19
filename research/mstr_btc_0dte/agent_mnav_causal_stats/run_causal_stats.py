#!/usr/bin/env python3
"""Statistical companion for the causal 15:59 version of frozen M1.

This is intentionally not a new strategy search.  It rebuilds the exact
frozen M1 inputs and changes only the known candle-completion defect: the BTC
close used at the 16:00 ET MSTR decision must be the close of the minute
starting at 15:59 ET.  It retains the 10/50/no-regime rule, filing ledger,
split treatment, next-open fills, and 3 bp per-side + $0.005/share costs.

Outputs live only beside this script.  The authoritative ``agent_mnav`` and
the independent causal audit directories remain unmodified.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MNAV = ROOT / "agent_mnav"
AUDIT = ROOT / "agent_mnav_audit"
STATS = ROOT / "agent_mnav_stats"
for directory in (str(MNAV), str(AUDIT), str(STATS)):
    if directory not in sys.path:
        sys.path.insert(0, directory)

import mnav_core as core  # noqa: E402
import reproduce_causal_1559 as causal  # noqa: E402
import run_stats_audit as original_stats  # noqa: E402
import validate_frozen as frozen_runner  # noqa: E402


VALID_START = pd.Timestamp("2023-01-03")
VALID_END = pd.Timestamp("2026-08-10")
REPS = 20_000
BLOCKS = (5, 20, 60)
SEED = 20261017


def previous(signal: pd.Series, before: pd.Timestamp) -> bool:
    prior = signal.loc[signal.index < before]
    return bool(prior.iloc[-1]) if not prior.empty else False


def execute(panel: pd.DataFrame, signal: pd.Series, *, start_long: bool) -> tuple[pd.Series, pd.DataFrame, pd.Series]:
    equity, trades = core.simulate_long_only(
        panel,
        signal.reindex(panel.index).fillna(False).astype(bool),
        slippage_bps_each_side=3.0,
        commission_per_actual_share=0.005,
        start_long=start_long,
    )
    with_start = pd.concat(
        [pd.Series([1.0], index=[equity.index[0] - pd.Timedelta(nanoseconds=1)]), equity]
    )
    return equity, trades, with_start.pct_change().dropna()


def performance(equity: pd.Series, trades: pd.DataFrame, returns: pd.Series, signal: pd.Series, *, start_long: bool) -> dict[str, float | int]:
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    nav = pd.concat([pd.Series([1.0], index=[equity.index[0] - pd.Timedelta(nanoseconds=1)]), equity])
    entries = int((trades["side"] == "buy").sum()) if not trades.empty else 0
    exits = int(trades["side"].astype(str).str.startswith("sell").sum()) if not trades.empty else 0
    positioned = signal.reindex(equity.index).shift(1, fill_value=start_long).astype(bool)
    return {
        "total_return": float(equity.iloc[-1] - 1.0),
        "cagr": float(equity.iloc[-1] ** (1.0 / years) - 1.0),
        "annualized_mean": float(252 * returns.mean()),
        "annualized_volatility": float(np.sqrt(252) * returns.std(ddof=1)),
        "annualized_sharpe": float(np.sqrt(252) * returns.mean() / returns.std(ddof=1)),
        "max_drawdown": float((nav / nav.cummax() - 1.0).min()),
        "round_trips": min(entries, exits),
        "time_long": float(positioned.mean()),
    }


def hac(x: np.ndarray, lags: int) -> dict[str, float | int]:
    """Bartlett Newey--West test of a daily mean differential."""

    x = np.asarray(x, dtype=float)
    n = len(x)
    mean = float(x.mean())
    demeaned = x - mean
    used = min(lags, n - 1)
    long_run = float(demeaned @ demeaned / n)
    for lag in range(1, used + 1):
        autocov = float(demeaned[lag:] @ demeaned[:-lag] / n)
        long_run += 2 * (1 - lag / (used + 1)) * autocov
    se = math.sqrt(max(long_run, 0) / n)
    t = mean / se if se else float("nan")
    return {
        "n": n,
        "hac_lags": used,
        "daily_mean": mean,
        "annualized_mean": 252 * mean,
        "hac_se_daily_mean": se,
        "t_stat": t,
        "normal_two_sided_p": math.erfc(abs(t) / math.sqrt(2)) if math.isfinite(t) else float("nan"),
    }


def sharpe(samples: np.ndarray) -> np.ndarray:
    return np.sqrt(252) * samples.mean(axis=1) / samples.std(axis=1, ddof=1)


def joint_block_bootstrap(returns: pd.DataFrame) -> pd.DataFrame:
    """Paired circular moving-block intervals for causal M1 comparisons."""

    values = returns.to_numpy(dtype=float)
    n = len(values)
    names = list(returns.columns)
    pairs = [("M1_causal_1559", "MSTR_buy_and_hold"), ("M1_causal_1559", "MSTR_close_above_50SMA")]
    col = {name: pos for pos, name in enumerate(names)}
    rows: list[dict[str, object]] = []
    observed = sharpe(values[None, :, :])[0]
    for block in BLOCKS:
        rng = np.random.default_rng(SEED + block)
        blocks_per_draw = math.ceil(n / block)
        offset = np.arange(block)
        chunks: list[np.ndarray] = []
        for start in range(0, REPS, 250):
            batch = min(250, REPS - start)
            starts = rng.integers(0, n, size=(batch, blocks_per_draw))
            index = (starts[:, :, None] + offset[None, None, :]) % n
            index = index.reshape(batch, -1)[:, :n]
            chunks.append(sharpe(values[index]))
        samples = np.concatenate(chunks)
        for left, right in pairs:
            delta = samples[:, col[left]] - samples[:, col[right]]
            rows.append({
                "strategy": left,
                "benchmark": right,
                "metric": "annualized_sharpe_difference",
                "block_length_sessions": block,
                "bootstrap_reps": REPS,
                "observed": float(observed[col[left]] - observed[col[right]]),
                "percentile_ci_2_5": float(np.quantile(delta, 0.025)),
                "percentile_ci_97_5": float(np.quantile(delta, 0.975)),
                "resample_fraction_less_or_equal_zero": float((delta <= 0).mean()),
            })
    return pd.DataFrame(rows)


def main() -> None:
    frozen = original_stats.json.loads((MNAV / "FROZEN_RULES.json").read_text())
    m1 = next(rule for rule in frozen["rules"] if rule["id"] == "M1")
    expected = {"premium_momentum_days_L": 10, "premium_sma_days_S": 50, "btc_momentum_days": None}
    if {key: m1[key] for key in expected} != expected:
        raise AssertionError("Expected the frozen 10/50/no-regime M1 rule")

    observations = core.observations_from_filings(MNAV / "sec_source/dev_filings/MANIFEST.json")
    observations += core.observations_from_filings(MNAV / "sec_source/holdout_filings/MANIFEST.json")
    full_panel = core.build_panel(sorted(observations, key=lambda x: x.filing_date), start="2020-08-01", end=str(VALID_END.date()))
    full_panel = causal.rebuilt_panel_with_causal_btc(full_panel)
    causal_m1 = frozen_runner.make_signal(full_panel, m1)
    trend50 = original_stats.trend50_signal(full_panel)
    valid = full_panel.loc[VALID_START:VALID_END]

    signals = {
        "M1_causal_1559": causal_m1,
        "MSTR_close_above_50SMA": trend50,
        "MSTR_buy_and_hold": pd.Series(True, index=full_panel.index),
    }
    output_rows: list[dict[str, object]] = []
    returns: dict[str, pd.Series] = {}
    for name, signal in signals.items():
        start_long = previous(signal, valid.index[0])
        equity, trades, daily = execute(valid, signal, start_long=start_long)
        output_rows.append({"strategy": name, **performance(equity, trades, daily, signal, start_long=start_long)})
        returns[name] = daily
    frame = pd.DataFrame(returns)
    if frame.isna().any().any() or len(frame) != len(valid):
        raise RuntimeError("Unexpected return alignment")
    output = pd.DataFrame(output_rows)
    output.to_csv(HERE / "CAUSAL_PERFORMANCE.csv", index=False)
    bootstrap = joint_block_bootstrap(frame)
    bootstrap.to_csv(HERE / "CAUSAL_BLOCK_BOOTSTRAP.csv", index=False)

    hac_rows: list[dict[str, object]] = []
    comparisons = [("M1_causal_1559", "zero_cash"), ("M1_causal_1559", "MSTR_buy_and_hold"), ("M1_causal_1559", "MSTR_close_above_50SMA")]
    for left, right in comparisons:
        x = frame[left].to_numpy() if right == "zero_cash" else (frame[left] - frame[right]).to_numpy()
        for lags in (20, 60):
            hac_rows.append({"strategy": left, "benchmark": right, **hac(x, lags)})
    pd.DataFrame(hac_rows).to_csv(HERE / "CAUSAL_HAC.csv", index=False)

    reference = original_stats.json.loads((AUDIT / "CAUSAL_1559_M1.json").read_text())["causal_1559_path"]
    ours = output.set_index("strategy").loc["M1_causal_1559"]
    for key, ref_key in (("total_return", "total_return"), ("cagr", "cagr"), ("annualized_sharpe", "annualized_sharpe"), ("max_drawdown", "max_drawdown")):
        if not np.isclose(float(ours[key]), float(reference[ref_key]), atol=1e-12):
            raise AssertionError(f"Causal reproduction mismatch for {key}")
    print(output.to_string(index=False))
    print(pd.DataFrame(hac_rows).to_string(index=False))
    print(bootstrap.to_string(index=False))


if __name__ == "__main__":
    main()
