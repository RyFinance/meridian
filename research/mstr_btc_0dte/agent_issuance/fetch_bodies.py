"""Recon step 1: fetch Strategy (MSTR) 8-K primary documents for the weekly
capital-markets tables (ATM sales, BTC purchases, preferred repurchases).

Derived index only in this folder; the filing bodies go to a scratch cache
outside the repo (SEC content is publicly official, but the exercise keeps the
repo evidence trail to derived data + source URLs).
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

HEADERS = {"User-Agent": "CCP academic event-study research contact@example.com", "Accept-Encoding": "gzip, deflate"}
BASE = "https://www.sec.gov"
CIK = "0001050446"
NODASH_CIK = str(int(CIK))
HERE = Path(__file__).resolve().parent
CACHE = Path("/private/var/folders/90/ddskxhqn2k30py1w250kbq1r0000gn/T/opencode/mstr_8k_cache")
START, END = "2024-09-01", "2026-10-16"


def get(url: str, is_json: bool = False):
    for n in range(4):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                time.sleep(0.12)
                return r.json() if is_json else r.text
            if r.status_code in {403, 429, 500, 502, 503}:
                time.sleep(n + 1)
                continue
            raise RuntimeError(f"HTTP {r.status_code}: {url}")
        except requests.RequestException:
            if n == 3:
                raise
            time.sleep(n + 1)
    raise RuntimeError(f"unretrievable: {url}")


def rows_from_table(table: dict) -> list[dict]:
    keys = list(table)
    n = len(table[keys[0]]) if keys else 0
    return [{k: table[k][i] for k in keys} for i in range(n)]


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    sub = get(f"https://data.sec.gov/submissions/CIK{CIK}.json", is_json=True)
    tables = [sub["filings"]["recent"]]
    for f in sub["filings"].get("files", []):
        tables.append(get("https://data.sec.gov/submissions/" + f["name"], is_json=True))
    filings = pd.DataFrame([row for table in tables for row in rows_from_table(table)])
    filings = filings.loc[
        (filings["form"] == "8-K") & (filings["filingDate"] >= START) & (filings["filingDate"] <= END)
    ].sort_values(["filingDate", "accessionNumber"]).reset_index(drop=True)
    print(f"8-K filings in [{START}, {END}]: {len(filings)}")
    out = []
    for _, row in filings.iterrows():
        acc = row["accessionNumber"]
        nodash = acc.replace("-", "")
        primary = row["primaryDocument"]
        local = CACHE / f"{acc}_{primary}"
        url = f"{BASE}/Archives/edgar/data/{NODASH_CIK}/{nodash}/{primary}"
        if not local.exists():
            local.write_text(get(url), encoding="utf-8", errors="replace")
        out.append({
            "filing_date": row["filingDate"],
            "acceptance_utc": row["acceptanceDateTime"],
            "accession": acc,
            "items": row.get("items", ""),
            "primary_document": primary,
            "source_url": url,
            "local_path": str(local),
        })
    idx = pd.DataFrame(out)
    idx.to_csv(HERE / "filings_index.csv", index=False)
    print(idx.groupby(idx.filing_date.str[:7]).size().to_string())


if __name__ == "__main__":
    main()
