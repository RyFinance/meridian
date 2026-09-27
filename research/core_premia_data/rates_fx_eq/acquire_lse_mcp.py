"""Bounded, read-only LSE Terminal MCP ingest (hard cap: 58 tool calls, task limit 60).

Uses the project's research-only bridge (``research.lse_mcp_client``), which whitelists read tools
only. Calls, in priority order:
  1. terminal_status                                   (1)
  2. get_history 1d for all 19 ``index`` catalog series  (19)  -- UTC-day bars, 2023+ history
  3. macro_series JGB_FUT (bond_futures), 5 windows     (5)   -- front-month continuous JGB future
  4. get_history 1d FGBL, FESX (Eurex, 2025+)           (2)
  5. macro_series *_SW_FWD 1-week forward points, 9 G10 pairs x 3 windows (27)
Each raw text response is written verbatim through the collectors snapshot writer; the
response is checked for the MCP 'truncated' marker (observed at ~1,100 rows per call in earlier
sessions), so windows are kept to <=~1,000 rows.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.core_premia_data.rates_fx_eq.acquire_lse_mcp
"""
from __future__ import annotations

import json

from research.collectors import common as cc
from research.core_premia_data.rates_fx_eq.common import META, RAW, log_attempt, utc_now, write_json
from research.lse_mcp_client import Terminal, content_text

CAP = 58
INDEX = ["NAS100/USD", "US30/USD", "SPX500/USD", "NASCOMP/USD", "SOX/USD", "DE30/EUR", "UK100/GBP",
         "EU50/EUR", "US2000/USD", "FR40/EUR", "IT40/EUR", "HK33/HKD", "JP225/USD", "UK250/GBP",
         "ES35/EUR", "CN50/USD", "CH20/CHF", "NL30/EUR", "AU200/AUD"]
JGB_WINDOWS = [("2010-01-01", "2013-06-30"), ("2013-07-01", "2016-12-31"), ("2017-01-01", "2020-06-30"),
               ("2020-07-01", "2023-12-31"), ("2024-01-01", "2026-09-26")]
FWD_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD", "USDSEK", "USDNOK"]
FWD_WINDOWS = [("2015-01-01", "2018-12-31"), ("2019-01-01", "2022-12-31"), ("2023-01-01", "2026-09-26")]


def main() -> dict:
    calls = []
    with Terminal() as t:
        def call(name, args, label, timeout=120):
            if len(calls) >= CAP:
                calls.append({"label": label, "skipped": "call cap reached"})
                return None
            t0 = utc_now()
            try:
                res = t.call(name, args, timeout=timeout)
                txt = content_text(res)
                err = bool(res.get("isError"))
            except Exception as e:  # noqa: BLE001
                txt, err = f"EXCEPTION {e!r}", True
            trunc = "truncated" in txt[-400:].lower()
            rec = cc.write_snapshot("lse_mcp", label.replace("/", "_"), txt.encode(), when=t0, ext="txt", root=RAW,
                                    extra_meta={"tool": name, "arguments": args, "is_error": err,
                                                "truncated_marker": trunc})
            row = {"n": len(calls) + 1, "label": label, "tool": name, "arguments": args, "chars": len(txt),
                   "is_error": err, "truncated": trunc, "path": rec["path"], "fetched_at_utc": rec["fetched_at_utc"]}
            calls.append(row)
            log_attempt({"source": "lse_mcp", "name": label, "outcome": "error" if err else ("truncated" if trunc else "ok"),
                         "chars": len(txt), "path": rec["path"]})
            return txt

        status = call("terminal_status", {}, "terminal_status", 30) or ""
        if "not running" in status.lower():
            # Guard added after the 2026-09-26 07:35Z run, which lacked it and spent 53 further
            # calls that all failed with the same app-not-running error (no data returned).
            calls.append({"label": "ABORT", "skipped": "LSE Terminal not running; no further calls"})
            out = {"run_at_utc": utc_now().isoformat(), "call_cap": CAP, "calls_made": 1, "calls": calls}
            write_json(META / "acquire_lse_mcp_results_aborted.json", out)
            return out
        for s in INDEX:
            call("get_history", {"symbol": s, "timeframe": "1d", "start": "2023-01-01", "end": "2026-09-26",
                                 "limit": 5000}, f"index_1d_{s}")
        for a, b in JGB_WINDOWS:
            call("macro_series", {"symbol": "JGB_FUT", "dataset": "bond_futures", "start": a, "end": b,
                                  "limit": 5000, "order": "asc"}, f"JGB_FUT_{a}")
        for s in ("FGBL", "FESX"):
            call("get_history", {"symbol": s, "timeframe": "1d", "start": "2025-01-01", "end": "2026-09-26",
                                 "limit": 5000}, f"eurex_1d_{s}")
        for p in FWD_PAIRS:
            for a, b in FWD_WINDOWS:
                call("macro_series", {"symbol": f"{p}_SW_FWD", "dataset": "fx_derivatives", "start": a, "end": b,
                                      "limit": 5000, "order": "asc"}, f"{p}_SW_FWD_{a}")
    out = {"run_at_utc": utc_now().isoformat(), "call_cap": CAP,
           "calls_made": sum(1 for c in calls if "skipped" not in c), "calls": calls}
    write_json(META / "acquire_lse_mcp_results.json", out)
    return out


if __name__ == "__main__":
    o = main()
    print(json.dumps({"calls_made": o["calls_made"],
                      "problems": [c for c in o["calls"] if c.get("is_error") or c.get("truncated") or c.get("skipped")]},
                     indent=1)[:4000])
