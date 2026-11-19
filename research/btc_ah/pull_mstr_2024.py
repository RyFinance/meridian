"""MSTR 1m (LSE vault, UTC) for weekdays 2024-01-02..2026-04-28: check window for opening mean-reversion leads."""
import time, pandas as pd
from pathlib import Path
from research.lse_mcp_client import Terminal
from research.mstr_btc_0dte.pull_stock_1m_dev import pull_day
OUT = Path(__file__).parent / "mstr_1m_2024"
days = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2024-01-02", "2026-04-28")]
n = 0
with Terminal() as t:
    for i, d in enumerate(days):
        if (OUT / f"{d}.parquet").exists(): continue
        df = pull_day(t, d)
        if df is not None and len(df): df.to_parquet(OUT / f"{d}.parquet", index=False); n += 1
        if i % 50 == 0: print(i, d, n, flush=True)
        time.sleep(0.5)
print("days saved", n)
