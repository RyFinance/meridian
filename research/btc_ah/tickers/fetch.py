import yfinance as yf, pandas as pd, os, sys
D = "/Users/rytty/CCP/quant_v7/research/btc_ah/tickers"
TICK = ["MSTR","MARA","RIOT","CLSK","HUT","BITF","CIFR","WULF","IREN","COIN","HOOD","SMLR","BTBT","IBIT","BITO","BITX","MSTU","MSTX"]
CUT = pd.Timestamp("2026-08-10")
for t in TICK:
    for itv in ["1d","60m"]:
        out = f"{D}/{t}_{itv}.parquet"
        if os.path.exists(out): continue
        try:
            kw = dict(interval=itv, auto_adjust=False, progress=False, actions=False)
            if itv=="1d": kw["start"]="2010-01-01"; kw["end"]="2026-08-12"
            else: kw["period"]="720d"
            df = yf.download(t, **kw)
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df = df.rename(columns=str.lower)
            df.index = pd.to_datetime(df.index)
            if df.index.tz is not None: df.index = df.index.tz_convert("America/New_York").tz_localize(None)
            df = df[df.index <= CUT + pd.Timedelta(days=1)] if itv=="60m" else df[df.index <= CUT]
            df.to_parquet(out)
            print(t, itv, len(df), df.index.min() if len(df) else None, df.index.max() if len(df) else None, flush=True)
        except Exception as e:
            print("FAIL", t, itv, repr(e)[:200], flush=True)
