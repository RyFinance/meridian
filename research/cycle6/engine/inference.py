"""Estimates and inference (FRAMEWORK §4, A4 §2/§6, A5 §C-D guards).

calibrated_p: A4 §2 null-calibrated HAC t, one-sided (mean > 0), exact (full=True), B from the spec (9,999),
crash layer (intensity per year converted to per month, jump in sd) and bandwidth fraction from the spec.
calibrated_ci: A4 §6 studentised AR-sieve bootstrap-t (B = 499), 90%; 95% when crash-declared and n < 120.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from research.amendment4 import calib, ci

PPY = 12


def window(s: pd.Series | pd.DataFrame, start=None, end=None):
    idx = s.index
    m = np.ones(len(idx), bool)
    if start is not None:
        m &= idx >= pd.Period(start, "M")
    if end is not None:
        m &= idx <= pd.Period(end, "M")
    return s[m]


def crash_tuple(crash: dict | None, ppy: int = PPY):
    if not crash:
        return None
    return (float(crash["intensity_per_year"]) / ppy, float(crash["jump_sd"]))


def calibrated_p(x, *, B: int, seed: int, crash: dict | None, bandwidth_fraction: float, overlap: int = 1) -> dict:
    x = np.asarray(pd.Series(x).dropna(), float)
    if x.size < 24:
        return {"p": None, "t": None, "L": None, "n": int(x.size), "note": "fewer than 24 months"}
    r = calib.calibrated_pvalues(x[None, :], B=int(B), seed=int(seed), crash=crash_tuple(crash), full=True,
                                 bandwidth_fraction=float(bandwidth_fraction), overlap=int(overlap))
    return {"p": float(r["p"][0]), "t": float(r["t"][0]), "L": int(r["L"]), "ar_order": int(r["ar_order"][0]),
            "n": int(x.size), "B": int(B), "crash": crash, "bandwidth_fraction": float(bandwidth_fraction)}


def ci_level(n: int, crash_declared: bool, base: float = 0.90, short_crash: float = 0.95) -> float:
    return short_crash if (crash_declared and n < 120) else base


def calibrated_ci(x, *, level: float, B: int = ci.B_CI, seed: int = 1) -> dict:
    x = np.asarray(pd.Series(x).dropna(), float)
    if x.size < 24:
        return {"level": level, "n": int(x.size), "note": "fewer than 24 months"}
    r = ci.calibrated_ci(x, level=level, q=PPY, B=int(B), seed=int(seed))
    return {"level": level, "n": int(x.size), "B": int(B),
            "mean_ann": {"lo": r["mean_ann"][0], "hi": r["mean_ann"][1], "est": r["mean_ann"][2]},
            "sharpe_ann": {"lo": r["sharpe_ann"][0], "hi": r["sharpe_ann"][1], "est": r["sharpe_ann"][2]},
            "L": int(r["L"])}


def basic_stats(x: pd.Series) -> dict:
    x = x.dropna()
    n = len(x)
    if n < 2:
        return {"n": n}
    m, sd = float(x.mean()), float(x.std(ddof=1))
    nav = (1 + x).cumprod()
    years = n / PPY
    return {"n": n, "first": str(x.index[0]), "last": str(x.index[-1]),
            "mean_ann": m * PPY, "vol_ann": sd * math.sqrt(PPY),
            "sharpe_ann": m / sd * math.sqrt(PPY) if sd > 0 else None,
            "cagr": float(nav.iloc[-1] ** (1 / years) - 1) if nav.iloc[-1] > 0 else None,
            "max_drawdown": max_drawdown(x), "hit_rate": float((x > 0).mean())}


def max_drawdown(x: pd.Series | np.ndarray) -> float:
    nav = np.cumprod(1 + np.asarray(x, float))
    peak = np.maximum.accumulate(np.concatenate([[1.0], nav]))[1:]
    return float((nav / peak - 1).min())


def calendar_years(x: pd.Series) -> dict:
    x = x.dropna()
    yr = (1 + x).groupby(x.index.year).prod() - 1
    if yr.empty:
        return {}
    return {"best_year": int(yr.idxmax()), "best_year_ret": float(yr.max()),
            "worst_year": int(yr.idxmin()), "worst_year_ret": float(yr.min()),
            "by_year": {int(k): float(v) for k, v in yr.items()}}


def _sharpe(x) -> float | None:
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if x.size < 3 or x.std(ddof=1) == 0:
        return None
    return float(x.mean() / x.std(ddof=1) * math.sqrt(PPY))


def concentration(x: pd.Series, asset_pnl: pd.DataFrame | None = None) -> dict:
    """A5 G3/G4: top-5%-months share of P&L, max-year share, leave-one-year-out Sharpe (min / full), best
    contiguous 12/24 months removed, sign test, largest-asset share."""
    from scipy import stats as st
    x = x.dropna()
    tot = float(x.sum())
    out = {"total_pnl": tot, "total_pnl_nonpositive": tot <= 0}
    if len(x) < 12:
        return out
    k = int(math.ceil(0.05 * len(x)))
    out["top5pct_months_share"] = float(np.sort(x.to_numpy())[::-1][:k].sum() / tot) if tot != 0 else None
    ys = x.groupby(x.index.year).sum()
    out["max_year_share"] = float(ys.max() / tot) if tot != 0 else None
    out["max_year"] = int(ys.idxmax())
    full = _sharpe(x)
    loyo = {int(y): _sharpe(x[x.index.year != y]) for y in ys.index}
    vals = [v for v in loyo.values() if v is not None]
    out["leave_one_year_out_min_sharpe"] = min(vals) if vals else None
    out["full_sharpe"] = full
    for w in (12, 24):
        if len(x) > w + 12:
            roll = x.rolling(w).sum()
            end = int(np.nanargmax(roll.to_numpy()))
            keep = np.ones(len(x), bool)
            keep[end - w + 1: end + 1] = False
            out[f"sharpe_best_{w}m_removed"] = _sharpe(x.to_numpy()[keep])
    npos = int((x > 0).sum())
    out["sign_test_p"] = float(st.binomtest(npos, int((x != 0).sum()), 0.5, alternative="greater").pvalue)
    if asset_pnl is not None and not asset_pnl.empty:
        a = asset_pnl.reindex(x.index).sum()
        at = float(a.sum())
        out["asset_pnl"] = {str(k): float(v) for k, v in a.items()}
        out["largest_asset"] = str(a.idxmax())
        out["largest_asset_share"] = float(a.max() / at) if at != 0 else None
    return out


def hac_ols(y: pd.Series, X: pd.DataFrame) -> dict:
    """OLS with intercept, Newey-West (Bartlett, plug-in lags) standard errors."""
    df = pd.concat([y.rename("_y"), X], axis=1).dropna()
    n = len(df)
    if n < 24:
        return {"n": n, "note": "fewer than 24 common months"}
    Y = df["_y"].to_numpy()
    Z = np.column_stack([np.ones(n), df[X.columns].to_numpy()])
    ZtZi = np.linalg.inv(Z.T @ Z)
    b = ZtZi @ Z.T @ Y
    u = Y - Z @ b
    L = calib.nw_default_lags(n)
    g = Z * u[:, None]
    S = g.T @ g
    for k in range(1, L + 1):
        G = g[k:].T @ g[:-k]
        S += (1 - k / (L + 1)) * (G + G.T)
    V = ZtZi @ S @ ZtZi
    se = np.sqrt(np.diag(V))
    names = ["alpha"] + list(X.columns)
    out = {"n": n, "nw_lags": L, "coef": dict(zip(names, map(float, b))), "t": dict(zip(names, map(float, b / se)))}
    out["alpha_ann"] = float(b[0] * PPY)
    mean = float(Y.mean())
    out["alpha_share_of_mean"] = float(b[0] / mean) if mean != 0 else None
    return out


def betas(y: pd.Series, refs: dict[str, pd.Series]) -> dict:
    if not refs:
        return {}
    X = pd.concat({k: v for k, v in refs.items()}, axis=1)
    return hac_ols(y, X)
