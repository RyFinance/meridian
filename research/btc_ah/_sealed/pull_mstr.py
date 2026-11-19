"""Sealed holdout: MSTR 1m incl. extended hours, weekdays 2026-08-11..2026-10-16, from LSE Terminal (not inspected)."""
import sys, time, pandas as pd
from pathlib import Path
from research.lse_mcp_client import Terminal
from research.mstr_btc_0dte.pull_stock_1m_dev import pull_day
OUT = Path(__file__).parent / "mstr_1m"; OUT.mkdir(exist_ok=True)
days = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2026-08-11", "2026-10-16")]
n = 0
with Terminal() as t:
    for d in days:
        if (OUT / f"{d}.parquet").exists(): continue
        df = pull_day(t, d)
        if df is not None and len(df): df.to_parquet(OUT / f"{d}.parquet", index=False); n += 1
        time.sleep(1.0)
print("days saved", n)
