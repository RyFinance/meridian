"""Tests for research/collectors/* -- all HTTP is mocked; nothing here hits the network.

Covers: the common snapshot writer (immutability, manifest append-only, hashing), and each
collector's run_once() against a fake requests.get, including its handling of a non-200
(403/404/451) response.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from research.collectors import (
    binance_futures,
    bybit,
    cboe_options,
    common,
    deribit,
    etf_holdings,
    finra_regsho,
    finra_short_interest,
    ibkr_borrow,
    okx,
)


class FakeResponse:
    def __init__(self, status_code=200, content=b"{}", url="https://example.test/x"):
        self.status_code = status_code
        self.content = content
        self.url = url

    @property
    def text(self):
        return self.content.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------------------
# common.py
# --------------------------------------------------------------------------------------

def test_write_snapshot_creates_dated_dir_and_manifest_line(tmp_path):
    when = dt.datetime(2026, 9, 25, 12, 34, 56, tzinfo=dt.timezone.utc)
    rec = common.write_snapshot("demo", "foo", b"hello world", when=when, root=tmp_path)
    expected_dir = tmp_path / "demo" / "2026" / "09" / "25"
    files = list(expected_dir.glob("foo.*.json"))
    assert len(files) == 1
    assert files[0].read_bytes() == b"hello world"
    manifest = (tmp_path / "demo" / "manifest.jsonl").read_text().strip().splitlines()
    assert len(manifest) == 1
    line = json.loads(manifest[0])
    assert line["sha256"] == rec["sha256"] == common.sha256_bytes(b"hello world")
    assert line["bytes"] == 11


def test_write_snapshot_never_overwrites(tmp_path):
    when = dt.datetime(2026, 9, 25, 12, 0, 0, tzinfo=dt.timezone.utc)
    common.write_snapshot("demo", "foo", b"one", when=when, root=tmp_path)
    with pytest.raises(common.SnapshotExists):
        common.write_snapshot("demo", "foo", b"one", when=when, root=tmp_path)


def test_write_snapshot_different_content_same_second_is_a_new_file(tmp_path):
    when = dt.datetime(2026, 9, 25, 12, 0, 0, tzinfo=dt.timezone.utc)
    r1 = common.write_snapshot("demo", "foo", b"one", when=when, root=tmp_path)
    r2 = common.write_snapshot("demo", "foo", b"two", when=when, root=tmp_path)
    assert r1["path"] != r2["path"]
    manifest = (tmp_path / "demo" / "manifest.jsonl").read_text().strip().splitlines()
    assert len(manifest) == 2


def test_manifest_is_append_only_across_runs(tmp_path):
    common.write_snapshot("demo", "a", b"1", when=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc), root=tmp_path)
    common.write_snapshot("demo", "b", b"2", when=dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc), root=tmp_path)
    lines = (tmp_path / "demo" / "manifest.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["name"] == "a"
    assert json.loads(lines[1])["name"] == "b"


def test_http_get_does_not_retry_a_404(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(url)
        return FakeResponse(status_code=404, content=b"not found")

    monkeypatch.setattr("requests.get", fake_get)
    resp = common.http_get("https://example.test/missing")
    assert resp.status_code == 404
    assert len(calls) == 1  # no retry burned on an informative 404


def test_http_get_retries_transient_error_then_succeeds(monkeypatch):
    import requests

    attempts = {"n": 0}

    def fake_get(url, params=None, headers=None, timeout=None):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise requests.exceptions.ConnectionError("boom")
        return FakeResponse(status_code=200, content=b"ok")

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr(common.time, "sleep", lambda *_a, **_k: None)
    resp = common.http_get("https://example.test/ok", retries=3)
    assert resp.status_code == 200
    assert attempts["n"] == 2


# --------------------------------------------------------------------------------------
# per-collector run_once() -- happy path + one blocked/unavailable path each
# --------------------------------------------------------------------------------------

def _patch_root(monkeypatch, module, tmp_path):
    """Redirect a collector's write_snapshot calls into tmp_path via common.COLLECT_ROOT."""
    monkeypatch.setattr(common, "COLLECT_ROOT", tmp_path)


def test_binance_futures_run_once_writes_five_files_per_symbol(monkeypatch, tmp_path):
    _patch_root(monkeypatch, binance_futures, tmp_path)

    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(status_code=200, content=json.dumps({"symbol": params.get("symbol")}).encode())

    monkeypatch.setattr("requests.get", fake_get)
    result = binance_futures.run_once(symbols=["BTCUSDT"])
    assert result["status"] == "ok"
    assert result["n_files"] == 5
    assert result["blocked"] == []


def test_binance_futures_run_once_records_451_as_blocked(monkeypatch, tmp_path):
    _patch_root(monkeypatch, binance_futures, tmp_path)

    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(status_code=451, content=b"geo-blocked")

    monkeypatch.setattr("requests.get", fake_get)
    result = binance_futures.run_once(symbols=["BTCUSDT"])
    assert result["n_files"] == 0
    assert result["blocked"], "a 451 must be surfaced, not silently dropped"


def test_bybit_run_once_happy_path(monkeypatch, tmp_path):
    _patch_root(monkeypatch, bybit, tmp_path)

    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(status_code=200, content=b'{"result": {"list": []}}')

    monkeypatch.setattr("requests.get", fake_get)
    result = bybit.run_once(symbols=["BTCUSDT"])
    assert result["status"] == "ok"
    assert result["n_files"] == 2  # tickers.linear + open-interest.BTCUSDT


def test_okx_run_once_happy_path(monkeypatch, tmp_path):
    _patch_root(monkeypatch, okx, tmp_path)

    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(status_code=200, content=b'{"code": "0", "data": []}')

    monkeypatch.setattr("requests.get", fake_get)
    result = okx.run_once()
    assert result["status"] == "ok"
    assert result["n_files"] == 2


def test_deribit_run_once_happy_path(monkeypatch, tmp_path):
    _patch_root(monkeypatch, deribit, tmp_path)

    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(status_code=200, content=b'{"result": []}')

    monkeypatch.setattr("requests.get", fake_get)
    result = deribit.run_once(currencies=["BTC"])
    assert result["status"] == "ok"
    assert result["n_files"] == 2  # option book summary + future book summary


def test_cboe_options_walks_back_to_most_recent_published_day(monkeypatch, tmp_path):
    _patch_root(monkeypatch, cboe_options, tmp_path)

    seen_urls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        seen_urls.append(url)
        # Only the third-most-recent weekday (index 2) is "published".
        if len(seen_urls) < 3:
            return FakeResponse(status_code=404, content=b"")
        return FakeResponse(status_code=200, content=b'{"ratios": []}')

    monkeypatch.setattr("requests.get", fake_get)
    when = dt.datetime(2026, 9, 25, 22, 0, tzinfo=dt.timezone.utc)  # a Friday
    result = cboe_options.run_once(when=when, max_lookback=5)
    assert result["status"] == "partial"  # found the file, but only after two 404s
    assert result["n_files"] == 1
    assert len(result["errors"]) == 2


def test_cboe_options_all_days_unpublished_is_reported_not_crashed(monkeypatch, tmp_path):
    _patch_root(monkeypatch, cboe_options, tmp_path)

    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(status_code=404, content=b"")

    monkeypatch.setattr("requests.get", fake_get)
    result = cboe_options.run_once(max_lookback=3)
    assert result["status"] == "failed"
    assert result["n_files"] == 0
    assert len(result["errors"]) == 3


def test_finra_regsho_fetches_all_five_tapes_once_a_day_is_found(monkeypatch, tmp_path):
    _patch_root(monkeypatch, finra_regsho, tmp_path)

    def fake_get(url, params=None, headers=None, timeout=None):
        if "CNMSshvol" in url and url.endswith("20260924.txt"):
            return FakeResponse(status_code=200, content=b"Date|Symbol\r\n")
        if "CNMSshvol" in url:
            return FakeResponse(status_code=403, content=b"not yet")
        return FakeResponse(status_code=200, content=b"Date|Symbol\r\n")

    monkeypatch.setattr("requests.get", fake_get)
    when = dt.datetime(2026, 9, 24, 23, 0, tzinfo=dt.timezone.utc)  # a Thursday
    result = finra_regsho.run_once(when=when, max_lookback=3)
    assert result["n_files"] == 5


def test_finra_short_interest_picks_most_recent_published_settlement(monkeypatch, tmp_path):
    _patch_root(monkeypatch, finra_short_interest, tmp_path)

    def fake_get(url, params=None, headers=None, timeout=None):
        if "20260915" in url:
            return FakeResponse(status_code=200, content=b"col1|col2\r\n")
        return FakeResponse(status_code=403, content=b"not published")

    monkeypatch.setattr("requests.get", fake_get)
    when = dt.datetime(2026, 9, 25, tzinfo=dt.timezone.utc)
    result = finra_short_interest.run_once(when=when)
    assert result["n_files"] == 1
    assert "20260915" in result["files"][0]


def test_etf_holdings_run_once_happy_path(monkeypatch, tmp_path):
    _patch_root(monkeypatch, etf_holdings, tmp_path)

    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(status_code=200, content=b"ticker,shares\nAAPL,100\n")

    monkeypatch.setattr("requests.get", fake_get)
    result = etf_holdings.run_once()
    assert result["status"] == "ok"
    assert result["n_files"] == 2  # IVV + SPY


def test_ibkr_borrow_falls_through_mirrors_and_reports_failure(monkeypatch, tmp_path):
    _patch_root(monkeypatch, ibkr_borrow, tmp_path)

    def fake_get(url, params=None, headers=None, timeout=None):
        raise __import__("requests").exceptions.ReadTimeout("timed out")

    monkeypatch.setattr("requests.get", fake_get)
    result = ibkr_borrow.run_once(timeout=1)
    assert result["status"] == "failed"
    assert result["n_files"] == 0
    assert len(result["errors"]) == 3  # one per mirror


def test_ibkr_borrow_succeeds_on_first_reachable_mirror(monkeypatch, tmp_path):
    _patch_root(monkeypatch, ibkr_borrow, tmp_path)

    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(status_code=200, content=b"#SYM\tRebate\tFee\nAAPL\t4.5\t0.25\n")

    monkeypatch.setattr("requests.get", fake_get)
    result = ibkr_borrow.run_once()
    assert result["status"] == "ok"
    assert result["n_files"] == 1
