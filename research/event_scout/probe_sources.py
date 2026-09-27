"""Event-data scout: small, polite feasibility probes of free event-family sources.

No strategy return is computed here. This only checks:
- whether a free endpoint is reachable with a polite, no-email User-Agent
  (per the workload-D instruction: "quant_v7-research/1.0", NO email address);
- the shape/timestamp precision of what it returns;
- a rough event count where cheap to obtain.

Outputs go to data/event_scout/ (raw small samples) and reports/event_scout/probe_log.json
(the manifest of what was fetched, when, and the outcome). Nothing here is committed or pushed.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "event_scout"
REPORT_DIR = ROOT / "reports" / "event_scout"
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS_NO_EMAIL = {"User-Agent": "quant_v7-research/1.0"}
TIMEOUT = 15
SLEEP_BETWEEN = 1.0

log = []


def record(name, url, headers, note=""):
    entry = {
        "name": name,
        "url": url,
        "headers_sent": headers,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
        entry["status_code"] = resp.status_code
        entry["content_length_bytes"] = len(resp.content)
        entry["content_type"] = resp.headers.get("Content-Type")
        entry["ok"] = resp.ok
        entry["note"] = note
        if resp.ok:
            # keep only a small sample on disk
            ext = "json" if "json" in (resp.headers.get("Content-Type") or "") else "txt"
            sample_path = DATA_DIR / f"{name}.{ext}"
            content = resp.content[:20000]  # cap sample size
            sample_path.write_bytes(content)
            entry["sample_saved"] = str(sample_path.relative_to(ROOT))
            entry["sample_bytes_saved"] = len(content)
        else:
            entry["body_snippet"] = resp.text[:500]
    except Exception as exc:  # noqa: BLE001
        entry["ok"] = False
        entry["error"] = repr(exc)
        entry["note"] = note
    log.append(entry)
    print(f"{name}: ok={entry.get('ok')} status={entry.get('status_code')} err={entry.get('error','')}")
    time.sleep(SLEEP_BETWEEN)
    return entry


# 1. SEC EDGAR submissions API (no-email UA per instruction; SEC's own policy asks for an
#    email-bearing UA, so this tests exactly that friction point).
record(
    "sec_edgar_submissions_aapl",
    "https://data.sec.gov/submissions/CIK0000320193.json",
    HEADERS_NO_EMAIL,
    "SEC asks for an email in the UA (sec.gov/os/webmaster-faq#developers); we deliberately omit it per instructions.",
)

# 2. SEC EDGAR full text search (same UA policy applies)
record(
    "sec_edgar_fts_8k_402",
    "https://efts.sec.gov/LATEST/search-index?q=%22non-reliance%22&forms=8-K&dateRange=custom&startdt=2026-01-01&enddt=2026-01-31",
    HEADERS_NO_EMAIL,
    "Full text search, item 4.02 non-reliance proxy query, Jan 2026 only.",
)

# 3. Binance USD-M perpetuals funding rate history (public, no key)
record(
    "binance_funding_btcusdt",
    "https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=5",
    HEADERS_NO_EMAIL,
    "Funding rate history, most recent 5 settlements.",
)

# 4. Binance USD-M exchange info (to count live perpetual symbols)
record(
    "binance_exchangeinfo",
    "https://fapi.binance.com/fapi/v1/exchangeInfo",
    HEADERS_NO_EMAIL,
    "To count TRADING PERPETUAL symbols for 8h funding cross-section size.",
)

# 5. Nasdaq Reg SHO threshold list, today's file (may 404 on weekends/holidays; that's expected)
today = datetime.now().strftime("%Y%m%d")
record(
    "nasdaq_regsho_threshold_today",
    f"https://www.nasdaqtrader.com/dynamic/SymDir/regsho/nasdaqth{today}.txt",
    HEADERS_NO_EMAIL,
    "Daily Reg SHO threshold list, today's date; expect possible 404 if markets closed/not yet posted.",
)

# 6. OCC daily open interest CSV download
record(
    "occ_daily_open_interest",
    "https://marketdata.theocc.com/daily-open-interest?reportDate=09/23/2026&action=download&format=csv",
    HEADERS_NO_EMAIL,
    "Free daily OI by OCC; WebFetch tool got 403 on the info page, testing direct CSV endpoint with curl-equivalent UA.",
)

# 7. FINRA Reg SHO daily short volume file (for cross-reference/context only; other agent's territory,
#    but useful to confirm the exact file naming/timestamp convention noted in data_scout report)
record(
    "finra_regsho_daily_shortvol",
    f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{today}.txt",
    HEADERS_NO_EMAIL,
    "Cross-check only; FINRA/short-volume territory belongs to another workload agent.",
)

REPORT_DIR.joinpath("probe_log.json").write_text(json.dumps(log, indent=2))
print("\nWrote", REPORT_DIR / "probe_log.json")
