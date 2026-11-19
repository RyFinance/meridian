# crypto_deep (agent: crypto_deep)

Sealed: nothing dated after 2026-08-10 ET loaded (common.load filters at ET 2026-08-10 23:59). Dev = 2017-2022, check = 2023-01..2026-08-10. Costs 10 bp RT (5 bp/side) for BTC, ETH, SOL. Code: `common.py`, `fomc_run.py`, `offhours_run.py`, `fetch_sol.py`. Full tables: `out/fomc_cells.csv`, `out/offhours_cells.csv`, trade files `out/*_trades.csv`.

## Verdicts
- **Job 1, FOMC continuation: WEAK, does not hold on the extended dev.** BTC check is positive (+88 bp, t 1.9), but dev 2017-22 is flat (+4 bp, n 42, t 0.1) and the non-FOMC control is +20 bp in the same dev. The lead's dev (+112 bp) is 15 events from 2020-08..2022-06 (t 1.0); the same window reproduces it, so it is a small-sample figure. ETH replicates the check sign (+208 bp, t 2.3) but its dev is negative (-82 bp, t -1.0). Not EDGE.
- **Job 2, off-hours sessions (BTC, ETH, SOL): NONE**, with one WEAK exception (SOL weekend continuation, see below). 0 of 81 signal lines have check t >= 2 in the with-direction.

## Setup and variant count
- FOMC decision dates hardcoded from the public Fed calendar: 71 scheduled meetings 2017-09-20..2026-07-29 (dev 42, check 29 entries). Emergency 2020-03-03 and 2020-03-15 excluded. Cross-check vs `economic_calendar.csv` (US "Fed Interest Rate Decision"): all 71 match; the calendar's only extra dates are those two emergencies.
- Bars: 15m, built from BTC 1m (BTC-Acum parquet), ETH 5m (the Coinbase pull already in `eth_names/data`, resampled; spot-checked against a fresh curl pull, 288 bars identical), SOL 15m (Coinbase fetch, starts 2021-06-17, so SOL dev is only 2021-06..2022-12).
- Decision at T uses only the bar that completes at T; entry and exit at the open of the bar starting at the stated time.
- Variants: FOMC 2 assets x 3 entries x 4 exits x 2 directions = **48**. Off-hours 3 assets x (9 signal families x 3 thresholds + 5 drift families) x 2 directions = **192**. Total **240** (120 unique up to the flip). Expect ~6 chance hits at |t| >= 2 among them.
- BTC check loses 2 FOMC events (2024-07-31, 2024-12-18) to gaps in the 1m file (no bars 13:45-16:15 ET); not imputed.

## Job 1: FOMC grid (with-direction bp (t) / flip bp)
Entry 14:30 / 14:45 / 15:00 ET; exits same day 16:00, next day 09:30, next day 16:00, day+2 16:00.

| BTC, window | D 16:00 | D+1 09:30 | D+1 16:00 | D+2 16:00 |
|---|---|---|---|---|
| 14:30 dev | -21 (-0.9) / +1 | +14 (+0.3) / -34 | +4 (+0.1) / -24 | +79 (+0.9) / -99 |
| 14:45 dev | -10 (-0.5) / -10 | +25 (+0.5) / -45 | +15 (+0.2) / -35 | +90 (+1.0) / -110 |
| 15:00 dev | -3 (-0.2) / -17 | +32 (+0.7) / -52 | +21 (+0.3) / -41 | +96 (+1.1) / -116 |
| 14:30 check | +32 (+1.0) / -52 | +83 (+1.9) / -103 | +88 (+1.9) / -108 | +109 (+1.9) / -129 |
| 14:45 check | +36 (+1.2) / -56 | +87 (+2.2) / -107 | +92 (+2.1) / -112 | +113 (+2.0) / -133 |
| 15:00 check | +22 (+0.9) / -42 | +73 (+2.0) / -93 | +77 (+1.8) / -97 | +99 (+1.8) / -119 |

| ETH, window | D 16:00 | D+1 09:30 | D+1 16:00 | D+2 16:00 |
|---|---|---|---|---|
| 14:30 dev | -4 (-0.1) / -16 | -6 (-0.1) / -14 | -82 (-1.0) / +62 | +11 (+0.1) / -31 |
| 14:45 dev | +6 (+0.2) / -26 | +2 (+0.0) / -22 | -74 (-0.9) / +54 | +20 (+0.2) / -40 |
| 15:00 dev | +9 (+0.5) / -29 | +5 (+0.1) / -25 | -70 (-0.9) / +50 | +24 (+0.2) / -44 |
| 14:30 check | -6 (-0.2) / -14 | +122 (+1.8) / -142 | +208 (+2.3) / -228 | +248 (+1.8) / -268 |
| 14:45 check | +7 (+0.3) / -27 | +136 (+2.2) / -156 | +223 (+2.6) / -243 | +261 (+2.0) / -281 |
| 15:00 check | +4 (+0.2) / -24 | +131 (+2.3) / -151 | +219 (+2.7) / -239 | +258 (+2.0) / -278 |

- Non-FOMC control (same rule, every other weekday, 14:30 entry, D+1 16:00): BTC dev +20 (t 1.7), check -0.3 (t 0.0), full +12; ETH dev +5, check -11, full -1. The control is positive in dev for BTC, so the FOMC dev effect is nil relative to it.
- Lead rule, BTC 14:30 -> next day 16:00, full: n 69, win 52%, +37 bp (t 0.85), avg win +297, avg loss -247. Dev n 42: avg win +358, avg loss -288. Check n 27: win 63%, avg win +228, avg loss -151. Flip in check -108 bp (t -2.3). Per-year BTC: 2017 +260(3), 2018 -102, 2019 -124, 2020 +10, 2021 +111, 2022 +30, 2023 +2, 2024 +187, 2025 +100, 2026 +87.
- Worst fills (buy at bar high, sell at bar low): BTC lead rule check drops from +88 to +4 bp; full from +37 to -45. The edge does not survive pessimistic fills.
- Entry-time sensitivity (14:30 vs 14:45 vs 15:00) barely matters; the sign is set at 14:30. Longer holds carry bigger means but the non-event control also rises with hold length (BTC D+2 control +15 bp full), so day+2 gains are mostly drift.

## Job 2: off-hours, threshold 0, with-direction net bp (t), n
Drift rows are unconditional long (no signal). Family definitions in `offhours_run.py`.

| family | BTC dev | BTC check | ETH dev | ETH check | SOL dev | SOL check |
|---|---|---|---|---|---|---|
| F1a weekend: sign(Fri16->Sun18), Sun18->Mon09:30 | +1 (0.0) n263 | +19 (+1.1) n179 | +8 (+0.3) n280 | +25 (+1.1) n189 | +106 (+1.6) n80 | +52 (+1.8) n189 |
| F1b weekend: sign(Fri16->Mon09:30), Mon09:30->16:00 | -22 (-1.6) | +5 (+0.3) | -31 (-1.8) | -7 (-0.3) | -30 (-0.7) | -26 (-1.1) |
| F1d weekend drift, long Fri16->Mon09:30 | +42 (+1.3) | +25 (+1.0) | +78 (+1.7) | +21 (+0.6) | -39 (-0.4) | +75 (+1.5) |
| F2a Sun17->18 sign, hold to 19:00 | -7 (-1.1) | -10 (-1.9) | -15 (-2.0) | -16 (-2.4) | -19 (-1.1) | -7 (-0.8) |
| F2b sign(Fri16->Sun18), hold to 19:00 | -7 (-1.2) | +10 (+1.8) | -7 (-1.0) | +11 (+1.7) | -3 (-0.2) | +14 (+1.5) |
| F2c sign(Sun18->18:30), 18:30->19:00 | -11 (-2.7) | -9 (-3.2) | -11 (-2.5) | -11 (-3.0) | -25 (-2.6) | -6 (-1.0) |
| F2d sign(Sun18->19), hold to Mon09:30 | -9 (-0.4) | -21 (-1.3) | -31 (-1.1) | +10 (+0.5) | +90 (+1.4) | -43 (-1.6) |
| F2d0 Sun18->19 drift, long | -9 (-1.5) | -1 (-0.2) | -18 (-2.4) | +3 (+0.4) | -26 (-1.6) | +4 (+0.4) |
| F3 Asia 20:00, sign(09:30->16:00), hold 1h | -11 (-4.3) | -10 (-5.4) | -8 (-2.7) | -6 (-2.8) | -5 (-0.6) | -9 (-2.4) |
| F3 Asia 20:00, same signal, hold 4h (to 00:00) | -2 (-0.4) | -11 (-3.8) | -2 (-0.4) | -10 (-2.7) | -2 (-0.2) | -6 (-1.2) |
| F3 Asia 20:00, same signal, hold 8h (to 04:00) | +5 (+0.9) | -7 (-2.0) | -1 (-0.1) | -6 (-1.3) | -1 (-0.1) | 0 (0.0) |
| F3d Asia 20:00 drift, long, hold 1h / 4h / 8h | -12 / -20 / -13 (dev t -4.9 / -4.3 / -2.2) | -8 / -9 / -11 | -11 / -21 / -15 | -8 / -7 / -8 | +3 / 0 / +10 | -3 / +4 / +8 |

- Asia and Sunday signals: gross (net + 10 bp) is about 0 bp in every cell, and the with and flip means sum to -20 bp, so the negative t-stats are cost, not direction. Asia after strong US moves (|move| >= 1% or 2%) does not separate from weak moves.
- Dev top 3 by t (dev n >= 30, dev mean > 0), signal rules only: ETH Asia 8h, |move| >= 2%, with (dev +25 bp, t 1.7, n 484) -> check -21 bp (t -1.9, n 271). BTC Asia 8h, |move| >= 2%, with (dev +22, t 1.7, n 363) -> check -12 (t -1.3, n 206). SOL weekend F1a, all, with (dev +106, t 1.6, n 80) -> check +52 (t 1.8, n 189).
- Overall top-3 including drift: ETH F1d weekend long (dev +78, t 1.7) -> check +22 (t 0.6); the two Asia rules above.
- Weekend drift diagnostic (gross, no cost): weekend Fri16->Mon09:30 vs Mon-Thu 16:00->09:30 overnight. BTC check +35 vs +18 bp; ETH +32 vs +22; SOL +85 vs +34. The flip of every weekend signal loses, so the weekend long is beta, not a signal.

## Candidate for follow-up (WEAK, not EDGE)
SOL weekend continuation F1a: buy Sun 18:00 ET if the Fri 16:00 -> Sun 18:00 move is positive (sell if negative), exit Mon 09:30 open, 10 bp RT. Check +52 bp (t 1.8, n 189). Only SOL, dev n 80, and BTC/ETH on the same rule show dev about 0 and check +19 / +25 (t about 1.1). Needs an out-of-sample run after 2026-08-10, which the sealed holdout does not give.
