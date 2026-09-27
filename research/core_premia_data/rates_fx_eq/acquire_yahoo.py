"""Keyless Yahoo Finance chart-API ingest (raw JSON per ticker): equity index levels (mostly
price-only), total-return indices where Yahoo carries them, country equity ETFs (adjusted close
includes distributions), government-bond ETFs, currency ETFs, CME continuous front-month futures
(unadjusted roll jumps -- used only as an overlap check), and ^IRX.

Caveats recorded in the completeness record: Yahoo adjusted closes are re-based retroactively at
every new distribution (not point-in-time as stored, although the implied returns are); index bars
are exchange-local closes; continuous futures carry unadjusted roll gaps.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.core_premia_data.rates_fx_eq.acquire_yahoo
"""
from __future__ import annotations

import json
import time
import urllib.parse

from research.core_premia_data.rates_fx_eq.common import META, fetch, utc_now, write_json

CHART = "https://query2.finance.yahoo.com/v8/finance/chart/{t}"

TICKERS = {
    "index_price": "^GSPC ^NDX ^DJI ^RUT ^GSPTSE ^FTSE ^FTMC ^FCHI FTSEMIB.MI ^IBEX ^AEX ^SSMI ^STOXX50E "
                   "^N225 ^HSI ^AXJO ^AORD ^KS11 ^TWII ^BVSP ^MXX ^BSESN ^NSEI 000001.SS ^STI ^JKSE ^KLSE "
                   "^OMX ^BFX ^ATX ^NZ50 XU100.IS ^MERV ^TA125.TA".split(),
    "index_tr": "^SP500TR ^GDAXI".split(),  # ^GDAXI = DAX performance (gross total-return) index
    "etf_equity": "SPY QQQ DIA IWM EFA EEM EWJ EWG EWU EWC EWA EWQ EWI EWP EWL EWN EWD EWH EWS EWK EWO EWW "
                  "EWZ EWY EWT EZA FXI MCHI INDA EWM EIS TUR ENZL EDEN ENOR EPOL".split(),
    "etf_bond": "SHY IEI IEF TLH TLT GOVT BWX IGOV IGLT.L IBGM.AS EXHD.DE EXHB.DE 2510.T 2561.T XGB.TO "
                "ZFL.TO XBB.TO IGB.AX CSBGC0.SW".split(),
    "etf_fx": "FXE FXY FXB FXA FXC FXF UUP".split(),
    "future_cont": "ES=F NQ=F YM=F RTY=F NKD=F ZN=F ZB=F ZF=F ZT=F 6E=F 6J=F 6B=F 6A=F 6C=F 6S=F 6N=F 6M=F".split(),
    "rate": ["^IRX"],
}


def _valid(body: bytes):
    try:
        d = json.loads(body)
        res = d["chart"]["result"][0]
        n = len(res.get("timestamp") or [])
    except Exception as e:  # noqa: BLE001
        return False, f"bad chart json: {e!r}"[:120]
    return n > 0, f"{n} bars"


def safe(t: str) -> str:
    return t.replace("^", "IDX_").replace("=", "_EQ_").replace(".", "_")


def run(only: list[str] | None = None) -> dict:
    period2 = int(time.time())
    out = {}
    for kind, ticks in TICKERS.items():
        for t in ticks:
            if only and t not in only:
                continue
            url = (CHART.format(t=urllib.parse.quote(t)) +
                   f"?period1=-2208988800&period2={period2}&interval=1d&events=div%7Csplit&includeAdjustedClose=true")
            r = fetch("yahoo_chart", safe(t), url, ext="json", validate=_valid, retries=6, backoff=2.0)
            out[t] = {"kind": kind, "ok": r is not None, "url": url, "raw_path": r["path"] if r else None,
                      "sha256": r["sha256"] if r else None, "fetched_at_utc": r["fetched_at_utc"] if r else None,
                      "attempt": r.get("attempt") if r else None}
            time.sleep(0.4)
    prev = {}
    p = META / "acquire_yahoo_results.json"
    if p.exists():
        prev = json.loads(p.read_text()).get("results", {})
    prev.update(out)
    write_json(p, {"run_at_utc": utc_now().isoformat(), "results": prev})
    return out


if __name__ == "__main__":
    import sys
    res = run(sys.argv[1:] or None)
    print({k: v["ok"] for k, v in res.items()})
