"""MBS negative-convexity premium: MBB vs point-in-time rate hedge (research/mbs_convexity/PLAN.md). Frozen by the plan."""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.return_search.run import cash_rates
from research.struct_common import etf, monthly_hedge

COSTS = {"gross": (0.0, 0.0, 0.0), "base": (3e-4, 2e-4, 0.003), "stress": (9e-4, 6e-4, 0.010)}  # (MBB side, hedge side, borrow)


def book(window: tuple[str, str], cost_key: str) -> tuple[pd.Series, pd.DataFrame]:
    c_mbb, c_h, borrow = COSTS[cost_key]
    px = pd.concat([etf("MBB"), etf("IEF"), etf("SHY")], axis=1, keys=["MBB", "IEF", "SHY"]).dropna()
    sess = px.index
    H = monthly_hedge(px["MBB"], px[["IEF", "SHY"]], sess)
    r = px.pct_change().fillna(0.0)
    rf = cash_rates(sess, "2026-09-18").reindex(sess).fillna(0.0)
    h = H.shift(1)                                           # hedge set at close t earns from t+1
    live = h.notna().all(axis=1)
    days = pd.Series(np.r_[1, np.diff(sess.values).astype("timedelta64[D]").astype(int)], index=sess)
    ex = r["MBB"] - h["IEF"] * r["IEF"] - h["SHY"] * r["SHY"] - (1 - h["IEF"] - h["SHY"]) * rf
    dh = H.diff().abs().sum(axis=1).fillna(0.0)
    first_live = live.idxmax()
    tc = (dh * c_h).shift(1).fillna(0.0)
    tc.loc[first_live] += c_mbb + (H.loc[H.index < first_live].iloc[-1].sum() if (H.index < first_live).any() else 0.0) * c_h
    bor = (h["IEF"] + h["SHY"]) * borrow * days / 365.0
    out = (ex - tc - bor)[live]
    return out.loc[window[0]:window[1]], H
