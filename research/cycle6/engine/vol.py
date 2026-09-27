"""MOP ex-ante volatility (Sol's component-1 text, A5 §A):

  sigma^2_{i,d} = A * sum_{j>=0} w_j (r_{i,d-j} - mu_{i,d})^2,   w_j = (1-delta) delta^j,  delta = com/(com+1)
  mu_{i,d}      = sum_j w_j r_{i,d-j}                              (same weights; mean-centred)

with com = 60 days (delta = 60/61) and A = 261 in the spec. The sum is truncated at the instrument's first valid
observation and the remaining weights renormalised to one. Only the instrument's valid days count as observations
(NaN days are skipped, not zero-filled). The estimate at d uses returns through d; it is NaN until the instrument has
``min_obs`` valid observations (756 in the spec) and when the variance is not positive. ``lag_obs`` shifts the
estimate by that many of the instrument's own observations (0 = information through the decision close).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import lfilter


def ew_vol_1d(x: np.ndarray, com_days: float, annualisation: float, min_obs: int) -> np.ndarray:
    x = np.asarray(x, float)
    if x.size == 0:
        return x.copy()
    delta = com_days / (com_days + 1.0)
    a = [1.0, -delta]
    s0 = lfilter([1.0], a, np.ones_like(x))
    s1 = lfilter([1.0], a, x)
    s2 = lfilter([1.0], a, x * x)
    mu = s1 / s0
    var = annualisation * (s2 / s0 - mu * mu)
    cnt = np.arange(1, x.size + 1)
    out = np.full(x.size, np.nan)
    ok = (cnt >= min_obs) & (var > 0)
    out[ok] = np.sqrt(var[ok])
    return out


def ew_vol(daily: pd.DataFrame, *, com_days: float, annualisation: float, min_obs: int,
           lag_obs: int = 0) -> pd.DataFrame:
    out = pd.DataFrame(np.nan, index=daily.index, columns=daily.columns)
    for c in daily.columns:
        s = daily[c].dropna()
        if s.empty:
            continue
        v = pd.Series(ew_vol_1d(s.to_numpy(), com_days, annualisation, min_obs), index=s.index)
        if lag_obs:
            v = v.shift(int(lag_obs))
        out.loc[s.index, c] = v.to_numpy()
    return out


def ew_vol_bruteforce(x: np.ndarray, com_days: float, annualisation: float, min_obs: int) -> np.ndarray:
    """O(n^2) reference implementation for tests."""
    x = np.asarray(x, float)
    delta = com_days / (com_days + 1.0)
    out = np.full(x.size, np.nan)
    for d in range(x.size):
        j = np.arange(d + 1)
        w = (1 - delta) * delta ** j
        w = w / w.sum()
        r = x[d - j]
        mu = (w * r).sum()
        var = annualisation * (w * (r - mu) ** 2).sum()
        if d + 1 >= min_obs and var > 0:
            out[d] = np.sqrt(var)
    return out
