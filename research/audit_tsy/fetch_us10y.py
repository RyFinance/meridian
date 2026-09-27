"""Remaining LSE US10Y (bonds dataset) ranges; the first pulls were truncated at ~1,100 obs.
4 read-only macro_series calls (session total 39 -> 43 of 60)."""
import json
from pathlib import Path
from research.lse_mcp_client import Terminal, content_text
OUT = Path(__file__).resolve().parents[2] / "reports" / "audit_tsy"
RANGES = [("2007-05-01", "2011-06-30"), ("2011-07-01", "2014-12-31"), ("2019-06-12", "2023-06-30"), ("2023-07-01", "2026-09-22")]
log = []
with Terminal() as t:
    for s, e in RANGES:
        res = t.call("macro_series", {"symbol": "US10Y", "dataset": "bonds", "start": s, "end": e, "limit": 5000, "order": "asc"}, timeout=120)
        txt = content_text(res)
        (OUT / f"lse_US10Y_raw_{s}.txt").write_text(txt)
        log.append({"range": [s, e], "chars": len(txt), "truncated": "truncated" in txt[-200:], "is_error": bool(res.get("isError"))})
(OUT / "lse_us10y_call_log.json").write_text(json.dumps({"calls": len(log), "session_total_after": 39 + len(log), "log": log}, indent=1))
print(log)
