"""Single entry point: builds every reports/null_lab2/ output in order.

Run with:
    cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python research/null_lab2/run_all.py

Takes well under the 15-minute CPU budget (the calibration step, the only compute-heavy one, runs
in well under a minute on a single core).
"""
from __future__ import annotations

import csv
import pathlib
import time

from research.null_lab2 import build_gate_table, calibrate, flags, multiple_testing


def main() -> None:
    t0 = time.time()
    build_gate_table.write()

    rows = calibrate.run_all()
    out_path = pathlib.Path("reports/null_lab2/calibration.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {out_path}")

    flags.build()
    multiple_testing.build()
    print(f"done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
