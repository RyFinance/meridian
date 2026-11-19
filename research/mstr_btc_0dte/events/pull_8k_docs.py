"""Download MSTR 8-K primary documents from EDGAR (2020+) into events/docs/, cached.
Rate-limited well below SEC's 10 req/s fair-access limit; retries 429/5xx with backoff.
"""
from __future__ import annotations
import re, sys, time, urllib.request, urllib.error
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)
UA = "quant_v7-research (contact: research@example.com)"
MIN_INTERVAL = 1.0 / 6.0

def fetch(url: str, tries: int = 5) -> bytes:
    last = None
    for i in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 403, 500, 502, 503):
                last = e; time.sleep(2 * (i + 1)); continue
            raise
        except Exception as e:
            last = e; time.sleep(2 * (i + 1))
    raise RuntimeError(f"failed {url}: {last}")

def main():
    k = pd.read_parquet(ROOT / "8k_all.parquet").sort_values("filingDate")
    todo = [(r.accessionNumber, r.primaryDocument) for _, r in k.iterrows()]
    done = failed = skipped = 0
    for acc, doc in todo:
        out = DOCS / f"{acc}.htm"
        if out.exists() and out.stat().st_size > 0:
            skipped += 1; continue
        url = f"https://www.sec.gov/Archives/edgar/data/1050446/{acc.replace('-', '')}/{doc}"
        try:
            body = fetch(url)
            out.write_bytes(body)
            done += 1
        except Exception as e:
            print(f"FAIL {acc} {url}: {e}", file=sys.stderr)
            failed += 1
        time.sleep(MIN_INTERVAL)
    print(f"downloaded={done} skipped={skipped} failed={failed} total={len(todo)}")

if __name__ == "__main__":
    main()
