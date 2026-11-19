"""Fetch daily (full history) and 60m (~730d) OHLC for ETH-linked names via yfinance.

yfinance `end` is exclusive, so end='2026-08-11' yields data through 2026-08-10 only.
Every frame is filtered to <= 2026-08-10 immediately after loading.
Output: ./data/<TICKER>_1d.parquet, ./data/<TICKER>_60m.parquet (ET tz-naive timestamps).
"""
import os

import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

TICKERS = ["BMNR", "SBET", "BTCS", "ETHZ", "GAME", "BTBT", "ETHA", "ETHE", "FETH", "ETHU", "COIN"]
CUTOFF = pd.Timestamp("2026-08-10 23:59:59")
END = "2026-08-11"  # exclusive


def clean(df):
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [str(c).lower() for c in df.columns]
    idx = df.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    df.index = pd.DatetimeIndex(idx, name="ts_et")
    df = df[["open", "high", "low", "close", "volume"]].dropna(subset=["open", "close"])
    df = df[df.index <= CUTOFF]  # SEALED: nothing after 2026-08-10
    return df.sort_index()


def main():
    for t in TICKERS:
        # 60m: yfinance caps intraday at 730 days counted back from today (2026-10-17), so use an explicit start.
        for kind, kw in [("1d", dict(period="max", interval="1d")),
                         ("60m", dict(start="2024-10-20", interval="60m"))]:
            try:
                raw = yf.download(t, end=END, auto_adjust=True, progress=False,
                                  multi_level_index=False, **kw)
            except Exception as e:  # noqa: BLE001
                print(t, kind, "ERROR", type(e).__name__, flush=True)
                continue
            if raw is None or raw.empty:
                print(t, kind, "no data", flush=True)
                continue
            df = clean(raw)
            if df.empty:
                print(t, kind, "empty after filter", flush=True)
                continue
            df.to_parquet(os.path.join(DATA, f"{t}_{kind}.parquet"))
            print(t, kind, len(df), df.index.min(), df.index.max(), flush=True)


if __name__ == "__main__":
    main()
