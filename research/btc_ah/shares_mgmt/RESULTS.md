# MSTR shares: trade management on the BTC 16:00->09:25 ET move

Question: can stops, targets, trailing, scale-outs, time exits and confirmation entries turn a MSTR share day-trade keyed on BTC's off-hours move into a positive-expectancy rule net of 3 bp/side?

**Verdict: NONE.** The dev edge in the top rules does not survive the check half, and in the best cases the flipped direction makes money too. The dev profit comes from intraday reversal after a 1% excursion, not from BTC.

## Setup
- Dev: stock_1m_dev RTH, 2020-08-12..2023-12-31, 788 usable days. Check: mstr_stock_1m_lse RTH, 2026-04-29..2026-08-10, 57 days. Nothing after 2026-08-10 was loaded. 2024-01..2026-04-28 is unused (no MSTR data loaded for it).
- BTC: polymarket 1m, bar label = bar open, UTC converted to ET. Signal = close(09:24 bar) / close(15:59 bar of previous weekday) - 1, known at 09:25.
- Gap beta fitted on dev only: MSTR (09:30 open / prior 15:59 close - 1) on BTC move = 0.892.
- Costs: 3 bp per side, 6 bp round trip per share. Worst-fill stress: buy at bar high, sell at bar low.
- Fills: next-bar open for market entries. Stops are checked before targets within a bar. Gap-throughs fill at the open.
- Code: `research/btc_ah/shares_mgmt/sim.py` (grid), `top3.py` (stress and per-year). Outputs: `base_grid.csv`, `filter_grid.csv`, `all_results.csv`.

## Variants tested
- Direction (3): with BTC; against BTC; conv = trade toward beta*BTC (overshoot -> short, undershoot -> long).
- Entry (6): 09:31; 5-min OR break; 15-min OR break; pullback 0.5% then next-bar open; pullback 1.0%; 10:01 gated on BTC 09:30-10:00 agreeing.
- Exit (17): fixed SL/TP (6 pairs, 0.5-3%); ATR SL/TP (2); trail 1%, 2% (2); half off at +1R with trail 1% or 2% (2); time stop 10:30, 12:00, 16:00 (3); break-even at +0.5% or +1% with SL 1% / TP 2% (2).
- Base grid: 3 x 6 x 17 = **306 rules**.
- Filters: top 10 base rules by dev t (n>=50) x 9 filters (|BTC| quartiles, weekday) = **90 rules**.
- Total tested: **396**. The flip control was computed for every rule (396 more runs, not counted as tests).

## Top 3 by dev t (n>=50), with check and flip
| Rule | Dev n | Dev WR | Dev mean (bp) | Dev t | Check n | Check WR | Check mean (bp) | Check t | Flip dev mean / t | Flip check mean / t |
|---|---|---|---|---|---|---|---|---|---|---|
| conv \| PB 1% \| time 10:30 | 502 | 59% | +49.5 | 4.42 | 37 | 54% | -3.3 | -0.09 | +23.0 / 2.18 | +70.1 / 2.48 |
| with \| PB 1% \| time 10:30 | 564 | 57% | +37.0 | 3.54 | 42 | 69% | +45.0 | 1.59 | +32.0 / 2.93 | +26.7 / 0.96 |
| with \| PB 1% \| time 10:30 \| Tue | 121 | 65% | +83.9 | 3.46 | 7 | 86% | +140.7 | 2.53 | +38.0 / 1.65 | +53.8 / 1.18 |

Avg win / avg loss (dev, bp): rule 1 +199 / -169; rule 2 +194 / -175; rule 3 +218 / -169.
Worst-fill stress, dev/check mean: rule 1 +19 / -29; rule 2 +9 / +19; rule 3 +53 / +106.
Per-year dev means (bp), rule 1: 2020 +53, 2021 +31, 2022 +47, 2023 +70. Check is a single year, 2026.

## Flip control
- Flip makes money for all three top rules, so the signal is not BTC-directional. For PB rules, with and against are nearly identical (dev +37 vs +32). BTC direction adds about 5 bp.
- The with/against pair is mirror images by construction, so its flip control is not independent. The conv flip is the divergence trade.
- Across the 306 base rules, 12 of 111 with positive dev mean also have a positive flipped dev mean.

## Other results
- Best rule whose flip is negative: conv \| E0931 \| time 12:00 \| Fri. Dev n 151, WR 60%, mean +92 bp, t 3.41; flip -104 bp, t -3.86. Check n 12, mean +104 bp, t 1.04. Worst-fill dev t 2.02. This is one weekday cell chosen from 5, so its p-value after Bonferroni over 396 tests is about 0.3.
- Baseline with \| 09:31 \| 16:00 exit: dev +25 bp, t 1.48, flip -37. Check +56 bp, t 1.21.
- Exit families (17 families, 18 rules each): median dev mean ranges from -5 bp (trail 1%) to +16 bp (ATR 1/2 and 16:00 time); the median check mean is negative for all 17. Check t < -2 for 28 of 306 base rules; check t > 2 for 2.
- Dev-to-check decay is large for every family. Rules with dev t > 3 (5 of 306): 2 have check mean > 0, none have check t > 2.
- Win rate is not the test. The high-WR PB time-exit rules (about 55-65% WR) have avg win 194-218 bp against avg loss 169-175 bp, and their check means are near zero.

## Verdict
NONE. No rule has a positive, t > 2 check result and a negative flip. The best dev rules are intraday mean-reversion after a 1% dip or rip (flip-positive), and the dev-check gap is large. The one flip-negative rule is a single-weekday, n=12 check cell. Do not trade it. A next step would be a forward test of the conv|E0931|time12:00 idea, not further tuning on dev.
