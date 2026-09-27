# Credit-conditions gate for equity exposure: development FAIL, validation not run

Run 2026-09-23. Plan: `research/credit_gate/PLAN.md`, registered at 22:07:40 with code hashes,
before any return. Code: `research/credit_gate/`. Tests: `tests/test_credit_gate.py` (4 pass).
Output: `dev_results.json`, `dev_daily_base.csv`, `dev_signals.csv`. The ledger grows by 1 trial.

## Data

- **Source:** LSE vault `credit_indices`, iBoxx **total-return levels, not spreads**. Pulled in full
  history (2010-01-04 → 2026-09-11) into `data/credit_indices/`: USD_LIQ_HY, USD_LIQ_IG, USD_CORP,
  USD_CORP_{AAA,AA,A,BBB}, USD_CORP_1_3, USD_CORP_BBB_{1_3,7_10}, USD_CORP_A_7_10, EUR_LIQ_HY,
  EUR_LIQ_CORP, EUR_CORP{,_BBB,_AAA}, GBP_CORP{,_BBB,_AAA}. The manifest has sha256 hashes.
- **Verification:**
  - they track HYG and LQD at the ETF return plus the expense ratio;
  - they are date-aligned, but the index lags the ETF by about a day on stale bond pricing;
  - no gaps over 5 days;
  - 16 stray weekend rows, which are dropped.

## Result (month-end decisions 2010-04 → 2017-12, 93 months; daily marked)

| Book | Net excess Sharpe (2 bp) | CAGR | Max DD |
|---|---:|---:|---:|
| **G: SPY if 63-day HY-over-short-IG excess > 0, else T-bills** | 0.91 | 10.5% | −16.7% |
| C_EXP: constant 76% SPY (G's average exposure) | 0.96 | 10.9% | −14.3% |
| C_TREND: SPY's own 63-day trend gate | 0.71 | 8.0% | −20.9% |
| SPY buy-and-hold | 0.96 | 14.1% | −18.6% |

**Gate.** The active return G − C_EXP must have a Sharpe ≥ 0.65. It has **−0.04** (−0.29%/yr;
stress −0.38%/yr; bootstrap p 0.58): **FAIL**.
- G beats C_TREND by +2.3%/yr, but not significantly (p 0.20).
- Shift null: p 0.45, null mean −0.07 ± 0.29; P(pass | null) = 0% over 72 shifts.
- G is not selected, and validation (2018–2026) stays locked.

Active return by year: −5.0%, +2.7%, −3.3%, +1.3%, −1.3%, −2.9%, +0.5%, +4.5%, +1.3%
(2010 → 2018-01).

**Deviation, recorded:**
- The plan said the shift null would use CE over 2010–2026.
- The code loaded SPY only up to the end of the development window, so the null used only
  2010-04 → 2018-01 month-ends: 72 circular shifts within the development window.
- This is more conservative about leakage, and it does not change the conclusion.

## Reading

- **Credit conditions add nothing beyond holding the same average equity exposure.**
- The gate beats SPY's own trend gate, but mainly by being invested more often (76% vs 80%, with
  different months). The two agree in 80% of months.
- It lowers volatility in proportion to lower exposure. It does not improve timing.
- At a monthly horizon, US high-yield credit carries no equity-timing information that the equity
  market does not already have. This is consistent with the literature finding that equity leads
  credit.

## Classification

Credit-conditions → equity timing (monthly, HY-vs-short-IG) is **SPENT**. Do not re-specify the
lookback, the pair, the threshold or the sign. The credit indices remain available.

Untested uses of the same data:
- the rating/maturity term structure as a cross-sectional signal for sector or quality equity books;
- EUR/GBP credit for European equities;
- credit as the traded asset.

Priors for all three are low given this null.
