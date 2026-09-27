"""Probe which SEC/EDGAR hosts are reachable from this environment with a compliant,
non-personal User-Agent, and record the outcome (this is itself a scouting result, not
just plumbing -- it determines what "sample downloads" are even possible here).

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.edgar_scout.probe_access
"""
from __future__ import annotations

from research.edgar_scout.common import DATA_DIR, Manifest, USER_AGENT, get

# One representative URL per host/product. www.sec.gov hosts every *bulk* data set
# (13F, insider Form345, Financial Statement Data Sets, fails-to-deliver, full-index,
# Archives filing documents, cgi-bin company browse). data.sec.gov and efts.sec.gov host
# the JSON submissions/XBRL/full-text-search APIs.
TARGETS = {
    "www.sec.gov/root": "https://www.sec.gov/",
    "www.sec.gov/cgi-bin/browse-edgar": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany",
    "www.sec.gov/Archives/full-index": "https://www.sec.gov/Archives/edgar/full-index/2024/QTR1/form.idx",
    "www.sec.gov/Archives/filing-dir": "https://www.sec.gov/Archives/edgar/data/320193/",
    "www.sec.gov/files/13F-zip": "https://www.sec.gov/files/structureddata/data/form-13f/2013q2_form13f.zip",
    "www.sec.gov/files/insider-zip": "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/2024q1_form345.zip",
    "www.sec.gov/files/dera-fsds-zip": "https://www.sec.gov/files/dera/data/financial-statement-data-sets/2024q1.zip",
    "www.sec.gov/files/ftd-zip": "https://www.sec.gov/files/data/fails-deliver-data/cnsfails202401a.zip",
    "data.sec.gov/submissions": "https://data.sec.gov/submissions/CIK0000320193.json",
    "data.sec.gov/xbrl-companyconcept": "https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/Assets.json",
    "data.sec.gov/xbrl-frames": "https://data.sec.gov/api/xbrl/frames/us-gaap/Assets/USD/CY2023Q4I.json",
    "efts.sec.gov/search": "https://efts.sec.gov/LATEST/search-index?q=%22test%22&forms=8-K&startdt=2024-01-01&enddt=2024-01-02",
}


def main() -> None:
    manifest = Manifest()
    results = {}
    for key, url in TARGETS.items():
        resp = get(url)
        ok = resp.status_code == 200
        results[key] = {
            "url": url,
            "status": resp.status_code,
            "ok": ok,
            "bytes": len(resp.content),
            "content_type": resp.headers.get("Content-Type", ""),
            "title_snippet": _extract_title(resp.text) if not ok else "",
        }
        print(f"{key:38s} {resp.status_code} {'OK' if ok else 'REFUSED'}  {results[key]['title_snippet']}")
        manifest.record_bytes(f"probe/{key.replace('/', '_')}.raw",
                               url, resp.content, resp.status_code)
    (DATA_DIR / "access_probe.json").parent.mkdir(parents=True, exist_ok=True)
    import json
    (DATA_DIR / "access_probe.json").write_text(json.dumps(
        {"user_agent": USER_AGENT, "results": results}, indent=1))
    manifest.write(DATA_DIR / "probe" / "manifest.json")


def _extract_title(html: str) -> str:
    import re
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"<h1>(.*?)</h1>", html, re.S | re.I)
    return m.group(1).strip() if m else html[:120].replace("\n", " ")


if __name__ == "__main__":
    main()
