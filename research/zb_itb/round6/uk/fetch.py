"""Fetch frozen yfinance 60m (730d) and 1d (max) for ZB/ZN futures and UK targets into uk/data."""
from pathlib import Path
import yfinance as yf
OUT = Path(__file__).parent / "data"
SYMS = ["ZB=F", "ZN=F", "PSN.L", "TW.L", "BKG.L", "BTRW.L", "BDEV.L", "VTY.L", "CRST.L",
        "^FTMC", "VMID.L", "LLOY.L"]
for s in SYMS:
    for interval, period in [("60m", "730d"), ("1d", "max")]:
        try:
            d = yf.download(s, period=period, interval=interval, auto_adjust=False, progress=False)
            if d is None or len(d) == 0:
                print(s, interval, "EMPTY"); continue
            d.columns = d.columns.get_level_values(0)
            f = OUT / f"{s.replace('=', '_').replace('^', 'IDX_').replace('.', '_')}_{interval}.parquet"
            d.to_parquet(f)
            print(s, interval, len(d), d.index.min(), d.index.max())
        except Exception as e:
            print(s, interval, "ERR", repr(e)[:150])
