"""Vectorised synthetic daily/periodic return generators for gate calibration.

Everything here is synthetic. No project price data, no family evaluate.py, and no locked
validation window is read or computed by this module.

Design note (documented approximation)
---------------------------------------
Rather than reverse-engineering each family's exact volatility from its raw prices (which the
workstream is barred from loading), each simulated series is generated as a stationary AR(1)
process at the family's own reporting frequency, with:
  - length matched to the family's actual development/validation window (in periods);
  - an annualised volatility representative of the book type (spread/market-neutral books use a
    lower vol than raw long-only books, consistent with what's visible in reports/*/dev_results.json
    -- e.g. mbs_convexity ann_vol ~1.2%, commodity_roll ~10-11%, tsy_month_end active_ann ~3%, all in
    the single low-double-digit range);
  - an autocorrelation phi chosen so the realised sampling dispersion of the annualised Sharpe
    (kappa = sd(Sharpe_hat) * sqrt(T)) lands near the range `reports/null_lab/REPORT.md` already
    established empirically for this project's own engines: kappa in roughly [0.85, 1.4], median
    ~0.95-1.08 for market-neutral books and up to ~1.3-1.4 for persistent/trending signals.

kappa is *reported*, not assumed: `calibrate.kappa_of` measures it directly off each simulated
null-world batch, so a reviewer can check it against the null_lab range rather than take it on
faith.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import lfilter


def ar1_paths(n_periods: int, n_draws: int, periods_per_year: float, annual_vol: float,
              annual_mean: float, phi: float, rng: np.random.Generator) -> np.ndarray:
    """Simulate n_draws stationary AR(1) return paths of length n_periods.

    Returns an (n_draws, n_periods) array. The marginal (unconditional) annualised vol equals
    `annual_vol` and the annualised mean equals `annual_mean`, by construction: the AR(1)
    recursion only reshapes the autocovariance structure, not the marginal variance.
    """
    if n_periods <= 1:
        n_periods = 2
    sigma_period = annual_vol / np.sqrt(periods_per_year)
    mu_period = annual_mean / periods_per_year
    phi = float(np.clip(phi, -0.95, 0.95))
    sigma_eps = sigma_period * np.sqrt(max(1e-12, 1 - phi ** 2))
    eps = rng.normal(0.0, sigma_eps, size=(n_draws, n_periods))
    # AR(1): x_t = phi * x_{t-1} + eps_t, vectorised across draws via lfilter along axis=1.
    x = lfilter([1.0], [1.0, -phi], eps, axis=1)
    return x + mu_period


def sharpe_of(paths: np.ndarray, periods_per_year: float) -> np.ndarray:
    mean = paths.mean(axis=1)
    sd = paths.std(axis=1, ddof=1)
    sd = np.where(sd <= 0, np.nan, sd)
    return mean / sd * np.sqrt(periods_per_year)


def ann_mean_of(paths: np.ndarray, periods_per_year: float) -> np.ndarray:
    return paths.mean(axis=1) * periods_per_year


def naive_t_of(paths: np.ndarray) -> np.ndarray:
    """t-stat of the per-period mean under the naive iid SE, computed directly off the simulated
    (already-autocorrelated) path. Used as a documented proxy for a Newey-West HAC t-stat: since
    the path itself carries the AR(1) structure, the *sampling* distribution of this statistic
    across Monte Carlo draws already reflects the autocorrelation-driven SE inflation, even though
    the per-draw formula is the plain iid one."""
    n = paths.shape[1]
    mean = paths.mean(axis=1)
    sd = paths.std(axis=1, ddof=1)
    sd = np.where(sd <= 0, np.nan, sd)
    return mean / sd * np.sqrt(n)


def kappa_of(sharpe_null_zero_mean: np.ndarray, years: float) -> float:
    """kappa = sd(Sharpe_hat) * sqrt(years), the null_lab convention (REPORT.md section 4)."""
    return float(np.nanstd(sharpe_null_zero_mean) * np.sqrt(years))
