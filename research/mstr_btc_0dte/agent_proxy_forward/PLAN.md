# P1 source-transition forward audit (registered before tail outcomes)

## Fixed rule

Use the already frozen P1 rule from `../agent_proxy/frozen_rules.json`, without
any change:

1. At 09:29 ET, calculate BTC off-hours return from the completed 15:59 ET
   minute of the preceding MSTR session to the completed 09:28 ET minute today.
2. If it is at least +2.0%, buy MSTR at its official regular-session open and
   sell at that session's official close; otherwise remain in cash.
3. Charge $0.005/share and 3 bp on each auction side.  No short, leverage,
   after-hours fill, or parameter variation is allowed.

## Why this is only an audit, not a replacement validation

The original BTC minute source ends before the 2026-08-11 US pre-open.  A local
Binance BTCUSDT perpetual minute archive spans February--September 2026.  The
post-2026-08-10 period is chronologically untouched by the original P1 test,
but it uses a different BTC price source.  Therefore this test is a
**source-transition forward audit**, not a clean continuation of the primary
validation or evidence for changing the rule.

Before looking at post-2026-08-10 MSTR outcomes, the script must calculate the
same signal from both sources on their August overlap and record per-session
threshold agreement.  If signal agreement is poor, the tail result can only be
reported as an inconclusive source-sensitivity observation.

## Locked forward sample and report rules

- First eligible entry date strictly after 2026-08-10.
- Last date is the last MSTR session with a complete 09:28 ET Binance signal no
  later than 2026-09-30, the final local Binance archive month.
- Report every eligible session, active trades, net compound, mean/t-stat,
  max drawdown, and source-overlap agreement.  Do not tune the threshold,
  time convention, or execution rule based on the result.
