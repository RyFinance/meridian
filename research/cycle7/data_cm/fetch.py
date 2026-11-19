"""Cycle-7 CM data agent: raw acquisition (DATA ONLY; no signal / strategy / control / portfolio return).

Downloads, unmodified:
  * Yahoo daily OHLC + Adj Close (yfinance, auto_adjust=False) for every candidate single-commodity fund/ETN/ETC
    line and every probed-but-empty ticker (recorded as 'no free history');
  * EIA NYMEX futures bulk workbook PET_PRI_FUT_S1_D.xls (C1..C4: WTI, NYH conventional/RFG gasoline, RBOB,
    No.2 heating oil, Mont Belvieu propane; EIA stopped publishing after 2024-04-05);
  * ECB EUR/USD reference rate (for the EUR Milan ETC lines only).
Writes data/cycle7/cm/raw/* and data/cycle7/cm/raw/manifest.json (URL, retrieved_at, sha256, bytes, rows, first/last).
Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.cycle7.data_cm.fetch
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import warnings
from pathlib import Path

import pandas as pd
import requests

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "cycle7" / "cm" / "raw"
YH = RAW / "yahoo"

# every ticker probed (instruments with history AND probes that returned nothing are both recorded)
YAHOO = [
    # US single-commodity funds / ETNs (live and dead)
    "CANE", "SGG", "JO", "CAFE", "NIB", "BAL", "JJU", "FOIL", "JJN", "LD", "JJT", "COW", "LSTK", "HOGS", "UHN",
    "KEUA", "KCCA", "GRN", "NAGS", "CRUD", "SGAR", "CHOC", "CTNN", "LEDD", "NINI", "CUPM", "JJC", "OIL", "GAZ",
    "PGM", "DGL", "DBS", "BALB", "NIBB", "SGGB", "JJUB", "JJNB", "JJTB", "HEAT", "KRBN",
    # WisdomTree single-commodity ETC lines, LSE (USD)
    "COCO.L", "COFF.L", "COTN.L", "SUGA.L", "NICK.L", "ALUM.L", "ZINC.L", "HOGS.L", "CATL.L", "CARB.L",
    "TINM.L", "SOYO.L", "LEAD.L", "HEAT.L", "LHOG.L", "LCAT.L", "GASO.L", "SOYB.L", "UGAS.L",
    # WisdomTree EUR lines, Borsa Italiana (only used where no USD line has history)
    "TINM.MI", "LEAD.MI", "SOYO.MI", "HEAT.MI", "CATL.MI",
    # EUR lines of products that also have a USD LSE line (conversion-method validation only)
    "NICK.MI", "ALUM.MI", "ZINC.MI", "COFF.MI", "COTN.MI", "SUGA.MI", "HOGS.MI", "COCO.MI",
    # traded proxies of cycle-6 markets (EIA splice QA)
    "UGA",
]
EIA_URL = "https://www.eia.gov/dnav/pet/xls/PET_PRI_FUT_S1_D.xls"
ECB_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?format=csvdata&startPeriod=1999-01-01"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    import yfinance as yf
    YH.mkdir(parents=True, exist_ok=True)
    man = {"retrieved_by": "research/cycle7/data_cm/fetch.py", "files": {}, "empty_probes": {}}
    now = lambda: dt.datetime.now(dt.timezone.utc).isoformat()
    for t in YAHOO:
        try:
            tk = yf.Ticker(t)
            h = tk.history(period="max", auto_adjust=False)
            meta = {k: tk.history_metadata.get(k) for k in ("currency", "longName", "exchangeName", "instrumentType")} if len(h) else {}
        except Exception as e:  # noqa: BLE001
            h, meta = pd.DataFrame(), {"error": str(e)[:200]}
        if len(h) < 2:
            man["empty_probes"][t] = {"rows": int(len(h)), "retrieved_at": now(), **meta}
            continue
        h = h.reset_index().rename(columns={"Adj Close": "Adj_Close", "Stock Splits": "Stock_Splits",
                                            "Capital Gains": "Capital_Gains"})
        h["Date"] = h["Date"].astype(str)
        p = YH / f"{t}.parquet"
        h.to_parquet(p, index=False)
        man["files"][f"yahoo/{t}.parquet"] = {"url": f"yfinance Ticker('{t}').history(period='max', auto_adjust=False)",
                                              "retrieved_at": now(), "sha256": sha(p), "bytes": p.stat().st_size,
                                              "rows": len(h), "first": h.Date.iloc[0][:10], "last": h.Date.iloc[-1][:10], **meta}
    for name, url in (("eia/PET_PRI_FUT_S1_D.xls", EIA_URL), ("ecb_eurusd_daily.csv", ECB_URL)):
        p = RAW / name
        p.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, timeout=120, headers={"User-Agent": "quant_v7-research/1.0"})
        r.raise_for_status()
        p.write_bytes(r.content)
        man["files"][name] = {"url": url, "retrieved_at": now(), "sha256": sha(p), "bytes": p.stat().st_size}
    (RAW / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True))
    print(len(man["files"]), "files;", len(man["empty_probes"]), "empty probes")


if __name__ == "__main__":
    main()
