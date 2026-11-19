# Cycle 8 continuation — corrections, daily tails and direct LSE audit

**Portfolio construction from known US-tradable risk premia, not alpha research.** For a Canadian retail investor, the objective remains the highest expected long-run return from the fixed US-listed menu, subject to a 60/40 Sharpe hurdle and drawdown tolerances of 25%, 35% or 50%. The owner chooses the tolerance. No new portfolio, ticker substitution, optimized weight or leverage level is introduced. Zero validated alpha edges remain; earlier failed cycles remain spent.

Client date: **October 1, 2026, America/Vancouver**. Some UTC receipts fall on October 2. This is a post-result continuation, not an independent confirmatory experiment. Original US1 code, data snapshots, report and results are preserved.

## What changes the answer, and what does not

The independent audit found a real discrepancy between the expected-return formula and the forward overlay risk simulation. It also showed that month-end drawdown screening misses substantial daily risk. Those defects warranted new, separately frozen calculations. C1 corrects only overlay arithmetic premiums. C2 makes funded and overlay arithmetic means consistent with the declared ranking model, while retaining its approximate half-variance forecast. The daily supplement measures daily losses inside entire jointly sampled asset/FX months.

**The three-tolerance answer survives these checks:** no supported candidate at 25% or 35%; unlevered 60/40 remains the highest-return conditional candidate at 50%. Its corrected daily 20-year breach probability is 3.71%, compared with the original monthly estimate of 2.65%. No fully certified winner is established because official-close provenance, old gold tails, missing early trend history and historical house margin rules remain unresolved.

A third attempted repair used observed London gold fixings from a free historical archive. It produced an apparent 35% candidate, but deeper validation uncovered impossible fixing dates and a suspicious isolated crash/rebound. **C3 is quarantined and excluded from every decision.** A better-looking answer from defective source data is not evidence of a better portfolio.

| Tolerance | Supported conditional answer | Expected nominal return | Corrected forward risk evidence | Fully certified answer |
|---|---|---|---|---|
| 25% | None | — | No joint Sharpe/risk pass; P3 daily breach 81.36% | None |
| 35% | None | — | P3 daily breach 45.07%; accepted non-P3 rows fail the joint gate | None |
| 50% | P3 at 1x: 60% SPY / 40% IEF style | 4.21%–6.15%; center 5.21% | Daily breach 3.71%; month-end C2 2.60% | None |

These ranges retain the frozen forward ranking assumptions; they are scenarios, not confidence intervals. Neutral expected CAD/USD log drift gives the same nominal growth expectation in both currencies, while currency still changes risk. The 20-year probability concerns drawdown in **either USD or CAD**. The original historical point Sharpe must meet same-window 60/40 in **both currencies**. Daily checks are available for P1/P2/P3; trend-containing C2 risks remain monthly and cannot establish a daily limit. P4 at 1.25x passes the accepted monthly 50% screen, with lower expected return, but is not certified. No externally borrowed row wins the highest-return comparison.

## Unlevered 60/40: daily versus month-end

| Lens | Limit | Month-end risk, same paths | Daily risk | 95% Monte Carlo interval for daily estimate |
|---|---|---|---|---|
| historical | 25% | 47.26% | 55.88% | 54.90%–56.85% |
| historical | 35% | 4.90% | 8.10% | 7.58%–8.65% |
| historical | 50% | 0.09% | 0.18% | 0.11%–0.28% |
| C2 | 25% | 69.16% | 81.36% | 80.58%–82.11% |
| C2 | 35% | 31.27% | 45.07% | 44.10%–46.05% |
| C2 | 50% | 2.60% | 3.71% | 3.36%–4.10% |

The intervals quantify finite simulation sampling only. They do not cover expected-return uncertainty, structural change, missing crises, source errors or model error. For the 50% forward result, the 95% Monte Carlo interval is 3.36%–4.10%. For 35%, the daily estimate is much larger than 10%. The original historical 35% month-end probability was 4.90%; measuring the same sampled history daily raises it to 8.10%. Lower future expected returns raise the corrected daily figure to 45.07%.

The daily simulation keeps complete observed equity, Treasury and FX paths within each sampled month. Months are drawn jointly with a 24-month mean stationary-block length, using 10,000 paths and the unchanged seed. It discards the same 36-month burn-in and evaluates 240 subsequent months. Portfolio targets reset monthly; margin accrues and is checked daily. Padding slots have zero returns and carry and add no elapsed time. No trend or old gold daily returns are invented in this supplement. Treasury-calendar and FX observation-time approximations remain. Drawdown is close-to-close, not intraday.

## What the model correction fixes

Original central XT expected arithmetic premium was 1.0000% annually in the risk bootstrap, but 1.7730% in the ranking formula. XB was 0.6000% versus 0.8699%, including the bond fee. A 50% overlay therefore had an annual portfolio-mean mismatch of approximately 0.3865 or 0.1350 percentage points at outer 1x. C1 fits those overlay arithmetic targets and leaves other means unchanged. C2 scales primitive gross simple returns to match the ranking's monthly arithmetic mean exactly, and defines each overlay as its corresponding funded sleeve return minus the same forward cash.

| Row | Original forward 50% risk | C1 overlay correction | C2 coherent means | Frozen forward expected return center |
|---|---|---|---|---|
| P3@1 | 2.65% | not rerun | 2.60% | 5.21% |
| P4@1 | 0.83% | not rerun | 0.80% | 5.08% |
| P4@1.25 | 8.28% | not rerun | 8.00% | 4.95% |
| P6a@1 | 35.96% | 34.72% | 35.12% | 6.21% |
| P6b@1 | 45.93% | 45.52% | 45.57% | 5.77% |

Correcting the overlay discrepancy reduces the trend stack's modeled 50% risk slightly, but leaves it far above 10%. The daily C2 60/40 simulation has median realized 20-year CAGR of 5.26%, close to the 5.21% approximate ranking center; this is a model diagnostic, not a new forecast or a confidence bound.

C2 is not exact lognormal mathematics. The original model's variance estimate comes from a common historical window; its annual arithmetic target adds half variance to the geometric scenario, and cash/financing use annual simple rates divided by twelve. The implied geometric sleeve means are saved in moment_checks.csv. The corrected US equity and bond geometric means for the P3 window are approximately 5.43% and 4.12%, respectively. Target-fitting and exact overlay identities pass deterministic checks; remaining approximation is visible rather than silently removed.

## Direct LSE audit: stronger evidence, incomplete repair

The desktop tool inventory still exposes no LSE tool, but the repository's existing read-only stdio bridge successfully reached its already configured Terminal. No configuration or credential was changed. This supersedes the earlier session's availability finding, which remains preserved with its date.

The direct audit sampled three full SPY minute sessions, August 17–19, 2026, and compared them with LSE daily bars and the existing exchange-local ETF series. All sessions extend from 08:00 UTC to 23:59 UTC. In August, 20:00 UTC corresponds to 16:00 Eastern. The daily close exactly equals the final 23:59 UTC minute on all three dates.

| Date | Parsed 1-minute bars | LSE daily close | Last 23:59 UTC close | 19:59 UTC close | 20:00 UTC close | Saved exchange close |
|---|---|---|---|---|---|---|
| 2026-08-17 | 936 | 772.65 | 772.65 | 772.66 | 772.65 | 772.67 |
| 2026-08-18 | 954 | 767.06 | 767.06 | 767.27 | 767.36 | 767.45 |
| 2026-08-19 | 930 | 770.01 | 770.01 | 769.08 | 769.18 | 769.06 |

The three-day request advertised 2,820 bars but its text output was truncated at roughly 60,000 characters. The audit therefore reacquired one complete day per request and verified 936, 954 and 930 rows. Reported header coverage alone is not proof of complete delivered data. The history tool's ISO-time example also failed: this provider requires YYYY-MM-DD date arguments. Those failures and successful requests are snapshotted.

For all fourteen named ETFs, an August daily request returned SPY, VTI, GLD and TLT; the other ten reported no candle data. Returned histories contain all 21 SPY calendar dates for the requested completed month. In SPY, 20 of 21 closes differ from the saved exchange close by more than one cent; the largest difference is $4.54. This demonstrates that the vendor daily close cannot be substituted as a regular-session total-return close for this study. A 19:59 or 20:00 minute close also does not uniquely establish the closing auction, so the audit does not claim a completed official-close reconstruction.

The LSE US10Y series was compared with the frozen DGS10 yield source in 1990 and 2026. Median absolute gaps are 0.90 and 0.80 basis points; maximum gaps are 13.20 and 3.00 basis points, with level correlations 0.995 and 0.998. This is useful overlap evidence, but different market-observation conventions and calendar coverage remain. LSE catalog metadata offers US10Y from 1990, insufficient to replace the earlier crisis history. Policy-rate catalog metadata offers a US series from 1971; its target definition must be established before replacing effective FEDFUNDS. No benchmark type was silently substituted.

Current observations are documented in LSE_MINUTE_CLOSE_AUDIT.csv, LSE_ETF_AUGUST_AUDIT.csv and LSE_RATES_AUDIT.json. Every raw reply is archived and hashed. The empirical result is consistent with the [maintainer's earlier caveat](https://github.com/OlegDyukel/lse-data-mcp#data-caveats), but establishes only the sampled SPY convention, not a proof about every asset or vendor revision.

## Failed gold repair: quarantine record

The free [Center for Financial Stability archive](https://www.centerforfinancialstability.org/hfs.php) supplied a March 2015 workbook with daily London AM and PM gold prices and source metadata referring to LBMA. The PM USD extraction contains 10,745 numerical observations from April 1968 through December 2010, no duplicate dates, positive prices and no missing month ends in 1971–2004. Those initial checks were insufficient.

A deeper audit found **584 weekend PM observations**. London fixing benchmarks are not published on weekends, according to the [LBMA pricing documentation](https://www.lbma.org.uk/prices-and-data/lbma-precious-metal-prices). A February 5, 1983 Saturday observation falls from $498.50 to $342.40 and then rebounds to $490.25 on the next observation: approximately −31.31% followed by +43.18%. After 1999, many quotes appear on Tuesday–Saturday, suggesting a calendar alignment problem. The daily overlap with GLD does not reconcile, although level and monthly correlations are high. High level correlation is therefore inadequate for validating daily paths.

C3 was preregistered as a source correction before its portfolio returns. It replaced old monthly-average gold with observed month ends, holding the fixed P4/P5 rules unchanged. It produced a numerical P5 at 1.25x Sharpe pass and a 3.88% forward monthly probability of breaching 35%, with an expected center of 4.52%. **That apparent new 35% answer is rejected because the source failed validation.** The tables are kept only as a failed diagnostic and are prominently listed in GOLD_QUARANTINE.json. No arbitrary weekend removal or one-day shift is accepted without independent primary confirmation.

The official [LBMA historical table](https://www.lbma.org.uk/prices-and-data/lbma-precious-metal-prices) now directs users to licensed portal access. No paid data was purchased or restricted access bypassed. An additional LSE gold-price search returned no commodity price series or XAUUSD instrument. The old gold-tail gate remains unresolved. The [AQR century trend paper](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing) describes a longer reconstruction, while its [downloadable TSMOM factor page](https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Factors-Monthly?aqrPDF=1) explicitly begins in January 1985. A paper figure is not an obtained numerical series; the missing 1970s trend gate remains unresolved.

## Accounts, crises and 12% growth

The supported conditional implementation remains fully paid 60% SPY / 40% IEF, monthly rebalance, with the original approximately 0.1167% weighted fund fee plus declared trading and FX costs. It can be held without account margin in a TFSA or RRSP subject to eligibility. The original withholding and account-source note remains linked; this continuation does not update fee forecasts, assume universal treaty treatment or claim that a generic maintenance calculation is a broker's initial-margin permission.

The exact original worst named CAD 60/40 crisis remains 1973–74: −25.22% cumulative and 31.09% month-end drawdown, with full-sample CAD daily proxy drawdown of 32.98%. The crisis helper has a genuine endpoint-coverage defect: it accepts a series ending before a named crisis ends. A strict consecutive-month endpoint check found **zero affected saved original crisis rows**. The demonstrated bug should be corrected before reuse on partial future windows, but no original crisis result is silently rewritten.

Kelly remains an approximate historical growth diagnostic. It does not authorize the same multiple for portfolios with different embedded gross exposure. Generic 30% maintenance results for leveraged funds are counterfactual, because actual initial/house requirements are unverified. The unlevered candidate avoids that account borrowing issue.

The stronger daily risk evidence further weakens a 12% growth target. In the C2 forward supplement, 2x US equity has a 97.94% probability of exceeding 50% drawdown over twenty years, and 2x 60/40 has 73.49%. Their original forward return centers are 3.50% and 4.53%, respectively, not 12%. Higher leverage does not supply a 12% central expected return under the frozen retail-financing assumptions. The old historical examples with roughly 80%–90% losses remain relevant; no accepted correction pairs a 12% expected return with a validated 25%, 35% or 50% ceiling.

## All corrected monthly rows

These are C2 central forward probabilities, before applying the historical Sharpe hurdle and certification exclusions. The original forward expected-return centers are retained for comparison. Cash's Sharpe against itself is undefined, P7 remains cautionary, and short actual fund histories remain excluded from winner certification. A tiny risk number from RSSB's short history is not accepted evidence of long-run safety.

| Row | Original forward center | C2 P(DD>25%) | C2 P(DD>35%) | C2 P(DD>50%) | Original joint Sharpe pass |
|---|---|---|---|---|---|
| P1@1 | 5.40% | 94.42% | 75.03% | 49.91% | no |
| P1@1.25 | 5.14% | 99.03% | 89.29% | 65.06% | no |
| P1@1.5 | 4.74% | 99.88% | 96.80% | 76.10% | no |
| P1@2 | 3.50% | 100.00% | 99.82% | 93.88% | no |
| P2@1 | 5.36% | 90.61% | 62.51% | 15.10% | no |
| P2@1.25 | 5.22% | 94.90% | 76.19% | 47.55% | no |
| P2@1.5 | 4.99% | 98.37% | 91.64% | 63.56% | no |
| P2@2 | 4.25% | 99.94% | 97.60% | 80.78% | no |
| P3@1 | 5.21% | 69.16% | 31.27% | 2.60% | yes |
| P3@1.25 | 5.12% | 85.72% | 60.76% | 13.21% | no |
| P3@1.5 | 4.98% | 94.01% | 78.69% | 34.70% | no |
| P3@2 | 4.53% | 99.25% | 93.19% | 67.94% | no |
| P4@1 | 5.08% | 63.36% | 16.60% | 0.80% | yes |
| P4@1.25 | 4.95% | 84.25% | 51.55% | 8.00% | yes |
| P4@1.5 | 4.77% | 94.08% | 76.79% | 23.78% | yes |
| P4@2 | 4.22% | 99.72% | 93.56% | 65.08% | no |
| P5@1 | 4.61% | 9.34% | 0.40% | 0.00% | no |
| P5@1.25 | 4.45% | 31.43% | 3.96% | 0.03% | no |
| P5@1.5 | 4.27% | 56.17% | 16.04% | 1.00% | no |
| P5@2 | 3.83% | 91.12% | 55.44% | 14.51% | no |
| P6a@1 | 6.21% | 95.73% | 68.62% | 35.12% | yes |
| P6a@1.25 | 6.14% | 99.11% | 89.59% | 59.00% | yes |
| P6a@1.5 | 5.92% | 99.93% | 98.12% | 73.31% | yes |
| P6a@2 | 5.03% | 100.00% | 99.64% | 95.58% | yes |
| P6b@1 | 5.77% | 94.92% | 80.96% | 45.57% | no |
| P6b@1.25 | 5.59% | 99.15% | 92.61% | 66.59% | no |
| P6b@1.5 | 5.25% | 99.82% | 96.01% | 82.20% | no |
| P6b@2 | 4.13% | 100.00% | 99.65% | 94.52% | no |
| NTSX@1 | 5.36% | 96.15% | 45.61% | 7.20% | yes |
| NTSX@1.25 | 5.02% | 97.81% | 94.00% | 27.34% | no |
| NTSX@1.5 | 4.50% | 99.32% | 96.57% | 54.94% | no |
| NTSX@2 | 2.95% | 100.00% | 98.98% | 95.35% | no |
| RSSB@1 | 7.33% | 0.10% | 0.00% | 0.00% | no |
| RSSB@1.25 | 7.62% | 2.00% | 0.01% | 0.00% | no |
| RSSB@1.5 | 7.80% | 14.30% | 0.48% | 0.00% | no |
| RSSB@2 | 7.79% | 73.02% | 12.45% | 0.11% | no |
| RSST@1 | 5.86% | 84.89% | 34.12% | 1.65% | no |
| RSST@1.25 | 5.59% | 100.00% | 70.40% | 13.08% | no |
| RSST@1.5 | 5.12% | 100.00% | 100.00% | 40.51% | no |
| RSST@2 | 3.59% | 100.00% | 100.00% | 86.28% | no |
| GDE@1 | 4.28% | 100.00% | 99.96% | 72.63% | yes |
| GDE@1.25 | 3.36% | 100.00% | 100.00% | 99.83% | yes |
| GDE@1.5 | 2.14% | 100.00% | 100.00% | 99.98% | yes |
| GDE@2 | -1.18% | 100.00% | 100.00% | 100.00% | yes |
| P7a@1 | 7.31% | 99.85% | 97.12% | 76.23% | no |
| P7a@1.25 | 7.13% | 99.99% | 99.10% | 91.23% | no |
| P7a@1.5 | 6.63% | 100.00% | 99.89% | 97.52% | no |
| P7a@2 | 4.71% | 100.00% | 99.99% | 99.75% | no |
| P7b@1 | 6.84% | 99.99% | 99.55% | 93.58% | no |
| P7b@1.25 | 5.89% | 100.00% | 99.99% | 99.02% | no |
| P7b@1.5 | 4.38% | 100.00% | 99.99% | 99.56% | no |
| P7b@2 | -0.34% | 100.00% | 100.00% | 99.99% | no |
| P8@1 | 3.49% | 10.92% | 1.17% | 0.02% | no |
| P8@1.25 | 3.11% | 13.40% | 1.89% | 0.03% | no |
| P8@1.5 | 2.74% | 17.32% | 2.84% | 0.05% | no |
| P8@2 | 1.98% | 24.56% | 6.72% | 0.23% | no |

## All daily-risk rows

| Row | Lens | Daily P25 | Daily P35 | Daily P50 | Month-end P50, same paths | Mean calls over 20 years |
|---|---|---|---|---|---|---|
| P1@1 | historical | 95.99% | 72.01% | 34.14% | 25.23% | 0.000 |
| P1@1.25 | historical | 99.64% | 93.28% | 61.80% | 55.95% | 0.000 |
| P1@1.5 | historical | 99.97% | 97.72% | 73.60% | 66.00% | 0.000 |
| P1@2 | historical | 100.00% | 99.97% | 96.16% | 87.85% | 0.357 |
| P2@1 | historical | 91.09% | 58.21% | 4.75% | 2.83% | 0.000 |
| P2@1.25 | historical | 96.31% | 72.22% | 38.07% | 14.26% | 0.000 |
| P2@1.5 | historical | 99.18% | 94.36% | 59.65% | 53.95% | 0.000 |
| P2@2 | historical | 99.99% | 99.10% | 84.39% | 71.80% | 0.000 |
| P3@1 | historical | 55.88% | 8.10% | 0.18% | 0.09% | 0.000 |
| P3@1.25 | historical | 88.61% | 48.98% | 2.79% | 1.87% | 0.000 |
| P3@1.5 | historical | 95.97% | 66.90% | 21.09% | 8.71% | 0.000 |
| P3@2 | historical | 99.61% | 96.30% | 62.28% | 48.62% | 0.000 |
| P1@1 | C2 | 98.68% | 81.46% | 56.53% | 49.91% | 0.000 |
| P1@1.25 | C2 | 99.95% | 96.32% | 71.90% | 65.06% | 0.000 |
| P1@1.5 | C2 | 100.00% | 99.10% | 82.60% | 76.11% | 0.000 |
| P1@2 | C2 | 100.00% | 100.00% | 97.94% | 93.90% | 0.357 |
| P2@1 | C2 | 95.72% | 68.11% | 20.35% | 15.10% | 0.000 |
| P2@1.25 | C2 | 98.77% | 82.03% | 57.20% | 47.56% | 0.000 |
| P2@1.5 | C2 | 99.88% | 96.21% | 70.08% | 63.56% | 0.000 |
| P2@2 | C2 | 100.00% | 99.55% | 94.69% | 80.80% | 0.000 |
| P3@1 | C2 | 81.36% | 45.07% | 3.71% | 2.60% | 0.000 |
| P3@1.25 | C2 | 93.32% | 67.90% | 17.09% | 13.23% | 0.000 |
| P3@1.5 | C2 | 97.80% | 83.95% | 47.28% | 34.71% | 0.000 |
| P3@2 | C2 | 99.97% | 97.29% | 73.49% | 67.97% | 0.000 |

## Receipts, verification and limitations

| Artifact | UTC receipt | SHA-256 |
|---|---|---|
| C1/C2/daily preregistration and code receipt | 2026-10-02T06:00:59.465988+00:00 | 3c1e2baffa639cf895bf7f07d043b10aa54ce85b207f3db1fd4d5d04d3c638be |
| C3 gold repair receipt | 2026-10-02T06:06:33.337382+00:00 | f99e7619e4275027796ac31eef5dad9be0a49f8f70497e5ff842a466cecabc86 |

C1/C2 evaluated 64 correction rows: eight minimal overlay corrections and all 56 coherent-mean rows. The daily supplement evaluated 24 combinations: three portfolios, four leverage levels, two lenses, each with 10,000 paths. C3 evaluated eight gold-dependent combinations; all are quarantined for source failure. A default interpreter lacked numba for C3 intervals; rerunning with the existing project virtual environment completed the unchanged code. No environment settings or system packages were modified. A workbook reader was installed only in the new follow-up directory to inspect the free archive.

Checks passed for exact arithmetic means, overlay identity, source month-end anchoring, joint asset/FX indexing, threshold and horizon probability monotonicity, daily drawdown at least month-end drawdown on the same paths, matching P3 at 1x month-end probabilities against the original and C2, strict saved crisis coverage, and unchanged frozen receipt files. Original code and numerical snapshot hashes are verified again. These verify calculation consistency, not model truth.

Three subagents were dispatched. One returned the overlay inconsistency before all three hit usage limits. The coordinator reproduced it independently and completed the computations and audit. Unavailable evidence remains unavailable; usage limits do not justify accepting incomplete gates.

## Artifacts

- [AUDIT_MODEL.md](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only_followup/AUDIT_MODEL.md)
- [correction_risk.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only_followup/correction_risk.csv)
- [daily_risk.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only_followup/daily_risk.csv)
- [moment_checks.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only_followup/moment_checks.csv)
- [verification.json](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only_followup/verification.json)
- [receipt.json](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only_followup/receipt.json)
- [LSE_MINUTE_CLOSE_AUDIT.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only_followup/LSE_MINUTE_CLOSE_AUDIT.csv)
- [LSE_ETF_AUGUST_AUDIT.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only_followup/LSE_ETF_AUGUST_AUDIT.csv)
- [LSE_DAILY_CLOSE_COMPARISON.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only_followup/LSE_DAILY_CLOSE_COMPARISON.csv)
- [LSE_RATES_AUDIT.json](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only_followup/LSE_RATES_AUDIT.json)
- [GOLD_QUARANTINE.json](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only_followup/GOLD_QUARANTINE.json)
- [GOLD_WEEKEND_FLAGS.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only_followup/GOLD_WEEKEND_FLAGS.csv)
- [GOLD_1983_BAD_PRINT.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only_followup/GOLD_1983_BAD_PRINT.csv)
- [gold_overlap.json](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only_followup/gold_overlap.json)
- [gold_receipt.json](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only_followup/gold_receipt.json)
- [Original complete US1 results](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/RESULTS.md)
- [Frozen follow-up protocol](/Users/rytty/CCP/quant_v7/research/cycle8_us_only_followup/PREREG.md)

![Daily risk comparison](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only_followup/daily_risk_comparison.png)
