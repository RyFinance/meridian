# MSTR/BTC intraday options search: protocol (registered 2026-10-16, before any 2024+ minute data is viewed)

## Data windows
- Development: 1-minute MSTR option prints from 2020-08-10 to 2023-12-31 (`chunk_000`, already examined in `backtest_tp.py`). Any number of variants may be tried here.
- Validation: 1-minute prints from 2024-01-01 to 2026-09-17. They are LOCKED. `load_1m()` callers must pass `window="dev"`. Validation runs once, only for the frozen candidates listed in `CANDIDATES.md`, after that file is registered in `research/preregistrations.jsonl`.
- Caveat: daily MSTR prices and daily option prints for 2024+ were already seen in `REPORT.md`/`backtest.py` (hold-to-close buying), so validation is clean only for the minute-level path rules.

## Selection and gates
- At most 3 candidates. Each is chosen on dev net results under BOTH fill models, and must be positive under the pessimistic one.
- A dev candidate needs mean net return per trade > 0 under both fill models, t ≥ 2.0 under base fills, and ≥ 150 trades.
- Validation pass requires all of:
  - mean net > 0 under both fill models;
  - one-sided t ≥ 1.65 (Bonferroni over 3 candidates: t ≥ 2.13) under base fills;
  - no single year of 2024, 2025, 2026 with mean below −10% per trade.
- A validation pass leads to a forward paper test only.
