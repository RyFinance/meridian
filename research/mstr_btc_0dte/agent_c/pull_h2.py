"""Retry 60m for tickers whose period=730d request failed (start inside window)."""
import yfinance as yf, pandas as pd
from pathlib import Path
H = Path(__file__).parent
h = pd.read_parquet(H/"hourly.parquet")
add = {}
for t in ["IBIT","FBTC","CORZ"]:
    y = yf.download(t, start=(pd.Timestamp.today()-pd.Timedelta(days=725)).strftime("%Y-%m-%d"), interval="60m", auto_adjust=False, progress=False, multi_level_index=False)
    print(t, len(y)); add[t] = y
h = pd.concat([h, pd.concat(add, names=["tk","ts"])]); h.to_parquet(H/"hourly.parquet")
print(h.index.get_level_values(1).min(), h.index.get_level_values(1).max())
