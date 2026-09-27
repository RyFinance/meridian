# Credit-conditions gate for equity exposure: pre-registration

Written 2026-09-23, before any strategy or signal–return statistic was computed.

Before registration, only these ran:
- the credit-index pull (`data/credit_indices/`, 19 iBoxx series, manifest);
- semantics QA against HYG/LQD (total-return levels; date-aligned; the index lags the ETF by about
  a day on stale pricing);
- gap QA (no gaps over 5 days; 16 weekend rows, which are dropped).

Code frozen with this plan: `research/credit_gate/core.py` and `evaluate.py`.
Tests: `tests/test_credit_gate.py`.

## Novelty

- The iBoxx credit indices have never been used.
- The only prior credit input was one feature (the LQD/IEF 63-day change) among many in the
  return-search stock-picking ML models, which failed.
- No standalone test of credit conditions predicting another asset exists in
  `preregistrations.jsonl`.

## Mechanism and direction (fixed)

- **Mechanism.** Credit investors are senior, institutional and focused on default risk. A fall
  in high-yield bonds' excess return over short investment-grade bonds signals deteriorating
  credit conditions, and precedes weaker equity risk appetite.
- **Direction.** Credit excess return (CE) > 0 over the last 63 index observations means hold
  equities; ≤ 0 means hold T-bills. The reverse is never tested.

## Signal and book G (the only candidate)

- **Signal.** CE = log(USD_LIQ_HY / USD_CORP_1_3) now minus 63 index observations earlier, using
  only values dated t−1 or earlier, where t is each month-end NYSE session.
  - USD_CORP_1_3 is short-duration IG. It removes most rate exposure while keeping credit risk.
- **Book G.** If CE > 0, SPY at 100%; otherwise T-bills (prior IRX). Missing CE means T-bills.
  - The weight changes at the close of t+1 and earns from the next session.
  - Returns are yfinance adjusted SPY with daily marking.
- **Costs.** Base 2 bp, stress 6 bp per side on the traded weight.

## Controls and null

- **C_EXP:** a constant SPY weight equal to G's average weight over the window. This is the
  exposure-matched benchmark required by the protocol amendment.
- **C_TREND:** SPY's own 63-session return to t−1 > 0 means SPY, else T-bills, on the same
  schedule. This separates credit information from equity momentum.
- **Shift null:** every circular shift, of 12 or more months, of the monthly CE series over
  2010–2026. Only CE values are reused; only development returns are computed. Each shifted
  signal is evaluated against its own exposure-matched control. This gives p and P(pass | null).

## Windows

- **Development:** month-ends 2010-04-30 → 2017-12-29.
- **Validation (locked):** 2018-01-31 → 2026-08-31.
  - It needs `VALIDATION_UNLOCK.md` registered, and runs once if G is selected.

## Gates

**Development.** G is selected if all of these hold:
- the Sharpe of the active daily return (G − C_EXP) is ≥ 1.8/√T (T ≈ 7.7 years, so about 0.65);
- the stress active mean is > 0;
- the mean of (G − C_TREND) is > 0;
- the shift-null p is < 0.05.

**Validation:** active Sharpe ≥ 0.75, stress active mean > 0, block-bootstrap p < 0.05, and
G − C_TREND mean > 0. A pass means a forward test only.

## Known limits

- **Few independent switches:** a single time series of monthly decisions, so power is low.
- **Index lag.** The index lags ETF prices by about a day. The t−1 cut-off and t+1 execution make
  this conservative, not leaky.
- **Viewed history.** SPY 2010–2017 history has been viewed in many earlier trials, with other
  signals.
