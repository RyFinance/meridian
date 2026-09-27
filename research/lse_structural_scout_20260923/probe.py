"""Read-only LSE MCP check for contract-level futures data availability."""
from __future__ import annotations

import json
import re
from pathlib import Path

from research.lse_mcp_client import Terminal, content_text

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/lse_structural_scout_20260923"


def main():
    catalog = json.loads((ROOT / "data/lse_catalog_20260917.json").read_text())
    futures = [x for x in catalog if x.get("dataset") == "futures"]
    result = {"catalog_futures_count": len(futures),
              "conventional_expiry_symbols": [x["symbol"] for x in futures if re.fullmatch(r"[A-Z]{1,4}[FGHJKMNQUVXZ]\d{2,4}", x["symbol"])],
              "search": {}, "history": {}, "routes": {}}
    with Terminal() as terminal:
        for symbol in ("GC.F", "GCZ25", "GCZ26", "CLZ26", "FGBL", "FGBLZ25", "FGBLH26", "FEU3"):
            result["search"][symbol] = content_text(terminal.call("search_instruments", {"query": symbol, "limit": 5}, 30))[:700]
        for symbol in ("GC.F", "GCZ26", "CLZ26", "FGBL", "FGBLZ25", "FEU3"):
            result["history"][symbol] = content_text(terminal.call("get_history", {"symbol": symbol, "timeframe": "1d", "start": "2025-05-01", "end": "2025-05-10", "limit": 10}, 30))[:650]
        for path in ("/api/futures/contracts", "/api/futures/chain"):
            result["routes"][path] = content_text(terminal.call("api_get", {"path": path}, 30))[:300]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mcp_probe.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"catalog_futures_count": result["catalog_futures_count"],
                      "conventional_expiry_symbols": result["conventional_expiry_symbols"],
                      "route_results": result["routes"]}, indent=2))


if __name__ == "__main__":
    main()
