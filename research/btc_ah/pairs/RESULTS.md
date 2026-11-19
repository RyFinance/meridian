# Market-neutral open-gap pairs: stock vs BTC ETF (BITO / IBIT)

**Verdict: WEAK.** No rule survives dev-to-check with a consistent sign and t > 2. The best dev-selected rule (COIN, 2-day hold) decays from +157 bp to +47 bp. The MSTR open-to-next-open rule holds in check but has n = 28 and fails the 10:30 entry test.

## Setup (as built, `pairs_gap.py`)
- Signal at the 09:30 open: gap_s = open_t / close_{t-1} - 1. Residual = gap_s - beta * gap_ref.
- Beta: OLS slope of stock gap on ref gap, 120 rows, min 60, window ends at t-1 (past only).
- Ref leg: BITO before 2024-01-12, IBIT from 2024-01-12 (gap spliced per day). Only tradable hedges are used.
- Rule: |residual| > X. Reversion = short the rich leg, buy the other, beta-weighted (short $1 stock, long $beta ETF).
- Exits: C0 = close same day; O1 = open next day; C3 = close after 3 sessions.
- Costs: 3 bp per execution, 4 per round trip. Per $1 stock leg: 6(1+beta) bp. At beta 1 that is 12 bp.
- Dev = entries to 2024-06-30. Check = 2024-07-01 to 2026-08-10. Holdout cut applied on load.
- Effective sample starts 2022-01 (beta warm-up). Universe: MSTR, COIN, MARA, equal-weight miner basket (RIOT, CLSK, HUT, WULF, IREN, CIFR, BTBT).

## Variant count
- Searched: 4 names x 4 thresholds (X = 1, 2, 3, 5%) x 3 exits = **48 reversion variants**. Selection used dev only, with n >= 30 (36 eligible).
- Flip (momentum) controls: the same 48 with sign reversed. These are not searched.
- Sensitivities (check only): 10:30-bar entry (3 cases), borrow fee (3 levels).

## Top 3 by dev t (n >= 30), with check, flip, and per-year
| Rule | Dev n | Dev win | Dev net bp (t) | Chk n | Chk win | Chk net bp (t) | Flip dev / chk bp |
|---|---|---|---|---|---|---|---|
| COIN C3, X=2% | 130 | 55% | +157 (1.64) | 79 | 53% | +47 (0.47) | -179 / -70 |
| MSTR O1, X=3% | 42 | 52% | +175 (1.48) | 28 | 75% | +198 (1.74) | -199 / -224 |
| COIN O1, X=3% | 61 | 59% | +142 (1.36) | 32 | 47% | -101 (-1.07) | -164 / +77 |

Per-year net bp (n) across dev and check, from entries:
- COIN C3 X2%: 2022 +251 (61), 2023 -2 (48), 2024 +158 (40), 2025 +19 (39), 2026 +86 (21)
- MSTR O1 X3%: 2022 +323 (23), 2023 -4 (3), 2024 +90 (30), 2025 +312 (4), 2026 +149 (10)
- COIN O1 X3%: 2022 +245 (36), 2023 +78 (16), 2024 -28 (19), 2025 -193 (15), 2026 -169 (7)Avg win / loss, check (bp): COIN C3 +579/-558; MSTR O1 +391/-384; COIN O1 +322/-474.

## All 48 reversion variants (summary)
- Dev mean of means: +68 bp. Check mean: -17 bp. Dev-check correlation of means: -0.3.
- Positive in both halves: 16 of 48. Dev > 0: 32. Check > 0: 26.
- Check t > 2: MSTR C0 X3% (n 28, +228 bp), MSTR O1 X5% (n 5), MARA C0 X1% (n 231, +57 bp, but dev -2 bp).
- Basket (MINERS) and MARA show no dev-supported edge. Best MINERS dev cell fails check.

## Flip (momentum) control
- Flip dev > 0 in 9 of 48 cells. Check > 0 in 19 of 48. Both halves > 0 in 3 of 48.
- Flip top-3 cells are negative in dev, so the reversion direction is not drift. COIN O1 X3% flip is +77 in check. Flip check t > 2 is COIN X5% only (n 4 to 20).

## Entry-price sensitivity (60m data, check only, entries 2024-10 to 2026-08)
- Entry at the 10:30 bar open, not the 09:30 print:
  - COIN C3 X2%: +64 bp, t 0.61, n 70
  - MSTR O1 X3%: +87 bp, t 1.00, n 22
  - COIN O1 X3%: -82 bp, t -1.05, n 27
- The 09:30 print is not a realistic fill for a decision made at 09:30. The MSTR result halves and loses significance under the next-bar entry.

## Borrow-fee caveat (short stock leg)
- Stock-short fee at 0%, 5%, 20% per year: changes net by less than 10 bp per trade for these holds.
- Hard-to-borrow miners (WULF, IREN, CIFR, BTBT, CLSK) can carry 20% to 100%+ fees or be unavailable. Not tested per name.
- ETF-leg short borrow assumed 0.25%. The basket result is weak regardless.

## Caveats
- BTC-1m reference for 2020-2021 not used: no tradable hedge exists there, as the brief notes.
- Daily-bar model. No intraday fills, no worst-fill test. 3 bp per execution assumed.
- t-stats treat overlapping daily trades as independent, which overstates them for O1 and C3.
- Holdout: all loads cut at <= 2026-08-10. The 60m files were filtered to < 2026-08-11 right after load, before use.
- Disclosure: a first run had an inverted position sign, fixed before any selection. Numbers are from the fixed run (`variants.csv`, `pairs_gap.py`, `sens.py`).
