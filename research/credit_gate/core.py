"""Credit-conditions gate for equity exposure (research/credit_gate/PLAN.md). Frozen by the plan.

* **Credit excess (CE).** The log change over the last 63 index observations of
  USD_LIQ_HY / USD_CORP_1_3 (both iBoxx total-return levels, from the LSE vault), using only index
  values dated t−1 or earlier.
* **Book G.** Decided at each month-end close t: hold SPY if CE > 0, otherwise T-bills. The switch is
  executed at the close of the next session (t+1). No leverage.
* **Controls:**
  - C_EXP: a constant SPY weight equal to G's average weight in the same window;
  - C_TREND: SPY if SPY's own 63-session return to t−1 is > 0.
  Both use identical timing and costs.
* **Costs.** Base 2 bp, stress 6 bp per side on the traded weight.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
LOOK = 63
COSTS = {"gross": 0.0, "base": 2e-4, "stress": 6e-4}


def credit_series() -> pd.Series:
    def s(name):
        d = pd.read_parquet(ROOT / "data" / "credit_indices" / f"{name}.parquet")
        x = d.set_index(pd.to_datetime(d["date"]))["value"].astype(float).sort_index()
        return x[(x.index.dayofweek < 5) & ~x.index.duplicated(keep="last")]
    j = pd.concat([s("USD_LIQ_HY"), s("USD_CORP_1_3")], axis=1, keys=["hy", "ig13"]).dropna()
    return np.log(j["hy"] / j["ig13"])


def spy_and_cash(end: str) -> tuple[pd.Series, pd.Series]:
    from research.return_search.run import cash_rates
    d = pd.read_parquet(ROOT / "data" / "multiasset" / "etf" / "SPY.parquet")
    px = d.set_index(pd.to_datetime(d["date"]))["close"].sort_index().loc[:end]
    return px, cash_rates(px.index, end)


def signal_at(series: pd.Series, t: pd.Timestamp, look: int = LOOK) -> float:
    s = series.loc[: t - pd.Timedelta(days=1)]
    if len(s) <= look or (t - s.index[-1]).days > 7:
        return np.nan
    return float(s.iloc[-1] - s.iloc[-1 - look])


def month_end_sessions(idx: pd.DatetimeIndex, start: str, end: str) -> pd.DatetimeIndex:
    s = pd.Series(idx, index=idx)
    me = pd.DatetimeIndex(s.groupby(idx.to_period("M")).max().to_numpy())
    return me[(me >= pd.Timestamp(start)) & (me <= pd.Timestamp(end))]


def weights_from_signal(sig: pd.Series, px_idx: pd.DatetimeIndex) -> pd.Series:
    """Target weight decided at month-end t (1 if sig>0, 0 if <=0 or NaN) effective from the close of t+1."""
    w = pd.Series(np.nan, index=px_idx)
    pos = {d: i for i, d in enumerate(px_idx)}
    for t, v in sig.items():
        i = pos[t] + 1
        if i < len(px_idx):
            w.iloc[i] = 1.0 if (np.isfinite(v) and v > 0) else 0.0
    return w.ffill().fillna(0.0)


def daily_returns(w: pd.Series, px: pd.Series, rf: pd.Series, cost: float) -> pd.Series:
    """Return on day d uses the weight held at the close of d-1."""
    r = px.pct_change().fillna(0.0)
    held = w.shift(1).fillna(0.0)
    turn = w.diff().abs().fillna(w.iloc[0])
    tc = turn.shift(1).fillna(0.0) * cost
    return held * r + (1 - held) * rf - tc


def sharpe(x: pd.Series) -> float:
    return float(x.mean() / x.std(ddof=1) * np.sqrt(252)) if x.std(ddof=1) > 0 else float("nan")
