"""OKX: SWAP (perpetual) tickers and open interest, market-wide, in two calls.

Keyless, public REST only (www.okx.com/api/v5). No account, no key, no order endpoint.
OKX's robots.txt explicitly `Allow: /api/*?` (checked 2026-09-25), so keyless REST reads
are not disallowed by the site's own crawl policy.

`market/tickers?instType=SWAP` and `public/open-interest?instType=SWAP` each return the
full market in one call (no per-symbol looping needed), so this collector is two requests
per run regardless of how many perpetuals OKX lists.

    PYTHONPATH=. .venv/bin/python -m research.collectors.okx
"""
from __future__ import annotations

from research.collectors.common import FetchError, http_get, summarize, utc_now, write_snapshot

SOURCE = "okx"
BASE = "https://www.okx.com"


def run_once(when=None) -> dict:
    when = when or utc_now()
    records: list[dict] = []
    errors: list[str] = []

    calls = [
        ("tickers.swap", "/api/v5/market/tickers", {"instType": "SWAP"}),
        ("open-interest.swap", "/api/v5/public/open-interest", {"instType": "SWAP"}),
    ]
    for name, path, params in calls:
        try:
            resp = http_get(f"{BASE}{path}", params=params)
            if resp.status_code == 200:
                records.append(write_snapshot(SOURCE, name, resp.content, when=when, extra_meta={"url": resp.url}))
            else:
                errors.append(f"{name}: HTTP {resp.status_code}: {resp.text[:200]!r}")
        except FetchError as e:
            errors.append(f"{name}: {e}")

    return summarize(SOURCE, records, errors=errors)


if __name__ == "__main__":
    import json
    print(json.dumps(run_once(), indent=2))
