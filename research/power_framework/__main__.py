"""CLI: ``python -m research.power_framework SPEC.json --json-out ... --markdown-out ...``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.power_framework.preregistration import (
    PreregistrationPowerSpec,
    analyze_preregistration,
    freeze_disclosure,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Calculate and freeze a pre-return quant_v7 power disclosure."
    )
    parser.add_argument("spec", type=Path, help="JSON PreregistrationPowerSpec")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="emit a diagnostic disclosure even when protocol checks are incomplete",
    )
    args = parser.parse_args(argv)
    if (args.json_out is None) != (args.markdown_out is None):
        parser.error("--json-out and --markdown-out must be supplied together")
    plan = PreregistrationPowerSpec.from_dict(json.loads(args.spec.read_text()))
    if args.json_out is None:
        disclosure = analyze_preregistration(plan)
        print(json.dumps(disclosure, indent=2, sort_keys=True, allow_nan=False))
        return 0 if disclosure["protocol_amendment_2"]["registration_ready"] else 2
    disclosure = freeze_disclosure(
        plan,
        args.json_out,
        args.markdown_out,
        require_ready=not args.allow_incomplete,
    )
    print(disclosure["sha256"])
    return 0 if disclosure["protocol_amendment_2"]["registration_ready"] else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
