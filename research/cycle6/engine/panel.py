"""Panel plumbing: calendar-month compounding, next-session holding periods, month-end sampling.

Conventions (fixed; used by every style):
- A *month* is a pandas monthly Period. Monthly per-instrument excess return = compounded daily excess return
  over the instrument's valid days in that calendar month (NaN if it has none).
- Signals/weights are formed at the month-end close of period t (information through that close) and indexed by t.
- Net holding period labelled m: from the close of the instrument's first valid day of month m to the close of its
  first valid day of month m+1 (i.e. its days 2..end of m plus day 1 of m+1). Weights formed at t are held over the
  holding period labelled t+1 (one-session lag, A5 G7).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def to_period_index(idx) -> pd.PeriodIndex:
    return pd.DatetimeIndex(idx).to_period("M")


def full_months(first: pd.Period, last: pd.Period) -> pd.PeriodIndex:
    return pd.period_range(first, last, freq="M")


def month_range_of(daily: pd.DataFrame) -> pd.PeriodIndex:
    p = to_period_index(daily.index)
    return full_months(p.min(), p.max())


def monthly_returns(daily: pd.DataFrame) -> pd.DataFrame:
    """Calendar-month compounded excess return per instrument (month-end close to month-end close)."""
    lr = np.log1p(daily)
    per = to_period_index(daily.index)
    s = lr.groupby(per).sum(min_count=1)
    return np.expm1(s).reindex(month_range_of(daily))


def first_day_mask(daily: pd.DataFrame) -> pd.DataFrame:
    """True on each instrument's first valid day of each calendar month."""
    valid = daily.notna()
    per = to_period_index(daily.index)
    cnt = valid.astype(int).groupby(per).cumsum()
    return valid & (cnt == 1)


def net_period_returns(daily: pd.DataFrame) -> pd.DataFrame:
    """Compounded excess return over the next-session holding period labelled m (see module doc)."""
    lr = np.log1p(daily)
    per = to_period_index(daily.index)
    months = month_range_of(daily)
    fd = first_day_mask(daily)
    lr0 = lr.fillna(0.0)
    tot = lr0.groupby(per).sum().reindex(months, fill_value=0.0)
    first = lr0.where(fd, 0.0).groupby(per).sum().reindex(months, fill_value=0.0)
    nval = daily.notna().astype(int).groupby(per).sum().reindex(months, fill_value=0)
    nfirst = fd.astype(int).groupby(per).sum().reindex(months, fill_value=0)
    s = tot - first + first.shift(-1).fillna(0.0)
    n = nval - nfirst + nfirst.shift(-1).fillna(0).astype(int)
    return np.expm1(s).where(n > 0)


def month_end_sample(daily: pd.DataFrame | pd.Series, months: pd.PeriodIndex | None = None):
    """Last valid value within each calendar month (NaN if none in that month: no stale carry-forward)."""
    per = to_period_index(daily.index)
    out = daily.groupby(per).last()
    return out.reindex(months if months is not None else full_months(per.min(), per.max()))


def to_monthly_panel(df: pd.DataFrame, months: pd.PeriodIndex, columns) -> pd.DataFrame:
    """Monthly-dated wide panel -> PeriodIndex, last observation per month, aligned to months x columns."""
    per = to_period_index(df.index)
    out = df.groupby(per).last()
    return out.reindex(index=months, columns=list(columns))
