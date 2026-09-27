"""Month-end index extension in non-Treasury bond sectors, rate-hedged (research/sector_month_end/PLAN.md). Frozen by the plan."""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from research.return_search.run import cash_rates
from research.struct_common import etf, monthly_hedge
from research.tsy_month_end.core import weights

SECTORS = ["LQD", "MBB", "TIP"]
COSTS = {"gross": (0.0, 0.0), "base": (3e-4, 2e-4), "stress": (9e-4, 6e-4)}   # (ETF leg, hedge legs) per side


@lru_cache(maxsize=None)
def hedged(sector: str) -> tuple[pd.Series, pd.Series]:
    """Daily rate-hedged excess return of the sector ETF and the hedge size (h_IEF + h_SHY) held that day."""
    px = pd.concat([etf(sector), etf("IEF"), etf("SHY")], axis=1, keys=["X", "IEF", "SHY"]).dropna()
    sess = px.index
    H = monthly_hedge(px["X"], px[["IEF", "SHY"]], sess).shift(1)          # set at close t, earns from t+1
    r = px.pct_change()
    rf = cash_rates(sess, "2026-09-18").reindex(sess).fillna(0.0)
    hx = r["X"] - H["IEF"] * r["IEF"] - H["SHY"] * r["SHY"] - (1 - H["IEF"] - H["SHY"]) * rf
    return hx.dropna(), (H["IEF"] + H["SHY"]).reindex(hx.dropna().index)


def sector_book(sector: str, window, cost_key: str, w_fn=None) -> tuple[pd.Series, pd.Series]:
    """Returns (book returns, exposure-matched control) for one sector over the window."""
    ce, ch = COSTS[cost_key]
    hx, hs = hedged(sector)
    hx, hs = hx.loc[window[0]:window[1]], hs.loc[window[0]:window[1]]
    sess = hx.index
    w = (w_fn(sess) if w_fn else weights(sess, "last")).reindex(sess).fillna(0.0)
    held = w.shift(1).fillna(0.0)
    tc = w.diff().abs().fillna(w.iloc[0]) * (ce + ch * hs.fillna(1.0))
    r = held * hx - tc
    ctrl = float(w.mean()) * hx
    return r, ctrl


def book(window, cost_key: str, w_fn=None) -> tuple[pd.Series, pd.Series, dict]:
    parts, ctrls = {}, {}
    for s in SECTORS:
        r, c = sector_book(s, window, cost_key, w_fn)
        parts[s], ctrls[s] = r, c
    P, C = pd.DataFrame(parts), pd.DataFrame(ctrls)
    return P.mean(axis=1, skipna=True), C.mean(axis=1, skipna=True), {"P": P, "C": C}
