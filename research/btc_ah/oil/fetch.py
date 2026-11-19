"""Pull oil/gas futures + equities/ETFs from yfinance; filter to <= 2026-08-10 immediately (sealed holdout)."""
import pandas as pd, yfinance as yf
from pathlib import Path
C = Path(__file__).parent / "cache"
CUTOFF = pd.Timestamp("2026-08-10 23:59:59")  # ET-naive; nothing later is kept
FUT = ["CL=F", "BZ=F", "NG=F"]
EQ = ["USO","BNO","UCO","SCO","XLE","XOP","OIH","XOM","CVX","OXY","COP","DVN","FANG","APA",
      "FRO","DHT","STNG","TNK","UNG","BOIL"]
def clean(d):
    d = d.copy()
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    idx = d.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    d.index = idx
    d = d[d.index <= CUTOFF]
    return d[["Open","High","Low","Close","Volume"]].dropna(subset=["Close"])
def name(s): return s.replace("=F", "_F")
if __name__ == "__main__":
    for s in FUT + EQ:
        h = yf.download(s, period="730d", interval="1h", progress=False, auto_adjust=True)
        h = clean(h); h.to_parquet(C / f"h1_{name(s)}.parquet")
        print("1h", s, len(h), h.index.min(), h.index.max(), flush=True)
    for s in FUT + EQ:
        d = yf.download(s, start="2000-01-01", end="2026-08-11", interval="1d", progress=False, auto_adjust=True)
        d = clean(d); d.to_parquet(C / f"d1_{name(s)}.parquet")
        print("1d", s, len(d), d.index.min(), d.index.max(), flush=True)
