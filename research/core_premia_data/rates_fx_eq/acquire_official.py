"""Keyless official-source ingest: Fed DDP (H.10 FX, H.15 Treasury CMT), Bank of England IADB,
Deutsche Bundesbank SDMX, Japan MOF JGB curve, Bank of Canada Valet, Sveriges Riksbank SWEA,
Norges Bank SDMX, SNB data portal, OECD SDMX (monthly long-term and 3M interbank rates),
and the AQR TSMOM benchmark workbook (bytes frozen; only its date axis is read elsewhere).

Raw response bytes only -- no reformatting, no returns. FRED/ALFRED and the ECB data API were
unreachable from this host (TLS stream reset / timeout, also outside the sandbox); Stooq serves a
JavaScript proof-of-work bot check and is NOT bypassed; RBA timed out; RBNZ returned 403.
These are recorded as endpoint failures by ``probe_blocked``.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.core_premia_data.rates_fx_eq.acquire_official
"""
from __future__ import annotations

import json
import sys

from research.core_premia_data.rates_fx_eq.common import fetch, log_attempt, META, write_json, utc_now

DDP = "https://www.federalreserve.gov/datadownload/Output.aspx"
H10_PKG = "60f32914ab61dfab590e0e470153e3ae"  # H.10 daily "Rates in currency per U.S. dollar" package
H15_PKG = "bf17364827e38702b42a58cf8eaa3f78"  # H.15 Treasury Constant Maturities, all observations
H10_CHUNKS = [(1971, 1980), (1981, 1990), (1991, 2000), (2001, 2010), (2011, 2020), (2021, 2026)]

BOE = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"
BOE_CODES = {  # code: (label, tenor_years, kind)
    "IUDSNZC": ("UK nominal zero-coupon 5y (BoE fitted curve)", 5, "zero"),
    "IUDMNZC": ("UK nominal zero-coupon 10y (BoE fitted curve)", 10, "zero"),
    "IUDLNZC": ("UK nominal zero-coupon 20y (BoE fitted curve)", 20, "zero"),
    "IUDSNPY": ("UK nominal par yield 5y (BoE fitted curve)", 5, "par"),
    "IUDMNPY": ("UK nominal par yield 10y (BoE fitted curve)", 10, "par"),
    "IUDLNPY": ("UK nominal par yield 20y (BoE fitted curve)", 20, "par"),
    "IUDBEDR": ("UK Bank Rate", 0, "policy"),
    "IUDSOIA": ("SONIA overnight", 0, "overnight"),
    "IUDVCDA": ("BoE IADB IUDVCDA sterling 3M money-market rate (label unverified; discontinued 2018-06-29)", 0.25, "money_market"),
}

BBK = "https://api.statistiken.bundesbank.de/rest/data/BBSIS"
BBK_TENORS = [1, 2, 5, 10, 20, 30]  # par yields derived from Bund term structure, annual coupons

MOF_ALL = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv"
MOF_CUR = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv"

BOC = "https://www.bankofcanada.ca/valet/observations/{sid}/json"
BOC_SERIES = {"BD.CDN.2YR.DQ.YLD": 2, "BD.CDN.5YR.DQ.YLD": 5, "BD.CDN.10YR.DQ.YLD": 10,
              "BD.CDN.LONG.DQ.YLD": 30, "V80691303": 0.25}

RIKS = "https://api.riksbank.se/swea/v1/Observations/{sid}/1980-01-01/2026-09-26"
RIKS_SERIES = {"SEGVB2YC": 2, "SEGVB5YC": 5, "SEGVB10YC": 10, "SETB3MBENCH": 0.25,
               "SEDP3MSTIBORDELAYC": 0.25}

NORGES = "https://data.norges-bank.no/api/data/GOVT_GENERIC_RATES/B.{tenor}.{inst}?format=csv&startPeriod=1980-01-01"
NORGES_SERIES = {("3M", "TBIL"): 0.25, ("12M", "TBIL"): 1, ("3Y", "GBON"): 3, ("5Y", "GBON"): 5, ("10Y", "GBON"): 10}

SNB = "https://data.snb.ch/api/cube/rendoblim/data/csv/en"

OECD = "https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0/.M.{m}.PA.....?startPeriod=1950-01&dimensionAtObservation=AllDimensions&format=csvfilewithlabels"
OECD_MEASURES = ["IRLT", "IR3TIB", "IRSTCI"]

AQR = "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Time-Series-Momentum-Factors-Monthly.xlsx"
AQR_PAGE = "https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Factors-Monthly"

BLOCKED_PROBES = {
    "fred_fredgraph": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=IRLTLT01DEM156N",
    "alfred_vintages": "https://alfred.stlouisfed.org/graph/alfredgraph.csv?id=IRLTLT01DEM156N",
    "ecb_data_api": "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?lastNObservations=3&format=csvdata",
    "stooq_csv": "https://stooq.com/q/d/l/?s=^dax&i=d",
    "rba_f2": "https://www.rba.gov.au/statistics/tables/csv/f2-data.csv",
    "rbnz_b2": "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily.xlsx",
}


def _csv_rows(min_rows):
    def v(body: bytes):
        n = body.count(b"\n")
        return (n >= min_rows, f"{n} lines < {min_rows}")
    return v


def _not_html(body: bytes):
    head = body[:400].lower()
    return (b"<html" not in head and b"object moved" not in head, "html/error page")


def _json_obs(key):
    def v(body: bytes):
        try:
            d = json.loads(body)
        except ValueError:
            return False, "not json"
        n = len(d.get(key, [])) if isinstance(d, dict) else len(d)
        return n > 0, f"{n} observations"
    return v


def run() -> dict:
    results = {}

    def rec(key, r, url, **extra):
        results[key] = {"ok": r is not None, "url": url, "raw_path": r["path"] if r else None,
                        "sha256": r["sha256"] if r else None, "bytes": r["bytes"] if r else 0,
                        "fetched_at_utc": r["fetched_at_utc"] if r else None, "attempt": r.get("attempt") if r else None,
                        **extra}

    # Fed H.10 (chunked: the all-observations request intermittently returns an empty 200)
    for a, b in H10_CHUNKS:
        url = (f"{DDP}?rel=H10&series={H10_PKG}&lastobs=&from=01/01/{a}&to=12/31/{b}"
               "&filetype=csv&label=include&layout=seriescolumn&type=package")
        rec(f"fed_h10/{a}_{b}", fetch("fed_h10", f"h10_daily_{a}_{b}", url, ext="csv", validate=_csv_rows(200), retries=8), url)
    url = f"{DDP}?rel=H15&series={H15_PKG}&lastobs=&from=&to=&filetype=csv&label=include&layout=seriescolumn&type=package"
    rec("fed_h15/cmt", fetch("fed_h15", "h15_cmt_daily_all", url, ext="csv", validate=_csv_rows(10000), retries=8), url)

    for code in BOE_CODES:
        url = f"{BOE}?csv.x=yes&Datefrom=01/Jan/1970&Dateto=now&SeriesCodes={code}&CSVF=TN&UsingCodes=Y"
        rec(f"boe/{code}", fetch("boe_iadb", code, url, ext="csv", validate=_not_html), url)

    for t in BBK_TENORS:
        key = f"D.I.ZAR.ZI.EUR.S1311.B.A604.R{t:02d}XX.R.A.A._Z._Z.A"
        url = f"{BBK}/{key}?format=csv"
        rec(f"bundesbank/par_{t}y", fetch("bundesbank", f"BBSIS_ZAR_R{t:02d}XX", url, ext="csv", validate=_csv_rows(1000)), url)

    rec("mof/jgbcme_all", fetch("mof_japan", "jgbcme_all", MOF_ALL, ext="csv", validate=_csv_rows(1000)), MOF_ALL)
    rec("mof/jgbcme_current", fetch("mof_japan", "jgbcme_current_month", MOF_CUR, ext="csv", validate=_csv_rows(2)), MOF_CUR)

    for sid in BOC_SERIES:
        url = BOC.format(sid=sid) + "?start_date=1900-01-01"
        rec(f"boc/{sid}", fetch("boc_valet", sid, url, ext="json", validate=_json_obs("observations")), url)

    for sid in RIKS_SERIES:
        url = RIKS.format(sid=sid)
        rec(f"riksbank/{sid}", fetch("riksbank", sid, url, ext="json", validate=_json_obs("x")), url)

    for (tenor, inst) in NORGES_SERIES:
        url = NORGES.format(tenor=tenor, inst=inst)
        rec(f"norges/{tenor}_{inst}", fetch("norges_bank", f"GOVT_GENERIC_RATES_B_{tenor}_{inst}", url, ext="csv",
                                           validate=_csv_rows(10)), url)

    rec("snb/rendoblim", fetch("snb", "rendoblim", SNB, ext="csv", validate=_csv_rows(100)), SNB)

    for m in OECD_MEASURES:
        url = OECD.format(m=m)
        rec(f"oecd/{m}", fetch("oecd_sdmx", f"DF_FINMARK_{m}", url, ext="csv", validate=_csv_rows(1000), timeout=300), url)

    rec("aqr/tsmom_xlsx", fetch("aqr", "TSMOM_factors_monthly", AQR, ext="xlsx", min_bytes=10000), AQR)
    rec("aqr/tsmom_page", fetch("aqr", "TSMOM_dataset_page", AQR_PAGE, ext="html", min_bytes=1000), AQR_PAGE)

    write_json(META / "acquire_official_results.json", {"run_at_utc": utc_now().isoformat(), "results": results})
    return results


def probe_blocked() -> dict:
    """One bounded probe per known-unreachable free source; records the failure, never bypasses."""
    out = {}
    for name, url in BLOCKED_PROBES.items():
        r = fetch("blocked_probe", name, url, ext="bin", retries=2, backoff=2.0, timeout=45,
                  validate=lambda b: (b"verify your browser" not in b and b"<html" not in b[:300].lower(),
                                      "bot-check or HTML page (not bypassed)"))
        out[name] = {"url": url, "reachable_data": r is not None}
    write_json(META / "blocked_probe_results.json", {"run_at_utc": utc_now().isoformat(), "results": out})
    return out


if __name__ == "__main__":
    if "--blocked" in sys.argv:
        print(json.dumps(probe_blocked(), indent=1))
    else:
        res = run()
        print(json.dumps({k: (v["ok"], v["bytes"]) for k, v in res.items()}, indent=1))
