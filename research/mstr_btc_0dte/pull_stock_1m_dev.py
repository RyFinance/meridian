"""Pull MSTR stock 1-minute bars from LSE Terminal MCP for the DEV window only (< 2024-01-01).

Mirrors pull_1m.py discipline: dev-only, resumable, one parquet file per day.
Never requests 2024+ (that window stays locked until candidates are registered).
Bars are UTC; extended hours included (00:00-23:59 UTC); as-traded prices (pre 2024-08 split
in the dev era). Run: PYTHONPATH=. .venv/bin/python -m research.mstr_btc_0dte.pull_stock_1m_dev
"""
from __future__ import annotations

import io
import time
from pathlib import Path

import pandas as pd

from research.lse_mcp_client import Terminal, content_text

H = Path(__file__).parent
OUT = H / "stock_1m_dev"
ROOT_DATE = H.parents[1] / "BTC-Acum"
DEV_START, DEV_END_LOCK = "2020-08-11", "2024-01-01"   # dev window; 2024+ is LOCKED


def trading_days() -> list[str]:
    """Daily sessions inside the dev window from the BTC-off-hours panel (which lists
    consecutive yfinance sessions)."""
    p = pd.read_parquet(H / "daily_panel.parquet")
    days = [d.strftime("%Y-%m-%d") for d in p.index if d < pd.Timestamp(DEV_END_LOCK)]
    return days


def pull_day(t: Terminal, day: str) -> pd.DataFrame | None:
    """LSE Terminal quirk: single-day ranges return nothing; a [day, day+1) range
    returns only day's bars."""
    nxt = (pd.Timestamp(day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    last = None
    for attempt in range(5):
        try:
            r = t.call("get_history", {"symbol": "MSTR", "timeframe": "1m",
                                       "start": day, "end": nxt, "limit": 1000})
            txt = content_text(r)
            start = next((i for i, line in enumerate(txt.splitlines())
                          if line.startswith("time,")), None)
            if start is None:
                return None   # no data that day (holiday)
            df = pd.read_csv(io.StringIO("\n".join(txt.splitlines()[start:])))
            times = pd.to_datetime(df["time"], utc=True)
            day_utc = pd.Timestamp(day, tz="UTC")
            return df[(times >= day_utc) & (times < day_utc + pd.Timedelta(days=1))]
        except Exception as e:  # noqa: BLE001 - pull resilience
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"{day}: {last}")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    days = trading_days()
    todo = [d for d in days if not (OUT / f"{d}.parquet").exists()]
    print(f"days: {len(days)} total, {len(todo)} to pull", flush=True)
    with Terminal() as t:
        for i, day in enumerate(todo):
            df = pull_day(t, day)
            if df is not None:
                df.to_parquet(OUT / f"{day}.parquet", index=False)
            if (i + 1) % 20 == 0:
                print(f"{i + 1}/{len(todo)}", flush=True)
            time.sleep(1.0)   # be gentle with the terminal


if __name__ == "__main__":
    main()
