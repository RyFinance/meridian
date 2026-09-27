"""New structural-information scout (cycle 5, Program D): coverage-only probes.

Rules honoured here:
- keyless, User-Agent "quant_v7-research/1.0", no email, no accounts;
- only coverage is computed (first/last dates, counts, symbol/series presence). No returns, no signal statistics,
  no signal->return relationships. Values are never summarised;
- small samples to data/new_info_scout/, total well under 300 MB, with a manifest (URL, status, bytes, sha256, UTC).

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.new_info_scout.probe
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import pathlib
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "new_info_scout"
OUT = ROOT / "reports" / "new_info_scout"
UA = {"User-Agent": "quant_v7-research/1.0"}
MANIFEST: list[dict] = []
COVERAGE: dict[str, dict] = {}


def fetch(url: str, save: str | None = None, timeout: int = 60, max_bytes: int = 60_000_000) -> bytes | None:
    rec = {"url": url, "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            body = r.read(max_bytes + 1)
            rec["status"] = r.status
    except urllib.error.HTTPError as e:
        rec["status"], body = e.code, None
    except Exception as e:  # network / sandbox / timeout
        rec["status"], rec["error"], body = None, f"{type(e).__name__}: {e}"[:200], None
    if body is not None:
        rec["bytes"] = len(body)
        rec["truncated"] = len(body) > max_bytes
        rec["sha256"] = hashlib.sha256(body).hexdigest()
        if save:
            p = DATA / save
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(body)
            rec["saved_as"] = str(p.relative_to(ROOT))
    MANIFEST.append(rec)
    time.sleep(0.3)
    return body


# ------------------------------------------------------------------------------------------ 1. NY Fed PD stats
def nyfed_primary_dealer() -> None:
    """Coverage of the weekly FR 2004 primary-dealer statistics (positions, financing, fails), keyless API."""
    p = DATA / "nyfed_pd" / "pd_all_timeseries.csv"
    if p.exists():
        body = p.read_bytes()
        MANIFEST.append({"url": "https://markets.newyorkfed.org/api/pd/get/all/timeseries.csv",
                         "status": 200, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                         "saved_as": str(p.relative_to(ROOT)), "note": "fetched earlier this session by curl"})
    else:
        body = fetch("https://markets.newyorkfed.org/api/pd/get/all/timeseries.csv", "nyfed_pd/pd_all_timeseries.csv",
                     timeout=300, max_bytes=150_000_000)
    fetch("https://markets.newyorkfed.org/api/pd/list/seriesbreaks.json", "nyfed_pd/seriesbreaks.json")
    fetch("https://markets.newyorkfed.org/api/pd/list/timeseries.json", "nyfed_pd/timeseries_list.json")
    first, last, n = {}, {}, {}
    rd = csv.reader(io.StringIO(body.decode()))
    next(rd)
    for d, k, _v in rd:           # value column deliberately ignored
        n[k] = n.get(k, 0) + 1
        first[k] = min(first.get(k, d), d)
        last[k] = max(last.get(k, d), d)
    # Treasury coupon net outright position chain across the series breaks (identifiers only)
    chain = {
        "1998-01..2001-06 (coupons >5y, net outright)": ["PDPUSGCS5MNOP"],
        "2001-07..2013-03 (coupons 6-11y, >11y, net outright)": ["PDPUSGCS611NOP", "PDPUSGCSM11NOP"],
        "2013-04..now (coupons 6-7, 7-11, 11-21, >21y)": ["PDPOSGSC-G6L7", "PDPOSGSC-G7L11", "PDPOSGSC-G11L21",
                                                           "PDPOSGSC-G21"],
    }
    COVERAGE["nyfed_primary_dealer"] = {
        "n_series": len(n), "first_date": min(first.values()), "last_date": max(last.values()),
        "series_starting_before_2001": sum(1 for k in n if first[k] < "2001-07-01"),
        "treasury_coupon_long_duration_chain": {lab: {k: [first.get(k), last.get(k), n.get(k)] for k in ks}
                                                 for lab, ks in chain.items()},
        "weeks_1998_to_now": sum(1 for k in ["PDPUSGTBNOP"] for _ in [0]) and None,
        "notes": ["as-of dates are Wednesdays; data released the following Thursday ~16:15 ET (8-day lag)",
                  "API serves latest values only: no vintages, so revisions cannot be audited",
                  "bucket definitions change at the 2001-07, 2013-04, 2015, 2022, 2024 series breaks"],
    }


# ------------------------------------------------------------------------------------------ 2. FINRA margin stats
def finra_margin() -> None:
    body = fetch("https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx",
                 "finra_margin/margin-statistics.xlsx")
    page = fetch("https://www.finra.org/rules-guidance/key-topics/margin-accounts/margin-statistics",
                 "finra_margin/margin_statistics_page.html")
    info = {}
    if body:
        z = zipfile.ZipFile(io.BytesIO(body))
        ss = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            ss = [("".join(t.text or "" for t in si.iter() if t.tag.endswith("}t"))) for si in root]
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        dates = []
        for row in sheet.findall(".//m:row", ns):
            c = row.find("m:c", ns)
            if c is None:
                continue
            v = c.find("m:v", ns)
            if v is None:
                continue
            txt = ss[int(v.text)] if c.get("t") == "s" else v.text
            if re.match(r"^\d{4}-\d{2}$", txt or ""):
                dates.append(txt)
        info = {"n_month_rows": len(dates), "first_month": min(dates) if dates else None,
                "last_month": max(dates) if dates else None}
    if page:
        links = sorted(set(re.findall(r'href="([^"]+\.xlsx?)"', page.decode("utf-8", "ignore"))))
        info["xlsx_links_on_page"] = links[:10]
    COVERAGE["finra_margin_statistics"] = info


# ------------------------------------------------------------------------------------------ 3. Binance archive listings
def s3_list(prefix: str, max_keys: int = 1000, delimiter: str | None = "/") -> tuple[list[str], list[str]]:
    base = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
    url = f"{base}?list-type=2&prefix={prefix}&max-keys={max_keys}" + (f"&delimiter={delimiter}" if delimiter else "")
    body = fetch(url)
    if not body:
        return [], []
    root = ET.fromstring(body)
    ns = "{http://s3.amazonaws.com/doc/2006-03-01/}"
    keys = [e.find(f"{ns}Key").text for e in root.findall(f"{ns}Contents")]
    prefs = [e.find(f"{ns}Prefix").text for e in root.findall(f"{ns}CommonPrefixes")]
    return keys, prefs


def binance_listings() -> None:
    out = {}
    for mkt in ("um", "cm"):
        _, types = s3_list(f"data/futures/{mkt}/daily/")
        out[f"{mkt}_daily_types"] = [t.split("/")[-2] for t in types]
    for mkt, sym in (("um", "BTCUSDT"), ("cm", "BTCUSD_PERP")):
        for typ in ("metrics", "liquidationSnapshot"):
            keys, _ = s3_list(f"data/futures/{mkt}/daily/{typ}/{sym}/", delimiter=None)
            dates = sorted(re.findall(r"(\d{4}-\d{2}-\d{2})", " ".join(keys)))
            out[f"{mkt}/{typ}/{sym}"] = {"n_files_first_page": len(keys), "first": dates[0] if dates else None,
                                          "last_on_first_page": dates[-1] if dates else None}
    _, syms = s3_list("data/futures/um/daily/liquidationSnapshot/")
    out["um_liquidationSnapshot_symbols_first_page"] = len(syms)
    # one tiny sample file each (structure only)
    for mkt, sym, typ in (("um", "BTCUSDT", "metrics"),):
        k = out.get(f"{mkt}/{typ}/{sym}", {}).get("first")
        if k:
            fetch(f"https://data.binance.vision/data/futures/{mkt}/daily/{typ}/{sym}/{sym}-{typ}-{k}.zip",
                  f"binance/{sym}-{typ}-{k}.zip")
    COVERAGE["binance_archive"] = out


# ------------------------------------------------------------------------------------------ 4. Stablecoin supply
def defillama_stablecoins() -> None:
    body = fetch("https://stablecoins.llama.fi/stablecoincharts/all?stablecoin=1", "defillama/usdt_all.json")
    lst = fetch("https://stablecoins.llama.fi/stablecoins?includePrices=false", "defillama/stablecoins_list.json")
    info = {}
    if body:
        d = json.loads(body)
        ts = sorted(int(x["date"]) for x in d)
        info["usdt_points"] = len(ts)
        info["usdt_first"] = dt.datetime.utcfromtimestamp(ts[0]).date().isoformat()
        info["usdt_last"] = dt.datetime.utcfromtimestamp(ts[-1]).date().isoformat()
    if lst:
        info["n_stablecoins_listed"] = len(json.loads(lst).get("peggedAssets", []))
    info["notes"] = ["DefiLlama backfills and re-derives history (no vintages): not point-in-time",
                     "useful only from ~2019 at scale"]
    COVERAGE["defillama_stablecoins"] = info


# ------------------------------------------------------------------------------------------ 5. FRED / fiscaldata / Fed
def reachability() -> None:
    res = {}
    for lab, url in (
        ("fred_custody_WMTSECL1", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=WMTSECL1"),
        ("fred_margin_BOGZ1", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=BOGZ1FL663067003Q"),
        ("fiscaldata_mspd", "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/debt/mspd/"
                            "mspd_table_1?page%5Bsize%5D=1&sort=record_date"),
        ("fed_h41_page", "https://www.federalreserve.gov/releases/h41/"),
        ("cftc_tff_2006", "https://www.cftc.gov/files/dea/history/fut_fin_txt_2006_2016.zip"),
        ("deribit_settlements", "https://www.deribit.com/api/v2/public/get_last_settlements_by_currency?"
                                "currency=BTC&type=delivery&count=5"),
        ("bitmex_settled", "https://www.bitmex.com/api/v1/instrument?filter=%7B%22state%22%3A%22Settled%22%2C"
                           "%22rootSymbol%22%3A%22XBT%22%7D&count=5&columns=symbol,listing,expiry,settle"),
        ("okx_delivery_history", "https://www.okx.com/api/v5/public/instruments?instType=FUTURES&uly=BTC-USD"),
    ):
        body = fetch(url, timeout=45, max_bytes=2_000_000)
        rec = MANIFEST[-1]
        res[lab] = {"status": rec.get("status"), "bytes": rec.get("bytes"), "error": rec.get("error")}
    COVERAGE["reachability"] = res


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for f in (nyfed_primary_dealer, finra_margin, binance_listings, defillama_stablecoins, reachability):
        try:
            f()
        except Exception as e:  # keep going; record the failure
            COVERAGE[f.__name__ + "_error"] = f"{type(e).__name__}: {e}"[:300]
    (DATA / "MANIFEST.json").write_text(json.dumps(MANIFEST, indent=1))
    (OUT / "coverage.json").write_text(json.dumps(COVERAGE, indent=1, default=str))
    print(json.dumps(COVERAGE, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
