"""Archive LSE credit-index development inputs through read-only Terminal MCP."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd

from research.lse_mcp_client import Terminal, content_text


OUT = Path("data/lse/credit_lead")
SYMBOLS = ("USD_LIQ_IG", "USD_LIQ_HY")
YEARS = range(2010, 2021)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"source": "LSE Terminal MCP macro_series, dataset=credit_indices",
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "windows": []}
    for symbol in SYMBOLS:
        frames = []
        with Terminal() as terminal:
            for year in YEARS:
                args = {"symbol": symbol, "dataset": "credit_indices",
                        "start": f"{year}-01-01", "end": f"{year}-12-31",
                        "order": "asc", "limit": 5000}
                response = content_text(terminal.call("macro_series", args, timeout=90))
                if "truncated" in response.lower():
                    raise RuntimeError(f"MCP truncation {symbol} {year}")
                rows = json.loads(response)
                if not isinstance(rows, list) or not rows or len(rows) >= 5000:
                    raise RuntimeError(f"Empty/truncated {symbol} {year}")
                raw = OUT / f"{symbol}_{year}.json"
                raw.write_text(response + "\n")
                frame = pd.DataFrame(rows)
                if not {"symbol", "date", "value"}.issubset(frame):
                    raise RuntimeError(f"Unexpected fields {symbol} {year}")
                if not (frame.symbol == symbol).all():
                    raise RuntimeError(f"Symbol contamination {symbol} {year}")
                frame["date"] = pd.to_datetime(frame.date)
                if frame.date.duplicated().any():
                    raise RuntimeError(f"Duplicate dates {symbol} {year}")
                frames.append(frame)
                manifest["windows"].append({"symbol": symbol, "year": year,
                                            "rows": len(frame), "first": frame.date.min().date().isoformat(),
                                            "last": frame.date.max().date().isoformat(),
                                            "raw_path": str(raw), "sha256": sha256(raw.read_bytes()).hexdigest()})
        panel = pd.concat(frames, ignore_index=True).sort_values("date")
        if panel.date.duplicated().any():
            raise RuntimeError(f"Duplicate dates {symbol}")
        path = OUT / f"{symbol}_dev.parquet"
        panel.to_parquet(path, index=False)
        manifest[symbol] = {"rows": len(panel), "first": panel.date.min().date().isoformat(),
                            "last": panel.date.max().date().isoformat(), "panel_path": str(path),
                            "sha256": sha256(path.read_bytes()).hexdigest()}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({symbol: manifest[symbol] for symbol in SYMBOLS}, indent=2))


if __name__ == "__main__":
    main()
