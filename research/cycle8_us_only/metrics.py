"""Cycle 8 metrics (FRAMEWORK §5.1-§5.3)."""
from __future__ import annotations

import numpy as np
import pandas as pd

CRISES = {
    "1973-74 oil/inflation": ("1973-01", "1974-12"),
    "1979-81 Volcker": ("1979-10", "1981-09"),
    "1987 crash": ("1987-08", "1987-12"),
    "2000-02 dot-com": ("2000-09", "2002-09"),
    "2007-09 GFC": ("2007-11", "2009-02"),
    "2020 COVID": ("2020-02", "2020-03"),
    "2022 stocks+bonds": ("2022-01", "2022-10"),
}
CRISES_US1926 = {"1929-32 Depression": ("1929-09", "1932-06"), "1937-38": ("1937-03", "1938-03")}


def wealth_from_returns(r: pd.Series) -> pd.Series:
    return (1 + r).cumprod()


def drawdowns(w: np.ndarray) -> np.ndarray:
    peak = np.maximum.accumulate(w)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.nan_to_num(1 - w / peak, nan=1.0)


def longest_underwater(w: np.ndarray) -> int:
    """Longest run (in periods) from a peak until wealth regains it (or the sample ends)."""
    peak = np.maximum.accumulate(w)
    under = w < peak - 1e-12
    best = cur = 0
    for u in under:
        cur = cur + 1 if u else 0
        best = max(best, cur)
    return int(best)


def ulcer(w: np.ndarray) -> float:
    dd = drawdowns(w) * 100
    return float(np.sqrt(np.mean(dd ** 2)))


def summary(r: pd.Series, rf: pd.Series, cpi: pd.Series | None = None, sharpe_ci=True) -> dict:
    """Monthly returns r (CAD), CAD T-bill monthly return rf, CPI index (same index) -> metrics dict."""
    r = r.dropna()
    rf = rf.reindex(r.index)
    n = len(r)
    w = np.concatenate([[1.0], (1 + r.values).cumprod()])
    yrs = n / 12
    cagr = w[-1] ** (1 / yrs) - 1 if w[-1] > 0 else -1.0
    out = {"start": r.index[0].strftime("%Y-%m"), "end": r.index[-1].strftime("%Y-%m"), "months": n,
           "cagr": cagr, "vol": r.std(ddof=1) * np.sqrt(12)}
    if cpi is not None:
        c = cpi.reindex(r.index)
        c0 = cpi.shift(1).reindex(r.index).iloc[0]
        infl = (c.iloc[-1] / c0) ** (1 / yrs) - 1
        out["cagr_real"] = (1 + cagr) / (1 + infl) - 1
    ex = (r - rf).values
    out["sharpe"] = ex.mean() / ex.std(ddof=1) * np.sqrt(12)
    if sharpe_ci:
        from research.amendment4.ci import calibrated_ci
        ci = calibrated_ci(ex, level=0.95, q=12, seed=20260928)
        out["sharpe_lo"], out["sharpe_hi"] = ci["sharpe_ann"][0], ci["sharpe_ann"][1]
    dd = drawdowns(w)
    out["maxdd"] = dd.max()
    out["underwater_m"] = longest_underwater(w)
    roll = pd.Series(w).pct_change(12).dropna()
    out["worst12"] = roll.min() if len(roll) else np.nan
    out["ulcer"] = ulcer(w)
    return out


def crisis_table(r: pd.Series, crises=CRISES) -> dict:
    out = {}
    for name, (a, b) in crises.items():
        seg = r.loc[a:b]
        if len(seg) == 0 or seg.index[0] > pd.Timestamp(a) + pd.offsets.MonthEnd(0) or seg.isna().any():
            out[name] = (np.nan, np.nan)
            continue
        w = np.concatenate([[1.0], (1 + seg.values).cumprod()])
        out[name] = (w[-1] - 1, drawdowns(w).max())
    return out


def stationary_indices(n: int, T: int, P: int, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    """Politis-Romano stationary bootstrap indices, (P, T) into range(n), circular wrap."""
    p = 1.0 / mean_block
    idx = np.empty((P, T), dtype=np.int64)
    idx[:, 0] = rng.integers(0, n, P)
    new = rng.random((P, T)) < p
    starts = rng.integers(0, n, (P, T))
    for t in range(1, T):
        idx[:, t] = np.where(new[:, t], starts[:, t], (idx[:, t - 1] + 1) % n)
    return idx


def kelly(r1: np.ndarray, mrate_m: np.ndarray, B=5000, mean_block=24, seed=20260928) -> dict:
    """Growth-optimal margin leverage L* = (mean(r) - mean(margin)) / var(r) with stationary-bootstrap spread."""
    r1 = np.asarray(r1, float)
    mr = np.asarray(mrate_m, float)
    n = len(r1)
    point = (r1.mean() - mr.mean()) / r1.var(ddof=1)
    rng = np.random.default_rng(seed)
    idx = stationary_indices(n, n, B, mean_block, rng)
    rr, mm = r1[idx], mr[idx]
    ls = (rr.mean(1) - mm.mean(1)) / rr.var(1, ddof=1)
    return {"kelly_point": point, "kelly_median": float(np.median(ls)), "kelly_p05": float(np.quantile(ls, 0.05)),
            "half_kelly": 0.5 * float(np.median(ls)), "half_kelly_p05": 0.5 * float(np.quantile(ls, 0.05))}
