"""Freeze cycle-8 inputs (data/cycle8/proc + data/cycle8/cma) with research.data_snapshot. No returns computed."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
STORE = REPO / "data/cycle8/snapshot_store"
VERSION = "cycle8_v1"


def _stamps(obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and re.search(r"retriev|utc|fetched", k, re.I) and re.match(r"\d{4}-\d{2}-\d{2}T", v):
                out.append(v)
            _stamps(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _stamps(v, out)


def _iso(ts):
    t = pd.Timestamp(ts)
    return (t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")).isoformat()


def meta_for(scope, root, p, fallback):
    rel = p.relative_to(root).as_posix()
    mj = REPO / "data/cycle8/meta" / f"{p.name}.json"
    st, src, url = [], "cycle8 data pass", None
    if mj.exists():
        j = json.loads(mj.read_text())
        _stamps(j, st)
        src = str(j.get("source", src))[:500]
        url = j.get("url") or j.get("urls") or j.get("source_url")
        url = json.dumps(url)[:500] if url is not None else None
    info = dict(source=src, source_identifier=url or f"data/cycle8/{scope}/{rel}",
                retrieved_at=_iso(max(st)) if st else fallback, logical_as_of="2026-09-28", symbol=p.stem)
    if p.suffix == ".parquet":
        d = pd.read_parquet(p)
        info["row_count"] = int(len(d))
        try:
            ix = pd.DatetimeIndex(d.index)
            info.update(first_timestamp=_iso(ix.min()), last_timestamp=_iso(ix.max()), temporal=True)
        except Exception:
            info.update(first_timestamp=None, last_timestamp=None, temporal=False)
    else:
        try:
            info["row_count"] = int(len(pd.read_csv(p))) if p.suffix == ".csv" else 1
        except Exception:
            info["row_count"] = 1
        info.update(first_timestamp=None, last_timestamp=None, temporal=False)
    return f"{scope}/{rel}", info


def main():
    fallback = "2026-09-28T07:00:00+00:00"
    scopes, meta = [], {}
    for scope, root, inc in [("proc", REPO / "data/cycle8/proc", ["**/*.parquet", "**/*.csv"]),
                             ("cma", REPO / "data/cycle8/cma", ["*.csv"])]:
        scopes.append({"name": scope, "root": str(root), "include": inc})
        files = sorted(set(q for pat in inc for q in root.glob(pat) if q.is_file()))
        for p in files:
            k, v = meta_for(scope, root, p, fallback)
            meta[k] = v
    inv = "proc/etf_inventory.csv"
    spec = {"dataset_version": VERSION, "scopes": scopes, "metadata": meta,
            "universe": {"membership_artifact": inv, "exclusions": [], "symbol_mappings": {}, "delistings": [],
                         "delisting_note": "index/sleeve inputs, no stock universe; ETF inventory lists tickers"},
            "intermediate_artifacts": []}
    sp = REPO / f"research/cycle8/snapshot_spec_{VERSION}.json"
    sp.write_text(json.dumps(spec, indent=1, default=str))
    r = subprocess.run([sys.executable, "-m", "research.data_snapshot", "--store", str(STORE), "freeze", str(sp)],
                       cwd=REPO, capture_output=True, text=True)
    print(r.stdout[-3000:], r.stderr[-3000:])


if __name__ == "__main__":
    main()
