"""Freeze a cycle-7 sample data directory with research.data_snapshot (director tool; no returns computed).

usage: python -m research.cycle7.freeze <data_dir> <dataset_version> <source_label>
Retrieval time comes from the directory's completeness.json (latest retrieval stamp found), never from mtime.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
STORE = REPO / "data/cycle7/snapshot_store"


def _stamps(obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and re.search(r"retriev|utc|fetched", k, re.I) and re.match(r"\d{4}-\d{2}-\d{2}T", v):
                out.append(v)
            _stamps(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _stamps(v, out)


def _iso(ts: str) -> str:
    t = pd.Timestamp(ts)
    return (t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")).isoformat()


def main(data_dir: str, version: str, label: str) -> None:
    root = (REPO / data_dir).resolve()
    comp = json.loads((root / "completeness.json").read_text())
    st = []
    _stamps(comp, st)
    if not st:
        raise SystemExit("no retrieval stamp in completeness.json")
    retrieved = _iso(max(st))
    meta = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        info = dict(source=label, source_identifier=f"{data_dir}/{rel}", retrieved_at=retrieved,
                    logical_as_of="2026-09-27", symbol=p.stem)
        if p.suffix == ".parquet":
            d = pd.read_parquet(p)
            dc = "date" if "date" in d.columns else ("month" if "month" in d.columns else None)
            info["row_count"] = int(len(d))
            if dc is not None and len(d):
                s = pd.to_datetime(d[dc].astype(str))
                info.update(first_timestamp=_iso(str(s.min())), last_timestamp=_iso(str(s.max())), temporal=True)
                if "market_id" in d.columns:
                    info["symbol"] = ",".join(sorted(map(str, d.market_id.unique())))[:2000]
            else:
                info.update(first_timestamp=None, last_timestamp=None, temporal=False)
        else:
            info["row_count"] = int(len(pd.read_csv(p))) if p.suffix == ".csv" else 1
            info.update(first_timestamp=None, last_timestamp=None, temporal=False)
        meta[f"eval/{rel}"] = info
    cl = pd.read_csv(root / "candidate_list.csv")
    fails = cl[cl.qa_status != "PASS"] if "qa_status" in cl.columns else cl.iloc[0:0]
    spec = {"dataset_version": version,
            "scopes": [{"name": "eval", "root": str(root), "include": ["**/*"]}],
            "metadata": meta,
            "universe": {"membership_artifact": "eval/candidate_list.csv",
                         "exclusions": json.loads(fails.to_json(orient="records")),
                         "symbol_mappings": {}, "delistings": [],
                         "delisting_note": "instruments that stopped trading are kept for the dates they traded "
                                           "(last_date in candidate_list.csv)"},
            "intermediate_artifacts": []}
    sp = REPO / f"research/cycle7/snapshot_spec_{version}.json"
    sp.write_text(json.dumps(spec, indent=1, default=str))
    r = subprocess.run([sys.executable, "-m", "research.data_snapshot", "--store", str(STORE), "freeze", str(sp)],
                       cwd=REPO, capture_output=True, text=True)
    print(r.stdout[-2000:], r.stderr[-2000:])


if __name__ == "__main__":
    main(*sys.argv[1:4])
