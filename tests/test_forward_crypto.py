"""Tests for research/forward_crypto: collector (mocked HTTP) and targets (mocked snapshot fixtures).

No network. No registry write -- these tests never touch reports/forward/registry.jsonl or
research/preregistrations.jsonl. No decision day used here is inside or before the locked validation
window (2023-01-01..2026-08-31); the refusal for that window is itself tested.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pytest

from research.crypto_funding_xs import core as c
from research.forward_crypto import collector, targets

UTC = dt.timezone.utc


def T(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text).replace(tzinfo=UTC)


# ============================================================================================ collector

class _Resp:
    def __init__(self, status_code, content, text=""):
        self.status_code = status_code
        self.content = content
        self.text = text or content.decode() if isinstance(content, bytes) else str(content)


def test_get_raises_geoblocked_on_451(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return _Resp(451, b"blocked")

    monkeypatch.setattr("requests.get", fake_get)
    with pytest.raises(collector.GeoBlocked):
        collector._get("/fapi/v1/exchangeInfo")


def test_get_never_retries_a_451(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, params=None, headers=None, timeout=None):
        calls["n"] += 1
        return _Resp(451, b"blocked")

    monkeypatch.setattr("requests.get", fake_get)
    with pytest.raises(collector.GeoBlocked):
        collector._get("/fapi/v1/exchangeInfo")
    assert calls["n"] == 1


def test_get_retries_transient_errors_then_succeeds(monkeypatch):
    import requests

    calls = {"n": 0}

    def fake_get(url, params=None, headers=None, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.exceptions.ConnectionError("boom")
        return _Resp(200, b'{"ok": true}')

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr(collector.time, "sleep", lambda *_a, **_k: None)
    out = collector._get("/fapi/v1/exchangeInfo", retries=5)
    assert json.loads(out) == {"ok": True}
    assert calls["n"] == 3


def test_write_raw_never_overwrites(tmp_path):
    now = T("2026-10-01T00:01:00")
    p1 = collector._write_raw(tmp_path, "exchangeInfo", b'{"a": 1}', now)
    assert p1.exists()
    with pytest.raises(collector.CollectorError):
        collector._write_raw(tmp_path, "exchangeInfo", b'{"a": 1}', now)


def test_usdt_perp_symbols_filters_type_quote_status():
    ei = {"symbols": [
        {"symbol": "BTCUSDT", "contractType": "PERPETUAL", "quoteAsset": "USDT", "status": "TRADING"},
        {"symbol": "BTCUSD_PERP", "contractType": "PERPETUAL", "quoteAsset": "USD", "status": "TRADING"},
        {"symbol": "ETHUSDT_250926", "contractType": "CURRENT_QUARTER", "quoteAsset": "USDT", "status": "TRADING"},
        {"symbol": "OLDUSDT", "contractType": "PERPETUAL", "quoteAsset": "USDT", "status": "SETTLING"},
        {"symbol": "ETHUSDT", "contractType": "PERPETUAL", "quoteAsset": "USDT", "status": "TRADING"},
    ]}
    assert collector.usdt_perp_symbols(ei) == ["BTCUSDT", "ETHUSDT"]


def test_collect_writes_manifest_and_stops_cleanly_on_geoblock(tmp_path, monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return _Resp(451, b"blocked")

    monkeypatch.setattr("requests.get", fake_get)
    now = T("2026-10-01T00:01:00")
    out = collector.collect(now=now, out_root=tmp_path)
    assert out["blocked"] is True
    manifest = list((tmp_path / "2026-10-01").glob("_manifest.*.json"))
    assert len(manifest) == 1
    assert json.loads(manifest[0].read_text())["blocked"] is True


# ============================================================================================ targets fixtures

DECISION_DAY = "2026-10-01"  # well after the locked validation window (ends 2026-08-31)


def _ms(ts: str) -> int:
    return int(pd.Timestamp(ts, tz="UTC").timestamp() * 1000)


def _write_envelope(day_dir: Path, name: str, body, fetched_at="000100"):
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / f"{name}.{fetched_at}.deadbeef00000000.json"
    path.write_text(json.dumps({"endpoint": name, "fetched_at_utc": "2026-10-01T00:01:00.000000Z",
                                "sha256_of_raw_body": "x", "body": body}))
    return path


def _klines_for(days: list[str], opens: dict[str, float] | float, closes: dict[str, float] | float,
                quote_vol: dict[str, float] | float) -> list[list]:
    rows = []
    for d in days:
        o = opens[d] if isinstance(opens, dict) else opens
        cl = closes[d] if isinstance(closes, dict) else closes
        v = quote_vol[d] if isinstance(quote_vol, dict) else quote_vol
        open_ms = _ms(d)
        rows.append([open_ms, str(o), str(max(o, cl)), str(min(o, cl)), str(cl), "1", open_ms + 86_399_999,
                    str(v), 100, "0", "0", "0"])
    return rows


def _funding_for(times: list[str], rate: float) -> list[dict]:
    return [{"symbol": "X", "fundingTime": _ms(t), "fundingRate": f"{rate}", "markPrice": "1"} for t in times]


def _funding_settlements(decision_day: pd.Timestamp, days_back: int, per_day: int = 3) -> list[str]:
    """Binance funds every 8h (3x/day); one settlement per day is below MIN_SETTLE. ISO timestamps,
    oldest first, days_back..1 days before `decision_day` at evenly spaced hours."""
    out = []
    for k in range(days_back, 0, -1):
        base = decision_day - pd.Timedelta(days=k)
        for h in range(per_day):
            out.append((base + pd.Timedelta(hours=h * (24 // per_day))).isoformat())
    return out


@pytest.fixture
def snapshot(tmp_path):
    """A synthetic but shaped-correctly snapshot for DECISION_DAY: 30 candidate symbols, enough
    trailing volume/funding history to clear every frozen eligibility gate, with the funding signal
    monotone in symbol index so the bottom/top quintiles are exactly known in advance."""
    day_dir = tmp_path / DECISION_DAY
    decision = pd.Timestamp(DECISION_DAY)
    hist_days = [(decision - pd.Timedelta(days=k)).strftime("%Y-%m-%d") for k in range(35, 0, -1)]
    funding_times = _funding_settlements(decision, days_back=7, per_day=3)  # 21 settlements > MIN_SETTLE

    n = 30
    onboard = _ms("2026-01-01")  # well over 60 days before DECISION_DAY
    symbols = [f"SYM{i:02d}USDT" for i in range(n)]
    ei = {"symbols": [{"symbol": s, "contractType": "PERPETUAL", "quoteAsset": "USDT", "status": "TRADING",
                       "onboardDate": onboard} for s in symbols]}
    _write_envelope(day_dir, "exchangeInfo", ei)

    for i, sym in enumerate(symbols):
        # distinct, comfortably-ranked volume so every symbol lands in the top-100-by-volume universe
        vol = 10_000_000.0 + i * 10_000
        _write_envelope(day_dir, f"klines.{sym}", _klines_for(hist_days, opens=1.0 + i * 0.01, closes=1.0 + i * 0.01,
                                                              quote_vol=vol))
        # funding rate strictly increasing in i: SYM00 has the most negative (bottom quintile -> long),
        # SYM29 the most positive (top quintile -> short)
        rate = (i - (n - 1) / 2) * 0.0001
        _write_envelope(day_dir, f"fundingRate.{sym}", _funding_for(funding_times, rate=rate))
        _write_envelope(day_dir, f"premiumIndex.{sym}", {"symbol": sym, "markPrice": f"{1.0 + i * 0.01}"})
    return tmp_path


def test_decision_weights_refuses_inside_locked_validation_window(snapshot):
    with pytest.raises(targets.TargetsError, match="locked validation window"):
        targets.decision_weights("2026-08-15", root=snapshot)
    with pytest.raises(targets.TargetsError, match="locked validation window"):
        targets.decision_weights("2023-06-01", root=snapshot)


def test_decision_weights_refuses_missing_snapshot(tmp_path):
    with pytest.raises(targets.TargetsError, match="no forward_crypto snapshot"):
        targets.decision_weights(DECISION_DAY, root=tmp_path)


def test_decision_weights_matches_frozen_quintile_construction(snapshot):
    out = targets.decision_weights(DECISION_DAY, root=snapshot)
    n = 30
    k = int((n * c.Q))  # frozen: floor(0.2 * n), n=30 -> 6
    assert out["n_long"] == k and out["n_short"] == k
    longs = sorted(out["weights"], key=lambda s: out["weights"][s], reverse=True)  # positive weights: longs
    long_syms = {s for s, w in out["weights"].items() if w > 0}
    short_syms = {s for s, w in out["weights"].items() if w < 0}
    # signal increasing in index -> bottom quintile (most negative) = lowest-index symbols = longs
    expected_long = {f"SYM{i:02d}USDT" for i in range(0, k)}
    expected_short = {f"SYM{i:02d}USDT" for i in range(n - k, n)}
    assert long_syms == expected_long
    assert short_syms == expected_short
    # dollar-neutral, gross 1, equal-weighted within each leg
    assert out["gross"] == pytest.approx(1.0)
    assert out["net"] == pytest.approx(0.0)
    each = 0.5 / k
    assert all(abs(abs(w) - each) < 1e-9 for w in out["weights"].values())
    assert out["missing_open_price"] == []
    # the fixture's klines stop the day before the decision day (the forming candle is never provided),
    # so the day-t open must come from the premiumIndex fallback, not a (nonexistent) klines_1d_open
    assert all(v["source"] == "premiumIndex_markPrice_fallback" for v in out["open_prices"].values())


def test_decision_weights_never_uses_the_forming_candle_for_the_decision_day(snapshot):
    """If a (malformed/early) klines snapshot includes a bar whose open_time IS the decision day, it
    must be dropped, not used as a completed trailing-volume observation."""
    day_dir = snapshot / DECISION_DAY
    sym = "SYM00USDT"
    kl = targets.load_symbol_klines(day_dir, sym)
    kl_with_today = kl + [[targets.pd.Timestamp(DECISION_DAY).value // 10**6, "999", "999", "999", "999",
                           "1", 0, "999999999", 1, "0", "0", "0"]]
    _write_envelope(day_dir, f"klines.{sym}", kl_with_today, fetched_at="000200")
    out = targets.decision_weights(DECISION_DAY, root=snapshot)
    # the absurd same-day volume (999999999) must not have entered the trailing-volume ranking
    assert out["n_candidate_symbols"] == 30
    assert sym in out["weights"]  # still eligible/ranked from its real trailing history


def test_frozen_files_are_unmodified_by_this_module():
    """Sanity check that targets.py truly imports, not reimplements, the frozen rule."""
    prov = targets.frozen_provenance()
    for path in targets.FROZEN_FILES:
        assert path in prov
    import hashlib

    assert prov["research/crypto_funding_xs/core.py"] == hashlib.sha256(
        (targets.ROOT / "research/crypto_funding_xs/core.py").read_bytes()).hexdigest()


def test_candidate_symbols_excludes_frozen_exclusion_bases():
    ei = {"symbols": [
        {"symbol": "BTCUSDT", "contractType": "PERPETUAL", "quoteAsset": "USDT", "status": "TRADING",
         "onboardDate": _ms("2020-01-01")},
        {"symbol": "BTCDOMUSDT", "contractType": "PERPETUAL", "quoteAsset": "USDT", "status": "TRADING",
         "onboardDate": _ms("2020-01-01")},
        {"symbol": "DEFIUSDT", "contractType": "PERPETUAL", "quoteAsset": "USDT", "status": "TRADING",
         "onboardDate": _ms("2020-01-01")},
    ]}
    syms = [s for s, _ in targets.candidate_symbols(ei)]
    assert syms == ["BTCUSDT"]
