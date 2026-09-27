"""A5 §E combined book: ERC combiner, 10% ex-ante vol target, 2x gross cap, cash/financing, leverage-for-12%
information calc and the stationary-block MDD simulation. All numbers arrive via ``params`` from the book spec;
module constants only name A5's defaults for reference.

At month-end t (weights applied to sleeve returns labelled t+1): eligible sleeves = those with a return at t;
covariance = the trailing ``cov_months`` sleeve returns ending at t (earlier months only), requiring that many
common observations; shrink ``shrink`` toward the diagonal; nonnegative ERC weights summing to one. Fallback:
normalised 1/sigma from lagged individual vols (>= ``fallback_min_obs`` months, same trailing window); else cash.
Scale k = vol_target / sqrt(12 w'Sw) (S = the shrunk covariance; for the 1/sigma fallback its diagonal), then
capped so that gross = k * sum_s w_s g_s <= gross_cap (g_s = sleeve gross notional/NAV if supplied, else 1).
Excess return = k sum_s w_s r_s + cash/financing adjustment relative to T-bill:
  a = k sum w_s ; a <= 1: (1-a)(c - tb), c = max(0, tb - cash_spread) ; a > 1: -(a-1) financing_spread.
T-bill: annual decimal yield at the previous month-end, /12.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

A5_DEFAULTS = {"cov_months": 60, "shrink": 0.25, "vol_target": 0.10, "gross_cap": 2.0,
               "cash_spread": 0.005, "financing_spread": 0.02, "fallback_min_obs": 12}


def erc_weights(S: np.ndarray, tol: float = 1e-12, max_iter: int = 10_000) -> np.ndarray | None:
    """Nonnegative long-only ERC via cyclical coordinate descent on 0.5 y'Sy - (1/n) sum log y."""
    S = np.asarray(S, float)
    n = S.shape[0]
    if n == 0 or not np.all(np.isfinite(S)) or np.any(np.diag(S) <= 0):
        return None
    try:
        np.linalg.cholesky(S)
    except np.linalg.LinAlgError:
        return None
    b = np.full(n, 1.0 / n)
    y = 1.0 / np.sqrt(np.diag(S))
    for _ in range(max_iter):
        y_old = y.copy()
        for i in range(n):
            a = S[i, i]
            c = S[i] @ y - a * y[i]
            y[i] = (-c + math.sqrt(c * c + 4 * a * b[i])) / (2 * a)
        if np.max(np.abs(y - y_old)) < tol * max(1.0, np.max(np.abs(y))):
            break
    w = y / y.sum()
    rc = w * (S @ w)
    if not np.all(w > 0) or np.max(np.abs(rc / rc.sum() - b)) > 1e-6:
        return None
    return w


def risk_contributions(w, S):
    w = np.asarray(w, float)
    rc = w * (np.asarray(S) @ w)
    return rc / rc.sum()


def build_book(sleeves: pd.DataFrame, tbill_ann: pd.Series, params: dict,
               gross: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """sleeves: month x sleeve net excess returns (PeriodIndex). Returns (book frame, weights frame)."""
    p = {**A5_DEFAULTS, **params}
    months = sleeves.index
    tb = tbill_ann.reindex(months).shift(1) / 12.0
    rows, wrows = [], []
    for j in range(1, len(months)):
        t, h = months[j - 1], months[j]
        hist = sleeves.iloc[max(0, j - p["cov_months"]): j]
        elig = [c for c in sleeves.columns if pd.notna(sleeves.at[t, c])]
        method, w, S = "cash", None, None
        if elig:
            H = hist[elig]
            common = H.dropna()
            if len(common) >= p["cov_months"] and len(elig) >= 1:
                C = common.cov().to_numpy()
                S = (1 - p["shrink"]) * C + p["shrink"] * np.diag(np.diag(C))
                w = erc_weights(S)
                method = "erc" if w is not None else "fallback"
            if w is None:
                sd = H.std(ddof=1)
                cnt = H.count()
                ok = [c for c in elig if cnt[c] >= p["fallback_min_obs"] and sd[c] > 0]
                if ok:
                    inv = 1.0 / sd[ok].to_numpy()
                    w = inv / inv.sum()
                    S = np.diag(sd[ok].to_numpy() ** 2)
                    elig = ok
                    method = "inv_vol"
                else:
                    method, w = "cash", None
        rec = {"month": h, "method": method, "n_sleeves": 0, "k": 0.0, "alloc": 0.0, "gross": 0.0,
               "exante_vol": 0.0, "sleeve_ret": 0.0}
        if w is not None:
            vol = math.sqrt(12 * float(w @ S @ w))
            k = p["vol_target"] / vol if vol > 0 else 0.0
            g = np.ones(len(elig)) if gross is None else gross.reindex(index=[h], columns=elig).fillna(1.0).to_numpy()[0]
            gr = k * float(np.sum(w * g))
            if gr > p["gross_cap"]:
                k *= p["gross_cap"] / gr
                gr = p["gross_cap"]
            r = sleeves.loc[h, elig].to_numpy()
            sret = float(np.nansum(k * w * r))
            rec.update({"n_sleeves": len(elig), "k": k, "alloc": k * float(w.sum()), "gross": gr,
                        "exante_vol": k * vol, "sleeve_ret": sret})
            for c, wi in zip(elig, w):
                wrows.append({"month": str(h), "sleeve": c, "erc_weight": float(wi), "scaled_weight": float(k * wi)})
        tbm = tb.get(h, np.nan)
        a = rec["alloc"]
        if pd.isna(tbm):
            adj = np.nan
        elif a <= 1:
            adj = (1 - a) * (max(0.0, tbm - p["cash_spread"] / 12.0) - tbm)
        else:
            adj = -(a - 1) * p["financing_spread"] / 12.0
        rec["cash_fin_adj"] = adj
        rec["excess"] = rec["sleeve_ret"] + (adj if pd.notna(adj) else 0.0)
        rec["total"] = rec["excess"] + (tbm if pd.notna(tbm) else np.nan)
        rows.append(rec)
    book = pd.DataFrame(rows).set_index("month")
    return book, pd.DataFrame(wrows)


def stationary_block_indices(T: int, n_paths: int, horizon: int, mean_block: float, rng) -> np.ndarray:
    p = 1.0 / mean_block
    idx = np.empty((n_paths, horizon), np.int64)
    idx[:, 0] = rng.integers(0, T, n_paths)
    for h in range(1, horizon):
        new = rng.random(n_paths) < p
        idx[:, h] = np.where(new, rng.integers(0, T, n_paths), (idx[:, h - 1] + 1) % T)
    return idx


def mdd_simulation(X, *, weights=None, n_paths: int = 10_000, horizon: int = 120, mean_block: float = 12,
                   seed: int = 20260925) -> dict:
    """Paired stationary-block resampling of monthly rows (X: T or T x k; with k sleeves, rows are resampled
    jointly -- preserving the sleeve covariance -- and combined with fixed ``weights``)."""
    X = np.asarray(X, float)
    if X.ndim == 2:
        X = X @ np.asarray(weights, float) if weights is not None else X.sum(axis=1)
    X = X[~np.isnan(X)]
    rng = np.random.default_rng(int(seed))
    idx = stationary_block_indices(len(X), n_paths, horizon, mean_block, rng)
    paths = X[idx]
    nav = np.cumprod(1 + paths, axis=1)
    peak = np.maximum.accumulate(np.concatenate([np.ones((n_paths, 1)), nav], axis=1), axis=1)[:, 1:]
    mdd = (nav / peak - 1).min(axis=1)
    return {"n_paths": n_paths, "horizon_months": horizon, "mean_block": mean_block, "seed": seed,
            "mdd_median": float(np.median(mdd)), "mdd_p05": float(np.quantile(mdd, 0.05)),
            "mdd_p95": float(np.quantile(mdd, 0.95))}


def block_bootstrap_mean_lcb(x, *, level: float = 0.75, n_draws: int = 10_000, mean_block: float = 12,
                             seed: int = 20260925) -> float:
    """One-sided `level` lower confidence bound of the mean (stationary block bootstrap percentile)."""
    x = np.asarray(pd.Series(x).dropna(), float)
    rng = np.random.default_rng(int(seed))
    idx = stationary_block_indices(len(x), n_draws, len(x), mean_block, rng)
    return float(np.quantile(x[idx].mean(axis=1), 1 - level))


def leverage_for_target(excess_monthly, tbill_ann_mean: float, *, target_total_ann: float = 0.12,
                        lcb_level: float = 0.75, cash_spread: float = 0.005, financing_spread: float = 0.02,
                        cap: float = 2.0, n_draws: int = 10_000, mean_block: float = 12,
                        seed: int = 20260925) -> dict:
    """A5 §E information-only calc: m = min(post-pub mean excess, its one-sided 75% block LCB) (annualised);
    total(L) = tb + L m + [L<=1: (1-L)(max(0,tb-cash_spread)-tb)] - [L>1: (L-1) financing_spread];
    solve total(L) = target; 'not attainable' if m <= 0 or L > cap."""
    x = np.asarray(pd.Series(excess_monthly).dropna(), float)
    mean = float(x.mean() * 12)
    lcb = block_bootstrap_mean_lcb(x, level=lcb_level, n_draws=n_draws, mean_block=mean_block, seed=seed) * 12
    m = min(mean, lcb)
    out = {"mean_ann": mean, "lcb75_ann": lcb, "conservative_mean_ann": m, "tbill_ann": tbill_ann_mean,
           "target_total_ann": target_total_ann}
    tb = tbill_ann_mean
    c = max(0.0, tb - cash_spread)
    if m <= 0:
        out.update({"leverage": None, "status": "not attainable (conservative mean <= 0)"})
        return out
    # L <= 1 branch: total = L (tb + m) + (1 - L) c
    L1 = (target_total_ann - c) / (tb + m - c) if (tb + m - c) > 0 else math.inf
    if 0 <= L1 <= 1:
        L = L1
    else:
        L = (target_total_ann - tb - financing_spread) / (m - financing_spread) if m > financing_spread else math.inf
        if L < 1:
            L = math.inf
    out["leverage"] = None if not math.isfinite(L) else float(L)
    out["status"] = "attainable" if math.isfinite(L) and L <= cap else "not attainable (leverage > cap)"
    return out
