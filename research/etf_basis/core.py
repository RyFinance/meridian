"""Bond-ETF liquidity provision: buy HYG / LQD at deep discounts to their own iBoxx index
(research/etf_basis/PLAN.md). Frozen by the plan.

* **Basis.** b_t = log(ETF adj close_t) − log(iBoxx TR index_t), on dates where both exist.
  d_t = b_t − mean(b over the previous 250 obs). z_t = d_t / sd(d over the previous 250 obs).
* **Signal B.** On day t, if z_t ≤ −2: hold the ETF long from the close of t+1 for 5 sessions (earning
  sessions t+2 … t+6). Overlapping triggers extend the hold; the position is at most 1 per ETF.
  The book is the equal-weight average of the HYG and LQD sleeves.
* **Control C_REV.** The same rule, triggered by the ETF's own 5-session return z ≤ −2 (own-price
  reversal), with the same standardisation window.
* **Costs.** Base 3 bp, stress 10 bp per side on |Δposition|. Idle cash earns T-bills (excess 0).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PAIRS = {"HYG": "USD_LIQ_HY", "LQD": "USD_LIQ_IG"}
WIN, Z, HOLD = 250, -2.0, 5
COSTS = {"gross": 0.0, "base": 3e-4, "stress": 10e-4}


def load(etf: str, idx: str, end: str) -> pd.DataFrame:
    e = pd.read_parquet(ROOT / "data" / "multiasset" / "etf" / f"{etf}.parquet")
    e = e.set_index(pd.to_datetime(e["date"]))["close"].sort_index()
    i = pd.read_parquet(ROOT / "data" / "credit_indices" / f"{idx}.parquet")
    i = i.set_index(pd.to_datetime(i["date"]))["value"].astype(float).sort_index()
    i = i[(i.index.dayofweek < 5) & ~i.index.duplicated(keep="last")]
    df = pd.concat([e, i], axis=1, keys=["etf", "idx"]).loc[:end]
    return df


def zscore(x: pd.Series) -> pd.Series:
    m = x.rolling(WIN, min_periods=WIN).mean().shift(1)
    s = (x - m).rolling(WIN, min_periods=WIN).std().shift(1)
    return (x - m) / s


def basis_z(df: pd.DataFrame) -> pd.Series:
    both = df.dropna()
    b = np.log(both["etf"]) - np.log(both["idx"])
    return zscore(b).reindex(df.index)


def own_z(df: pd.DataFrame) -> pd.Series:
    e = df["etf"].dropna()
    r5 = np.log(e).diff(HOLD)
    return zscore(r5).reindex(df.index)


def positions(trig: pd.Series, sessions: pd.DatetimeIndex) -> pd.Series:
    """Trigger on day t (trig <= Z) -> position 1 held at the closes of t+1 .. t+HOLD (earns t+2 .. t+HOLD+1)."""
    t = trig.reindex(sessions)
    fire = (t <= Z).to_numpy()
    pos = np.zeros(len(sessions))
    for i in np.flatnonzero(fire):
        pos[i + 1:i + 1 + HOLD] = 1.0
    return pd.Series(pos, index=sessions)


def sleeve_returns(pos: pd.Series, px: pd.Series, rf: pd.Series, cost: float) -> pd.Series:
    """Excess return; the return on day d uses the position held at the close of d−1."""
    r = px.pct_change().fillna(0.0)
    held = pos.shift(1).fillna(0.0)
    tc = pos.diff().abs().fillna(pos.iloc[0]).shift(1).fillna(0.0) * cost
    return held * (r - rf) - tc


def sharpe(x: pd.Series) -> float:
    s = x.std(ddof=1)
    return float(x.mean() / s * np.sqrt(252)) if s > 0 else float("nan")
