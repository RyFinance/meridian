# Bond-market monetary-policy trend → equity-index selection: pre-registration

Written 2026-09-23, before any equity-index return, signal–return statistic or strategy return was
computed. Before registration, only these ran:
- data pulls: yields in `data/bond_yields/`, with QA; local indices in `data/policy_trend/`,
  checked for gaps and bad ticks only;
- the signal-only coverage check: N eligible per month, z dispersion, rank autocorrelation 0.74.

Code frozen with this plan: `research/policy_trend/core.py` and `evaluate.py`.
Tests: `tests/test_policy_trend.py`, 6 passing.

## Why this is new

- The project used government yields only to **trade constructed bonds**: the multi-asset bond
  carry, momentum and value sleeves, and US curve slope in overlays.
- It has never used bond-market information to choose **other** assets.
- The failed `macro_surprise` study used calendar surprises, not market yields.
- This is not equity momentum. Equity momentum is run as a control (C_MOM), and alpha against it
  is reported.

See `research/LSE_FRONTIER_MAP_2026-09-23.md`.

## Mechanism and direction (fixed)

- **Mechanism.** Changes in short-dated government yields summarise the market's view of the local
  monetary-policy path. Equity markets absorb gradual policy easing or tightening slowly:
  discount-rate and credit-conditions channels, and investors' limited attention to foreign policy
  cycles. This is the monetary-policy component of macro momentum (Brooks 2017, *A Half Century of
  Macro Momentum*, AQR), where falling yields predict equity-index outperformance.
- **Direction.** Economies whose short yields **fell** most over six months, relative to their own
  volatility, outperform those whose yields **rose** most, over the next month. **If this fails,
  the reverse is not tested.**

## Universe (10 economies, fixed by data availability, not by returns)

| Economy | Short yield | Usable from | Local index |
|---|---|---|---|
| US | US2Y | 2012-09-24 | ^GSPC |
| UK | UK2Y | 1991 | ^FTSE |
| Euro area | DE2Y | 2006-03 | ^STOXX50E |
| Japan | JP2Y | 2006-03 | ^N225 |
| Australia | AU2Y | 2006-03 | ^AXJO |
| Canada | CA2Y | 2010-01 | ^GSPTSE |
| Korea | KR2Y | 2010-06-28 | ^KS11 |
| India | IN2Y | 2010-02-27 (after a misprint) | ^NSEI |
| China | CN2Y | 2012-10-08 | 000001.SS |
| Indonesia | ID1Y | 2014-01-01 (noisy before) | ^JKSE |

Brazil, South Africa and Turkey have short tenors only from 2025-07; Mexico has none. All four are
excluded.

## Signal and book P1 (the only candidate)

1. **Signal date.** Each business month-end t. Only yield rows dated **t−1 or earlier** are used.
   Weekend rows are dropped. A yield row must be no more than 10 days old. If the last 10
   observations are identical, the yield is treated as stale and the economy is ineligible.
2. **Δy.** The yield now minus the yield 182 days earlier.
3. **z.** Δy divided by the standard deviation of the last 252 daily yield changes × √126. At least
   200 changes are required.
4. **Book.** N = eligible economies (≥ 6, else no book); k = floor(N/3).
   - **Long** the k lowest z (most easing); **short** the k highest.
   - Within each leg, weights ∝ 1/σ of 63-day local-index log returns. Each leg is 1.0.
5. **Return.** The futures-equivalent excess return of each local index from its last close ≤ t to
   its last close ≤ the next month-end:
   - price return minus the local short yield (at t−1) × days/365;
   - dividends are omitted. They are similar across countries and largely cancel in a long-short
     book; this is a stated approximation.
6. **Costs** (index futures), per side on |Δweight|: base 2 bp, stress 6 bp.

## Controls and nulls

- **C_MOM:** the same construction on each index's 6-month price return, long winners.
- **C_RATE:** long the lowest yield levels.
- The alpha of P1 on both controls is reported.
- **Null 1:** 2,000 within-date permutations of z across eligible economies. This gives p and
  P(pass | null).
- **Null 2:** every circular time-shift of the full z panel by 18 or more months. This keeps signal
  persistence and cross-section but breaks the alignment with returns. It gives p and
  P(pass | null).
  - It uses yield-derived signals from all years as null raw material. No validation-period return
    is computed.

## Windows

- **Development:** signal month-ends 2011-07-29 → 2018-12-31 (90 months; returns to 2019-01-31).
- **Validation (locked):** 2019-01-31 → 2026-08-31.
  - The run refuses to start without `research/policy_trend/VALIDATION_UNLOCK.md` registered.
  - It runs once, only if P1 is selected.

## Gates (protocol amendment 2026-09-23)

**Development.** P1 is selected if all of these hold:
- net base Sharpe ≥ 1.8/√T, where T = 7.5 years, so 0.657;
- stress mean > 0;
- permutation p < 0.05.

**Validation.** P1 passes if all of these hold:
- net base Sharpe ≥ 0.75;
- stress mean > 0;
- block-bootstrap p < 0.05 (3-month blocks);
- permutation p < 0.05.

A pass means a frozen forward test only. A fail is recorded, and no lookback, scaling, universe,
lag or sign is re-specified.

## Known limits

- **Breadth.** Only 6–10 economies, with 2–3 per leg. The Sharpe standard error over 7.5 years is
  about 0.37, so the test has limited power.
- **Instrument.** Local price indices are not the traded instrument. Index futures are, but futures
  roll and basis are not modelled beyond the rate-carry term.
- **Viewed history.** These index price paths were seen in other forms by earlier trials, through
  the ETFs. The yield-based signal was not.
