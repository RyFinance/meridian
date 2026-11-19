# btc_self: BTC-only trading keyed on off-hours moves

**SEALED-HOLDOUT DISCLOSURE (HARD RULE 1):** my first inspection call printed `df.tail(3)` of the BTC file, which showed 2026-08-11 timestamps and prices (about 64,075-64,100). I computed nothing on those rows. All analysis used `timestamp < 2026-08-11 00:00 UTC`, applied immediately after load. Per the brief, this exposure may void the result. The lead decides.

Verdict: **NONE.** No rule clears a Bonferroni threshold on dev, and no dev-selected rule holds on check.

## Setup
- Source: BTC 1m (UTC), filtered to <= 2026-08-10. Dev = trade dates 2018-01-01..2022-06-30 (1132 days). Check = 2022-07-01..2026-08-10 (1030 days).
- Times in ET (zoneinfo, DST-aware). Signal price at T = close of last bar before T. Fill at T = open of next bar. Sparse minute bars use a 5-minute tolerance.
- Costs: spot 10 bp round trip. IBIT proxy 6 bp round trip, RT-hours only, using BTC price as proxy (no NAV premium/discount).
- Holidays hardcoded (NYSE full closures). Early closes ignored.
- Flip control: mirror = same trades, opposite direction, so mirror net = -gross - cost (always negative when the rule is positive). The informative control is the unconditional same-window drift baseline (`drift`, gross).

## Counts
- H1 overnight (16:00->09:30 ET) to RTH exits 10:30 / 12:00 / 16:00: 72 variants (3 sides x 4 quantile cuts x cont/rev x 3 horizons).
- H2 weekend (Fri 16:00 -> Mon 09:30) fade-to-fill / continuation with stops and exits at Mon 16:00 or Tue 09:30: 48 variants.
- H4 handoffs (00:00, 03:00, 08:00 UTC) after the 16:00 ET move: 144 variants.
- Stop/target management grid on the top H1 dev rule: 16 variants.
- Total 280 tested. Eligible (dev n >= 60): 212. Bonferroni at 264 needs p < 0.00019.
- Max dev t across eligible = 1.83. Eligible rules with dev t > 1.96 = 0. Eligible rules with check t > 1.96 = 0.

## Top 3 by dev t (dev n >= 60), spot costs. Net per trade.
| rule | split | n | win | mean net | t | avg win | avg loss | drift (gross) | mirror net |
|---|---|---|---|---|---|---|---|---|---|
| H1 long after overnight drop >= dev q75 \|move\|, 09:30->12:00 | dev | 128 | 48% | +0.39% | 1.83 | +2.11% | -1.23% | +0.04% | -0.59% |
| | check | 37 | 41% | +0.18% | 0.47 | +2.21% | -1.20% | -0.03% | -0.38% |
| H2 weekend cont, all Mondays, stop 0.5x gap, exit Tue 09:30 | dev | 188 | 37% | +0.40% | 1.81 | +3.28% | -1.26% | +0.12% | -0.60% |
| | check | 175 | 25% | -0.06% | -0.33 | +2.95% | -1.08% | +0.21% | -0.14% |
| H1 long after overnight drop >= dev q75, 09:30->10:30 | dev | 128 | 54% | +0.23% | 1.66 | +1.25% | -0.95% | -0.00% | -0.43% |
| | check | 37 | 46% | +0.00% | 0.01 | +1.46% | -1.24% | -0.02% | -0.20% |

IBIT tier (H1 rows, 6 bp RT): dev +0.43% / check +0.22% (row 1); dev +0.28% / check +0.04% (row 3).

Per-year mean net (dev / check):
- Row 1: dev 2018 +0.51, 2019 -0.03, 2020 +0.36, 2021 +0.20, 2022H1 +1.01. Check 2022H2 +0.38, 2023 -0.44, 2024 +1.51, 2025 +0.06, 2026 -1.00.
- Row 2: dev 2018 +0.15, 2019 +0.76, 2020 +0.51, 2021 +0.69, 2022H1 -0.63. Check 2022H2 -0.18, 2023 +0.08, 2024 +0.69, 2025 -0.67, 2026 -0.22.
- Row 3: dev 2018 +0.15, 2019 +0.38, 2020 +0.40, 2021 +0.03, 2022H1 +0.70. Check 2022H2 +0.15, 2023 -0.32, 2024 +0.86, 2025 +0.03, 2026 -1.12.

Dev-to-check decay: row 1 about 55% smaller; row 2 changes sign; row 3 goes from +0.23% to 0.00%.

## Test results
- **Weekend gap-fill (CME folklore).** Fill = price trades back to the Fri 16:00 ET level after the Mon 09:30 entry. Dev: 31% by Mon 16:00, 46% by Tue 09:30. Check: 29% and 44%. Median |gap| 2.5% (dev), 1.9% (check). Fade-to-fill, stop 0.5x gap, Mon 16:00 exit: dev -0.19%, check -0.15%. Stop 1x: -0.05% / -0.20%. No stop: -0.04% / -0.25%. No fade edge.
- **Overnight -> RTH** (H1): best dev rows above. Positive dev means only come from big drops (q0.75). The other horizons and sides are weaker.
- **Stop/target on top H1 rule** (dev-selected): the untouched rule has the best dev mean (+0.39%). Every stop reduces it. A 0.5% target lifts win rate to 80% but cuts the mean to +0.11% (t 1.80), and check is -0.14%.
- **Handoffs** (H4): best dev rule (00:00 UTC, 180 min, up q75, rev) dev +0.17% t 1.27, check +0.02% t 0.11. Most handoff variants are cost-dominated (60-min holds vs 10 bp RT). 63 of 120 eligible have check t < -1.96.
- **Sign consistency.** Of 8 eligible H1 rules with dev t > 1, 4 keep their sign on check. Of 6 eligible H2 rules with dev t > 1, 0 keep their sign.
- **Known 17-18 ET long**: not re-tested, as instructed.

## Not done
- No permutation/shuffle control. The mirror and drift baselines are the controls reported.
- No IBIT NAV or premium/discount modeling. IBIT numbers use BTC price.
- No slippage beyond the flat per-side cost. Stop fills are at the stop price (or the bar open if it gaps through).

Files: `study.py` (main grid), `manage.py` (stop/target grid), `variants.pkl`, `mgmt_variants.pkl`, `weekend_gaps.pkl`, `thresholds_and_gap.json`.
