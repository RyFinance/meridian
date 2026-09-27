"""Run every enabled collector once and print a combined summary.

    PYTHONPATH=. .venv/bin/python -m research.collectors.collect_all
    PYTHONPATH=. .venv/bin/python -m research.collectors.collect_all --only binance_futures,deribit

This module does not schedule itself -- no cron/launchd job is created anywhere in this
package. See the "Recommended schedule" note in this task's final report for the exact
command a human (or the user's own scheduler) should run, and how often.
"""
from __future__ import annotations

import argparse
import json
import sys

from research.collectors import (
    binance_futures,
    bybit,
    cboe_options,
    deribit,
    etf_holdings,
    finra_regsho,
    finra_short_interest,
    ibkr_borrow,
    okx,
)

COLLECTORS = {
    "binance_futures": binance_futures.run_once,
    "bybit": bybit.run_once,
    "okx": okx.run_once,
    "deribit": deribit.run_once,
    "cboe_options": cboe_options.run_once,
    "finra_regsho": finra_regsho.run_once,
    "finra_short_interest": finra_short_interest.run_once,
    "etf_holdings": etf_holdings.run_once,
    "ibkr_borrow": ibkr_borrow.run_once,
}


def run_all(only: list[str] | None = None) -> dict:
    names = only or list(COLLECTORS)
    results = {}
    for name in names:
        if name not in COLLECTORS:
            results[name] = {"source": name, "status": "unknown_collector"}
            continue
        try:
            results[name] = COLLECTORS[name]()
        except Exception as e:  # noqa: BLE001 - one collector's crash must not stop the rest
            results[name] = {"source": name, "status": "crashed", "error": repr(e)}
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", type=str, default=None, help="comma-separated subset of collector names")
    args = ap.parse_args(argv)
    only = [s.strip() for s in args.only.split(",")] if args.only else None
    results = run_all(only)
    print(json.dumps(results, indent=2))
    return 0 if all(r.get("status") in ("ok", "partial") for r in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
