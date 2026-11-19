"""Pull hourly bars (yfinance, 730d cap) for signal futures and ETF targets.
Sealed holdout: request end is exclusive at 2026-08-11, and rows are filtered to <= 2026-08-10 ET."""
import yfinance as yf, pandas as pd
from pathlib import Path
H = Path(__file__).parent
CACHE = H / "cache"; CACHE.mkdir(exist_ok=True)
SIG = ["6E=F", "6J=F", "6B=F", "ZN=F", "ZB=F"]
TGT = ["FXE", "FXY", "UUP", "FXB", "TLT", "IEF", "TMF", "TBT", "KRE", "XLU", "XHB", "ITB"]
CAP = pd.Timestamp("2026-08-11", tz="America/New_York")  # exclusive
import sys
for sym in (SIG + TGT):
    d = yf.download(sym, period="730d", interval="1h",
                    progress=False, auto_adjust=False, multi_level_index=False, prepost=True)
    d = d.dropna(how="all")
    ix = d.index if d.index.tz is not None else d.index.tz_localize("UTC")
    idx = ix.tz_convert("America/New_York")
    d = d[idx < CAP].copy()
    d.index = idx[idx < CAP]
    d.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in d.columns]
    d.to_parquet(CACHE / f"{sym.replace('=','_')}_1h.parquet")
    print(sym, len(d), d.index.min(), d.index.max(), flush=True)
