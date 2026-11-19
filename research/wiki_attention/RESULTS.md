# Wikipedia attention edge: RESULTS

**Verdict: NONE.** No spec shows a sign-stable, cost-surviving edge. Dev and check disagree in sign for the main H1 spec, and H2 and H3 are not significant in check.

## Data and rules
- Universe: 136 large-cap US names with both series (144 mapped; MMC has no yfinance history, others lacked coverage). Titles hand-mapped (UPS to "United Parcel Service", SLB to "SLB").
- Attention: en.wikipedia daily "user" views, 2019-01-01 to 2026-10-16 (Wikimedia REST API).
- Prices: yfinance auto-adjusted OHLC. Signal dated d (views complete after UTC midnight d+1) enters at the open of the first trading day after d; holds are open-to-open.
- Dev 2019-2022, check 2023-2026-10-16. Costs 5 bp per side.
- Spike z = (log views_t - median of prior 60 days) / std of prior 60 days (std floored at 0.05).

## Results (net of costs; t = HAC Newey-West)
| Spec | Dev bp (t) | Check bp (t) | Flip check bp (t) |
|---|---|---|---|
| H1 z>3, reversal, h=1 | -4.7 (-0.73) | +2.1 (+0.33) | -22.1 (-3.44) |
| H1 z>3, reversal, h=5 (primary) | -35.0 (-2.47) | +12.0 (+0.95) | -32.0 (-2.54) |
| H1 z>3, reversal, h=10 | -42.9 (-2.54) | +12.3 (+0.68) | -32.3 (-1.78) |
| H1 z>2.5, reversal, h=5 | -26.7 (-2.30) | +3.2 (+0.29) | -23.2 (-2.14) |
| H2 weekly 1w vs 4w, long low / short high | -27.9 (-3.17) | -14.1 (-1.29) | -8.8 (-0.80) |
| H2 weekly 2w vs 8w, long low / short high | -20.6 (-2.08) | -7.8 (-0.85) | -6.5 (-0.71) |
| H3 SPY next week, beta on Mz (bp per SD) | +18.2 (t 1.54) | -4.6 (t -0.42) | n/a |
| H3 long SPY if Mz>0 | +20.3 (+1.25) | -5.4 (-0.35) | flip -0.5 (-0.03) |

Flip column: for H1 the flip is the continuation strategy; for H2 it is long high / short low; for H3 it is short when Mz>0.

Per-year net bp, primary H1 reversal h=5: 2019 -17, 2020 -44, 2021 -32, 2022 -48, 2023 -18, 2024 +44, 2025 -7, 2026 +34.
Per-year net bp, H2 1w long low: 2019 -12, 2020 -33, 2021 -46, 2022 -19, 2023 -23, 2024 +10, 2025 -21, 2026 -25.

Placebo (H1 z>3 h=5, attention circularly shifted per name, 20 draws): median reversal net -12.3 bp, 95th percentile -1.9 bp. The real dev figure (-35 bp) is below the placebo median, so it does not isolate a reversal effect.

Event counts: H1 about 2,500 (z>3) and 3,600 (z>2.5), 10-day spacing per name. H2 about 400 weeks. H3 392 weeks.

## Interpretation
- H1 (spike reversal): the dev-period reversal does not replicate in check (sign flips to +12 bp). Check-period continuation is -32 bp (t -2.5), which is also not stable across the full sample. Neither direction survives costs with a consistent sign.
- H2 (weekly attention-change sort): the long-low-attention leg loses in both periods, but check t is -1.3 at 1w and the flip is insignificant. Weekly turnover of about 2.3 units costs roughly 11 bp per week, which dominates the gross spread.
- H3 (aggregate attention to SPY): dev beta is weakly positive (t 1.5) and check is zero. No stable market-timing signal.

## Multiple testing
10 primary specs (6 H1, 2 H2, 2 H3) plus 1 placebo. No spec clears |t| > 2.5 in check in the dev-favored direction. Bonferroni over 10 would need roughly |t| > 3.3.

## Caveats
- Survivorship: universe is today's large caps, which biases cross-sectional sorts and reversal tests.
- Attention spikes coincide with earnings and news; there is no event control, so H1 may just measure event drift.
- H1 t-stats treat events as independent, ordered by date with lag = h. Same-day clustering across names is not modeled, so SEs may be understated.
- Shorting costs, borrow fees and capacity are ignored. 5 bp per side is an assumption.
- Pageviews reflect en.wikipedia only and can be driven by bots or Google traffic changes despite the "user" filter.

## Files
- research/wiki_attention/universe.py (ticker to title map)
- research/wiki_attention/fetch.py (pageviews and prices cache; 429 retry)
- research/wiki_attention/analysis.py (all tests)
- research/wiki_attention/results.json, h1_events_z3_h5.csv
- research/wiki_attention/cache/ (raw pageviews and prices)
