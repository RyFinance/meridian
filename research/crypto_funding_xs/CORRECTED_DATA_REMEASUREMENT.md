# crypto_funding_xs: corrected-data re-measurement of development (registered before the re-run)

Written 2026-09-25 by the director under protocol amendment 1 §C.8. The rule's conditions:
- the spec is unchanged, and only the data changes;
- the re-run is registered before it is executed;
- it is an audit, not a new trial;
- the locked validation window opens only if the corrected development run passes the gate in force when the
  original plan was registered.

## Defect

The as-run development result (Sharpe 1.65, p 0.038, FAIL; `reports/crypto_funding_xs/dev_results.json`) used an
incomplete Binance archive:
- 69 USDT symbols (3,281 files) arrived after the run, because the parallel downloader silently treated failed S3
  listings as empty;
- a strict re-listing (`research/c4_data/verify_binance.py`) then found 202 more missing kline files, including NEAR
  (from 2020-10) and XTZ (from 2020-02). They were fetched on 2026-09-25.
- The archive now matches the S3 listing for every verified symbol. Four 2025+ symbols could not be listed; they have
  no development-window data.
- Evidence: `research/crypto_funding_xs/FROZEN_CLAIM.md` and `data/c4/binance_um/completeness_check.json`.

## Re-measurement (fixed now)

- **Code:** the frozen `core.py` (f7811a55…) and `evaluate.py` (e9ef68b9…), unchanged. They are called by
  `research/crypto_funding_xs/remeasure.py`, which asserts both hashes and writes only to
  `reports/crypto_funding_xs/corrected/`. The original as-run files are preserved.
- **Window:** development only, 2020-01-01 → 2022-12-31.
- **Gate (as originally registered):**
  - base Sharpe ≥ 1.8/√T;
  - stress mean > 0;
  - mean-centred 21-day block-bootstrap p < 0.025.
- **Decision rule:**
  - **FAIL:** the family is settled as a development FAIL on complete data. No further runs.
  - **PASS:** stop. Two independent adversarial audits (implementation/data, statistical/economic). The validation
    window stays locked in this cycle by the user's explicit instruction, and any unlock is the user's decision.
    The claim is NOT declared a survivor.
- **Reporting:** both the as-run and the corrected results are reported, side by side.
