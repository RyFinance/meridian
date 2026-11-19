"""Re-fetch the 09:30/16:00 ET endpoint candles for every validation weekday, correctly
converted to UTC (the first attempt formatted local wall time as Z). Appends to
btc_1m_coinbase.parquet and dedups on candle-start ts.
"""
from __future__ import annotations

import datetime as dt
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

H = Path(__file__).parent
OUT = H / "btc_1m_coinbase.parquet"
ETZ = ZoneInfo("America/New_York")
API = "https://api.exchange.coinbase.com/products/BTC-USD/candles?"


def get(url: str) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": "research-backfill/1.1",
                                               "Accept": "application/json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception:  # noqa: BLE001
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed: {url[:120]}")


def fetch_range(start: dt.datetime, end: dt.datetime, rows: list) -> None:
    """start/end are tz-aware UTC datetimes."""
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
    df0 = pd.read_parquet(OUT).set_index(pd.to_datetime(pd.read_parquet(OUT).ts, utc=True))
    before = len(df0)
    rows: list = []
    panel = pd.read_parquet(H / "daily_panel.parquet")
    val_days = [d.date() for d in panel.index if d >= pd.Timestamp("2024-01-01")]
    for d in val_days:
        for hh, mm in ((9, 30), (16, 0)):
            t = dt.datetime.combine(d, dt.time(hh, mm), tzinfo=ETZ).astimezone(dt.timezone.utc)
            fetch_range(t - dt.timedelta(minutes=2), t, rows)
    new = pd.DataFrame(rows).drop_duplicates("ts")
    allx = pd.concat([df0.reset_index().drop(columns="index", errors="ignore"), new],
                     ignore_index=True).drop_duplicates("ts").sort_values("ts")
    allx.to_parquet(OUT, index=False)
    print(f"added {len(allx) - before} endpoint candles; total {len(allx)} rows", flush=True)


if __name__ == "__main__":
    main()
