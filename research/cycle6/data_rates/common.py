"""Shared plumbing for the cycle-6 rates/FX/commodity data pass. DATA ONLY: no signals, no strategy returns."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "cycle6" / "rates"
RAW = OUT / "raw"
META = OUT / "meta"
OLD = ROOT / "data" / "core_premia" / "rates_fx_eq"
COMM = ROOT / "data" / "core_premia" / "commod_bench"
for _d in (OUT, RAW, META):
    _d.mkdir(parents=True, exist_ok=True)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, sort_keys=True, default=str))
