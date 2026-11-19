"""Build a reproducible SEC-primary-source inventory for MSTR issuance events.

This script deliberately does *not* load price data.  It downloads EDGAR
metadata and potentially relevant primary documents, then writes mechanical
text flags and snippets for a later source-ledger review.  It is the only
network-fetching component of this research track.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup


HERE = Path(__file__).resolve().parent
CACHE = HERE / "sec_primary"
CIK = "0001050446"  # Strategy / MicroStrategy Incorporated
CIK_NO_DASH = str(int(CIK))
SEC_DATA = "https://data.sec.gov"
SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
HEADERS = {
    "User-Agent": "CCP issuance-event academic research contact@example.com",
    "Accept-Encoding": "gzip, deflate",
}
START = pd.Timestamp("2019-12-01")
END = pd.Timestamp("2026-10-16")
FORMS = {
    "8-K",
    "424B1",
    "424B2",
    "424B3",
    "424B4",
    "424B5",
    "424B7",
    "424B8",
    "FWP",
    "S-3",
    "S-3/A",
    "S-3ASR",
    "S-3MEF",
    "S-1",
    "S-1/A",
}


def get(session: requests.Session, url: str, json_response: bool = False) -> Any:
    """Retrieve an SEC resource conservatively and fail rather than skip it."""
    last: Exception | None = None
    for attempt in range(5):
        try:
            response = session.get(url, headers=HEADERS, timeout=45)
            if response.status_code == 200:
                time.sleep(0.16)  # <= 6.25 requests/s, below SEC's 10/s guidance
                return response.json() if json_response else response.text
            if response.status_code in {403, 429, 500, 502, 503, 504}:
                time.sleep(1.0 + attempt)
                continue
            response.raise_for_status()
        except requests.RequestException as exc:
            last = exc
            time.sleep(1.0 + attempt)
    raise RuntimeError(f"SEC retrieval failed after retries: {url}; last={last}")


def rows(table: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = list(table)
    count = len(table[keys[0]]) if keys else 0
    return [{key: table[key][i] for key in keys} for i in range(count)]


def plain_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))


def snippet(text: str, positions: list[int], radius: int = 900) -> str:
    if not positions:
        return ""
    start = max(0, min(positions) - 180)
    return text[start : start + radius]


def mechanical_flags(text: str) -> dict[str, Any]:
    lower = text.lower()
    convertible_positions = [
        match.start()
        for match in re.finditer(r"convertible(?:\s+(?:senior\s+)?)?notes?", lower)
    ]
    atm_positions = [
        match.start()
        for match in re.finditer(
            r"at[- ]the[- ]market|\batm\s+(?:offering|program|sales)|equity distribution agreement|sales agreement",
            lower,
        )
    ]
    initiation = bool(
        re.search(
            r"proposes?\s+to\s+offer|proposed\s+(?:private\s+)?offering|"
            r"announced\s+(?:the\s+)?pricing|announced\s+(?:a\s+)?(?:private\s+)?offering|"
            r"commenced\s+(?:a\s+)?(?:private\s+)?offering|entered\s+into|"
            r"launch(?:ed|es)\s+(?:a\s+)?(?:new\s+)?(?:at[- ]the[- ]market|ATM)",
            lower,
        )
    )
    is_convertible_candidate = bool(convertible_positions) and initiation
    is_atm_candidate = bool(atm_positions) and initiation
    return {
        "has_convertible_terms": bool(convertible_positions),
        "has_atm_terms": bool(atm_positions),
        "has_initiation_language": initiation,
        "convertible_candidate": is_convertible_candidate,
        "atm_candidate": is_atm_candidate,
        "snippet": snippet(text, convertible_positions + atm_positions),
    }


def main() -> None:
    CACHE.mkdir(exist_ok=True)
    session = requests.Session()
    submission = get(session, f"{SEC_DATA}/submissions/CIK{CIK}.json", json_response=True)
    tables = [submission["filings"]["recent"]]
    for old_file in submission["filings"].get("files", []):
        tables.append(get(session, f"{SEC_DATA}/submissions/{old_file['name']}", json_response=True))
    filings = pd.DataFrame([record for table in tables for record in rows(table)])
    filings["filingDate"] = pd.to_datetime(filings["filingDate"])
    forms = filings["form"].fillna("").str.upper()
    scope = filings.loc[
        filings["filingDate"].between(START, END) & forms.isin(FORMS)
    ].copy()
    scope = scope.sort_values(["filingDate", "acceptanceDateTime", "accessionNumber"]).drop_duplicates("accessionNumber")
    required = ["filingDate", "acceptanceDateTime", "accessionNumber", "form", "primaryDocument", "items", "reportDate"]
    for column in required:
        if column not in scope:
            scope[column] = ""
    scope[required].to_csv(HERE / "sec_filings_index.csv", index=False)
    print(f"scoped SEC filings: {len(scope)}")

    sources: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for row_number, (_, row) in enumerate(scope.iterrows(), start=1):
        accession = str(row["accessionNumber"])
        primary_doc = str(row["primaryDocument"] or "")
        if not primary_doc or primary_doc.lower() == "nan":
            failures.append({"accession": accession, "error": "missing primaryDocument"})
            continue
        filename = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{accession}_{primary_doc}")
        cached = CACHE / filename
        url = f"{SEC_ARCHIVES}/{CIK_NO_DASH}/{accession.replace('-', '')}/{primary_doc}"
        try:
            if cached.exists():
                html = cached.read_text(encoding="utf-8", errors="replace")
            else:
                html = get(session, url)
                cached.write_text(html, encoding="utf-8")
            text = plain_text(html)
            flags = mechanical_flags(text)
            sources.append(
                {
                    "filing_date": pd.Timestamp(row["filingDate"]).date().isoformat(),
                    "acceptance_utc": row["acceptanceDateTime"],
                    "accession": accession,
                    "form": row["form"],
                    "items": row["items"],
                    "report_date": row["reportDate"],
                    "primary_document": primary_doc,
                    "source_url": url,
                    "source_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
                    "local_cache": str(cached.relative_to(HERE)),
                    "text_characters": len(text),
                    **flags,
                }
            )
        except Exception as exc:  # Fail closed after creating a failure record.
            failures.append({"accession": accession, "error": str(exc)})
        if row_number % 25 == 0 or row_number == len(scope):
            print(f"processed {row_number}/{len(scope)}; candidates={sum(x['convertible_candidate'] or x['atm_candidate'] for x in sources)}")

    pd.DataFrame(sources).to_csv(HERE / "source_scan.csv", index=False)
    pd.DataFrame(failures, columns=["accession", "error"]).to_csv(HERE / "source_failures.csv", index=False)
    if failures:
        raise RuntimeError(f"{len(failures)} primary-document failures; do not use a partial event universe")
    candidates = pd.DataFrame(sources)
    candidates = candidates.loc[candidates.convertible_candidate | candidates.atm_candidate].copy()
    candidates.to_csv(HERE / "candidate_sources.csv", index=False)
    print(f"complete: {len(sources)} sources, {len(candidates)} mechanical candidates")


if __name__ == "__main__":
    main()
