"""Download ONE small quarterly/period sample of each SEC bulk "data set" ZIP that lives
under www.sec.gov/files/... (13F, insider Form 3/4/5, XBRL Financial Statement Data Sets,
fails-to-deliver). www.sec.gov access from this environment is intermittent (some GETs
succeed, some return 403 "Undeclared Automated Tool" / "Request Rate Threshold Exceeded",
HEAD requests fail more often than GET) -- so this retries with backoff and records every
attempt, success or refusal, in the manifest. Per the task's hard constraint, the User-Agent
never carries a personal email; if a URL is refused on every attempt we record the refusal
and move on rather than escalating.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.edgar_scout.sample_bulk_downloads
"""
from __future__ import annotations

import time

from research.edgar_scout.common import DATA_DIR, Manifest, get

TARGETS = {
    # (rel_path under data/edgar_scout/raw/) : url
    "raw/13f_2013q2.zip": "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/2013q2_form13f.zip",
    "raw/insider_2025q3_form345.zip": "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/2025q3_form345.zip",
    "raw/xbrl_fsds_2024q1.zip": "https://www.sec.gov/files/dera/data/financial-statement-data-sets/2024q1.zip",
    "raw/ftd_2024q1a.zip": "https://www.sec.gov/files/data/fails-deliver-data/cnsfails202401a.zip",
}

MAX_ATTEMPTS = 6
BACKOFF_S = [1, 2, 4, 8, 15, 25]


def fetch_with_retry(url: str) -> tuple[int, bytes, list[dict]]:
    attempts = []
    for i in range(MAX_ATTEMPTS):
        resp = get(url, timeout=60)
        attempts.append({"attempt": i + 1, "status": resp.status_code, "bytes": len(resp.content)})
        if resp.status_code == 200:
            return resp.status_code, resp.content, attempts
        time.sleep(BACKOFF_S[min(i, len(BACKOFF_S) - 1)])
    return resp.status_code, resp.content, attempts


def main() -> None:
    manifest = Manifest()
    attempt_log = {}
    for rel_path, url in TARGETS.items():
        print(f"fetching {url} ...")
        status, content, attempts = fetch_with_retry(url)
        attempt_log[rel_path] = attempts
        out = DATA_DIR / rel_path
        out.parent.mkdir(parents=True, exist_ok=True)
        if status == 200:
            out.write_bytes(content)
            manifest.record_bytes(rel_path, url, content, status)
            print(f"  OK: {len(content)/1e6:.2f} MB in {len(attempts)} attempt(s)")
        else:
            manifest.record_refusal(rel_path, url, status, content.decode(errors="replace"))
            print(f"  REFUSED after {len(attempts)} attempts: last status {status}")
    manifest.write(DATA_DIR / "raw" / "manifest.json")
    import json
    (DATA_DIR / "raw" / "attempt_log.json").write_text(json.dumps(attempt_log, indent=1))


if __name__ == "__main__":
    main()
