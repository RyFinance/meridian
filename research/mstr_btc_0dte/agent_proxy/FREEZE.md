# Frozen candidates before validation

Freeze timestamp: 2026-10-16 (local research session).  No 2023+ proxy outcome
data were read in selecting these rules.  The exact candidate definitions are in
`frozen_rules.json`; its SHA-256 is recorded by the validation program.

Development was restricted to dates through 2022-12-30.  The exploratory grid
considered 0.0%, 0.5%, 1.0%, 1.5%, 2.0%, 2.5%, 3.0%, 4.0%, and 5.0% positive BTC
off-hours thresholds for the individual names and simple equal-weight baskets.
That breadth creates selection risk.  It is the reason that the following
out-of-sample decision gate is intentionally demanding rather than treating a
positive headline compound return as evidence.

A candidate is called a *credible positive net edge* only if its single
2023-to-last-available-BTC validation shows all of the following:

1. Positive baseline net compound return after the stated costs;
2. Annualized daily-return Sharpe of at least 0.50;
3. At least 75 position-days, and maximum drawdown no worse than -50%;
4. Positive net compound return at the baseline threshold after a +3 bp/side
   cost shock (6 bp/side auction friction plus the $0.005/share fee); and
5. Both adjacent fixed threshold checks (1.5% and 2.5%) have positive baseline
   net compound returns.  Annual and fixed calendar subperiod splits are
   reported as diagnostic evidence; a single good year cannot overturn a failed
   gate above.

All candidates are long-only.  The signal is available before the opening
auction, and no observed opening price is used to choose a trade.  Thus the test
measures whether a BTC proxy continues to drift after an already-known BTC
off-hours move; it does not falsely assume that an opening-auction fill can be
conditioned on that auction's realized price.
