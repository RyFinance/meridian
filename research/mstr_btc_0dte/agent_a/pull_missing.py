"""Fetch MSTR 1m days (2026-04-28..2026-09-16) missing from mstr_stock_1m_lse.parquet.
Writes one parquet per day to agent_a/stock_1m/. Read-only vault access."""
import time
from pathlib import Path
import pandas as pd
from data.lse_vault import Vault

H = Path(__file__).parent
OUT = H / "stock_1m"
base = pd.read_parquet(H.parent / "mstr_stock_1m_lse.parquet")
have = set((base.ts - pd.Timedelta(hours=4)).dt.strftime("%Y-%m-%d"))  # rough ET date
y = pd.read_parquet(H.parent / "mstr_daily_yf.parquet")
days = [d.strftime("%Y-%m-%d") for d in y.index if pd.Timestamp("2026-04-28") <= d <= pd.Timestamp("2026-09-16")]
v = Vault()
for d in days:
    f = OUT / f"{d}.parquet"
    if f.exists():
        continue
    nb = base[(base.ts >= pd.Timestamp(d) + pd.Timedelta(hours=8)) & (base.ts < pd.Timestamp(d) + pd.Timedelta(hours=24))]
    if len(nb) > 700:
        continue
    nxt = (pd.Timestamp(d) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    df = None
    for a in range(5):
        try:
            df = v.candles("MSTR", "1m", start=d, end=nxt); break
        except Exception as e:
            print("retry", d, type(e).__name__, flush=True); time.sleep(4 * (a + 1))
    if df is None or df.empty:
        print(d, "EMPTY", flush=True); continue
    df.to_parquet(f); print(d, len(df), "base had", len(nb), flush=True)
