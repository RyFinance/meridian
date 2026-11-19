# Pull daily (max) and 60m (730d) bars via yfinance; filter to <= 2026-08-10 immediately after load (sealed holdout).
import os, sys
import pandas as pd, yfinance as yf
OUT = "/Users/rytty/CCP/quant_v7/research/btc_ah/intl/data"
CUT = pd.Timestamp("2026-08-10")
ETF = ["EWJ","DXJ","FXI","KWEB","MCHI","EWY","EWT","INDA","EWZ","EWW","EWG","EWU","EZU","VGK"]
ADR = ["TSM","BABA","PDD","JD","BIDU","SONY","TM","ASML","SAP","NVO","HSBC","INFY"]
HOME = ["2330.TW","9988.HK","^N225","^HSI","^KS11","^TWII","^STOXX50E","^GDAXI","^FTSE"]
FUT = ["ES=F"]
ALL = ETF + ADR + HOME + FUT

def flat(df, t):
    if isinstance(df.columns, pd.MultiIndex):
        df = df.xs(t, axis=1, level=1) if t in df.columns.get_level_values(1) else df.droplevel(1, axis=1)
    return df

def fetch(t, interval, period):
    d = yf.download(t, period=period, interval=interval, progress=False, auto_adjust=False)
    d = flat(d, t)
    if d.empty: return d
    if interval == "1d":
        idx = pd.to_datetime(d.index).tz_localize(None) if getattr(d.index, "tz", None) else pd.to_datetime(d.index)
        d.index = idx.normalize()
        d = d[d.index <= CUT]
    else:
        idx = d.index.tz_convert("America/New_York") if d.index.tz is not None else d.index
        d.index = idx
        d = d[d.index.tz_localize(None) <= CUT + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)]
    return d[["Open","High","Low","Close","Volume"]].dropna(subset=["Open","Close"])

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    which = sys.argv[1]
    for t in ALL:
        fn = f"{OUT}/{which}_{t.replace('^','').replace('=','_').replace('.','_')}.parquet"
        try:
            if which == "daily": d = fetch(t, "1d", "max")
            else: d = fetch(t, "60m", "730d")
            d.to_parquet(fn)
            print(which, t, len(d), d.index.min(), d.index.max(), flush=True)
        except Exception as e:
            print("FAIL", which, t, e, flush=True)
