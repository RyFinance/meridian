"""Read-only summary of the insider Form 3/4/5 data ALREADY downloaded and used by
research/insider (data/sec_insider/, all 82 quarterly SEC structured ZIPs, 2006q1-2026q2,
per data/sec_insider/manifest.json and reports/insider/REPORT.md). This scout does not
re-download or edit that data; it only measures it, to report accurate scale for the
"already used" row in the dataset catalog.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.edgar_scout.local_insider_stats
"""
from __future__ import annotations

import json

import pandas as pd

from research.edgar_scout.common import DATA_DIR, ROOT

SEC_INSIDER = ROOT / "data" / "sec_insider"


def main() -> None:
    out = {}
    manifest = json.loads((SEC_INSIDER / "manifest.json").read_text())
    out["n_quarterly_zips_already_local"] = len(manifest)
    out["total_bytes_already_local"] = sum(v["bytes"] for v in manifest.values())
    out["quarters_covered"] = sorted(k.replace("_form345.zip", "") for k in manifest)

    own = pd.read_parquet(SEC_INSIDER / "own.parquet")
    out["own_parquet_rows"] = len(own)
    out["own_parquet_cols"] = list(own.columns)
    om = pd.read_parquet(SEC_INSIDER / "om.parquet")
    out["om_parquet_rows"] = len(om)
    out["om_parquet_cols"] = list(om.columns)

    coverage = json.loads((SEC_INSIDER / "coverage.json").read_text())
    out["coverage_json_top_keys"] = list(coverage.keys())

    (DATA_DIR / "local_insider_stats.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: v for k, v in out.items() if not k.endswith("cols")}, indent=1, default=str))


if __name__ == "__main__":
    main()
