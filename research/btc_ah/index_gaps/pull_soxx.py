import yfinance as yf, pandas as pd
C = "/Users/rytty/CCP/quant_v7/research/btc_ah/index_gaps/cache"
df = yf.download("SOXX", start="2010-01-01", end="2026-08-11", interval="1d", auto_adjust=False, progress=False, multi_level_index=False)
df = df.loc[df.index <= "2026-08-10"]; df.to_parquet(f"{C}/SOXX_1d.parquet"); print(len(df))
f = pd.read_parquet(f"{C}/ES_60m.parquet"); print(f.index[:3].tolist()); print(f.index.hour.value_counts().sort_index().to_dict())
