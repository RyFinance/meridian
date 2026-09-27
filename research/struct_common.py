"""Shared helpers for the 2026-09-23 structural/market-structure experiments (commodity_roll, mbs_convexity,
sector_month_end, fx_hedge_rebal). New module; does not alter any registered code."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "research" / "preregistrations.jsonl"


def registered(path: str) -> bool:
    f = ROOT / path
    if not f.exists():
        return False
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    return any(json.loads(l).get("file") == path and json.loads(l).get("sha256") == h for l in PREREG.read_text().splitlines())


def etf(t: str) -> pd.Series:
    for d in (ROOT / "data" / "commodity_roll", ROOT / "data" / "multiasset" / "etf"):
        p = d / f"{t}.parquet"
        if p.exists():
            x = pd.read_parquet(p)
            return x.set_index(pd.to_datetime(x["date"]))["close"].sort_index()
    raise FileNotFoundError(t)


def sharpe(x: pd.Series, ann: float = 252) -> float:
    s = x.std(ddof=1)
    return float(x.mean() / s * np.sqrt(ann)) if s > 0 else float("nan")


def centred_block_p(x: np.ndarray, block: int = 21, draws: int = 5000, seed: int = 20260923) -> float:
    """One-sided p for mean <= 0: circular block bootstrap of the mean-centred series."""
    x = np.asarray(x, float)
    n, cx = len(x), x - x.mean()
    rng = np.random.default_rng(seed)
    idx = (rng.integers(0, n, size=(draws, -(-n // block)))[:, :, None] + np.arange(block)).reshape(draws, -1)[:, :n] % n
    return float((np.sum(cx[idx].mean(axis=1) >= x.mean()) + 1) / (draws + 1))


def null_pass_rate(x: np.ndarray, x_stress: np.ndarray, gate: float, alpha: float, block: int = 21, draws: int = 1000,
                   seed: int = 20260923, ann: float = 252) -> float:
    """P(full gate pass | zero-mean world): resample mean-centred base/stress series jointly, apply the gate."""
    x, xs = np.asarray(x, float), np.asarray(x_stress, float)
    n = len(x)
    c, cs = x - x.mean(), xs - x.mean()           # keep the stress-vs-base cost difference
    rng = np.random.default_rng(seed + 1)
    passes = 0
    for _ in range(draws):
        idx = (rng.integers(0, n, size=-(-n // block))[:, None] + np.arange(block)).ravel()[:n] % n
        b, s = c[idx], cs[idx]
        sr = b.mean() / b.std(ddof=1) * np.sqrt(ann) if b.std() > 0 else 0
        if sr >= gate and s.mean() > 0 and centred_block_p(b, block, 200, seed) < alpha:
            passes += 1
    return passes / draws


def monthly_hedge(y: pd.Series, xs: pd.DataFrame, sess: pd.DatetimeIndex, lookback: int = 252) -> pd.DataFrame:
    """Point-in-time no-intercept OLS hedge set at each month's first session using returns up to t-1, clipped [0,2]."""
    ry, rx = y.pct_change(), xs.pct_change()
    first = pd.Series(sess, index=sess).groupby(sess.to_period("M")).min()
    H = pd.DataFrame(np.nan, index=sess, columns=xs.columns)
    for t in first:
        i = sess.get_loc(t)
        if i < lookback + 1:
            continue
        w = slice(sess[i - lookback], sess[i - 1])
        Y, X = ry.loc[w].to_numpy(), rx.loc[w].to_numpy()
        ok = np.isfinite(Y) & np.isfinite(X).all(axis=1)
        if ok.sum() < 200:
            continue
        b = np.linalg.lstsq(X[ok], Y[ok], rcond=None)[0]
        H.loc[t] = np.clip(b, 0, 2)
    return H.ffill()
