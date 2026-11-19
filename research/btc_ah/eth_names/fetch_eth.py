"""Fetch ETH-USD 5m candles from Coinbase public API (via curl), 2017-01-01 .. 2026-08-10 16:00 ET.

Sealed holdout: request end is 2026-08-10T20:00Z (= 16:00 ET on 2026-08-10); nothing later is requested.
Output: ./data/eth_5m.parquet with columns ts_utc (naive UTC), open, high, low, close, volume.
"""
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

GRAN = 300  # 5 minutes
CHUNK = timedelta(seconds=GRAN * 300)  # 300 candles per request = 25h
START = datetime(2017, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 8, 10, 20, 0, tzinfo=timezone.utc)  # 16:00 ET on 2026-08-10 (sealed)


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_chunk(args):
    s, e = args
    url = (f"https://api.exchange.coinbase.com/products/ETH-USD/candles?granularity={GRAN}"
           f"&start={iso(s)}&end={iso(e)}")
    for attempt in range(8):
        out = subprocess.run(["curl", "-s", "-m", "30", url], capture_output=True, text=True).stdout
        try:
            rows = json.loads(out)
            if isinstance(rows, list):
                return rows
        except Exception:
            pass
        time.sleep(1.0 + attempt)  # rate limited / transient: back off
    raise RuntimeError(f"failed chunk {s}")


def main():
    chunks = []
    s = START
    while s < END:
        e = min(s + CHUNK, END)
        chunks.append((s, e))
        s = e
    print("chunks", len(chunks), flush=True)
    rows = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        for i, r in enumerate(ex.map(fetch_chunk, chunks)):
            rows.extend(r)
            if i % 300 == 0:
                print("done", i, round(time.time() - t0), "s", flush=True)
    df = pd.DataFrame(rows, columns=["t", "low", "high", "open", "close", "volume"])
    df = df.drop_duplicates("t").sort_values("t")
    df["ts_utc"] = pd.to_datetime(df["t"], unit="s")
    df = df[["ts_utc", "open", "high", "low", "close", "volume"]]
    # hard filter: nothing at or after the sealed cutoff
    df = df[df["ts_utc"] < pd.Timestamp("2026-08-10 20:00:00")]
    df.to_parquet(os.path.join(DATA, "eth_5m.parquet"), index=False)
    print("saved", len(df), df["ts_utc"].min(), df["ts_utc"].max(), flush=True)


if __name__ == "__main__":
    main()
