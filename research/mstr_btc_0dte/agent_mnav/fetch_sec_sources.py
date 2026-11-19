#!/usr/bin/env python3
"""Download the SEC primary datasets used by the mNAV study.

The SEC requires an identifying User-Agent.  Files are cached locally so the
research run is reproducible; this script does not alter any shared project
artifact.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen


CIK = "0001050446"  # MicroStrategy / Strategy Inc.
BASE = "https://data.sec.gov"
USER_AGENT = "mnav-research/1.0 research@example.invalid"
OUT = Path(__file__).resolve().parent / "sec_source"


def get(url: str) -> bytes:
    # Do not request compression: urllib does not transparently decode it.
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=45) as response:
        return response.read()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    sources = {
        "companyfacts.json": f"{BASE}/api/xbrl/companyfacts/CIK{CIK}.json",
        "submissions.json": f"{BASE}/submissions/CIK{CIK}.json",
    }
    manifest: dict[str, dict[str, str]] = {}
    for name, url in sources.items():
        data = get(url)
        # Verify that responses are JSON before persisting them as input data.
        json.loads(data)
        target = OUT / name
        target.write_bytes(data)
        manifest[name] = {"url": url, "sha256": hashlib.sha256(data).hexdigest()}
    # The SEC keeps older filings in one or more historical submissions files.
    # Fetch the linked files too; the current submissions feed is otherwise
    # truncated before the initial bitcoin-acquisition period.
    submissions = json.loads((OUT / "submissions.json").read_bytes())
    for entry in submissions.get("filings", {}).get("files", []):
        name = entry["name"]
        url = f"{BASE}/submissions/{name}"
        data = get(url)
        json.loads(data)
        (OUT / name).write_bytes(data)
        manifest[name] = {"url": url, "sha256": hashlib.sha256(data).hexdigest()}
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
