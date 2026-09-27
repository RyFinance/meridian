"""Proposed A4 event-design effective-N validator; does not mutate Amendment 4.

The A4 calibrated p-value operates on calendar-time returns and does not use
effective N. This validator prevents a sparse event strategy's power report
from calling non-event days independent bets.
"""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np


def event_effective_n(
    event_returns: Sequence[float],
    cluster_ids: Sequence[object],
    daily_effective_n: float,
    *,
    overlap_multiplicity: float = 1.0,
    hac_lags: int | None = None,
) -> dict[str, float]:
    """Cap a daily-series effective N by event count and event dependence.

    Cluster IDs must denote preregistered, non-overlapping dependence groups
    (for scheduled FOMC, calendar years). D is floored at one. Group-sum
    variance and event-order Bartlett HAC estimate two dependence channels;
    the larger is used. An explicitly declared payoff overlap factor multiplies
    the group estimate. This is a conservative power/reporting diagnostic, not
    a replacement for the A4 calendar-time p-value.
    """
    x = np.asarray(event_returns, dtype=float)
    groups = np.asarray(cluster_ids)
    m = len(x)
    if m < 3 or len(groups) != m or not np.isfinite(x).all():
        raise ValueError("need at least three finite event returns and matching cluster IDs")
    if not math.isfinite(daily_effective_n) or daily_effective_n <= 0:
        raise ValueError("daily effective N must be positive and finite")
    if not math.isfinite(overlap_multiplicity) or overlap_multiplicity < 1:
        raise ValueError("overlap multiplicity must be at least one")
    unique, inv = np.unique(groups, return_inverse=True)
    g = len(unique)
    if g < 3:
        raise ValueError("at least three independent clusters are needed")
    centered = x - x.mean()
    var = float(np.mean(centered * centered))
    if var <= 0:
        raise ValueError("event returns have zero variance")
    sums = np.bincount(inv, weights=centered, minlength=g)
    cluster_d = max(1.0, float((g / (g - 1)) * np.sum(sums * sums) / (m * var)))
    lags = min(m // 3, max(1, int(round(m ** (1 / 3))))) if hac_lags is None else int(hac_lags)
    if not 0 <= lags <= m // 3:
        raise ValueError("invalid event HAC lags")
    lrv = var
    for lag in range(1, lags + 1):
        lrv += 2 * (1 - lag / (lags + 1)) * float(np.dot(centered[lag:], centered[:-lag]) / m)
    hac_d = max(1.0, lrv / var)
    event_d = max(hac_d, cluster_d * overlap_multiplicity)
    capped = min(float(daily_effective_n), float(m), m / event_d)
    return {"n_events": float(m), "n_clusters": float(g), "cluster_D": cluster_d,
            "event_hac_D": hac_d, "overlap_multiplicity": float(overlap_multiplicity),
            "event_D": event_d, "effective_n": capped}
