"""Build the deterministic snapshot spec from the wave-2 JKP acquisition log."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("data/sol_beyond_menu/wave2_raw").resolve()
OUT = Path("research/sol_beyond_menu/wave2_jkp_freeze_spec.json")


def main() -> None:
    log = json.loads((ROOT / "completeness.json").read_text())
    metadata = {}
    for filename, info in log["records"].items():
        temporal = filename.endswith(".zip")
        metadata[f"raw/{filename}"] = {
            "source": "JKP Global Factor Data public S3, CC BY-NC 4.0",
            "source_identifier": info["endpoint"],
            "retrieved_at": info["retrieved_at_utc"],
            "logical_as_of": "2025-12-31" if temporal else "2026-09-27",
            "symbol": filename,
            "first_timestamp": info["first_timestamp"] + "T00:00:00Z" if temporal else None,
            "last_timestamp": info["last_timestamp"] + "T00:00:00Z" if temporal else None,
            "row_count": info.get("row_count", 0),
            "temporal": temporal,
        }
    for filename, source, count in (
        ("universe.json", "wave-2 preregistered JKP universe artifact", 2),
        ("completeness.json", "JKP acquisition completeness log", len(log["records"])),
    ):
        metadata[f"raw/{filename}"] = {
            "source": source, "source_identifier": None,
            "retrieved_at": log["retrieval_finished_at_utc"],
            "logical_as_of": "2026-09-27", "symbol": filename,
            "first_timestamp": None, "last_timestamp": None,
            "row_count": count, "temporal": False,
        }
    spec = {"dataset_version": "sol_wave2_jkp_v1",
            "scopes": [{"name": "raw", "root": str(ROOT), "include": ["**/*"]}],
            "universe": {"membership_artifact": "raw/universe.json",
                         "exclusions": {"wave2": ["Claude six styles", "wave-1 tests", "paid WRDS stock-level inputs", "2016-01 onward locked"]},
                         "symbol_mappings": {"JKP_ACCRUALS": "accruals", "JKP_DEBT_ISSUANCE": "debt_issuance"},
                         "delistings": {"equity_constituents": "embedded in author-produced JKP factor portfolios; raw security-level delisting file not public"}},
            "intermediate_artifacts": [], "metadata": metadata}
    OUT.write_text(json.dumps(spec, indent=2) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
