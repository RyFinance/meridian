# MSTR open reversal (09:30 open, fade a 1% excursion, exit 10:00-12:00)

**Verdict: NONE.** The lead's +37 to +50 bp edge comes from a timing bug in `shares_mgmt/sim.py`. With the bug fixed, the direction-neutral and BTC-conditioned rules are flat out of sample, and their flips are as good as the originals.

## Bug in prior sim (affects its time-exit results)
- For `time` exits, `sim_exit` returns the open of the exit minute even when the entry is after it. Those trades exit before they enter.
- Prior `with|PB1%|time10:30` (dev +37.0 bp, n 564): 96 trades enter after 10:30 and carry a mean of +207 bp. The valid 468 trades average +2.1 bp.
- `against`: valid -2.9 bp (n 498). `conv`: valid +14.2 bp (n 416), invalid +220 bp. The same pattern holds for 12:00 exits.
- The prior `with`/`against` symmetry (+37/+32) is produced by this artifact, not by a direction-neutral edge.
- Reproduced via read-only import of `sim.py`: `xcheck_bug.py`, `xcheck_dates.py`, `xcheck_prior.py`.

## Step 1: 2020-08-12..2023-12-29, MSTR RTH minutes, 3 bp/side
- Rules: 2 families x X {0.5,1,1.5,2%} x exit {10:00,10:30,11:00,12:00} x stop {none,1%,2%} = **96 rules**, each run with base and worst fills (worst = bar high on buys, bar low on sells). Flip controls: 96 more, not counted.
- DN = fade the first 1% excursion, either side. BC = wait only for the move against BTC's 16:00->09:25 direction, trade with BTC.
- Dev = <= 2022-06-30 (451 days, used for the pick). Check = 2022-07-01..2023-12-31 (376 days).
- Base rules with dev > 0 and check > 0: 17 of 96. Dev t > 2: 0 of 96. Best check t over all rules: 2.43 (not the dev pick).
- Worst fills: dev mean > 0 for 0 of 96 rules.

| Frozen rule (picked on dev) | Dev n | Dev bp | Dev t | Check n | Check bp | Check t | All bp |
|---|---|---|---|---|---|---|---|
| DN: X 0.5%, exit 10:00, stop 1% | 444 | +8.9 | 1.13 | 375 | -10.4 | -1.42 | +0.1 |
| DN flip (momentum) | 444 | -9.4 | -1.16 | 375 | -22.1 | -3.27 | -15.2 |
| BC: X 1%, exit 10:00, no stop | 245 | +12.0 | 0.88 | 196 | +12.0 | 0.95 | +12.0 |
| BC flip | 245 | -24.0 | -1.75 | 196 | -24.0 | -1.91 | -24.0 |

Worst fills, frozen rules: DN -64 bp dev / -72 bp check. BC -45 bp dev / -44 bp check.
Per-year (base, all of 2020-2023): DN +23, +14, -10, -11 (2020-23). BC +94, +9, -5, +18.

## Step 2: out of sample, frozen before this step (FROZEN.md)
Parity spot (`val_days_full.pkl`, Mon/Fri only, dropped after 2026-08-10), 8 bp/side (3 base + 5 extra). Bars built from consecutive spot points; base uses open = prior point, worst uses max/min.

| Sample / rule | n | Win | Mean bp | t | Avg win / loss bp | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|
| DN frozen, base | 233 | 39% | -4.5 | -0.48 | +146 / -101 | -15 (77) | +0 (98) | +1 (58) |
| DN frozen, worst | 233 | 32% | -40.7 | -4.37 | +133 / -123 | -50 | -37 | -35 |
| DN flip, base | 233 | 37% | +5.9 | 0.49 | +179 / -97 | +57 | -34 | +5 |
| DN flip, worst | 233 | 30% | -44.5 | -4.46 | +146 / -125 | | | |
| BC frozen, base | 114 | 48% | -11.8 | -0.56 | +135 / -148 | -19 (42) | +3 (43) | -24 (29) |
| BC frozen, worst | 114 | 43% | -43.0 | -1.98 | +116 / -163 | | | |
| BC flip, base | 114 | 46% | -20.2 | -0.97 | +135 / -150 | -13 | -35 | -9 |
| BC flip, worst | 114 | 40% | -51.9 | -2.56 | +121 / -165 | | | |

Sensitivity, 3 bp/side on the same spot path (Mon/Fri): DN base +5.5 (t 0.57), BC base -1.8 (t -0.09).

Real stock minutes, 2026-04-29..08-10, 3 bp/side (cross-check):
- DN Mon/Fri, n 24: base +20.8 bp (t 0.56), worst -70.3 (t -2.89). Flip base -47.4 (t -2.01).
- DN all weekdays, n 61: base +8.1 (t 0.37), worst -66.4 (t -4.09).
- BC Mon/Fri, n 12: base -60.3 (t -1.33). BC all weekdays, n 30: base -37.2 (t -1.03).
- Parity spot on the same 2026 days (Mon/Fri, n 27, 8 bp): DN base +10.2 bp. Roughly consistent with the real-bar result, but n is tiny.

## Notes
- Step-2 DN and BC are both flat on base fills. Their flips are no worse, so there is no BTC-direction signal and no reversal signal.
- The worst-fill penalty (about 60 bp per round trip) is the brief's bar-extreme definition. It is harsh for limit orders, but it is not what decides the verdict: base fills are already flat or negative.
- Parity-spot noise is unmeasured. Stops are approximated from consecutive spot points, and that may change stop results.
- Holdout: no price after 2026-08-10 was loaded or used. `_sealed/` was not touched.

## Files (this folder)
core.py (rule engine), step1.py / step1_summary.csv / step1_trades.pkl, FROZEN.md, step2.py / step2_results.csv, xcheck_*.py (prior-bug diagnostics).
