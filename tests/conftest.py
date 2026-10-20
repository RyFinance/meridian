"""Suite-wide isolation for live state files that library code appends to.

earnings.ingestion.fetch_ticker_earnings_live records every announcement date it
sees into bot/state/earnings_schedule_log.jsonl. Tests (including the ones that
hit the real network, or fake a yfinance Ticker) must never write the real bot's
log, so every test gets its own empty one.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_schedule_log(tmp_path, monkeypatch):
    import earnings.ingestion as ingestion

    monkeypatch.setattr(ingestion, "SCHEDULE_LOG_FILE", tmp_path / "earnings_schedule_log.jsonl")
    yield


@pytest.fixture(autouse=True)
def _isolated_broker_state(tmp_path, monkeypatch):
    """Broker selection, credentials and broker ledgers live in a per-test
    directory, and live trading is off unless a test turns it on."""
    from bot import broker_config

    state = tmp_path / "broker_state"
    monkeypatch.setattr(broker_config, "STATE_DIR", state)
    monkeypatch.setattr(broker_config, "SELECTION_PATH", state / "broker.json")
    monkeypatch.setattr(broker_config, "CREDENTIALS_PATH", state / "brokers.local.json")
    monkeypatch.delenv("MERIDIAN_ALLOW_LIVE", raising=False)
    monkeypatch.delenv("MERIDIAN_LIVE_MAX_ORDER_USD", raising=False)
    yield


_REPO = __import__("pathlib").Path(__file__).resolve().parent.parent
_RESEARCH_DATA = (_REPO / "data", _REPO / "reports")


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    """Research tests that read the large research datasets (not shipped in the
    slim repo; re-pull them with the data/ scripts) skip instead of failing."""
    try:
        return (yield)
    except FileNotFoundError as exc:
        missing = __import__("pathlib").Path(str(exc.filename or "")).resolve()
        if any(missing.is_relative_to(root) for root in _RESEARCH_DATA):
            pytest.skip(f"research dataset not in this checkout: {missing.relative_to(_REPO)}")
        raise


# Tests that read the real cached daily prices (data/raw/, filled by the first
# trading cycle or data/ingestion.refresh_cached_history) or a real heartbeat.
_NEEDS_PRICE_CACHE = (
    "test_live_backtest_providers.py::",
    "test_dashboard_backend.py::test_equity_curve_has_one_point_per_exit_date",
    "test_dashboard_backend.py::test_open_position_reconstructed_via_paper_execution_client",
    "test_dashboard_backend.py::test_reopened_ticker_preserves_full_trade_history",
    "test_dashboard_backend.py::test_stats_with_two_closed_trades_is_not_insufficient",
    "test_dashboard_backend.py::test_status_endpoint_real",
)


def pytest_collection_modifyitems(config, items):
    cache = _REPO / "data" / "raw" / "AAPL.parquet"
    heartbeat = _REPO / "bot" / "state" / "heartbeat.txt"
    if cache.exists() and heartbeat.exists():
        return
    skip = pytest.mark.skip(reason="needs the local price cache and bot heartbeat; run scripts/cycle.sh once")
    for item in items:
        if any(key in item.nodeid for key in _NEEDS_PRICE_CACHE):
            item.add_marker(skip)
