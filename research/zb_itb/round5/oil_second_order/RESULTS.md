# Oil / natgas second-order users: first-hour test (round 5)

**Verdict: NONE** for the spec (first hour, 10:30 exit). WEAK at best for airlines at 11:30 / close, not tradable as is.

## Setup
- Signal: d = sign(futures 08:00 bar close / prior-session 15:00 bar close). Start-labeled bars verified: CL=F 765/765 and NG=F 760/760 overlapping bars match the start-labeled 5m aggregate (end-labeled: 4/731 and 12/732).
- Trade: entry 09:30 60m Open. Exits: 10:30 (close of 09:30 bar), 11:30, close (last regular bar). Net = sign x d x log return - round trip cost.
- Sign: "-d" = brief's hypothesis (oil up, short the user). "+d" = flip control.
- Cost: 2 bp/side; 5 bp/side when median dollar volume < $100M (only JETS, $98M).
- Dev 2024-05-28..2025-06-30; check 2025-07-01..2026-10-16. Mean in bp, t, win rate.

## Per name (-d at 10:30, the spec), dev and check
| Signal | Group | Name | Cost | Dev n / mean / t / win | Check n / mean / t / win | -d@close dev / chk (mean, t) | +d@10:30 chk (mean, t) |
|---|---|---|---|---|---|---|---|
| oil | airlines | JETS | 5 | 252 / 4.6 / 0.66 / 53% | 313 / 3.4 / 0.57 / 51% | 17.1 / 1.53 ; 14.9 / 1.67 | -23.4 / -4.00 |
| oil | airlines | DAL | 2 | 252 / 20.2 / 2.01 / 53% | 312 / 4.2 / 0.54 / 52% | 35.5 / 2.33 ; 6.7 / 0.57 | -12.2 / -1.56 |
| oil | airlines | UAL | 2 | 252 / 19.0 / 1.55 / 53% | 314 / 7.7 / 0.84 / 52% | 37.5 / 1.94 ; 18.9 / 1.40 | -15.7 / -1.71 |
| oil | airlines | AAL | 2 | 252 / 22.5 / 2.01 / 55% | 314 / 5.9 / 0.64 / 52% | 38.7 / 2.29 ; 26.0 / 1.89 | -13.9 / -1.52 |
| oil | airlines | LUV | 2 | 252 / 12.0 / 1.30 / 52% | 313 / 11.6 / 1.39 / 49% | 21.2 / 1.56 ; 28.7 / 2.31 | -19.6 / -2.34 |
| oil | airlines | ALK | 2 | 252 / 16.1 / 1.65 / 53% | 313 / 19.6 / 1.90 / 55% | 33.2 / 2.11 ; 28.7 / 1.95 | -27.6 / -2.68 |
| oil | cruise | CCL | 2 | 252 / 9.6 / 0.82 / 49% | 312 / -2.1 / -0.23 / 46% | 29.7 / 1.86 ; 4.1 / 0.32 | -5.9 / -0.66 |
| oil | cruise | RCL | 2 | 252 / 5.6 / 0.50 / 50% | 313 / 5.9 / 0.65 / 52% | 24.6 / 1.61 ; 7.6 / 0.57 | -13.9 / -1.53 |
| oil | cruise | NCLH | 2 | 252 / 4.9 / 0.40 / 50% | 313 / 4.2 / 0.44 / 51% | 30.1 / 1.77 ; 9.9 / 0.72 | -12.2 / -1.28 |
| oil | truck | ODFL | 2 | 252 / -3.8 / -0.45 / 46% | 314 / -0.4 / -0.04 / 51% | 12.6 / 1.03 ; 9.5 / 0.78 | -7.6 / -0.85 |
| oil | truck | JBHT | 2 | 252 / -1.1 / -0.15 / 50% | 314 / 3.5 / 0.47 / 51% | 10.6 / 0.98 ; 6.1 / 0.59 | -11.5 / -1.53 |
| oil | truck | FDX | 2 | 252 / -9.8 / -1.61 / 46% | 313 / -3.1 / -0.49 / 46% | 1.8 / 0.19 ; 0.0 / 0.00 | -4.9 / -0.79 |
| oil | truck | UPS | 2 | 252 / -5.3 / -0.86 / 49% | 313 / 8.7 / 1.36 / 53% | 3.5 / 0.40 ; 6.1 / 0.71 | -16.7 / -2.60 |
| oil | chem | DOW | 2 | 252 / 1.2 / 0.17 / 50% | 312 / -10.1 / -1.01 / 43% | 23.0 / 1.79 ; -15.5 / -1.16 | 2.1 / 0.21 |
| oil | chem | LYB | 2 | 252 / -1.9 / -0.29 / 52% | 313 / -8.6 / -0.90 / 48% | 12.5 / 1.11 ; -15.2 / -1.17 | 0.6 / 0.07 |
| oil | refiners | VLO | 2 | 252 / -8.3 / -0.94 / 50% | 313 / -2.3 / -0.29 / 51% | 4.2 / 0.31 ; 12.0 / 1.08 | -5.7 / -0.71 |
| oil | refiners | MPC | 2 | 252 / -2.6 / -0.29 / 51% | 313 / -0.1 / -0.02 / 53% | 11.1 / 0.86 ; 10.3 / 0.99 | -7.9 / -1.03 |
| oil | refiners | PSX | 2 | 252 / -9.4 / -1.25 / 49% | 313 / 7.6 / 1.08 / 56% | 3.4 / 0.30 ; 12.9 / 1.33 | -15.6 / -2.23 |
| ng | utilities | XLU | 2 | 248 / -11.4 / -2.86 / 38% | 312 / -6.6 / -1.81 / 46% | -8.2 / -1.29 ; -5.5 / -1.10 | -1.4 / -0.38 |
| ng | utilities | NEE | 2 | 248 / -11.1 / -1.69 / 47% | 312 / -10.0 / -1.91 / 45% | -2.2 / -0.22 ; -11.0 / -1.47 | 2.0 / 0.38 |
| ng | utilities | DUK | 2 | 248 / -10.2 / -2.47 / 43% | 312 / -8.1 / -2.19 / 42% | -5.5 / -0.83 ; -7.5 / -1.47 | 0.1 / 0.03 |
| ng | fert | CF | 2 | 248 / 3.0 / 0.36 / 50% | 311 / -1.4 / -0.16 / 51% | 4.6 / 0.40 ; 5.7 / 0.47 | -6.6 / -0.75 |
| ng | fert | NTR | 2 | 248 / -6.8 / -0.85 / 47% | 312 / -5.7 / -0.76 / 46% | 1.7 / 0.16 ; 0.1 / 0.01 | -2.3 / -0.31 |

Controls (-d, 10:30 dev / check mean, t): SPY oil -1.7 / -0.68 ; -2.1 / -1.11. USO -7.9 / -1.60 ; -4.7 / -1.13. XLE -5.3 / -1.03 ; -2.2 / -0.49. SPY NG -1.7 / -0.66 ; -2.0 / -1.05.

## Composite baskets (equal weight, pre-set sign -d, 10:30 / 11:30 / close)
- Oil users (18 names): dev +4.1 / +5.3 / +19.5 bp (t 0.7 / 0.8 / 1.9); check +3.1 / +7.7 / +9.5 bp (t 0.6 / 1.4 / 1.4).
- Half-years, 10:30: 2024H2 +5.5 (t 0.9), 2025H1 +2.4 (0.2), 2025H2 +9.7 (1.1), 2026 -1.0 (-0.2).
- SPY placebo, same signal: 10:30 dev -1.7 / check -2.1; close dev +10.5 (t 1.6) / check +0.2.
- NG basket (utilities + fertilizers, -d, 10:30): dev -7.3 (t -1.8), check -6.3 (t -1.6). Wrong sign, not an edge.

## Where the move shows up (gap vs first hour, aligned with d, bp)
- USO / XLE overnight gap: +161 / +54 (check), +108 / +51 (dev). First hour: about 0. Direct oil equities price the overnight move at the open, as the earlier study said.
- Airlines overnight gap: about -60 to -85 bp in check but +13 to +20 bp in dev (sign flips across regimes, 2026 drives the check). First hour (to 10:30): -8 to -23 bp (check), -15 to -27 bp (dev).
- Read: the open already carries most of the oil move for airlines in 2026. The lag left for the first hour is small.

## Verdict and caveats
- Spec (-d, 10:30): no name or basket has an edge in both periods. Basket t about 0.6 to 0.7.
- Close / 11:30: airline names show positive check results (ALK 11:30 +32 bp, t 2.8; LUV close +29 bp, t 2.3). They are selected out of about 70 sign-and-exit variants per name group, their dev values are weaker, the SPY close placebo is +10 bp in dev, and the basket fades in 2026. WEAK, not EDGE.
- Variants: 23 names x 3 exits x 2 signs = 138 name variants (plus 4 controls). 20 have |check t| >= 2, but 16 of those are the +d (flip) mirror. Of the 69 -d name variants, 3 are positive at |t| >= 2 in check (ALK 11:30, LUV 11:30, LUV close) and 1 is negative (DUK 10:30). Expected by chance at |t| >= 2 is about 3.5 of 69.
- Costs: 2 bp/side everywhere except JETS (5 bp). At 5 bp/side, every number above drops by about 6 bp.
- Refiners: both signs tested. The -d spec at 10:30 has |t| <= 1.3 in both periods for VLO, MPC and PSX.
- Files: study2.py (main), gap_check.py, by_period.py, pick_names.py, results_clean.csv, composite.csv, gap_check.csv, check_labels.py.
