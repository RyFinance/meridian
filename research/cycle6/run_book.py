"""Thin CLI wrapper; all logic (and the guards) lives in the hashed engine: research/cycle6/engine/runner.py."""
import sys

from research.cycle6.engine.guards import GuardError
from research.cycle6.engine.runner import main_book

if __name__ == "__main__":
    try:
        sys.exit(main_book())
    except GuardError as exc:
        sys.exit(f"REFUSED: {exc}")
