"""Signals and month-end weight builders. Every paper number arrives through arguments (the spec's params dict);
nothing here hard-codes a lookback, target or shrink value.

All inputs are monthly wide panels (PeriodIndex x market_id) aligned to the same months/columns, except BAB's
daily inputs. A weight row indexed t is formed with information through the month-end close of t and is
expressed per unit of NAV (the portfolio return is sum_i w_i r_i).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ------------------------------------------------------------------------------------------------ helpers
def _zero_undefined(W: pd.DataFrame, defined: pd.Series) -> pd.DataFrame:
    W = W.fillna(0.0)
    W.loc[~defined.reindex(W.index, fill_value=False)] = 0.0
    return W


def cumulative_log(mret: pd.DataFrame, length: int, skip: int = 0) -> pd.DataFrame:
    """Sum of log(1+r) over months t-skip-length+1 .. t-skip; NaN unless all `length` months are present."""
    lr = np.log1p(mret)
    s = lr.rolling(int(length), min_periods=int(length)).sum()
    return s.shift(int(skip)) if skip else s


# ------------------------------------------------------------------------------------------------ TSMOM
def tsmom_weights(mret: pd.DataFrame, vol_me: pd.DataFrame, *, lookback_months: int, target_vol: float,
                  min_assets: int, force_long: bool = False):
    """MOP: sign of trailing `lookback_months` cumulative excess return (months t-L+1..t incl. t), position
    sign x target_vol / sigma_t, equal average over eligible instruments (exact zero sign: flat but counted).
    force_long=True gives the always-long control (same instruments, same scaling).
    Returns (W, eligible mask, n_eligible)."""
    cum = cumulative_log(mret, lookback_months)
    sig = np.sign(cum)
    if force_long:
        sig = sig.where(sig.isna(), 1.0)
    vol = vol_me.reindex(index=mret.index, columns=mret.columns)
    elig = sig.notna() & vol.notna() & (vol > 0)
    n = elig.sum(axis=1)
    pos = (sig * target_vol / vol).where(elig)
    W = pos.div(n.where(n > 0), axis=0)
    return _zero_undefined(W, n >= min_assets), elig, n


# ------------------------------------------------------------------------------------------------ ranks
def xs_rank_weights(signal: pd.DataFrame, *, min_assets: int, vol: pd.DataFrame | None = None,
                    eligible: pd.DataFrame | None = None):
    """KMVP/AMP rank weights w = z [rank - (N+1)/2]; longs sum to +1, shorts to -1 (ties: average rank).
    Optional per-asset vol scaling: c_i / sigma_i, then each leg renormalised to +-1.
    Returns (W, eligible mask, n_eligible)."""
    elig = signal.notna() if eligible is None else (eligible & signal.notna())
    if vol is not None:
        vol = vol.reindex(index=signal.index, columns=signal.columns)
        elig = elig & vol.notna() & (vol > 0)
    s = signal.where(elig)
    n = elig.sum(axis=1)
    c = s.rank(axis=1, method="average").sub((n + 1) / 2.0, axis=0)
    if vol is not None:
        c = c / vol
    pos = c.clip(lower=0)
    neg = (-c).clip(lower=0)
    ps, ns = pos.sum(axis=1), neg.sum(axis=1)
    W = pos.div(ps.where(ps > 0), axis=0) - neg.div(ns.where(ns > 0), axis=0)
    defined = (n >= min_assets) & (ps > 0) & (ns > 0)
    return _zero_undefined(W, defined), elig, n


# ------------------------------------------------------------------------------------------------ signals
def momentum_signal(mret: pd.DataFrame, *, lookback_months: int, skip_months: int) -> pd.DataFrame:
    """AMP: cumulative return over the past `lookback_months` skipping the most recent `skip_months`
    (12/1 -> months t-11..t-1)."""
    return cumulative_log(mret, lookback_months - skip_months, skip_months)


def _window_mean(x: pd.DataFrame, lo: int, hi: int) -> pd.DataFrame:
    """Mean of x over months t-hi .. t-lo (all present)."""
    lo, hi = int(lo), int(hi)
    return x.shift(lo).rolling(hi - lo + 1, min_periods=hi - lo + 1).mean()


def value_reversal(level: pd.DataFrame, *, window_lo_months: int, window_hi_months: int) -> pd.DataFrame:
    """AMP 5-year reversal: log(average level over months t-hi..t-lo / level_t) (54/66 = 4.5-5.5 years)."""
    return np.log(_window_mean(level, window_lo_months, window_hi_months) / level)


def level_from_returns(mret: pd.DataFrame) -> pd.DataFrame:
    """Cumulative excess-return index (NaN months carry the level; NaN before the first observation)."""
    lvl = np.exp(np.log1p(mret.fillna(0.0)).cumsum())
    started = mret.notna().cummax()
    return lvl.where(started)


def fx_ppp_value(spot: pd.DataFrame, cpi: pd.DataFrame, cpi_us: pd.Series, *, window_lo_months: int,
                 window_hi_months: int, cpi_lag_months: int) -> pd.DataFrame:
    """AMP FX value: log(avg spot 4.5-5.5y ago / spot now) - [dlog CPI_foreign - dlog CPI_US] over the same
    period, i.e. minus the real appreciation. Spot = USD per unit of foreign currency. CPI panels are lagged by
    `cpi_lag_months` (publication) before use."""
    lo, hi = window_lo_months, window_hi_months
    c = np.log(cpi.shift(cpi_lag_months))
    cu = np.log(cpi_us.shift(cpi_lag_months))
    nominal = np.log(_window_mean(spot, lo, hi) / spot)
    dcf = c - _window_mean(c, lo, hi)
    cu_df = pd.DataFrame({k: cu for k in spot.columns}, index=spot.index)
    dcu = cu_df - _window_mean(cu_df, lo, hi)
    return nominal - (dcf - dcu)


def bond_value(yld: pd.DataFrame, *, kind: str, window_lo_months: int | None = None,
               window_hi_months: int | None = None, inflation: pd.DataFrame | None = None) -> pd.DataFrame:
    """kind='yield_change': y_t - mean(y over months t-hi..t-lo) (5-year change; higher = cheaper);
    kind='real_yield': y_t - inflation_t (inflation panel given, already point-in-time)."""
    if kind == "yield_change":
        return yld - _window_mean(yld, window_lo_months, window_hi_months)
    if kind == "real_yield":
        return yld - inflation
    raise ValueError(f"unknown bond value kind {kind}")


def fx_carry(foreign_rate: pd.DataFrame, us_rate: pd.Series) -> pd.DataFrame:
    """KMVP FX carry (S-F)/F = (i* - i)/(1 + i) (annual rates, decimals)."""
    return foreign_rate.sub(us_rate, axis=0).div(1.0 + us_rate, axis=0)


def bond_carry(yld: pd.DataFrame, short_rate: pd.DataFrame, rolldown: pd.DataFrame | None = None) -> pd.DataFrame:
    """KMVP bond carry: term spread y - r_f plus roll-down if supplied."""
    c = yld - short_rate
    return c + rolldown if rolldown is not None else c


def commodity_carry(f_near: pd.DataFrame, f_far: pd.DataFrame, months_apart: pd.DataFrame | float) -> pd.DataFrame:
    """KMVP commodity carry from two contracts: (F_near - F_far) / F_far, annualised by 12/months_apart."""
    return (f_near / f_far - 1.0) * (12.0 / months_apart)


def seasonality_signal(mret: pd.DataFrame, *, years: int, min_years: int) -> pd.DataFrame:
    """Signal at t for month t+1: mean of the same-calendar-month returns r_{t+1-12k}, k=1..years, needing
    >= min_years observations. Only data through t is used."""
    acc = None
    cnt = None
    for k in range(1, int(years) + 1):
        lag = mret.shift(12 * k - 1)
        acc = lag.fillna(0.0) if acc is None else acc + lag.fillna(0.0)
        cnt = lag.notna().astype(int) if cnt is None else cnt + lag.notna().astype(int)
    return (acc / cnt).where(cnt >= int(min_years))


def permute_month_labels(mret: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Calendar-shuffle placebo: within each calendar year the 12 month-of-year labels are permuted (one
    permutation per year, shared by all instruments), i.e. R'[y, m] = R[y, pi_y(m)]."""
    idx = mret.index
    out = mret.copy()
    vals = mret.to_numpy()
    years = idx.year
    months = idx.month
    newv = np.full_like(vals, np.nan)
    for y in np.unique(years):
        rows = np.where(years == y)[0]
        pos = {m: r for m, r in zip(months[rows], rows)}
        perm = rng.permutation(12) + 1
        for m, r in pos.items():
            src = pos.get(int(perm[m - 1]))
            if src is not None:
                newv[r] = vals[src]
    out.iloc[:, :] = newv
    return out


# ------------------------------------------------------------------------------------------------ BAB
def fp_betas(daily: pd.DataFrame, bench: pd.Series, *, vol_window_days: int, vol_min_days: int,
             corr_window_days: int, corr_min_days: int, overlap_days: int, shrink_w: float) -> pd.DataFrame:
    """Frazzini-Pedersen: beta = rho * sigma_i / sigma_m; sigma from `vol_window_days` of daily log returns,
    rho from `corr_window_days` of `overlap_days`-day overlapping log returns; shrunk w*beta + (1-w)*1.
    Returned daily (information through each date)."""
    b = bench.reindex(daily.index)
    lr, lb = np.log1p(daily), np.log1p(b)
    sd_i = lr.rolling(vol_window_days, min_periods=vol_min_days).std()
    sd_m = lb.rolling(vol_window_days, min_periods=vol_min_days).std()
    r3 = lr.rolling(overlap_days, min_periods=overlap_days).sum()
    b3 = lb.rolling(overlap_days, min_periods=overlap_days).sum()
    rho = r3.rolling(corr_window_days, min_periods=corr_min_days).corr(b3)
    beta = rho * sd_i.div(sd_m, axis=0)
    return shrink_w * beta + (1.0 - shrink_w)


def bab_weights(beta_me: pd.DataFrame, *, min_assets: int, signal: pd.DataFrame | None = None):
    """FP BAB: rank on beta (or on `signal` for placebos, with the same eligibility), z = rank,
    w_H = k (z - zbar)^+, w_L = k (z - zbar)^-, k = 2 / sum|z - zbar| (each leg sums to 1); each leg levered to
    beta one: W = w_L / beta_L - w_H / beta_H. Returns (W, eligible, n)."""
    elig = beta_me.notna() & (beta_me > 0)
    sig = beta_me if signal is None else signal
    elig = elig & sig.notna()
    s = sig.where(elig)
    n = elig.sum(axis=1)
    c = s.rank(axis=1, method="average").sub((n + 1) / 2.0, axis=0)
    k = 2.0 / c.abs().sum(axis=1)
    wH = c.clip(lower=0).mul(k, axis=0)
    wL = (-c).clip(lower=0).mul(k, axis=0)
    bH = (wH * beta_me).sum(axis=1)
    bL = (wL * beta_me).sum(axis=1)
    W = wL.div(bL.where(bL > 0), axis=0) - wH.div(bH.where(bH > 0), axis=0)
    defined = (n >= min_assets) & (bL > 0) & (bH > 0)
    return _zero_undefined(W, defined), elig, n


# ------------------------------------------------------------------------------------------------ BSV sizing
def rolling_vol_monthly(mret: pd.DataFrame, *, window_months: int, min_months: int) -> pd.DataFrame:
    """Simple (equal-weight) rolling vol of monthly returns over months t-window+1..t, annualised by sqrt(12)."""
    return mret.rolling(int(window_months), min_periods=int(min_months)).std() * np.sqrt(12.0)


def vol_size(W: pd.DataFrame, vol: pd.DataFrame, *, floor_quantile: float | None = None,
             floor_abs: float | None = None) -> pd.DataFrame:
    """BSV position sizing: w_i / max(sigma_i, floor_t); floor_t = max(cross-sectional `floor_quantile` of the
    eligible vols at t, floor_abs) (each optional)."""
    v = vol.reindex(index=W.index, columns=W.columns).where(W != 0)
    floor = pd.Series(0.0, index=W.index)
    if floor_quantile is not None:
        floor = np.maximum(floor, v.quantile(float(floor_quantile), axis=1).fillna(0.0))
    if floor_abs is not None:
        floor = np.maximum(floor, float(floor_abs))
    vf = v.clip(lower=floor, axis=0)
    return (W / vf).where(W != 0, 0.0).fillna(0.0)


def rolling_cov_cube(mret: pd.DataFrame, *, window_months: int, min_months: int) -> np.ndarray:
    """(T, N, N) pairwise-complete covariance of monthly returns over months t-window+1..t (NaN -> 0)."""
    T, N = mret.shape
    out = np.zeros((T, N, N))
    for j in range(T):
        win = mret.iloc[max(0, j - int(window_months) + 1): j + 1]
        if len(win) >= int(min_months):
            out[j] = np.nan_to_num(win.cov(min_periods=int(min_months)).to_numpy())
    return out


def class_vol_target(W: pd.DataFrame, mret: pd.DataFrame, *, target_vol: float, window_months: int,
                     min_months: int, method: str, cov_cube: np.ndarray | None = None):
    """BSV class vol target: scale_t = target_vol / sigma_hat_t with past data only.
    method 'ex_ante_cov': sigma_hat_t = sqrt(12 W_t' S_t W_t), S_t = trailing `window_months` covariance;
    method 'strategy_realised': sigma_hat_t = sqrt(12) sd of the unscaled strategy's own past monthly returns
    (sum_i W_{s-1,i} R_{s,i}, s <= t) over the trailing window. Returns (scaled W, scale Series; NaN = undefined)."""
    Wa = W.reindex(index=mret.index, columns=mret.columns).fillna(0.0)
    if method == "ex_ante_cov":
        if cov_cube is None:
            cov_cube = rolling_cov_cube(mret, window_months=window_months, min_months=min_months)
        w = Wa.to_numpy()
        var = np.einsum("ti,tij,tj->t", w, cov_cube, w) * 12.0
        sig = pd.Series(np.sqrt(np.where(var > 0, var, np.nan)), index=Wa.index)
        have = mret.notna().rolling(int(window_months), min_periods=1).sum().max(axis=1) >= int(min_months)
        sig = sig.where(have)
    elif method == "strategy_realised":
        r = (Wa.shift(1) * mret.fillna(0.0)).sum(axis=1).where(Wa.shift(1).abs().sum(axis=1) > 0)
        sig = r.rolling(int(window_months), min_periods=int(min_months)).std() * np.sqrt(12.0)
    else:
        raise ValueError(f"unknown class vol method {method}")
    scale = (float(target_vol) / sig).where(sig > 0)
    return Wa.mul(scale.fillna(0.0), axis=0), scale


# ------------------------------------------------------------------------------------------------ FP monthly
def fp_betas_monthly(mret: pd.DataFrame, bench: pd.Series, *, vol_window_months: int, vol_min_months: int,
                     corr_window_months: int, corr_min_months: int, overlap_months: int, shrink_w: float,
                     log_returns: bool = True) -> pd.DataFrame:
    """FP monthly-data fallback (Treasuries, Table VI): beta = rho sigma_i / sigma_m with rolling
    `vol_window_months` vols and `corr_window_months` correlation of `overlap_months`-month returns, minimum
    observations as given; shrunk w*beta + (1-w)*1. Indexed by month-end t (information through t)."""
    b = bench.reindex(mret.index)
    lr = np.log1p(mret) if log_returns else mret
    lb = np.log1p(b) if log_returns else b
    sd_i = lr.rolling(vol_window_months, min_periods=vol_min_months).std()
    sd_m = lb.rolling(vol_window_months, min_periods=vol_min_months).std()
    if overlap_months > 1:
        lr = lr.rolling(overlap_months, min_periods=overlap_months).sum()
        lb = lb.rolling(overlap_months, min_periods=overlap_months).sum()
    rho = lr.rolling(corr_window_months, min_periods=corr_min_months).corr(lb)
    beta = rho * sd_i.div(sd_m, axis=0)
    return shrink_w * beta + (1.0 - shrink_w)
