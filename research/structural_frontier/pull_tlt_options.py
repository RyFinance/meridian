"""Archive historical TLT option contract-day prints for source QA only."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pandas as pd

from data.lse_vault import Vault
from data.pull_options_1d import export_all


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/lse/structural_frontier"
START, END = "2014-06-01", "2023-01-01"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "TLT_options_2014_2022.parquet"
    if path.exists():
        raise SystemExit("Source archive already exists; no replacement")
    data = export_all(Vault(), "TLT", START, END)
    if data.empty or data.ts.max() >= pd.Timestamp(END, tz="UTC"):
        raise RuntimeError("Bad date extent")
    if data.duplicated(["ts", "osi"]).any() or (data.volume <= 0).any():
        raise RuntimeError("Duplicate contract-days or nonpositive volume")
    data.to_parquet(path, index=False)
    manifest = {"source": "LSE options export, timeframe=1d; trade prints, not quotes",
                "underlying": "TLT", "request_start": START, "request_end_exclusive": END,
                "rows": len(data), "dates": int(data.ts.nunique()),
                "first": str(data.ts.min()), "last": str(data.ts.max()),
                "sha256": sha256(path.read_bytes()).hexdigest()}
    (OUT / "TLT_options_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
