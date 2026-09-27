"""research.amendment4.dgp -- synthetic return processes for the Amendment-4 simulations (zero-mean noise, unit
diffusion scale; shift by S / sqrt(q) * sd for a true annualised Sharpe S). Synthetic only."""
from __future__ import annotations

import math

import numpy as np
from scipy.signal import lfilter


def iid(P, n, rng):
    return rng.standard_normal((P, n))


def ar1(P, n, rng, phi):
    e = rng.standard_normal((P, n))
    e[:, 1:] *= math.sqrt(1 - phi * phi)
    return lfilter([1.0], [1.0, -phi], e, axis=1) if phi else e


def overlap(P, n, rng, H):
    base = rng.standard_normal((P, n + H - 1))
    cs = np.concatenate([np.zeros((P, 1)), np.cumsum(base, axis=1)], axis=1)
    return (cs[:, H:] - cs[:, :-H]) / math.sqrt(H)


def crash_moments(p, J):
    """Z + (I - p) J with I ~ Bernoulli(p): cumulants add (Bernoulli k3 = p(1-p)(1-2p), k4 = p(1-p)(1-6p+6p^2))."""
    var = 1 + p * (1 - p) * J * J
    k3 = p * (1 - p) * (1 - 2 * p) * J ** 3
    k4 = p * (1 - p) * (1 - 6 * p + 6 * p * p) * J ** 4
    return {"var": var, "skew": k3 / var ** 1.5, "exkurt": k4 / var ** 2}


def crash(P, n, rng, p, J, phi=0.0):
    """Z + I*J - p*J, standardised to unit variance (optionally AR(1) phi on top)."""
    I = rng.random((P, n)) < p
    x = (rng.standard_normal((P, n)) + I * J - p * J) / math.sqrt(1 + p * (1 - p) * J * J)
    if phi:
        x[:, 1:] *= math.sqrt(1 - phi * phi)
        x = lfilter([1.0], [1.0, -phi], x, axis=1)
    return x


def regime(P, n, rng, mean_sr_ann, q, dur):
    """Two-state symmetric Markov regime mean +-m (m = mean_sr_ann / sqrt(q) diffusion sds), expected regime
    duration `dur` periods. Unconditional mean 0. Returned standardised to unit variance."""
    m = mean_sr_ann / math.sqrt(q)
    sw = 1.0 / dur
    s = np.where(rng.random(P) < 0.5, 1.0, -1.0)
    u = rng.random((P, n))
    st = np.empty((P, n))
    for t in range(n):
        s = np.where(u[:, t] < sw, -s, s)
        st[:, t] = s
    return (m * st + rng.standard_normal((P, n))) / math.sqrt(1 + m * m)


def regime_D(mean_sr_ann, q, dur):
    m = mean_sr_ann / math.sqrt(q)
    w = m * m / (1 + m * m)
    lam = 1 - 2.0 / dur
    return 1 + 2 * w * lam / (1 - lam)


SCENARIOS = {
    # name: (generator, kwargs, q, n, declared overlap H, declared crash)
    "monthly_iid_10y": (iid, {}, 12, 120, 1, None),
    "monthly_ar1_0.3_10y": (ar1, {"phi": 0.3}, 12, 120, 1, None),
    "monthly_overlap3_10y": (overlap, {"H": 3}, 12, 120, 3, None),
    "weekly_overlap4_5y": (overlap, {"H": 4}, 52, 260, 4, None),
    "monthly_carry_crash_10y": (crash, {"p": 0.2 / 12, "J": -6.0}, 12, 120, 1, None),
    "monthly_carry_crash_10y_declared": (crash, {"p": 0.2 / 12, "J": -6.0}, 12, 120, 1, (0.2 / 12, -6.0)),
    "daily_regime180_sr0.5_10y": (regime, {"mean_sr_ann": 0.5, "q": 252, "dur": 180}, 252, 2520, 1, None),
    "daily_regime180_sr1.0_10y": (regime, {"mean_sr_ann": 1.0, "q": 252, "dur": 180}, 252, 2520, 1, None),
    "monthly_regime6m_sr1.0_10y": (regime, {"mean_sr_ann": 1.0, "q": 12, "dur": 6}, 12, 120, 1, None),
    "daily_iid_10y": (iid, {}, 252, 2520, 1, None),
    "daily_ar1_0.1_10y": (ar1, {"phi": 0.1}, 252, 2520, 1, None),
}


def generate(name, P, rng):
    g, kw, q, n, H, cr = SCENARIOS[name]
    return g(P, n, rng, **kw)
