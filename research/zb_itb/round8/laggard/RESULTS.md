# Round 8: laggard homebuilder (ZB sign, 1m vault, entry 09:31/09:35, exit 10:29 close)
Costs 3 bp/side/stock (6 bp RT per leg). beta_i = rolling 120d no-intercept regression of open gap on m (past-only, min 30d). Dev <=2025-06-30, check >=2025-07-01. Scripts: run.py (6 names), run5.py (5 names, no NVR). 16 variants tried (+200 random draws).
Coverage: exact-minute bars required. NVR (thin) has 09:30 bar on only 280/570 signal days, KBH ~511, so the 6-name run has n=182 and is unreliable; headline uses 5 names (DHI LEN PHM TOL KBH), n=415 days.

| 5 names, entry 09:31 | n | net bp | t | Sharpe | dev bp (t) | check bp (t) |
|---|---|---|---|---|---|---|
| Laggard (min d*resid) | 415 | 18.6 | 2.75 | 2.14 | 13.5 (1.41) | 23.0 (2.42) |
| Laggard, 09:35 entry | 332 | 12.2 | 2.00 | 1.74 | 11.4 (1.29) | 13.0 (1.54) |
| Top-2 laggards | 415 | 14.6 | 2.43 | 1.89 | 11.6 (1.38) | 17.1 (2.01) |
| Equal-weight basket 09:31 | 415 | 13.2 | 2.28 | 1.77 | 11.3 (1.39) | 14.9 (1.81) |
| Best single name (TOL) | 415 | 14.8 | 2.32 | 1.80 | 12.6 (1.38) | 16.8 (1.87) |
| Leader (max d*resid) | 415 | 11.2 | 1.74 | 1.36 | 9.7 (1.05) | 12.5 (1.39) |
| Random pick (200 draws) | 415 | 13.4 (sd 2.4) | ~2.1 | | | |
| Long-short laggard minus leader, 09:31 (0.5 each leg) | 415 | -2.3 | -1.05 | -0.82 | -4.1 | -0.7 |
| Long-short, 09:35 | 332 | -6.5 | -3.26 | -2.84 | -8.6 | -4.5 |
| Flip control (-d, laggard) | 415 | -30.6 | -4.52 | | | |

6-name (n=182): laggard 19.1 bp t 1.91; EW 9.0 t 1.1; leader 1.3; random 9.3; LS 2.9 t 0.7. Same ordering, too few trades.

## Findings
- The 09:31 entry keeps the edge: EW basket still +13 bp net after the first minute is skipped (the ZB edge is not all in the opening print).
- Laggard beats the EW basket by ~5 bp and random pick by ~5 bp (about 2 sd of the random-draw spread), and leader is ~7 bp worse. But the laggard minus leader gap is not significant: the long-short is negative/zero. So the residual ranking adds at most a small, unproven amount; the paired difference laggard minus EW (~5 bp on ~415 days with daily sd of ~100+ bp) has t well under 2 (not computed formally, selected on 16 variants).
- 09:35 entry halves the pickup (12 bp laggard, 11 bp EW): most of the catch-up that remains is in the first minutes; waiting costs.
- Long-short is not viable: removing the sector move removes the edge (the edge is the common sector move, not cross-sectional catch-up). At 09:35 it is significantly negative, i.e. the leader catches up more than the laggard.

## Verdict: NONE for the laggard idea (WEAK at best)
Trade the equal-weight basket (or the plain ZB rule) at 09:31 instead; the laggard selection is not distinguishable from random pick/best name after multiple variants and costs more selection noise. Long-short has no edge.
