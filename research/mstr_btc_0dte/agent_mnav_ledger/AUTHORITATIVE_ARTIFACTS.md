# Authoritative artifacts — 8-K holdings-ledger study

Only the following files in this directory are authoritative for this separate
workstream:

- `PROTOCOL.md` — pre-result methodology and research firewall.
- `ledger_study.py` — deterministic parser, panel builder, execution engine,
  statistics, and phase runner.
- `DEV_*` — development-only inputs, ledger, panel and results.
- `FROZEN_RULES.json` — rule payload and SHA-256 written before validation.
- `FROZEN_RULES_AMENDMENT_02.json` and
  `PARSER_REMEDIATION_02_SOURCE_AUDIT.md` — the now-superseded ledger-parser
  provenance amendment and its source-reconciliation evidence.  They remain
  audit records, not a complete validation clearance.
- `REPORT.md` — final interpretation and limitations.

Inputs are read-only files outside this directory.  Every phase writes an
input-manifest that gives their SHA-256 hashes, the precise input conventions,
and the hashes of each SEC primary document used in its ledger.

No `HOLDOUT_*` file elsewhere in `research/mstr_btc_0dte` is an input or
authority for this study.

There is presently **no authoritative validation-result set**.  `SEALED_*`
without a remediation prefix is retained only as the explicitly invalidated
initial parser-run record documented in `SEALED_RUN_01_INVALID.md`.
`SEALED_REMEDIATION_01_*` is retained only as the explicitly invalidated
intermediate parser-run record documented in
`SEALED_REMEDIATION_01_INVALID.md`.  `SEALED_REMEDIATION_02_*` is retained
only as the explicitly invalidated share-anchor-run record documented in
`SEALED_REMEDIATION_02_INVALID.md`.  None of those three sets is
authoritative.
