"""Dump families.ROWS to reports/null_lab2/gate_table.csv (task 1)."""
from __future__ import annotations

import csv
import pathlib

from research.null_lab2.families import ROWS

FIELDS = [
    "family", "registered_at", "protocol", "archetype",
    "dev_years", "val_years",
    "dev_thresh_formula", "dev_thresh_val", "dev_kind", "k",
    "dev_null", "dev_alpha", "stress_cond",
    "val_thresh", "val_null", "val_alpha",
    "dev_outcome", "val_outcome", "source", "notes",
]


def write(path: str = "reports/null_lab2/gate_table.csv") -> None:
    out_path = pathlib.Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for row in ROWS:
            d = row.as_row()
            w.writerow({k: d[k] for k in FIELDS})
    print(f"wrote {len(ROWS)} rows to {out_path}")


if __name__ == "__main__":
    write()
