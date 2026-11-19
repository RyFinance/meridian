"""Pull regular-session intraday bars from the LSE vault for the ZB->homebuilder verification.
5m bars 2010-01-01..2026-09-16 for TLT + builders (+ placebo ETFs if present); 1m bars 2024-05-01..2026-09-16 for builders.
Resumable: one parquet per (symbol, timeframe, year). Run outside the sandbox (proxy truncates chunked responses)."""
import sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd
from data.lse_vault import Vault
OUT = Path(__file__).parent / "vault"; OUT.mkdir(exist_ok=True)
v = Vault()
SYMS = ["TLT", "DHI", "LEN", "PHM", "TOL", "KBH", "NVR", "SPY", "XLU", "KRE", "IEF", "HD", "LOW", "BLDR"]
jobs = [(s, "5m", y) for s in SYMS for y in range(2010, 2027)] + [(s, "1m", y) for s in ["TLT", "DHI", "LEN", "PHM", "TOL", "KBH", "NVR", "SPY"] for y in (2024, 2025, 2026)]
def run(job):
    s, tf, y = job
    f = OUT / f"{s.replace('/', '_')}_{tf}_{y}.parquet"
    if f.exists(): return f"{f.name} cached"
    start = f"{y}-01-01" if not (tf == "1m" and y == 2024) else "2024-05-01"
    end = f"{y}-12-31" if y < 2026 else "2026-09-17"
    for a in range(4):
        try:
            d = v.candles(s, tf, start=start, end=end); break
        except Exception as e:
            err = e; time.sleep(5 * (a + 1))
    else:
        return f"{f.name} FAILED {err!r}"
    d.to_parquet(f); return f"{f.name} {len(d)} rows"
with ThreadPoolExecutor(2) as ex:
    for i, msg in enumerate(ex.map(run, jobs)):
        print(i, msg, flush=True)
print("DONE")
