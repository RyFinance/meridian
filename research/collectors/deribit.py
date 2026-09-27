"""Deribit: option book summaries (all strikes/expiries), BTC and ETH.

Keyless, public JSON-RPC over HTTPS (www.deribit.com/api/v2/public). No account, no key.

`get_book_summary_by_currency(kind=option)` returns, in one call per currency, every listed
option's mark IV, open interest, volume, bid/ask, and underlying price -- the entire vol
surface's raw inputs for that instant. This is the only free, keyless, all-strikes option
snapshot found among the candidates in this task (Cboe's public feeds give index-level
put/call ratios and volume, not a per-strike book).

    PYTHONPATH=. .venv/bin/python -m research.collectors.deribit
"""
from __future__ import annotations

from research.collectors.common import FetchError, http_get, summarize, utc_now, write_snapshot

SOURCE = "deribit"
BASE = "https://www.deribit.com/api/v2/public"
CURRENCIES = ["BTC", "ETH"]


def run_once(currencies: list[str] | None = None, when=None) -> dict:
    when = when or utc_now()
    currencies = currencies or CURRENCIES
    records: list[dict] = []
    errors: list[str] = []

    for ccy in currencies:
        try:
            resp = http_get(f"{BASE}/get_book_summary_by_currency",
                             params={"currency": ccy, "kind": "option"})
            if resp.status_code == 200:
                records.append(write_snapshot(SOURCE, f"book_summary.{ccy}", resp.content, when=when,
                                               extra_meta={"url": resp.url}))
            else:
                errors.append(f"book_summary.{ccy}: HTTP {resp.status_code}: {resp.text[:200]!r}")
        except FetchError as e:
            errors.append(f"book_summary.{ccy}: {e}")
        # Also record the future/perpetual book summary for the same currency: gives a
        # cheap, same-call basis snapshot (dated futures + perpetual) alongside the options.
        try:
            resp = http_get(f"{BASE}/get_book_summary_by_currency",
                             params={"currency": ccy, "kind": "future"})
            if resp.status_code == 200:
                records.append(write_snapshot(SOURCE, f"book_summary_future.{ccy}", resp.content, when=when,
                                               extra_meta={"url": resp.url}))
            else:
                errors.append(f"book_summary_future.{ccy}: HTTP {resp.status_code}: {resp.text[:200]!r}")
        except FetchError as e:
            errors.append(f"book_summary_future.{ccy}: {e}")

    return summarize(SOURCE, records, errors=errors)


if __name__ == "__main__":
    import json
    print(json.dumps(run_once(), indent=2))
