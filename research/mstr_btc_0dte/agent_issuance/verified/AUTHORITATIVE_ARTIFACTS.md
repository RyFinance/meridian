# Issuance-event study: authoritative boundary

This `verified/` directory is the complete, attributable record for the
issuance / convertible research track started on 2026-10-17.  Files in its
parent `agent_issuance/` directory pre-date this run and are **not inputs or
evidence** for this study.

The authoritative chain is:

1. `PROTOCOL.md` — written before return analysis;
2. `collect_sec_sources.py` and `sec_filings_index.csv` — SEC EDGAR metadata
   and primary-document cache;
3. `candidate_sources.csv` / `event_ledger.csv` — source URLs, EDGAR acceptance
   timestamps, event classifications, and deduplication decisions;
4. `development_candidate_summary.csv`, `development_event_trades.csv`,
   `development_matched_controls.csv`, `development_manifest.json` —
   development-only selection evidence;
5. `FROZEN_RULES.md` — the rule-freeze decision (no rule frozen) recorded before
   any 2024+ issuance-event return calculation;
6. `validate_frozen.py`, `holdout_results.*`, and `REPORT.md` — a single sealed
   2024–2026 evaluation if a development rule qualifies.

In this run no rule passed development, so there is intentionally no
validate_frozen.py or holdout return artifact. DATA_INTEGRITY_NOTE.md records
the limited up-front input inventory and the precise scope of the no-holdout
claim.

No purchase-event data, pre-existing `HOLDOUT_*` artifact, or parent-directory
CSV is used in the calculations.  A source document is considered available
only at its SEC `acceptanceDateTime`; trading is delayed to a conservative
subsequent regular-hours open when required.
