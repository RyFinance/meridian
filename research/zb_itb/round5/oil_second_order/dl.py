"""Download yfinance inputs for the oil second-order study into this folder's cache."""
import yfinance as yf, os
D = "research/zb_itb/round5/oil_second_order/cache/"
S = ["JETS","DAL","UAL","AAL","LUV","ALK","CCL","RCL","NCLH","ODFL","JBHT","FDX","UPS",
     "DOW","LYB","VLO","MPC","PSX","XLU","NEE","DUK","CF","NTR","SPY","USO","XLE"]
F = ["CL=F","NG=F"]
def sv(s, a_kw, name):
    try:
        d = yf.download(s, progress=False, auto_adjust=False, multi_level_index=False, **a_kw)
        if len(d) > 0:
            d.to_parquet(D + name)
        print(name, len(d), d.index.min() if len(d) else None, d.index.max() if len(d) else None, flush=True)
    except Exception as e:
        print(name, "ERR", e, flush=True)
for s in S + F:
    t = s.replace("=", "_")
    sv(s, dict(period="730d", interval="60m"), f"{t}_60m.parquet")
    sv(s, dict(period="max", interval="1d"), f"{t}_1d.parquet")
for s in F:
    t = s.replace("=", "_")
    sv(s, dict(period="60d", interval="5m"), f"{t}_5m.parquet")
