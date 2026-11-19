# BTC slow-trend → MSTR long/cash regime experiment

## Hypothesis

Unlike the already-rejected intraday and overnight lead-lag ideas, BTC's **slow,
observable end-of-day trend** may identify periods in which holding MSTR from the
next regular-session open has a favorable net payoff.  The position is long
MSTR or cash only; it does not require a BTC short, MSTR borrow, options, or
extended-hours execution.

## Timing and costs

At 16:00 ET on session *t*, calculate whether BTC's 16:00 price is above its
trailing simple moving average.  Enter, exit, or remain flat at MSTR's official
open on session *t+1*.  Daily P&L is the next official-open to official-open
return.  Costs are charged on every entry and exit:

- base: 3 bp auction slippage plus $0.005 per MSTR share per side;
- stress: 6 bp plus $0.010 per share per side;
- cash earns zero, a conservative simplification relative to T-bill interest.

## Anti-overfitting protocol

1. **Development only:** 2020-08-11 through 2022-12-30.  Explore the single
   `BTC > SMA(L)` family for L in 20, 40, 60, 100, 150, and 200 sessions.
2. Choose no more than two adjacent / conceptually similar rules based on
   development performance and stability across 2021 and 2022.  Record them in
   `FROZEN_RULES.md` before running any post-2022 result.
3. **One validation only:** 2023-01-03 through 2026-08-10.  Do not adjust
   lookback, threshold, direction, or costs afterward.  Report base and stress
   results, annual returns, turnover, drawdown, and comparison to buy-and-hold
   MSTR.

Pass language is reserved for a rule with a positive stress-cost validation
return, sensible risk-adjusted results, and no evidence that one isolated year
is carrying the result.  A positive raw return alone is not enough.
