# Invalidated remediation-01 record — do not interpret as a result

`SEALED_REMEDIATION_01_*` was produced under the unchanged frozen rule
payload, but it is **not a valid holdout result** and must not be interpreted.
The table parser remediation in that run remained incomplete in three
source-evidenced ways:

1. In multi-row BTC Update filings it selected the first table row rather than
   the row with the latest disclosed **As of** date.  This affected, among
   others, the January 5 and April 6, 2026 filings.
2. The loose table search could read an unrelated financial-table number in
   no-purchase disclosures instead of the BTC Update row.
3. Its event predicate was purchase-only, omitting four structured BTC-sale
   filings with explicit current holdings: June 1, July 6, August 3, and
   August 10, 2026.  The July 6 filing contains two sale periods and its
   latest source row is 2,225 BTC sold / 843,775 BTC held as of July 5.

The preserved intermediate output hashes are:

- `SEALED_REMEDIATION_01_SUMMARY.csv`:
  `0c26c30195e03295899c59ad0f25bdbdbce4d4a5a78425c51bb5905607ad60f6`
- `SEALED_REMEDIATION_01_INFERENCE.csv`:
  `3f158b553ba7bbd72612b9aae72f92cf52bbe2852863f08d7f4d1dd75c14550c`
- `SEALED_REMEDIATION_01_BTC_LEDGER.csv`:
  `b586f60e333ba6db2b426a3e939d878d6ef4a863dc2bff2614af97304d35a369`

This is a source-extraction/provenance correction, not an outcome-driven
strategy change.  `FROZEN_RULES_AMENDMENT_02.json` records the unchanged rule
payload and locks the one permitted source-audited final run under the
`SEALED_REMEDIATION_02_*` prefix.

No positive or negative performance conclusion may be drawn from this
invalidated intermediate run.
