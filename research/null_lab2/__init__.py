"""Workstream C1: null-world calibration across all registered research families.

Submodules:
  families.py    -- the gate table, hand-extracted from each family's PLAN.md / evaluate.py /
                     reports/*/*_results.json (no locked validation data was computed).
  sim_params.py  -- per-family synthetic-series parameters for calibration.
  synth.py       -- vectorised AR(1) synthetic return generators.
  calibrate.py   -- Monte-Carlo gate calibration (P(pass|null), power).
  build_gate_table.py -- dumps families.ROWS to reports/null_lab2/gate_table.csv.
  flags.py       -- derives reports/null_lab2/flags.csv from families.ROWS + calibration.csv.
  multiple_testing.py -- project-wide trial accounting -> reports/null_lab2/multiple_testing.csv.
  run_all.py     -- single entry point that runs everything below the 15-minute CPU budget.

No family's evaluate.py is imported or executed by this package, and no validation-window price or
return data is loaded. Everything here is synthetic-data simulation plus reads of already-existing
reports/*/*.json files.
"""
