"""Pull Coinbase BTC-USD 1m candles to extend the daily panel's btc_off through the
end of the validation window (2026-09-17).

The panel (daily_panel.parquet) uses the LSE vault BTC/USD 1m series, which ends
2026-08-11 08:03 UTC. This script fetches from the SAME endpoint the registered
forward test uses (api.exchange.coinbase.com/products/BTC-USD/candles, granularity=60):

  1. the missing tail: 2026-08-10T00:00Z .. 2026-09-18T14:00Z (full 1m series)
  2. 2-minute windows ending 09:30 ET and 16:00 ET for every validation weekday
     (2024-01-01..2026-08-10) so the Coinbase-vs-LSE btc_off agreement is measured
     on the exact endpoints the day-filter uses.

Outputs: research/mstr_btc_0dte/btc_1m_coinbase.parquet (ts open high low close volume, UTC).
Dev window data is NOT touched; this only serves the 2024+ day filter.
"""
from __future__ import annotations

import datetime as dt
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

H = Path(__file__).parent
OUT = H / "btc_1m_coinbase.parquet"
ET = dt.timezone(dt.timedelta(hours=-5))  # fixed EST offset used by candles? -> use ET below
from zoneinfo import ZoneInfo  # noqa: E402

ETZ = ZoneInfo("America/New_York")
API = "https://api.exchange.coinbase.com/products/BTC-USD/candles?"
TAIL_START = dt.datetime(2026, 8, 10, 0, 0, tzinfo=dt.timezone.utc)
TAIL_END = dt.datetime(2026, 9, 18, 14, 0, tzinfo=dt.timezone.utc)


def get(url: str) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": "research-backfill/1.0",
                                               "Accept": "application/json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception:  # noqa: BLE001
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed: {url[:120]}")


def fetch_range(start: dt.datetime, end: dt.datetime, rows: list) -> None:
    cur = start
    while cur < end:
        nxt = min(cur + dt.timedelta(minutes=300), end)
        q = urllib.parse.urlencode({"granularity": 60, "start": cur.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    "end": nxt.strftime("%Y-%m-%dT%H:%M:%SZ")})
        for r in get(API + q):
            rows.append(dict(ts=r[0], open=r[3], high=r[2], low=r[1], close=r[4], volume=r[5]))
        cur = nxt
        time.sleep(0.25)


def main() -> None:
    rows: list = []
    fetch_range(TAIL_START, TAIL_END, rows)
    n_tail = len(rows)
    print(f"tail: {n_tail} bars {TAIL_START:%Y-%m-%d} .. {TAIL_END:%Y-%m-%d}", flush=True)

    # endpoints for every validation weekday (NYSE sessions are approximated by weekday<5; the
    # panel itself only keeps days present in mstr_daily_yf, and its btc_off is what we compare)
    dp = pd.read_parquet(H / "daily_panel.parquet")
    val_days = [d.date() for d in dp.index if d >= pd.Timestamp("2024-01-01")]
    for d in val_days:
        for hh, mm in ((9, 30), (16, 0)):
            t = dt.datetime.combine(d, dt.time(hh, mm), tzinfo=ETZ)
            fetch_range(t - dt.timedelta(minutes=2), t, rows)
    df = (pd.DataFrame(rows).drop_duplicates("ts").sort_values("ts"))
    df["ts"] = pd.to_datetime(df.ts, unit="s", utc=True)
    df.to_parquet(OUT, index=False)
    print(f"saved {len(df)} rows ({len(df) - n_tail} endpoint probes) -> {OUT.name}", flush=True)


if __name__ == "__main__":
    main()
