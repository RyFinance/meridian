# Round 6: NG=F / CL=F overnight → gas producers, LNG, shippers, oil services (09:30→10:30)

Files: `fetch.py` (yfinance pull, 2026-10-18), `gas_test.py` (main; log `run_log.txt`, table `gas_results.csv`), `gas_extra.py` (pooled + SPY-hedged; log `extra_log.txt`).

## Setup
- Signal: d = sign(log(FUT 60m close of 08:00 bar on D / close of 15:00 bar on prev session)). Start-labeled; known before 09:00.
- Entry: daily Open (MOO). Exits: 09:30-bar close (10:30), 10:30-bar close (11:30), daily close.
- Costs: 2 bp/side if median 60d $ADV >= $300M, 5 bp if $20M–300M, 10 bp if < $20M (my cutoffs). Round trip = 2 sides.
- Dev 2024-05-28..2025-06-30 (~250–270 days). Check 2025-07-01..2026-10-16 (~305–320 days).
- Data gaps: CTRA, CHK, SWN, TELL, CIVI returned no data. EXE 60m starts 2024-10-02 (dev only 170–185 days).
- NFE excluded: 60m prices ~50x the daily series around 2025-05-15, and the daily series alternates between ~0.33 and ~16 in 2026 (split-type breaks).
- Integrity check: drop days where the 09:30 bar open is more than 20% off the daily open. Affects no retained ticker.

## Key results (net bp per trade; t in parentheses)
| Rule (signal → name, exit) | cost | Dev | Check | Check hit | Flip check (-d) |
|---|---|---|---|---|---|
| NG → EQT, 11:30 (dev pick) | 2 | +13.9 (1.42) | +11.8 (1.39) | 0.50 | -19.8 (-2.33) |
| NG → EQT, 10:30 | 2 | +5.0 (0.57) | +15.4 (2.03) | 0.55 | -23.4 (-3.09) |
| NG → EXE, 10:30 | 2 | +8.5 (1.01) | +18.4 (2.64) | 0.57 | -26.4 (-3.78) |
| NG → EXE, 11:30 | 2 | +9.6 (1.04) | +16.5 (2.11) | 0.54 | -24.5 (-3.13) |
| NG → LNG, 10:30 | 2 | +6.3 (0.89) | +11.7 (1.77) | 0.55 | -19.7 (-2.98) |
| NG → FCG, 11:30 | 10 | -17.9 (-2.35) | -12.9 (-2.08) | 0.45 | -27.1 (-4.36) |
| CL → XOP, 10:30 | 2 | +1.4 (0.20) | -4.2 (-0.70) | 0.48 | -3.8 (-0.64) |
| CL → FRO, 10:30 | 5 | -27.4 (-3.05) | -15.5 (-1.71) | 0.47 | -4.5 (-0.49) |
| CL → XLE, close | 2 | -14.5 (-1.71) | -8.1 (-1.33) | 0.46 | +0.1 (0.02) |

Pooled, equal-weight across names (gas: NG signal, 9 names; oil: CL signal, 11 names):
- Gas, 10:30: dev -1.4 (t -0.29), check +3.9 (t 0.85).
- Gas, 11:30: dev +0.6 (t 0.10), check +0.9 (t 0.17).
- Oil, 10:30: dev -6.4 (t -0.91), check -9.2 (t -1.57).

## Controls
- **Flip (-d):** shown in the table. It mirrors the main trade, so it confirms direction but is not independent evidence.
- **SPY placebo:** NG signal gives -6.6 bp (dev t -2.5) and -6.0 bp (check t -3.2) at 10:30; CL gives -6.5 bp and -6.1 bp. The overnight energy move is priced negatively in SPY's first hour, so long-only energy rules carry market beta.
- **SPY-hedged (target minus SPY, both legs costed):** EQT 11:30 +10.7 bp (check t 1.25); EXE 10:30 +15.5 bp (check t 2.16); EXE 11:30 +15.1 bp (check t 1.87); LNG 10:30 +9.2 bp (check t 1.32); XLE/XOP -6 to -8 bp.
- **Wrong-signal:** CL → gas names and NG → oil names. 0 of 60 rows have positive check |t| > 2 (3 rows have check t < -2), so no cross-talk edge.

## Variants and multiple testing
- 126 rows in `gas_results.csv`: 60 primary (20 names × 3 exits), 60 wrong-signal, 6 SPY placebo. Pooled (6) and hedged (7) checks are separate.
- Best rule by dev only: positive-mean rule with the highest dev t = NG → EQT, 11:30 (dev t 1.42).
- No primary rule reaches dev t ≥ 2. Two-sided Bonferroni threshold for 60 tests is |t| ≈ 3.3.
- Three primary rules have check t ≥ 2 (EQT 10:30, EXE 10:30, EXE 11:30), but none was selected on dev. With 60 variants that is about what chance produces.

## Best rule, stated precisely
d = sign(log(NG=F 08:00-bar close / prior-session 15:00-bar close)). If d = +1, buy the name at the 09:30 open (MOO) and sell at the 10:30 bar close, costing 4 bp round trip. EQT: dev +13.9 bp (t 1.42, n 248); check +11.8 bp (t 1.39, n 313, hit 50%). No look-ahead.

## Verdict: NONE (family); best single names WEAK
- The hypothesis fails as a family: pooled gas and oil are about zero in both windows.
- EXE (10:30) and EQT are the only single names with positive sign in both windows and check t near 2. Hedged against SPY they fall to t 1.3–2.2, and they do not survive the multiple-test threshold.
- Gas and oil edges are much weaker than the homebuilder ZB result (+22 bp). Not tradable as-is.
