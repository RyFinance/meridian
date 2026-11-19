# Premium-momentum validation result (2023-01-01 .. 2026-08-10): FAILED

Pre-registered candidates and pass criteria: `CANDIDATES.md`. Validation trades: `val_M1.csv`, `val_M2.csv`.
Scorer: `score_val.py` (net_stress2x = gross - 2*(cost+carry) = 2*net_base - gross).
One trade dropped for a BTC open data gap (btc_open NaN on 2023-03-24); it does not change the conclusion.

## M1 (L=40, Z=1.0, H=5)
- dev (2020-08..2022-12): n=45, +308 bp/trade, t 2.20 (the frozen rule)
- validation: n=88, win 0.48, mean **-29.6 bp**, t **-0.35**; 2x stress: -66.7 bp, t -0.78
- per-year net: 2023 **-22.0%**, 2024 **-40.9%**, 2025 +40.2%, 2026 -3.3%  (two years < -20% -> FAIL)

## M2 (L=40, Z=1.5, H=10)
- dev: n=25, +392 bp/trade, t 1.60
- validation: n=41, win 0.46, mean **+91.4 bp**, t **0.52**; 2x stress: +39.9 bp, t 0.23
- per-year net: 2023 **-43.5%**, 2024 +47.1%, 2025 +16.8%, 2026 +17.1%  (2023 < -20% -> FAIL)

## Verdict
Both fail the pre-registered gate (need net mean > 0 base and stressed, one-sided t >= 1.96, no year < -20%).
M1 is plainly negative; M2 is positive-but-insignificant and carried entirely by 2024+2025 with a -44% year in 2023.
The 2020-22 "71% of momentum variants positive" pattern does not survive 2023-26. Premium momentum (regression-proxy residual) is dead as specified.
Do not re-run variants of this on the same panel and call it validation.
