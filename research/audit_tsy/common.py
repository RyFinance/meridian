"""Independent re-implementation helpers for the tsy_month_end audit (no import of the audited core)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "audit_tsy"
DEV = ("2003-01-02", "2014-12-31")
VAL = ("2015-01-02", "2026-08-31")
WINDOWS = {"dev": DEV, "val": VAL}


def yf_raw(sym: str) -> pd.DataFrame:
    h = pd.read_csv(OUT / f"yf_{sym}_raw{'_autoadjust_false' if sym == 'TLT' else ''}.csv", index_col=0)
    h.index = pd.to_datetime(h.index, utc=True).tz_convert("America/New_York").tz_localize(None).normalize()
    return h[~h.index.duplicated(keep="first")].sort_index()


def tr_from_raw(h: pd.DataFrame) -> pd.Series:
    """Total return from nominal close + cash dividend on its ex-date: (C_t + D_t)/C_{t-1} - 1."""
    c, d = h["Close"].astype(float), h["Dividends"].astype(float).fillna(0.0)
    return ((c + d) / c.shift(1) - 1.0)


def month_pos(idx: pd.DatetimeIndex) -> pd.DataFrame:
    """1-based session number within calendar month and number of sessions in the month."""
    per = idx.to_period("M")
    df = pd.DataFrame({"per": per}, index=idx)
    df["k"] = df.groupby("per").cumcount() + 1
    df["n"] = df.groupby("per")["k"].transform("max")
    df["from_end"] = df["n"] - df["k"]          # 0 = last session
    return df


def hold_mask(idx: pd.DatetimeIndex) -> pd.Series:
    """True on sessions whose close-to-close return is EARNED by M (the last 3 sessions of a month)."""
    mp = month_pos(idx)
    return pd.Series(mp["from_end"].le(2).to_numpy(), index=idx)


def book(ret: pd.Series, rf: pd.Series, earn: pd.Series, cost: float) -> tuple[pd.Series, pd.Series]:
    """M daily excess return and active return vs exposure-matched constant weight.

    earn[t] = 1 if M holds TLT over session t's return. Weight held at close t-1 = earn[t].
    Costs charged on the session the weight changes at the close (|dw| * cost)."""
    e = earn.astype(float)
    w_close = e.shift(-1).fillna(0.0)                  # weight set at close t (earns t+1)
    dw = w_close.diff().abs()
    dw.iloc[0] = w_close.iloc[0]
    m = e * (ret - rf) - dw * cost
    wbar = float(w_close.mean())
    ctrl = wbar * (ret - rf)
    return m, m - ctrl


def sharpe(x) -> float:
    x = pd.Series(x).dropna()
    s = x.std(ddof=1)
    return float(x.mean() / s * np.sqrt(252)) if s > 0 else float("nan")


def irx_rf(idx: pd.DatetimeIndex, irx: pd.Series) -> pd.Series:
    """Prior-day 13w bill yield, accrued over elapsed calendar days."""
    s = irx / 100.0
    rate = s.reindex(s.index.union(idx)).ffill().reindex(idx).shift().fillna(0)
    el = pd.Series(idx, index=idx).diff().dt.days.fillna(1)
    return rate * el / 365.25
