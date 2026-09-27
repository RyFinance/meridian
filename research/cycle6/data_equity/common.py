"""Cycle-6 equity data agent plumbing (DATA WORK ONLY; no signal/strategy/portfolio returns).

Raw bytes go through research.collectors.common.write_snapshot into data/cycle6/equity/raw;
every attempt is appended to raw/_attempts.jsonl (retrieval UTC recorded from the ingest, never mtime).
"""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path
from typing import Any

from research.collectors import common as cc

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "cycle6" / "equity"
RAW = OUT / "raw"
META = OUT / "meta"
PRIOR = ROOT / "data" / "core_premia" / "rates_fx_eq"
ATTEMPTS = RAW / "_attempts.jsonl"
for _d in (RAW, META):
    _d.mkdir(parents=True, exist_ok=True)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def log_attempt(rec: dict[str, Any]) -> None:
    with ATTEMPTS.open("a") as f:
        f.write(json.dumps({"logged_at_utc": utc_now().isoformat(), **rec}, sort_keys=True, default=str) + "\n")


def fetch(source: str, name: str, url: str, *, ext: str, retries: int = 4, backoff: float = 2.0,
          timeout: float = 120.0, validate=None) -> dict[str, Any] | None:
    import requests
    for attempt in range(1, retries + 1):
        t0 = utc_now()
        status, nbytes, err = None, 0, None
        try:
            r = requests.get(url, headers={"User-Agent": cc.USER_AGENT}, timeout=timeout)
            status, body = r.status_code, r.content
            nbytes = len(body)
            if status in cc.NO_RETRY_STATUS:
                log_attempt({"source": source, "name": name, "url": url, "attempt": attempt, "http_status": status,
                             "outcome": "blocked_no_retry"})
                return None
            if status == 200 and nbytes > 0:
                ok, why = (True, "") if validate is None else validate(body)
                if ok:
                    rec = cc.write_snapshot(source, name, body, when=t0, ext=ext, root=RAW,
                                            extra_meta={"url": url, "http_status": status, "attempt": attempt})
                    log_attempt({"source": source, "name": name, "url": url, "attempt": attempt, "http_status": status,
                                 "bytes": nbytes, "outcome": "ok", "path": rec["path"]})
                    return rec
                err = f"validation failed: {why}"
                if "0 bars" in why or "no data" in why:
                    log_attempt({"source": source, "name": name, "url": url, "attempt": attempt,
                                 "http_status": status, "outcome": "empty", "error": err})
                    return None
            else:
                err = f"http {status} / {nbytes} bytes"
        except Exception as e:  # noqa: BLE001
            err = repr(e)[:300]
        log_attempt({"source": source, "name": name, "url": url, "attempt": attempt, "http_status": status,
                     "bytes": nbytes, "outcome": "retry" if attempt < retries else "failed", "error": err})
        time.sleep(backoff * attempt)
    return None


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")


def latest(source: str, name: str) -> tuple[Path, dict] | None:
    man = RAW / source / "manifest.jsonl"
    if not man.exists():
        return None
    best = None
    for line in man.read_text().splitlines():
        rec = json.loads(line)
        if rec["name"] == name:
            best = rec
    return (RAW / best["path"], best) if best else None
