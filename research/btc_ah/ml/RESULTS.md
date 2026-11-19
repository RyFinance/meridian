# ML walk-forward: BTC off-hours features -> MSTR open->close (agent: ml)

Question: can a walk-forward model on BTC off-hours features predict MSTR 09:30->close net of costs?

## Setup
- 27 features, all known by 09:25 ET: BTC 16:00->09:25 return and 5 segment returns; realized vol, range,
  max drawdown/run-up; volume vs trailing 20 windows; late share; weekend, gap days, day of week; BTC 1/5/20-day
  momentum; MSTR prior-day return, 5/20-day momentum, prior range, prior open->close, gap history, 20-day vol.
  MSTR's own 09:30 gap is excluded.
- Target: log(Close/Open), entry 09:30 open, exit close. Cost 3 bp per side.
- Models: LightGBM regressor on log return; logistic regression on sign.
- Trade sign(pred) when |pred| > q-quantile of |pred| on the training window (q=0 trades all days).
- Walk-forward, expanding from 2020-08-12; OOS 2022-01-01..2026-08-10 (1068 days, 1371 usable rows overall).
  Yearly and quarterly retrains. Sealed holdout respected (BTC bars from 2026-08-11 ET dropped; daily rows after 2026-08-10 dropped).
- Not run: 09:30->10:30 target (1m MSTR data does not cover 2024-01..2026-04).

## Results (OOS 2022-01..2026-08-10, net of 6 bp round trip)
20 rule variants (2 schemes x 2 models x 5 thresholds), plus 5 shuffled-label seeds per cell.

| rule | n | hit | mean net bp | t | avg win / loss bp | dev n, mean, t | check n, mean, t | flip bp (t) |
|---|---|---|---|---|---|---|---|---|
| yearly logit q0 | 1068 | 0.512 | -0.9 | -0.06 | +341 / -360 | 124, +48, 0.87 | 944, -7, -0.50 | -11 (-0.76) |
| yearly logit q0.9 | 119 | 0.529 | +46 | 1.06 | +369 / -317 | 20, +130, 0.82 | 99, +30, 0.70 | -58 (-1.34) |
| yearly lgb q0 | 1068 | 0.505 | -10.7 | -0.73 | +337 / -365 | 124, -29, -0.52 | 944, -8, -0.56 | -1 (-0.09) |
| yearly lgb q0.8 | 138 | 0.478 | -49 | -1.13 | +357 / -421 | 18, -34, -0.22 | 120, -52, -1.16 | +37 (+0.86) |
| quarterly logit q0 | 1068 | 0.523 | +8.4 | 0.57 | +343 / -359 | 124, +54, 0.97 | 944, +2, 0.16 | -20 (-1.39) |
| quarterly logit q0.5 | 567 | 0.526 | +9.8 | 0.50 | +339 / -355 | 69, +61, 0.83 | 498, +3, 0.13 | -22 (-1.10) |
| quarterly lgb q0 | 1068 | 0.496 | -9.1 | -0.62 | +344 / -357 | 124, -48, -0.85 | 944, -4, -0.27 | -3 (-0.20) |
| quarterly lgb q0.9 | 40 | 0.450 | -1.1 | -0.01 | +495 / -407 | 5, +350, 1.11 | 35, -51, -0.58 | -11 (-0.12) |

Across all 20 cells: max |t| = 1.13 (yearly lgb q0.8, negative); max mean = +46 bp (yearly logit q0.9).
Benchmarks on the same days: always long -0.3 bp net, always short -11.7 bp net.

Shuffled-label control (same pipeline, permuted training targets, 5 seeds): per-cell mean t runs -0.96 to +0.43;
largest single-seed t = +1.67. Real-label max |t| = 1.13 sits inside this noise.

## Top 3 dev rules (dev = 2022-01..06; rules with dev n >= 30, ranked by dev t)
1. quarterly logit q0: dev +54 bp (t 0.97) -> check +2 bp (t 0.16).
2. yearly logit q0: dev +48 bp (t 0.87) -> check -7 bp (t -0.50).
3. yearly logit q0.5: dev +61 bp (t 0.84) -> check -10 bp (t -0.53).
Large dev-to-check decay: overfit noise.

## Per-year net bp (full OOS)
- quarterly logit q0: 2022 +9, 2023 -25, 2024 -34, 2025 +78, 2026 +11
- yearly logit q0.9: 2022 +63, 2023 -30, 2024 +96, 2025 +140, 2026 +145 (flip -58)
- yearly lgb q0.8: 2022 -113, 2023 -27, 2024 +163, 2025 -109, 2026 -130
Signs flip across years for each rule shown.

## Feature importance and leakage audit
- LightGBM gain share (fold average), top 8: m_prev_range 0.072, m_gap_absmean20 0.058, seg_16_20 0.057,
  late_share 0.054, m_vol20 0.053, btc_volratio 0.049, m_mom5 0.046, m_gap_prev 0.046. Flat; no dominant feature.
  weekend and gap_days get zero gain.
- Perturbation audit (audit.py): randomized all BTC bars and MSTR daily rows at or after 4 cutpoints (09:25 ET),
  rebuilt features. 98,442 cells for days decided before each cutpoint: 0 changed. Negative control (same test
  on days after the cutpoint): 13,754 of 16,308 cells changed, so the audit detects leakage.

## Verdict: NONE
No walk-forward model shows a net edge on MSTR open->close from BTC off-hours information. The best-looking cell
(yearly logit q0.9, +46 bp, t 1.06) is within shuffled-label noise and its flip is not clearly negative. Dev-selected
rules do not hold in check. Gross means on the all-day rules are only about +5 to +15 bp, so costs are not what decides
this; the signal is weak to absent.

Files: research/btc_ah/ml/{features.py, run_ml.py, audit.py, results.json, RESULTS.md}
