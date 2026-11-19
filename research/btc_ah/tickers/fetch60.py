# 60m pull with explicit window ending at the holdout cutoff (no post-2026-08-10 bars requested)
import yfinance as yf, pandas as pd, os
D = "/Users/rytty/CCP/quant_v7/research/btc_ah/tickers"
CUT = pd.Timestamp("2026-08-10")
for t in ["IBIT","MSTU","MSTX"]:
    try:
        df = yf.download(t, start="2024-10-20", end="2026-08-11", interval="1h", auto_adjust=False, progress=False, actions=False)
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.lower)
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None: df.index = df.index.tz_convert("America/New_York").tz_localize(None)
        df = df[df.index < CUT + pd.Timedelta(days=1)]
        print(t, "60m rows", len(df), flush=True)
        if len(df): df.to_parquet(f"{D}/{t}_60m.parquet")
    except Exception as e:
        print("FAIL", t, repr(e)[:160], flush=True)
