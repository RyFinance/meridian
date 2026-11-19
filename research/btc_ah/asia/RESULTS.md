# Asia BTC-linked stocks vs BTC (agent: asia), data to 2026-08-10 only

**Verdict: WEAK.** One HK name (0434.HK, Boyaa) shows a residual-gap fade that survives its own check period, but it does not replicate in the sister name 1723.HK. Japanese BTC names show no net edge after 20 bp round-trip costs.
## Universe (yfinance)
- Available: 3350.T Metaplanet, 3825.T Remixpoint, 8698.T Monex, 8473.T SBI, 9449.T GMO Internet, 0434.HK Boyaa, 1723.HK Moon Inc.
- Not on yfinance: DigiAsia (DIGIASIA.JK), 3654.T, 3356.T. Dropped.
- Era start: 3350 = 2024-04-01 (brief). 3825 = 2024-01-01 (my unverified proxy). Others = 2017-08-11 (crypto-business proxy, not treasuries).
- Dev/check cut = 60% of era: 3350 2025-08-30, 3825 2025-07-25, others 2023-01-03.
- 60m returned ~2.8 years (from 2023-10), not 730 days. For the five 2017-era names this is after the dev cut, so intraday results are check-only.
## Method (short)
- BTC: 1m close, filtered to <= 2026-08-10 right after load. Price known at T = bar starting T-2min. No look-ahead.
- Daily: OHLC adjusted by Adj Close / Close. Gap g = log(O_D / C_{D-1}). BTC move m = prior local close -> open. Tokyo close 06:30 UTC (06:00 before 2024-11-05), HK close 08:00 UTC.
- Residual: rolling past-only beta (W = 60/120/250) of g on m, resid = g - beta*m, z = resid / past std.
- Costs: 20 bp round trip (10 bp per side), net = gross - 0.20%.
- Intraday: 60m bars, decision at bar open t with BTC over [t-60m, t). Lunch-straddling bars excluded.
- Limit days: close = high (or low) and |ret| > 10% on raw data. Trade next open->close.
## Variant count
- 29 rules per ticker x 7 tickers = 203 attempted, 201 with trades. Families: btc_dir (3), resid follow/fade (18), limit cont/fade (2), intraday follow/fade (6).
## Top 3 by dev t (n_dev >= 30), net bp
| ticker | rule | dev n | dev bp | dev t | chk n | chk bp | chk t | flip chk bp |
|---|---|---|---|---|---|---|---|---|
| 0434.HK | resid fade W=250, abs z>=0.5 | 562 | +109 | 7.0 | 424 | +50 | 2.1 | -90 |
| 0434.HK | resid fade W=250, abs z>=1.0 | 306 | +157 | 6.9 | 196 | +95 | 3.0 | -135 |
| 0434.HK | resid fade W=120, abs z>=1.0 | 321 | +151 | 6.8 | 213 | +121 | 4.1 | -161 |

Per-year net bp, rule 1 (W=250, z>=0.5): 2018 +191, 2019 +51, 2020 +138, 2021 +94, 2022 +105, 2023 +130, 2024 -124, 2025 +106, 2026 +118. The 2024 loss is the one bad year.
Dev->check decay is 30-55%, not a collapse. Check net at 40 bp RT for rule 3: +101 (t 3.4).
## Test 1: daily gap vs BTC move (pooled, net)
| family | dev bp (t) | check bp (t) |
|---|---|---|
| resid follow, all W/thr (pooled) | -41 to -81 (t -7 to -9) | -32 to -60 (t -3.4 to -6.8) |
| resid fade, all W/thr (pooled) | +1 to +41 (t 0.3-3.9) | -8 to +20 (t -1.5 to 1.3) |
| btc_dir, JP pooled, abs m>=1% | +6 (t 1.1) | +5 (t 1.0) |
| btc_dir, JP pooled, abs m>=2% | +12 (t 1.9) | +4 (t 0.5) |

- Gap beta (full-era OLS slope, corr): 3350 1.43 (0.58), 3825 0.61 (0.49), 8698 0.24 (0.47), 8473 0.11 (0.27), 9449 0.12 (0.28), 0434 0.11 (0.18), 1723 0.01 (0.01). The BTC move is largely in the open for the two treasury names.
- Single-name btc_dir, abs m>=1%: 3825 dev +52 (t 1.7), check +82 (t 3.1, n=143), flip -122. Per-year net 2024 +84, 2025 +34, 2026 +81. 3350 abs m>=2%: dev +117 (t 1.7), check +54 (t 1.1, n=77). Both are positive in every year, but samples are small and not multiple-testing-proof (203 combos).
- Flip control for btc_dir: the opposite direction loses, so this is not pure drift. Up-day vs down-day open->close: 3350 +48 / -60 bp, 3825 +58 / -106 bp.
## Test 2: limit days
- Days flagged (in era): 3350 35, 3825 11, 8698 8, 1723 22, 0434 8. Too few to test; pooled next-day continuation dev +24 (t 0.1) and check +172 (n=23, t 0.6). Not an edge.
## Test 3: intraday 60m (BTC prior hour -> stock next hour), net bp
- Dev is empty for the five 2017-era names (60m data starts after their cut). Check-only for those.
- Pooled intra_follow, check: -17 (|BTC 1h|>=0), -14 (>=0.25%), -11 (>=0.5%). Fade is also negative. No edge.
- 0434.HK: corr(BTC prior hour, stock next hour) = +0.10 (n 3240). Follow gross +17 bp/hour, net -3 at 20 bp RT. At |BTC 1h| >= 0.5%: net +3 (t 0.3, n 559). Not tradable after costs.
- Other names: corr ~0.00-0.03.
## Caveats
- Sample: Metaplanet BTC era ~2.4 years; 3825 start is a proxy; limit-day n<=35.
- 0434 has 104 zero-range days and 14 days with open outside H/L. 1723 has 467 zero-range days and 31 bad opens. HK prints are noisy.
- 10 bp per side is optimistic for thin HK small caps.
- 1723.HK, the sister HK name, does not replicate: its top dev rules have check t 0.7-1.2.
- Raw gap fade with no BTC on 0434 check is -17 bp, while residual fade is +37 bp. So part of the effect is the BTC-residual piece, not generic gap reversal.
## Best rule to code (forward-test candidate, 0434.HK only)
Each trading day D, for 0434.HK: g = log(O_D / Adj C_{D-1}). m = log(BTC close at 00:00 UTC-1min / BTC close at prior 08:00 UTC-1min), using bars ending before the open (strict).
beta = past-only rolling cov(g, m) / var(m), W=120 (min 60), shifted by 1. resid = g - beta*m. z = resid / past 120-day std of resid.
If |z| >= 1.0: short at open if resid > 0, long at open if resid < 0. Exit at close D. Net = gross - 20 bp.
Dev net +151 bp (n 321), check +121 bp (n 213, t 4.1), 40 bp RT check +101 bp (t 3.4).
## Files
- Scripts: run_tests.py, lib.py, fetch.py, diag2-5.py. Cache: cache/. Trades: trades_all.parquet. Variants: variants.csv.
