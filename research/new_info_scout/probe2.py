"""Second coverage pass (fixes for probe.py): Binance listing pagination, FRED custody/margin coverage, MSPD depth,
Deribit/BitMEX dated-futures chain depth. Coverage only (dates, counts, identifiers); values are never summarised.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.new_info_scout.probe2
"""
from __future__ import annotations

import json
import re
import urllib.parse
import xml.etree.ElementTree as ET

from research.new_info_scout import probe as P

NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


def s3_all(prefix: str, delimiter: str | None = None, cap_pages: int = 10) -> tuple[list[str], list[str]]:
    base = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
    keys, prefs, token = [], [], None
    for _ in range(cap_pages):
        q = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if delimiter:
            q["delimiter"] = delimiter
        if token:
            q["continuation-token"] = token
        body = P.fetch(base + "?" + urllib.parse.urlencode(q), timeout=90)
        if not body:
            break
        root = ET.fromstring(body)
        keys += [e.find(f"{NS}Key").text for e in root.findall(f"{NS}Contents")]
        prefs += [e.find(f"{NS}Prefix").text for e in root.findall(f"{NS}CommonPrefixes")]
        t = root.find(f"{NS}NextContinuationToken")
        if t is None:
            break
        token = t.text
    return keys, prefs


def dates_of(keys):
    return sorted(re.findall(r"(\d{4}-\d{2}-\d{2})\.zip", " ".join(keys)))


def binance() -> dict:
    out = {}
    for mkt, typ, sym in (("um", "metrics", "BTCUSDT"), ("um", "metrics", "ETHUSDT"),
                          ("cm", "liquidationSnapshot", "BTCUSD_PERP"), ("cm", "metrics", "BTCUSD_PERP")):
        k, _ = s3_all(f"data/futures/{mkt}/daily/{typ}/{sym}/")
        d = dates_of(k)
        out[f"{mkt}/{typ}/{sym}"] = {"n_daily_files": len(d), "first": d[0] if d else None, "last": d[-1] if d else None}
    _, syms = s3_all("data/futures/um/daily/metrics/", delimiter="/")
    out["um_metrics_symbols"] = len(syms)
    _, lsyms = s3_all("data/futures/cm/daily/liquidationSnapshot/", delimiter="/")
    out["cm_liquidationSnapshot_symbols"] = len(lsyms)
    _, deliv = s3_all("data/futures/cm/daily/klines/", delimiter="/")
    dated = sorted(s.split("/")[-2] for s in deliv if re.search(r"_\d{6}/$", s))
    out["cm_dated_contract_folders"] = {"n": len(dated), "first": dated[:3], "last": dated[-3:]}
    _, udeliv = s3_all("data/futures/um/daily/klines/", delimiter="/")
    udated = sorted(s.split("/")[-2] for s in udeliv if re.search(r"_\d{6}/$", s))
    out["um_dated_contract_folders"] = {"n": len(udated), "first": udated[:3], "last": udated[-3:]}
    # one liquidation snapshot sample (structure only)
    ls = out["cm/liquidationSnapshot/BTCUSD_PERP"]
    if ls["first"]:
        P.fetch("https://data.binance.vision/data/futures/cm/daily/liquidationSnapshot/BTCUSD_PERP/"
                f"BTCUSD_PERP-liquidationSnapshot-{ls['first']}.zip",
                f"binance/BTCUSD_PERP-liquidationSnapshot-{ls['first']}.zip")
    return out


def fred(series: str) -> dict:
    body = P.fetch(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}", f"fred/{series}.csv", timeout=90)
    if not body:
        return {"status": P.MANIFEST[-1].get("status"), "error": P.MANIFEST[-1].get("error")}
    lines = body.decode().strip().splitlines()
    if len(lines) < 3 or "," not in lines[0]:
        return {"unexpected": lines[:2]}
    rows = [ln.split(",") for ln in lines[1:]]
    ok = [r[0] for r in rows if len(r) > 1 and r[1] not in ("", ".")]
    return {"header": lines[0], "n_obs": len(ok), "first": ok[0] if ok else None, "last": ok[-1] if ok else None}


def fiscaldata_mspd() -> dict:
    url = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/debt/mspd/mspd_table_1"
           "?fields=record_date&sort=record_date&page%5Bsize%5D=1")
    b1 = P.fetch(url, "fiscaldata/mspd_first.json", timeout=90)
    b2 = P.fetch(url.replace("sort=record_date", "sort=-record_date"), "fiscaldata/mspd_last.json", timeout=90)
    try:
        return {"first": json.loads(b1)["data"][0]["record_date"], "last": json.loads(b2)["data"][0]["record_date"]}
    except Exception as e:
        return {"error": str(e)[:200]}


def deribit_bitmex() -> dict:
    out = {}
    b = P.fetch("https://www.deribit.com/api/v2/public/get_last_settlements_by_currency?currency=BTC&type=delivery"
                "&count=1000&search_start_timestamp=1900000000000", "deribit/btc_delivery_settlements_page1.json",
                timeout=90)
    if b:
        s = json.loads(b).get("result", {}).get("settlements", [])
        ts = sorted(x["timestamp"] for x in s)
        import datetime as dt
        out["deribit_btc_delivery_page1"] = {"n": len(s), "oldest": dt.datetime.utcfromtimestamp(ts[0] / 1e3).date().isoformat()
                                             if ts else None, "has_more": bool(json.loads(b)["result"].get("continuation"))}
    b = P.fetch("https://www.bitmex.com/api/v1/instrument?filter=%7B%22rootSymbol%22%3A%22XBT%22%2C%22typ%22%3A%22FFCCSX%22%7D"
                "&count=500&columns=symbol,listing,expiry,settle,state", "bitmex/xbt_dated_futures.json", timeout=90)
    try:
        rows = json.loads(b) if b else []
    except ValueError:
        rows = []
        out["bitmex_error"] = "truncated JSON (network IncompleteRead)"
    if rows:
        exp = sorted(r["expiry"][:10] for r in rows if r.get("expiry"))
        out["bitmex_xbt_dated_futures"] = {"n": len(rows), "first_expiry": exp[0] if exp else None,
                                           "last_expiry": exp[-1] if exp else None}
    return out


def main():
    cov = json.loads((P.OUT / "coverage.json").read_text())
    cov["binance_archive_v2"] = binance()
    cov["fred"] = {s: fred(s) for s in ("WMTSECL1", "WFASECL1", "BOGZ1FL663067003Q", "WTREGEN", "WSHOMCB", "RRPONTSYD")}
    cov["fiscaldata_mspd"] = fiscaldata_mspd()
    cov["crypto_dated_futures"] = deribit_bitmex()
    man = json.loads((P.DATA / "MANIFEST.json").read_text())
    (P.DATA / "MANIFEST.json").write_text(json.dumps(man + P.MANIFEST, indent=1))
    (P.OUT / "coverage.json").write_text(json.dumps(cov, indent=1, default=str))
    for k in ("binance_archive_v2", "fred", "fiscaldata_mspd", "crypto_dated_futures"):
        print(k, json.dumps(cov[k], indent=1, default=str))


if __name__ == "__main__":
    main()
