"""Treasury month-end index-extension flow (research/tsy_month_end/PLAN.md). Frozen by the plan.

* **Book M.** Hold TLT (adjusted close) over the last 3 sessions of each calendar month. The weight is
  set at the close of the 4th-to-last session and the position closed at the close of the last
  session. Otherwise hold T-bills. The calendar is known in advance, so no signal lag is needed.
* **Placebo P_k.** The same 3-session hold, but ending at the k-th session of the month
  (k = 3 … 15), identical mechanics.
* **Control C_EXP.** A constant TLT weight equal to M's average weight.
* **Costs.** Base 2 bp, stress 6 bp per side on |Δweight|.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HOLD = 3
COSTS = {"gross": 0.0, "base": 2e-4, "stress": 6e-4}


def load(ticker: str = "TLT") -> pd.Series:
    d = pd.read_parquet(ROOT / "data" / "multiasset" / "etf" / f"{ticker}.parquet")
    return d.set_index(pd.to_datetime(d["date"]))["close"].sort_index()


def weights(sess: pd.DatetimeIndex, end_pos: str | int) -> pd.Series:
    """Weight held at each close. end_pos='last' = last session of month; int k = k-th session (1-based)."""
    s = pd.Series(np.arange(len(sess)), index=sess)
    grp = sess.to_period("M")
    rank = s.groupby(grp).rank(method="first").astype(int)          # 1-based session number in month
    n = s.groupby(grp).transform("size")
    end = n if end_pos == "last" else pd.Series(end_pos, index=sess)
    held = (rank >= end - HOLD) & (rank < end)                       # held at closes of end-3 .. end-1
    return held.astype(float)


def returns(w: pd.Series, px: pd.Series, rf: pd.Series, cost: float) -> pd.Series:
    r = px.pct_change().fillna(0.0)
    held = w.shift(1).fillna(0.0)
    tc = w.diff().abs().fillna(w.iloc[0]) * cost
    return held * (r - rf) - tc


def sharpe(x: pd.Series) -> float:
    s = x.std(ddof=1)
    return float(x.mean() / s * np.sqrt(252)) if s > 0 else float("nan")
