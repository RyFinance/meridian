# Cycle 6 feasibility (FRAMEWORK §1) — data availability only

Written 2026-09-26 by the FREEZE+SPEC agent after freezing snapshot `cycle6_eval_v1`
(manifest SHA-256 `ba67379be094135e32557468710a078ea9ac6f0d87516fef331e7788b22d29be`), before any
signal-conditioned, strategy, control or portfolio return. Counts were produced by
`python -m research.cycle6.feasibility_counts <view>` (research/cycle6/feasibility_counts.py; JSON in
research/cycle6/feasibility_counts.json) reading only the frozen view, using only non-missing masks and
observation counts (no return, signal, volatility or beta value). Identical output from the mutable
`data/cycle6/eval` tree and from the frozen view.

Rule: feasible iff the class portfolio is defined (≥ 3 eligible instruments for TSMOM, ≥ 4 for rank styles) on
**≥ 120 monthly dates** after each style's warm-up AND every spec input exists in the snapshot. Eligibility mirrors
the engine (see module docstring). BAB's `beta > 0` condition and exact-zero signals are value conditions and are not
evaluated here (both can only remove instruments on individual dates).

| Component | min N | Warm-up | Defined months | First | Max N | Defined post-pub | Inputs (all present in snapshot) | Fidelity data note | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| TSMOM-EQ | 3 | 756 daily obs + 12 monthly returns | 331 | 1999-03 | 34 | 189 | daily excess panel; AQR TSMOM class column | benchmark overlap 326 m | **feasible** |
| TSMOM-FI | 3 | 756 daily obs + 12 monthly returns | 403 | 1993-03 | 12 | 189 | daily excess panel; AQR TSMOM class column | benchmark overlap 398 m | **feasible** |
| TSMOM-FX | 3 | 756 daily obs + 12 monthly returns | 620 | 1975-02 | 9 | 189 | daily excess panel; AQR TSMOM class column | benchmark overlap 497 m | **feasible** |
| TSMOM-CM | 3 | 756 daily obs + 12 monthly returns | 227 | 2007-11 | 12 | 189 | daily excess panel; AQR TSMOM class column | benchmark overlap 222 m | **feasible** |
| XSMOM-EQ | 4 | 12/1 window (11 months) | 356 | 1997-02 | 34 | 210 | daily excess panel; AQR VME MOMLS class column | benchmark overlap 335 m | **feasible** |
| XSMOM-FI | 4 | 12/1 window (11 months) | 384 | 1994-10 | 12 | 210 | daily excess panel; AQR VME MOMLS class column | benchmark overlap 363 m | **feasible** |
| XSMOM-FX | 4 | 12/1 window (11 months) | 615 | 1975-07 | 9 | 210 | daily excess panel; AQR VME MOMLS class column | benchmark overlap 553 m | **feasible** |
| XSMOM-CM | 4 | 12/1 window (11 months) | 234 | 2007-04 | 12 | 210 | daily excess panel; AQR VME MOMLS class column | benchmark overlap 213 m | **feasible** |
| VAL-EQ | 4 | 66 months | 301 | 2001-09 | 34 | 210 | daily excess panel (level = cumulative excess index); AQR VALLS_VME_EQ | benchmark overlap 280 m | **feasible** |
| VAL-FI | 4 | 60 months yield | 335 | 1998-11 | 12 | 210 | 10y month-end yields; AQR VALLS_VME_FI | benchmark overlap 314 m | **feasible** |
| VAL-FX | 4 | 66 months spot+CPI | 560 | 1980-02 | 9 | 210 | spot, PIT foreign CPI, PIT US CPI; AQR VALLS_VME_FX | benchmark overlap 539 m | **feasible** |
| VAL-CM | 4 | 66 months | 179 | 2011-11 | 12 | 179 | daily excess panel (level = cumulative excess index); AQR VALLS_VME_COM | benchmark overlap 158 m | **feasible** |
| CARRY-FI | 4 | none (carry at t) | 395 | 1993-11 | 12 | 157 | 10y carry (y−rf+roll-down); KMVP T2 row; Century FI carry | paper coverage 0.651 (<0.95) | **feasible** |
| CARRY-FX | 4 | none (rates at t) | 626 | 1974-08 | 9 | 157 | foreign + US 3m rates; KMVP T2 row; Century FX carry | paper coverage 1.000 | **feasible** |
| CARRY-CM | 4 | — | 0 | — | 2 | — | energy curve inputs (WTI, NATGAS only) | — | **infeasible** — 2 energy instruments < 4-asset rank floor (ADDENDUM-1 item 6) |
| BAB-EQ | 4 | 120/252 d vol, 750/1260 d corr | 329 | 1999-05 | 33 | 189 | daily EQ panel; EW EQ benchmark; Century EQ Defensive | benchmark overlap 321 m | **feasible** |
| BAB-FI | 4 | 12m vol (12 obs), 60m corr (36 obs), monthly | 561 | 1980-01 | 4 | 189 | monthly US buckets 2/5/10/30y; EW-universe benchmark (engine); FP Table VI row | paper coverage 0.534 (<0.95) | **feasible** |
| SEAS-EQ | 4 | ≥1 same-month obs in 20y; 12 of 36m sizing vol; 12m class-vol history | 344 | 1998-02 | 34 | 141 | daily excess panel; BSV Table II Sharpe | paper coverage 0.446 (<0.95) | **feasible** |
| SEAS-FI | 4 | ≥1 same-month obs in 20y; 12 of 36m sizing vol; 12m class-vol history | 372 | 1995-10 | 12 | 92 | daily excess panel; BSV Table II Sharpe | paper coverage 0.522 (<0.95) | **feasible** |
| SEAS-FX | 4 | ≥1 same-month obs in 20y; 12 of 36m sizing vol; 12m class-vol history | 603 | 1976-07 | 9 | 92 | daily excess panel; BSV Table II Sharpe | paper coverage 1.000 | **feasible** |
| SEAS-CM | 4 | ≥1 same-month obs in 20y; 12 of 36m sizing vol; 12m class-vol history | 222 | 2008-04 | 12 | 141 | daily excess panel; BSV Table II Sharpe | paper coverage 0.118 (<0.95) | **feasible** |

**Result: 20 feasible, 1 infeasible (CARRY-CM). k = 20.**

Fidelity data notes are information from dates only (no values): "benchmark overlap" = months on which the class
portfolio would hold positions and the AQR column has a value (AQR-class tier needs n ≥ 60); "paper coverage" =
share of the paper sample's months on which the class portfolio would hold positions (paper-stat tier needs ≥ 0.95).
By FRAMEWORK §5 an unassessable fidelity is **fidelity FAIL**; on coverage alone that is foreseeable for CARRY-FI
(KMVP 1983-11..2012-09: only 4 of our 10y markets from 1993-11), BAB-FI (FP Table VI from 1952), SEAS-EQ, SEAS-FI and
SEAS-CM (BSV 1981..2011). These components remain feasible and are run once (FRAMEWORK §1: nothing dropped on
performance or on foreseeable fidelity); they cannot become POSITIVE or enter the book unless fidelity passes.
AQR VME class columns (XSMOM/VAL benchmarks) end 2025-01 in the frozen file.

**Update 2026-09-26 (director decisions, engine e9cec9f0…):** SEAS rows recounted for the BSV construction
(min_years 1, 36-month sizing vol with 12-month minimum, 120-month strategy-realised class vol with 12-month minimum);
BAB-FI recounted for FP's monthly method (12/60-month windows, 12/36 minimum obs). Verdicts unchanged; k = 20.
