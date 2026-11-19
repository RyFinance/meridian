"""Fetch daily Yahoo chart histories (adjclose, close, dividends) for managed-futures fund/ETF candidates.

Raw JSON bytes are kept; a retrieval log records url, UTC time, status, sha256. No statistics computed.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data/cycle9/live_trend/yahoo_raw"
UA = "Mozilla/5.0"

TICKERS = """RYMFX RYMTX RYIFX AQMIX AQMNX QMHIX QMHNX ASFYX AMFAX PQTIX PQTPX PQTAX MHFIX MHFAX EVOIX EVOAX MFTNX MFTFX
CSAIX CSAAX GMSSX GMSAX ABYIX ABYAX AHLIX AHLPX AHLYX LOTIX LOTAX EBSIX EBSAX EQCHX ECHAX EQAIX EQAAX SKLIX SKLAX
PFFNX PFFAX AMFZX AMFQX GPFIX GPFAX WAVIX WAVEX SPTIX SPTAX FUTRX FUTCX RTSIX MFTIX MFTAX TRNIX TRNAX HMFIX NGIFX NGAFX
EBHIX SMFIX RDMIX BLNDX MBXIX ATRFX DBMF KMLM CTA WTMF WDTI FMF FUT MFUT TFPN ASMF ISMF IMF FFUT HFMF RSST RSBT CTAP
JPFP HMF.TO HHF.TO RGBM.TO""".split()


def fetch(sym: str, log):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1=0&period2=9999999999&interval=1d&events=div,split"
    for attempt in range(4):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
        except Exception as e:  # network error
            log.append({"symbol": sym, "url": url, "utc": now(), "status": f"error {e}"})
            time.sleep(5)
            continue
        if r.status_code == 429:
            time.sleep(20 * (attempt + 1))
            continue
        out = RAW / f"{sym}.json"
        out.write_bytes(r.content)
        log.append({"symbol": sym, "url": url, "utc": now(), "status": r.status_code,
                    "sha256": hashlib.sha256(r.content).hexdigest(), "bytes": len(r.content)})
        return
    log.append({"symbol": sym, "url": url, "utc": now(), "status": "gave up (429)"})


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(tickers):
    RAW.mkdir(parents=True, exist_ok=True)
    log = []
    for s in tickers:
        if (RAW / f"{s}.json").exists():
            continue
        fetch(s, log)
        time.sleep(1.5)
    lf = RAW / "_retrieval_log.jsonl"
    with lf.open("a") as f:
        for e in log:
            f.write(json.dumps(e) + "\n")
    print(json.dumps(log[-3:], indent=0))


if __name__ == "__main__":
    main(sys.argv[1:] or TICKERS)
