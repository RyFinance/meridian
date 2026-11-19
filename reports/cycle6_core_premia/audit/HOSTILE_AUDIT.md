# Hostile audit: cycle-6 combined book (the only POSITIVE)

2026-09-27. Code and outputs: `reports/cycle6_core_premia/audit/` (`t1`–`t10`, `common.py`, `out/`). An independent
reproduction is in `repro/`.

**Independence disclosure.** This audit ran in the same session that built cycle 6, so the auditor is not
independent of the builder. Mitigations:
- the book was rebuilt by fresh code written from the A5 §E text, with no builder book or portfolio code;
- the sleeves were rebuilt by a separate agent that did not look at the builder's strategy code first;
- every test was run as mandated, and none was skipped.

## VERDICT: **FAILS**

**The single most important reason: the positive belongs to the 60/40 core, not the premia.**
- Measured against a volatility-matched 60/40 SPY/IEF control, the book's post-publication active Sharpe is **−0.07**
  (A4 calibrated p = 0.56).
- The book without the core is not positive: post-publication Sharpe 0.39, 90% CI [−0.23, 0.94].
- The core's own share of the book alone clears the rule: Sharpe 0.65, 90% CI [0.04, 1.23].

**A second, independent failure: an inference error.**
- A4 §6 requires the **95%** interval for crash-exposed series shorter than 120 months.
- The book holds two crash-declared sleeves (CARRY-FX, XSMOM-FX) and has only 92 post-publication months.
- The book spec never propagated the crash declaration.
- Under A4 as written, the raw-return 95% interval is [−0.04, 1.23], which includes zero. The book was never POSITIVE,
  even on raw returns.

## Evidence

| # | Test | Result | Finding |
|---|---|---|---|
| 1a | Book − vol-matched core control, post-pub (n = 92) | Active Sharpe −0.07; 90% CI [−0.86, 0.64]; p 0.56 (0.57 with crash layer and bandwidth 0.20) | **FATAL** |
| 1a | Same, core era 2002-09+ (n = 278) | Active Sharpe −0.06; 90% CI [−0.36, 0.24]; p 0.64 | **FATAL**: no edge over the core in 23 years |
| 1b | Ex-core book, post-pub | Sharpe 0.39; 90% CI [−0.23, 0.94]; p 0.16 | Not positive |
| 1b | Ex-core book, 2002-09+ / full 1975+ | 0.40 [0.12, 0.66] / 0.50 [0.25, 0.75] | Pre-2019 in-sample strength only |
| 1c | Regression on SPY and IEF, post-pub | Alpha 0.4%/yr (HAC t 0.41; A4 p 0.34); β_SPY 0.089 (t 6.2); R² 0.29 | No alpha |
| 1c | Same, ex-core | Alpha 0.4%/yr (t 0.40; p 0.34) | No alpha |
| 2 | Reproduction, book | My A5 §E rebuild vs builder: post-pub max \|Δ\| 0.0; full-sample max \|Δ\| 6e-5 (T-bill month-end convention before 1980); ERC/fallback months identical | Reproduces |
| 2 | Reproduction, sleeves (independent agent) | TSMOM-FI, TSMOM-CM, XSMOM-FX, CARRY-FX, CORE: identical to 1e-15 | Reproduces |
| 2 | VAL-FX, SEAS-FX divergences | VAL-FX: CPI-change operator (log of mean vs mean of log), 3 signal months pre-1996, ambiguous spec wording. SEAS-FX: the sizing-vol floor quantile excludes the zero-rank median asset (small bug; ranks and signs identical). Post-pub Sharpe changes ≤ 0.002 | Minor, disclosed |
| 3 | Own post-publication windows | TSMOM-FI 0.47 [−0.04, 0.92]; TSMOM-CM 0.45 [0.07, 0.83]; XSMOM-FX −0.12; VAL-FX −0.02; CARRY-FX 0.35 [−0.02, 0.75]; SEAS-FX −0.18 | 3 of 6 sleeves negative post-pub |
| 3 | Book on component-level post-pub returns (robustness) | From 2009-05: 0.79 [0.51, 1.09]; ex-core 0.40 [0.11, 0.69] | Core-heavy 2009–2013 (only 2 sleeves live); cannot create a pass |
| 4 | P&L share, post-pub | Core 44%, TSMOM-CM 36%, TSMOM-FI 32%, CARRY-FX 24%, XSMOM-FX 6%, SEAS-FX −12%, VAL-FX −26% | Positive = core + trend |
| 4 | By asset class, post-pub | FX: 69% of weight and 57% of risk, but **−9% of P&L** | FX concentration is risk without return |
| 4 | Drop one sleeve, post-pub | CI loses zero-exclusion when dropping TSMOM-FI, TSMOM-CM, CARRY-FX or CORE; dropping VAL-FX or SEAS-FX raises Sharpe to 0.81–0.82 | Fragile: 4 of 7 sleeves are each pivotal |
| 4 | Best year / 2022 | Best year 2019 (+4.5%, 33% of P&L), ex-2019 0.44 [−0.18, 0.98]; 2022 share 24%, ex-2022 0.54 [−0.02, 1.13]; top-5% months 64% of P&L | Concentrated |
| 5 | Fidelity selection vs performance (20 components) | Pass − fail post-pub Sharpe +0.13 (point-biserial 0.21, permutation p 0.19); optimism vs all components +0.09 Sharpe | Mild, not significant; not the driver |
| 6 | Null world, variant A (one sign process shared by all sleeves, preserves cross-correlation; 10,000 books) | 14.3% of nulls "POSITIVE" on raw returns; real Sharpe beaten by 9.3%; real active-vs-core beaten by 7.9% | Raw rule false-passes about 3× its nominal 5% |
| 6 | Null world, variant B (independent signs; 10,000) | 8.8% POSITIVE; beaten by 8.6% / 7.0%. ERC re-solve check, 300 nulls: 11.7% | Sleeve timing adds nothing significant (p ≈ 0.07–0.09) |
| 7 | Independent CI re-implementation (numpy AR sieve, bootstrap-t) | 90% [0.12, 1.11] vs builder [0.05, 1.10] | Consistent |
| 7 | Monte Carlo seed sensitivity (B = 499) | 90% lower bound across 50 seeds: −0.012 to 0.134; below zero for 6% of seeds | Pass hinges on simulation noise |
| 7 | A4 §6 rule: 95% interval (crash-exposed, n < 120) | A4 code [−0.04, 1.23]; independent [0.02, 1.19]; with crash layer [−0.20, 1.18] | **FATAL**: crash declaration not propagated to the book spec |
| 7 | B = 9,999 ledgered before returns? | FRAMEWORK §9 ledgered 19:45:41Z; first trial 20:23:31Z | OK (it applies to p-values, not the CI) |
| 8 | Look-ahead, perturbation test (independent agent) | Future data replaced by noise at 5 cuts: all earlier weights bit-identical, in the builder's saved weights too | None found |
| 8 | Point-in-time: CPI | US CPI = t−2 reading, released at t−1 (conservative). Foreign CPI uses the latest revised vintage with a 2-month lag, **not first release**; release dates could not be verified | Minor residual risk |
| 8 | Point-in-time: rates and FX | Short rates dated within month t; OECD averages lagged 1 month; H.10 spot is a market price, so its publication lag does not leak | OK |
| 8 | Point-in-time: seasonality | Same calendar month of earlier years only; the holding month is excluded | OK |
| 8 | Addendum-1 QA change steering selection (robustness) | Under the literal strict QA rule, XSMOM-FX and VAL-FX lose fidelity (β 0.62–0.63). That book would be TSMOM-FI, TSMOM-CM, CARRY-FX, SEAS-FX + core: 1.00 [0.35, 1.67]. Removing WTI changes nothing (0.60 [0.06, 1.11]) | The change added two losing FX sleeves, so it did not steer toward a pass. Book membership is fragile to data QA |
| 9 | Costs 2× / 3×, post-pub | 0.48 [−0.06, 0.99] / 0.37 [−0.18, 0.87] | Not robust to 2× costs |
| 9 | FX forward-point vs rate-differential bias | Book effect −0.003%/yr (per sleeve −0.08 to +0.08%/yr) | Negligible |
| 9 | Economic size, post-pub | Excess 1.7%/yr at 2.9% vol; cash + excess 4.6%/yr vs T-bill 2.8%; the 2× gross cap binds every month | Small; 12%/yr not attainable |
| 10 | TFSA ETF variant vs static exposure-matched ETF mix (static weights are the variant's average targets, ex post) | Post-pub: variant 0.52 vs static 1.27; difference −1.0%/yr, 90% CI [−1.89, −0.11]. Full 2002-08+: −0.65%/yr [−1.05, 0.10] | Timing subtracts value (report only) |

## What survives

- **Mechanics are clean.** The book and all six sleeves reproduce, with no look-ahead or cost error.
- **The negative finding is robust.** Over 2002–2026 the premia sleeves add nothing beyond a volatility-matched
  60/40: active Sharpe −0.06, CI [−0.36, 0.24].
- **Commodity trend is the one sleeve with some evidence.** Its own post-publication Sharpe is 0.45 [0.07, 0.83], but
  p = 0.017 is above the cycle's 0.0025 threshold. It is a single sleeve, not a book-level result.

## Consequences

1. **Reclassify.** The cycle-6 book moves from POSITIVE to **FAILS (hostile audit)**. 0 of 20 components and 0 books
   are positive.
2. **Protocol lesson 1: raw-return book rules must be gated on active returns versus the core.** The raw rule
   false-passes 9–14% in the null world.
3. **Protocol lesson 2: propagate crash declarations to any combination that holds crash-declared sleeves.**
4. **Protocol lesson 3: raise CI draws.** At B = 499 the CI lower bound moves ±0.07 with the seed.

No builder file, spec, ledger or earlier report was modified. Nothing was committed.
