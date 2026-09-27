"""FINRA bi-monthly short interest: incremental settlement-date update.

Keyless, public flat file on cdn.finra.org (equity/otcmarket/biweekly/). No account, no key.
Settlement dates fall near the 15th and the last calendar day of each month, and the file
for a settlement date is published roughly 7-8 business days later. This collector tries
the two most recent candidate settlement dates (this month's mid-month and month-end, plus
last month's) and keeps whichever most recent one is actually published (HTTP 200); an
unpublished date returns 403/404 and is recorded as an error, not treated as fatal.

Like finra_regsho.py, this is a genuinely new incremental collector, separate from the
project's existing one-time backfill (data/c4/finra_si/, through 2026-09-24).

    PYTHONPATH=. .venv/bin/python -m research.collectors.finra_short_interest
"""
from __future__ import annotations

import calendar
import datetime as dt

from research.collectors.common import FetchError, http_get, summarize, utc_now, write_snapshot

SOURCE = "finra_short_interest"
BASE = "https://cdn.finra.org/equity/otcmarket/biweekly"


def _settlement_dates(when: dt.datetime, n_months_back: int = 2) -> list[dt.date]:
    """Candidate settlement dates: the 15th (or nearest earlier business day) and the last
    calendar day of each of the last `n_months_back` months, most recent first."""
    out: list[dt.date] = []
    y, m = when.year, when.month
    for _ in range(n_months_back + 1):
        last_day = calendar.monthrange(y, m)[1]
        out.append(dt.date(y, m, last_day))
        out.append(dt.date(y, m, 15))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    out = [d for d in out if d <= when.date()]
    return sorted(out, reverse=True)


def run_once(when=None, n_months_back: int = 2) -> dict:
    when = when or utc_now()
    records: list[dict] = []
    errors: list[str] = []

    for d in _settlement_dates(when, n_months_back):
        url = f"{BASE}/shrt{d:%Y%m%d}.csv"
        try:
            resp = http_get(url)
        except FetchError as e:
            errors.append(f"{d.isoformat()}: {e}")
            continue
        if resp.status_code == 200:
            records.append(write_snapshot(SOURCE, f"shrt.{d:%Y%m%d}", resp.content, when=when, ext="csv",
                                           extra_meta={"url": resp.url, "settlement_date": d.isoformat()}))
            break  # most recent published settlement date found
        errors.append(f"{d.isoformat()}: HTTP {resp.status_code}")

    return summarize(SOURCE, records, errors=errors)


if __name__ == "__main__":
    import json
    print(json.dumps(run_once(), indent=2))
