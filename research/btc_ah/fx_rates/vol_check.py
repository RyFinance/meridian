"""Share of zero-volume pre-market 08:00 bars (stale-print risk) per ETF."""
import pandas as pd
from pathlib import Path
C = Path(__file__).parent / "cache"
for t in ["FXE", "FXY", "UUP", "FXB", "TLT", "IEF", "TMF", "TBT", "KRE", "XLU", "XHB", "ITB"]:
    d = pd.read_parquet(C / f"{t}_1h.parquet")
    d = d[d.index.date <= pd.Timestamp("2026-08-10").date()]
    k = d.index.strftime("%H:%M")
    pm = d[k == "08:00"]
    rth = d[k == "09:30"]
    print(t, "pm08 bars", len(pm), "zero-vol share", round((pm.volume == 0).mean(), 2), " rth09:30 zero-vol share", round((rth.volume == 0).mean(), 3))
