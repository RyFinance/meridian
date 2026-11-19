# Friday BTC trend → Monday MSTR-open test — rejected in development

This test asks a tradeable pre-weekend question rather than re-running the
rejected intraday lead-lag idea.  At Friday 16:00 ET, BTC's 5-, 10-, or
20-session return is known.  If positive, the rule buys MSTR in the official
Friday closing auction and exits at the next official MSTR open.  The intended
mechanism is conditional BTC weekend continuation being priced into MSTR's
Monday opening auction.

The pre-registered 2020-08-11 through 2022-12-30 development results were:

| BTC lookback | Cost case | Trades | Mean net / trade | Trade t-stat | Compounded return | 2021 | 2022 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | base | 53 | +31.9 bp | 0.51 | +12.4% | +22.0% | -7.9% |
| 5 | 2x stress | 53 | +23.3 bp | 0.37 | +7.3% | +19.7% | -9.7% |
| 10 | base | 48 | +72.3 bp | 1.11 | +34.8% | +15.7% | -0.6% |
| 10 | 2x stress | 48 | +63.6 bp | 0.97 | +29.3% | +13.7% | -2.1% |
| 20 | base | 51 | -19.8 bp | -0.25 | -17.0% | +12.6% | -37.0% |
| 20 | 2x stress | 51 | -28.2 bp | -0.36 | -20.6% | +10.3% | -38.1% |

Costs include 3 bp auction slippage and $0.005 per share at each side; the
stress case doubles both.  Cash earns zero.  Neither positive rule has a
convincing t-statistic or stable 2022 performance, while the adjacent 20-day
rule is negative.  The family fails its protocol's neighboring-cluster and
multi-year-stability requirements, so **no post-2022 validation was run**.

This is an honest development rejection, not a candidate strategy.
