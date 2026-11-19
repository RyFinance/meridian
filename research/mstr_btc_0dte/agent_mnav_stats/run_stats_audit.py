#!/usr/bin/env python3
"""Independent statistical audit of the frozen mNAV validation.

This is deliberately a read-only companion to ``agent_mnav``.  It reads only
the artifacts enumerated by that track's AUTHORITATIVE_ARTIFACTS.md, recreates
the published baseline-cost equity curves from the sealed panel/signals, and
writes statistical-audit outputs to this directory.  It does not select,
change, or re-run a replacement mNAV rule.

The only newly constructed comparator is one deliberately simple, single-rule
benchmark: long MSTR when its own close is above its 50-session SMA, otherwise
cash, executed at the next regular-session open under the same frozen cost
model.  The 50-session horizon is fixed before running this audit because it
is the common, pre-frozen trend horizon in M1/M3; no parameter search is run
for this comparator.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "agent_mnav"
VALID_START = pd.Timestamp("2023-01-03")
VALID_END = pd.Timestamp("2026-08-10")
SLIPPAGE_BPS = 3.0
COMMISSION = 0.005
BOOTSTRAP_REPS = 20_000
BOOTSTRAP_BLOCKS = (5, 20, 60)
HAC_LAGS = (20, 60)
SEED = 20261017


# Importing the frozen simulator keeps the execution conventions exactly the
# same while this audit remains read-only with respect to its source directory.
sys.path.insert(0, str(SOURCE))
from mnav_core import simulate_long_only  # noqa: E402


def prior_signal(signal: pd.Series, before: pd.Timestamp) -> bool:
    prior = signal.loc[signal.index < before]
    return bool(prior.iloc[-1]) if not prior.empty else False


def trend50_signal(panel: pd.DataFrame) -> pd.Series:
    """One fixed, non-optimized price-only long/cash comparison rule."""

    sma = panel["mstr_close"].rolling(50).mean()
    raw = (panel["mstr_close"] > sma).astype("boolean").where(sma.notna())
    return raw.ffill().fillna(False).astype(bool)


def execute(
    panel: pd.DataFrame,
    full_signal: pd.Series,
    *,
    start_long: bool,
) -> tuple[pd.Series, pd.DataFrame, pd.Series]:
    """Use the frozen next-open baseline-cost execution function unchanged."""

    signal = full_signal.reindex(panel.index).fillna(False).astype(bool)
    equity, trades = simulate_long_only(
        panel,
        signal,
        slippage_bps_each_side=SLIPPAGE_BPS,
        commission_per_actual_share=COMMISSION,
        start_long=start_long,
    )
    # Metrics in the source track include the initial buy cost; retain exactly
    # that convention by prepending NAV=1 immediately before the first open.
    with_start = pd.concat(
        [
            pd.Series([1.0], index=[equity.index[0] - pd.Timedelta(nanoseconds=1)]),
            equity,
        ]
    )
    returns = with_start.pct_change().dropna()
    return equity, trades, returns


def performance(
    equity: pd.Series,
    returns: pd.Series,
    trades: pd.DataFrame,
    signal: pd.Series,
    *,
    start_long: bool,
) -> dict[str, float | int | str]:
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1.0 / 365.25)
    vol = float(returns.std(ddof=1))
    sharpe = float(np.sqrt(252.0) * returns.mean() / vol) if vol else float("nan")
    nav_with_start = pd.concat(
        [pd.Series([1.0], index=[equity.index[0] - pd.Timedelta(nanoseconds=1)]), equity]
    )
    entries = int((trades["side"] == "buy").sum()) if not trades.empty else 0
    exits = int(trades["side"].astype(str).str.startswith("sell").sum()) if not trades.empty else 0
    positioned = signal.reindex(equity.index).shift(1, fill_value=start_long).astype(bool)
    return {
        "start": str(equity.index[0].date()),
        "end": str(equity.index[-1].date()),
        "sessions": int(len(equity)),
        "total_return": float(equity.iloc[-1] - 1.0),
        "cagr": float(equity.iloc[-1] ** (1.0 / years) - 1.0),
        "annualized_mean_return": float(252.0 * returns.mean()),
        "annualized_volatility": float(np.sqrt(252.0) * vol),
        "annualized_sharpe": sharpe,
        "max_drawdown": float((nav_with_start / nav_with_start.cummax() - 1.0).min()),
        "entry_trades": entries,
        "exit_trades": exits,
        "round_trips": float(min(entries, exits)),
        "time_long": float(positioned.mean()),
    }


def newey_west_mean_test(x: np.ndarray, lags: int) -> dict[str, float | int]:
    """HAC test of a mean return differential, using Bartlett weights."""

    x = np.asarray(x, dtype=float)
    n = len(x)
    mean = float(x.mean())
    demeaned = x - mean
    usable_lags = min(int(lags), n - 1)
    long_run_variance = float(np.dot(demeaned, demeaned) / n)
    for lag in range(1, usable_lags + 1):
        autocov = float(np.dot(demeaned[lag:], demeaned[:-lag]) / n)
        long_run_variance += 2.0 * (1.0 - lag / (usable_lags + 1.0)) * autocov
    se_mean = math.sqrt(max(long_run_variance, 0.0) / n)
    t_stat = mean / se_mean if se_mean else float("nan")
    # Normal large-sample approximation; it is reported as descriptive
    # evidence, not as an unadjusted multiple-testing certificate.
    p_two_sided = math.erfc(abs(t_stat) / math.sqrt(2.0)) if math.isfinite(t_stat) else float("nan")
    return {
        "n": n,
        "hac_lags": usable_lags,
        "daily_mean_difference": mean,
        "annualized_mean_difference": 252.0 * mean,
        "hac_se_daily_mean": se_mean,
        "t_stat": t_stat,
        "normal_two_sided_p": p_two_sided,
    }


def newey_west_single_factor_regression(
    y: np.ndarray, x: np.ndarray, lags: int
) -> dict[str, float | int]:
    """OLS alpha/beta with a Bartlett Newey--West covariance matrix.

    This is a one-factor timing diagnostic, not proof of a tradable economic
    alpha: both the strategy and benchmark are MSTR-derived portfolios.
    """

    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    n = len(y)
    design = np.column_stack([np.ones(n), x])
    coefficient = np.linalg.solve(design.T @ design, design.T @ y)
    residual = y - design @ coefficient
    moment = design * residual[:, None]
    usable_lags = min(int(lags), n - 1)
    meat = moment.T @ moment / n
    for lag in range(1, usable_lags + 1):
        cross = moment[lag:].T @ moment[:-lag] / n
        weight = 1.0 - lag / (usable_lags + 1.0)
        meat += weight * (cross + cross.T)
    bread_inverse = np.linalg.inv(design.T @ design / n)
    covariance = bread_inverse @ meat @ bread_inverse / n
    standard_error = np.sqrt(np.diag(covariance))
    alpha_t = coefficient[0] / standard_error[0] if standard_error[0] else float("nan")
    alpha_p = math.erfc(abs(alpha_t) / math.sqrt(2.0)) if math.isfinite(alpha_t) else float("nan")
    return {
        "n": n,
        "hac_lags": usable_lags,
        "daily_alpha_intercept": float(coefficient[0]),
        "annualized_alpha_intercept": float(252.0 * coefficient[0]),
        "beta_to_benchmark": float(coefficient[1]),
        "alpha_hac_se_daily": float(standard_error[0]),
        "alpha_t_stat": float(alpha_t),
        "alpha_normal_two_sided_p": float(alpha_p),
        "daily_return_correlation": float(np.corrcoef(y, x)[0, 1]),
    }


def metric_from_returns(samples: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Annualized arithmetic mean and annualized Sharpe for bootstrap samples."""

    mean = samples.mean(axis=1)
    vol = samples.std(axis=1, ddof=1)
    annual_mean = 252.0 * mean
    sharpe = np.sqrt(252.0) * mean / vol
    return annual_mean, sharpe


def moving_block_bootstrap(
    returns: pd.DataFrame,
    *,
    block_length: int,
    reps: int,
    seed: int,
) -> dict[tuple[str, str], dict[str, np.ndarray]]:
    """Joint circular moving-block bootstrap for all paired comparisons.

    Resampling common date blocks across every column preserves each pair's
    contemporaneous relation as well as serial structure within each block.
    It quantifies sampling uncertainty; it is not a multiple-testing-adjusted
    null p-value.
    """

    values = returns.to_numpy(dtype=float)
    n, n_series = values.shape
    if n_series != 4:
        raise ValueError("Expected M1, M3, B&H, and price-trend return columns")
    names = list(returns.columns)
    rng = np.random.default_rng(seed)
    blocks_per_sample = int(math.ceil(n / block_length))
    offsets = np.arange(block_length, dtype=int)
    batch_size = 250
    out: dict[tuple[str, str], dict[str, list[np.ndarray]]] = {}
    pairs = [("M1", "MSTR_buy_and_hold"), ("M3", "MSTR_buy_and_hold"), ("M1", "MSTR_close_above_50SMA"), ("M3", "MSTR_close_above_50SMA")]
    for pair in pairs:
        out[pair] = {"annualized_mean_difference": [], "annualized_sharpe_difference": []}
    col = {name: index for index, name in enumerate(names)}
    for first in range(0, reps, batch_size):
        size = min(batch_size, reps - first)
        starts = rng.integers(0, n, size=(size, blocks_per_sample))
        index = (starts[:, :, None] + offsets[None, None, :]) % n
        index = index.reshape(size, -1)[:, :n]
        sampled = values[index]
        annual_mean, sharpe = metric_from_returns(sampled)
        for left, right in pairs:
            out[(left, right)]["annualized_mean_difference"].append(
                annual_mean[:, col[left]] - annual_mean[:, col[right]]
            )
            out[(left, right)]["annualized_sharpe_difference"].append(
                sharpe[:, col[left]] - sharpe[:, col[right]]
            )
    return {
        pair: {metric: np.concatenate(parts) for metric, parts in series.items()}
        for pair, series in out.items()
    }


def bootstrap_rows(returns: pd.DataFrame) -> pd.DataFrame:
    observed_mean, observed_sharpe = metric_from_returns(returns.to_numpy(dtype=float)[None, :, :])
    observed_mean = observed_mean[0]
    observed_sharpe = observed_sharpe[0]
    column = {name: i for i, name in enumerate(returns.columns)}
    rows: list[dict[str, object]] = []
    for block_length in BOOTSTRAP_BLOCKS:
        boot = moving_block_bootstrap(
            returns,
            block_length=block_length,
            reps=BOOTSTRAP_REPS,
            seed=SEED + block_length,
        )
        for (left, right), distribution in boot.items():
            for metric, values in distribution.items():
                if metric == "annualized_mean_difference":
                    observed = observed_mean[column[left]] - observed_mean[column[right]]
                else:
                    observed = observed_sharpe[column[left]] - observed_sharpe[column[right]]
                rows.append(
                    {
                        "strategy": left,
                        "benchmark": right,
                        "metric": metric,
                        "block_length_sessions": block_length,
                        "bootstrap_reps": BOOTSTRAP_REPS,
                        "observed": float(observed),
                        "percentile_ci_2_5": float(np.quantile(values, 0.025)),
                        "percentile_ci_97_5": float(np.quantile(values, 0.975)),
                        "resample_fraction_less_or_equal_zero": float(np.mean(values <= 0.0)),
                    }
                )
    return pd.DataFrame(rows)


def main() -> None:
    # Guard the source boundary explicitly.  No HOLDOUT_* or concurrent files
    # are listed here or read below.
    authoritative = (SOURCE / "AUTHORITATIVE_ARTIFACTS.md").read_text()
    required = ["FROZEN_RULES.json", "SEALED_PANEL.parquet", "SEALED_SIGNALS.parquet", "DEV_GRID.csv"]
    if not all(name in authoritative for name in required):
        raise RuntimeError("Expected authoritative mNAV artifacts are not declared")

    frozen = json.loads((SOURCE / "FROZEN_RULES.json").read_text())
    if frozen["status"] != "FROZEN BEFORE SEALED-VALIDATION RUN":
        raise RuntimeError("Frozen rule file has an unexpected status")
    panel = pd.read_parquet(SOURCE / "SEALED_PANEL.parquet")
    signals = pd.read_parquet(SOURCE / "SEALED_SIGNALS.parquet")
    if panel.index.min() > VALID_START or panel.index.max() != VALID_END:
        raise RuntimeError("Unexpected sealed panel coverage")
    if not panel.index.equals(signals.index):
        raise RuntimeError("Panel and frozen signal indices do not match")
    valid_panel = panel.loc[VALID_START:VALID_END].copy()

    full_signals: dict[str, pd.Series] = {
        "M1": signals["M1"].astype(bool),
        "M3": signals["M3"].astype(bool),
    }
    full_signals["MSTR_close_above_50SMA"] = trend50_signal(panel)

    equity: dict[str, pd.Series] = {}
    returns: dict[str, pd.Series] = {}
    rows: list[dict[str, object]] = []
    for name in ("M1", "M3", "MSTR_close_above_50SMA"):
        start_long = prior_signal(full_signals[name], valid_panel.index[0])
        eq, trades, ret = execute(valid_panel, full_signals[name], start_long=start_long)
        equity[name], returns[name] = eq, ret
        rows.append(
            {"strategy": name, **performance(eq, ret, trades, full_signals[name].reindex(valid_panel.index), start_long=start_long)}
        )

    always_long = pd.Series(True, index=valid_panel.index)
    eq, trades, ret = execute(valid_panel, always_long, start_long=True)
    equity["MSTR_buy_and_hold"], returns["MSTR_buy_and_hold"] = eq, ret
    rows.append(
        {"strategy": "MSTR_buy_and_hold", **performance(eq, ret, trades, always_long, start_long=True)}
    )
    perf = pd.DataFrame(rows)
    # Exact baseline M1/M3 published values are a guard against silently
    # changing the execution or cost convention in this independent audit.
    reference = pd.read_csv(SOURCE / "DEV_VS_SEALED_SUMMARY.csv")
    sealed_reference = reference.loc[
        (reference["period"] == "sealed_2023_01_03_to_2026_08_10") & reference["strategy"].isin(["M1", "M3"])
    ].set_index("strategy")
    for name in ("M1", "M3"):
        ours = perf.set_index("strategy").loc[name]
        if not np.isclose(ours["total_return"], sealed_reference.loc[name, "total_return"], atol=1e-12):
            raise AssertionError(f"{name} total return does not reproduce authoritative output")
        if not np.isclose(ours["annualized_sharpe"], sealed_reference.loc[name, "annualized_sharpe"], atol=1e-12):
            raise AssertionError(f"{name} Sharpe does not reproduce authoritative output")

    ordered = ["M1", "M3", "MSTR_buy_and_hold", "MSTR_close_above_50SMA"]
    returns_frame = pd.DataFrame({name: returns[name] for name in ordered})
    if returns_frame.isna().any().any() or len(returns_frame) != len(valid_panel):
        raise RuntimeError("Unexpected return alignment or missing values")
    bootstrap = bootstrap_rows(returns_frame)

    hac_rows: list[dict[str, object]] = []
    regression_rows: list[dict[str, object]] = []
    for left, right in [
        ("M1", "MSTR_buy_and_hold"),
        ("M3", "MSTR_buy_and_hold"),
        ("M1", "MSTR_close_above_50SMA"),
        ("M3", "MSTR_close_above_50SMA"),
    ]:
        differential = (returns_frame[left] - returns_frame[right]).to_numpy()
        for lags in HAC_LAGS:
            hac_rows.append(
                {"strategy": left, "benchmark": right, **newey_west_mean_test(differential, lags)}
            )
            regression_rows.append(
                {
                    "strategy": left,
                    "benchmark": right,
                    **newey_west_single_factor_regression(
                        returns_frame[left].to_numpy(), returns_frame[right].to_numpy(), lags
                    ),
                }
            )
    hac = pd.DataFrame(hac_rows)
    regression = pd.DataFrame(regression_rows)
    cash_rows: list[dict[str, object]] = []
    for name in ("M1", "M3", "MSTR_close_above_50SMA", "MSTR_buy_and_hold"):
        for lags in HAC_LAGS:
            cash_rows.append(
                {"strategy": name, "benchmark": "zero_cash_return", **newey_west_mean_test(returns_frame[name].to_numpy(), lags)}
            )
    cash_hac = pd.DataFrame(cash_rows)

    dev_grid = pd.read_csv(SOURCE / "DEV_GRID.csv")
    dev_grid["sharpe_rank_descending"] = dev_grid["annualized_sharpe"].rank(method="min", ascending=False).astype(int)
    selection = {
        "development_grid_variants": int(len(dev_grid)),
        "M1_development_sharpe_rank": int(
            dev_grid.loc[
                (dev_grid["premium_momentum_days"] == 10)
                & (dev_grid["premium_sma_days"] == 50)
                & (dev_grid["btc_momentum_days"].astype(str) == "none"),
                "sharpe_rank_descending",
            ].iloc[0]
        ),
        "M3_development_sharpe_rank": int(
            dev_grid.loc[
                (dev_grid["premium_momentum_days"] == 20)
                & (dev_grid["premium_sma_days"] == 50)
                & (dev_grid["btc_momentum_days"].astype(str) == "20"),
                "sharpe_rank_descending",
            ].iloc[0]
        ),
        "development_variants_with_positive_sharpe": int((dev_grid["annualized_sharpe"] > 0).sum()),
        "development_variants_with_positive_total_return": int((dev_grid["total_return"] > 0).sum()),
    }

    perf.to_csv(HERE / "PERFORMANCE_REPLICATION.csv", index=False)
    bootstrap.to_csv(HERE / "BLOCK_BOOTSTRAP_COMPARISONS.csv", index=False)
    hac.to_csv(HERE / "HAC_MEAN_DIFFERENTIALS.csv", index=False)
    regression.to_csv(HERE / "HAC_SINGLE_FACTOR_ALPHA.csv", index=False)
    cash_hac.to_csv(HERE / "HAC_MEAN_VS_ZERO_CASH.csv", index=False)
    (HERE / "SELECTION_CONTEXT.json").write_text(json.dumps(selection, indent=2) + "\n")

    print("Independent mNAV statistical audit complete")
    print("\nPerformance replication:")
    print(perf.to_string(index=False))
    print("\nHAC mean differentials:")
    print(hac.to_string(index=False))
    print("\nHAC single-factor alpha diagnostics:")
    print(regression.to_string(index=False))
    print("\nHAC mean return versus zero-cash assumption:")
    print(cash_hac.to_string(index=False))
    print("\nBlock-bootstrap comparison summary:")
    print(bootstrap.to_string(index=False))
    print("\nSelection context:")
    print(json.dumps(selection, indent=2))


if __name__ == "__main__":
    main()
