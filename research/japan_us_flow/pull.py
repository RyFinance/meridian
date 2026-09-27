"""Archive the registered Japan development input from the read-only LSE MCP."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path

import pandas as pd

from research.lse_mcp_client import Terminal, content_text


OUT = Path("data/lse/japan_us_flow")
_bounds = list(pd.date_range("2016-06-01", "2020-12-01", freq="2MS"))
_bounds.append(pd.Timestamp("2021-01-01"))
RANGES = tuple((a.date().isoformat(), b.date().isoformat()) for a, b in zip(_bounds[:-1], _bounds[1:]))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    frames = []
    with Terminal() as terminal:
        for start, end in RANGES:
            response = content_text(terminal.call("get_history", {
                "symbol": "JP225/USD", "timeframe": "30m", "start": start,
                "end": end, "limit": 5000,
            }, timeout=120))
            lines = response.splitlines()
            if len(lines) < 3 or lines[1] != "time,open,high,low,close,volume":
                raise RuntimeError(f"Unexpected MCP response for {start}: {response[:200]}")
            if "truncated" in response.lower():
                raise RuntimeError(f"MCP response was truncated for {start}")
            raw = OUT / f"JP225_30m_{start[:7].replace('-', '')}.txt"
            raw.write_text(response + "\n")
            frame = pd.read_csv(StringIO("\n".join(lines[1:])))
            frame["time"] = pd.to_datetime(frame["time"], utc=True)
            if frame.empty or len(frame) >= 5000 or frame.time.duplicated().any():
                raise RuntimeError(f"Empty, truncated or duplicate window {start}")
            if frame.time.min() < pd.Timestamp(start, tz="UTC") or frame.time.max() >= pd.Timestamp(end, tz="UTC"):
                raise RuntimeError(f"Unexpected timestamp range {start}")
            frames.append(frame)
            records.append({"start": start, "end_exclusive": end, "rows": len(frame),
                            "first": frame.time.min().isoformat(), "last": frame.time.max().isoformat(),
                            "raw_path": str(raw), "sha256": sha256(raw.read_bytes()).hexdigest()})
    panel = pd.concat(frames, ignore_index=True).sort_values("time")
    if panel.time.duplicated().any():
        raise RuntimeError("Duplicate timestamps across windows")
    panel.to_parquet(OUT / "JP225_30m_dev.parquet", index=False)
    manifest = {"source": "LSE Terminal MCP get_history", "symbol": "JP225/USD",
                "timeframe": "30m", "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "ranges": records, "panel_sha256": sha256((OUT / "JP225_30m_dev.parquet").read_bytes()).hexdigest()}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"rows": len(panel), "first": panel.time.min().isoformat(),
                      "last": panel.time.max().isoformat(), "ranges": records}, indent=2))


if __name__ == "__main__":
    main()
