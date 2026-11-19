"""Par-bond repricing (FRAMEWORK §2), vectorised.

At step t−1 buy a par bond: coupon c = y_{t−1} (annual rate, semiannual payments), maturity T.
At t reprice it with remaining maturity T − Δ at yield y_t and add the coupon accrued over Δ (c·Δ):

    r_t = P(c, T − Δ, y_t) + c·Δ − 1,
    P(c, n, y) = (c / y)·(1 − (1 + y/2)^(−2n)) + (1 + y/2)^(−2n)     (semiannual compounding)

P(c, n, c) = 1 for any n, so an unchanged yield gives r = y·Δ exactly. The y → 0 limit
P = c·n + 1 is used where |y| < 1e-9. Δ = 1/12 monthly, 1/252 per trading day.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def par_price(c, n, y):
    c = np.asarray(c, dtype=float)
    y = np.asarray(y, dtype=float)
    n = np.asarray(n, dtype=float)
    disc = (1.0 + y / 2.0) ** (-2.0 * n)
    small = np.abs(y) < 1e-9
    ysafe = np.where(small, 1.0, y)
    annuity = np.where(small, n, (1.0 - disc) / ysafe)
    return c * annuity + disc


def par_bond_return(y_prev, y_now, maturity: float, dt: float):
    """Simple total return of a par bond bought at y_prev and repriced at y_now after dt years."""
    y_prev = np.asarray(y_prev, dtype=float)
    return par_price(y_prev, maturity - dt, y_now) + y_prev * dt - 1.0


def returns_from_yields(y: pd.Series, maturity: float, dt: float) -> pd.Series:
    """Return series from a yield-level series (annual decimals); first obs is NaN.

    Uses consecutive observations only (no gap filling); the caller supplies the sampled series.
    """
    y = y.astype(float)
    r = par_bond_return(y.shift(1).to_numpy(), y.to_numpy(), maturity, dt)
    return pd.Series(r, index=y.index, name=y.name)


def modified_duration_par(y: float, maturity: float) -> float:
    """Modified duration of a par bond (semiannual), for tests / notes."""
    eps = 1e-6
    p_up = par_price(y, maturity, y + eps)
    p_dn = par_price(y, maturity, y - eps)
    return float(-(p_up - p_dn) / (2 * eps))
