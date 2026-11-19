# Weekly issuance panel — anchor QA (descriptive artifact)

Five hand-picked anchor filings re-checked against the extracted CSVs and
(where the scratch SEC cache is present) the raw filing text. No returns,
no hypothesis; this only documents extraction fidelity for the eras used by
the descriptive panel. Anchors were taken by hand from the filings during
the 2026-10-17 review before this QA was written.

| Anchor | CSV extraction | Source document | Note |
| --- | --- | --- | --- |
| A1-2024-11-18 | PASS | all strings found | narrative era; the week that funded the 51,780 BTC purchase |
| A2-2025-06-16 | PASS | all strings found | zero-common week (preferred-only sales) |
| A3-2026-03-09 | PASS | all strings found | merged-cell table variant week |
| A4-2026-04-06 | PASS | all strings found | two reporting segments in one 8-K |
| A5-2026-10-05 | PASS | all strings found | repurchase-era week; MSTR sold only in the October segment |

Overall: **PASS** (5 anchors; tolerance ±$0.05M on rounded filing values; shares exact).
