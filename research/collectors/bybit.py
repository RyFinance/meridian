"""Bybit: linear-perpetual tickers (incl. funding/OI/mark/index) and open interest.

Keyless, public REST only (api.bybit.com/v5). No account, no key, no order endpoint.

Bybit's v5 `market/tickers` endpoint already returns, in one call for the whole linear
category, each symbol's mark price, index price, funding rate, open interest, and 24h
volume -- so one snapshot captures a broad cross-section cheaply (roughly 650KB/day for
~600 linear symbols). `market/open-interest` is called per-symbol for the liquid subset
in binance_futures.SYMBOLS-equivalent list below, to get a finer intraday OI series than
the single tickers snapshot alone would give.

Not geo-blocked from the sandbox this was written in (bybit.com serves US IPs).

    PYTHONPATH=. .venv/bin/python -m research.collectors.bybit
"""
from __future__ import annotations

from research.collectors.common import FetchError, http_get, summarize, utc_now, write_snapshot

SOURCE = "bybit"
BASE = "https://api.bybit.com"

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT",
]


def run_once(symbols: list[str] | None = None, when=None) -> dict:
    when = when or utc_now()
    symbols = symbols or SYMBOLS
    records: list[dict] = []
    errors: list[str] = []

    try:
        resp = http_get(f"{BASE}/v5/market/tickers", params={"category": "linear"})
        if resp.status_code == 200:
            records.append(write_snapshot(SOURCE, "tickers.linear", resp.content, when=when,
                                           extra_meta={"url": resp.url}))
        else:
            errors.append(f"tickers.linear: HTTP {resp.status_code}: {resp.text[:200]!r}")
    except FetchError as e:
        errors.append(f"tickers.linear: {e}")

    for sym in symbols:
        try:
            resp = http_get(f"{BASE}/v5/market/open-interest",
                             params={"category": "linear", "symbol": sym, "intervalTime": "1h", "limit": 200})
            if resp.status_code == 200:
                records.append(write_snapshot(SOURCE, f"open-interest.{sym}", resp.content, when=when,
                                               extra_meta={"url": resp.url}))
            else:
                errors.append(f"open-interest.{sym}: HTTP {resp.status_code}: {resp.text[:200]!r}")
        except FetchError as e:
            errors.append(f"open-interest.{sym}: {e}")

    return summarize(SOURCE, records, errors=errors)


if __name__ == "__main__":
    import json
    print(json.dumps(run_once(), indent=2))
