# Authoritative artifacts for the mNAV-dynamics track

Only the files listed below are outputs or source code from this mNAV-dynamics
run. They are the sole authoritative basis for `REPORT.md` and the result
summary provided to the parent task.

## Protocol and code

- `FROZEN_RULES.json`
- `FROZEN_RULES_AMENDMENT_01.json`
- `fetch_sec_sources.py`
- `download_dev_filings.py`
- `download_holdout_filings.py`
- `mnav_core.py`
- `dev_research.py`
- `validate_frozen.py`

## Cached source evidence

- `sec_source/MANIFEST.json`
- `sec_source/submissions.json`
- `sec_source/CIK0001050446-submissions-001.json`
- `sec_source/companyfacts.json`
- `sec_source/dev_filings/`
- `sec_source/holdout_filings/`
- `DEV_SEC_OBSERVATIONS.csv`
- `ALL_SEC_OBSERVATIONS.csv`

## Development outputs

- `DEV_AUDIT.json`
- `DEV_GRID.csv`
- `DEV_BENCHMARK.csv`
- `DEV_PANEL.parquet`

## Sealed outputs and checks

- `SEALED_RUN_MANIFEST.json`
- `SEALED_PANEL.parquet`
- `SEALED_SIGNALS.parquet`
- `DEV_VS_SEALED_SUMMARY.csv`
- `SUBPERIOD_RESULTS.csv`
- `SEALED_TRADES_M1.csv`
- `SEALED_TRADES_M2.csv`
- `SEALED_TRADES_M3.csv`
- `SEALED_COST_SENSITIVITY.csv`
- `SEALED_ADJACENT_PARAMETER_DIAGNOSTIC.csv`
- `GAP_POLICY_SENSITIVITY.csv`
- `SHARE_CLASS_SENSITIVITY.csv`
- `BTC_SOURCE_GAPS.csv`
- `SPLIT_SANITY_CHECK.csv`
- `VALIDATION_EXECUTION_AUDIT.json`
- `sealed_run.log`
- `REPORT.md`

In particular, files named `HOLDOUT_*`, `forward_m1.py`,
`holdout_research.py`, and `holdout_run.log` are not part of this run and
were neither read nor used by this track.
