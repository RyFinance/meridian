# mNAV trend family — sealed validation plan (registered BEFORE the run)

Companion to `FROZEN_RULES.json` (rules M1/M2/M3, frozen 2026-10-17) and
`FROZEN_RULES_AMENDMENT_01.json` (split-basis clarification).
This plan is registered in `research/preregistrations.jsonl` before
`holdout_research.py` is executed for the first time. No sealed-window
performance statistic of any kind (strategy or benchmark) has been computed at
registration time; only source-quality inspection (BTC 16:00 quote gaps) and
SEC filing parsing were performed.

## Sealed window

- Sessions: **2023-01-03 .. 2026-08-10** (first MSTR session strictly after the
  frozen development boundary 2022-12-30; last session with a 16:00 ET BTC
  quote — the BTC 1-minute source ends 2026-08-11 08:03 UTC).
- Warm-up: signals are computed on the causal panel from 2022-01-03 onward so
  that every sealed-window decision uses only real, prior observations; the
  simulation starts flat at the first sealed session open.

## Window disclosure

The 2023+ MSTR daily window is **not virgin project-wide**: it was used by the
independent premium residual-momentum workstream (`premium/RESULTS.md`, failed)
and by daily-granularity 8-K event studies (`events/`). Those used different
signals; no mNAV-trend statistic was ever computed on it, and the dev window
(2020-11..2022-12) selection in `DEV_GRID.csv` predates this registration.

## Data-quality disclosure

BTC 16:00 ET quotes are missing for 43 sealed sessions in two month-sized
source holes (2024-07-01..2024-07-31, 2024-12-02..2024-12-31). The frozen gap
policy applies: no forward-fill or interpolation; the prior stance is carried
and MSTR open-to-open P&L is booked throughout; after a gap, rolling inputs
warm up from observed data before a new signal can fire.

## Executed rules (frozen; parameters not re-chosen)

- M1: long when p_t − p_{t−10} > 0 and p_t > SMA50(p_t)  — dev best Sharpe.
- M2: long when p_t − p_{t−20} > 0 and p_t > SMA50(p_t)  — dev runner-up, kept
  as parameter-stability check.
- M3: M2 AND 20-day BTC momentum > 0  — predeclared conservative regime variant.
- p_t = log(gross BTC mNAV proxy) per `FROZEN_RULES.json`; signal after close,
  execution at next session open; 100% MSTR or 100% cash; forced final
  liquidation at the last sealed session open under exit costs.

## Costs

- Base: 3 bp slippage per side; $0.005 per actual share per side
  ($0.0005 per split-adjusted pseudo-share before 2024-08-08).
- Stress: 6 bp per side; 2× commission.
- Benchmark: MSTR buy-and-hold over the same window, same execution and cost
  model, `start_long=True`.

## Pre-registered gates (registered before any sealed statistic was computed)

Bootstrap: stationary block bootstrap of the aligned daily net-return pairs
(strategy, benchmark), mean block length 21 sessions, 2,000 draws, seed
20260817; statistic = annualized Sharpe difference D = SR_strategy − SR_benchmark
(SR = √252·mean/std of daily net returns); one-sided P(D > 0) over draws.

- **G1 (primary, M1):** base-cost net Sharpe(M1) > net Sharpe(B&H) AND
  P(D > 0) ≥ 0.95.
- **G2 (stress):** stress-cost net Sharpe(M1) > stress Sharpe(B&H) AND
  P(D > 0) ≥ 0.90.
- **G3 (realism):** M1 sealed-window net total return > 0 under base costs.
- **Verdict = PASS iff G1 and G2 and G3.** M2/M3 are corroboration only; a
  pass on M2/M3 cannot substitute for M1, and a fail on them does not overturn
  an M1 pass (they are reported for stability).

## Power disclosure (assumption-based; no sealed statistic used)

Assumed MSTR daily vol ≈ 5%; T ≈ 3.6 y → per-book se(SR) ≈ 1/√3.6 ≈ 0.53.
For a true Sharpe edge of ≈ 0.5 with return correlation ρ ≈ 0.7,
se(SR diff) ≈ 0.53·√(2(1−ρ)) ≈ 0.41 and P(P(D>0) ≥ 0.95) is low (~20–35%).
The design is therefore **MARGINAL** at that effect size: a pass is strong
evidence; a fail is reported with the bootstrap quantile and point estimates
and does not, by itself, refute small edges. No re-tuning or re-running on
this window follows either way.

## Outcome handling

- PASS → register a forward paper-test plan (no live orders, ever, in this
  research effort).
- FAIL → append honestly to `REPORT.md` and `HOLDOUT_RESULTS.md`; do not re-run
  variants on this window.

## Code

- Runner: `holdout_research.py` (this directory; hash registered before the run).
- Core mechanics: `mnav_core.py` (hash registered before the run).
- Frozen rule file and amendment hashes registered alongside.
