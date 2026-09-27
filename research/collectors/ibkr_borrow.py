"""Interactive Brokers public shortable-stock file: borrow rates and available shares.

IBKR publishes an anonymous, keyless, no-login flat file listing shortable-stock
availability and indicative borrow fees, updated intraday, at
`ftp3.interactivebrokers.com/usa.txt` (also `ftp2...`/`ftp1...` mirrors documented on
IBKR's own site). This is the source flagged by the project's own data-scout report
(reports/data_scout/REPORT.md, "Borrow fees" row) as the only free retail borrow-fee
signal, explicitly "current-only" -- there is no history and IBKR does not publish one, so
collecting it FORWARD from today is the only way it will ever exist in this project.

Access note (recorded honestly, not worked around): `ftp3.interactivebrokers.com` timed
out over HTTPS from the sandbox this collector was developed in, while the rest of
interactivebrokers.com (main site, robots.txt) was reachable. That looks like a
network/egress-path issue specific to that host in this environment, not a ToS block --
IBKR's file requires no login and no key, and third-party tools (e.g. iborrowdesk) have
long used it as a public source. `run_once()` reports the failure verbatim rather than
retrying through a different route; it should be re-tried from the machine that will
actually run daily collection before relying on it.

    PYTHONPATH=. .venv/bin/python -m research.collectors.ibkr_borrow
"""
from __future__ import annotations

from research.collectors.common import FetchError, http_get, summarize, utc_now, write_snapshot

SOURCE = "ibkr_borrow"
URLS = [
    "https://ftp3.interactivebrokers.com/usa.txt",
    "https://ftp2.interactivebrokers.com/usa.txt",
    "https://ftp1.interactivebrokers.com/usa.txt",
]


def run_once(when=None, timeout: float = 25.0) -> dict:
    when = when or utc_now()
    records: list[dict] = []
    errors: list[str] = []

    for url in URLS:
        try:
            resp = http_get(url, timeout=timeout, retries=1)  # one attempt per mirror; try the next mirror on failure
            if resp.status_code == 200:
                records.append(write_snapshot(SOURCE, "usa", resp.content, when=when, ext="txt",
                                               extra_meta={"url": url}))
                break
            errors.append(f"{url}: HTTP {resp.status_code}")
        except FetchError as e:
            errors.append(f"{url}: {e}")

    return summarize(SOURCE, records, errors=errors)


if __name__ == "__main__":
    import json
    print(json.dumps(run_once(), indent=2))
