# Invalidated sealed-run record — do not interpret as a result

The first validation invocation completed using the rule payload frozen in
`FROZEN_RULES.json`, but its ledger parser had a deterministic defect in
post-2024 SEC **BTC Update** tables.  The generic purchase regex read the
header footnote in `BTC Acquired (1)` as a one-bitcoin purchase before seeing
the table row.  It consequently produced 63 spurious one-BTC rows and carried
incorrect holdings between periodic explicit-total resets.

This is a data-extraction failure, not an outcome-driven parameter change.
The resulting artifacts are retained for audit only and are **not
authoritative**:

- `SEALED_SUMMARY.csv` SHA-256:
  `a2670c72c3c04f45a479cf3151de46782640a2888746c7d6c6964d9aa836fd7c`
- `SEALED_INFERENCE.csv` SHA-256:
  `b3be53b2da5d6c2c6f4f605c3d5c189ea77ce10e359bbae4d73327f72f8f1918`
- `SEALED_BTC_LEDGER.csv` SHA-256:
  `81c4a66effd21b9bcc5751e82bbe7716cb7696cad7bade576ad834b1604e0683`

The original source code was the development-frozen
`135e2f17b934dc4d130cae60c15857ba3b9e597be470a7c414217191f51d1e96`.
The corrected extractor, unchanged rule payload, and remedial run protocol
are locked in `FROZEN_RULES_AMENDMENT_01.json` before the corrected run.

No performance conclusion, positive or negative, may be drawn from this
invalidated run.
