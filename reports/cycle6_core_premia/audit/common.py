"""Hostile-audit helpers (independent of research/cycle6/engine book/portfolio code).

Book rule re-implemented from A5 §E text: trailing 60 months of sleeve returns (earlier months only), 25% shrink to
diagonal, long-only equal-risk-contribution weights, fallback 1/sigma (>=12 obs), scale to 10% ex-ante vol, 2x gross
notional cap (sleeve gross exposure x weight), cash earns max(0, tbill - 0.5pp), financed exposure pays tbill + 2pp.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
COMP = REPO / "reports/cycle6_core_premia/components"
BOOKDIR = REPO / "reports/cycle6_core_premia/book"
VIEW = REPO / "data/cycle6/snapshot_store/versions/cycle6_eval_v1/view/eval"
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

SLEEVES = ["TSMOM-FI", "TSMOM-CM", "XSMOM-FX", "VAL-FX", "CARRY-FX", "SEAS-FX"]
ALL20 = ("TSMOM-EQ TSMOM-FI TSMOM-FX TSMOM-CM XSMOM-EQ XSMOM-FI XSMOM-FX XSMOM-CM VAL-EQ VAL-FI VAL-FX VAL-CM "
         "CARRY-FI CARRY-FX BAB-EQ BAB-FI SEAS-EQ SEAS-FI SEAS-FX SEAS-CM").split()
ASSET = {"TSMOM-FI": "FI", "TSMOM-CM": "CM", "XSMOM-FX": "FX", "VAL-FX": "FX", "CARRY-FX": "FX", "SEAS-FX": "FX",
         "CORE": "EQ/FI core"}
CUTOFF = {"TSMOM-FI": "2011-01", "TSMOM-CM": "2011-01", "XSMOM-FX": "2009-04", "VAL-FX": "2009-04",
          "CARRY-FX": "2013-09", "SEAS-FX": "2019-02"}
POST = "2019-02"
P = dict(cov_months=60, shrink=0.25, vol_target=0.10, gross_cap=2.0, cash_spread=0.005, fin_spread=0.02,
         fallback_min_obs=12)


def pidx(s):
    s.index = pd.PeriodIndex(s.index.astype(str), freq="M")
    return s


def load_component(cid: str) -> pd.DataFrame:
    return pidx(pd.read_csv(COMP / cid / "net.csv", index_col=0))


def _daily_long(path, ids=None):
    d = pd.read_parquet(path)
    if ids is not None:
        d = d[d.market_id.isin(ids)]
    w = d.pivot(index="date", columns="market_id", values="value")
    w.index = pd.to_datetime(w.index)
    return w.sort_index()


def core_etf_daily():
    return _daily_long(VIEW / "series/core_etf_excess_daily.parquet")


def monthly_from_daily(w: pd.DataFrame) -> pd.DataFrame:
    """Calendar-month compounded excess returns (month-end to month-end)."""
    m = (1 + w.fillna(0)).groupby(w.index.to_period("M")).prod() - 1
    cnt = w.notna().groupby(w.index.to_period("M")).sum()
    return m.where(cnt > 0)


def lagged_period_returns(w: pd.DataFrame) -> pd.DataFrame:
    """Independent one-session-lag holding returns: month m = close of first session of m -> close of first session
    of m+1 (per instrument)."""
    out = {}
    for c in w.columns:
        s = w[c].dropna()
        lvl = (1 + s).cumprod()
        firsts = lvl.groupby(lvl.index.to_period("M")).head(1)
        r = firsts.shift(-1) / firsts - 1
        r.index = r.index.to_period("M")
        out[c] = r
    return pd.DataFrame(out)


def tbill_monthly():
    t = _daily_long(VIEW / "series/tbill_3m_daily.parquet")["TB3M"]   # already decimal (e.g. 0.0419)
    return t.groupby(t.index.to_period("M")).last()   # annualised, month-end value


def erc(S, tol=1e-12, it=20000):
    """Long-only ERC by cyclical coordinate descent (Griveau-Billion et al. 2013), sum w = 1."""
    n = S.shape[0]
    x = 1.0 / np.sqrt(np.diag(S))
    for _ in range(it):
        x_old = x.copy()
        for i in range(n):
            a = S[i, i]
            b = S[i] @ x - a * x[i]
            x[i] = (-b + math.sqrt(b * b + 4 * a * (1.0 / n))) / (2 * a)
        if np.max(np.abs(x - x_old)) < tol:
            break
    return x / x.sum()


def build_book(R: pd.DataFrame, G: pd.DataFrame | None, tb_ann: pd.Series, p=P, weights_out=False,
               include_from: dict | None = None):
    """R: month x sleeve net excess returns; G: sleeve gross notional per unit (held month); tb_ann: annual rate at
    month end. include_from: {sleeve: 'YYYY-MM'} -> sleeve only held from that month (still used in covariance)."""
    months = R.index
    rows, W = [], {}
    for j in range(1, len(months)):
        t, h = months[j - 1], months[j]
        hist = R.iloc[max(0, j - p["cov_months"]): j]
        elig = [c for c in R.columns if pd.notna(R.at[t, c])]
        if include_from:
            elig = [c for c in elig if c not in include_from or h >= pd.Period(include_from[c], "M")]
        method, w, S = "cash", None, None
        if elig:
            H = hist[elig]
            cm = H.dropna()
            if len(cm) >= p["cov_months"]:
                C = cm.cov().to_numpy()
                S = (1 - p["shrink"]) * C + p["shrink"] * np.diag(np.diag(C))
                w, method = erc(S), "erc"
            else:
                sd, cnt = H.std(ddof=1), H.count()
                ok = [c for c in elig if cnt[c] >= p["fallback_min_obs"] and sd[c] > 0]
                if ok:
                    w = (1 / sd[ok].to_numpy()); w = w / w.sum()
                    S = np.diag(sd[ok].to_numpy() ** 2); elig = ok; method = "inv_vol"
        k = alloc = gross = exante = 0.0
        ret = 0.0
        if w is not None:
            vol = math.sqrt(12 * float(w @ S @ w))
            k = p["vol_target"] / vol
            g = np.ones(len(elig)) if G is None else G.reindex(index=[h], columns=elig).fillna(1.0).to_numpy()[0]
            gross = k * float(np.sum(w * g))
            if gross > p["gross_cap"]:
                k *= p["gross_cap"] / gross; gross = p["gross_cap"]
            ret = float(np.nansum(k * w * R.loc[h, elig].to_numpy()))
            alloc = k * float(w.sum())
            W[h] = pd.Series(k * w, index=elig)
            exante = k * vol
        tbm = tb_ann.get(t, np.nan) / 12.0
        if alloc <= 1:
            adj = (1 - alloc) * (max(0.0, tbm - p["cash_spread"] / 12) - tbm)
        else:
            adj = -(alloc - 1) * p["fin_spread"] / 12
        rows.append(dict(month=h, method=method, k=k, alloc=alloc, gross=gross, exante=exante, sleeve_ret=ret,
                         cash_adj=adj, excess=ret + (adj if pd.notna(adj) else 0.0), tb=tbm))
    b = pd.DataFrame(rows).set_index("month")
    b = b[b.index >= b.index[b.method != "cash"].min()]
    return (b, pd.DataFrame(W).T) if weights_out else b


def sleeves_and_gross(ids=SLEEVES, with_core=True, cost_mult=1.0):
    R, G = {}, {}
    for c in ids:
        d = load_component(c)
        R[c] = d["ret_before_cost"] - cost_mult * d["cost"]
        G[c] = d["gross_exposure"]
    R, G = pd.DataFrame(R), pd.DataFrame(G)
    if with_core:
        bk = pidx(pd.read_csv(BOOKDIR / "sleeves.csv", index_col=0))
        R["CORE"] = bk["CORE"]
        G["CORE"] = 1.0
    idx = pd.period_range(R.index.min(), R.index.max(), freq="M")
    return R.reindex(idx), G.reindex(idx)


def stats(x):
    x = pd.Series(x).dropna()
    m, s = x.mean() * 12, x.std(ddof=1) * math.sqrt(12)
    nav = (1 + x).cumprod()
    return dict(n=len(x), first=str(x.index.min()), mean_ann=m, vol_ann=s, sharpe=m / s if s > 0 else np.nan,
                mdd=float((nav / nav.cummax() - 1).min()))


def calib_p(x, crash=False, bw=0.10, B=9999, seed=1):
    from research.amendment4 import calib
    kw = dict(B=B, seed=seed, full=True, bandwidth_fraction=bw)
    if crash:
        kw["crash"] = (0.2 / 12, -6.0)
    return float(calib.calibrated_pvalues(np.asarray(x, float)[None, :], **kw)["p"][0])


def calib_ci(x, level=0.90, seed=1):
    from research.amendment4 import ci
    r = ci.calibrated_ci(np.asarray(x, float), level=level, seed=seed)
    return r["sharpe_ann"]


def ols_hac(y, X, L=None):
    """OLS with intercept and Newey-West (Bartlett) HAC standard errors. Returns params, t, R2."""
    y = np.asarray(y, float); X = np.column_stack([np.ones(len(y)), np.asarray(X, float)])
    n, k = X.shape
    if L is None:
        L = int(np.floor(4 * (n / 100) ** (2 / 9)))
    XtXi = np.linalg.inv(X.T @ X); b = XtXi @ X.T @ y; e = y - X @ b
    U = X * e[:, None]; S = U.T @ U
    for l in range(1, L + 1):
        G = U[l:].T @ U[:-l]; S += (1 - l / (L + 1)) * (G + G.T)
    V = XtXi @ S @ XtXi
    r2 = 1 - e.var() / y.var()
    return b, b / np.sqrt(np.diag(V)), r2
