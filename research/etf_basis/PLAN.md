# Bond-ETF liquidity provision (HYG/LQD discount to own iBoxx index): pre-registration

Written 2026-09-24, before any return from this design was computed.

Before registration, only trigger-count QA ran (`reports/etf_basis/qa.json`):
- first valid z: 2012-01-03;
- development trigger days: about 146 for HYG and 133 for LQD;
- basis triggers overlap own-price triggers 23% (HYG) and 15% (LQD).

Code frozen with this plan: `research/etf_basis/core.py` and `evaluate.py`.
Tests: `tests/test_etf_basis.py`.

## Novelty

- No project trial has used bond-ETF price against the underlying index (ETF basis, a form of
  liquidity provision).
- The credit indices were first used in `credit_gate`, as an equity-timing signal that failed.
  This plan uses them as a NAV proxy for their own ETF: a different mechanism and instrument.

## Mechanism

- Bond ETFs let investors exit credit faster than the underlying bonds trade.
- Under selling pressure, HYG and LQD trade below their index value. The authorised participant
  and dealers who absorb the flow demand compensation, because of the cost of holding bond
  inventory and funding.
- A liquidity provider who buys the ETF at an abnormal discount should earn a partial reversal
  of the ETF price.
- **Direction (fixed):** long after a deep discount. Premiums are not traded (shorting is costly).
  The reverse is not tested.

## Rules (fixed)

1. **Pairs.** HYG with USD_LIQ_HY; LQD with USD_LIQ_IG (the iBoxx indices each fund tracks).
2. **Data.** ETF prices are yfinance adjusted closes (official session). Index values are LSE
   `credit_indices`, with weekend rows dropped.
3. **Basis and z.**
   - b = log(ETF) − log(index).
   - d = b − mean of the previous 250 observations.
   - z = d / standard deviation of d over the previous 250 observations.
4. **Trigger and position.** z ≤ −2 on day t means long the ETF at the close of t+1 for 5 sessions.
   Overlaps extend the hold; the position is at most 1.
   - The index is stale by about a day, and the one-day execution lag makes this conservative.
5. **Book.** B = the equal-weight average of the HYG and LQD sleeves. Excess return over T-bills.
6. **Costs.** Base 3 bp, stress 10 bp per side on |Δposition|.

## Controls and null

- **C_EXP:** a constant position in each ETF equal to B's average position; the exposure-matched
  control. The gate uses the active return B − C_EXP.
- **C_REV:** the same rule triggered by the ETF's own 5-session return z ≤ −2. This checks whether
  the basis beats plain own-price reversal.
- **Null:** 500 random circular shifts, each of 60 or more sessions, of each ETF's basis-z series.
  Clustering is kept and alignment is broken. Each shifted book is measured against its own
  exposure-matched control. This gives p, the 95th/99th percentiles and P(pass | null).

## Windows

- **Development:** 2010-01-04 → 2017-12-29 (effective from 2012-01-03).
- **Validation (locked):** 2018-01-02 → 2026-09-10. It needs `VALIDATION_UNLOCK.md` registered,
  and runs once if selected.

## Gates

**Development.** B is selected if all of these hold:
- active Sharpe ≥ 1.8/√T (T ≈ 6 years, so about 0.73);
- stress active mean > 0;
- the mean of (B − C_REV) is > 0;
- the shift-null p is < 0.05.

**Validation:** active Sharpe ≥ 0.75, stress active mean > 0, B − C_REV > 0, shift p < 0.05.

## Limits

- The index is only a NAV proxy: iBoxx index, not the fund's own NAV. Expense drift is removed by
  the rolling mean.
- The big stress episodes (2020, 2022) fall in validation. Development has 2015–16 energy credit
  stress.
- There are only two ETFs.
