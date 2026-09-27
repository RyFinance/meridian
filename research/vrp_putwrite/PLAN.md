# Monthly SPY put writing (volatility-insurance premium): pre-registration

Written 2026-09-24, before any return from this design was computed.

Before registration, only these ran:
- cycle-availability QA: 147 of 147 cycles had a valid near-ATM put print on the entry day;
  the median premium is 1.41% of strike; K/S is 0.9955–1.000; holding periods are 24–32 days after
  the Good-Friday fix.

Code frozen with this plan: `research/vrp_putwrite/core.py` and `evaluate.py`.
Tests: `tests/test_vrp_putwrite.py`.

## Novelty against the ledger

- `putwrite` P1–P3 sold **1-day** puts about 1σ out of the money. It failed at net 0.21, with a
  premium of about 1.5 bp per trade.
- This plan tests the **one-month, at-the-money** insurance premium: CBOE PUT-style.
- It is a different premium horizon, with a different buyer: institutional portfolio hedgers
  rolling monthly protection, not intraday or overnight demand.
- VIX-futures carry (`vix_basis`) is a different instrument; it failed in hold-out. The
  structural source here is the same volatility insurance, but priced in SPY options with
  cash-secured exposure.

## Mechanism

- End-users (pension funds, insurers and structured-product desks) buy index puts as insurance
  and pay above expected payout. Dealers and writers are paid for carrying crash risk and inventory.
- The premium should persist because the demand is mandate-driven and crash risk cannot be
  diversified.
- **Direction (fixed).** Selling puts earns more than an exposure-matched long position in SPY.

## Rules (fixed)

- **Cycles.** Enter at the first NYSE session after each monthly expiry. Sell one SPY put expiring
  at the next monthly expiry:
  - monthly expiry is the third Friday;
  - pre-2015 Saturday expiries map to the Friday;
  - in Good-Friday weeks the Thursday expiry is used.
- **Strike.** The highest strike ≤ the raw SPY close on the entry day, within 2%, that printed that
  day.
- **Premium.** The entry-day close print, rejected if below intrinsic value or outside 0.2–10% of K.
  A rejected or missing print means the cycle sits in cash.
- **Payoff.** max(K − S_X, 0), with S_X the raw SPY close on the expiry session.
  - Early exercise is ignored.
  - Dividends are ignored. They affect only the payoff through S_X, which is the actual raw price.
- **Accounting.** Fully collateralised on K. Excess return = (premium − payoff − cost) / K;
  collateral earns T-bills.
- **Costs.** Base 1%, stress 5% of the premium. Monthly ATM SPY put spreads are about 0.5–1% of the
  premium.
- **Data limit.** Premiums are trade prints, not quotes. There is no bid/ask.

## Control, benchmark and null

- **Exposure-matched control (C_HALF):** 0.5 × SPY excess return over the same cycle. An ATM put's
  delta is about −0.5, so writing it is about 0.5 long delta.
- Also reported:
  - CAPM regression on SPY excess, giving β and α with Newey-West t;
  - SPY itself;
  - the insurance premium per cycle, (premium − payoff)/K, with its t.
- **Null:**
  - a one-sided circular block bootstrap of the active return (PW − C_HALF), 3-cycle blocks,
    10,000 draws;
  - the deflated-Sharpe probability at 120 project trials.

## Windows

- **Development:** entries 2014-06 → 2019-12.
- **Validation (locked):** entries 2020-01 → 2026-08. It needs `VALIDATION_UNLOCK.md` registered,
  and runs once if selected.

## Gates

**Development.** PW is selected if all of these hold:
- active Sharpe ≥ 1.8/√T (T ≈ 5.6 years, so about 0.76);
- stress active mean > 0;
- CAPM α > 0;
- bootstrap p < 0.05.

**Validation:** active Sharpe ≥ 0.75, stress active mean > 0, α > 0, bootstrap p < 0.05.

## Limits

- 66 development cycles, so power is low.
- Crash exposure: the 2015, 2018 and 2019 drawdowns fall in development, and 2020 in validation.
- The premium is a single-print mid proxy.
