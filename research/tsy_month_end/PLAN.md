# Treasury month-end index-extension flow: pre-registration

Written 2026-09-24, before any return from this design was computed. Before registration, only the
TLT/IEF data layouts were checked (yfinance official closes, 2003-01 → 2026-09, no gaps).

Code frozen with this plan: `research/tsy_month_end/core.py` and `evaluate.py`.
Tests: `tests/test_tsy_month_end.py`.

## Novelty

- Month-end work in the ledger has covered only:
  - 60/40 SPY-vs-IEF rebalancing drift (R1–R3, failed validation);
  - SPY turn-of-month (multi-asset, round 2).
- The Treasury index-extension flow has not been tested in this project.

## Mechanism (forced flow)

- Bloomberg/ICE Treasury indices rebalance at month-end: new issues enter and maturing bonds leave,
  so index duration steps up.
- Index-tracking and benchmarked bond managers must extend duration into the close of the last
  session. That forced, calendar-known demand for long bonds pushes long Treasuries up in the final
  days.
- The liquidity provider who holds duration into the rebalance is paid for it.
- **Direction (fixed):** long long-duration Treasuries over the last 3 sessions of the month. The
  reverse is never tested.

## Rules (fixed)

- **Book M:** TLT (20+ year Treasuries), adjusted closes.
  - Weight 1 is held at the closes of the 4th-, 3rd- and 2nd-to-last sessions of each month, so it
    earns the last 3 sessions' returns. Otherwise T-bills (prior IRX).
- **Costs:** base 2 bp, stress 6 bp per side on |Δweight|; 24 trades a year.

## Control and nulls

- **C_EXP:** a constant TLT weight equal to M's average weight (about 3/21). The gate uses the active
  return M − C_EXP.
- **Gating null:** 1,000 random circular shifts, each of 5 or more sessions, of M's holding calendar.
  This breaks month alignment while keeping frequency and exposure. It gives p, the 95th/99th
  percentiles and P(pass | null).
- **Descriptive only:** the same 3-session hold ending at sessions k = 3 … 15 of each month
  (window-position placebo), and IEF under the same rule.

## Windows

- **Development:** 2003-01-02 → 2014-12-31 (12 years).
- **Validation (locked):** 2015-01-02 → 2026-08-31. It needs `VALIDATION_UNLOCK.md` registered,
  and runs once if selected.

## Gates

**Development.** M is selected if all of these hold:
- active Sharpe ≥ 1.8/√T (T ≈ 12 years, so about 0.52);
- stress active mean > 0;
- shift-null p < 0.05.

**Validation:** active Sharpe ≥ 0.75, stress active mean > 0, shift p < 0.05, block-bootstrap
p < 0.05.

## Limits

- TLT is only a proxy for the long end.
- The index-extension size varies by month (quarter-ends are larger); this is not modelled.
- The effect is published and practitioner-known, so it may be arbitraged. That is exactly what
  development tests.
