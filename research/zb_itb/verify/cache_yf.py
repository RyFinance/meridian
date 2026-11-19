"""Freeze yfinance inputs (fetched 2026-10-17/18) so every verification step uses identical data."""
from pathlib import Path
import yfinance as yf
OUT = Path(__file__).parent / "yf_cache"
def save(sym, interval, period, prepost=False):
    d = yf.download(sym, period=period, interval=interval, auto_adjust=False, progress=False, prepost=prepost)
    d.columns = d.columns.get_level_values(0)
    f = OUT / f"{sym.replace('=', '_')}_{interval}{'_pp' if prepost else ''}.parquet"; d.to_parquet(f)
    print(f.name, len(d), d.index.min(), d.index.max())
for s in ["ZB=F", "ZN=F", "ITB", "XHB", "SPY", "TLT", "DHI", "LEN", "PHM", "TOL", "KBH", "NVR", "XLU", "KRE", "VNQ", "IWM"]:
    save(s, "60m", "730d")
for s in ["ZB=F", "ITB", "XHB", "TLT", "DHI"]:
    save(s, "5m", "60d")
save("TLT", "5m", "60d", prepost=True)
for s in ["ITB", "XHB", "TLT", "IEF", "SPY", "DHI", "LEN", "PHM", "TOL", "KBH", "NVR", "ZB=F"]:
    save(s, "1d", "max")
