"""Verify the registry's hash chain and print the head line to anchor externally.

    PYTHONPATH=. .venv/bin/python -m research.forward.verify
    PYTHONPATH=. .venv/bin/python -m research.forward.verify --anchors reports/forward/anchors.jsonl
    PYTHONPATH=. .venv/bin/python -m research.forward.verify --expect 1:<sha256>

Exit code 0 = verifies; 1 = any edit, reorder, deletion, broken link, bad time
order, or mismatch with an anchored head.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.forward import registry


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="verify the forward registry hash chain")
    ap.add_argument("--registry", type=Path, default=registry.DEFAULT_REGISTRY)
    ap.add_argument("--anchors", type=Path, default=None, help="JSONL of {seq, hash, anchored_at_utc, channel}")
    ap.add_argument("--expect", action="append", default=[], metavar="SEQ:HASH",
                    help="an anchored head, e.g. from an email or commit message")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    anchors = registry.load_anchors(args.anchors)
    for item in args.expect:
        seq, _, h = item.partition(":")
        anchors.append((int(seq), h.strip()))
    report = registry.verify_chain(args.registry, anchors=anchors)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"{'OK' if report.ok else 'FAILED'}: {report.n_records} records, {report.anchors_checked} anchors checked")
        for e in report.errors:
            print(f"  ERROR line {e.line}: {e.code}: {e.message}")
        if report.head_hash:
            print(registry.head_line(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
