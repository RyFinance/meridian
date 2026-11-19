"""Download daily (2018-06..2026-08) and 60m (last ~730d) bars from yfinance, auto_adjust=False."""
import yfinance as yf, pandas as pd
from pathlib import Path
H = Path(__file__).parent
T = ["MSTR","MARA","RIOT","CLSK","HUT","HUT.TO","BITF","CIFR","WULF","IREN","BTBT","COIN","HOOD","SMLR","XYZ","SQ",
     "IBIT","FBTC","BITO","GBTC","HIVE","BTDR","CORZ","ARGO","SDIG","BTCM","GREE","CAN","SOS","MIGI","GLXY","SLNH"]
d, h = {}, {}
for t in T:
    try:
        x = yf.download(t, start="2018-06-01", end="2026-08-12", auto_adjust=False, progress=False, multi_level_index=False)
        if len(x): d[t] = x
        y = yf.download(t, period="730d", interval="60m", auto_adjust=False, progress=False, multi_level_index=False, prepost=False)
        if len(y): h[t] = y
    except Exception as e: print(t, "ERR", e)
    print(t, len(d.get(t, [])), d[t].index.min().date() if t in d else None, d[t].index.max().date() if t in d else None, "60m:", len(h.get(t, [])))
pd.concat(d, names=["tk","date"]).to_parquet(H/"daily.parquet")
pd.concat(h, names=["tk","ts"]).to_parquet(H/"hourly.parquet")
