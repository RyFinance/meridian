# Freeze record — written before sealed outcomes

`FROZEN_RULES.json` was registered at 2026-10-17T07:43:44Z.  Its canonical
rule payload SHA-256 is:

`1e3bf4ae5093c144fb5fc70d7c81d5773582fc862a9373407bc12eeefeac7486`

The development screen considered seven small, predeclared gross-premium
momentum variants through 2022-12-30 only.  Two hypotheses are sealed:

1. **MNL1_FAST_MOM05**: long MSTR when five-session gross BTC-mNAV momentum is
   positive; otherwise cash.
2. **MNL2_MOM10_LEVEL50**: long only when ten-session gross BTC-mNAV momentum
   is positive and the proxy exceeds its 50-session moving average; otherwise
   cash.

Both execute at the following MSTR regular open and retain the protocol's
120-session share-anchor age limit.  They were selected because their net
development results survived the doubled-cost check and were positive in the
specified development subperiods, **not** because development established
alpha.  In fact, neither had a positive robust daily-return differential
versus the matched MSTR price-trend benchmark.  This is a material selection
caveat that will remain in the final report regardless of the sealed result.

No 2023+ strategy-performance output from this workstream was opened before
this file was written.  The next performance computation is one invocation of
the frozen validation runner.
