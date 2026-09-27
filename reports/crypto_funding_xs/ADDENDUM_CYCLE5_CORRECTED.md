# crypto_funding_xs: cycle-5 addendum (the original REPORT.md is unchanged)

## Data defect

The as-run development result (Sharpe 1.65, p 0.038, FAIL) used an incomplete archive: 69 symbols arrived late and
202 more kline files were missing, including NEAR and XTZ. See `research/crypto_funding_xs/FROZEN_CLAIM.md`.

## Corrected re-measurement (amendment 1 §C.8)

- **Registration:** `research/crypto_funding_xs/CORRECTED_DATA_REMEASUREMENT.md` at 2026-09-25T23:48:08-0700, before
  the run.
- **Code:** unchanged (frozen hashes asserted by `remeasure.py`).
- **Outputs:** `reports/crypto_funding_xs/corrected/`.

| | As run | Corrected |
|---|---|---|
| Base Sharpe | 1.65 | **2.44** (gate 1.15) |
| Stress Sharpe | 0.95 | 1.52 |
| Bootstrap p | 0.038 | **0.0026** (< 0.025) |
| By year | 2020 +16%, 2021 +90%, 2022 −6% | 2020 +54%, 2021 +90%, 2022 −6% |
| Development gate | FAIL | **PASS** |

## Two independent hostile audits

**Implementation** (`reports/audit_funding_impl/REPORT.md`): **SURVIVES.**
- An independent re-implementation reproduces the result exactly.
- No look-ahead: lagging the weights by one day gives Sharpe 1.98.
- **Fixes, none of which changes the gate:**
  - archive gap days wrongly treated as delistings in the stress book (stress Sharpe 1.52 → about 1.87);
  - tie-breaking is mildly favourable (−0.06 Sharpe).

**Statistical and economic** (`reports/audit_funding_stat/REPORT.md`): **WEAKENED.**
- **Regime:** 2020-07 → 2021-06 has Sharpe 4.73. 2021-07 → 2022-12 has Sharpe 0.12 (p 0.45). The 588 days with a
  full 100-name universe have Sharpe 0.27.
- **Concentration:**
  - the top 10 coins make 71% of P&L;
  - one DOGE day makes 11%.
- **Factors:** not a known crypto factor. Alpha t is 3.55 against momentum, reversal, size, low-volatility, market
  and BTC.
- **Calibration:** the 21-day bootstrap under-covers. Under long-dependence nulls, false passes are 7–26%, and p is
  0.023–0.09.
- **Multiple testing:** Šidák over M_eff 25 with the calibrated null gives p ≈ 0.29–0.33.
- **Guards:**
  - G3 (concentration) FAIL;
  - G5 (null calibration) FAIL;
  - G6 (publication) FLAG or FAIL;
  - G1 PASS; G7 PASS.
- **Capacity:** about $1–5M. Binance is not available to US persons.
- **Validation:** its pass probability is about 0.10–0.20, because the stress leg effectively needs a base Sharpe of
  about 1.44.

## Status

**Development PASS on the frozen gate (corrected data); statistically WEAKENED; economically capacity-limited;
validation LOCKED.**

- It is **not a survivor**, and nothing is promoted.
- The validation unlock is the user's decision. The auditor recommends not unlocking now. If the family is to be
  closed, the auditor recommends registering a one-shot closure test first.
- The 2023–26 lock (`LOCK_2023_2026.md`) stays in force.
