"""Null-world generators: keep realistic market structure, destroy the signal -> future-return link.

Signal nulls (all operate on a panel of shape (T periods, N assets); NaN marks "no signal"):

  (a) `circular_shift`     real panel rolled in time by an offset in [min_offset, T - min_offset]
                           periods, so every value is paired with returns at least `min_offset`
                           periods away in either direction. Autocorrelation, cross-sectional
                           dispersion, per-asset tilts and the NaN pattern (moved with the values)
                           survive.
  (b) `ar1_panel`          synthetic per-asset AR(1) (+ optional per-asset fixed effect) with the
                           persistence of the real panel (`match_persistence`); the real NaN mask is
                           re-applied. `ma_panel` is the overlapping-window alternative (sum of q+1
                           iid shocks), which matches rolling-window signals whose autocorrelation
                           dies at lag q+1.
  (c) `permute_cross_section`  values shuffled across assets within each date (non-NaN slots only).

Return-path null:

  (d) `stationary_bootstrap`   Politis-Romano stationary bootstrap of whole dates (every asset moves
                               together), mean block length `mean_block`; volatility clustering
                               and cross-correlation survive, calendar alignment with the signal
                               does not.

Everything takes an explicit `numpy.random.Generator`; nothing reads global state.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq
from scipy.stats import multivariate_normal, norm


# -- (a) circular shift ----------------------------------------------------------------------------
def draw_offsets(n_periods: int, min_offset: int, size: int, rng: np.random.Generator) -> np.ndarray:
    """Uniform integer offsets in [min_offset, n_periods - min_offset] (both directions >= min_offset)."""
    hi = n_periods - min_offset
    if hi < min_offset:
        raise ValueError(f"panel of {n_periods} periods cannot be shifted by >= {min_offset} both ways")
    return rng.integers(min_offset, hi + 1, size=size)


def circular_shift(panel: np.ndarray, offset: int, min_offset: int) -> np.ndarray:
    """out[t] = panel[(t - offset) mod T]. Refuses offsets closer than min_offset to 0 or T."""
    T = panel.shape[0]
    if not (min_offset <= offset <= T - min_offset):
        raise ValueError(f"offset {offset} violates the >= {min_offset}-period separation")
    return np.roll(panel, offset, axis=0)


# -- persistence -----------------------------------------------------------------------------------
def _rank_rows(x: np.ndarray) -> np.ndarray:
    """Average-free ordinal ranks within each row, NaN kept."""
    out = np.full(x.shape, np.nan)
    for i, row in enumerate(x):
        m = np.isfinite(row)
        if m.sum():
            out[i, m] = np.argsort(np.argsort(row[m], kind="stable"), kind="stable") + 1.0
    return out


def rank_autocorr(panel: np.ndarray, lag: int, min_names: int = 5) -> float:
    """Mean over dates of the Spearman correlation between panel[t] and panel[t-lag] across assets."""
    vals = []
    for t in range(lag, panel.shape[0]):
        a, b = panel[t], panel[t - lag]
        m = np.isfinite(a) & np.isfinite(b)
        if m.sum() >= min_names:
            ra = _rank_rows(a[m][None])[0]
            rb = _rank_rows(b[m][None])[0]
            vals.append(np.corrcoef(ra, rb)[0, 1])
    return float(np.mean(vals)) if vals else float("nan")


def series_autocorr(x: np.ndarray, lag: int) -> float:
    x = np.asarray(x, float)
    a, b = x[lag:], x[:-lag]
    m = np.isfinite(a) & np.isfinite(b)
    return float(np.corrcoef(a[m], b[m])[0, 1])


def match_persistence(rho1: float, rho_long: float | None = None, long_lag: int = 12) -> tuple[float, float]:
    """(phi, fe_share) such that an AR(1) with a per-asset fixed effect of variance share fe_share has
    lag-1 autocorrelation rho1 and lag-`long_lag` autocorrelation rho_long:
        rho(k) = s + (1 - s) * phi**k.
    With rho_long None (or <= 0) the fixed effect is dropped and phi = rho1."""
    rho1 = float(np.clip(rho1, -0.99, 0.999))
    if rho_long is None or rho_long <= 0 or rho_long >= rho1:
        return rho1, 0.0
    s = float(rho_long)  # first guess: plateau
    for _ in range(50):
        phi = (rho1 - s) / (1 - s)
        s_new = (rho_long - phi ** long_lag) / (1 - phi ** long_lag)
        s_new = float(np.clip(s_new, 0.0, rho1 - 1e-6))
        if abs(s_new - s) < 1e-12:
            break
        s = s_new
    phi = (rho1 - s) / (1 - s)
    return float(phi), float(s)


# -- (b) synthetic persistent panels ---------------------------------------------------------------
def ar1_panel(T: int, N: int, phi: float, rng: np.random.Generator, fe_share: float = 0.0,
              worlds: int = 1) -> np.ndarray:
    """(worlds, T, N) standard-normal-marginal panels: sqrt(s)*a_i + sqrt(1-s)*AR(1)(phi), stationary
    from t = 0."""
    e = rng.standard_normal((worlds, T, N))
    x = np.empty_like(e)
    x[:, 0] = e[:, 0]
    c = np.sqrt(max(1.0 - phi * phi, 0.0))
    for t in range(1, T):
        x[:, t] = phi * x[:, t - 1] + c * e[:, t]
    if fe_share > 0:
        a = rng.standard_normal((worlds, 1, N))
        x = np.sqrt(fe_share) * a + np.sqrt(1.0 - fe_share) * x
    return x


def ma_panel(T: int, N: int, q: int, rng: np.random.Generator, worlds: int = 1) -> np.ndarray:
    """Overlapping-window null: x_t = sum_{j=0..q} e_{t-j} / sqrt(q+1); rho(k) = (q+1-k)/(q+1)."""
    e = rng.standard_normal((worlds, T + q, N))
    c = np.cumsum(e, axis=1)
    c = np.concatenate([np.zeros((worlds, 1, N)), c], axis=1)
    return (c[:, q + 1:] - c[:, :-q - 1]) / np.sqrt(q + 1)


def apply_mask(synth: np.ndarray, real: np.ndarray) -> np.ndarray:
    """Copy the real panel's NaN pattern onto (worlds, T, N) synthetic panels."""
    out = synth.copy()
    out[:, ~np.isfinite(real)] = np.nan
    return out


def binary_phi_for_switch_rate(p_in: float, rho_binary: float) -> float:
    """Latent AR(1) coefficient phi such that 1{z_t > q} (q = norm.ppf(1 - p_in)) has lag-1
    autocorrelation rho_binary."""
    q = norm.ppf(1 - p_in)
    var = p_in * (1 - p_in)

    def f(phi):
        both = multivariate_normal(mean=[0, 0], cov=[[1, phi], [phi, 1]]).cdf([-q, -q])  # P(z1>q, z2>q)
        return (both - p_in ** 2) / var - rho_binary

    lo, hi = -0.99, 0.99999
    if f(hi) < 0:
        return hi
    return float(brentq(f, lo, hi, xtol=1e-8))


# -- (c) cross-sectional permutation ---------------------------------------------------------------
def permute_cross_section(panel: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Shuffle the non-NaN values of every row among that row's non-NaN slots."""
    out = panel.copy()
    for t in range(panel.shape[0]):
        m = np.flatnonzero(np.isfinite(panel[t]))
        if len(m) > 1:
            out[t, m] = panel[t, rng.permutation(m)]
    return out


# -- (d) stationary bootstrap of whole dates -------------------------------------------------------
def stationary_bootstrap(n_source: int, length: int, mean_block: float, rng: np.random.Generator,
                         worlds: int = 1) -> np.ndarray:
    """(worlds, length) source-date indices. Each step continues the current block (circularly) with
    probability 1 - 1/mean_block, otherwise restarts at a uniform date."""
    p = 1.0 / mean_block
    start = rng.integers(0, n_source, size=(worlds, length))
    restart = rng.random((worlds, length)) < p
    restart[:, 0] = True
    # position within block: index since last restart
    idx = np.arange(length)[None, :].repeat(worlds, 0)
    last = np.where(restart, idx, 0)
    last = np.maximum.accumulate(last, axis=1)
    offset = idx - last
    base = np.take_along_axis(start, last, axis=1)
    return (base + offset) % n_source
