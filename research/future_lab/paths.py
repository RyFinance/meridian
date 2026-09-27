"""Path-risk analytics on simulated daily return matrices (paths x days). Vectorised."""
from __future__ import annotations

import numpy as np

DAYS = 252
FIN_SPREAD = 0.015  # financing at T-bill + 1.5%/yr on the borrowed (L-1) x NAV
RUIN_LEVEL = 0.5


def wealth(R: np.ndarray) -> np.ndarray:
    return np.cumprod(1.0 + R, axis=-1)


def max_drawdown(W: np.ndarray) -> np.ndarray:
    """Most negative drawdown (e.g. -0.25), peak including the starting value 1."""
    peak = np.maximum.accumulate(np.maximum(W, 1.0), axis=-1)
    return (W / peak - 1.0).min(axis=-1)


def drawdown_path(W: np.ndarray) -> np.ndarray:
    peak = np.maximum.accumulate(np.maximum(W, 1.0), axis=-1)
    return W / peak - 1.0


def running_max_dd(W: np.ndarray) -> np.ndarray:
    """Worst drawdown reached so far at each day (non-increasing)."""
    return np.minimum.accumulate(drawdown_path(W), axis=-1)


def longest_underwater(W: np.ndarray) -> np.ndarray:
    """Longest spell of consecutive days strictly below the running peak (days)."""
    under = drawdown_path(W) < -1e-12
    c = np.cumsum(under, axis=-1)
    reset = np.maximum.accumulate(np.where(~under, c, 0), axis=-1)
    return (c - reset).max(axis=-1)


def cagr(W_end: np.ndarray, days: int) -> np.ndarray:
    return np.power(np.maximum(W_end, 1e-12), DAYS / days) - 1.0


def excess_sharpe(R: np.ndarray, RF: np.ndarray) -> np.ndarray:
    X = R - RF
    sd = X.std(axis=-1, ddof=1)
    return np.divide(X.mean(axis=-1), sd, out=np.full(sd.shape, np.nan), where=sd > 0) * np.sqrt(DAYS)


def levered(R: np.ndarray, RF: np.ndarray, L: float, spread: float = FIN_SPREAD) -> np.ndarray:
    """Constant daily-rebalanced leverage L on the whole NAV, borrowing (L-1) x NAV at T-bill + spread.
    For PEAD this is conservative: its average gross exposure is 25-42%, so an actual account could
    scale positions without borrowing; here the full (L-1) is charged."""
    return L * R - (L - 1.0) * (RF + spread / DAYS)


def horizon_metrics(R: np.ndarray, RF: np.ndarray, h: int) -> dict[str, np.ndarray]:
    r, f = R[..., :h], RF[..., :h]
    W = wealth(r)
    return {"cagr": cagr(W[..., -1], h), "sharpe": excess_sharpe(r, f), "max_dd": max_drawdown(W),
            "underwater_years": longest_underwater(W) / DAYS, "terminal": W[..., -1],
            "min_wealth": np.minimum(W.min(axis=-1), 1.0)}


def q(x: np.ndarray, probs=(0.05, 0.25, 0.5, 0.75, 0.95)) -> dict[str, float]:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return {f"p{int(round(p * 100)):02d}": float(np.quantile(x, p)) for p in probs}
