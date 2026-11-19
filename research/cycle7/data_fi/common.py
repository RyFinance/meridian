"""Shared plumbing for the cycle-7 FI data pass (FI-NEW, FI-DEEP). DATA ONLY: no signals, no strategy returns."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "cycle7" / "fi"
RAW = OUT / "raw"
META = OUT / "meta"
D6 = ROOT / "data" / "cycle6"
OLD = ROOT / "data" / "core_premia" / "rates_fx_eq"
for _d in (OUT, RAW, META):
    _d.mkdir(parents=True, exist_ok=True)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    return sha_bytes(Path(p).read_bytes())


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, sort_keys=True, default=str))
