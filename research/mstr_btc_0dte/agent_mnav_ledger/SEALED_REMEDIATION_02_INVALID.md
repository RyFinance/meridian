# Invalidated remediation-02 record — do not interpret as a result

`SEALED_REMEDIATION_02_*` completed after the BTC-holdings ledger received a
clean source audit.  A subsequent panel-quality check, however, found a
separate deterministic defect in the reported-share-count input:

- The supplied `events/share_anchors.csv` records `classA=NaN`, `classB=NaN`,
  and `total=0` for the official 2025-05-05 and 2025-08-05 10-Q anchors.
- The code accepted non-null zero totals, then forward-filled the zero-share
  anchor from 2025-05-06 through 2025-11-03.  This made gross mNAV invalid and
  suppressed the rule signal for 126 2025 sessions.
- The corresponding cached SEC cover pages contain explicit, nonzero values:
  253,763,053 Class A + 19,640,250 Class B as of 2025-05-02
  (`0000950170-25-063536`), and 263,912,697 + 19,640,250 as of 2025-07-31
  (`0000950170-25-102209`).

This is a source-extraction/data-provenance defect, not a strategy change.
The repaired share extractor must be audited against every cached official
cover page before any further run is authorized.  In particular, no outcome
statistic from remediation-02 may be used to select a rule or support an edge
claim.

The preserved invalid output hashes are:

- `SEALED_REMEDIATION_02_SUMMARY.csv`:
  `0c26c30195e03295899c59ad0f25bdbdbce4d4a5a78425c51bb5905607ad60f6`
- `SEALED_REMEDIATION_02_INFERENCE.csv`:
  `3f158b553ba7bbd72612b9aae72f92cf52bbe2852863f08d7f4d1dd75c14550c`
- `SEALED_REMEDIATION_02_SHARE_ANCHORS.csv`:
  `4cb27910094ea3d58574f22de1f72aff0c3816b424827a625de21b7d9c96575f`
- `SEALED_REMEDIATION_02_PANEL.parquet`:
  `7665d7be45d46cb071c75467fafa29f902eee15bb274593c479a4b7db0323a98`

No positive or negative performance conclusion may be drawn from this
invalidated run.
