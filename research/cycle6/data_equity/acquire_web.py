"""Keyless web ingest for cycle-6 equity/macro data (DATA ONLY).

1. Yahoo chart API: equity index tickers NOT already in the frozen acquisition snapshot
   core_premia_rates_fx_eq_acq_v1 (total-return indices first, then extra price indices).
   Tickers already in that snapshot are reused from data/core_premia/rates_fx_eq (not re-pulled).
2. OECD SDMX DF_PRICES_ALL: CPI all-items index (2015=100), monthly and quarterly, not SA,
   all areas (for FX PPP value). Latest vintage only (no real-time vintages exist keylessly).

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.cycle6.data_equity.acquire_web
"""
from __future__ import annotations

import json
import time
import urllib.parse

from research.cycle6.data_equity.common import META, fetch, utc_now, write_json

CHART = "https://query2.finance.yahoo.com/v8/finance/chart/{t}"
# kind declared a priori from index methodology (vendor docs), not from data
YAHOO_NEW = {
    # total-return (gross/performance) indices, local currency
    "OSEBX.OL": "index_tr",   # Oslo Bors Benchmark Index (total return)
    "^SSHI": "index_tr",      # Swiss Performance Index SPI (total return)
    "^XNDX": "index_tr",      # Nasdaq-100 total return
    "^TX60": "index_price",
    "^J203.JO": "index_price", "^J200.JO": "index_price", "^TOPX": "index_price",
    "^OMXC25": "index_price", "^OMXH25": "index_price", "^OMXSPI": "index_price", "^OSEAX": "index_price",
    "^HSCE": "index_price", "^KS200": "index_price", "^CNXNIFTY": "index_price", "^IPSA": "index_price",
    "^SET.BK": "index_price", "^PSEI.PS": "index_price", "^ISEQ": "index_price", "PSI20.LS": "index_price",
    "^FTAS": "index_price", "000300.SS": "index_price", "^WIG20": "index_price",
    "^FTLC": "index_price", "^SPTSXTR": "index_tr",
}
# country ETFs not in the prior snapshot (dividend-yield source / tier-3 construction / QA proxy)
YAHOO_ETF = {"EFNL": "etf_equity", "EIRL": "etf_equity", "THD": "etf_equity", "EIDO": "etf_equity",
             "ECH": "etf_equity"}


def _yv(body: bytes):
    try:
        res = json.loads(body)["chart"]["result"][0]
        n = len(res.get("timestamp") or [])
    except Exception as e:  # noqa: BLE001
        return False, f"no data: {e!r}"[:120]
    return n > 0, f"{n} bars"


def _csv(min_rows):
    def v(body: bytes):
        n = body.count(b"\n")
        return n >= min_rows, f"{n} rows"
    return v


OECD_CPI = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/"
            ".{f}.N.CPI.IX._T.N._Z?startPeriod=1950-01&dimensionAtObservation=AllDimensions&format=csvfilewithlabels")


def run(part: str = "all") -> dict:
    out = {"run_at_utc": utc_now().isoformat(), "yahoo": {}, "oecd_cpi": {}}
    p2 = int(time.time())
    todo = {**({} if part == "etf" else YAHOO_NEW), **YAHOO_ETF}
    for t, kind in todo.items():
        url = CHART.format(t=urllib.parse.quote(t)) + (
            f"?period1=-2208988800&period2={p2}&interval=1d&events=div%7Csplit&includeAdjustedClose=true")
        r = fetch("yahoo_chart", t.replace("^", "IDX_").replace(".", "_"), url, ext="json", validate=_yv, retries=3)
        out["yahoo"][t] = {"kind": kind, "ok": r is not None, "url": url, "path": r["path"] if r else None,
                           "fetched_at_utc": r["fetched_at_utc"] if r else None}
        time.sleep(0.4)
    for f in (() if part == "etf" else ("M", "Q")):
        url = OECD_CPI.format(f=f)
        r = fetch("oecd_sdmx", f"DF_PRICES_ALL_CPI_{f}", url, ext="csv", validate=_csv(100), timeout=300)
        out["oecd_cpi"][f] = {"ok": r is not None, "url": url, "path": r["path"] if r else None,
                              "fetched_at_utc": r["fetched_at_utc"] if r else None}
    write_json(META / f"acquire_web_results{'' if part == 'all' else '_' + part}.json", out)
    return out


if __name__ == "__main__":
    import sys
    o = run(sys.argv[1] if len(sys.argv) > 1 else "all")
    print({k: v["ok"] for k, v in o["yahoo"].items()}, o["oecd_cpi"])
