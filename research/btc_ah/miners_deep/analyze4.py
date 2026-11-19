import pandas as pd, numpy as np
T = pd.read_parquet("/Users/rytty/CCP/quant_v7/research/btc_ah/miners_deep/trades.parquet")
v = "down_buy|z>=0|btc_above|vol_lo"
g = T[(T.variant==v)&(T.exit=="V_close")].dropna(subset=["net_worst"])
g = g[(g.date>="2024-08-01")&(g.date<="2026-08-10")]
print("worst-fill V_close:", len(g), "mean net bp", round(g.net.mean()*1e4,1), "worst-fill mean bp", round(g.net_worst.mean()*1e4,1), "worst win", round((g.net_worst>0).mean(),3))
print("by ticker (net bp, n):"); print(g.groupby("t").net.agg(["count","mean"]).assign(mean=lambda x: x["mean"]*1e4).round(1).to_string())
med = g.net.median()*1e4; print("median trade bp", round(med,1), "| share of total from top 5% trades:", round(g.net.nlargest(int(len(g)*0.05)).sum()/g.net.sum(),2))
