import yfinance as yf, pandas as pd
C = "/Users/rytty/CCP/quant_v7/research/btc_ah/miners_deep/cache"
CUT = pd.Timestamp("2026-08-10")
def clean(d):
    if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
    d = d.rename(columns=str.lower); d.index = pd.to_datetime(d.index)
    if d.index.tz is not None: d.index = d.index.tz_convert("America/New_York").tz_localize(None)
    return d
for t in ["BTDR", "APLD", "CORZ", "HIVE"]:
    h = clean(yf.download(t, start="2024-08-14", end="2026-08-11", interval="1h", auto_adjust=False, progress=False, actions=False))
    h = h[h.index < CUT + pd.Timedelta(days=1)]; h.index.name = "Datetime"
    h.to_parquet(f"{C}/{t}_60m.parquet"); print(t, "60m", len(h), h.index.min(), flush=True)
