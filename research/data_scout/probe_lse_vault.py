"""Tiny, read-only probe of the LSE vault for the data-scout report (2026-09-23).

Answers three questions with a handful of metered GET calls and very few rows:
  1. What does the plan allow (/usage)? Does the vault publish an API schema?
  2. Are delisted US equities present (SIVB, TWTR, FRC, CELG; ATVI/ANSS already 0 rows per ledger)?
  3. Does any reference dataset look like index membership, option quotes or open interest?

Never writes the API key anywhere; prints only status codes, row counts and field names.
Output: reports/data_scout/lse_probe_20260923.json
Run: PYTHONPATH=. .venv/bin/python -m research.data_scout.probe_lse_vault
"""
from __future__ import annotations

import json
from pathlib import Path

from data.lse_vault import Vault, VaultError

OUT = Path(__file__).resolve().parents[2] / "reports" / "data_scout" / "lse_probe_20260923.json"


def safe(fn, *a, **k):
    try:
        r = fn(*a, **k)
        return {"ok": True, "result": r}
    except VaultError as e:
        return {"ok": False, "error": str(e)[:300]}


def shape(obj):
    if isinstance(obj, list):
        return {"rows": len(obj), "fields": sorted(obj[0].keys()) if obj and isinstance(obj[0], dict) else None,
                "sample": obj[:1]}
    if isinstance(obj, dict):
        return {"keys": sorted(obj.keys())[:60]}
    return {"type": type(obj).__name__}


def main() -> None:
    v = Vault()
    res: dict = {}

    u = safe(v.usage)
    # usage holds plan limits, not secrets; keep only non-key fields
    if u["ok"]:
        res["usage"] = {k: val for k, val in u["result"].items() if "key" not in k.lower() and "token" not in k.lower()}
    else:
        res["usage"] = u

    # Delisted names: one tiny candle request each (limit 5 rows, a window when they traded).
    delisted = {"SIVB": "2022-01-03", "TWTR": "2021-01-04", "FRC": "2022-01-03", "CELG": "2018-01-02"}
    res["delisted_candles"] = {}
    for sym, day in delisted.items():
        r = safe(v._call, "GET", "/candles", {"symbol": sym, "timeframe": "1d", "start": day, "limit": 5})
        res["delisted_candles"][sym] = {"ok": r["ok"], "rows": len(r["result"]) if r["ok"] else 0,
                                        "error": r.get("error")}

    # Candidate reference datasets that would answer membership / option-quote questions.
    guesses = ["index_constituents", "constituents", "delistings", "options_quotes", "open_interest",
               "short_interest", "institutional_holdings"]
    res["ref_guesses"] = {}
    for g in guesses:
        r = safe(v._call, "GET", f"/ref/{g}", {"limit": 2})
        res["ref_guesses"][g] = shape(r["result"]) if r["ok"] else {"error": r["error"]}

    # A tiny window of the known options table: does any column hold bid/ask or OI?
    r = safe(v._call, "GET", "/candles", {"symbol": "SPY", "dataset": "options", "timeframe": "1d",
                                          "start": "2026-09-15", "end": "2026-09-15", "limit": 3})
    res["options_candle_fields"] = shape(r["result"]) if r["ok"] else {"error": r["error"]}

    res["bytes_used"] = v.bytes_used
    OUT.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()


def followup() -> None:
    """Second pass (3 calls, <=2 rows each): does the SEC-derived financial_reports set or the
    company_profiles set hold delisted filers even though candles do not?"""
    v = Vault()
    res = {}
    for ds, sym in [("financial_reports", "SIVB"), ("financial_reports", "TWTR"), ("company_profiles", "SIVB")]:
        r = safe(v._call, "GET", f"/ref/{ds}", {"symbol": sym, "limit": 2})
        res[f"{ds}:{sym}"] = shape(r["result"]) if r["ok"] else {"error": r["error"]}
    out = OUT.with_name("lse_probe_20260923_followup.json")
    out.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str)[:5000])


def followup_dividends() -> None:
    """Third pass (2 calls, <=2 rows): do corporate-action reference tables keep delisted payers?
    FRC (First Republic, paid dividends until 2023) and ATVI (annual dividend until 2023)."""
    v = Vault()
    res = {}
    for sym in ["FRC", "ATVI"]:
        r = safe(v._call, "GET", "/ref/dividends", {"symbol": sym, "limit": 2})
        res[f"dividends:{sym}"] = shape(r["result"]) if r["ok"] else {"error": r["error"]}
    out = OUT.with_name("lse_probe_20260923_dividends.json")
    out.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str)[:3000])
