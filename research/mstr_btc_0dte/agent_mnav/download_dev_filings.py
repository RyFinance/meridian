#!/usr/bin/env python3
"""Cache only development-period MSTR 10-Q/10-K source documents from EDGAR."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "sec_source"
OUT = SOURCE / "dev_filings"
CIK = "1050446"
USER_AGENT = "mnav-research/1.0 research@example.invalid"
CUTOFF = "2022-12-31"
START = "2020-08-01"


def load_filings() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for path in [SOURCE / "submissions.json", SOURCE / "CIK0001050446-submissions-001.json"]:
        doc = json.loads(path.read_text())
        fields = doc.get("filings", {}).get("recent", doc)
        for row in zip(
            fields["form"],
            fields["filingDate"],
            fields["reportDate"],
            fields["accessionNumber"],
            fields["primaryDocument"],
        ):
            form, filing_date, report_date, accession, primary_doc = row
            if form in {"10-Q", "10-K"} and START <= filing_date <= CUTOFF:
                records.append(
                    {
                        "form": form,
                        "filing_date": filing_date,
                        "report_date": report_date,
                        "accession": accession,
                        "primary_document": primary_doc,
                    }
                )
    return sorted(records, key=lambda x: x["filing_date"])


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=45) as response:
        return response.read()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    manifest: list[dict[str, str]] = []
    for rec in load_filings():
        acc_no_dash = rec["accession"].replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{acc_no_dash}/{rec['primary_document']}"
        filename = f"{rec['filing_date']}_{rec['form']}_{rec['accession']}.html"
        body = fetch(url)
        if b"MicroStrategy" not in body and b"MICROSTRATEGY" not in body:
            raise RuntimeError(f"Unexpected EDGAR response for {url}")
        (OUT / filename).write_bytes(body)
        manifest.append({**rec, "url": url, "file": filename, "sha256": hashlib.sha256(body).hexdigest()})
        time.sleep(0.15)
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"cached {len(manifest)} development filings at {OUT}")


if __name__ == "__main__":
    main()
