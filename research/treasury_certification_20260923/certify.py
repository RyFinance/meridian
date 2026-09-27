"""Independent, development-only audit of the frozen IEF-versus-SHY test.

This intentionally reads source ETF files directly and does not import the
structural_frontier evaluator. It never reads a price after 2014-12-31.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/treasury_certification_20260923"
END = pd.Timestamp("2014-12-31")
START = pd.Timestamp("2003-01-02")
ANNUAL = 252
BLOCK = 21
SEED = 20260923
REPLICATION_WORLDS = 5000
FUTURE_WORLDS = 10000


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(symbol: str) -> pd.DataFrame:
    path = ROOT / "data/multiasset/etf" / f"{symbol}.parquet"
    # Arrow filters ensure no held-out row enters the research process.
    frame = pd.read_parquet(path, columns=["date", "open", "source"],
                            filters=[("date", ">=", START), ("date", "<=", END)])
    assert frame["date"].is_unique and frame["date"].is_monotonic_increasing
    assert frame["open"].notna().all() and (frame["open"] > 0).all()
    assert set(frame["source"]) == {"yfinance auto_adjust=True"}
    return frame.set_index("date")[["open"]]


def drawdown(intervals: np.ndarray) -> float:
    wealth = np.r_[1.0, np.cumprod(1.0 + intervals)]
    return float(np.min(wealth / np.maximum.accumulate(wealth) - 1.0))


def measures(intervals: np.ndarray) -> dict:
    arr = np.asarray(intervals, dtype=float)
    return {
        "annual_mean": float(arr.mean() * ANNUAL),
        "annual_sharpe": float(arr.mean() / arr.std(ddof=1) * np.sqrt(ANNUAL)),
        "compounded_total": float(np.prod(1.0 + arr) - 1.0),
        "max_drawdown": drawdown(arr),
    }


def block_indices(rng: np.random.Generator, count: int, n: int,
                  length: int, block: int) -> np.ndarray:
    """Circular resampling in independently drawn, consecutive blocks."""
    starts = rng.integers(n, size=(count, (length + block - 1) // block))
    return ((starts[:, :, None] + np.arange(block)[None, None, :]) % n).reshape(count, -1)[:, :length]


def bootstrap_tail_and_ci(x: np.ndarray, stress: np.ndarray) -> dict:
    """Recompute the preregistered centered one-sided null from raw returns."""
    rng = np.random.default_rng(SEED)
    mean = x.mean()
    sample_means = []
    sample_stress_means = []
    sample_sharpes = []
    for _ in range(REPLICATION_WORLDS // 200):
        take = block_indices(rng, 200, len(x), len(x), BLOCK)
        worlds = x[take] - mean
        stressed = stress[take] - mean
        sample_means.append(worlds.mean(axis=1))
        sample_stress_means.append(stressed.mean(axis=1))
        sample_sharpes.append(worlds.mean(axis=1) / worlds.std(axis=1, ddof=1) * np.sqrt(ANNUAL))
    sample_means = np.concatenate(sample_means)
    sample_stress_means = np.concatenate(sample_stress_means)
    sample_sharpes = np.concatenate(sample_sharpes)
    tail = (1 + np.count_nonzero(sample_means >= mean)) / (REPLICATION_WORLDS + 1)
    years = (END - START).days / 365.25
    gate = 1.8 / np.sqrt(years)
    # Rank each zero-premium world against the empirical centered-null worlds.
    # Searching the sorted array avoids a 5,000x5,000 temporary matrix.
    sorted_means = np.sort(sample_means)
    ranks = np.searchsorted(sorted_means, sample_means, side="left")
    p_world = (1 + REPLICATION_WORLDS - ranks) / (REPLICATION_WORLDS + 1)
    pass_world = (sample_sharpes >= gate) & (sample_stress_means > 0) & (p_world < 0.05 / 3)
    return {
        "one_sided_null_p": float(tail),
        "annual_mean_95pct_block_ci": (np.quantile(sample_means + mean, [0.025, 0.975]) * ANNUAL).tolist(),
        "full_gate_false_pass_probability": float(pass_world.mean()),
        "full_gate_false_pass_mc_se": float(np.sqrt(pass_world.mean() * (1-pass_world.mean()) / REPLICATION_WORLDS)),
        "annual_sharpe_gate": float(gate),
        "seed": SEED,
        "worlds": REPLICATION_WORLDS,
        "block_sessions": BLOCK,
    }


def monthly_barbell(dates: pd.DatetimeIndex, tlt: np.ndarray, shy: np.ndarray) -> np.ndarray:
    """Fresh implementation of fixed 1/3 TLT, 2/3 SHY at each month's first open."""
    holdings = np.array([1.0 / 3, 2.0 / 3.0])
    interval = []
    for day, r_tlt, r_shy in zip(dates[:-1], tlt, shy):
        if interval and day.month != dates[len(interval) - 1].month:
            holdings = np.array([1.0 / 3, 2.0 / 3.0])
        r = np.array([r_tlt, r_shy])
        total = float(holdings @ r)
        interval.append(total)
        holdings = holdings * (1.0 + r) / (1.0 + total)
    return np.array(interval)


def best_window_removed(dates: pd.DatetimeIndex, x: np.ndarray, months: int) -> dict:
    best = None
    for begin in dates:
        finish = begin + pd.DateOffset(months=months)
        if finish > dates[-1]:
            break
        mask = (dates >= begin) & (dates < finish)
        contribution = x[mask].sum()
        if best is None or contribution > best[0]:
            best = (contribution, begin, finish, mask)
    return {"start": str(best[1].date()), "end_exclusive": str(best[2].date()),
            "remaining": measures(x[~best[3]])}


def alternate_paths(x: np.ndarray, stress: np.ndarray) -> dict:
    """Potential 3/5y futures under only the observed development return law.

    These are illustrative predictive distributions, never a held-out result or
    validation unlock. Both 21- and 63-session blocks are fixed robustness
    checks rather than parameter choices for the original candidate.
    """
    out = {}
    rng = np.random.default_rng(83219741)
    for horizon_years in (3, 5):
        length = ANNUAL * horizon_years
        for block in (21, 63):
            annual_means, sharpes, stressed = [], [], []
            for _ in range(FUTURE_WORLDS // 200):
                take = block_indices(rng, 200, len(x), length, block)
                w, s = x[take], stress[take]
                annual_means.append(w.mean(axis=1) * ANNUAL)
                sharpes.append(w.mean(axis=1) / w.std(axis=1, ddof=1) * np.sqrt(ANNUAL))
                stressed.append(s.mean(axis=1) * ANNUAL)
            means = np.concatenate(annual_means)
            sr = np.concatenate(sharpes)
            st = np.concatenate(stressed)
            key = f"{horizon_years}y_{block}d_blocks"
            out[key] = {
                "annual_mean_5_50_95pct": np.quantile(means, [.05, .5, .95]).tolist(),
                "sharpe_5_50_95pct": np.quantile(sr, [.05, .5, .95]).tolist(),
                "prob_positive_stress_mean": float(np.mean(st > 0)),
                "prob_sharpe_at_least_0_75": float(np.mean(sr >= .75)),
                "prob_both_validation_effect_gates": float(np.mean((sr >= .75) & (st > 0))),
                "worlds": FUTURE_WORLDS,
            }
    return out


def main() -> None:
    symbols = ("IEF", "SHY", "TLT", "SPY")
    book = {symbol: source(symbol) for symbol in symbols}
    days = book["IEF"].index
    for frame in book.values():
        days = days.intersection(frame.index)
    days = days.sort_values()
    assert days[0] == START and days[-1] == END
    interval = {symbol: book[symbol].loc[days, "open"].pct_change().iloc[1:].to_numpy(float)
                for symbol in symbols}
    ie = interval["IEF"].copy()
    ie[[0, -1]] -= .0003
    ie_stress = interval["IEF"].copy()
    ie_stress[[0, -1]] -= .0009
    shy = interval["SHY"]
    active = ie - shy
    active_stress = ie_stress - shy
    barbell = monthly_barbell(days, interval["TLT"], shy)
    interval_dates = days[:-1]
    annual = {str(y): float(active[interval_dates.year == y].sum())
              for y in sorted(set(interval_dates.year))}
    leave_year = {str(y): measures(active[interval_dates.year != y])
                  for y in sorted(set(interval_dates.year))}
    leave_year_sorted = sorted(leave_year.items(), key=lambda kv: kv[1]["annual_sharpe"])
    source_paths = {s: ROOT / "data/multiasset/etf" / f"{s}.parquet" for s in symbols}
    result = {
        "purpose": "independent certification of frozen development evidence, no validation read",
        "source_hashes": {s: file_hash(p) for s, p in source_paths.items()},
        "dates": [str(days[0].date()), str(days[-1].date())],
        "intervals": len(active),
        "ietf_base": measures(ie),
        "shy": measures(shy),
        "active_base": measures(active),
        "active_stress": measures(active_stress),
        "barbell": measures(barbell),
        "active_vs_barbell": measures(ie - barbell),
        "active_spy_minus_shy_corr": float(np.corrcoef(active, interval["SPY"] - shy)[0, 1]),
        "annual_active_sum": annual,
        "leave_one_calendar_year_out": leave_year,
        "lowest_sharpe_leave_one_year_out": [{"year": y, **v} for y, v in leave_year_sorted[:3]],
        "remove_2008_and_2011": measures(active[~interval_dates.year.isin([2008, 2011])]),
        "best_12m_removed": best_window_removed(interval_dates, active, 12),
        "best_24m_removed": best_window_removed(interval_dates, active, 24),
        "null": bootstrap_tail_and_ci(active, active_stress),
        "alternate_development_law_futures": alternate_paths(active, active_stress),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "independent_replication.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("dates", "intervals", "active_base", "null",
                                                "lowest_sharpe_leave_one_year_out", "remove_2008_and_2011",
                                                "alternate_development_law_futures")}, indent=2))


if __name__ == "__main__":
    main()
