"""Cycle 8 data acquisition: TREND sleeve inputs and retail ETF price histories.

Raw bytes only (no processing). Writes under data/cycle8/raw/{trend,etf}/ and a
retrieval log data/cycle8/raw/retrieval_log.json (URL, UTC time, HTTP status, bytes).

Run: python -m research.cycle8.data_trend.acquire   (from repo root)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "cycle8" / "raw"
LOG = RAW / "retrieval_log_trend_etf.json"

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
YAHOO_UA = "Mozilla/5.0"  # full browser UA and curl/python UAs get HTTP 429 from Yahoo

AQR = "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/"
TREND_FILES = {
    "tsmom_factors_monthly.xlsx": AQR + "Time-Series-Momentum-Factors-Monthly.xlsx",
    "tsmom_original_paper_data.xlsx": AQR + "Time-Series-Momentum-Original-Paper-Data.xlsx",
    "ff_research_data_factors_csv.zip":
        "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip",
}

# Yahoo symbols. Each entry: canonical name -> list of symbols to try in order.
ETFS: dict[str, list[str]] = {
    # Canadian asset-allocation / equity
    "XEQT.TO": ["XEQT.TO"], "VEQT.TO": ["VEQT.TO"], "ZEQT.TO": ["ZEQT.TO"],
    "XGRO.TO": ["XGRO.TO"], "VGRO.TO": ["VGRO.TO"], "VBAL.TO": ["VBAL.TO"], "XBAL.TO": ["XBAL.TO"],
    "HXT.TO": ["HXT.TO"], "XIC.TO": ["XIC.TO"], "XUS.TO": ["XUS.TO"], "XEF.TO": ["XEF.TO"],
    "XEC.TO": ["XEC.TO"], "VFV.TO": ["VFV.TO"], "ZSP.TO": ["ZSP.TO"],
    # Canadian bonds
    "ZAG.TO": ["ZAG.TO"], "XBB.TO": ["XBB.TO"], "VAB.TO": ["VAB.TO"],
    # Canadian gold
    "ZGLD.TO": ["ZGLD.TO"], "CGL-C.TO": ["CGL-C.TO", "CGL.TO"], "MNT.TO": ["MNT.TO"],
    # Canadian levered / capital-efficient / managed futures candidates
    "HQU.TO": ["HQU.TO"], "HSU.TO": ["HSU.TO"], "HXU.TO": ["HXU.TO"],
    "USSL.TO": ["USSL.TO"], "CASH.TO": ["CASH.TO"], "HISA.TO": ["HISA.TO"],
    "QQU.TO": ["QQU.TO"], "CANL.TO": ["CANL.TO"],
    "DBMF.NE": ["DBMF.NE"],
    "SPXU.TO": ["SPXU.TO"], "CNDU.TO": ["CNDU.TO"], "HEQL.TO": ["HEQL.TO"],
    "RGBM.TO": ["RGBM.TO"], "RGBM-U.TO": ["RGBM-U.TO"],
    # US managed futures
    "DBMF": ["DBMF"], "KMLM": ["KMLM"], "CTA": ["CTA"], "AQMIX": ["AQMIX"], "PQTIX": ["PQTIX"],
    "ASFYX": ["ASFYX"], "WTMF": ["WTMF"], "FMF": ["FMF"], "FFUT": ["FFUT"],
    # US capital-efficient / levered
    "NTSX": ["NTSX"], "NTSI": ["NTSI"], "NTSE": ["NTSE"], "RSSB": ["RSSB"], "RSST": ["RSST"],
    "RSBT": ["RSBT"], "GDE": ["GDE"], "SSO": ["SSO"], "UPRO": ["UPRO"], "UBT": ["UBT"], "TMF": ["TMF"],
    # US plain
    "SPY": ["SPY"], "VT": ["VT"], "VTI": ["VTI"], "VXUS": ["VXUS"], "TLT": ["TLT"], "IEF": ["IEF"],
    "GLD": ["GLD"], "GLDM": ["GLDM"], "IAU": ["IAU"],
}


def _log(entries: list[dict]) -> None:
    old = json.loads(LOG.read_text()) if LOG.exists() else []
    LOG.write_text(json.dumps(old + entries, indent=1))


def curl(url: str, out: Path, ua: str) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["curl", "-sL", "-m", "90", "-A", ua, "-o", str(out), "-w",
                        "%{http_code} %{content_type}", url], capture_output=True, text=True)
    code, _, ctype = r.stdout.partition(" ")
    return {"url": url, "file": str(out), "http": code, "content_type": ctype,
            "bytes": out.stat().st_size if out.exists() else 0,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def yahoo_url(sym: str) -> str:
    return (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
            "?period1=0&period2=9999999999&interval=1d&events=div,split")


def acquire_trend() -> None:
    es = [curl(u, RAW / "trend" / f, BROWSER_UA) for f, u in TREND_FILES.items()]
    for e in es:
        e["file"] = str(Path(e["file"]).relative_to(ROOT))
    _log(es)


# Downloaded in the first pass (2026-09-27) by mistaken guesses, kept as raw but not processed:
# EQL.TO (CI Invesco S&P 500 Equal Weight), HUBL.TO (Harvest US Bank Leaders Income), MFT.TO (Mackenzie
# Floating Rate Income). Not relevant to the menu.


def acquire_etfs(only: list[str] | None = None) -> None:
    entries = []
    for name, syms in ETFS.items():
        if only and name not in only:
            continue
        for s in syms:
            tmp = Path(os.environ.get("TMPDIR", "/tmp")) / f"yahoo_{name}.json"
            out = RAW / "etf" / f"{name}.json"
            e = curl(yahoo_url(s), tmp, YAHOO_UA)
            e["file"] = str(out.relative_to(ROOT))
            e.update(name=name, symbol=s)
            ok = False
            if e["http"] == "200":
                try:
                    res = json.loads(tmp.read_text())["chart"]["result"]
                    ok = bool(res and res[0].get("timestamp"))
                except Exception:
                    ok = False
            e["ok"] = ok
            entries.append(e)
            time.sleep(0.6)
            if ok:  # only successful responses are kept as raw bytes (no deletions in repo)
                shutil.copyfile(tmp, out)
                break
            e["file"] = None
            e["error_body"] = tmp.read_text()[:300] if tmp.exists() else ""
    _log(entries)


def acquire_fund_profiles() -> None:
    """Yahoo quoteSummary fundProfile/defaultKeyStatistics (expense ratio, inception). Needs cookie+crumb."""
    tmp = Path(os.environ.get("TMPDIR", "/tmp"))
    jar = tmp / "yahoo_cookies.txt"
    subprocess.run(["curl", "-s", "-A", YAHOO_UA, "-c", str(jar), "-o", "/dev/null", "https://fc.yahoo.com"])
    crumb = subprocess.run(["curl", "-s", "-A", YAHOO_UA, "-b", str(jar),
                            "https://query1.finance.yahoo.com/v1/test/getcrumb"],
                           capture_output=True, text=True).stdout.strip()
    entries = []
    for name in ETFS:
        if not (RAW / "etf" / f"{name}.json").exists():
            continue
        sym = json.loads((RAW / "etf" / f"{name}.json").read_text())["chart"]["result"][0]["meta"]["symbol"]
        url = (f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{sym}"
               "?modules=fundProfile,defaultKeyStatistics,quoteType")
        out = RAW / "etf" / "quotesummary" / f"{name}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["curl", "-s", "-m", "60", "-A", YAHOO_UA, "-b", str(jar), "-o", str(out),
                            "-w", "%{http_code}", url + f"&crumb={crumb}"], capture_output=True, text=True)
        entries.append({"name": name, "url": url + "&crumb=<session>", "file": str(out.relative_to(ROOT)),
                        "http": r.stdout, "bytes": out.stat().st_size,
                        "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        time.sleep(0.5)
    _log(entries)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["profiles"]:
        acquire_fund_profiles()
    elif len(sys.argv) > 1:  # e.g. python -m ...acquire SPXU.TO CNDU.TO
        acquire_etfs(sys.argv[1:])
    else:
        acquire_trend()
        acquire_etfs()
        acquire_fund_profiles()
