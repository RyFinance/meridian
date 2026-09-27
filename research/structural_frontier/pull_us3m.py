"""Archive LSE date-level US 3-month Treasury yields for put collateral accrual."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pandas as pd

from research.lse_mcp_client import Terminal, content_text


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/lse/structural_frontier"


def main() -> None:
    path = OUT / "US3M_2014_2022.parquet"
    if path.exists():
        raise SystemExit("Source archive already exists; no replacement")
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    with Terminal() as terminal:
        for year in range(2014, 2023):
            raw = content_text(terminal.call("macro_series", {"symbol": "US3M", "dataset": "bonds",
                                                               "start": f"{year}-01-01", "end": f"{year}-12-31",
                                                               "order": "asc", "limit": 500}))
            batch = json.loads(raw)
            rows.extend(batch)
            (OUT / f"US3M_{year}_raw.json").write_text(raw + "\n")
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame.date)
    if frame.empty or frame.date.duplicated().any() or frame.date.max() > pd.Timestamp("2022-12-31"):
        raise RuntimeError("Invalid US3M source extent")
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    audit = {"source": "LSE Terminal MCP macro_series bonds/US3M; yields in annual percent, date only",
             "rows": len(frame), "first": str(frame.date.min()), "last": str(frame.date.max()),
             "weekend_rows": int((frame.date.dt.dayofweek >= 5).sum()),
             "min_yield_percent": float(frame.value.min()), "max_yield_percent": float(frame.value.max()),
             "sha256": sha256(path.read_bytes()).hexdigest()}
    (OUT / "US3M_manifest.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
