"""Pagination status of the direct LSE MCP pulls: per symbol, next asc start and whether asc met the desc block."""
import json
from collections import defaultdict

from research.cycle7.data_fi.common import RAW
from research.cycle7.data_fi.lse_ingest import parse_reply

M = RAW / "lse_mcp" / "manifest.jsonl"


def status():
    recs = [json.loads(line) for line in M.read_text().splitlines()]
    by = defaultdict(list)
    for r in recs:
        by[r["arguments"]["symbol"]].append(r)
    out = {}
    for s, rs in by.items():
        desc_lo = min((r["last"] for r in rs if r["arguments"]["order"] == "desc"), default=None)
        asc_hi = max((r["last"] for r in rs if r["arguments"]["order"] == "asc"), default=None)
        untr = [r for r in rs if not r["truncated"]]
        done = bool(untr) or (desc_lo is not None and asc_hi is not None and asc_hi >= desc_lo)
        out[s] = {"next_asc_start": asc_hi, "desc_earliest": desc_lo, "done": done, "calls": len(rs)}
    return out


if __name__ == "__main__":
    for s, v in sorted(status().items()):
        print(s, v)
