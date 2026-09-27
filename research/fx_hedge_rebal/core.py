"""Month-end FX hedge-rebalancing flow (research/fx_hedge_rebal/PLAN.md). Frozen by the plan."""
from __future__ import annotations

from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from research.fx_news.evaluate import load_closes, price_at
from research.fx_news.events import PAIRS
from research.struct_common import ROOT

LONDON = ZoneInfo("Europe/London")
CCY_INDEX = {"EUR": "EZ", "GBP": "UK", "AUD": "AU", "JPY": "JP", "CAD": "CA"}
COSTS = {"gross": 0.0, "base": 1e-4, "stress": 3e-4}


def index_close(code: str) -> pd.Series:
    d = pd.read_parquet(ROOT / "data" / "policy_trend" / f"{code}.parquet")
    return d.set_index(pd.to_datetime(d["date"]))["close"].sort_index()


def month_end_days(start: str, end: str) -> pd.DatetimeIndex:
    return pd.date_range(start, end, freq="BME")                      # last weekday of each month


def london_to_utc(day: pd.Timestamp, hhmm: str) -> np.datetime64:
    t = pd.Timestamp(f"{day.date()} {hhmm}").tz_localize(LONDON).tz_convert("UTC").tz_localize(None)
    return np.datetime64(t, "ns")


def mtd(px: pd.Series, D: pd.Timestamp) -> float:
    prev_end = D.to_period("M").start_time - pd.Timedelta(days=1)
    a, b = px.loc[:prev_end], px.loc[: D - pd.Timedelta(days=1)]
    b = b[b.index > prev_end]
    if a.empty or b.empty:
        return np.nan
    return float(b.iloc[-1] / a.iloc[-1] - 1.0)


def events(start: str, end: str) -> pd.DataFrame:
    days = month_end_days(start, end)
    us = index_close("US")
    idx = {c: index_close(k) for c, k in CCY_INDEX.items()}
    closes = load_closes(start, end)
    rows = []
    for D in days:
        t_in, t_out = london_to_utc(D, "08:00"), london_to_utc(D, "16:00")
        for ccy, code in CCY_INDEX.items():
            rel = mtd(us, D) - mtd(idx[ccy], D)
            pair, orient = PAIRS[ccy]
            a = price_at(closes[pair], np.array([t_in]), 5)[0]
            b = price_at(closes[pair], np.array([t_out]), 5)[0]
            rows.append({"D": D, "ccy": ccy, "rel": rel, "sign": np.sign(rel) if np.isfinite(rel) else np.nan,
                         "ret": orient * (b / a - 1.0) if np.isfinite(a) and np.isfinite(b) else np.nan})
    return pd.DataFrame(rows)


def daily_book(ev: pd.DataFrame, sign_col: str, cost: float, days: pd.DatetimeIndex) -> pd.Series:
    ok = ev[sign_col].notna() & ev["ret"].notna() & (ev[sign_col] != 0)
    pnl = (ev.loc[ok, sign_col] * ev.loc[ok, "ret"] - 2 * cost).groupby(ev.loc[ok, "D"]).mean()
    return pnl.reindex(days, fill_value=0.0)
