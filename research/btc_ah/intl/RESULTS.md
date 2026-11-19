# Overnight home-market gap -> US ETF/ADR (intl), round 4

Scope: 232 rules, all costs on (ETF 2 bp/side, ADR 3 bp/side). Holdout: every cached file max date 2026-08-10 (checked, 0 violations).
Code: `intl/pull.py`, `intl/analyze.py`, `intl/report.py`, `intl/report2.py`. Full table: `intl/rules_dev_check.csv`.

## Variants
- 1a daily, Asia (14 pairs: EWJ/DXJ->N225, FXI/KWEB/MCHI/PDD/JD/BIDU->HSI, EWY->KS11, EWT->TWII, TSM->2330.TW, BABA->9988.HK, SONY/TM->N225): threshold {0, .5, 1, 2}% x {cont, fade} = 112. Entry at ADR open, exit at close. Split dev <=2022-06, check 2022-07..
- 1b 60m, Asia: 14 pairs x {raw home move, gap-residual} x {cont, fade} = 56. Entry 10:30 ET, exit 15:30 bar close. Split dev <=2025-06 / check after (60m sample starts 2023-11).
- 3 60m, Europe (8 pairs: EWG, EWU, EZU, VGK, ASML, SAP, NVO, HSBC): 2 signals x {0, 0.3}% x {cont, fade} = 64. Signal = Europe 09:00->10:00 ET move, residual = minus ADR 09:30->10:30 move. Entry 10:30, exit 11:30 ET.
- Not tested: INDA, EWZ, EWW, INFY (no home ref in brief). Europe daily (home closes 11:30 ET, look-ahead). Idea 2 is a note only.

## Results by family (dev / check)
| family | rules | dev mean>0 | check mean>0 | dev t>2 | check t>2 | median check mean |
|---|---|---|---|---|---|---|
| 1a daily Asia | 112 | 41 | 35 | 15 | 2 | -5.0 bp |
| 1b 60m Asia | 56 | 9 | 13 | 0 | 0 | -5.0 bp |
| 3 60m Europe | 64 | 5 | 7 | 0 | 0 | -5.0 bp |

Costs alone are about -4 to -6 bp per trade, so a 0 gross mean is already negative net.

## Top 3 by dev mean net (n_dev >= 30), then check
| rule | n dev | win | mean dev | t dev | avg win / avg loss | flip dev | n chk | mean chk | t chk | flip chk |
|---|---|---|---|---|---|---|---|---|---|---|
| TSM, |2330 ret| >= 2%, cont | 1279 | 54.4% | +22.4 bp | 3.02 | +1.91% / -1.79% | -34 bp | 252 | -42.8 bp | -3.09 | +31 bp |
| KWEB, HSI ret >= 1%, cont | 710 | 56.3% | +20.3 bp | 2.54 | +1.42% / -1.37% | -28 bp | 451 | -11.6 bp | -1.56 | +4 bp |
| TSM, |2330 ret| >= 1%, cont | 2784 | 53.8% | +19.8 bp | 4.73 | +1.61% / -1.45% | -32 bp | 520 | -21.0 bp | -2.43 | +9 bp |

Worst-fill (buy at high, sell at low) for the same three: dev -3.6%, -2.6%, -3.0% per trade. This is a bound, not a fill.

Per-year mean net, bp (2026 partial to Aug 10):
- TSM 2330 >=2% cont: 2000 66, 01 21, 02 -6, 03 75, 04 26, 05 42, 06 -18, 07 15, 08 69, 09 17, 10 84, 11 43, 12 1, 13 10, 14 26, 15 -15, 16 -13, 17 38, 18 -6, 19 -1, 20 -79, 21 1, 22 8, 23 -14, 24 -59, 25 -68, 26 -35.
- KWEB HSI >=1% cont: 2013 109, 14 42, 15 24, 16 11, 17 14, 18 11, 19 3, 20 -24, 21 29, 22 7, 23 -2, 24 3, 25 -8, 26 -21.
- TSM 2330 >=1% cont: 2000 63, 01 35, 02 5, 03 51, 04 30, 05 29, 06 12, 07 16, 08 49, 09 18, 10 31, 11 31, 12 25, 13 4, 14 16, 15 -7, 16 -8, 17 7, 18 -8, 19 19, 20 -25, 21 -10, 22 12, 23 -17, 24 -27, 25 -26, 26 -19.

The top 3 decay sign-flip in check. Their fade (the flip) makes +31 bp, +4 bp, +9 bp in check. This is regime change, not a stable edge.

## Idea 2 (note only, not tradable here)
US ADR open->close on D vs next Asia session return: corr 0.22 (PDD) to 0.54 (BABA), t 10 to 37 on Asia pairs. This is the US-to-Asia lead, but executing it needs the home market, so it stays a note. The corr is pre-cost and has no execution model.

## Diagnostic for idea 1 (is the US open fully priced?)
Daily gap on home move: slope 0.38 (DXJ) to 0.97 (PDD). corr(home move, open->close) -0.05 to +0.08. The open partly reprices the home move, and the remainder does not continue into the US session on average.

## Verdict: NONE
- No rule passes dev and check together. The best dev rules (t 2.5-4.7) flip sign in check. Across 112 daily rules, only 35 have positive check mean, and the median check mean is -5 bp.
- Multiple testing: with 232 rules, dev t of 3-4.7 does not survive a Bonferroni cut.
- Idea 3 (Europe overlap) and 60m Asia: dev t <= 1.1 for the best rule (HSBC, n=61) and none above 2; no check edge.
- Deviations: 60m dev/check split is 2025-06 (brief asked 2022-06; 60m data starts 2023-11). Gap signals use a 60m open price; daily uses home return only, which is known before 09:30 ET.
