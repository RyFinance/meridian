# Earnings information transfer (bellwether pre-market report -> peers) : VERDICT = NONE

## Setup
- Universe: 177 tickers in 28 hand-mapped clusters (big/regional/custody banks, brokers, airlines, rails, homebuilders, 3 semi groups, payments, consumer finance, pharma, oil services, big oil, mass/home retail, restaurants, trucking/freight, staples, managed care, telecom, autos, defense, industrials, insurers, medtech, chemicals). BK, CMA, TMHC had no data.
- Events: cluster-day = one or more cluster members with a yfinance earnings timestamp 05:00-09:00 ET (BMO), 2024-05-01..2026-10-16. 842 cluster-days (829-839 with a usable signal). Peers = all other cluster members with no earnings from D-1 to D+5. Equal-weight basket per event; sign = sign of reporter's abnormal move (reporter minus SPY).
- TIMING A (primary): prepost 60m data exists for the whole span. Signal = reporter's 09:00 bar close (bars are START-labeled, so the 09:00 bar spans 09:00-09:30 and closes before the open; verified on JPM) / prior 15:30-bar close - 1, minus SPY's same number. Peers entered at the official 09:30 bar Open (market-on-open). Reporter's own open is NOT used.
- TIMING B (fallback): signal = reporter's 09:30 open gap (abnormal vs SPY); peers entered at the 10:30 bar Open (after the first hour; a later-than-09:31 entry).
- Exits: 10:30 (h1, A only), 16:00 (15:30 bar close, "day"), close D+1, close D+3. Costs: 2 bp/side mega caps, 5 bp other, 10 bp thin (per-ticker tiers in universe.py).
- Split: dev = first 55% of event dates (to 2025-08-22), check = rest. Date-clustered t. Sanity: corr(reporter premarket move, open gap) = 0.97; reporter |abn move| 3.6% on event days vs 0.6% other days, so timestamps are right.

## Results (net bp per event; DEV | CHECK). Variants run: 21 grid (A x {0,1,2%} x 4 horizons + B x 3 x 3) plus controls/cuts, ~55 looks in total.
| rule | DEV n / mean / t / win | CHECK n / mean / t / win |
|---|---|---|
| A thr 1% day (pre-chosen primary) | 374 / -4.3 / -0.48 / .48 | 295 / -17.7 / -2.09 / .46 |
| A thr 0 h1 (first hour) | 471 / -6.3 / -1.73 / .47 | 368 / -3.8 / -0.73 / .49 |
| A thr 1% D+1 | 374 / -13.7 / -1.36 / .49 | 293 / -13.8 / -0.92 / .49 |
| A thr 2% D+3 (best dev net of all 21) | 302 / +3.0 / +0.18 / .53 | 232 / -42.2 / -2.00 / .48 |
| B thr 1% day (entry 10:30) | 378 / -4.7 / -0.69 / .46 | 298 / -18.9 / -3.28 / .41 |
All 21 variants have dev net between -20 and +3 bp, no dev t above +0.2. Gross (pre-cost) is also about 0: A 1% day gross +3.8 dev / -9.6 check.

## Controls (A, 1%, day; net DEV | CHECK)
- Flip (opposite direction): -11.8 (t -1.3) | +1.5 (t 0.2); gross sign differs between halves, so no stable reversal either.
- SPY placebo, same signal: -1.6 | -2.9 (about 0).
- Random non-peer basket, same day, same direction: -8.7 | -10.5 (gross -0.9 | -4.5): peers are no better than random.
- Same peers on non-event days (reporter premarket move >=1%, no earnings): net -3.5 | -5.4, GROSS +7.1 (t 3.1) | +5.9 (t 3.1). A small generic cluster premarket-continuation exists on non-earnings days and is NOT stronger on earnings days (+3.8 | -9.6 gross), and it does not survive cost.
- SPY-hedged peers: -10.7 | -22.8.
- Dose-response: peer day return on reporter move = +0.11 bp per 1% reporter move (t 0.11; dev -0.14, check -0.07). h1: +0.54 (t 0.74); D+1: +0.72 (t 0.47). Controlling for the peer's own premarket move changes nothing. |move| terciles (day gross DEV | CHECK): small -2.6|+17.2, mid +7.2|+5.4, big +8.4|-29.9. No monotone dose-response; the biggest reporter moves reverse in check.
- Peers already price the read-through: mean peer premarket abnormal move in reporter's direction is +34 bp, and nothing is left after the open.
- Per cluster (pooled, unselected, n 10-89): scatter from -100 to +85 bp net with no coherent pattern (homebuilders -101, home improvement -99, brokers +85); noise at these n, not reportable edge.

## Correlation with the ITB (ZB) rule
Daily net P&L of A/1%/day vs f3_trades_canonical (g_off - 4 bp): corr -0.06 on 264 overlapping days (-0.04 zero-filled). A/h1: -0.04. Independent, but there is nothing to diversify with.

## Verdict: NONE
Pre-market earnings read-through to same-industry peers is priced at the open (peers already move +34 bp in the reporter's direction pre-open) and the remaining first-hour, same-day and 1-3 day drift is zero (gross about 0, net negative after 8-20 bp round-trip costs), with no dependence on reporter move size, and no better than a random non-peer basket or non-event-day cluster moves. Caveats: 60m bars only (a 09:30 entry misses the first ~1 min; 5m data would not change a zero gross); yfinance earnings times are rounded to the hour; events overlap within a date, so n_dates (295) is the effective sample.
Files: universe.py, fetch.py, build.py, analyze.py, analyze2.py, analyze3.py (px60.pkl, earn.pkl, daily.pkl cached).
