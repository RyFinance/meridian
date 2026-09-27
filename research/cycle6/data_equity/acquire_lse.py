"""Read-only LSE Terminal ingest via the local engine REST API (GET only), DATA ONLY.

The MCP stdio bridge (research.lse_mcp_client) cannot launch the app from inside the command
sandbox (3 consecutive 'open -b' failures, recorded); the MCP tools themselves were confirmed
working (terminal_status, search_instruments, get_history) and they wrap this same engine.
Endpoints used (GET only): /api/candles, /api/macro/series, /api/economic-calendar.
No order/position/algo route is touched. Stops after 3 consecutive failures.

Run (needs localhost access): PYTHONPATH=. .venv/bin/python -m research.cycle6.data_equity.acquire_lse
"""
from __future__ import annotations

import json
import urllib.parse

from research.cycle6.data_equity.common import META, fetch, utc_now, write_json

ENGINE = "http://127.0.0.1:7799"
INDEX = ["SPX500/USD", "NAS100/USD", "US30/USD", "US2000/USD", "DE30/EUR", "UK100/GBP", "UK250/GBP", "EU50/EUR",
         "FR40/EUR", "IT40/EUR", "ES35/EUR", "NL30/EUR", "CH20/CHF", "HK33/HKD", "JP225/USD", "AU200/AUD", "CN50/USD"]
CPI = {"US": "unitedstaconpriindcp", "CA": "canadaconpriindcpi", "UK": "unitedkinconpriindcp",
       "DE": "germanyconpriindcpi", "FR": "franceconpriindcpi", "IT": "italyconpriindcpi", "ES": "spainconpriindcpi",
       "NL": "netherlandconpriindc", "BE": "belgiumconpriindcpi", "AT": "austriaconpriindcpi",
       "CH": "switzerlanconpriindc", "SE": "swedenconpriindcpi", "NO": "norwayconpriindcpi", "DK": "denmarkconpriindcpi",
       "JP": "japanconpriindcpi", "AU": "australiaconpriindcp", "NZ": "newzealanconpriindcp",
       "HK": "hongkongconpriindcpi", "SG": "singaporeconpriindcp", "KR": "southkoreconpriindcp",
       "TW": "taiwanconpriindcpi", "IN": "indiaconpriindcpi", "BR": "brazilconpriindcpi", "MX": "mexicoconpriindcpi",
       "ZA": "southafriconpriindcp", "CN": "chinaconpriindcpi", "MY": "malaysiaconpriindcpi", "ID": "indonesiaconpriindcp",
       "TR": "turkeyconpriindcpi", "PL": "polandconpriindcpi", "IL": "israelconpriindcpi", "TH": "thailandconpriindcpi"}


def _jv(key):
    def v(body: bytes):
        try:
            d = json.loads(body)
        except Exception as e:  # noqa: BLE001
            return False, f"no data: {e!r}"[:100]
        rows = d.get(key) if isinstance(d, dict) else d
        n = len(rows or [])
        return n > 0, f"{n} rows" if n else "no data"
    return v


def run() -> dict:
    out = {"run_at_utc": utc_now().isoformat(), "engine": ENGINE, "candles": {}, "cpi": {}, "calendar": {},
           "consecutive_fail_stop": False}
    fails = 0

    def get(kind, name, path, q, key):
        nonlocal fails
        if fails >= 3:
            out["consecutive_fail_stop"] = True
            return None
        url = ENGINE + path + "?" + urllib.parse.urlencode(q)
        r = fetch("lse_engine", name, url, ext="json", validate=_jv(key), retries=2)
        fails = 0 if r else fails + 1
        out[kind][name] = {"ok": r is not None, "url": url, "path": r["path"] if r else None,
                           "fetched_at_utc": r["fetched_at_utc"] if r else None}
        return r

    import datetime as _dt
    from research.collectors import common as cc
    from research.cycle6.data_equity.common import RAW
    for s in INDEX:  # the engine returns at most 5000 bars from `start`: page forward until short page
        start, page = "1990-01-01", 0
        while True:
            r = get("candles", f"{s.replace('/', '_')}_p{page}", "/api/candles",
                    {"provider": "lse", "symbol": s, "timeframe": "1d", "start": start, "end": "2026-09-26",
                     "limit": 5000}, "candles")
            if r is None:
                break
            c = json.loads((RAW / r["path"]).read_bytes())["candles"]
            if len(c) < 5000:
                break
            start = (_dt.datetime.fromtimestamp(c[-1][0], _dt.timezone.utc) + _dt.timedelta(days=1)).strftime("%Y-%m-%d")
            page += 1
    for c, sym in CPI.items():
        get("cpi", c, "/api/macro/series", {"symbol": sym, "start": "1900-01-01", "end": "2026-09-26",
                                            "order": "asc", "limit": 5000}, None)
    get("calendar", "CPI_released", "/api/economic-calendar",
        {"event": "CPI", "released": 1, "order": "asc", "limit": 20000, "start": "2000-01-01", "end": "2026-09-26"}, None)
    write_json(META / "acquire_lse_results.json", out)
    return out


if __name__ == "__main__":
    o = run()
    print(json.dumps({k: {n: v["ok"] for n, v in o[k].items()} for k in ("candles", "cpi", "calendar")}),
          o["consecutive_fail_stop"])
