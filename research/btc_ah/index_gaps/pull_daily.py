import yfinance as yf, pandas as pd, os
C = "/Users/rytty/CCP/quant_v7/research/btc_ah/index_gaps/cache"
SYMS = ["SPY","QQQ","IWM","TQQQ","SQQQ","SOXL","UVXY","^VIX"]
for s in SYMS:
    df = yf.download(s, start="1993-01-01", end="2026-08-11", interval="1d", auto_adjust=False, progress=False, multi_level_index=False)
    df = df.loc[df.index <= "2026-08-10"]
    df.to_parquet(f"{C}/{s.replace('^','')}_1d.parquet")
    print(s, len(df), df.index.min(), df.index.max())
