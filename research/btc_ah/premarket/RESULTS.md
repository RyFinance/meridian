# BTC -> MSTR pre-market / after-hours gap test (premarket/)

Verdict: **NONE**. No pre-market or after-hours gap rule is positive net of costs in its signal direction. Extended-hours data covers only 61 sessions (2026-04-29..2026-08-10), so there is no dev half for these tests.

## Data finding (read first)
- The brief says `stock_1m_dev` (2020-08..2023-12) is extended-hours. It is **regular session only** (13:30/14:30 UTC to 19:59/20:59 UTC, 09:30-15:59 ET, 102-390 bars/day). No bar before 09:30 ET or after 16:00 ET exists in any of the 827 files.
- The LSE terminal `get_history` returns the same RTH-only bars for 2021-11-23 (probe), so 2020-2023 extended hours are not available from either source.
- `mstr_stock_1m_lse.parquet` does have 04:00-20:00 ET bars (61 days, 2026-04-29..2026-08-10, filtered to <= 2026-08-10). Volume peaks at 09:29/09:30 and 15:59 ET after UTC->ET conversion, so the timestamps are UTC.
- BTC was cut at 2026-08-10 ET (the raw file runs to 2026-08-11 08:03 UTC; that tail was dropped).

## Method (script: premarket_backtest.py)
- P0: MSTR and BTC close of the bar labelled 15:59 ET on the prior session (after-hours: same day). Decision at T uses the last volume>0 MSTR print within 30 min before T (stale otherwise) and BTC at T-1min.
- gap = beta*BTC_ret - MSTR_ret. Enter if |gap| > thr, in sign(gap) direction. Entry bar T needs volume>0. Long fills at high*(1+15bp); short at low*(1-15bp).
- Exit: 09:30/09:35/09:45/10:00 bar open, 3 bp adverse (RTH). After-hours exit at next-day 08:00 open uses 15 bp; 09:30 uses 3 bp.
- beta_dev = 0.811 (through-origin OLS, RTH overnight: MSTR 15:59->09:30 open on BTC 15:59->09:29, dev days <= 2022-06-30, n=447, corr 0.87). beta_1 = 1.0. Check-era RTH beta (2022-07..2023-12) = 0.98, so the gap construction is stable.
- Flip control: same entry/exit mechanics, opposite direction.

## Counts
- Pre-market: 5 decision times x 2 betas x 4 thresholds x 4 exits = 160 possible cells; 152 non-empty across both windows (60 with n>=5). 664 pre-market trade rows across 15 unique days.
- After-hours: 3 times x 2 betas x 4 thresholds x 2 exits = 48 possible cells; 32 trade rows across 6 days.
- Skips (pre): 129 stale (no print in 30 min), 8 no entry volume, 19 no prior close. AH: 77 stale, 16 no entry.

## Results (net of costs; signal direction)
| Rule (decide, beta, thr, exit) | n | win | mean bp | t | avg win bp | avg loss bp | flip mean bp | flip t |
|---|---|---|---|---|---|---|---|---|
| PRIMARY pre 09:25, beta_dev, 0.5%, exit 09:30 | 12 | 17% | -38.0 | -3.00 | +31.8 | -52.0 | -45.2 | -2.94 |
| pre 08:00, beta_dev, 0.5%, exit 09:30 | 10 | 40% | -34.5 | -0.83 | +89.5 | -117.2 | -8.8 | -0.21 |
| pre 09:00, beta_1, 1.0%, exit 09:35 (best mean, n>=5) | 5 | 40% | +2.2 | 0.04 | +120.2 | -76.4 | -58.8 | -1.31 |
| AH 17:30, beta_dev, 0.5%, exit next 08:00 | 3 | 67% | +71.9 | 0.56 | +171.2 | -126.7 | -133.2 | -1.07 |

Across the 60 cells with n>=5: 1 has positive mean, 0 have t > 2, and 11 have t < -2 in the signal direction. The flip mean is positive in 30 of those 60, so the flip is not reliably worse than the signal.

Pooled over all trade rows, the signal averages -81 bp (pre-market) and +12 bp (after-hours, 6 days). The flip averages +19 bp and -65 bp. Mean of signal and flip, which approximates the cost-only level, is -31 bp (pre) and -27 bp (AH). Both directions lose about the same, so the loss is mostly cost, not direction.

## Verdict and caveats
- The primary rule is negative and significant at t = -3.0 in the signal direction, with the flip also negative. That is a cost and noise story, not a tradable edge.
- Pooled flip-positive results come from overlapping cells on 15 days. They were not pre-registered, so I do not count them as a reversal edge.
- No dev/check split is possible for extended hours. All results are check-only (2026, 61 days, n=3 to 12 per primary cell), so no parameter was picked on dev.
- Costs are as the brief specifies: 15 bp entry worst-fill plus 15 bp exit at 08:00 pre, and 3 bp at the 09:30 open. The cost of crossing the wide pre-market spread (a bid-ask of about 30 bp round trip plus worst-fill slippage) is larger than the gap in most rules.
- To test a dev half, the extended-hours data for 2020-2023 would need to come from a source other than stock_1m_dev or the LSE get_history endpoint I probed.
