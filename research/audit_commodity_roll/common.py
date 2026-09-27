"""Adversarial audit of commodity_roll (A1). DEV-ONLY loaders: every series is truncated at 2016-12-30
immediately after loading, and every loader asserts it. Independent of research/commodity_roll/core.py.
"""
from __future__ import annotations

import io
import json
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "audit_commodity_roll"
CACHE = OUT / "raw"
DEV0, DEV1 = "2006-07-21", "2016-12-30"
CUT = pd.Timestamp(DEV1)
PAIRS = {"crude": ("USL", "USO"), "natgas": ("UNL", "UNG"), "broad": ("DBC", "GSG")}
SIX = ["USL", "USO", "UNL", "UNG", "DBC", "GSG"]


def _cut(x):
    x = x.loc[:CUT]
    assert x.index.max() <= CUT, "LOCKED WINDOW LEAK"
    return x


def proj_close(t: str) -> pd.Series:
    """Project parquet close (yfinance auto_adjust=True), truncated at 2016-12-30 right after load."""
    for d in (ROOT / "data" / "commodity_roll", ROOT / "data" / "multiasset" / "etf"):
        p = d / f"{t}.parquet"
        if p.exists():
            x = pd.read_parquet(p)
            x["date"] = pd.to_datetime(x["date"])
            x = x[x["date"] <= CUT]                      # truncate immediately
            return _cut(x.set_index("date")["close"].sort_index().astype(float))
    raise FileNotFoundError(t)


def yf_raw(t: str) -> pd.DataFrame:
    """yfinance unadjusted OHLCV + actions, requested only up to 2016-12-30 (end exclusive 2016-12-31)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"yf_{t}.csv"
    if f.exists():
        x = pd.read_csv(f, index_col=0, parse_dates=True)
        return _cut(x)
    import yfinance as yf
    h = yf.Ticker(t).history(start="2006-01-01", end="2016-12-31", auto_adjust=False, actions=True)
    h.index = pd.to_datetime(h.index).tz_localize(None).normalize()
    h = _cut(h)
    h.to_csv(f)
    return h


def fred(sid: str) -> pd.Series:
    """FRED series requested with coed=2016-12-30 so nothing later is ever downloaded."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"fred_{sid}.csv"
    if not f.exists():
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd=2005-01-01&coed=2016-12-30"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        txt = urllib.request.urlopen(req, timeout=60).read().decode()
        f.write_text(txt)
    x = pd.read_csv(f)
    x.columns = ["date", "v"]
    x["date"] = pd.to_datetime(x["date"])
    x["v"] = pd.to_numeric(x["v"], errors="coerce")
    return _cut(x.set_index("date")["v"].dropna().sort_index())


def first_session_flags(idx: pd.DatetimeIndex) -> np.ndarray:
    per = idx.to_period("M")
    return np.r_[True, per[1:] != per[:-1]]


def pair(long_px: pd.Series, short_px: pd.Series, cost: float = 0.0, borrow: float = 0.0,
         hedge: float | None = None) -> pd.Series:
    """Own implementation: +1 long / -h short reset at each month's first session close, drift in between.
    hedge=None -> h=1 (registered dollar-neutral). Returns are on capital 1 (the long notional)."""
    j = pd.concat([long_px, short_px], axis=1, keys=["l", "s"]).dropna()
    r = j.pct_change()
    idx = j.index
    fs = first_session_flags(idx)
    h = 1.0 if hedge is None else hedge
    L = S = np.nan
    out = np.full(len(idx), np.nan)
    prev = idx[0]
    for i, d in enumerate(idx):
        if not np.isnan(L):
            rl, rs = r["l"].iat[i], r["s"].iat[i]
            dd = (d - prev).days
            pnl = L * rl - S * rs - S * borrow * dd / 365.0
            L *= 1 + rl
            S *= 1 + rs
            out[i] = pnl
        if fs[i] or np.isnan(L):
            tgtL, tgtS = 1.0, h
            if not np.isnan(L):
                out[i] -= cost * (abs(tgtL - L) + abs(tgtS - S))
            L, S = tgtL, tgtS
        prev = d
    return pd.Series(out, index=idx).dropna()


def book(parts: dict[str, pd.Series], w=(DEV0, DEV1)) -> pd.Series:
    P = pd.DataFrame(parts).loc[w[0]:w[1]]
    return P.mean(axis=1, skipna=True).dropna()


def sharpe(x, ann=252):
    x = pd.Series(x).dropna()
    s = x.std(ddof=1)
    return float(x.mean() / s * np.sqrt(ann)) if s > 0 else float("nan")


def nw_ols(y, X, lags=None, names=None):
    """OLS with Newey-West HAC; returns dict of coef/t. X excludes the constant."""
    import statsmodels.api as sm
    df = pd.concat([pd.Series(y, name="y"), pd.DataFrame(X)], axis=1).dropna()
    yy = df.iloc[:, 0]
    XX = sm.add_constant(df.iloc[:, 1:])
    n = len(df)
    if lags is None:
        lags = int(np.floor(4 * (n / 100) ** (2 / 9)))
    m = sm.OLS(yy, XX).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    out = {"n": n, "lags": lags, "r2": float(m.rsquared)}
    for k in m.params.index:
        out[str(k)] = {"coef": float(m.params[k]), "t": float(m.tvalues[k])}
    out["resid"] = m.resid
    return out


def strip(d):
    return {k: v for k, v in d.items() if k != "resid"}


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o)))
