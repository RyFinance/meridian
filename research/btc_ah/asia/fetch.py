import yfinance as yf, pandas as pd, os
D = "/Users/rytty/CCP/quant_v7/research/btc_ah/asia/cache"
os.makedirs(D, exist_ok=True)
TICK = ["3350.T","3825.T","8698.T","8473.T","9449.T","3356.T","0434.HK","1723.HK"]
CUT = pd.Timestamp("2026-08-10 23:59:59")
def flat(d):
    if isinstance(d.columns, pd.MultiIndex):
        d = d.droplevel(1, axis=1)
    return d
for t in TICK:
    safe = t.replace(".", "_")
    try:
        d = flat(yf.download(t, start="2015-01-01", end="2026-08-11", interval="1d", auto_adjust=False, progress=False, threads=False))
        d = d[d.index <= CUT]
        d.to_parquet(f"{D}/{safe}_1d.parquet")
        print(t, "1d rows", len(d), str(d.index.min().date()), str(d.index.max().date()))
    except Exception as e:
        print(t, "1d ERR", str(e)[:100])
    try:
        h = flat(yf.download(t, period="730d", interval="60m", auto_adjust=False, progress=False, threads=False))
        if len(h):
            idx = h.index
            h.index = idx.tz_convert("UTC").tz_localize(None) if idx.tz is not None else idx
            h = h[h.index <= CUT]
        h.to_parquet(f"{D}/{safe}_60m.parquet")
        print(t, "60m rows", len(h), str(h.index.min()) if len(h) else "-", str(h.index.max()) if len(h) else "-")
    except Exception as e:
        print(t, "60m ERR", str(e)[:100])
