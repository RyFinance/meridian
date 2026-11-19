# Round 5 / model_improve: can the ZB->ITB rule be improved? (29 variants incl. 2 controls)
Script: run.py (table.csv has full numbers). Entry = official open, exit = 60m bar close, cost 4bp RT (ITB/XHB/SPY), basket 7bp RT, NAIL 10bp/side (5bp/side shown too).
Every variant is scaled so average gross = 1x on dev days (constant carried to check). Daily series includes zero days for skipped trades, so Sharpe/t are comparable. "mean" = bp per day at 1x gross.
dev = 2024-05-28..2025-06-30, check = 2025-07-01..2026-10-16.

| variant | dev n | dev mean | dev t | dev Sh | dev DD% | chk n | chk mean | chk t | chk Sh | chk CAGR% | chk DD% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 00 baseline fixed, exit 10:30 | 260 | 16.6 | 2.93 | 2.82 | -7.3 | 310 | 27.4 | 4.27 | 3.77 | 99 | -12.6 |
| 01 size |m| cap2 | 260 | 25.7 | 3.12 | 2.99 | -11.1 | 310 | 23.1 | 3.39 | 2.99 | 78 | -9.1 |
| 02 size |m|/vol60 cap2 | 260 | 25.3 | 3.05 | 2.93 | -11.6 | 310 | 28.6 | 3.23 | 2.85 | 105 | -15.2 |
| 03 size sqrt|m| cap2 | 260 | 21.5 | 3.04 | 2.92 | -10.1 | 310 | 24.8 | 3.89 | 3.43 | 86 | -10.9 |
| 04 only |m|>dev median | 133 | 25.5 | 2.88 | 2.76 | -10.4 | 97 | 15.1 | 1.91 | 1.69 | 46 | -11.0 |
| 05 ZN only | 261 | 12.8 | 2.24 | 2.15 | -7.3 | 312 | 16.4 | 2.49 | 2.20 | 51 | -13.5 |
| 06 avg ZB+ZN (std) | 265 | 13.8 | 2.44 | 2.34 | -7.2 | 316 | 20.7 | 3.21 | 2.83 | 68 | -16.3 |
| 07 agree-only ZB&ZN | 230 | 17.4 | 2.84 | 2.73 | -8.3 | 279 | 25.8 | 3.70 | 3.27 | 91 | -12.5 |
| 08 overnight 16->08 only | 264 | 10.0 | 1.74 | 1.67 | -11.8 | 308 | 21.3 | 3.33 | 2.94 | 71 | -8.2 |
| 09 last hour 08->09 only | 251 | 4.4 | 0.75 | 0.72 | -11.8 | 306 | 6.4 | 0.92 | 0.81 | 18 | -19.3 |
| 10 over + 2*last | 266 | 13.5 | 2.39 | 2.29 | -7.3 | 315 | 15.8 | 2.45 | 2.16 | 49 | -13.0 |
| 11 XHB | 260 | 10.7 | 1.96 | 1.89 | -7.6 | 310 | 22.2 | 3.91 | 3.44 | 74 | -11.2 |
| 12 EW basket 6 names | 260 | 9.2 | 1.45 | 1.39 | -11.2 | 310 | 20.2 | 2.84 | 2.51 | 66 | -15.1 |
| 13 ITB+XHB avg | 260 | 13.7 | 2.49 | 2.40 | -7.5 | 310 | 24.8 | 4.15 | 3.66 | 86 | -11.9 |
| 14 NAIL 10bp/side | 260 | 39.3 | 2.36 | 2.27 | -23.2 | 310 | 65.9 | 3.48 | 3.07 | 422 | -31.3 |
| 14b NAIL 5bp/side | 260 | 49.3 | 2.96 | 2.84 | -22.4 | 310 | 76.0 | 4.01 | 3.53 | 572 | -29.2 |
| 15 exit 11:30 | 260 | 19.0 | 2.73 | 2.63 | -7.9 | 309 | 26.7 | 3.69 | 3.26 | 95 | -15.9 |
| 16 exit 13:30 | 260 | 22.6 | 2.71 | 2.60 | -7.9 | 309 | 26.3 | 3.38 | 2.98 | 93 | -17.4 |
| 17 exit close | 260 | 22.9 | 2.39 | 2.29 | -13.5 | 308 | 27.3 | 3.15 | 2.78 | 98 | -19.5 |
| 18 hold to close if profit@10:30 | 260 | 26.1 | 3.14 | 3.01 | -9.9 | 308 | 29.0 | 3.71 | 3.27 | 107 | -17.3 |
| 19 hold to 11:30 if profit@10:30 | 260 | 20.3 | 3.04 | 2.92 | -8.1 | 309 | 27.2 | 3.90 | 3.44 | 98 | -14.6 |
| 20 d=sign(beta*m-gap) | 266 | -8.4 | -1.46 | -1.41 | -25.9 | 316 | -16.8 | -2.57 | -2.27 | -34 | -45.5 |
| 21 only if open under-priced | 121 | 14.9 | 1.70 | 1.63 | -15.0 | 103 | 17.3 | 2.23 | 1.97 | 54 | -21.9 |
| 22 size by clipped d*(beta*m-gap) | 121 | 19.1 | 1.36 | 1.31 | -20.5 | 103 | 18.0 | 2.14 | 1.89 | 57 | -13.2 |
| 23 extend to 11:30 if remaining unpriced>0 @10:30 | 260 | 19.6 | 3.16 | 3.03 | -7.3 | 310 | 28.1 | 4.27 | 3.76 | 102 | -13.9 |
| 24 as 23 and in profit | 260 | 19.0 | 3.11 | 2.99 | -7.1 | 310 | 27.4 | 4.25 | 3.74 | 99 | -12.5 |
| 25 under-priced filter + exit 11:30 | 121 | 20.7 | 1.97 | 1.90 | -18.0 | 103 | 15.0 | 1.71 | 1.50 | 46 | -23.9 |
| C1 flip control | 260 | -24.6 | -4.34 | -4.17 | -52.0 | 310 | -35.4 | -5.52 | -4.87 | -59 | -67.6 |
| C2 placebo SPY | 260 | -1.9 | -0.75 | -0.72 | -8.4 | 310 | -1.4 | -0.74 | -0.65 | -3 | -7.0 |

beta (ITB gap on ZB move, dev only) = 0.36. NAIL vs ITB first-hour: corr 0.98, slope 2.89, ~$55M/day, price ~$34 (liquid enough for ~5bp/side).

## Verdicts
1. Sizing (01-04): NONE. Dev gain in mean (+9 bp) with Sharpe +0.1-0.2, but check Sharpe falls 3.77 -> 2.85-3.43 and dev drawdown rises 50%. Dev-only gains are within noise; fixed size is best on check.
2. Composite (05-10): NONE. ZN adds nothing (avg and ZN-only are worse than ZB alone; agree-only is flat and drops ~12% of trades). Signal lives in the overnight leg (over alone check 2.94, last hour alone ~0.8); weighting the last hour is worse.
3. Instrument (11-14): NONE. ITB is best or tied. XHB, basket and ITB+XHB all have lower dev Sharpe (basket's higher costs hurt). NAIL: same Sharpe as ITB at 5bp/side (2.84/3.53), lower at 10bp, 3x the drawdown (-22 / -31%); it is leverage, not edge. Skip unless the user wants leverage and can accept -30% DD.
4. Exit (15-19): WEAK/NONE. Later exits and hold-if-profit raise dev Sharpe (18: 3.01 vs 2.82) but lower check Sharpe (3.27 vs 3.77) with deeper DD (-17%). A real post-10:30 drift exists in dev, not confirmed in check. Keep 10:30.
5. Unpriced gap (20-25): NONE. sign(beta*m - gap) as direction is strongly negative (the gap does not help, the sign of m is the signal). Filtering to "open under-priced" halves trades and degrades both periods. Only 23 (extend to 11:30 if remaining unpriced>0 at 10:30) is neutral-to-slightly-positive (dev 3.03, check 3.76 vs 2.82/3.77): flat on check, so no evidence.

## Recommendation
No change. Keep the fixed-size ZB sign -> ITB 09:30 official open -> 10:30 exit. Nothing beat the baseline on both dev and check: the one candidate that moved dev only (23 or 18) is flat/worse on check, and the dev winners (01, 18) lose 0.5-0.8 Sharpe on check.
Overfitting: 29 variants, many correlated; dev t of 3.0-3.1 for the "best" ones against baseline 2.9 is not distinguishable from selection noise. Controls behave: flip is -4.2 Sharpe dev / -4.9 check, SPY placebo about 0.
