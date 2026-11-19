"""Find MicroStrategy BTC-acquisition disclosures in official SEC 8-K filings.

This intentionally caches only derived candidate rows/snippets, not filing bodies.
Run from this directory.  SEC requires an identifiable User-Agent; replace the
contact address if these results are refreshed outside this research session.
"""
from __future__ import annotations

import json
import re
import time
import argparse
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup


CIK = "0001050446"
BASE = "https://www.sec.gov"
HEADERS = {
    "User-Agent": "CCP academic event-study research contact@example.com",
    "Accept-Encoding": "gzip, deflate",
}
OUT = Path(__file__).parent


def get(session: requests.Session, url: str, is_json: bool = False):
    for attempt in range(4):
        try:
            r = session.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                time.sleep(0.12)  # comfortably below SEC's public request ceiling
                return r.json() if is_json else r.text
            if r.status_code in (403, 429, 500, 502, 503):
                time.sleep(1.0 * (attempt + 1))
                continue
            raise RuntimeError(f"{r.status_code} {url}")
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"Unable to retrieve {url}")


def rows_from_table(table: dict) -> list[dict]:
    keys = list(table)
    n = len(table[keys[0]]) if keys else 0
    return [{k: table[k][i] for k in keys} for i in range(n)]


def plain(html: str) -> str:
    # lxml is materially faster on EDGAR's verbose inline HTML.
    return re.sub(r"\s+", " ", BeautifulSoup(html, "lxml").get_text(" ")).strip()


def match_windows(text: str) -> list[str]:
    lower = text.lower()
    # Requiring a completed acquisition verb rejects routine risk-factor wording.
    patterns = [
        r"(?:purchased|acquired|purchases of|acquisitions of).{0,220}?(?:bitcoin|bitcoins|btc)",
        r"(?:bitcoin|bitcoins|btc).{0,220}?(?:purchased|acquired)",
    ]
    matches = []
    for pat in patterns:
        for m in re.finditer(pat, lower, flags=re.I):
            snippet = text[max(0, m.start() - 170): min(len(text), m.end() + 280)]
            if snippet not in matches:
                matches.append(snippet)
    return matches[:4]


def filing_docs(session: requests.Session, accession: str, primary: str, include_exhibits: bool) -> list[tuple[str, str]]:
    nodash = accession.replace("-", "")
    if not include_exhibits:
        return [(primary, f"{BASE}/Archives/edgar/data/{int(CIK)}/{nodash}/{primary}")]
    index_url = f"{BASE}/Archives/edgar/data/{int(CIK)}/{nodash}/index.json"
    index = get(session, index_url, is_json=True)
    names = [x["name"] for x in index.get("directory", {}).get("item", [])]
    # Search only human-readable filing/exhibit documents.  The primary doc first
    # makes source attribution deterministic when duplicated in the directory.
    keep = [primary] + [
        x for x in names
        # EDGAR's accession-level .txt is a concatenated raw submission and can
        # be enormous.  The same filing/exhibits are available as individual
        # HTML documents, so do not parse raw .txt except if it is the declared
        # primary document itself.
        if x.lower().endswith((".htm", ".html")) and x != primary
        and not x.lower().endswith((".xsd", ".xml"))
    ]
    result, seen = [], set()
    for name in keep:
        if name in seen:
            continue
        seen.add(name)
        result.append((name, f"{BASE}/Archives/edgar/data/{int(CIK)}/{nodash}/{name}"))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-exhibits", action="store_true", help="also scan individual HTML exhibits")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="9999-12-31", help="inclusive ISO date")
    args = parser.parse_args()
    session = requests.Session()
    sub = get(session, f"https://data.sec.gov/submissions/CIK{CIK}.json", is_json=True)
    tables = [sub["filings"]["recent"]]
    for f in sub["filings"].get("files", []):
        tables.append(get(session, "https://data.sec.gov/submissions/" + f["name"], is_json=True))
    filings = pd.DataFrame([row for table in tables for row in rows_from_table(table)])
    filings = filings.loc[
        (filings["form"] == "8-K") & (filings["filingDate"] >= args.start) & (filings["filingDate"] <= args.end)
    ].sort_values(["filingDate", "accessionNumber"]).reset_index(drop=True)
    print(f"Scanning {len(filings)} MicroStrategy 8-K filings from {filings.filingDate.min()} onward")

    candidates = []
    failures = []
    for num, row in filings.iterrows():
        accession = row["accessionNumber"]
        try:
            hits = []
            for doc_name, url in filing_docs(session, accession, row["primaryDocument"], args.include_exhibits):
                txt = plain(get(session, url))
                windows = match_windows(txt)
                if windows:
                    hits.append((doc_name, url, windows))
            if hits:
                for doc_name, url, windows in hits:
                    candidates.append({
                        "filing_date": row["filingDate"],
                        "acceptance_utc": row["acceptanceDateTime"],
                        "accession": accession,
                        "items": row.get("items", ""),
                        "primary_document": row["primaryDocument"],
                        "matched_document": doc_name,
                        "source_url": url,
                        "snippet": " || ".join(windows),
                    })
        except Exception as exc:  # retain visibility into incomplete source coverage
            failures.append({"accession": accession, "filing_date": row["filingDate"], "error": str(exc)})
        if (num + 1) % 25 == 0 or num + 1 == len(filings):
            print(f"{num + 1}/{len(filings)}; matches={len(candidates)}; failures={len(failures)}")

    suffix = "with_exhibits" if args.include_exhibits else "primary_only"
    pd.DataFrame(candidates).to_csv(OUT / f"sec_purchase_candidates_{suffix}.csv", index=False)
    pd.DataFrame(failures).to_csv(OUT / f"sec_purchase_scan_failures_{suffix}.csv", index=False)
    manifest = {
        "retrieved": str(date.today()),
        "cik": CIK,
        "source": "SEC submissions JSON plus filing-directory / document URLs",
        "filings_scanned": int(len(filings)),
        "candidate_document_matches": int(len(candidates)),
        "failures": int(len(failures)),
        "method": "8-K filing/exhibit text has completed-acquisition and bitcoin/BTC terms within 220 characters",
        "include_exhibits": args.include_exhibits,
        "date_range": [args.start, args.end],
    }
    (OUT / f"sec_purchase_scan_manifest_{suffix}.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
