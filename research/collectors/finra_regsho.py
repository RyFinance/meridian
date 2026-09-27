"""FINRA Reg SHO daily short-sale volume: incremental daily update.

Keyless, public flat files on cdn.finra.org. No account, no key. This is a *different*
copy from the project's existing one-time historical backfill (data/c4/finra_regsho/,
2018-08-01..2026-09-24, built in an earlier cycle) -- that backfill is not incremental
and nothing currently re-runs it. This collector's only job is to keep picking up each
new trading day's file the moment it is published, under data/collect/finra_regsho/, so
the series never again falls behind "whenever someone happens to re-run a backfill".

Files are published for the CNMS (consolidated) tape plus four individual trading-facility
tapes (FNSQ Nasdaq, FNYX NYSE, FORF ADF/ORF, FNRA FINRA). All five are fetched. FINRA
publishes each day's file the same evening (Last-Modified confirmed ~1-2h after close in
an earlier scout pass); a same-day request before publication returns 403, which this
collector treats as "not yet published" and walks back to the most recent day that is.

    PYTHONPATH=. .venv/bin/python -m research.collectors.finra_regsho
"""
from __future__ import annotations

import datetime as dt

from research.collectors.common import FetchError, http_get, summarize, utc_now, write_snapshot

SOURCE = "finra_regsho"
BASE = "https://cdn.finra.org/equity/regsho/daily"
TAPES = ["CNMS", "FNSQ", "FNYX", "FORF", "FNRA"]


def _candidate_dates(when: dt.datetime, max_lookback: int) -> list[dt.date]:
    d = when.date()
    out = []
    for _ in range(max_lookback):
        if d.weekday() < 5:
            out.append(d)
        d -= dt.timedelta(days=1)
    return out


def run_once(when=None, max_lookback: int = 5) -> dict:
    when = when or utc_now()
    records: list[dict] = []
    errors: list[str] = []

    found_date: dt.date | None = None
    for d in _candidate_dates(when, max_lookback):
        url = f"{BASE}/CNMSshvol{d:%Y%m%d}.txt"
        try:
            resp = http_get(url)
        except FetchError as e:
            errors.append(f"CNMS {d.isoformat()}: {e}")
            continue
        if resp.status_code == 200:
            found_date = d
            records.append(write_snapshot(SOURCE, f"CNMSshvol.{d:%Y%m%d}", resp.content, when=when, ext="txt",
                                           extra_meta={"url": resp.url, "trade_date": d.isoformat()}))
            break
        errors.append(f"CNMS {d.isoformat()}: HTTP {resp.status_code}")

    if found_date is not None:
        for tape in TAPES:
            if tape == "CNMS":
                continue  # already fetched above
            url = f"{BASE}/{tape}shvol{found_date:%Y%m%d}.txt"
            try:
                resp = http_get(url)
                if resp.status_code == 200:
                    records.append(write_snapshot(SOURCE, f"{tape}shvol.{found_date:%Y%m%d}", resp.content,
                                                   when=when, ext="txt",
                                                   extra_meta={"url": resp.url, "trade_date": found_date.isoformat()}))
                else:
                    errors.append(f"{tape} {found_date.isoformat()}: HTTP {resp.status_code}")
            except FetchError as e:
                errors.append(f"{tape} {found_date.isoformat()}: {e}")

    return summarize(SOURCE, records, errors=errors)


if __name__ == "__main__":
    import json
    print(json.dumps(run_once(), indent=2))
