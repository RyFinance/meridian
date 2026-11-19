import pyarrow.parquet as pq, pandas as pd
TK="/Users/rytty/CCP/quant_v7/research/btc_ah/tickers/"; CA="/Users/rytty/CCP/quant_v7/research/btc_ah/miners_deep/cache/"
t = pq.read_table(TK+"MARA_60m.parquet", filters=[("Datetime","<",pd.Timestamp("2026-08-11"))]).to_pandas()
print(t.columns.tolist(), t.index.name, t.index[:3] if t.index.name else None, len(t))
d = t.set_index("Datetime").sort_index() if "Datetime" in t.columns else t
print(d.index.min(), d.index.max(), sorted(set(d.index.time))[:12])
x = pq.read_table(TK+"MARA_1d.parquet", filters=[("Date","<",pd.Timestamp("2026-08-11"))]).to_pandas()
print(x.columns.tolist(), x.index[:2], len(x), x.Date.max() if "Date" in x.columns else x.index.max())
b = pq.read_table("/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet", columns=["timestamp"], filters=[("timestamp","<",pd.Timestamp("2026-08-11",tz="UTC"))]).to_pandas()
print("btc rows", len(b), b.timestamp.min(), b.timestamp.max())
c = pq.read_table(CA+"APLD_60m.parquet").to_pandas(); print("APLD60", c.shape, c.columns.tolist())
