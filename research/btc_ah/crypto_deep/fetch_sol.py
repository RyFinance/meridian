"""Fetch SOL-USD 15m candles from Coinbase public API via curl (Python urllib fails through the proxy).
Sealed: request end = 2026-08-11 04:00 UTC (= 00:00 ET 2026-08-11). Nothing dated after 2026-08-10 ET is kept.
Also spot-checks the ETH 5m file already on disk against a fresh curl pull for one day.
Output: data/sol_15m.parquet (ts_utc naive UTC, open, high, low, close, volume).
"""
import json, os, subprocess, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
GRAN = 900
CHUNK = timedelta(seconds=GRAN * 300)
START = datetime(2020, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 8, 11, 4, 0, tzinfo=timezone.utc)


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(args, product="SOL-USD", gran=GRAN):
    s, e = args
    url = (f"https://api.exchange.coinbase.com/products/{product}/candles?granularity={gran}"
           f"&start={iso(s)}&end={iso(e)}")
    for attempt in range(10):
        out = subprocess.run(["curl", "-s", "-m", "30", url], capture_output=True, text=True).stdout
        try:
            rows = json.loads(out)
            if isinstance(rows, list):
                return rows
        except Exception:
            pass
        time.sleep(1.0 + attempt)
    raise RuntimeError(f"failed chunk {s}")


def main():
    chunks, s = [], START
    while s < END:
        e = min(s + CHUNK, END)
        chunks.append((s, e))
        s = e
    print("chunks", len(chunks), flush=True)
    rows, t0 = [], time.time()
    with ThreadPoolExecutor(max_workers=3) as ex:
        for i, r in enumerate(ex.map(fetch, chunks)):
            rows.extend(r)
            if i % 100 == 0:
                print("done", i, round(time.time() - t0), "s", flush=True)
    df = pd.DataFrame(rows, columns=["t", "low", "high", "open", "close", "volume"])
    df = df.drop_duplicates("t").sort_values("t")
    df["ts_utc"] = pd.to_datetime(df["t"], unit="s")
    df = df[["ts_utc", "open", "high", "low", "close", "volume"]]
    df = df[df["ts_utc"] < pd.Timestamp("2026-08-11 04:00:00")]
    df.to_parquet(os.path.join(DATA, "sol_15m.parquet"), index=False)
    print("SOL saved", len(df), df.ts_utc.min(), df.ts_utc.max(), flush=True)

    # spot check ETH 5m on disk vs fresh pull for 2024-03-11..2024-03-12
    eth = pd.read_parquet("/Users/rytty/CCP/quant_v7/research/btc_ah/eth_names/data/eth_5m.parquet")
    a, b = pd.Timestamp("2024-03-11 00:00"), pd.Timestamp("2024-03-12 00:00")
    disk = eth[(eth.ts_utc >= a) & (eth.ts_utc < b)].set_index("ts_utc").sort_index()
    fresh = pd.DataFrame(fetch((a.tz_localize("UTC").to_pydatetime(), b.tz_localize("UTC").to_pydatetime()),
                               "ETH-USD", 300), columns=["t", "low", "high", "open", "close", "volume"])
    fresh["ts_utc"] = pd.to_datetime(fresh["t"], unit="s")
    fresh = fresh.set_index("ts_utc").sort_index()
    j = disk.join(fresh[["open", "close"]], rsuffix="_api", how="inner")
    print("ETH spot check bars", len(j), "max |open diff|", (j.open - j.open_api).abs().max(),
          "max |close diff|", (j.close - j.close_api).abs().max(), flush=True)


if __name__ == "__main__":
    main()
