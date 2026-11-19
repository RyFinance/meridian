"""Free official web sources for cycle-7 FI (sandboxed HTTPS; blocked hosts recorded, never bypassed).

  akk_hu     ÁKK (Hungarian Government Debt Management Agency) daily benchmark yields, all tenors (10Y used)
  bbk_r0815  Bundesbank BBSIS daily yields on listed Federal securities, residual maturity 8-15y (DE pre-1997 extension)
  bbk_r0910u Bundesbank unweighted listed Federal securities residual 9-10y (daily from 1994; reference)
  statcan_v39055  Statistics Canada table 10-10-0139 v39055 GoC benchmark 10y yield, daily (CA pre-2001 extension)
  snb_rendoblid   SNB daily spot (zero-coupon) Confederation yields (recorded; zero-coupon -> not the cycle-6 input)
  boe_glcnominalddata  BoE archive nominal yield curves (daily spot/forward; recorded)
Run: PYTHONPATH=. .venv/bin/python -m research.cycle7.data_fi.acquire_web
"""
from __future__ import annotations

import json
import subprocess

from research.cycle7.data_fi.common import RAW, sha_bytes, utc_now, write_json, META

UA = "Mozilla/5.0 (quant_v7 research)"
AKK = "https://www.akk.hu/api/data/xpose3-dwh/data?query=getBenchmark&dateStart={a}&dateEnd={b}&orderField=date&orderDirection=ASC"
BBK = "https://api.statistiken.bundesbank.de/rest/data/BBSIS/{k}?format=csv&lang=en"
STATCAN = ("https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorByReferencePeriodRange?vectorIds=%2239055%22"
           "&startRefPeriod=1950-01-01&endReferencePeriod=2026-09-30")
SNB = "https://data.snb.ch/api/cube/rendoblid/data/csv/en"
BOE = "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/glcnominalddata.zip"
BLOCKED_PROBES = {
    "rba_f2_daily": "https://www.rba.gov.au/statistics/tables/xls/f02d.xlsx",
    "rbnz_b2_daily": "https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily.xlsx",
    "boi_edge_sdmx": "https://edge.boi.gov.il/FusionEdgeServer/sdmx/v2/data/dataflow/BOI.STATISTICS/BR/1.0/",
    "fred": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=IRLTLT01KRM156N",
    "ecb_data_api": "https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.BB.U_A10Y.YLD?format=csvdata&lastNObservations=2",
    "nbp_pl": "https://www.nbp.pl/",
    "bsp_ph": "https://www.bsp.gov.ph/",
    "dnb_nl": "https://www.dnb.nl/",
    "nbb_be_stat": "https://stat.nbb.be/",
    "bof_fi": "https://www.suomenpankki.fi/",
    "bank_of_greece": "https://www.bankofgreece.gr/",
    "hkma_api": "https://api.hkma.gov.hk/public/market-data-and-statistics/daily-monetary-statistics/daily-figures-interbank-liquidity?pagesize=3",
    "us_treasury_csv": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/all?type=daily_treasury_yield_curve&field_tdr_date_value=1990",
}


def get(url: str, timeout: int = 300):
    p = subprocess.run(["curl", "-sS", "-L", "-m", str(timeout), "-A", UA, "-w", "\n__HTTP__%{http_code}", url],
                       capture_output=True)
    out = p.stdout
    code = None
    if b"\n__HTTP__" in out:
        out, c = out.rsplit(b"\n__HTTP__", 1)
        code = c.decode()
    return out, code, p.stderr.decode()[:300]


def save(source: str, name: str, content: bytes, url: str, code, ext: str, log: list):
    d = RAW / source
    d.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    p = d / f"{name}.{now:%Y%m%dT%H%M%S}.{ext}"
    p.write_bytes(content)
    rec = {"source": source, "name": name, "url": url, "http_status": code, "bytes": len(content),
           "sha256": sha_bytes(content), "path": str(p.relative_to(RAW)), "fetched_at_utc": now.isoformat()}
    with (d / "manifest.jsonl").open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    log.append(rec)
    return p


def main():
    log, blocked = [], {}
    for y in range(1990, 2027, 4):
        url = AKK.format(a=f"{y}-01-01", b=f"{y + 3}-12-31")
        b, c, e = get(url)
        save("akk_hu", f"benchmark_{y}", b, url, c, "json", log)
    for name, k in (("bbk_r0815", "D.I.UMR.RD.EUR.S1311.B.A604.R0815.R.A.A._Z._Z.A"),
                    ("bbk_r0910u", "D.I.UMU.RD.EUR.S1311.B.A604.R0910.R.A.A._Z._Z.A")):
        url = BBK.format(k=k)
        b, c, e = get(url)
        save("bundesbank", name, b, url, c, "csv", log)
    b, c, e = get(STATCAN, 600)
    save("statcan", "v39055", b, STATCAN, c, "json", log)
    b, c, e = get(SNB)
    save("snb", "rendoblid", b, SNB, c, "csv", log)
    b, c, e = get(BOE, 600)
    save("boe", "glcnominalddata", b, BOE, c, "zip", log)
    for k, u in BLOCKED_PROBES.items():
        b, c, e = get(u, 25)
        blocked[k] = {"url": u, "http_status": c, "curl_error": e, "bytes": len(b)}
    write_json(META / "acquire_web.json", {"run_at_utc": utc_now().isoformat(), "fetches": log, "probes": blocked})
    for r in log:
        print(r["name"], r["http_status"], r["bytes"])
    for k, v in blocked.items():
        print("probe", k, v["http_status"], v["curl_error"][:80])


if __name__ == "__main__":
    main()
