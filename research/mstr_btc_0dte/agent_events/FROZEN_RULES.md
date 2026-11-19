# Frozen purchase-announcement rules

These rules were written before reading any 2023+ event returns.  The
development period is 2020-01-01 through 2022-12-31; the single holdout starts
2023-01-01.

## Signal universe

An event is a positive BTC purchase disclosed in MicroStrategy/Strategy's
official SEC 8-K text.  The source timestamp is EDGAR `acceptanceDateTime`,
not a third-party timestamp or an assumed press-release time.  Filings that
state that no BTC was purchased, a financing-only filing, and a duplicate
historical restatement are excluded.

## Entry convention

The entry is the MSTR regular-hours **close** on the filing date when EDGAR
accepted the filing before 16:00 America/New_York; otherwise it is the next
available MSTR regular-hours close.  A market-on-close order could be submitted
after the public filing and before that close.  This intentionally does not
claim an intraday fill or use a pre-market press-release time.

If two entries would occur on the same close, they are one combined signal. If
the strategy is already long from an earlier event, it does not add leverage;
the exit is extended to the later of the scheduled exits.

## Rules tested once on the holdout

1. **P1:** long MSTR from that entry close to the next trading-session close.
2. **P5:** long MSTR from that entry close to the fifth subsequent
   trading-session close.

Costs are applied at both fills: 3 bp adverse execution each side plus
$0.005/share each side.  No short positions, borrow assumptions, or
unmodelled intraday execution are used.

BTC's prior five-calendar-day return at the entry close is reported as a
descriptive regime split, not promoted to a third trading rule.
