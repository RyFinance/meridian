"""NYSE regular-session calendar: full holidays, 13:00 early closes, session
times in UTC. Rule-based (no exchange_calendars dependency in .venv).

Unscheduled closures (e.g. a national day of mourning) cannot be predicted by
rules; callers that decide on a date also check that official price data for
that date exists.
"""
from __future__ import annotations

import datetime as dt
from functools import lru_cache
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
OPEN = dt.time(9, 30)
CLOSE = dt.time(16, 0)
EARLY_CLOSE = dt.time(13, 0)


def _easter(year: int) -> dt.date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month, day = divmod(h + l_ - 7 * m + 114, 31)
    return dt.date(year, month, day + 1)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    first = dt.date(year, month, 1)
    return first + dt.timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> dt.date:
    nxt = dt.date(year + (month == 12), month % 12 + 1, 1)
    last = nxt - dt.timedelta(days=1)
    return last - dt.timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: dt.date, saturday_to_friday: bool = True) -> dt.date | None:
    if day.weekday() == 5:
        return day - dt.timedelta(days=1) if saturday_to_friday else None
    if day.weekday() == 6:
        return day + dt.timedelta(days=1)
    return day


@lru_cache(maxsize=None)
def holidays(year: int) -> frozenset[dt.date]:
    days = [
        _observed(dt.date(year, 1, 1), saturday_to_friday=False),  # NYSE does not close Fri Dec 31
        _nth_weekday(year, 1, 0, 3),     # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),     # Washington's Birthday
        _easter(year) - dt.timedelta(days=2),  # Good Friday
        _last_weekday(year, 5, 0),       # Memorial Day
        _observed(dt.date(year, 6, 19)) if year >= 2022 else None,  # Juneteenth
        _observed(dt.date(year, 7, 4)),  # Independence Day
        _nth_weekday(year, 9, 0, 1),     # Labor Day
        _nth_weekday(year, 11, 3, 4),    # Thanksgiving
        _observed(dt.date(year, 12, 25)),  # Christmas
    ]
    return frozenset(d for d in days if d is not None)


@lru_cache(maxsize=None)
def early_closes(year: int) -> frozenset[dt.date]:
    out = {_nth_weekday(year, 11, 3, 4) + dt.timedelta(days=1)}  # day after Thanksgiving
    july3 = dt.date(year, 7, 3)
    if july3.weekday() < 4 and july3 not in holidays(year):  # July 4 falls Tue..Fri
        out.add(july3)
    dec24 = dt.date(year, 12, 24)
    if dec24.weekday() < 5 and dec24 not in holidays(year):
        out.add(dec24)
    return frozenset(out)


def is_session(day: dt.date) -> bool:
    return day.weekday() < 5 and day not in holidays(day.year)


def session_close_time(day: dt.date) -> dt.time:
    return EARLY_CLOSE if day in early_closes(day.year) else CLOSE


def open_utc(day: dt.date) -> dt.datetime:
    return dt.datetime.combine(day, OPEN, tzinfo=ET).astimezone(dt.timezone.utc)


def close_utc(day: dt.date) -> dt.datetime:
    return dt.datetime.combine(day, session_close_time(day), tzinfo=ET).astimezone(dt.timezone.utc)


def next_session(day: dt.date) -> dt.date:
    d = day + dt.timedelta(days=1)
    while not is_session(d):
        d += dt.timedelta(days=1)
    return d


def previous_session(day: dt.date) -> dt.date:
    d = day - dt.timedelta(days=1)
    while not is_session(d):
        d -= dt.timedelta(days=1)
    return d


def sessions_between(start: dt.date, end: dt.date) -> list[dt.date]:
    """Sessions with start <= day <= end."""
    out, d = [], start
    while d <= end:
        if is_session(d):
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def first_session_of_month(year: int, month: int) -> dt.date:
    d = dt.date(year, month, 1)
    while not is_session(d):
        d += dt.timedelta(days=1)
    return d


def add_sessions(day: dt.date, n: int) -> dt.date:
    d = day
    for _ in range(n):
        d = next_session(d)
    return d


def to_date(value) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])
