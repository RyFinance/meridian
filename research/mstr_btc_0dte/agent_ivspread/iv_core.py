"""Shared measurement mechanics for the MSTR-vs-IBIT IV-spread study.

Research only.  Spec frozen in PREREGISTRATION.md; any change needs an
amendment entry in research/preregistrations.jsonl before re-running.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
MSTR_OPTIONS = PROJECT / "data" / "lse" / "options_mstr" / "MSTR.parquet"
IBIT_OPTIONS = PROJECT / "data" / "lse" / "options_ibit_1d" / "IBIT.parquet"
MSTR_DAILY = PROJECT / "research" / "mstr_btc_0dte" / "mstr_daily_yf.parquet"
IBIT_DAILY = PROJECT / "data" / "ibit_daily_yf.parquet"

WINDOW_START = pd.Timestamp("2024-11-19").date()
WINDOW_END = pd.Timestamp("2026-09-16").date()
DTE_BAND = (20, 45)
TARGET_DTE = 30
MONEYNESS = 0.10
MIN_PRINT = 0.005
VOL_SIGMA_BOUNDS = (0.05, 5.0)
Z_WINDOW = 120
Z_MIN_PERIODS = 60
Z_ENTRY = -1.0


def bs_price(spot: float, strike: float, t_years: float, sigma: float, kind: str) -> float:
    if t_years <= 0 or sigma <= 0:
        return np.nan
    d1 = (np.log(spot / strike) + 0.5 * sigma * sigma * t_years) / (sigma * np.sqrt(t_years))
    d2 = d1 - sigma * np.sqrt(t_years)
    if kind == "C":
        return spot * norm.cdf(d1) - strike * norm.cdf(d2)
    return strike * norm.cdf(-d2) - spot * norm.cdf(-d1)


def implied_vol(print_px: float, spot: float, strike: float, t_years: float, kind: str) -> float:
    intrinsic = max(0.0, spot - strike) if kind == "C" else max(0.0, strike - spot)
    if print_px <= max(MIN_PRINT, intrinsic):
        return np.nan
    lo, hi = VOL_SIGMA_BOUNDS
    if bs_price(spot, strike, t_years, hi, kind) < print_px:
        return np.nan
    try:
        return float(brentq(lambda s: bs_price(spot, strike, t_years, s, kind) - print_px, lo, hi, xtol=1e-6))
    except ValueError:
        return np.nan


def session_iv_series(options_path: Path, daily_close: pd.Series) -> pd.DataFrame:
    """One row per session with the frozen ATM ~30dte IV measurement."""
    opts = pd.read_parquet(options_path, columns=["ts", "expiry", "opt_type", "strike", "close", "volume"])
    opts["d"] = pd.to_datetime(opts["ts"]).dt.date
    opts["expiry"] = pd.to_datetime(opts["expiry"]).dt.date
    opts = opts[(opts.d >= WINDOW_START) & (opts.d <= WINDOW_END)]
    opts["dte"] = (pd.to_datetime(opts["expiry"]) - pd.to_datetime(opts["d"])).dt.days
    opts = opts[(opts.close > MIN_PRINT) & (opts.volume >= 1)]

    close = daily_close.copy()
    close.index = pd.DatetimeIndex(close.index).normalize().date

    rows = []
    for d, g in opts.groupby("d"):
        spot = close.get(d, np.nan)
        expiries = sorted(g.expiry.unique())
        band = [e for e in expiries if DTE_BAND[0] <= (e - d).days <= DTE_BAND[1]]
        rec = {"date": d, "iv_call": np.nan, "iv_put": np.nan, "iv": np.nan,
               "expiry": pd.NaT, "dte": np.nan, "strike": np.nan, "spot": spot}
        if band and not pd.isna(spot):
            chosen = min(band, key=lambda e: (abs((e - d).days - TARGET_DTE), e))
            ge = g[g.expiry == chosen]
            ge = ge[(ge.strike / spot - 1).abs() <= MONEYNESS]
            if len(ge):
                k = ge.assign(m=(ge.strike / spot - 1).abs()).sort_values("m").strike.iloc[0]
                t = (chosen - d).days / 365.0
                rec["expiry"], rec["dte"], rec["strike"] = chosen, (chosen - d).days, k
                for kind, col in (("C", "iv_call"), ("P", "iv_put")):
                    side = ge[(ge.strike == k) & (ge.opt_type == kind)]
                    if len(side):
                        rec[col] = implied_vol(float(side.close.iloc[0]), spot, k, t, kind)
                vals = [v for v in (rec["iv_call"], rec["iv_put"]) if not pd.isna(v)]
                if vals:
                    rec["iv"] = float(np.mean(vals))
        rows.append(rec)
    out = pd.DataFrame(rows).set_index("date")
    return out


def spread_and_z(iv_mstr: pd.Series, iv_ibit: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"iv_mstr": iv_mstr, "iv_ibit": iv_ibit})
    df["spread"] = df.iv_mstr - df.iv_ibit
    roll = df["spread"].rolling(Z_WINDOW, min_periods=Z_MIN_PERIODS)
    df["z"] = (df["spread"] - roll.mean()) / roll.std(ddof=1)
    return df
