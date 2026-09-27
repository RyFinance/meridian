"""Population-level (not just our 64-CIK sample) counts via EDGAR full text search
(efts.sec.gov, reachable from this environment), for one recent representative quarter
(2024 Q1) unless noted. FTS indexes filings' own text, so an item-code count is the number
of 8-Ks whose text contains that literal "Item X.XX" caption (8-K cover pages always state
their item numbers verbatim, so this is a reliable, if not perfectly exact, breadth proxy).

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.edgar_scout.sample_fts
"""
from __future__ import annotations

import json
import urllib.parse as up

from research.edgar_scout.common import DATA_DIR, Manifest, get

Q1_2024 = ("2024-01-01", "2024-03-31")

EIGHT_K_ITEMS = ["1.01", "1.03", "2.02", "2.05", "2.06", "3.01", "5.02", "7.01", "8.01"]

FORM_QUERIES = {
    "13F-HR_filings_Q1_2024": {"forms": "13F-HR", "q": None},
    "13F-NT_filings_Q1_2024": {"forms": "13F-NT", "q": None},
    "144_filings_Q1_2024": {"forms": "144", "q": None},
    "SC13D_filings_Q1_2024": {"forms": "SC 13D", "q": None},
    "SC13G_filings_Q1_2024": {"forms": "SC 13G", "q": None},
    "NT10-K_filings_Q1_2024": {"forms": "NT 10-K", "q": None},
    "424B2_filings_Q1_2024": {"forms": "424B2", "q": None},
    "424B5_filings_Q1_2024": {"forms": "424B5", "q": None},
    "S-3_filings_Q1_2024": {"forms": "S-3", "q": None},
    "8-K_all_filings_Q1_2024": {"forms": "8-K", "q": None},
    "10-K_all_filings_Q1_2024": {"forms": "10-K", "q": None},
}


def fts_url(q: str | None, forms: str, start: str, end: str) -> str:
    params = {"forms": forms, "startdt": start, "enddt": end}
    if q:
        params["q"] = q
    return "https://efts.sec.gov/LATEST/search-index?" + up.urlencode(params)


def hit_total(resp_json: dict) -> int | None:
    return resp_json.get("hits", {}).get("total", {}).get("value")


def main() -> None:
    manifest = Manifest()
    out = {}

    # 8-K item-code breadth (text-search proxy) for one quarter
    for item in EIGHT_K_ITEMS:
        url = fts_url(f'"Item {item}"', "8-K", *Q1_2024)
        resp = get(url)
        key = f"8K_item_{item}_Q1_2024"
        if resp.status_code == 200:
            d = resp.json()
            out[key] = {"total_hits": hit_total(d), "url": url}
            manifest.record_bytes(f"fts/{key}.json", url, resp.content, 200)
        else:
            out[key] = {"error": resp.status_code, "url": url}
            manifest.record_refusal(f"fts/{key}", url, resp.status_code, resp.text)
        print(key, out[key])

    # form-type population counts for one quarter
    for key, spec in FORM_QUERIES.items():
        url = fts_url(spec["q"], spec["forms"], *Q1_2024)
        resp = get(url)
        if resp.status_code == 200:
            d = resp.json()
            out[key] = {"total_hits": hit_total(d), "url": url}
            manifest.record_bytes(f"fts/{key}.json", url, resp.content, 200)
        else:
            out[key] = {"error": resp.status_code, "url": url}
            manifest.record_refusal(f"fts/{key}", url, resp.status_code, resp.text)
        print(key, out[key])

    # EDGAR full text search coverage start (sanity probe: does a 2001 query return hits?)
    for yr in (2001, 2005, 2010):
        url = fts_url(None, "8-K", f"{yr}-01-01", f"{yr}-01-31")
        resp = get(url)
        key = f"fts_coverage_probe_{yr}"
        if resp.status_code == 200:
            d = resp.json()
            out[key] = {"total_hits": hit_total(d), "url": url}
        else:
            out[key] = {"error": resp.status_code, "url": url}
        print(key, out[key])

    (DATA_DIR / "fts_sample.json").write_text(json.dumps(out, indent=1))
    manifest.write(DATA_DIR / "fts" / "manifest.json")


if __name__ == "__main__":
    main()
