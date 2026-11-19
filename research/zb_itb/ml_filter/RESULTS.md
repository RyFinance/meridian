# ML filter / sizer on the ZB->ITB rule: walk-forward test (2026-10-19)

**VERDICT: NEUTRAL (no real ML edge; not HELPS).** 7 of 8 model/threshold combos FAIL: lower total P&L and Sharpe than baseline. The 8th (Ridge skip) technically clears baseline and the shuffles, but only because it re-learned the "post-holiday" flag. The win-rate gain is +0.8 pt.

## Setup
- Trades: the frozen 570 (net = g_off - 4 bp). Walk-forward: expanding window, monthly refit, first fold has 220 training trades. **OOS = 350 trades, 2025-05-01 to 2026-10-16** (18 monthly folds).
- 22 features, all aligned to trade direction where directional (`features.py`): |m|, |m| z (60d), 4 ZB path segments (16-20, 20-02, 02-08, 08-09 ET), ZN agree + ZN move, ES=F move 16:00->09:00 (60m fetched from yfinance, `ES_F_60m.parquet`), ITB 5/20d return and 5/20d vol, 60d ITB-TLT corr, weekday dummies, post-holiday, long/short, previous trade's net and win.
- Models (fixed in advance, no tuning): LogisticRegression(C=0.02); Ridge(alpha=500, standardized, target winsorized 2/98%); LightGBM (2 levels, 4 leaves, 120 trees, lr 0.03, lambda 10, min leaf 25, 70% row/col subsample). Median-imputed.
- Sharpe is daily, mean/std x sqrt(252), skipped days count as 0. maxDD is on exp(cumsum). P&L in bp of log return summed over trades. Only 8 combos were run, all reported.

## Leakage checks (`leak_check.py`: all pass)
- My `m` equals the frozen `m` on all 582 rows (max diff 1e-16).
- Every intraday source bar ended at or before 09:00 ET on D (0 violations; minimum slack 0 min, because `m` itself ends at 09:00). The ITB, TLT, `prev_net` and `mhist` inputs are only rows dated before D.
- Truncation test: for 60 random days I rebuilt features from data cut off at 09:00 ET on D. 0 mismatches versus the full-data features.
- Training rows are only trades before the month's first day, and their outcomes (10:30) are known. Hyperparameters and thresholds were fixed before looking at OOS.
- Caveat: the "post-holiday is bad" finding is already in VERIFICATION.md, which was written from the full sample. That is soft contamination in favor of the one combo that won.

## OOS results, same 350 trades (baseline: win 59.1%, mean +26.8 bp, total +9386 bp, Sharpe 3.94, maxDD -12.0%)
| combo | trades | win | mean bp | total bp | Sharpe | maxDD | AUC | vs baseline |
|---|---|---|---|---|---|---|---|---|
| LR-cls skip p<base-3pt | 217 | 57.1 | 18.6 | 4042 | 2.22 | -12.8 | 0.52 | FAIL |
| LR-cls skip p<base | 166 | 60.8 | 20.3 | 3372 | 2.21 | -10.3 | 0.52 | FAIL (win up, P&L/Sharpe down) |
| GBM-cls skip p<base-3pt | 213 | 57.7 | 20.3 | 4320 | 2.44 | -12.2 | 0.48 | FAIL |
| GBM-cls skip p<base | 172 | 58.1 | 21.5 | 3697 | 2.28 | -12.6 | 0.48 | FAIL |
| Ridge-reg skip pred<0 | 334 | 59.9 | 29.3 | 9770 | 4.23 | -10.4 | 0.51 | marginal pass |
| GBM-reg skip pred<0 | 287 | 58.9 | 26.3 | 7548 | 3.38 | -14.4 | 0.50 | FAIL |
| Ridge-reg size (w=pred/mean, clip 0-2) | avg w .87 | 59.9 | | 8423 (9720 per unit w) | 3.53 | -12.3 | | FAIL |
| GBM-reg size | avg w .84 | 58.9 | | 6396 (7611 per unit w) | 2.79 | -17.1 | | FAIL |

Classifier AUC is 0.48-0.52 (chance). Spearman IC of regression predictions with realised net is -0.07 to 0.00.

## Controls (random = 2000 random skips of the same count; shuffle = 20 seeds of permuted training targets, same pipeline, scored on real OOS outcomes). Fraction of controls >= the model:
| combo | random: win / Sharpe / P&L | shuffle: win / Sharpe / P&L |
|---|---|---|
| LR-cls (-3pt) | .87 / .96 / .97 | .85 / .95 / 1.0 |
| LR-cls (base) | .31 / .79 / .86 | .20 / .70 / .75 |
| GBM-cls (-3pt) | .77 / .88 / .92 | .90 / .95 / 1.0 |
| GBM-cls (base) | .70 / .79 / .82 | .75 / .95 / .95 |
| Ridge skip | .15 / **.016 / .023** | .10 / **0 / 0** |
| GBM-reg skip | .64 / .68 / .57 | .50 / .75 / .75 |
| Ridge size | n/a / .41 / .37 | .10 / .55 / .50 |
| GBM-reg size | n/a / .68 / .85 | .50 / .90 / 1.0 |
- The classifier filters do worse than a random skip of the same size. Their win-rate changes sit inside the random range (p 0.3-0.87).
- Shuffled-label models give mean Sharpe 2.7-3.9 and total P&L 4.8k-9.1k. Filters cut P&L mechanically because every skipped trade has positive expected value.

## Why Ridge skip looks good, and why that is not ML (`diag.py`, post-hoc)
- It skips 16 trades (net -384 bp, 44% win). 7 of the 16 are post-holiday days; OOS post-holiday trades (11) sum to -881 bp.
- Top ridge coefficient is `postholiday` (-4.05 std-units, the largest). Drop that feature and the same pipeline gives Sharpe 3.70, P&L 8646: **below baseline**. A plain "skip post-holiday" rule gives Sharpe 4.41, P&L 10267, win 60.0%, and beats the ridge.
- By half: first half Sharpe 2.99 vs baseline 3.08 (ridge worse); second half 5.39 vs 4.72.
- Evidence is 11 OOS trades. Chosen as 1 of 8, a Bonferroni-adjusted random-control p is about 0.13-0.18. Not significant.

## Feature importances (mean over 18 folds, `importances.csv`)
- LR-cls |coef|: ret5_al .16, postholiday .12, long .10, ret20_al .08, zn_agree .07, vol20 .07 (flat, no dominant feature, AUC 0.52).
- GBM-cls gain share: ret5_al .18, prev_net .10, es_al .10, ret20_al .09, vol20 .09, corr60 .08 (noise-like spread).
- Ridge-reg |coef| (bp per std): postholiday 4.1, ret20_al 2.2, es_al 2.1, absm 1.9, vol5 1.9, corr60 1.8.
- The ITB-TLT correlation, ES move, ZN agreement, |m|, and path segments carry no stable signal. The sign of the top coefficients flips between model types.

## Bottom line
- Sizing by predicted return hurt. No filter raised win rate meaningfully while holding P&L and Sharpe. The two with a higher win rate (LR skip p<base 60.8%, Ridge 59.9%) are either within random range or driven by one flag.
- The rule has no model-detectable heterogeneity on 570 trades. Keep it unfiltered, at most with a plain post-holiday skip, which is an untested hypothesis on 18 trades. Do not add ML.
