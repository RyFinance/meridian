"""Promotion guards for candidate strategies (Workstream C2, edge certification).

Pure functions on pandas/numpy inputs. Nothing here reads or writes files, calls another family's
evaluate.py, or touches a locked validation window: callers are responsible for supplying already
-truncated, already-loaded series. Every guard returns a dict with at least
``{"pass": bool | None | "flag", "reason": str, "threshold": ..., "value": ...}``. ``pass=None``
means the guard did not run because its inputs were not supplied (NOT-RUN); ``pass="flag"`` means
the guard ran but the result needs a human read rather than a clean pass/fail (e.g. a single-asset
strategy, or too little post-publication data).

Convention used throughout: "Sharpe" is the annualised mean/vol (``mean / std * sqrt(periods_per_year)``,
the same convention as ``research/struct_common.sharpe`` and ``research/tsy_month_end/core.sharpe``);
"t-stat" is the plain one-sample t-statistic for a zero mean (``mean / (std / sqrt(n))``), which is
approximately ``Sharpe * sqrt(years)``. Frequency (daily vs monthly) is auto-detected from the median
gap between index timestamps unless a series is too short, in which case daily is assumed.

## Guard thresholds (module-level constants, all documented at the point of declaration below)

| Guard | Condition | Threshold |
|---|---|---|
| G1 beta | NW-HAC alpha t-stat vs all benchmarks jointly | t >= 2.0 AND alpha >= 50% of mean return |
| G2 reduced exposure | active return vs exposure-matched AND vol-matched control | IR > 0 AND t >= 2.0 (both controls) |
| G3 concentration | top-5%-months P&L share | < 50% |
| | max single-year P&L share | < 35% |
| | leave-one-year-out minimum Sharpe | >= 50% of full-period Sharpe |
| | monthly sign-test p | < 0.05 |
| G4 one asset | max single-asset P&L share | < 50% |
| | every leave-one-asset-out Sharpe | > 0 |
| G5 null calibration | P(pass | null) | <= 0.05 |
| | null distribution mean (if supplied), flag only | \\|mean\\| > 0.30 |
| G6 post-publication | post-publication t-stat | >= 1.65 (flag if fewer than 60 obs) |
| G7 execution lag | one-bar-lagged Sharpe / original Sharpe | >= 60% |
"""
from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import binomtest

# ----------------------------------------------------------------------------------------------
# Shared conventions
# ----------------------------------------------------------------------------------------------
DEFAULT_PERIODS_PER_YEAR = 252           # daily
MONTHLY_PERIODS_PER_YEAR = 12
DAILY_FREQ_MAX_MEDIAN_GAP_DAYS = 7       # median gap <= this many days => treat the series as daily

HAC_LAG_DAILY = 10                        # Newey-West lag, daily data
HAC_LAG_MONTHLY = 3                       # Newey-West lag, monthly data

# ----------------------------------------------------------------------------------------------
# G1 beta
# ----------------------------------------------------------------------------------------------
G1_ALPHA_T_MIN = 2.0
G1_ALPHA_SHARE_MIN = 0.50                 # alpha must be >= this share of the (raw, per-period) mean return

# ----------------------------------------------------------------------------------------------
# G2 reduced exposure
# ----------------------------------------------------------------------------------------------
G2_T_MIN = 2.0

# ----------------------------------------------------------------------------------------------
# G3 concentration
# ----------------------------------------------------------------------------------------------
G3_TOP5PCT_MONTHS_SHARE_MAX = 0.50
G3_MAX_YEAR_SHARE_MAX = 0.35
G3_LOYO_SHARPE_RATIO_MIN = 0.50
G3_SIGN_TEST_P_MAX = 0.05

# ----------------------------------------------------------------------------------------------
# G4 one asset
# ----------------------------------------------------------------------------------------------
G4_MAX_ASSET_SHARE_MAX = 0.50

# ----------------------------------------------------------------------------------------------
# G5 null calibration
# ----------------------------------------------------------------------------------------------
G5_NULL_PASS_RATE_MAX = 0.05
G5_NULL_MEAN_ABS_FLAG = 0.30              # |mean of the supplied null distribution| above this is flagged
                                           # as "this null does not centre near zero" (e.g. a shift null
                                           # whose mean Sharpe is -0.96 tests "better than random windows",
                                           # not "positive")

# ----------------------------------------------------------------------------------------------
# G6 post-publication
# ----------------------------------------------------------------------------------------------
G6_POSTPUB_T_MIN = 1.65
G6_MIN_POSTPUB_OBS = 60                   # fewer observations after publication_date => flag, not fail

# ----------------------------------------------------------------------------------------------
# G7 execution lag
# ----------------------------------------------------------------------------------------------
G7_LAG_SHARPE_RATIO_MIN = 0.60


# ================================================================================================
# Small numeric helpers
# ================================================================================================

def _clean(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return x[np.isfinite(x)]


def sharpe(x: np.ndarray | pd.Series, periods_per_year: int = DEFAULT_PERIODS_PER_YEAR) -> float:
    x = _clean(x.to_numpy() if isinstance(x, pd.Series) else x)
    if len(x) < 2:
        return float("nan")
    s = x.std(ddof=1)
    return float(x.mean() / s * np.sqrt(periods_per_year)) if s > 0 else float("nan")


def t_stat(x: np.ndarray | pd.Series) -> float:
    x = _clean(x.to_numpy() if isinstance(x, pd.Series) else x)
    n = len(x)
    if n < 2:
        return float("nan")
    s = x.std(ddof=1)
    return float(x.mean() / (s / np.sqrt(n))) if s > 0 else float("nan")


def _infer_periods_per_year(index) -> int:
    idx = pd.DatetimeIndex(index)
    if len(idx) < 3:
        return DEFAULT_PERIODS_PER_YEAR
    gaps = np.diff(idx.values).astype("timedelta64[D]").astype(int)
    gaps = gaps[gaps > 0]
    if len(gaps) == 0:
        return DEFAULT_PERIODS_PER_YEAR
    median_gap = float(np.median(gaps))
    return DEFAULT_PERIODS_PER_YEAR if median_gap <= DAILY_FREQ_MAX_MEDIAN_GAP_DAYS else MONTHLY_PERIODS_PER_YEAR


def _hac_lag(periods_per_year: int) -> int:
    return HAC_LAG_DAILY if periods_per_year == DEFAULT_PERIODS_PER_YEAR else HAC_LAG_MONTHLY


def _not_run(reason: str) -> dict:
    return {"pass": None, "reason": reason, "threshold": None, "value": None}


# ================================================================================================
# G1: beta / NW-HAC alpha
# ================================================================================================

def g1_beta(returns: pd.Series, benchmarks: Mapping[str, pd.Series]) -> dict:
    """NW-HAC alpha t-stat of `returns` against all `benchmarks` jointly. Pass if alpha t >= 2 and
    alpha >= 50% of the mean return. Reports each beta."""
    if returns is None or not benchmarks:
        return _not_run("NOT-RUN: returns or benchmarks not supplied")

    names = list(benchmarks.keys())
    df = pd.concat({"y": returns, **{n: benchmarks[n] for n in names}}, axis=1).dropna()
    if len(df) < 10:
        return _not_run(f"NOT-RUN: only {len(df)} overlapping observations")

    periods_per_year = _infer_periods_per_year(df.index)
    lag = _hac_lag(periods_per_year)

    y = df["y"].to_numpy()
    X = sm.add_constant(df[names].to_numpy())
    model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": lag})

    alpha = float(model.params[0])
    alpha_t = float(model.tvalues[0])
    betas = {n: float(model.params[i + 1]) for i, n in enumerate(names)}
    mean_return = float(df["y"].mean())
    alpha_share = alpha / mean_return if mean_return != 0 else float("nan")

    passed = bool(alpha_t >= G1_ALPHA_T_MIN and alpha >= G1_ALPHA_SHARE_MIN * mean_return)
    reason = (
        f"alpha t={alpha_t:.2f} ({'>=' if alpha_t >= G1_ALPHA_T_MIN else '<'} {G1_ALPHA_T_MIN}); "
        f"alpha_ann={alpha * periods_per_year:.4f} vs {G1_ALPHA_SHARE_MIN:.0%} of mean_ann="
        f"{mean_return * periods_per_year:.4f} "
        f"({'meets' if alpha >= G1_ALPHA_SHARE_MIN * mean_return else 'misses'} the share test)"
    )
    return {
        "pass": passed,
        "reason": reason,
        "threshold": {"alpha_t_min": G1_ALPHA_T_MIN, "alpha_share_min": G1_ALPHA_SHARE_MIN},
        "value": {
            "alpha_t": alpha_t,
            "alpha_ann": alpha * periods_per_year,
            "mean_return_ann": mean_return * periods_per_year,
            "alpha_share_of_mean": alpha_share,
            "betas": betas,
            "hac_lag": lag,
            "periods_per_year": periods_per_year,
            "n_obs": int(len(df)),
        },
    }


# ================================================================================================
# G2: reduced exposure
# ================================================================================================

def g2_reduced_exposure(returns: pd.Series, benchmarks: Mapping[str, pd.Series],
                         exposure: pd.Series | None) -> dict:
    """Active return of `returns` vs (a) an exposure-matched control (avg |exposure| x benchmark) and
    (b) a vol-matched benchmark. Pass if both active series have IR > 0 and t-stat >= 2. Uses the first
    entry of `benchmarks` as the exposure/vol-matched reference asset."""
    if returns is None or exposure is None or not benchmarks:
        return _not_run("NOT-RUN: returns, exposure or benchmarks not supplied")

    bench_name = next(iter(benchmarks))
    bench = benchmarks[bench_name]
    df = pd.concat({"y": returns, "w": exposure, "b": bench}, axis=1).dropna()
    if len(df) < 10:
        return _not_run(f"NOT-RUN: only {len(df)} overlapping observations")

    periods_per_year = _infer_periods_per_year(df.index)
    avg_abs_w = float(df["w"].abs().mean())
    exposure_matched_control = avg_abs_w * df["b"]
    active_exposure_matched = (df["y"] - exposure_matched_control).to_numpy()

    y_std, b_std = df["y"].std(ddof=1), df["b"].std(ddof=1)
    vol_scale = float(y_std / b_std) if b_std > 0 else float("nan")
    vol_matched_control = vol_scale * df["b"]
    active_vol_matched = (df["y"] - vol_matched_control).to_numpy()

    ir_exp, t_exp = sharpe(active_exposure_matched, periods_per_year), t_stat(active_exposure_matched)
    ir_vol, t_vol = sharpe(active_vol_matched, periods_per_year), t_stat(active_vol_matched)

    passed = bool(ir_exp > 0 and t_exp >= G2_T_MIN and ir_vol > 0 and t_vol >= G2_T_MIN)
    reason = (
        f"vs exposure-matched control ({avg_abs_w:.3f} x {bench_name}): IR={ir_exp:.2f}, t={t_exp:.2f}; "
        f"vs vol-matched control ({vol_scale:.3f} x {bench_name}): IR={ir_vol:.2f}, t={t_vol:.2f}"
    )
    return {
        "pass": passed,
        "reason": reason,
        "threshold": {"t_min": G2_T_MIN, "ir_min": 0.0},
        "value": {
            "benchmark_used": bench_name,
            "avg_abs_exposure": avg_abs_w,
            "exposure_matched": {"ir": ir_exp, "t": t_exp},
            "vol_match_scale": vol_scale,
            "vol_matched": {"ir": ir_vol, "t": t_vol},
            "periods_per_year": periods_per_year,
            "n_obs": int(len(df)),
        },
    }


# ================================================================================================
# G3: concentration
# ================================================================================================

def g3_concentration(returns: pd.Series) -> dict:
    """Four concentration checks on `returns` (a daily or monthly P&L/return series): top-5%-months
    share of total P&L, max single-year share, leave-one-year-out minimum Sharpe, and a monthly
    sign-test."""
    if returns is None:
        return _not_run("NOT-RUN: returns not supplied")

    s = returns.dropna()
    if len(s) < 10:
        return _not_run(f"NOT-RUN: only {len(s)} observations")

    periods_per_year = _infer_periods_per_year(s.index)
    idx = pd.DatetimeIndex(s.index)
    monthly = s.groupby(idx.to_period("M")).sum()
    yearly = s.groupby(idx.to_period("Y")).sum()
    total = float(s.sum())

    k = max(1, int(np.ceil(0.05 * len(monthly))))
    top5_sum = float(monthly.sort_values(ascending=False).iloc[:k].sum())
    top5_share = top5_sum / total if total != 0 else float("nan")

    max_year_share = float(yearly.abs().max() / abs(total)) if total != 0 else float("nan")
    max_year = yearly.abs().idxmax()

    full_sharpe = sharpe(s.to_numpy(), periods_per_year)
    loyo = {}
    for y in yearly.index:
        mask = idx.to_period("Y") != y
        loyo[str(y)] = sharpe(s.to_numpy()[mask], periods_per_year)
    loyo_min = min(loyo.values()) if loyo else float("nan")
    loyo_ratio = loyo_min / full_sharpe if full_sharpe and np.isfinite(full_sharpe) and full_sharpe != 0 else float("nan")

    n_pos = int((monthly > 0).sum())
    sign_p = float(binomtest(n_pos, len(monthly), 0.5).pvalue)

    cond_top5 = top5_share < G3_TOP5PCT_MONTHS_SHARE_MAX
    cond_year = max_year_share < G3_MAX_YEAR_SHARE_MAX
    cond_loyo = np.isfinite(loyo_ratio) and loyo_ratio >= G3_LOYO_SHARPE_RATIO_MIN
    cond_sign = sign_p < G3_SIGN_TEST_P_MAX
    passed = bool(cond_top5 and cond_year and cond_loyo and cond_sign)

    reason = (
        f"top5%-months share={top5_share:.2%} (<{G3_TOP5PCT_MONTHS_SHARE_MAX:.0%}: {cond_top5}); "
        f"max-year share={max_year_share:.2%} in {max_year} (<{G3_MAX_YEAR_SHARE_MAX:.0%}: {cond_year}); "
        f"LOYO min Sharpe={loyo_min:.2f} vs full {full_sharpe:.2f} ratio={loyo_ratio:.2f} "
        f"(>={G3_LOYO_SHARPE_RATIO_MIN:.0%}: {cond_loyo}); sign-test p={sign_p:.4f} (<{G3_SIGN_TEST_P_MAX}: {cond_sign})"
    )
    return {
        "pass": passed,
        "reason": reason,
        "threshold": {
            "top5pct_months_share_max": G3_TOP5PCT_MONTHS_SHARE_MAX,
            "max_year_share_max": G3_MAX_YEAR_SHARE_MAX,
            "loyo_sharpe_ratio_min": G3_LOYO_SHARPE_RATIO_MIN,
            "sign_test_p_max": G3_SIGN_TEST_P_MAX,
        },
        "value": {
            "top5pct_months_share": top5_share,
            "max_year_share": max_year_share,
            "max_year": str(max_year),
            "full_sharpe": full_sharpe,
            "loyo_min_sharpe": loyo_min,
            "loyo_sharpe_ratio": loyo_ratio,
            "loyo_by_year": loyo,
            "sign_test_p": sign_p,
            "n_months": int(len(monthly)),
            "n_years": int(len(yearly)),
            "periods_per_year": periods_per_year,
        },
    }


# ================================================================================================
# G4: one asset
# ================================================================================================

def g4_one_asset(asset_pnl: pd.DataFrame | None) -> dict:
    """Per-asset concentration: max single-asset share of P&L < 50%, and every leave-one-asset-out
    Sharpe > 0. A single-asset strategy is flagged rather than passed or failed."""
    if asset_pnl is None or asset_pnl.shape[1] == 0:
        return _not_run("NOT-RUN: asset_pnl not supplied")

    assets = list(asset_pnl.columns)
    if len(assets) == 1:
        return {
            "pass": "flag",
            "reason": f"single-asset strategy ({assets[0]}): flagged, not evaluated as n/a",
            "threshold": {"max_asset_share_max": G4_MAX_ASSET_SHARE_MAX},
            "value": {"n_assets": 1, "max_asset_share": "n/a", "loo_sharpes": "n/a"},
        }

    df = asset_pnl.dropna(how="all").fillna(0.0)
    periods_per_year = _infer_periods_per_year(df.index)
    totals = df.sum()
    total = float(totals.sum())
    max_share = float(totals.abs().max() / abs(total)) if total != 0 else float("nan")
    max_asset = str(totals.abs().idxmax())

    full = df.sum(axis=1)
    loo_sharpes = {a: sharpe((full - df[a]).to_numpy(), periods_per_year) for a in assets}
    all_positive = all(v > 0 for v in loo_sharpes.values())

    passed = bool(max_share < G4_MAX_ASSET_SHARE_MAX and all_positive)
    reason = (
        f"max single-asset share={max_share:.2%} ({max_asset}, <{G4_MAX_ASSET_SHARE_MAX:.0%}); "
        f"leave-one-asset-out Sharpes all > 0: {all_positive} ({loo_sharpes})"
    )
    return {
        "pass": passed,
        "reason": reason,
        "threshold": {"max_asset_share_max": G4_MAX_ASSET_SHARE_MAX, "loo_sharpe_min": 0.0},
        "value": {
            "n_assets": len(assets),
            "max_asset_share": max_share,
            "max_asset": max_asset,
            "loo_sharpes": loo_sharpes,
            "periods_per_year": periods_per_year,
        },
    }


# ================================================================================================
# G5: null calibration
# ================================================================================================

def g5_null_calibration(null_pass_rate: float | None,
                         null_distribution: np.ndarray | pd.Series | None = None) -> dict:
    """Pass if P(pass | null) <= 0.05. If the caller also supplies the null distribution (e.g. of
    Sharpes), flag when its mean is far from zero: such a null tests "better than a shifted world",
    not "better than nothing"."""
    if null_pass_rate is None:
        return _not_run("NOT-RUN: null_pass_rate not supplied")

    passed = bool(null_pass_rate <= G5_NULL_PASS_RATE_MAX)
    flag = None
    null_mean = None
    if null_distribution is not None:
        arr = _clean(np.asarray(null_distribution, dtype=float))
        if len(arr):
            null_mean = float(arr.mean())
            if abs(null_mean) > G5_NULL_MEAN_ABS_FLAG:
                flag = (
                    f"null mean ({null_mean:.3f}) is far from zero: this null calibrates 'better than "
                    f"the null's own shifted world', not 'better than random/zero'"
                )

    reason = f"P(pass|null)={null_pass_rate:.4f} ({'<=' if passed else '>'} {G5_NULL_PASS_RATE_MAX})"
    if flag:
        reason += f"; FLAG: {flag}"
    return {
        "pass": passed,
        "reason": reason,
        "threshold": {"null_pass_rate_max": G5_NULL_PASS_RATE_MAX, "null_mean_abs_flag": G5_NULL_MEAN_ABS_FLAG},
        "value": {"null_pass_rate": null_pass_rate, "null_mean": null_mean, "flag": flag},
    }


# ================================================================================================
# G6: post-publication
# ================================================================================================

def g6_post_publication(returns: pd.Series, publication_date: str | None) -> dict:
    """Sharpe and t-stat of `returns` strictly after `publication_date`. Pass if t >= 1.65; flag
    "insufficient post-pub data" instead of failing when there are too few observations."""
    if returns is None or publication_date is None:
        return _not_run("NOT-RUN: returns or publication_date not supplied")

    pub = pd.Timestamp(publication_date)
    post = returns.dropna()
    post = post[pd.DatetimeIndex(post.index) > pub]
    n = len(post)
    periods_per_year = _infer_periods_per_year(returns.index)

    if n < G6_MIN_POSTPUB_OBS:
        return {
            "pass": "flag",
            "reason": f"insufficient post-pub data (n={n} < {G6_MIN_POSTPUB_OBS} obs after {pub.date()})",
            "threshold": {"t_min": G6_POSTPUB_T_MIN, "min_obs": G6_MIN_POSTPUB_OBS},
            "value": {"n_obs": n, "publication_date": str(pub.date())},
        }

    post_sharpe = sharpe(post.to_numpy(), periods_per_year)
    post_t = t_stat(post.to_numpy())
    passed = bool(post_t >= G6_POSTPUB_T_MIN)
    reason = f"post-pub (n={n}) Sharpe={post_sharpe:.2f}, t={post_t:.2f} (>={G6_POSTPUB_T_MIN}: {passed})"
    return {
        "pass": passed,
        "reason": reason,
        "threshold": {"t_min": G6_POSTPUB_T_MIN, "min_obs": G6_MIN_POSTPUB_OBS},
        "value": {
            "n_obs": n,
            "publication_date": str(pub.date()),
            "post_pub_sharpe": post_sharpe,
            "post_pub_t": post_t,
            "periods_per_year": periods_per_year,
        },
    }


# ================================================================================================
# G7: execution lag
# ================================================================================================

def g7_execution_lag(returns: pd.Series, lagged_returns: pd.Series | None) -> dict:
    """Pass if the one-bar-lagged Sharpe is >= 60% of the original Sharpe."""
    if returns is None or lagged_returns is None:
        return _not_run("NOT-RUN: returns or lagged_returns not supplied")

    df = pd.concat({"y": returns, "yl": lagged_returns}, axis=1).dropna()
    if len(df) < 10:
        return _not_run(f"NOT-RUN: only {len(df)} overlapping observations")

    periods_per_year = _infer_periods_per_year(df.index)
    s0 = sharpe(df["y"].to_numpy(), periods_per_year)
    s1 = sharpe(df["yl"].to_numpy(), periods_per_year)
    ratio = s1 / s0 if s0 and np.isfinite(s0) and s0 != 0 else float("nan")
    passed = bool(np.isfinite(ratio) and ratio >= G7_LAG_SHARPE_RATIO_MIN)
    reason = f"lagged Sharpe={s1:.2f} / original Sharpe={s0:.2f} = {ratio:.2%} (>={G7_LAG_SHARPE_RATIO_MIN:.0%}: {passed})"
    return {
        "pass": passed,
        "reason": reason,
        "threshold": {"lag_sharpe_ratio_min": G7_LAG_SHARPE_RATIO_MIN},
        "value": {"original_sharpe": s0, "lagged_sharpe": s1, "ratio": ratio, "periods_per_year": periods_per_year},
    }


# ================================================================================================
# certify(): run every guard whose inputs are available
# ================================================================================================

def certify(returns: pd.Series, *, benchmarks: dict[str, pd.Series],
            exposure: pd.Series | None = None,
            asset_pnl: pd.DataFrame | None = None,
            null_pass_rate: float | None = None,
            null_distribution: np.ndarray | pd.Series | None = None,
            publication_date: str | None = None,
            lagged_returns: pd.Series | None = None) -> dict[str, Any]:
    """Run the promotion guards (G1-G7) that can run given the supplied inputs.

    Returns a dict keyed by guard name; each value has ``pass`` (True/False/"flag"/None for NOT-RUN),
    ``reason``, ``threshold`` and ``value``. Nothing here reads or writes any file.
    """
    return {
        "G1_beta": g1_beta(returns, benchmarks),
        "G2_reduced_exposure": g2_reduced_exposure(returns, benchmarks, exposure),
        "G3_concentration": g3_concentration(returns),
        "G4_one_asset": g4_one_asset(asset_pnl),
        "G5_null_calibration": g5_null_calibration(null_pass_rate, null_distribution),
        "G6_post_publication": g6_post_publication(returns, publication_date),
        "G7_execution_lag": g7_execution_lag(returns, lagged_returns),
    }
