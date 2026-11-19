# Fetch daily (2019-01-01..) and 60m (~730d) bars for miners not in tickers/. Cache in miners_deep/cache. Holdout: end before 2026-08-11.
import yfinance as yf, pandas as pd, os
C = "/Users/rytty/CCP/quant_v7/research/btc_ah/miners_deep/cache"
CUT = pd.Timestamp("2026-08-10")
def clean(d):
    if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
    d = d.rename(columns=str.lower); d.index = pd.to_datetime(d.index)
    if d.index.tz is not None: d.index = d.index.tz_convert("America/New_York").tz_localize(None)
    return d
for t in ["BTDR", "APLD", "CORZ", "GLXY", "HIVE"]:
    d = clean(yf.download(t, start="2019-01-01", end="2026-08-11", interval="1d", auto_adjust=False, progress=False, actions=False))
    d = d[d.index <= CUT]; d.index.name = "Date"
    d.to_parquet(f"{C}/{t}_1d.parquet"); print(t, "1d", len(d), d.index.min().date(), d.index.max().date(), flush=True)
    h = clean(yf.download(t, start="2024-08-01", end="2026-08-11", interval="1h", auto_adjust=False, progress=False, actions=False))
    h = h[h.index < CUT + pd.Timedelta(days=1)]; h.index.name = "Datetime"
    h.to_parquet(f"{C}/{t}_60m.parquet"); print(t, "60m", len(h), flush=True)
