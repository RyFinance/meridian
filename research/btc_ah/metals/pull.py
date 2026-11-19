"""Pull hourly bars (yfinance, 730d cap) for metals futures and equity/ETF targets.
Filters every frame to < 2026-08-11 00:00 ET (sealed holdout: nothing after 2026-08-10).
Output: research/btc_ah/metals/cache/<SYM>.parquet with ET-naive timestamps.
"""
from pathlib import Path
import time
import pandas as pd
import yfinance as yf

H = Path(__file__).parent
CACHE = H / "cache"
FUTS = ["GC=F", "SI=F", "HG=F"]
EQS = ["GLD", "SLV", "GDX", "GDXJ", "NUGT", "NEM", "GOLD", "AEM", "KGC",
       "PAAS", "AG", "HL", "FCX", "SCCO", "COPX"]
CUT = pd.Timestamp("2026-08-11 00:00", tz="America/New_York")


def pull(sym: str, prepost: bool) -> pd.DataFrame:
    d = yf.download(sym, period="730d", interval="1h", auto_adjust=False,
                    progress=False, threads=False, prepost=prepost)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.rename(columns=str.lower)
    idx = pd.DatetimeIndex(d.index)
    idx = idx.tz_convert("America/New_York") if idx.tz is not None else idx.tz_localize("America/New_York")
    d.index = idx
    d = d[d.index < CUT]           # SEALED HOLDOUT FILTER, applied right after load
    return d[["open", "high", "low", "close", "volume"]].sort_index()


def main() -> None:
    CACHE.mkdir(exist_ok=True)
    for s in FUTS:
        pull(s, prepost=True).to_parquet(CACHE / f"{s.replace('=', '_')}.parquet")
        time.sleep(0.5)
    for s in EQS:
        pull(s, prepost=True).to_parquet(CACHE / f"{s}.parquet")
        time.sleep(0.5)
    print("done")


if __name__ == "__main__":
    main()
