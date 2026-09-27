"""Binance USD-M futures: open interest and long/short positioning ratios.

Keyless, public REST only (fapi.binance.com). No account, no key, no order endpoint.

Why this module exists despite research/forward_crypto/collector.py already recording
Binance funding rate, klines, and premiumIndex: openInterestHist, topLongShortPositionRatio,
topLongShortAccountRatio, and globalLongShortAccountRatio are DIFFERENT endpoints that
research/forward_crypto never calls, and Binance's API only serves the last ~30 days of
history for them (unlike funding rate, which is queryable back to a symbol's listing).
Collecting these NOW is the only way to ever have pre-today history of them -- a gap that
cannot be backfilled later.

Forced-liquidation orders (`wss://fstream.binance.com/ws/!forceOrder@arr`) are explicitly
NOT collected here: Binance only streams these live over a websocket and exposes no
historical REST endpoint for them. A `run_once()` snapshot tool cannot capture a stream;
that would need a long-lived subscriber process, which is out of scope for this collector
(see the module docstring's "Scheduling" note in collect_all.py for the honest limitation).

Geo-blocking: if fapi.binance.com returns 451 from wherever this runs, that is recorded
verbatim in the manifest and NOT worked around (no VPN/proxy). It was reachable (HTTP 200)
from the sandbox this module was written in.

    PYTHONPATH=. .venv/bin/python -m research.collectors.binance_futures
"""
from __future__ import annotations

from research.collectors.common import FetchError, http_get, summarize, utc_now, write_snapshot

SOURCE = "binance_futures"
BASE = "https://fapi.binance.com"

# A fixed, liquid-majors universe. Deliberately small and explicit (not "every symbol"):
# openInterestHist/topLongShortPositionRatio are per-symbol calls, and the 30-day API
# window means broad coverage matters less than simply starting today for the names most
# likely to be used in any future crowding/positioning study.
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT",
    "DOTUSDT", "TRXUSDT", "BCHUSDT", "NEARUSDT", "SUIUSDT",
]

PERIOD = "1h"  # finest granularity Binance offers for these endpoints


def _snap(name: str, path: str, params: dict, when, records: list, errors: list) -> None:
    try:
        resp = http_get(f"{BASE}{path}", params=params)
    except FetchError as e:
        errors.append(f"{name}: {e}")
        return
    if resp.status_code != 200:
        errors.append(f"{name}: HTTP {resp.status_code}: {resp.text[:200]!r}")
        return
    rec = write_snapshot(SOURCE, name, resp.content, when=when, extra_meta={"url": resp.url})
    records.append(rec)


def run_once(symbols: list[str] | None = None, when=None) -> dict:
    when = when or utc_now()
    symbols = symbols or SYMBOLS
    records: list[dict] = []
    errors: list[str] = []
    blocked: list[str] = []

    for sym in symbols:
        # Current open interest (point-in-time; no window param).
        _snap(f"openInterest.{sym}", "/fapi/v1/openInterest", {"symbol": sym}, when, records, errors)
        # Historical open interest -- only the trailing ~30 days are ever served.
        _snap(f"openInterestHist.{sym}", "/futures/data/openInterestHist",
              {"symbol": sym, "period": PERIOD, "limit": 500}, when, records, errors)
        # Top-trader positioning, by position size and by account count -- both ~30-day windows.
        _snap(f"topLongShortPositionRatio.{sym}", "/futures/data/topLongShortPositionRatio",
              {"symbol": sym, "period": PERIOD, "limit": 500}, when, records, errors)
        _snap(f"topLongShortAccountRatio.{sym}", "/futures/data/topLongShortAccountRatio",
              {"symbol": sym, "period": PERIOD, "limit": 500}, when, records, errors)
        # All-trader (global) long/short account ratio -- same ~30-day window.
        _snap(f"globalLongShortAccountRatio.{sym}", "/futures/data/globalLongShortAccountRatio",
              {"symbol": sym, "period": PERIOD, "limit": 500}, when, records, errors)

    for err in errors:
        if "451" in err:
            blocked.append(err)

    return summarize(SOURCE, records, errors=errors, blocked=blocked)


if __name__ == "__main__":
    import json
    print(json.dumps(run_once(), indent=2))
