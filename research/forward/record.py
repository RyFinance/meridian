"""Manual entry point for writing to the forward registry. Never scheduled.

    # create a registry (genesis only; refuses to overwrite)
    PYTHONPATH=. .venv/bin/python -m research.forward.record --init
    # register the frozen momentum_gold_v1 spec (once)
    PYTHONPATH=. .venv/bin/python -m research.forward.record --strategy momentum_gold_v1 --register-spec
    # the decision: run after the 2026-10-01 close (>= 16:15 ET) and before the 2026-10-02 open (09:30 ET)
    PYTHONPATH=. .venv/bin/python -m research.forward.record --strategy momentum_gold_v1 --date 2026-10-01
    # PEAD: read-only ingest of the bot's live decisions (registers the running code on first use)
    PYTHONPATH=. .venv/bin/python -m research.forward.record --strategy pead_bot_v1 --ingest
    # a future research candidate
    PYTHONPATH=. .venv/bin/python -m research.forward.record --strategy my_cand_v1 --register-spec path/spec.json
    PYTHONPATH=. .venv/bin/python -m research.forward.record --strategy my_cand_v1 --date 2026-10-05 --targets '{"SPY": 1.0}'
    # retract a mistaken record without editing history
    PYTHONPATH=. .venv/bin/python -m research.forward.record --void 7 --reason "wrong date"

Every command accepts --registry PATH (default reports/forward/registry.jsonl)
and --dry-run (print the record, write nothing).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from research.forward import adapters, nyse, registry
from research.forward.prices import default_pricebook


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="write one entry to the forward registry (manual, not scheduled)")
    ap.add_argument("--registry", type=Path, default=registry.DEFAULT_REGISTRY)
    ap.add_argument("--init", action="store_true", help="create the registry with a genesis record")
    ap.add_argument("--strategy")
    ap.add_argument("--register-spec", nargs="?", const="", default=None, metavar="SPEC_JSON",
                    help="register a spec (momentum_gold_v1: no argument; generic: path to spec JSON)")
    ap.add_argument("--date", help="decision date YYYY-MM-DD")
    ap.add_argument("--targets", help='generic strategies: JSON weights, e.g. \'{"SPY": 0.6, "GLD": 0.4}\'')
    ap.add_argument("--ingest", action="store_true", help="pead_bot_v1: ingest live decisions from bot/state (read-only)")
    ap.add_argument("--bot-state", type=Path, default=adapters.BOT_STATE)
    ap.add_argument("--void", type=int, help="seq of a record to retract")
    ap.add_argument("--reason", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--price-source", choices=["lse", "yfinance"], default="lse")
    ap.add_argument("--no-prices", action="store_true", help="do not snapshot as-of closes (offline)")
    ap.add_argument("--allow-late", action="store_true",
                    help="record a decision after its execution time, flagged and excluded from evaluation")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    path = args.registry

    try:
        if args.init:
            if args.dry_run:
                print(f"would create {path} with a genesis record")
                return 0
            rec = registry.init(path, note=args.note)
            print(json.dumps(rec, indent=2))
            return 0
        if args.void is not None:
            if not args.reason:
                raise SystemExit("--void needs --reason")
            if args.dry_run:
                print(f"would void seq {args.void}: {args.reason}")
                return 0
            rec = registry.append(path, "void", strategy_id=args.strategy, payload={"voids_seq": args.void, "reason": args.reason})
            print(json.dumps(rec, indent=2))
            return 0
        if not args.strategy:
            ap.error("--strategy is required")
        sid = args.strategy
        if args.register_spec is not None:
            if sid == adapters.MG_ID:
                rec = adapters.register_momentum_gold(path, dry_run=args.dry_run)
            elif sid == adapters.PEAD_ID:
                raise SystemExit("pead_bot_v1 registers itself on the first --ingest")
            else:
                if not args.register_spec:
                    raise SystemExit("generic strategies: --register-spec path/to/spec.json")
                rec = adapters.register_generic(path, sid, Path(args.register_spec), dry_run=args.dry_run)
            print(json.dumps(rec, indent=2, default=str))
            return 0
        if args.ingest:
            if sid != adapters.PEAD_ID:
                raise SystemExit("--ingest is only for pead_bot_v1")
            summary = adapters.ingest_pead(path, state_dir=args.bot_state, dry_run=args.dry_run)
            print(json.dumps(summary, indent=2, default=str))
            return 0
        if not args.date:
            ap.error("--date is required for a decision")
        day = nyse.to_date(args.date)
        book = None if args.no_prices else default_pricebook(args.price_source)
        try:
            if sid == adapters.MG_ID:
                rec = adapters.record_momentum_gold(path, day, pricebook=book, allow_late=args.allow_late,
                                                    dry_run=args.dry_run)
            else:
                targets = json.loads(args.targets) if args.targets else None
                rec = adapters.record_targets_decision(path, sid, day, targets=targets, pricebook=book,
                                                       allow_late=args.allow_late, dry_run=args.dry_run)
        finally:
            if book is not None:
                book.close()
        print(json.dumps(rec, indent=2, default=str))
        if not args.dry_run:
            report = registry.verify_chain(path)
            print(registry.head_line(report))
        return 0
    except (adapters.AdapterError, registry.RegistryError) as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
