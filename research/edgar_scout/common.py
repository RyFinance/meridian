"""Shared HTTP + manifest helpers for the EDGAR/SEC data scout (research cycle 4, Workload B).

Fair-access policy: SEC asks for <=10 req/s; we cap at 4 req/s (0.25s min spacing) to every
*.sec.gov host. User-Agent is descriptive and carries NO personal email, per the task's hard
constraint ("do NOT impersonate a person or use anyone's email"). If a host refuses that
User-Agent, we record the refusal (host, path, status, response snippet) instead of retrying
around it or escalating to a real contact address.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "edgar_scout"
REPORT_DIR = ROOT / "reports" / "edgar_scout"

USER_AGENT = "quant_v7-research/1.0 (non-commercial research)"
MIN_INTERVAL_S = 0.25  # 4 req/s, under the 5 req/s self-imposed cap and SEC's 10 req/s ceiling

_last_call: dict[str, float] = {}


def _throttle(host: str) -> None:
    last = _last_call.get(host, 0.0)
    now = time.monotonic()
    wait = MIN_INTERVAL_S - (now - last)
    if wait > 0:
        time.sleep(wait)
    _last_call[host] = time.monotonic()


def get(url: str, timeout: int = 20) -> requests.Response:
    """GET with the descriptive non-personal User-Agent and per-host throttling."""
    host = url.split("/")[2]
    _throttle(host)
    return requests.get(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"},
                         timeout=timeout)


@dataclass
class Manifest:
    """Accumulates {path: {url, fetch_time, sha256, bytes, status}} and writes it out as JSON."""
    entries: dict[str, dict[str, Any]] = field(default_factory=dict)

    def record_bytes(self, rel_path: str, url: str, content: bytes, status: int) -> None:
        self.entries[rel_path] = {
            "url": url,
            "fetch_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": status,
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    def record_refusal(self, key: str, url: str, status: int, snippet: str) -> None:
        self.entries[key] = {
            "url": url,
            "fetch_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": status,
            "refused": True,
            "response_snippet": snippet[:300],
        }

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.entries, indent=1, sort_keys=True))


def save_json(rel_path: str, obj: Any, manifest: Manifest, url: str, status: int = 200) -> Path:
    """Write obj as pretty JSON under DATA_DIR/rel_path and register it in manifest."""
    out = DATA_DIR / rel_path
    out.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(obj, indent=1, sort_keys=True).encode()
    out.write_bytes(content)
    manifest.record_bytes(rel_path, url, content, status)
    return out
