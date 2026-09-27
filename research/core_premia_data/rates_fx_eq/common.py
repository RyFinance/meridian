"""Shared plumbing for the core-premia rates / FX / equity-index data layer.

DATA WORK ONLY. Nothing in this package computes a signal, a signal-conditioned
return, a strategy/control/portfolio return, or a correlation of any signal with
future returns. Instrument-level returns are computed only in ``synthetic.py``
for data QA (synthetic-construction error), as allowed by the task's hard rule.

Raw bytes are written through ``research.collectors.common.write_snapshot`` (the
existing immutable collectors writer) into ``data/core_premia/rates_fx_eq/raw``;
every HTTP attempt (success, empty body, failure, retry) is also appended to
``raw/_attempts.jsonl`` so the acquisition-completeness record can be rebuilt
from the ingest itself, never from filesystem mtimes.
"""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path
from typing import Any

from research.collectors import common as cc

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "core_premia" / "rates_fx_eq"
RAW = DATA / "raw"
PROC = DATA / "processed"
SYN = DATA / "synthetic"
META = DATA / "meta"
REPORT = ROOT / "reports" / "core_premia_20260925" / "rates_fx_eq"
STORE = ROOT / "data" / "core_premia" / "snapshot_store_rates_fx_eq"
ATTEMPTS = RAW / "_attempts.jsonl"
UA = cc.USER_AGENT

for _d in (RAW, PROC, SYN, META, REPORT):
    _d.mkdir(parents=True, exist_ok=True)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def log_attempt(rec: dict[str, Any]) -> None:
    rec = {"logged_at_utc": utc_now().isoformat(), **rec}
    with ATTEMPTS.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True, default=str) + "\n")


def fetch(source: str, name: str, url: str, *, ext: str, params: dict | None = None,
          retries: int = 5, backoff: float = 3.0, min_bytes: int = 1, timeout: float = 120.0,
          validate=None, headers: dict | None = None) -> dict[str, Any] | None:
    """GET ``url`` with retries (network errors, 5xx/429, and *empty 200 bodies*, which the
    Fed DDP returns intermittently). 403/404/451 are recorded and never retried or bypassed.
    On success the raw body is written once via the collectors snapshot writer and the
    manifest record is returned; on final failure ``None`` is returned. Every attempt is logged.
    """
    import requests

    hdrs = {"User-Agent": UA}
    hdrs.update(headers or {})
    for attempt in range(1, retries + 1):
        t0 = utc_now()
        status, nbytes, err = None, 0, None
        try:
            r = requests.get(url, params=params, headers=hdrs, timeout=timeout)
            status, body = r.status_code, r.content
            nbytes = len(body)
            if status in cc.NO_RETRY_STATUS:
                log_attempt({"source": source, "name": name, "url": r.url, "attempt": attempt,
                             "http_status": status, "bytes": nbytes, "outcome": "blocked_no_retry"})
                return None
            if status == 200 and nbytes >= min_bytes:
                ok, why = (True, "") if validate is None else validate(body)
                if ok:
                    rec = cc.write_snapshot(source, name, body, when=t0, ext=ext, root=RAW,
                                            extra_meta={"url": r.url, "http_status": status,
                                                        "attempt": attempt})
                    log_attempt({"source": source, "name": name, "url": r.url, "attempt": attempt,
                                 "http_status": status, "bytes": nbytes, "outcome": "ok",
                                 "path": rec["path"]})
                    return rec
                err = f"validation failed: {why}"
            else:
                err = f"http {status} / {nbytes} bytes"
        except Exception as e:  # network error
            err = repr(e)[:300]
        log_attempt({"source": source, "name": name, "url": url, "params": params, "attempt": attempt,
                     "http_status": status, "bytes": nbytes, "outcome": "retry" if attempt < retries else "failed",
                     "error": err})
        time.sleep(backoff * attempt)
    return None


def latest_raw(source: str, name: str) -> tuple[Path, dict] | None:
    """Most recent successful raw snapshot for (source, name) from its manifest.jsonl."""
    man = RAW / source / "manifest.jsonl"
    if not man.exists():
        return None
    best = None
    for line in man.read_text().splitlines():
        rec = json.loads(line)
        if rec["name"] == name:
            best = rec
    if best is None:
        return None
    return RAW / best["path"], best


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")
