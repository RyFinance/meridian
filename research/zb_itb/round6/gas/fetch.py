"""Fetch yfinance 60m (730d) and 1d (max) for NG=F, CL=F, gas/oil targets and placebo into gas/data."""
from pathlib import Path
import yfinance as yf
OUT = Path(__file__).parent / "data"
SYMS = ["NG=F","CL=F","EQT","RRC","AR","CTRA","CNX","EXE","CHK","SWN","LNG","TELL","NFE","KOLD","BOIL","FCG",
        "XOP","OIH","RIG","VAL","NOG","MTDR","SM","CIVI","FRO","STNG","XLE","USO","SPY"]
for s in SYMS:
    for interval, period in [("60m","730d"),("1d","max")]:
        try:
            d = yf.download(s, period=period, interval=interval, auto_adjust=False, progress=False)
            if d is None or len(d)==0:
                print(s, interval, "EMPTY"); continue
            d.columns = d.columns.get_level_values(0)
            f = OUT / f"{s.replace('=','_')}_{interval}.parquet"; d.to_parquet(f)
            print(s, interval, len(d), d.index.min(), d.index.max())
        except Exception as e:
            print(s, interval, "ERR", repr(e)[:150])
