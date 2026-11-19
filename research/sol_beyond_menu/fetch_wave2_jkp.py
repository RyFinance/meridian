"""Acquire only the free JKP theme inputs selected for the wave-2 feasibility screen.

No factor returns are inspected, selected on performance, or calculated here.
Completeness records include source endpoints, retries, expected/received
objects, archive contents, timestamps, instruments and missing cells.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests


ROOT = Path("data/sol_beyond_menu/wave2_raw")
BASE = "https://jkpfactors-data.s3.amazonaws.com/public"
REGIONS = ("usa", "developed", "emerging", "world")


def fetch(url: str, path: Path) -> dict:
    failures = []
    for attempt in range(1, 4):
        try:
            r = requests.get(url, timeout=90)
            r.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
            return {"endpoint": url, "http_status": r.status_code, "attempts": attempt,
                    "failures": failures, "bytes": len(r.content),
                    "sha256": hashlib.sha256(r.content).hexdigest(),
                    "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                    "last_modified": r.headers.get("Last-Modified"),
                    "etag": r.headers.get("ETag")}
        except (requests.RequestException, OSError) as exc:
            failures.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
            if attempt < 3:
                time.sleep(attempt)
    raise RuntimeError(f"download failed after three attempts: {url}: {failures}")


def inspect_zip(path: Path, region: str) -> dict:
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"expected exactly one CSV inside {path}, got {names}")
        text = io.TextIOWrapper(z.open(names[0]), encoding="utf-8-sig", newline="")
        rows = csv.DictReader(text)
        required = {"date", "location", "name", "ret"}
        if not required.issubset(set(rows.fieldnames or [])):
            raise ValueError(f"missing required columns in {path}: {rows.fieldnames}")
        dates, factors, locations = set(), set(), set()
        n = 0
        missing_return = 0
        for row in rows:
            n += 1
            dates.add(row["date"])
            factors.add(row["name"])
            locations.add(row["location"])
            if row["ret"].lower() in ("na", "", "nan"):
                missing_return += 1
        if not dates or not factors:
            raise ValueError(f"empty JKP archive for {region}")
        return {"archive_member": names[0], "row_count": n,
                "first_timestamp": min(dates), "last_timestamp": max(dates),
                "unique_dates": len(dates), "factors": sorted(factors),
                "locations": sorted(locations), "expected_dense_cells": len(dates) * len(factors),
                "received_cells": n, "missing_dense_cells": len(dates) * len(factors) - n,
                "missing_return_values": missing_return}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    records = {}
    manifest_path = ROOT / "jkp_availability.json"
    records["jkp_availability.json"] = fetch(BASE + "/availability.json", manifest_path)
    availability = json.loads(manifest_path.read_text())
    if not all("all_themes" in availability["factors"][r] for r in REGIONS):
        raise ValueError("JKP availability no longer includes all requested theme archives")
    for region in REGIONS:
        filename = f"[{region}]_[all_themes]_[monthly]_[vw_cap].zip"
        url = BASE + "/" + quote(filename)
        info = fetch(url, ROOT / filename)
        info.update(inspect_zip(ROOT / filename, region))
        info["expected_archives"] = 1
        info["received_archives"] = 1
        info["pagination"] = "none; one public archive per region/selector/frequency/weighting"
        records[filename] = info
    docs_url = BASE.replace("/public", "") + "/documents/Documentation.pdf"
    records["JKP_Documentation.pdf"] = fetch(docs_url, ROOT / "JKP_Documentation.pdf")
    records["JKP_Documentation.pdf"].update({"pagination": "none", "expected_documents": 1,
                                                "received_documents": 1})
    now = datetime.now(timezone.utc).isoformat()
    universe = {"dataset_version": "sol_wave2_jkp_v1", "regions": list(REGIONS),
                "selector": "all_themes", "frequency": "monthly", "weighting": "vw_cap",
                "candidate_themes": ["accruals", "debt_issuance"],
                "exclusions": ["all six Claude styles", "wave-1 candidates", "paid stock-level WRDS characteristics"],
                "holdout_rule": "last 25% of complete monthly history, at least 60 months; cut fixed in prereg before returns"}
    (ROOT / "universe.json").write_text(json.dumps(universe, indent=2) + "\n")
    summary = {"retrieval_finished_at_utc": now, "expected_archives": len(REGIONS),
               "received_archives": len(REGIONS), "failed_archives": [],
               "expected_regions": list(REGIONS), "received_regions": list(REGIONS),
               "missing_instruments": [], "records": records}
    (ROOT / "completeness.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: {q: v for q, v in info.items() if q in ("row_count", "first_timestamp", "last_timestamp", "factors", "missing_dense_cells")}
                      for k, info in records.items()}, indent=2))


if __name__ == "__main__":
    main()
