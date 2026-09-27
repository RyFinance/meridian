"""Commodity roll premium via same-commodity ETF pairs (research/commodity_roll/PLAN.md). Frozen by the plan."""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.struct_common import etf

PAIRS = {"crude": ("USL", "USO"), "natgas": ("UNL", "UNG"), "broad": ("DBC", "GSG")}  # (long deferred, short front)
COSTS = {"gross": (0.0, 0.0), "base": (10e-4, 0.010), "stress": (30e-4, 0.040)}      # (per-side trade cost, annual borrow)


def pair_returns(long_px: pd.Series, short_px: pd.Series, cost: float, borrow: float) -> pd.Series:
    """Dollar-neutral pair on capital 1: +1 long / -1 short reset at each month's first session close; drift between."""
    j = pd.concat([long_px, short_px], axis=1, keys=["l", "s"]).dropna()
    rl, rs = j["l"].pct_change().fillna(0.0).to_numpy(), j["s"].pct_change().fillna(0.0).to_numpy()
    d = j.index
    first = pd.Series(d, index=d).groupby(d.to_period("M")).transform("min").to_numpy() == d.to_numpy()
    days = np.r_[1, np.diff(d.values).astype("timedelta64[D]").astype(int)]
    L = S = 0.0
    out = np.zeros(len(d))
    for i in range(len(d)):
        pnl = L * rl[i] - S * rs[i] - S * borrow * days[i] / 365.0
        L *= 1 + rl[i]
        S *= 1 + rs[i]
        if first[i]:                                  # rebalance at this session's close (after earning the day)
            pnl -= cost * (abs(1.0 - L) + abs(1.0 - S))
            L = S = 1.0
        out[i] = pnl
    return pd.Series(out, index=d)


def book(window: tuple[str, str], cost_key: str) -> tuple[pd.Series, pd.DataFrame]:
    cost, borrow = COSTS[cost_key]
    parts = {k: pair_returns(etf(a), etf(b), cost, borrow) for k, (a, b) in PAIRS.items()}
    P = pd.DataFrame(parts).loc[window[0]:window[1]]
    # a pair is live from the day after its first rebalance (first month-start inside its data)
    for k in P:
        s = parts[k].loc[window[0]:window[1]]
        d = s.index
        first = d[pd.Series(d, index=d).groupby(d.to_period("M")).transform("min").to_numpy() == d.to_numpy()]
        start = first[0] if len(first) else d[-1]
        P.loc[:start, k] = np.nan
    return P.mean(axis=1, skipna=True).dropna(), P
