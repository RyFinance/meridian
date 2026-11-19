import yfinance as yf, pandas as pd
C = "/Users/rytty/CCP/quant_v7/research/btc_ah/index_gaps/cache"
for s in ["SPY","QQQ","IWM","TQQQ","SQQQ","SOXL","UVXY","ES=F","NQ=F"]:
    df = yf.download(s, period="730d", interval="60m", auto_adjust=False, progress=False, multi_level_index=False, prepost=True)
    df.index = pd.DatetimeIndex(df.index)
    df = df.loc[df.index < pd.Timestamp("2026-08-11", tz=df.index.tz)] if df.index.tz is not None else df.loc[df.index < "2026-08-11"]
    df.to_parquet(f"{C}/{s.replace('=F','F')}_60m.parquet")
    print(s, len(df), df.index.min(), df.index.max(), df.index.tz)
