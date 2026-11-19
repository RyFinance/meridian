# Daily options on BTC off-hours signals (MSTR, IBIT), 2026-10-17

Holdout: all data filtered to <= 2026-08-10 at load. Scripts: `run_options_daily.py` (log in `run_log.txt`, all variants in `variants.csv`, trades in `trades.pkl`).

## What was tested
- Schema: ts (UTC midnight = trade date), expiry, opt_type, strike (as-traded per date, pre-split values before 2024-08-08), open/high/low/close, volume. The files only contain printed contracts, so volume > 0 on every row. Spot is inferred each day from put-call parity on that day's own prints (median over expiries, 2-30 DTE).
- Dev = signal date <= 2022-06-30; check = 2022-07-01..2026-08-10. IBIT starts 2024-11-20, so IBIT has no dev sample and cannot be used for selection.
- Idea (a) rule A: signal = BTC 15:00-16:00 ET move (`lh`) or 09:30-16:00 ET move (`sess`), threshold 0 / 0.5% / 1%. Buy ATM call if up, put if down. Entry at the day-t close print, exit at the next weekday open print. DTE band 2-10, 2-5 or 6-10 (shortest eligible expiry).
- Idea (b) rule B: overnight BTC shock `off_in` (prior 16:00 to 09:29 ET) above 3/4/5%. Enter the reversal vertical at the open print (long ATM, short 10% OTM, same expiry, DTE 3-10). Exit at the close print after 1, 2 or 4 days.
- Count: 54 rule variants (36 A, 18 B), each with its flipped-direction control (108 backtests).
- Fills: primary = print +/- half-spread max($0.03, 2.5%) plus $0.65/contract/side (x100). Worst case = high for buys, low for sells. Minimum premium $0.10. Returns are per-contract, net of costs.

## BTC: does the move carry past 16:00 ET?
- Sign-aligned mean of the next 16:00 to 09:29 BTC move: +6bp (|lh|>0, t 0.84), +8bp (|lh|>0.5%, t 0.55), -18bp (|lh|>1%, t -0.67). Correlation about 0 (-0.02 to -0.08). No continuation after 16:00.
- Overnight |move| > 4% occurred on 344 days (192 up, 152 down).

## Results (top rows; all 54 variants in variants.csv)
Primary = print fills. Worst = high/low fills. Returns are per trade.

| Rule (MSTR unless noted) | n dev | dev primary mean / median | n chk | chk primary mean / median / t | chk win (primary) | chk worst mean |
|---|---|---|---|---|---|---|
| A lh >1%, DTE 6-10 | 37 | +7.0% / +2.1% | 53 | -4.1% / -5.6% / -1.06 | 36% | -33.2% |
| A sess >1%, DTE 6-10 | 145 | +0.6% / -8.4% | 383 | -4.2% / -8.4% / -2.29 | 35% | -37.5% |
| A lh >0.5%, DTE 6-10 | 110 | -3.7% / -7.9% | 194 | -1.2% / -5.5% / -0.52 | 41% | -36.0% |
| A lh >0, DTE 2-10 | 331 | -2.2% / -9.0% | 945 | -4.6% / -7.5% / -3.63 | 39% | -53.0% |
| B off_in >3%, t+2 | 77 | -8.2% / -24.6% | 129 | +22.3% / -41.2% / +0.63 | 29% | -77.2% |
| B off_in >4%, t+2 | 53 | -5.8% / -22.8% | 72 | +64.5% / -35.7% / +1.03 | 40% | -73.0% |
| B off_in >5%, t+1 | 42 | -6.0% / -14.4% | 40 | +13.0% / -22.2% / +0.68 | 38% | -81.3% |

Top 3 by dev worst-case mean (the selection criterion, dev only):
1. A lh >1%, DTE 6-10: dev worst -16.2% (n 37), check worst -33.2% (n 53).
2. A sess >1%, DTE 6-10: dev worst -25.4% (n 145), check worst -37.5% (n 383).
3. A lh >0.5%, DTE 6-10: dev worst -27.1% (n 110), check worst -36.0% (n 194).

## Best rule, exact
Signal at 16:00 ET on day t: r = BTC close(15:59 bar) / open(15:00 bar) - 1. If r > +1%, buy the ATM MSTR call at the day-t close. If r < -1%, buy the ATM put. Use the shortest listed expiry with 6-10 DTE and the strike nearest spot (within 5%). Sell at the next weekday open print. Do this only if the contract printed on both days.

## Flip control (same rule, reversed direction)
- Rule 1: check primary flip -7.2% (rule -4.1%). Dev flip -13.2% (rule +7.0%).
- Rule 2: check primary flip -6.7% (rule -4.2%). Dev flip -11.8% (rule +0.6%).
- Rule 3: check primary flip -8.4% (rule -1.2%).
- The rule beats its flip by 3 to 7 points on primary check, but both sides are net negative, so the gap is cost drift in the spread, not a tradable edge.

## Per-year, best rule (rule 1, primary / worst mean)
- Primary: 2021 -1% (n 25), 2022 +8% (n 23), 2023 -4% (n 11), 2024 +2% (n 14), 2025 -10% (n 10), 2026 -4% (n 7).
- Worst: every year negative (-17% to -49%).

## Verdict: NONE
- No rule passes on dev and check at the same time. Dev-to-check decay is large, and dev primary means of +7% (rule 1) and +0.6% (rule 2) become -4% and -4% on check.
- Rule B (overreaction vertical): dev primary is negative for all shocks. Check means are positive only with fat right tails (median -22% to -41%, n 40-129, t below 1.1).
- Criterion (c): no rule has a high win rate with a positive mean that holds on check. Win rates reach 36 to 41% on primary, and 2 to 11% on worst fills.
- IBIT (check only, no dev): A lh >0.5% DTE 6-10 primary +3.5% (n 69, median -5.1%, t 0.63), flip -12.4%. B off_in >5% t+2 primary +20% on n 11 (too small, not selectable).
- Caveats: fills are primary/worst prints, not intraday quotes. Entry at the 16:00 close uses BTC through 15:59 (same minute). Multiple-testing risk is real (54 variants).
