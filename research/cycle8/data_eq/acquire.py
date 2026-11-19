"""Cycle 8 equity / FX / CPI raw acquisition (research only).

Downloads every raw input to data/cycle8/raw/eq/ keeping the original bytes and
appends one record per download (URL, retrieval UTC, bytes, sha256, status) to
data/cycle8/raw/eq/_acquire_log.json. Failures are recorded, never retried with
changed network/sandbox settings.

Usage:  python research/cycle8/data_eq/acquire.py [--only name1,name2]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "cycle8" / "raw" / "eq"
LOG = RAW / "_acquire_log.json"

UA_CHROME = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
UA_SHORT = "Mozilla/5.0"

KF = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
YH = "https://{host}/v8/finance/chart/{sym}?period1=0&period2=9999999999&interval=1d&events=div,split"
MSCI = ("https://app2.msci.com/products/service/index/indexmaster/getLevelDataForGraph?"
        "currency_symbol=USD&index_variant={var}&start_date=19970101&end_date={end}"
        "&data_frequency={freq}&index_codes={code}")
VALET = "https://www.bankofcanada.ca/valet/observations/{s}/csv"

TODAY = dt.date.today().strftime("%Y%m%d")

# name -> (list of candidate URLs, filename, timeout seconds)
SOURCES: dict[str, tuple[list[str], str, int]] = {
    # Ken French
    "kf_ff3_monthly": ([KF + "F-F_Research_Data_Factors_CSV.zip"], "F-F_Research_Data_Factors_CSV.zip", 120),
    "kf_ff3_daily": ([KF + "F-F_Research_Data_Factors_daily_CSV.zip"], "F-F_Research_Data_Factors_daily_CSV.zip", 120),
    "kf_intl_countries": ([KF + "F-F_International_Countries.zip"], "F-F_International_Countries.zip", 120),
    "kf_intl_indices": ([KF + "F-F_International_Indices.zip"], "F-F_International_Indices.zip", 120),
    "kf_emerging_5f": ([KF + "Emerging_5_Factors_CSV.zip"], "Emerging_5_Factors_CSV.zip", 120),
    "kf_devexus_3f": ([KF + "Developed_ex_US_3_Factors_CSV.zip"], "Developed_ex_US_3_Factors_CSV.zip", 120),
    "kf_europe_3f": ([KF + "Europe_3_Factors_CSV.zip"], "Europe_3_Factors_CSV.zip", 120),
    "kf_japan_3f": ([KF + "Japan_3_Factors_CSV.zip"], "Japan_3_Factors_CSV.zip", 120),
    "kf_apxj_3f": ([KF + "Asia_Pacific_ex_Japan_3_Factors_CSV.zip"], "Asia_Pacific_ex_Japan_3_Factors_CSV.zip", 120),
    "kf_europe_3f_daily": ([KF + "Europe_3_Factors_Daily_CSV.zip"], "Europe_3_Factors_Daily_CSV.zip", 120),
    "kf_japan_3f_daily": ([KF + "Japan_3_Factors_Daily_CSV.zip"], "Japan_3_Factors_Daily_CSV.zip", 120),
    "kf_apxj_3f_daily": ([KF + "Asia_Pacific_ex_Japan_3_Factors_Daily_CSV.zip"], "Asia_Pacific_ex_Japan_3_Factors_Daily_CSV.zip", 120),
    "kf_intl_index_detail": (["https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/int_index_port_formed.html"],
                             "kf_int_index_port_formed.html", 60),
    # Shiller
    "shiller_ie_data": (["https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/downloads/ie_data.xls"],
                        "ie_data.xls", 120),
    # MSCI (validation, 2000-12+ as served)
    **{f"msci_{c}_{v}_{f}": ([MSCI.format(var=v, end=TODAY, freq=fq, code=c)], f"msci_{c}_{v}_{f}.json", 120)
       for c in ("990300", "990100", "891800", "984000")
       for v in ("GRTR", "NETR")
       for f, fq in (("m", "END_OF_MONTH"), ("d", "DAILY"))},
    # FRED
    **{f"fred_{s}": ([FRED + s], f"fred_{s}.csv", 150)
       for s in ("DEXCAUS", "EXCAUS", "CPIAUCNS", "CPALCY01CAM661N", "CANCPIALLMINMEI")},
    # Federal Reserve H.10 full release package (source of FRED DEXCAUS: RXI_N.B.CA daily noon NY buying rate)
    "frb_h10_zip": (["https://www.federalreserve.gov/datadownload/Output.aspx?rel=H10&filetype=zip"], "frb_H10.zip", 300),
    # Bank of Canada Valet (FX validation)
    "boc_FXUSDCAD": ([VALET.format(s="FXUSDCAD")], "boc_FXUSDCAD.csv", 90),
    "boc_IEXE0101": ([VALET.format(s="IEXE0101")], "boc_IEXE0101.csv", 90),
    "boc_FXMUSDCAD": ([VALET.format(s="FXMUSDCAD")], "boc_FXMUSDCAD.csv", 90),
    # StatCan CPI table 18-10-0004 (full table zip via WDS redirect target)
    "statcan_18100004": (["https://www150.statcan.gc.ca/n1/tbl/csv/18100004-eng.zip"], "statcan_18100004-eng.zip", 300),
    # Yahoo daily
    **{f"yahoo_{n}": ([YH.format(host=h, sym=s) for h in ("query2.finance.yahoo.com", "query1.finance.yahoo.com")],
                      f"yahoo_{n}.json", 90)
       for n, s in (("GSPTSE", "%5EGSPTSE"), ("EFA", "EFA"), ("EEM", "EEM"), ("SPY", "SPY"),
                    ("XIC.TO", "XIC.TO"), ("CADX", "CAD%3DX"))},
}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _curl(url: str, out: Path, timeout: int, ua: str) -> tuple[int, str]:
    r = subprocess.run(["curl", "-sS", "-L", "-m", str(timeout), "-A", ua, "-o", str(out),
                        "-w", "%{http_code}", url], capture_output=True, text=True)
    return r.returncode, (r.stdout.strip() + " " + r.stderr.strip()).strip()


def _looks_ok(name: str, p: Path) -> bool:
    if not p.exists() or p.stat().st_size < 200:
        return False
    head = p.read_bytes()[:400]
    if b"Too Many Requests" in head or b"<html" in head.lower() and not name.startswith("kf_intl_index_detail"):
        return False
    if name.startswith("msci_") and b"error_code" in head:
        return False
    return True


def fetch(name: str) -> dict:
    urls, fname, timeout = SOURCES[name]
    out = RAW / fname
    tmp = out.with_suffix(out.suffix + ".part")
    rec = {"name": name, "file": str(out.relative_to(ROOT)), "attempts": []}
    for url in urls:
        for ua in (UA_SHORT, UA_CHROME):
            for attempt in range(2):
                t = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                rc, info = _curl(url, tmp, timeout, ua)
                ok = rc == 0 and _looks_ok(name, tmp)
                rec["attempts"].append({"url": url, "ua": ua, "utc": t, "rc": rc, "info": info, "ok": ok})
                if ok:
                    tmp.replace(out)
                    rec.update(status="ok", url=url, retrieved_utc=t, bytes=out.stat().st_size, sha256=_sha(out))
                    return rec
                time.sleep(3)
    if tmp.exists():
        # keep failure body for inspection, never overwrite a good file
        tmp.replace(out.with_suffix(out.suffix + ".failed"))
    rec["status"] = "failed"
    return rec


# BLS public API v1 (no key; <=10 years per request): US CPI-U all items NSA, used because FRED CPIAUCNS timed out
BLS_SERIES = "CUUR0000SA0"
BLS_CHUNKS = [(y, min(y + 9, dt.date.today().year)) for y in range(1913, dt.date.today().year + 1, 10)]
BLS_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"


def fetch_bls(y0: int, y1: int) -> dict:
    name = f"bls_{BLS_SERIES}_{y0}_{y1}"
    out = RAW / f"{name}.json"
    body = json.dumps({"seriesid": [BLS_SERIES], "startyear": str(y0), "endyear": str(y1)})
    t = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = subprocess.run(["curl", "-sS", "-m", "90", "-A", UA_SHORT, "-H", "Content-Type: application/json",
                        "-X", "POST", "-d", body, "-o", str(out) + ".part", BLS_URL], capture_output=True, text=True)
    part = Path(str(out) + ".part")
    ok = r.returncode == 0 and part.exists() and b"REQUEST_SUCCEEDED" in part.read_bytes()[:200]
    rec = {"name": name, "file": str(out.relative_to(ROOT)), "url": BLS_URL + " POST " + body, "attempts": [
        {"utc": t, "rc": r.returncode, "info": r.stderr.strip(), "ok": ok}]}
    if ok:
        part.replace(out)
        rec.update(status="ok", retrieved_utc=t, bytes=out.stat().st_size, sha256=_sha(out))
    else:
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
        rec = fetch(n)
        log[n] = rec
        print(f"{n:32s} {rec['status']:6s} {rec.get('bytes', '')}")
        LOG.write_text(json.dumps(log, indent=1))
        if n.startswith("yahoo_"):
            time.sleep(2)
    for y0, y1 in BLS_CHUNKS:
        n = f"bls_{BLS_SERIES}_{y0}_{y1}"
        if a.only and "bls" not in a.only.split(","):
            continue
        rec = fetch_bls(y0, y1)
        log[n] = rec
        print(f"{n:32s} {rec['status']:6s} {rec.get('bytes', '')}")
        LOG.write_text(json.dumps(log, indent=1))
        time.sleep(1)


if __name__ == "__main__":
    main()
