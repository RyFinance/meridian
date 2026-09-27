# Cycle 6: Styles-Everywhere book — results

2026-09-27. Every spec was ledgered before its first return and run once; there were no reruns and no bug fixes
(`research/cycle6/trial_ledger.csv`). Rules: `research/cycle6/FRAMEWORK.md`, `FRAMEWORK_ADDENDUM_1.md`, A4 and A5 as
written, with the FRAMEWORK §9 deviations. Snapshots: `cycle6_eval_v1` `ba67379b…`, `cycle6_trade_v1` `940335bf…`.
Engine `e9cec9f0…`.

**Headline.**
- **Components:** 0 of 20 are POSITIVE. 6 pass fidelity, and the smallest post-publication p-value is 0.021, against a
  threshold of 0.05/20 = 0.0025.
- **Book:** POSITIVE under the frozen rule. Post-publication net Sharpe is 0.60, with a 90% interval of [0.05, 1.10]
  over 92 months.
- **Tradable variants:** neither excludes zero at its headline setting.

## Components

Definitions:
- **Fidelity:** the gross shadow against the benchmark. The AQR-class tier reports ρ / β / TE÷σ; the paper-stat tier
  reports coverage of the paper's sample. Thresholds are in FRAMEWORK §5.
- **Sharpe:** net of base costs and one-session lag, with the A4 calibrated 90% interval.
- **p:** A4 null-calibrated, one-sided, on the post-publication net active series (book minus exposure-matched
  control), B = 9,999.
- **Stress:** post-publication net Sharpe at 3× costs.

| ID | Fidelity | Detail | Sharpe, full [90% CI] | Sharpe, post-pub [90% CI] | Post from, n | Active, post | p | Stress, post | Max DD | Best / worst year | POSITIVE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TSMOM-EQ | FAIL | ρ .84, β .68 (below .70), TE÷σ .54 | 0.44 [0.03, 0.85] | 0.16 [−0.38, 0.68] | 2011-01, 189 | −0.14 | 0.726 | 0.14 | −58% | 2017 +67% / 2011 −32% | no |
| TSMOM-FI | **PASS** | ρ .88, β .89, TE÷σ .49 | 0.46 [0.21, 0.68] | 0.47 [0.02, 0.86] | 2011-01, 189 | 0.44 | 0.038 | 0.43 | −54% | 2022 +117% / 1994 −44% | no |
| TSMOM-FX | FAIL | ρ .74, β 1.06, TE÷σ .95 (above .90) | 0.42 [0.09, 0.73] | 0.00 [−0.41, 0.34] | 2011-01, 189 | −0.09 | 0.720 | −0.05 | −78% | 1987 / 1975 | no |
| TSMOM-CM | **PASS** | ρ .74, β .89, TE÷σ .81 | 0.45 [0.08, 0.78] | 0.45 [0.09, 0.79] | 2011-01, 189 | 0.46 | 0.023 | 0.40 | −40% | 2015 / 2016 | no |
| XSMOM-EQ | FAIL | ρ .56, TE÷σ 1.25 | 0.37 [0.09, 0.65] | 0.35 [−0.07, 0.73] | 2009-04, 210 | 0.39 | 0.052 | 0.31 | −54% | 1997 / 1999 | no |
| XSMOM-FI | FAIL | ρ .59, TE÷σ 1.14 | 0.20 [−0.09, 0.45] | 0.26 [−0.19, 0.67] | 2009-04, 210 | 0.44 | 0.067 | 0.14 | −13% | 2013 / 1999 | no |
| XSMOM-FX | **PASS** | ρ .91, β .90, TE÷σ .42 | 0.16 [−0.04, 0.34] | −0.12 [−0.46, 0.20] | 2009-04, 210 | 0.04 | 0.424 | −0.23 | −35% | 1980 / 1991 | no |
| XSMOM-CM | FAIL | ρ .650 (just below .65), TE÷σ 1.10 | 0.29 [0.01, 0.56] | 0.33 [0.06, 0.63] | 2009-04, 210 | 0.39 | 0.036 | 0.29 | −47% | 2025 / 2008 | no |
| VAL-EQ | FAIL | ρ .30, β .32 (5-year reversal, not BE/ME) | −0.19 [−0.47, 0.05] | −0.35 [−0.66, −0.08] | 2009-04, 210 | −0.32 | 0.974 | −0.37 | −62% | 2002 / 2019 | no |
| VAL-FI | FAIL | ρ .72, TE÷σ 1.04 | 0.40 [0.06, 0.71] | 0.36 [−0.15, 0.84] | 2009-04, 210 | 0.53 | 0.047 | 0.29 | −13% | 2009 / 2008 | no |
| VAL-FX | **PASS** | ρ .92, β .93, TE÷σ .40 | 0.43 [0.17, 0.68] | −0.02 [−0.40, 0.42] | 2009-04, 210 | 0.16 | 0.208 | −0.06 | −19% | 1985 / 2023 | no |
| VAL-CM | FAIL | ρ .25, β .37 (total-return index, not spot) | −0.19 [−0.75, 0.39] | −0.19 [−0.75, 0.39] | 2009-04, 178 | −0.12 | 0.684 | −0.21 | −76% | 2013 / 2026 | no |
| CARRY-FI | FAIL | coverage .65 of the KMVP sample; vol off by 3.0 pp | 0.43 [0.13, 0.73] | 0.27 [−0.30, 0.81] | 2013-09, 157 | 0.43 | 0.118 | 0.22 | −16% | 1996 / 2022 | no |
| CARRY-FX | **PASS** | KMVP Table 2 mean, vol and Sharpe within bands; coverage 1.00 | 0.43 [0.18, 0.67] | 0.35 [−0.04, 0.75] | 2013-09, 157 | 0.52 | **0.021** | 0.32 | −31% | 1996 / 2008 | no |
| BAB-EQ | FAIL | ρ .44, β .43 vs AQR Defensive | 0.18 [−0.28, 0.66] | −0.30 [−0.73, 0.10] | 2011-01, 189 | −0.17 | 0.789 | −0.32 | −41% | 2004 / 2026 | no |
| BAB-FI | FAIL | coverage .53 of FP Table VI | −0.21 [−0.42, −0.02] | −0.19 [−0.51, 0.20] | 2011-01, 189 | −0.09 | 0.677 | −0.19 | −61% | 2009 / 2008 | no |
| SEAS-EQ | FAIL | coverage .45 of BSV; Sharpe off by .32 | 0.04 [−0.17, 0.28] | 0.02 [−0.36, 0.41] | 2015-01, 141 | 0.08 | 0.391 | −0.24 | −32% | 2008 / 2020 | no |
| SEAS-FI | FAIL | coverage .52; Sharpe off by .40 | 0.05 [−0.32, 0.40] | 0.20 [−0.30, 0.63] | 2019-02, 92 | 0.55 | 0.036 | −0.30 | −53% | 2003 / 2008 | no |
| SEAS-FX | **PASS** | BSV Table II Sharpe within .30; coverage 1.00 | −0.30 [−0.51, −0.10] | −0.18 [−1.00, 0.55] | 2019-02, 92 | −0.15 | 0.671 | −0.57 | −86% | 2022 / 1995 | no |
| SEAS-CM | FAIL | coverage .12 | −0.42 [−0.81, −0.06] | −0.57 [−1.05, −0.10] | 2015-01, 141 | −0.58 | 0.991 | −0.76 | −65% | 2019 / 2015 | no |

- **Infeasible, not run:** CARRY-CM (2 energy instruments, below the 4-asset floor) and equity carry (no free data).
- **Concentration:** in `components/<ID>/metrics.json`. The post-publication top-5%-month shares are meaningless for
  books whose total P&L is near zero; examples are TSMOM-FX, VAL-FX and SEAS-EQ.

## Combined book (spec `BOOK` `8843f97f…`)

- **Sleeves:** the 6 fidelity-passing components (TSMOM-FI, TSMOM-CM, XSMOM-FX, VAL-FX, CARRY-FX, SEAS-FX) plus the
  core, 60/40 SPY/IEF, from 2002-08.
- **Weighting:** A5 §E. Equal risk contribution applied in 322 months, the 1/σ fallback in 291.

| Window | n | Net excess Sharpe [90% CI] | Mean, annual | Vol, annual | Max DD | POSITIVE |
|---|---|---|---|---|---|---|
| Full, 1975-09 → 2026-09 | 613 | 0.58 [0.33, 0.83] | 2.3% | 3.9% | −11.5% | — |
| Post-publication, 2019-02 → | 92 | **0.60 [0.05, 1.10]** | 1.7% | 2.9% | −3.3% | **YES (by rule)** |

- **Volatility is well under the 10% target.** The A5 §E 2× gross-notional cap binds: mean gross is 2.00, because
  TSMOM sleeves carry large notional at 0.40/σ. The book therefore runs at about 3–4% volatility.
- **Post-publication window:** it starts 2019-02 because SEAS-FX, a fidelity pass, carries the BSV cutoff.
- **12%/yr (A5 §E, information only):** not attainable. The conservative mean is 1.26%/yr and the required leverage
  exceeds the cap.
- **Simulated 10-year max drawdown:** median −7.2%, with a 5th–95th percentile range of −13.1% to −4.0%.
- **Correlations among included sleeves:** on 226 common months, |ρ| ≤ 0.39. VAL-FX vs XSMOM-FX is −0.39 and VAL-FX vs
  TSMOM-CM −0.33. Across all 20 components the mean |ρ| is 0.11. Full matrix: `component_correlations.csv`.

## Canadian tradable variants (separate ledger entries; the paper spec is not replaced)

Both variants run from 2002-08. The post-publication window is the book's (2019-02 →, n = 92). Sharpe is on
excess returns with the A4 90% interval.

| Variant (spec) | Setting | Full Sharpe | Post Sharpe [90% CI] | Vol | Max DD | Notes |
|---|---|---|---|---|---|---|
| ETF long/flat (`172112e3…`) | **TFSA, CAD, 100k (headline)** | 0.33 | 0.52 [−0.07, 1.16] | 1.6–2.2% | −7% | gross 0.31, 69% cash; costs about 0.24%/yr |
| | TFSA, CAD, 25k / 250k | 0.25 / 0.35 | 0.41 / 0.55 | | | integer-share rounding costs little |
| | RRSP, CAD, 100k | 0.36 | 0.54 [−0.06, 1.18] | | | |
| | Funded in USD (either account) | 0.34–0.36 | 0.25–0.26 | | | CAD translation changes the post-pub result |
| | Norbert's gambit, 0.15% | 0.22 | 0.37 | | | FX conversion is the largest sensitivity |
| Margin: ETFs + micro futures (`c78fd4b1…`) | **CAD 100k (headline)** | 0.20 | 0.08 [−0.78, 0.90] | 2.5% | −8% | 16% of targets can't be held at this size |
| | CAD 25k / 250k / unrounded | −0.02 / 0.30 / 0.29 | −0.26 / 0.46 / 0.56 | | | contract rounding is decisive below 250k |
| | Borrow, spreads or FX ×3 | 0.10–0.15 | −0.09 to 0.00 | | | |

- **Dropped from both variants:** 10 of 12 bond countries (no single-country 5–15y ETF), SEK (FXS was liquidated and
  has no free history), and NOK and NZD (never listed).
- **Futures in the margin variant:** returns are paper-series proxies, not traded futures prices.
- **Commodity-pool ETFs (USO, UNG)** may be restricted for Canadian residents.

## Trial count (cycle 6)

- 23 runs: 20 components, 1 book and 2 variants. No reruns and no bug-fix entries.
- The Bonferroni denominator is k = 20, fixed before the first run.
- The book and the variants are reported under their own rules and are not added to k.

## Prereg ledger

Full ledger with UTC times: `research/cycle6_prereg_ledger.md`.

| Entry | SHA-256 |
|---|---|
| FRAMEWORK | 2576bf12f23baa9f93a70257b5ae779cda21bda55ef8150d89983b8a297875aa |
| ADDENDUM-1 | 72ea818058040cbee35d9531dab5d5baf841750a35a77d6828886d148a9037ae |
| ENGINE | e9cec9f0f81d15cc13968456abcbeb24fb84d85d1a29df29bc1e1eff95469422 |
| snapshot cycle6_eval_v1 | ba67379be094135e32557468710a078ea9ac6f0d87516fef331e7788b22d29be |
| k = 20 (FEASIBILITY.md) | ba0385654691b0523e4c618e7120e974add46cbbca221eb05600c70c87d7e1ae |
| TSMOM-EQ / FI / FX / CM | ea524f95… / 188d8cc9… / 9e72dcd4… / 6bd6f56b… |
| XSMOM-EQ / FI / FX / CM | d83fa03a… / dfdae81d… / 2f520f6a… / 0b2c741e… |
| VAL-EQ / FI / FX / CM | 04864ea3… / 9f221d33… / 285afa0d… / c338bd9d… |
| CARRY-FI / FX | b28c152f… / 4b154993… |
| BAB-EQ / FI | 61978edc… / 842dc68e… |
| SEAS-EQ / FI / FX / CM | d4786ef6… / 9d6e5a8d… / 3863dc7f… / a35b021f… |
| BOOK | 8843f97fe7eb6137f338f458eb9d09f406daea082d19e186cc37a577601a706b |
| TRADABLE code / snapshot cycle6_trade_v1 | 82cbf425… / 940335bf… |
| TRADE-ETF-LF / TRADE-MARGIN | 172112e3… / c78fd4b1… |

## Process disclosures

- **LSE Terminal access:** the MCP Python bridge failed, so both data agents read the LSE Terminal through its local,
  read-only HTTP API (127.0.0.1:7799) with the sandbox disabled. No order, algo or broker route was used.
- **Pre-return fixes:** the rates agent adjusted the QA start rule and TE months after seeing instrument-level QA
  status (no strategy returns). These were adopted in ADDENDUM-1 before any return.
- **Positives:** the book is the only positive and is flagged for the owner's later audit. Nothing here rescues the
  non-positives.
