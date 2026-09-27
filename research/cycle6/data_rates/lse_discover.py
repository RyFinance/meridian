"""Read-only LSE macro catalog discovery (macro_search only). Stops after 3 consecutive failures."""
from __future__ import annotations

import json

from research.collectors import common as cc
from research.cycle6.data_rates.common import META, RAW, utc_now, write_json
from research.lse_mcp_client import Terminal, content_text

COUNTRIES = ["US", "DE", "JP", "AU", "FR", "IT", "CH", "SE", "NO", "NZ", "ES", "NL", "BE", "AT", "DK", "GB", "UK",
             "CA", "EU"]
QUERIES = [("yield", None), ("rate", None), ("bill", None), ("interbank", None)]


def main():
    log, fails, out = [], 0, {}
    with Terminal() as t:
        st = content_text(t.call("terminal_status", {}, timeout=30))
        if "not running" in st.lower():
            write_json(META / "lse_discover.json", {"aborted": "terminal not running"}); return
        for c in COUNTRIES:
            for q, cat in QUERIES:
                if fails >= 3:
                    log.append({"country": c, "q": q, "skipped": "3 consecutive failures"}); continue
                args = {"query": q, "country": c, "limit": 300}
                t0 = utc_now()
                try:
                    res = t.call("macro_search", args, timeout=60); txt = content_text(res); err = bool(res.get("isError"))
                except Exception as e:  # noqa: BLE001
                    txt, err = f"EXCEPTION {e!r}", True
                fails = fails + 1 if err else 0
                rec = cc.write_snapshot("lse_mcp_catalog", f"search_{c}_{q}", txt.encode(), when=t0, ext="json", root=RAW,
                                        extra_meta={"tool": "macro_search", "arguments": args, "is_error": err})
                log.append({"country": c, "q": q, "err": err, "path": rec["path"], "at": rec["fetched_at_utc"]})
                if not err:
                    try:
                        for s in json.loads(txt).get("series", []):
                            out[(s["dataset"], s["symbol"])] = s
                    except Exception:  # noqa: BLE001
                        pass
    write_json(META / "lse_discover.json", {"run_at_utc": utc_now().isoformat(), "calls": log,
                                           "series": list(out.values())})
    print(len(log), len(out))


if __name__ == "__main__":
    main()
