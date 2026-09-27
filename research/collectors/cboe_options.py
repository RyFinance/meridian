"""Cboe: daily options market-statistics JSON (put/call ratios, volume by class).

Keyless, public static JSON on cdn.cboe.com. No account, no key. Cboe's robots.txt
(www.cboe.com/robots.txt, checked 2026-09-25) disallows only `/book/` and
`*market_statistics/volume_reports/` -- this collector touches neither; the
`cdn.cboe.com/data/us/options/market_statistics/daily/<date>_daily_options` endpoint is
a small (~7KB) precomputed summary, not a scrape of a disallowed report page.

The file is published per US trading day and keyed by date in its URL; there is no
"latest" alias, so this collector tries today's date and walks backward (skipping
weekends) until it finds a published file or exhausts `max_lookback` days -- this
naturally self-heals across holidays without a hardcoded market calendar.

    PYTHONPATH=. .venv/bin/python -m research.collectors.cboe_options
"""
from __future__ import annotations

import datetime as dt

from research.collectors.common import FetchError, http_get, summarize, utc_now, write_snapshot

SOURCE = "cboe_options"
BASE = "https://cdn.cboe.com/data/us/options/market_statistics/daily"


def _candidate_dates(when: dt.datetime, max_lookback: int) -> list[dt.date]:
    d = when.date()
    out = []
    for _ in range(max_lookback):
        if d.weekday() < 5:  # Mon-Fri only; Cboe doesn't publish for weekends
            out.append(d)
        d -= dt.timedelta(days=1)
    return out


def run_once(when=None, max_lookback: int = 5) -> dict:
    when = when or utc_now()
    records: list[dict] = []
    errors: list[str] = []

    for d in _candidate_dates(when, max_lookback):
        url = f"{BASE}/{d.isoformat()}_daily_options"
        try:
            resp = http_get(url)
        except FetchError as e:
            errors.append(f"{d.isoformat()}: {e}")
            continue
        if resp.status_code == 200:
            records.append(write_snapshot(SOURCE, f"daily_options.{d.isoformat()}", resp.content, when=when,
                                           extra_meta={"url": resp.url, "trade_date": d.isoformat()}))
            break  # most recent published day found; stop walking further back
        errors.append(f"{d.isoformat()}: HTTP {resp.status_code}")

    return summarize(SOURCE, records, errors=errors)


if __name__ == "__main__":
    import json
    print(json.dumps(run_once(), indent=2))
