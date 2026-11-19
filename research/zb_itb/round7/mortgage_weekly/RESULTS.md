# Round 7 mortgage_weekly: rate surprises, rate trends, ITB/ZB residuals (2026-10-18)

Costs 4 bp round trip (2 bp/side). Net = pos x ITB log return - 4 bp.
Daily splits: dev 2006-2018, check 2019-2026-10-16. 60m splits: dev 2024-05-28..2025-06-30, check 2025-07-01..2026-10-16.
Controls: flip = opposite direction on the same trades; SPY = same trades on SPY.
Variants tried: 19 main (6 + 4 + 9). |t| around 2 is about what 19 variants give by chance.

| Variant | dev n | dev bp | dev t | chk n | chk bp | chk t | chk hit | flip chk bp | SPY chk t |
|---|---|---|---|---|---|---|---|---|---|
| 1A PMMS surprise S, Thu cl->Fri cl | 658 | -3.7 | -0.50 | 406 | +4.8 | 0.56 | 0.52 | -12.8 | -0.05 |
| 1B as 1A, abs(zS)>0.5 | 289 | -2.8 | -0.23 | 232 | +9.9 | 0.93 | 0.53 | -17.9 | 0.50 |
| 1C raw PMMS change X, Thu cl->Fri cl | 619 | +0.9 | 0.12 | 384 | -8.2 | -0.96 | 0.49 | +0.2 | -1.51 |
| 1D S, 60m Thu 12:30->16:00 | 55 | +14.8 | 1.56 | 66 | -18.1 | -1.81 | 0.44 | +10.1 | -2.59 |
| 1E S, 60m Thu 12:30->Fri cl | 55 | +20.6 | 0.89 | 66 | -10.4 | -0.42 | 0.39 | +2.4 | -1.04 |
| 1F as 1D, abs(zS)>0.5 | 34 | +21.5 | 1.55 | 30 | -17.2 | -1.18 | 0.47 | +9.2 | -0.77 |
| 2A TNX 5d chg, next-day ITB open->cl | 3158 | +3.6 | 0.95 | 1952 | -4.0 | -1.05 | 0.47 | -4.0 | -0.95 |
| 2B as 2A, top-30% abs chg | 792 | +0.9 | 0.09 | 608 | +5.8 | 0.80 | 0.49 | -13.8 | 0.78 |
| 2C ZB 5d return, next-day ITB open->cl | 3152 | +1.2 | 0.30 | 1937 | -1.0 | -0.27 | 0.48 | -7.0 | -0.37 |
| 2D as 2C, top-30% abs ret | 953 | -1.4 | -0.16 | 625 | +4.0 | 0.53 | 0.48 | -12.0 | 0.10 |
| 3a resid(ITB on ZB) thr 1, hold 1d | 665 | -9.9 | -1.01 | 402 | -4.2 | -0.34 | 0.50 | -3.8 | 0.55 |
| 3b resid thr 1, hold 3d | 432 | -6.9 | -0.32 | 282 | -19.4 | -0.92 | 0.52 | +11.4 | -0.19 |
| 3c resid thr 1, hold 5d | 335 | +60.4 | 1.94 | 210 | +2.8 | 0.08 | 0.50 | -10.8 | 0.10 |
| 3d resid thr 2, hold 1d | 153 | +3.3 | 0.13 | 89 | -19.4 | -0.77 | 0.48 | +11.4 | -0.25 |
| 3e resid thr 2, hold 3d | 123 | +14.5 | 0.34 | 79 | -83.3 | -1.70 | 0.48 | +75.3 | -1.47 |
| 3f resid thr 2, hold 5d | 111 | -22.7 | -0.34 | 72 | +14.4 | 0.17 | 0.46 | -22.4 | 0.19 |
| 3g raw ITB z thr 2, hold 1d | 163 | -2.2 | -0.08 | 99 | -3.4 | -0.09 | 0.51 | -4.6 | 0.07 |
| 3h raw ITB z thr 2, hold 3d | 138 | +17.4 | 0.42 | 85 | -20.1 | -0.40 | 0.52 | +12.1 | -0.75 |
| 3i raw ITB z thr 2, hold 5d | 120 | +15.3 | 0.23 | 75 | +46.1 | 0.55 | 0.53 | -54.1 | 0.34 |

## Rules
- **1 (PMMS).** Freddie PMMS (FRED MORTGAGE30US, Thursday 12:00 ET release). X = weekly change in pp. Y = 10Y (^TNX) change Wed-to-Wed. S = X - beta*Y, beta is expanding OLS on past weeks only. zS = S / past-only std. Position = -sign(S) (higher-than-implied rates short ITB). Entry at Thu close or 12:30 bar open.
- **2 (trend).** 5d change in ^TNX (or ZB return), signal at close t, trade ITB open->close on t+1. Expected sign: yields up -> short. Threshold is the expanding past-only 70th percentile of abs signal.
- **3 (residual).** Past-only 120d rolling beta of ITB on ZB close-to-close. e = rI - beta*rZ. Signal z = e / past-only std. Revert: position = -sign(z), entered at close t+1 (ZB daily timing is not confirmed, so one bar of lag), held k days, non-overlapping.

## Controls and checks
- **MBA applications:** skipped. No free weekly series is available here (FRED does not carry it).
- **Overnight control (2024-05+, idea 2):** OLS of ITB open->close(t+1) on the trend position and the overnight rule d(t+1). Trend coefficient: TNX +6.3 bp (t 0.99), ZB +8.0 bp (t 1.24). d coefficient t 4.5. The trend adds nothing beyond the overnight rule.
- **Survivorship:** none of the 19 variants passes the check split with a flip-consistent sign and |t| >= 2.

## Verdicts
- **Idea 1 (PMMS surprise): NONE.** Dev-best by dev bp is 1F (+21.5, t 1.55). Check -17.2 bp, t -1.18, sign reversed.
- **Idea 2 (multi-day trend): NONE.** Dev-best is 2A (+3.6, t 0.95). Check -4.0 bp, t -1.05. Adds nothing beyond the overnight rule.
- **Idea 3 (residual reversion): NONE.** Dev-best is 3c (+60 bp, t 1.94, n 335). Check +2.8 bp, t 0.08. Dev-only.

## Caveats
- The 60m samples are small (n 30-66 per split). The t values are not reliable.
- Daily ITB close-to-close uses raw (unadjusted) Close, so ex-dividend drops enter the close-to-close returns. Open->close is unaffected.
- ^TNX is in percent. The 10Y change uses the Wed close, so it may lag the Mon-Wed survey window slightly.
- The SPY placebo in 1A shows a dev-only -11.7 bp (t -2.89) that does not reappear in check (-0.05). It indicates the sign is not market-specific in dev, and is not evidence of edge.

Files: dl.py, an.py, results.csv, cache/. Scripts run from /Users/rytty/CCP/quant_v7 with PYTHONPATH=. .venv/bin/python.
