# Month-end FX hedge-rebalancing flow (Melvin & Prins 2015): pre-registration

Status: DRAFT until registered. Written 2026-09-23 before any return of this design was computed.

## Novelty and mechanism

- **Mechanism.** Global investors hold foreign equities with currency hedges that are reset at the
  month-end London 4 pm WM/R fix.
  - If US equities outperform a foreign market during the month, foreign holders of US equities
    are under-hedged. They must **sell USD** forward at the month-end fix, and US holders of the
    foreign market must buy less.
  - This is a forced, predictable, price-insensitive flow.
  - Melvin & Prins (2015, *Journal of Financial Markets*) document that FX moves into the
    month-end fix in the direction implied by relative equity performance.
- **Who pays:** hedgers who must trade at the fix regardless of price.
- **Why it persists:** benchmarked hedging mandates.
- **Prior use:** the spent `fx_session` study tested UNCONDITIONAL hourly session and fix-reversal
  rules. The equity-conditional month-end hedge flow has never been tested. `fx_news` used macro
  releases. This test is distinct.
- **Direction (fixed):** if the US index outperformed the foreign index month-to-date, go long the
  foreign currency against USD into the fix; otherwise go long USD. Never reversed.

## Data

- **FX:** `data/fx_1m/` (LSE 1-minute, quote-derived, UTC, bar-start; QA in
  `research/fx_news/PLAN.md`).
- **Pairs and foreign indices:**

  | Pair | Foreign index |
  |---|---|
  | EUR/USD | ^STOXX50E |
  | GBP/USD | ^FTSE |
  | AUD/USD | ^AXJO |
  | USD/JPY | ^N225 |
  | USD/CAD | ^GSPTSE |

  CHF is excluded: no Swiss index is on disk.
- **US index:** ^GSPC. Local price indices come from `data/policy_trend/{US,EZ,UK,AU,JP,CA}.parquet`.

## Rules

- **Month-end day D** = the last weekday of each calendar month (a proxy for the WM/R month-end
  fixing day).
- **Signal**, computed from index closes dated **strictly before D**:
  - rel_i = (US index MTD return) − (foreign index i MTD return), each measured from the last close
    of the prior month to the last close before D, in local terms.
  - The currency position is sign(rel_i): long the foreign currency if US outperformed.
  - If either index has no close in the month before D, there is no trade.
- **Window:** enter at 08:00 Europe/London on D (the 1-minute close at the bar ending 08:00 London);
  exit at 16:00 Europe/London on D, at the fix. London time is converted to UTC with DST.
  - Prices come from `research.fx_news.evaluate.price_at` semantics, with a 5-minute look-back.
- **Return per pair:** position × (foreign currency return vs USD), oriented as in
  `research/fx_news/events.py` PAIRS.
- **Book:** the equal-weight average over available pairs. Daily P&L is booked on D; other days
  are 0.
- **Costs:** 1 bp (base) or 3 bp (stress) per side per unit notional; 2 sides per event.

## Controls and null

- **C_USDSHORT:** always long the foreign currency in the same windows. This tests for a generic
  month-end USD pattern.
- **C_SIGN:** within-pair permutation of the trade signs across month-ends, 2,000 draws, seed
  20260923. Timing is kept and only the equity-flow information is destroyed. This gives the gating
  p-value and P(pass | null).
- **Reported:**
  - hit rate, mean bp per event and per pair;
  - year-by-year results;
  - quarter-end vs other months;
  - |rel| tercile dose-response, descriptive.

## Windows

- **Development:** month-ends 2015-01 → 2020-12 (72).
- **Validation (locked):** 2021-01 → 2026-08.

## Gates

**Development.** Selected if all of these hold:
- net base Sharpe of the daily book series ≥ 1.8/√T (T = 6 years, so 0.735);
- stress mean > 0;
- permutation p < 0.05.

**Validation:** net Sharpe ≥ 0.75, stress mean > 0, permutation p < 0.05.

## Limits

- Only 72 development events per pair.
- The WM/R fix day is proxied by the last weekday; UK holidays are not modelled.
- Hedge-ratio conventions vary across investors.
- The effect may have moved earlier in the day since 2015 (post-2015 fix reforms widened the fix
  window to 5 minutes).
