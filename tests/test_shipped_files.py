"""Every file the trading cycle and the desk read at runtime must ship with the
repo, so a fresh clone can score and trade without the research datasets.
(A trimmed reports/universe_ranking.csv once made every signal fail to score.)"""
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

RUNTIME_FILES = [
    "models/pead_model_expanded.joblib",
    "data/pead_labeled_features_expanded.parquet",
    "data/expanded_universe_all_tickers.txt",
    "reports/universe_ranking.csv",
    "reports/universe_selection.txt",
    "reports/circuit_breaker_daily_production.csv",
    "reports/higher_sharpe/inputs/french_daily.zip",
    "reports/pead_live_backtest_metrics.json",
    "reports/pead_live_backtest_monte_carlo.json",
    "research/preregistrations.jsonl",
]


@pytest.mark.parametrize("path", RUNTIME_FILES)
def test_runtime_file_ships_with_the_repo(path):
    assert (REPO / path).is_file(), f"{path} is read at runtime but missing from the repo"


def test_cached_earnings_history_covers_the_watched_universe():
    """Tickers without a cached file (new listings, renames) fall back to live
    data in earnings.ingestion; the cache just has to cover nearly all of them."""
    from bot.earnings_watcher import load_validated_universe

    tickers = load_validated_universe()
    cached = [t for t in tickers if (REPO / "data" / "earnings_raw" / f"{t}.parquet").is_file()]
    assert len(cached) >= 0.95 * len(tickers), f"only {len(cached)}/{len(tickers)} tickers have cached earnings"
