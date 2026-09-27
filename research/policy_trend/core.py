"""Bond-market monetary-policy trend -> equity-index selection (research/policy_trend/PLAN.md).

Everything here is frozen by the plan:

* **Signal.** At month-end t, each economy's short-tenor government yield change over the prior 182
  days, using only yield rows dated t−1 or earlier. It is scaled by the trailing volatility of daily
  yield changes (252 obs, ×√126): z = Δy / σ. Negative z means easing.
* **Book P1.** Long the k economies with the lowest z, short the k with the highest (k = floor(N/3);
  no book if N < 6). Weights are inverse 63-day local-index volatility within each leg, each leg 1.0.
* **Returns.** The futures-equivalent excess return of each local index from its last close ≤ t to
  its last close ≤ next month-end: price return minus the local short yield × days/365.
* **Costs.** Base 2 bp, stress 6 bp per side on |Δweight|.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
YDIR, IDIR = ROOT / "data" / "bond_yields", ROOT / "data" / "policy_trend"
ECON = {  # economy: (yield file, usable-from date per yield QA)
    "US": ("US2Y", "2012-09-24"), "UK": ("UK2Y", "1991-01-03"), "EZ": ("DE2Y", "2006-03-01"),
    "JP": ("JP2Y", "2006-03-01"), "AU": ("AU2Y", "2006-03-01"), "CA": ("CA2Y", "2010-01-01"),
    "KR": ("KR2Y", "2010-06-28"), "IN": ("IN2Y", "2010-02-27"), "CN": ("CN2Y", "2012-10-08"),
    "ID": ("ID1Y", "2014-01-01"),
}
LOOKBACK_D, FRESH_D, VOL_OBS, MIN_VOL_OBS, STALE_OBS = 182, 10, 252, 200, 10
IDX_VOL, MIN_N = 63, 6
COSTS = {"gross": 0.0, "base": 2e-4, "stress": 6e-4}


def load_yields() -> dict[str, pd.Series]:
    out = {}
    for k, (f, start) in ECON.items():
        d = pd.read_parquet(YDIR / f"{f}.parquet")
        s = d.assign(date=pd.to_datetime(d["date"])).drop_duplicates("date", keep="last").set_index("date")["value"]
        s = s[(s.index.dayofweek < 5) & (s.index >= pd.Timestamp(start))].sort_index().astype(float)
        out[k] = s
    return out


def load_indices() -> pd.DataFrame:
    px = {}
    for k in ECON:
        d = pd.read_parquet(IDIR / f"{k}.parquet")
        px[k] = d.assign(date=pd.to_datetime(d["date"])).drop_duplicates("date").set_index("date")["close"].sort_index()
    return pd.DataFrame(px)


def month_ends(start: str, end: str) -> pd.DatetimeIndex:
    return pd.date_range(start, end, freq="BME")


def signal_panel(yields: dict[str, pd.Series], dates: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame]:
    """z (easing negative) and the current yield level, per month-end; NaN if ineligible."""
    z = pd.DataFrame(np.nan, index=dates, columns=list(ECON))
    lvl = z.copy()
    for k, s in yields.items():
        vals, idx = s.to_numpy(), s.index.values
        for t in dates:
            cut = np.datetime64(t - pd.Timedelta(days=1))
            i = np.searchsorted(idx, cut, side="right") - 1
            if i < MIN_VOL_OBS or (cut - idx[i]) > np.timedelta64(FRESH_D, "D"):
                continue
            if np.all(vals[i - STALE_OBS + 1:i + 1] == vals[i]):
                continue
            then = cut - np.timedelta64(LOOKBACK_D, "D")
            j = np.searchsorted(idx, then, side="right") - 1
            if j < 0 or (then - idx[j]) > np.timedelta64(FRESH_D, "D"):
                continue
            dy = np.diff(vals[max(0, i - VOL_OBS):i + 1])
            if len(dy) < MIN_VOL_OBS or dy.std() == 0:
                continue
            z.loc[t, k] = (vals[i] - vals[j]) / (dy.std(ddof=1) * np.sqrt(126))
            lvl.loc[t, k] = vals[i]
    return z, lvl


def book(score: pd.DataFrame, vol: pd.DataFrame, low_long: bool = True) -> pd.DataFrame:
    """Long the k lowest (low_long) or highest scores, short the other end; inverse-vol legs."""
    w = pd.DataFrame(0.0, index=score.index, columns=score.columns)
    for t in score.index:
        s = score.loc[t].dropna()
        s = s[vol.loc[t, s.index].notna()]
        n = len(s)
        if n < MIN_N:
            continue
        k = n // 3
        r = s.rank(method="first", ascending=low_long)
        long_, short_ = r.index[r <= k], r.index[r > n - k]
        iv = 1.0 / vol.loc[t]
        w.loc[t, long_] = iv[long_] / iv[long_].sum()
        w.loc[t, short_] = -iv[short_] / iv[short_].sum()
    return w


def period_returns(px: pd.DataFrame, yields: dict[str, pd.Series], dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Futures-equivalent excess return of each index from date t to the next date (last close ≤ each)."""
    out = pd.DataFrame(np.nan, index=dates[:-1], columns=px.columns)
    for k in px.columns:
        p = px[k].dropna()
        y = yields[k]
        for a, b in zip(dates[:-1], dates[1:]):
            pa, pb = p.loc[:a], p.loc[:b]
            if pa.empty or (a - pa.index[-1]).days > FRESH_D or (b - pb.index[-1]).days > FRESH_D:
                continue
            ya = y.loc[:a - pd.Timedelta(days=1)]
            if ya.empty:
                continue
            out.loc[a, k] = pb.iloc[-1] / pa.iloc[-1] - 1.0 - ya.iloc[-1] / 100.0 * (b - a).days / 365.0
    return out


def index_vol(px: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    r = np.log(px).diff()
    v = r.rolling(IDX_VOL, min_periods=IDX_VOL - 5).std()
    return v.reindex(dates, method="ffill")


def pnl(w: pd.DataFrame, ret: pd.DataFrame, cost: float) -> pd.Series:
    w = w.loc[ret.index]
    gross = (w * ret.fillna(0.0)).sum(axis=1)
    turn = w.diff().abs().sum(axis=1)
    turn.iloc[0] = w.iloc[0].abs().sum()
    return gross - turn * cost


def sharpe_m(x: pd.Series) -> float:
    return float(x.mean() / x.std(ddof=1) * np.sqrt(12)) if x.std(ddof=1) > 0 else float("nan")
