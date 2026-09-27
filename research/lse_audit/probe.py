"""Tiny, read-only audit probe of the LSE vault reference/event datasets (2026-09-23).

Scope: dividends, stock_splits, financial_reports, insider_trades, company_profiles,
stock_fundamentals, cot, economic_calendar, bond_yields (reference version).

Budget discipline (hard rule: <=50 rows/call, <=60 calls total):
  * cot and economic_calendar are answered entirely from the local caches already pulled
    by data/pull_lse_history.py / a prior macro_surprise pull (data/lse/cot/cot.parquet,
    data/lse/econ_calendar_us.parquet) -- zero vault calls.
  * dividends / stock_splits / financial_reports for the 5 rows-per-year sample tickers
    (AAPL, JPM, XOM, KO, T) are answered from the local per-symbol caches under data/lse/
    (already pulled for the full validated universe) -- zero vault calls.
  * Everything else (delisted-coverage checks, field discovery for insider_trades /
    company_profiles / stock_fundamentals / bond_yields, financial_reports report_type
    diversity) goes through the live vault, using the raw `Vault._call` with an explicit
    `limit` so every request is capped regardless of how much history exists server-side.
    `Vault.reference()` (read in data/lse_vault.py) is used directly only where the
    underlying data is provably tiny per symbol (corporate actions for one company), since
    for dated datasets it auto-paginates at 5,000 rows/request.

Never prints or writes the API key. Writes only under reports/lse_audit/.
Run: PYTHONPATH=. .venv/bin/python -m research.lse_audit.probe
"""
from __future__ import annotations

import json
from pathlib import Path

from data.lse_vault import Vault, VaultError

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "lse_audit" / "probe_20260923.json"

DELISTED = ["SIVB", "FRC", "ATVI", "TWTR", "CELG", "BBBY"]
SAMPLE_TICKERS = ["AAPL", "JPM", "XOM", "KO", "T"]

calls_made = 0


def safe(fn, *a, **k):
    global calls_made
    calls_made += 1
    try:
        return {"ok": True, "result": fn(*a, **k)}
    except VaultError as e:
        return {"ok": False, "error": str(e)[:300]}


def shape(rows, sample_n=1):
    if isinstance(rows, list):
        return {
            "rows": len(rows),
            "fields": sorted(rows[0].keys()) if rows and isinstance(rows[0], dict) else None,
            "sample": rows[:sample_n],
        }
    return {"type": type(rows).__name__, "value": rows}


def ref_probe(v: Vault, dataset: str, limit: int = 50, **filters):
    r = safe(v._call, "GET", f"/ref/{dataset}", {**filters, "limit": limit})
    return shape(r["result"]) if r["ok"] else {"error": r["error"]}


def main() -> None:
    v = Vault()
    res: dict = {}

    # -- 0. usage snapshot (no secrets) --------------------------------------------------
    u = safe(v.usage)
    if u["ok"]:
        res["usage_before"] = {k: val for k, val in u["result"].items()
                               if "key" not in k.lower() and "token" not in k.lower()}

    # -- 1. financial_reports: report_type diversity + raw field blob -----------------------
    # local caches only kept report_type="income" (see data/pull_lse_history.py); check
    # whether balance/cashflow report types exist at all, and what the raw "data" JSON blob
    # holds beyond the 6 fields the project extracted.
    res["financial_reports_report_types_AAPL"] = ref_probe(v, "financial_reports", limit=50, symbol="AAPL")

    # -- 2. delisted coverage: financial_reports, dividends, stock_splits, insider_trades,
    #       company_profiles, stock_fundamentals ------------------------------------------
    res["delisted_coverage"] = {}
    for ds in ["financial_reports", "dividends", "stock_splits", "insider_trades",
               "company_profiles", "stock_fundamentals"]:
        res["delisted_coverage"][ds] = {}
        for sym in DELISTED:
            res["delisted_coverage"][ds][sym] = ref_probe(v, ds, limit=5, symbol=sym)

    # -- 3. insider_trades: field discovery + rows-per-year sample for the 5 large tickers --
    res["insider_trades_fields_AAPL"] = ref_probe(v, "insider_trades", limit=50, symbol="AAPL")
    res["insider_trades_sample"] = {}
    for sym in SAMPLE_TICKERS:
        res["insider_trades_sample"][sym] = ref_probe(v, "insider_trades", limit=50, symbol=sym)

    # -- 4. company_profiles: field discovery + a couple of large-cap checks ----------------
    res["company_profiles_fields_AAPL"] = ref_probe(v, "company_profiles", limit=5, symbol="AAPL")
    res["company_profiles_sample"] = {}
    for sym in ["JPM", "XOM"]:
        res["company_profiles_sample"][sym] = ref_probe(v, "company_profiles", limit=5, symbol=sym)

    # -- 5. stock_fundamentals: field discovery + a couple of large-cap checks --------------
    res["stock_fundamentals_fields_AAPL"] = ref_probe(v, "stock_fundamentals", limit=5, symbol="AAPL")
    res["stock_fundamentals_sample"] = {}
    for sym in ["JPM", "XOM"]:
        res["stock_fundamentals_sample"][sym] = ref_probe(v, "stock_fundamentals", limit=5, symbol=sym)

    # -- 6. bond_yields (reference version): structure + history start ----------------------
    # unknown filter keys ahead of time; try unfiltered first, small limit.
    res["bond_yields_ref_unfiltered"] = ref_probe(v, "bond_yields", limit=10)
    # try ascending order (oldest first) to see history start, if the API respects it like
    # the paged candle/reference endpoints do (order=asc).
    r = safe(v._call, "GET", "/ref/bond_yields", {"limit": 10, "order": "asc"})
    res["bond_yields_ref_order_asc"] = shape(r["result"]) if r["ok"] else {"error": r["error"]}

    u2 = safe(v.usage)
    if u2["ok"]:
        res["usage_after"] = {k: val for k, val in u2["result"].items()
                              if "key" not in k.lower() and "token" not in k.lower()}

    res["calls_made"] = calls_made
    res["bytes_used"] = v.bytes_used
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, default=str))
    print(f"calls_made={calls_made} bytes_used={v.bytes_used}")
    print(json.dumps(res, indent=1, default=str)[:2000])


if __name__ == "__main__":
    main()
