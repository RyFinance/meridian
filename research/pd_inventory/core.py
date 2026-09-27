"""Primary-dealer long-dated Treasury inventory -> 10-year duration timing (research/pd_inventory/PLAN.md). Frozen by the plan."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PD = ROOT / "data" / "new_info_scout" / "nyfed_pd"
FRED = ROOT / "data" / "c4" / "fred"
SEGMENTS = [("1998-01-28", "2001-06-30", ["PDPUSGCS5MNOP"]),
            ("2001-07-01", "2013-03-31", ["PDPUSGCS611NOP", "PDPUSGCSM11NOP"]),
            ("2013-04-01", "2014-12-31", ["PDPOSGSC-G6L7", "PDPOSGSC-G7L11", "PDPOSGSC-G11"]),
            ("2015-01-01", "2022-01-04", ["PDPOSGSC-G6L7", "PDPOSGSC-G7L11", "PDPOSGSC-G11"]),
            ("2022-01-05", "2024-07-02", ["PDPOSGSC-G6L7", "PDPOSGSC-G7L11", "PDPOSGSC-G11L21", "PDPOSGSC-G21"]),
            ("2024-07-03", "2099-12-31", ["PDPOSGSC-G6L7", "PDPOSGSC-G7L11", "PDPOSGSC-G11L21", "PDPOSGSC-G21"])]
LOOK, MIN_PRIOR, CLIP, PUB_LAG_DAYS, DUR = 52, 13, 2.0, 9, 7.0
COSTS = {"gross": 0.0, "base": 1e-4, "stress": 3e-4}          # price units per unit |dw| per side


def inventory() -> pd.DataFrame:
    """Weekly net outright >6y coupon position ($mn) with its segment id (z-scores never cross segments)."""
    d = pd.read_csv(PD / "pd_all_timeseries.csv")
    d.columns = ["date", "series", "v"]
    d["date"] = pd.to_datetime(d["date"])
    d["v"] = pd.to_numeric(d["v"], errors="coerce")
    out = []
    for k, (a, b, ids) in enumerate(SEGMENTS):
        x = d[d.series.isin(ids) & (d.date >= a) & (d.date <= b)].pivot_table(index="date", columns="series", values="v")
        x = x.dropna(subset=ids) if set(ids) <= set(x.columns) else x.iloc[0:0]
        out.append(pd.DataFrame({"x": x[ids].sum(axis=1), "seg": k}))
    return pd.concat(out).sort_index()


def signal(inv: pd.DataFrame) -> pd.DataFrame:
    s = []
    for _, g in inv.groupby("seg"):
        prev = g.x.shift(1)
        mu = prev.rolling(LOOK, min_periods=MIN_PRIOR).mean()
        sd = prev.rolling(LOOK, min_periods=MIN_PRIOR).std(ddof=1)
        z = ((g.x - mu) / sd).clip(-CLIP, CLIP)
        s.append(g.assign(z=z, w=z / CLIP))
    s = pd.concat(s).dropna(subset=["w"])
    s["avail"] = s.index + pd.Timedelta(days=PUB_LAG_DAYS)   # published Thursday t+8 ~16:15 ET; first usable H.15 close >= t+9
    return s


def dgs10() -> pd.Series:
    x = pd.read_csv(FRED / "DGS10.csv")
    x.columns = ["date", "v"]
    return pd.Series(pd.to_numeric(x.v, errors="coerce").to_numpy(), index=pd.to_datetime(x.date)).dropna()


def weights_daily(sig: pd.DataFrame, days: pd.DatetimeIndex) -> pd.Series:
    """Position held from each H.15 close onward: the latest signal whose availability date <= that date."""
    w = pd.Series(sig.w.to_numpy(), index=sig.avail.to_numpy()).sort_index()
    w = w[~w.index.duplicated(keep="last")]
    return w.reindex(w.index.union(days)).ffill().reindex(days).fillna(0.0)


def book(window: tuple[str, str], cost_key: str, w_override: pd.Series | None = None) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Daily P&L of w x (-7 * dy), position set at close t earns t -> t+1. Returns (book, active, weights)."""
    y = dgs10()
    days = y.loc[window[0]:window[1]].index
    w = w_override.reindex(days).fillna(0.0) if w_override is not None else weights_daily(signal(inventory()), days)
    dur_ret = (-(y.diff()) / 100.0 * DUR).reindex(days).fillna(0.0)
    held = w.shift(1).fillna(0.0)
    tc = w.diff().abs().fillna(w.abs()) * COSTS[cost_key]
    b = held * dur_ret - tc
    ctrl = float(w.mean()) * dur_ret                             # exposure-matched control (amendment-4 proposal Q1, adopted voluntarily)
    return b, b - ctrl, w
