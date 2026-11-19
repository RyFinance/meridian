"""Cycle 8 rates / bond-yield / gold raw acquisition (research only).

Downloads every raw input to data/cycle8/raw/rates/ keeping the original bytes and
writes one record per download (URL, retrieval UTC, bytes, sha256, status) to
data/cycle8/raw/rates/_acquire_log.json. Failures are recorded and skipped; network,
sandbox and permission settings are never changed. Free sources only.

Usage:  python research/cycle8/data_rates/acquire.py [--only name1,name2]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "cycle8" / "raw" / "rates"
LOG = RAW / "_acquire_log.json"

UA = "Mozilla/5.0"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
VALET = "https://www.bankofcanada.ca/valet/observations/{s}/json"
YH = "https://{host}/v8/finance/chart/{sym}?period1=0&period2=9999999999&interval=1d&events=div,split"
KF = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"

SOURCES: dict[str, tuple[list[str], str, int]] = {
    # FRED (US yields, US bills, OECD Canada fallbacks)
    **{f"fred_{s}": ([FRED + s], f"fred_{s}.csv", 150)
       for s in ("GS10", "DGS10", "DGS20", "DGS30", "TB3MS", "DTB3",
                 "IRLTLT01CAM156N", "IR3TIB01CAM156N", "IRSTCB01CAM156N")},
    # Bank of Canada Valet
    **{f"boc_{s}": ([VALET.format(s=s)], f"boc_{s}.json", 120)
       for s in ("BD.CDN.10YR.DQ.YLD", "TB.CDN.90D.MID", "V39079", "STATIC_ATABLE_V39079",
                 "V122530", "V122531", "V122487", "V39078")},
    # Statistics Canada 10-10-0122-01 (ex-CANSIM 176-0043): BoC financial market statistics,
    # last Wednesday of month unless stated, 1934+
    "statcan_10100122": (["https://www150.statcan.gc.ca/n1/tbl/csv/10100122-eng.zip"],
                         "statcan_10100122-eng.zip", 300),
    # Shiller long rate (pre-1953 US 10Y)
    "shiller_ie_data": (["https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/downloads/ie_data.xls"],
                        "ie_data.xls", 150),
    # Ken French RF
    "kf_ff3_monthly": ([KF + "F-F_Research_Data_Factors_CSV.zip"], "F-F_Research_Data_Factors_CSV.zip", 120),
    # Damodaran annual returns (free long US 10Y T-bond reference, 1928+)
    "damodaran_histretSP": (["https://pages.stern.nyu.edu/~adamodar/pc/datasets/histretSP.xls"],
                            "damodaran_histretSP.xls", 120),
    # Gold: datahub / GitHub datasets/gold-prices (World Bank from 1960)
    "gold_monthly": (["https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"],
                     "gold_prices_monthly.csv", 90),
    "gold_datapackage": (["https://raw.githubusercontent.com/datasets/gold-prices/main/datapackage.json"],
                         "gold_prices_datapackage.json", 90),
    "gold_daily_try": (["https://raw.githubusercontent.com/datasets/gold-prices/main/data/daily.csv"],
                       "gold_prices_daily.csv", 90),
    # Yahoo daily (validation + gold daily)
    **{f"yahoo_{n}": ([YH.format(host=h, sym=s) for h in ("query1.finance.yahoo.com", "query2.finance.yahoo.com")],
                      f"yahoo_{n}.json", 90)
       for n, s in (("GC=F", "GC%3DF"), ("GLD", "GLD"), ("IEF", "IEF"), ("TLT", "TLT"),
                    ("XBB.TO", "XBB.TO"), ("ZAG.TO", "ZAG.TO"), ("VAB.TO", "VAB.TO"),
                    ("VFITX", "VFITX"), ("VUSTX", "VUSTX"))},
}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fetch(name: str, urls: list[str], fn: str, timeout: int) -> dict:
    out = RAW / fn
    rec = {"name": name, "file": str(out.relative_to(ROOT)), "attempts": []}
    for url in urls:
        t0 = dt.datetime.now(dt.timezone.utc)
        tmp = Path(os.environ.get("TMPDIR", "/tmp")) / f"c8rates_{fn}.part"
        # FRED stalls / resets on a browser-like User-Agent: send curl's default UA there.
        ua = [] if "fred.stlouisfed.org" in url else ["-A", UA]
        cp = subprocess.run(["curl", "-s", "-L", "-m", str(timeout), *ua, "-o", str(tmp),
                             "-w", "%{http_code}", url], capture_output=True, text=True)
        code = cp.stdout.strip()
        ok = cp.returncode == 0 and code == "200" and tmp.exists() and tmp.stat().st_size > 200
        rec["attempts"].append({"url": url, "retrieved_utc": t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "http": code, "curl_rc": cp.returncode,
                                "bytes": tmp.stat().st_size if tmp.exists() else 0, "ok": ok})
        if ok:
            shutil.move(str(tmp), out)
            rec.update(url=url, retrieved_utc=rec["attempts"][-1]["retrieved_utc"],
                       bytes=out.stat().st_size, sha256=_sha(out), status="ok")
            return rec
    rec["status"] = "failed"
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    log = json.loads(LOG.read_text()) if LOG.exists() else {}
    names = [n for n in SOURCES if not a.only or n in a.only.split(",")]
    for n in names:
        urls, fn, to = SOURCES[n]
        r = fetch(n, urls, fn, to)
        log[n] = r
        print(f"{n:32s} {r['status']:6s} {r.get('bytes', 0):>10}")
        LOG.write_text(json.dumps(log, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
