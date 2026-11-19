"""Freeze yfinance inputs for the FX second-order test (own folder only)."""
from pathlib import Path
import yfinance as yf
OUT = Path(__file__).parent / "yf_cache"
FX = ["DX-Y.NYB", "6E=F", "6J=F", "JPY=X", "6A=F", "^TNX"]
TGT = ["TM", "HMC", "SONY", "MUFG", "SMFG", "EWJ", "DXJ", "GDX", "NEM", "AEM", "KO", "PG", "MCD",
       "AAPL", "MSFT", "CAT", "DE", "EEM", "EWZ", "EWW", "BHP", "RIO", "EWA", "SPY"]
def save(sym, interval, period):
    try:
        d = yf.download(sym, period=period, interval=interval, auto_adjust=False, progress=False)
    except Exception as e:
        print("FAIL", sym, interval, e); return
    if d is None or len(d) == 0:
        print("EMPTY", sym, interval); return
    d.columns = d.columns.get_level_values(0)
    f = OUT / f"{sym.replace('=', '_').replace('^', '').replace('.', '_')}_{interval}.parquet"
    d.to_parquet(f)
    print(f.name, len(d), d.index.min(), d.index.max(), flush=True)
for s in FX:
    save(s, "60m", "730d")
for s in TGT:
    save(s, "60m", "730d")
for s in TGT + ["6E=F", "6J=F", "6A=F", "DX-Y.NYB"]:
    save(s, "1d", "max")
