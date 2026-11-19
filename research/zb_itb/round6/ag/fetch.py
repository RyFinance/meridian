"""Fetch frozen yfinance 60m (730d) and 1d (max) for grain futures and the equity/ETF universe into ag/data."""
from pathlib import Path
import yfinance as yf
OUT = Path(__file__).parent / "data"
SYMS = ["ZC=F","ZS=F","ZW=F","ADM","BG","ANDE","CTVA","FMC","MOS","CF","NTR","DE","AGCO","CNH","LNDC",
        "MOO","CORN","SOYB","WEAT","GIS","K","CAG","TSN","PPC","HRL","SPY"]
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
