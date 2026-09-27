"""Shared HTTP/manifest helpers for the survivor-free US equity feasibility pilot (cycle 5, B2).

Policy: User-Agent "quant_v7-research/1.0" (no email, no personal identity), per-host throttling,
no accounts, no API keys, no CAPTCHA / JS-challenge bypass. A refused request is recorded, not
worked around. Every stored response is written under data/survivor_equity_pilot/ and logged to
manifest.jsonl with URL, UTC fetch time, HTTP status, bytes and sha256.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "survivor_equity_pilot"
REPORT_DIR = ROOT / "reports" / "survivor_equity_pilot"
MANIFEST = DATA_DIR / "manifest.jsonl"
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "quant_v7-research/1.0"
HOST_INTERVAL = {  # seconds between calls per host
    "data.sec.gov": 0.25, "efts.sec.gov": 0.3, "www.sec.gov": 1.0,
    "query1.finance.yahoo.com": 1.0, "query2.finance.yahoo.com": 1.0,
    "web.archive.org": 1.5, "archive.org": 1.5,
}
_last: dict[str, float] = {}
_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"})


def _throttle(host: str) -> None:
    gap = HOST_INTERVAL.get(host, 0.5)
    wait = gap - (time.monotonic() - _last.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.monotonic()


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_name(url: str) -> str:
    s = re.sub(r"^https?://", "", url)
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    return s[:180]


def fetch(url: str, subdir: str, fname: str | None = None, timeout: int = 40, retries: int = 2,
          store: bool = True) -> tuple[int, bytes | None, str | None]:
    """GET url; store body under DATA_DIR/subdir; append manifest line. Returns (status, body, relpath).

    Retries only on network errors / 5xx / 429 with backoff; 403/404 are recorded as-is.
    """
    host = url.split("/")[2]
    status, body = -1, None
    for attempt in range(retries + 1):
        _throttle(host)
        try:
            r = _session.get(url, timeout=timeout)
            status, body = r.status_code, r.content
            if status in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(3 * (attempt + 1))
                continue
            break
        except requests.RequestException as e:  # record and retry
            status, body = -1, str(e).encode()
            if attempt < retries:
                time.sleep(3 * (attempt + 1))
    rel = None
    if store and body is not None:
        d = DATA_DIR / subdir
        d.mkdir(parents=True, exist_ok=True)
        p = d / (fname or safe_name(url))
        p.write_bytes(body)
        rel = str(p.relative_to(ROOT))
    with MANIFEST.open("a") as f:
        f.write(json.dumps({"url": url, "fetch_time_utc": utcnow(), "status": status,
                            "bytes": len(body) if body else 0,
                            "sha256": hashlib.sha256(body).hexdigest() if body else None,
                            "file": rel}) + "\n")
    return status, body, rel


def cached_json(url: str, subdir: str, fname: str | None = None):
    """Return parsed JSON, reusing a stored copy if the manifest already has a 200 for it."""
    p = DATA_DIR / subdir / (fname or safe_name(url))
    if p.exists() and p.stat().st_size > 0:
        try:
            return 200, json.loads(p.read_bytes())
        except json.JSONDecodeError:
            pass
    st, body, _ = fetch(url, subdir, fname)
    if st == 200 and body:
        try:
            return st, json.loads(body)
        except json.JSONDecodeError:
            return st, None
    try:
        return st, json.loads(body) if body else None
    except (json.JSONDecodeError, TypeError):
        return st, None
