"""Common snapshot writer for research/collectors/*.

Every collector in this package fetches a keyless public endpoint, writes the raw
response bytes as an immutable file, and appends one record to a per-source,
append-only manifest. Nothing here computes a return, a signal, or any derived
statistic -- collectors fetch, hash, and record. That analysis, if any, happens
later, in a different program, against these frozen files.

Layout (all under data/collect/):
    data/collect/<source>/YYYY/MM/DD/<name>.<HHMMSS>.<sha256 prefix>.<ext>
    data/collect/<source>/manifest.jsonl   (one JSON object per line, append-only)

A snapshot path is never overwritten. If the exact path already exists (same
source, name, second, and content hash), write_snapshot raises SnapshotExists
instead of silently clobbering it -- a caller that wants a fresh sample should
simply call again a moment later, which produces a new, additional file.

    UA = "quant_v7-research/1.0"   (no personal email, per the task's rules)
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
COLLECT_ROOT = ROOT / "data" / "collect"
USER_AGENT = "quant_v7-research/1.0"
DEFAULT_TIMEOUT = 20.0
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 1.5

# Status codes that mean "this call is informative as-is, do not retry":
# 403 -- ToS/CDN block (or, for a bi-monthly/dated file, simply not yet published);
# 404 -- not found (dated file not published yet, or wrong URL pattern);
# 451 -- geo-block (Binance et al.); never bypassed, per the project's rules.
NO_RETRY_STATUS = {403, 404, 451}


class SnapshotExists(RuntimeError):
    """Refused to overwrite an existing immutable snapshot file."""


class FetchError(RuntimeError):
    """A GET failed after retries, or returned a status the caller must handle explicitly."""


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def day_dir(source: str, when: dt.datetime, root: Path = COLLECT_ROOT) -> Path:
    return root / source / f"{when:%Y}" / f"{when:%m}" / f"{when:%d}"


def write_snapshot(source: str, name: str, content: bytes, *, when: dt.datetime | None = None,
                    ext: str = "json", root: Path | None = None, extra_meta: dict[str, Any] | None = None,
                    ) -> dict[str, Any]:
    """Write one immutable raw snapshot and append one manifest.jsonl record.

    Returns the manifest record that was appended. `content` is written exactly as
    given (raw bytes) -- collectors do not reformat or subset what the source sent.

    `root` defaults to the CURRENT value of `common.COLLECT_ROOT` (looked up at call
    time, not at import time), so tests can monkeypatch `common.COLLECT_ROOT` to
    redirect every collector's writes into a tmp_path without passing `root=` through
    each collector's own call sites.
    """
    if root is None:
        root = COLLECT_ROOT
    when = when or utc_now()
    d = day_dir(source, when, root)
    d.mkdir(parents=True, exist_ok=True)
    digest = sha256_bytes(content)
    fname = f"{name}.{when:%H%M%S}.{digest[:16]}.{ext}"
    path = d / fname
    if path.exists():
        raise SnapshotExists(f"refusing to overwrite existing snapshot {path}")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(content)
    tmp.rename(path)
    record: dict[str, Any] = {
        "source": source,
        "name": name,
        "fetched_at_utc": when.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "path": str(path.relative_to(root)),
        "bytes": len(content),
        "sha256": digest,
    }
    if extra_meta:
        record.update(extra_meta)
    manifest_path = root / source / "manifest.jsonl"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("a") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def http_get(url: str, *, params: dict | None = None, headers: dict | None = None,
             timeout: float = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES, backoff: float = DEFAULT_BACKOFF):
    """GET with the project's UA and a retry policy that never retries an informative
    status (403/404/451) -- those are reported to the caller as-is, not masked by a retry
    loop. Only transient network errors and 5xx/429 are retried, with linear backoff.
    """
    import requests

    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=hdrs, timeout=timeout)
        except requests.RequestException as e:
            last_err = e
            time.sleep(backoff * (attempt + 1))
            continue
        if resp.status_code in NO_RETRY_STATUS or resp.status_code == 200:
            return resp
        last_err = FetchError(f"GET {url}: HTTP {resp.status_code}: {resp.text[:200]!r}")
        time.sleep(backoff * (attempt + 1))
    raise FetchError(f"GET {url} failed after {retries} attempts: {last_err!r}")


def dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def summarize(source: str, records: list[dict[str, Any]], *, errors: list[str] | None = None,
              blocked: list[str] | None = None) -> dict[str, Any]:
    """A uniform run_once() return shape across every collector."""
    total_bytes = sum(r.get("bytes", 0) for r in records)
    return {
        "source": source,
        "status": "ok" if records and not errors else ("partial" if records else "failed"),
        "n_files": len(records),
        "total_bytes": total_bytes,
        "errors": errors or [],
        "blocked": blocked or [],
        "files": [r["path"] for r in records],
    }
