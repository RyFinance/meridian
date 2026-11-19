"""Ingest one LSE MCP `macro_series` reply that the agent called DIRECTLY through the MCP tool (no Python bridge).

The MCP client persists long replies to a tool-results text file; this script copies that file byte-for-byte into
data/cycle7/fi/raw/lse_mcp/, appends a manifest record (tool, arguments, source file, sha256, ingest time) and
reports the complete rows it holds. Replies are cut by the terminal at ~60,000 characters with a
'... truncated' marker; only complete JSON row objects before the cut are used (parse_reply).

Pull protocol (fixed before any data were looked at): per symbol one call order=desc over the whole catalog range
(newest ~1,000 rows), then order=asc calls from the catalog first date, each next call starting at the last complete
date of the previous reply (overlap de-duplicated by date), until the asc replies reach the desc reply's earliest date.
Usage: python -m research.cycle7.data_fi.lse_ingest <tool_result_file> '<json arguments>'
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

from research.cycle7.data_fi.common import RAW, sha_file, utc_now

LSE = RAW / "lse_mcp"
ROW = re.compile(r'\{"symbol":"([^"]+)","date":"(\d{4}-\d{2}-\d{2})","value":(-?[0-9.eE+-]+|null)\}')


def parse_reply(text: str):
    rows = [(s, d, None if v == "null" else float(v)) for s, d, v in ROW.findall(text)]
    return rows, "... truncated" in text[-400:]


def main(src: str, args_json: str):
    args = json.loads(args_json)
    src_p = Path(src)
    syms = {s for s, _, _ in parse_reply(src_p.read_text())[0]}
    if syms != {args["symbol"]}:
        raise SystemExit(f"symbol mismatch: file has {syms}, arguments say {args['symbol']}")
    LSE.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    dst = LSE / f"{args['symbol']}_{args.get('order', 'asc')}_{args.get('start', '')}_{now:%Y%m%dT%H%M%S}.txt"
    shutil.copyfile(src_p, dst)
    text = dst.read_text()
    rows, trunc = parse_reply(text)
    rec = {"tool": "mcp__lse-terminal__macro_series", "arguments": args, "tool_result_file": src_p.name,
           "path": str(dst.relative_to(RAW)), "sha256": sha_file(dst), "bytes": dst.stat().st_size,
           "ingested_at_utc": now.isoformat(), "n_rows": len(rows), "truncated": trunc,
           "first": rows[0][1] if rows else None, "last": rows[-1][1] if rows else None}
    with (LSE / "manifest.jsonl").open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    print(json.dumps({k: rec[k] for k in ("n_rows", "truncated", "first", "last")}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
