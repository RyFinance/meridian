# Options-Implied Stock Signals — Development Summary

## What was tested

Options-implied stock signals on a new dataset. Registered 2026-09-18 in `research/preregistrations.jsonl` (plus amendments 1–5), written before any option-derived statistic was computed.

Four cross-sectional weekly candidates on daily OPRA trade prints (LSE vault, 2014-06 onward; trade prices, not quotes, so each signal is averaged over 5 trading days):

- **H1_os** — option-to-stock volume ratio (Johnson & So 2012). High O/S → lower returns; long lowest quintile, short highest.
- **H2_ivspread** — call-minus-put IV spread (Cremers & Weinbaum 2010). High spread → higher returns; long highest, short lowest.
- **H3_skew** — put skew (Xing, Zhang & Zhao 2010). High skew → lower returns; long lowest, short highest.
- **H4_composite** — fixed equal-weight blend of percentile ranks of −O/S, +IV spread, −skew.

Universe: 100 S&P 500 names with options history from 2014-06-30 or earlier, ranked by mean dollar volume over 2014-01..2014-06. Signal date = last trading day of each calendar week; entry at the next session's open; hold to the open after the next signal date (~1 week). Equal weight, 20 names per leg, base costs 5 bps/side + 0.5%/yr borrow.

## Development window

Signal dates **2014-07-01 → 2019-12-31** (287 active weeks). Development gate: net base excess Sharpe ≥ 0.5 on weekly returns (√52 annualized). If no candidate passes, the experiment stops with a null result and validation is not run.

## Results (net, base)

| Candidate | Base Sharpe | Stressed Sharpe |
|-----------|------------:|----------------:|
| H1_os      | −0.37 | −1.55 |
| H2_ivspread | −0.91 | −2.83 |
| H3_skew   | −0.94 | −2.66 |
| H4_composite | −1.08 | −2.90 |

## Pass / fail

**All four failed.** None reached the ≥ 0.5 development gate; `selected: []`.

## Main conclusion

A registered null result. Every registered options-implied signal — including the composite — delivered negative net excess Sharpe in development (annual mean −3.0% to −9.4%, max drawdown −25% to −50% base; stress costs nearly quadruple the drag). Under the protocol, validation (2020-01-01 → 2026-09-17) is not run and the experiment stops. Options prices in 100 mega caps post-2014, with trade prints rather than quotes, do not translate into a tradable cross-sectional signal — consistent with the stated prior of a net Sharpe of 0 to 0.8 at best, and no threshold, window, universe, or cost figure may be changed without a new registration.
