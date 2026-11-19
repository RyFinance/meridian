"""Independent re-implementation of the six book sleeves + core (weights only; accounting in common.run_book).

Every signal function takes `asof_cut` (a Timestamp or None). When set, all daily/monthly inputs dated after the cut
are replaced by garbage (perturbation) -- used by lookahead.py to prove weights at t <= cut do not move.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import (avg_rank_weights, calendar_monthly, monthly_signal, universe, wide)

BP = {"EQ": 2, "FI": 2, "FX": 3, "CM": 6}
PANEL = {"FI": "eval/panels/daily_excess_FI10.parquet", "CM": "eval/panels/daily_excess_CM.parquet",
         "FX": "eval/panels/daily_excess_FX.parquet"}


def perturb_daily(d: pd.DataFrame, cut, seed=1):
    if cut is None:
        return d
    d = d.copy()
    rng = np.random.default_rng(seed)
    mask = d.index > cut
    d.loc[mask] = d.loc[mask].where(d.loc[mask].isna(), rng.normal(0, 0.05, size=d.loc[mask].shape))
    return d


def perturb_monthly(m: pd.DataFrame, cut, seed=2):
    if cut is None:
        return m
    m = m.copy()
    rng = np.random.default_rng(seed)
    mask = m.index > pd.Period(cut, "M")
    m.loc[mask] = m.loc[mask].where(m.loc[mask].isna(), np.abs(rng.normal(1, 0.5, size=m.loc[mask].shape)) + 0.01)
    return m


def load_daily(cls):
    ids = universe(cls)
    return wide(PANEL[cls], ids).reindex(columns=ids)


# ---------------------------------------------------------------- TSMOM (MOP 2012 / A5-C1)
def ewm_vol(s: pd.Series) -> pd.Series:
    """sigma^2 = 261 * sum_j w_j (r_{d-j} - mu)^2, w_j prop. (1-d) d^j, d = 60/61, normalised over available
    obs (truncate at first obs, renormalise); mu = EW mean with the same weights. Valid obs only."""
    v = s.ewm(com=60, adjust=True).var(bias=True)
    return np.sqrt(261 * v)


def tsmom_weights(cls, asof_cut=None, daily=None):
    d = load_daily(cls) if daily is None else daily
    d = perturb_daily(d, asof_cut)
    mret = calendar_monthly(d)
    per = d.index.to_period("M")
    vol_m, nobs_m = {}, {}
    for c in d.columns:
        s = d[c].dropna()
        v = ewm_vol(s)
        n = pd.Series(np.arange(1, len(s) + 1), index=s.index)
        vol_m[c] = v.groupby(s.index.to_period("M")).last()
        nobs_m[c] = n.groupby(s.index.to_period("M")).last()
    vol_m = pd.DataFrame(vol_m).reindex(columns=d.columns)
    nobs_m = pd.DataFrame(nobs_m).reindex(columns=d.columns)
    months = pd.period_range(per.min(), per.max(), freq="M")
    mret = mret.reindex(months)
    vol_m = vol_m.reindex(months).ffill()   # last valid close <= month-end t
    nobs_m = nobs_m.reindex(months).ffill()
    W = {}
    for t in months:
        win = mret.loc[t - 11:t]
        if len(win) < 12:
            continue
        ok = win.notna().all() & (nobs_m.loc[t] >= 756) & vol_m.loc[t].notna() & (vol_m.loc[t] > 0)
        elig = ok[ok].index
        if len(elig) < 3:
            continue
        cum = (1 + win[elig]).prod() - 1
        sgn = np.sign(cum)
        W[t] = (sgn * 0.40 / vol_m.loc[t, elig]) / len(elig)
    return W, d


# ---------------------------------------------------------------- XSMOM-FX (AMP 2013)
def xsmom_weights(cls, asof_cut=None, daily=None):
    d = load_daily(cls) if daily is None else daily
    d = perturb_daily(d, asof_cut)
    mret = calendar_monthly(d)
    months = pd.period_range(mret.index.min(), mret.index.max(), freq="M")
    mret = mret.reindex(months)
    W = {}
    for t in months:
        win = mret.loc[t - 11:t - 1]
        if len(win) < 11:
            continue
        ok = win.notna().all()
        elig = ok[ok].index
        if len(elig) < 4:
            continue
        sig = (1 + win[elig]).prod() - 1
        W[t] = avg_rank_weights(sig)
    return W, d


# ---------------------------------------------------------------- VAL-FX (AMP 2013 5y PPP)
def val_fx_weights(asof_cut=None, daily=None, cpi_geo=False):
    """cpi_geo=False: log(arith. window-mean CPI) (spec reading, same as spot); True: mean of log CPI (builder)."""
    ids = universe("FX")
    d = load_daily("FX") if daily is None else daily
    d = perturb_daily(d, asof_cut)
    spot = perturb_monthly(monthly_signal("eval/signals/fx_spot_monthly.parquet", ids).reindex(columns=ids), asof_cut, 3)
    cpi = perturb_monthly(monthly_signal("eval/signals/fx_cpi_pit_monthly.parquet", ids).reindex(columns=ids), asof_cut, 4)
    cus = perturb_monthly(monthly_signal("eval/series/cpi_us_pit_monthly.parquet").iloc[:, [0]], asof_cut, 5).iloc[:, 0]
    months = pd.period_range(spot.index.min(), spot.index.max(), freq="M")
    spot, cpi, cus = spot.reindex(months), cpi.reindex(months), cus.reindex(months)
    W = {}
    for t in months:
        lo, hi = t - 66, t - 54
        if lo < months[0]:
            continue
        ws, wc, wu = spot.loc[lo:hi], cpi.loc[lo:hi], cus.loc[lo:hi]
        ok = spot.loc[t].notna() & cpi.loc[t].notna() & ws.notna().all() & wc.notna().all()
        if pd.isna(cus.loc[t]) or wu.isna().any():
            continue
        elig = ok[ok].index
        if len(elig) < 4:
            continue
        if cpi_geo:
            cf, cu = np.log(wc[elig]).mean(), np.log(wu).mean()
        else:
            cf, cu = np.log(wc[elig].mean()), np.log(wu.mean())
        v = (np.log(ws[elig].mean() / spot.loc[t, elig])
             - ((np.log(cpi.loc[t, elig]) - cf) - (np.log(cus.loc[t]) - cu)))
        W[t] = avg_rank_weights(v)
    return W, d


# ---------------------------------------------------------------- CARRY-FX (KMVP 2018 Carry1M)
def carry_fx_weights(asof_cut=None, daily=None):
    ids = universe("FX")
    d = load_daily("FX") if daily is None else daily
    d = perturb_daily(d, asof_cut)
    fr = perturb_monthly(monthly_signal("eval/signals/fx_foreign_rate_monthly.parquet", ids).reindex(columns=ids), asof_cut, 6)
    us = perturb_monthly(monthly_signal("eval/series/usd_rate_3m_monthly.parquet").iloc[:, [0]], asof_cut, 7).iloc[:, 0]
    W = {}
    for t in fr.index:
        if t not in us.index or pd.isna(us.loc[t]):
            continue
        row = fr.loc[t].dropna()
        if len(row) < 4:
            continue
        i = us.loc[t]
        carry = (row - i) / (1 + i)
        W[t] = avg_rank_weights(carry)
    return W, d


# ---------------------------------------------------------------- SEAS-FX (BSV 2021 construction)
def seas_bsv_weights(cls, asof_cut=None, daily=None, years=20, min_years=1, sv_win=36, sv_min=12, fq=0.1,
                     fabs=0.025, target=0.10, cv_win=120, cv_min=12, floor_excl_zero=False):
    d = load_daily(cls) if daily is None else daily
    d = perturb_daily(d, asof_cut)
    mret = calendar_monthly(d)
    months = pd.period_range(mret.index.min(), mret.index.max(), freq="M")
    mret = mret.reindex(months)
    unscaled = {}
    unscaled_ret = {}   # realised gross month return of the unscaled book, keyed by holding month
    W = {}
    for t in months:
        # signal: same calendar month as holding month t+1 over prior 20 years: months t+1-12k, k=1..20
        same = [t + 1 - 12 * k for k in range(1, years + 1)]
        same = [m for m in same if m >= months[0]]
        if not same:
            continue
        sm = mret.loc[same]
        cnt = sm.notna().sum()
        sig = sm.mean()
        # sizing vol: trailing 36 monthly returns t-35..t, >=12
        sw = mret.loc[t - (sv_win - 1):t]
        sv = sw.std(ddof=1) * np.sqrt(12)
        svn = sw.notna().sum()
        ok = (cnt >= min_years) & (svn >= sv_min) & sv.notna()
        elig = ok[ok].index
        if len(elig) < 4:
            continue
        rw = avg_rank_weights(sig[elig])
        s = sv[elig]
        sq = s[rw != 0] if floor_excl_zero else s   # builder convention: zero-rank (median) asset excluded
        floor = max(float(sq.quantile(fq)), fabs)
        u = rw / s.clip(lower=floor)
        unscaled[t] = u
        h = t + 1
        if h in mret.index:
            unscaled_ret[h] = float((u * mret.loc[h, u.index].fillna(0)).sum())
        # class vol target from unscaled strategy's own realised returns through t
        past = pd.Series({m: r for m, r in unscaled_ret.items() if m <= t and m > t - cv_win})
        if len(past) < cv_min:
            continue
        cv = past.std(ddof=1) * np.sqrt(12)
        if not np.isfinite(cv) or cv <= 0:
            continue
        W[t] = u * (target / cv)
    return W, d


# ---------------------------------------------------------------- CORE 60/40
def core_weights(asof_cut=None):
    d = wide("eval/series/core_etf_excess_daily.parquet", ["SPY", "IEF"])[["SPY", "IEF"]]
    d = perturb_daily(d, asof_cut)
    months = sorted(set(d.dropna().index.to_period("M")))
    # signal month-end t = every month in which both ETFs are priced (first: 2002-07, IEF from 2002-07-31);
    # held t+1 (net: first trading day t+1 -> first trading day t+2), same as component convention.
    W = {m: pd.Series({"SPY": 0.6, "IEF": 0.4}) for m in months}
    return W, d
