"""Shared panel builder for agent_b: BTC off-hours split into early window E and remainder R.

All returns are log returns. BTC price at instant t = close of the 1m bar whose start is
t-1min (asof, max staleness 15 min, else NaN).
"""
from __future__ import annotations

import datetime as dt
from functools import lru_cache
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from research.forward import nyse

ET = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
BTC_PATH = "/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet"
MSTR_PATH = "/Users/rytty/CCP/quant_v7/research/mstr_btc_0dte/mstr_daily_yf.parquet"
OUT = "/Users/rytty/CCP/quant_v7/research/mstr_btc_0dte/agent_b"
SPLIT_DATE = pd.Timestamp("2024-08-08")  # MSTR 10:1 split effective; yf prices are split-adjusted


@lru_cache(maxsize=1)
def btc() -> pd.Series:
    d = pd.read_parquet(BTC_PATH, columns=["timestamp", "close"])
    s = d.set_index("timestamp")["close"].sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s


def price_at(times_utc: pd.DatetimeIndex, stale_min: int = 15) -> np.ndarray:
    s = btc()
    q = pd.DatetimeIndex(times_utc) - pd.Timedelta(minutes=1)
    idx = s.index.searchsorted(q, side="right") - 1
    out = np.full(len(q), np.nan)
    ok = idx >= 0
    bar_t = s.index[np.clip(idx, 0, None)]
    age = (q - bar_t) / pd.Timedelta(minutes=1)
    ok &= np.asarray(age) <= stale_min
    out[ok] = s.values[idx[ok]]
    return out


def et(day: dt.date, h: int, m: int = 0) -> pd.Timestamp:
    return pd.Timestamp(dt.datetime.combine(day, dt.time(h, m), ET)).tz_convert(UTC)


def build_panel(start="2017-08-18", end="2026-08-10") -> pd.DataFrame:
    days = nyse.sessions_between(pd.Timestamp(start).date(), pd.Timestamp(end).date())
    rows = []
    for d in days:
        p = nyse.previous_session(d)
        rows.append(dict(
            date=pd.Timestamp(d), prev=pd.Timestamp(p), gap_days=(d - p).days,
            t_close=pd.Timestamp(nyse.close_utc(p)).tz_convert(UTC),
            t_open=pd.Timestamp(nyse.open_utc(d)).tz_convert(UTC),
            t_20=et(p, 20),                       # 20:00 ET on prev session day (AH close)
            t_04=et(d, 4),                        # 04:00 ET on session day (pre-market open)
            t_sat16=et(p + dt.timedelta(days=1), 16),   # close + 1 calendar day 16:00
            t_sun20=et(d - dt.timedelta(days=1), 20),   # 20:00 ET evening before session
        ))
    P = pd.DataFrame(rows)
    for c in ["t_close", "t_open", "t_20", "t_04", "t_sat16", "t_sun20"]:
        P["p" + c[1:]] = price_at(pd.DatetimeIndex(P[c]))
    lr = lambda a, b: np.log(P["p_" + b] / P["p_" + a])
    P["off"] = lr("close", "open")
    # weekday-style windows (valid for all overnights)
    P["E20"], P["R20"] = lr("close", "20"), lr("20", "open")
    P["E04"], P["R04"] = lr("close", "04"), lr("04", "open")
    # long (weekend/holiday) windows
    P["Esat"], P["Rsat"] = lr("close", "sat16"), lr("sat16", "open")
    P["Esun"], P["Rsun"] = lr("close", "sun20"), lr("sun20", "open")
    P["kind"] = np.where(P.gap_days == 1, "weeknight", "long")
    P["year"] = P.date.dt.year
    P["dow"] = P.date.dt.dayofweek
    return P


@lru_cache(maxsize=1)
def mstr() -> pd.DataFrame:
    m = pd.read_parquet(MSTR_PATH)[["Open", "Close"]].copy()
    m.index = pd.to_datetime(m.index).normalize()
    m["prev_close"] = m.Close.shift(1)
    m["gap"] = np.log(m.Open / m.prev_close)
    m["raw_px"] = np.where(m.index < SPLIT_DATE, m.Open * 10, m.Open)  # traded price for commission
    return m


def stats(x: pd.Series, per_year: float) -> dict:
    """x = per-opportunity net returns (fraction of notional), 0 on skip nights."""
    x = pd.Series(x).dropna()
    traded = x[x != 0]
    n = len(traded)
    mu, sd = traded.mean(), traded.std()
    t = mu / sd * np.sqrt(n) if n > 1 and sd > 0 else np.nan
    sh = x.mean() / x.std() * np.sqrt(per_year) if x.std() > 0 else np.nan
    eq = x.cumsum()
    mdd = (eq - eq.cummax()).min()
    return dict(n=n, mean_bp=mu * 1e4, win=(traded > 0).mean(), t=t, sharpe=sh,
                tot_pct=x.sum() * 100, mdd_pct=mdd * 100)
