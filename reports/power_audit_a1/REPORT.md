# Power framework audit (cycle 5, Program A1)

*Written by the cycle-5 independent auditor A1. Saved by the director session.*

## Summary

I found no material coding or sign error in `research/power/`. The formulas are right under the models they state. Three things are wrong in how they are used:

- **The one Monte Carlo miss** is about one-third a real bias and two-thirds Monte Carlo noise. It is not the 2–3 pp bias the report describes.
- **"53 of 54 agree" is weak evidence.** Every Monte Carlo uses the same model as the formula it checks. Some also plug the formula's own standard error or D into the test statistic.
- **Amendment 3's validation-gate size claim is false** when the gate uses a HAC t on monthly or weekly windows.

Two inputs overstate effective observations, and they flip the verdict for commodity_roll.

Everything is on synthetic data. Nothing existing was edited. Total CPU was about 6 minutes.

## Findings, ranked by severity

**1. HIGH: the HAC-t option in Amendment 3 P2 is oversized on short windows.**
- Amendment 3 lets a plan register "a HAC t" and claims P(pass | S=0) ≤ α/k_val, and that the gate is "uniformly most powerful at its size".
- I ran a literal Newey–West t with the framework's own plug-in lags, 40,000 paths per case. At α = 0.05/3, actual size over nominal was:

| Series | Actual / nominal size |
|---|---|
| Monthly iid, 10 years | 1.29× |
| Monthly AR(1) 0.3, 10 years | 1.87× |
| Monthly 3-month overlap, 10 years | 2.11× |
| Weekly 4-week overlap, 5 years | 2.28× |
| Weekly AR(1) 0.1, 4.7 years (FINRA validation window) | 1.25× |
| Daily series | 1.04–1.12× |

- The ratio gets worse as α gets smaller.
- The literal 21-day circular block bootstrap is fine: 5.3% ± 0.2% at 0.05, and 1.66% at 0.0167 (`cbb_size.csv`).
- Cycle 4 saw this problem (7.6% at nominal 5%) but tagged it "INFO" and dropped it from the count.

**2. HIGH: effective observations exceed raw observations for commodity_roll, and this flips its verdict.**
- The spec uses D = 0.60, backed out of one realised bootstrap p. The framework therefore reports 17,311 effective observations from 15,233 raw ones.
- With D = 1.0, joint power under the proposed gate falls from 0.63 (DECISIVE) to 0.43 (MARGINAL). With D = 1.2 the current-gate verdict becomes INCAPABLE (`spec_sensitivities.csv`).
- The report's "commodity_roll .63 → DECISIVE" line should not stand.

**3. MEDIUM: the Monte Carlo suite is largely circular.** Details are in the circularity section below.

**4. MEDIUM: the proposed-gate numbers use k_val = 1 even though the cycle-4 batch is k = 3.**
- All cycle-4 specs set `pav.k_val = 1`. Amendment 3 defines k_val as the number of candidates taken to validation together.
- With k_val = 3, Treasury auction surprise joint power falls from 0.49 to 0.39. Binance falls from 0.059 to 0.033 and FINRA from 0.091 to 0.055.
- None of the verdicts change, but the report's "0.49 under the proposed gate" is optimistic.

**5. MEDIUM: the breadth formula is right, but its correlation parameter is easy to misread.**
- ρ_bet = ρ_resid × ρ_signal is exact in a one-factor model. With several orthogonal factors, the product of the total shares is an upper bound on ρ_bet, so it is conservative.
- The trap is that ρ_resid must be the variance share of the factor the signal is tilted towards. It is not the average pairwise residual correlation.
- In a synthetic test (N = 2000, 10 sectors plus a style factor, signal tilted to the style factor), the true effective breadth was 39.3. The formula gives 39.2 when fed the factor share.
- Fed the measured average pairwise correlation of market-neutral residuals (≈0.00006, which is about zero by construction), it gives 1,943. That overstates the implied Sharpe by 7.0× (`breadth_semantics.csv`).
- The spec wording "rho_resid 0.2–0.4 after market-neutral" is ambiguous on exactly this point.

**6. MEDIUM: the winner's-curse prior is too generous.**
- The conditional median-unbiased estimator is correctly calibrated: P(estimate ≤ S | passed) is 0.50–0.52 across S from 0 to 1. It is very noisy (sd 0.8–1.65).
- The N(0, 0.5²) posterior mean averages 0.46 for true nulls that passed the dev gate, so it barely shrinks at all.
- For tsy_month_end (dev estimate 0.664), a prior with 80% mass at zero gives 0.15, and 90% gives 0.08, against 0.45 under N(0, 0.5²).
- This does not change Amendment 3's conclusion that validation misses were the likely outcome; it strengthens it.

**7. LOW: smaller items.**
- **Sharpe SE:** the Lo/Opdyke κ is 3–3.5% low in short samples (monthly AR(1) 0.5 over 5 years; monthly crash innovations over 10 years). Ŝ is biased upward by 0.04–0.06 at S = 1.
- **Turnover:** the formula understates realised turnover by 0.5–3%. That overstates net Sharpe by at most 0.014, not the "~5%" the report cites.
- **Two-stage independence:** exact at a fixed S. If the true Sharpe varies between dev and validation windows, joint power at a mean of 0.7 ranges from 0.36 to 0.45 against the fixed-S 0.42 (`two_stage_heterogeneity.csv`).
- **Floor not wired in:** plan_check never applies the 0.30 floor from Amendment 3 P2. It is non-binding in all 18 specs; the lowest threshold is 0.41.
- **Unchecked cluster-size variation:** the Monte Carlo ignores cluster-size variation, so the cv = 0.4 used by c4c is never checked.
- **Citation:** "Zoellner & Pfeiffer 2008" appears garbled; it is likely Zöllner & Pritchard (2007) or Zhong & Prentice (2008). Andrews, Kitagawa & McCloskey is about argmax selection, not threshold truncation.
- **Formulas checked and correct:**
  - D1 and D2, including the AR(1)-overlap and persistent-overlap forms;
  - the Bartlett and Newey–West expectations;
  - the Opdyke signs and coefficients, (g4−1)/4 and −g3·s;
  - the Kish/Moulton m_w = E[A²]/E[A] and the Poisson concurrency result;
  - crash cumulants, the one-factor portfolio cumulants and the lognormal scale-mixture moments;
  - quantile-tilt moments, the turnover orthant formula and the 4τc cost;
  - the both-halves integral, the one-factor book Sharpe and the NW plug-in rule.

## Attribution of the Monte Carlo miss

Setup: 17 sleeves, 5 real, s = 0.6, ρ = 0.15, AR(1) 0.1 weekly, `sleeve_miss.json`.

| Estimate | P(joint pass) |
|---|---|
| Cycle-4 analytic (independent inclusion) | 0.4745 |
| Exact one-factor analytic (A1, Gauss–Hermite over the common factor) | 0.4858 |
| A1 independent Monte Carlo, own seeds, explicit AR recursion, 100k paths | 0.4850 ± 0.0016 |
| Cycle-4 simulator re-seeded, 100k paths | 0.4893 ± 0.0016 |
| Cycle-4 reported, 3k paths | 0.507 ± 0.009 |

The reported 3.25 pp gap splits into two parts:

- **Correlated inclusion accounts for +1.14 pp**, computed exactly with no Monte Carlo.
  - The number of null sleeves included has variance 3.47 in the Monte Carlo against 1.89 under the binomial assumption; the one-factor model gives 3.48.
  - The other terms are negligible. The residual from inclusion rates and non-normal Ŝ is +0.01 pp. The hold-stage t versus the normal approximation is −0.09 ± 0.15 pp.
- **Monte Carlo noise accounts for about +2.0 pp.** The 3k-path run landed about 2.2 standard errors high.
- **Ruled out:** a coding error, the autocorrelation handling, Sharpe-estimator assumptions and gate calibration.
  - With ρ = 0 the binomial analytic matches (0.6986 vs 0.7005 ± 0.002).
  - With φ = 0 the same +1.1 pp remains.
  - With ρ = 0.3 the bias grows to +2.8 pp.
- **The direction is conservative both ways.** At S = 0 the binomial overstates false-pass (0.0222 vs 0.0207).
- **The registered retrospective is unaffected.** Joint power at 0.7 moves from 0.191 to 0.193, so it stays INCAPABLE.
- **What the real gate would compute shifts it further.** A literal NW hold-out t gives 0.509 at s = 0.6 and 0.0249 at s = 0, against 0.0205. That is another +2.3 pp of power and a 21% oversize.

## Circularity assessment

Source: `circularity_classification.csv` and `noncircular_rechecks.csv`.

- **Same model everywhere.** All 54 Monte Carlo checks simulate exactly the analytic's own data-generating model: one-factor Rademacher, equicorrelation, Gaussian AR(1) and same-day-only event correlation. Model misspecification is never tested.
- **The analytic's own quantities appear in the Monte Carlo test statistic in 15 rows:**
  - the 4 IC-power rows, where the rejection statistic divides by the analytic SD;
  - 3 panel rows, which use the true D;
  - 3 sleeve rows, which use the true D;
  - 3 carry rows and 2 overlap rows, which use `ideal_null`.
- **Panel effective breadth is not tested.** It is an algebraic identity, because per-market Sharpe is set to S/√N_eff.
- **About 10 rows are vacuous size checks.** The ±3 pp tolerance is at least half the quantity being checked. A 50% size error, such as 7.6% at nominal 5%, would pass.
- **Only 8 rows are genuinely independent:** the two-stage rows with the literal block bootstrap. A few literal-moment rows (κ, sd of mean CAR, long-short sd/mean/turnover, the naive-t rows) are independent of the formula but still share its data-generating model.
- **Re-run with practitioner statistics:**
  - IC with overlap, where cycle-4 reported 5%: size is 7.1% at H = 3 and 9.5% at H = 6. Cycle 4 computed this but never reported it.
  - Panel with a literal NW t: size is 5.9–6.9%.
  - Carry with a literal NW t: false-pass is 5.0% against 3.6% analytic (K = 8) and 4.2% against 3.6% (K = 4).

## Effective sample size

Breadth is never counted as independent in power itself: power depends only on years, κ and the gate, and that is correct. Breadth enters only through the implied Sharpe. Effective observations are overstated in three places:

1. **The D < 1 input** for commodity_roll, where effective exceeds raw by 1.14×.
2. **The ρ_resid parameter**, if filled with a measured pairwise correlation. The overstatement can be about 50× in effective breadth, or 7× in Sharpe.
3. **Hold-out and validation HAC t's** in small samples, which in effect use an estimated D that is too small.

The event design effects are sensible as stated, but depend entirely on the assumed icc:

| Design | m_w | Design effect | Effective events per year |
|---|---|---|---|
| PEAD | 70 | 2.39 | 213 of 510 |
| 8,000 events | — | 7.7 | 1,034 of 8,000 |

## Proposed Amendment 4 (draft, not registered)

> **Protocol amendment 4: calibration fixes to amendment 3.** Applies to families registered after its hash is recorded.
>
> **Q1. Validation p-value.** A HAC t may be registered only if the PLAN shows, from a synthetic Monte Carlo of ≥ 20,000 paths at the plan's own n, frequency, D and α/k_val, that its size is ≤ 1.25 × nominal. Otherwise, use the mean-centred block bootstrap, or a fixed-b / small-sample-corrected HAC with its simulated critical value. Monthly, weekly and overlapping-horizon designs default to the bootstrap.
>
> **Q2. k_val in power.** Power and verdicts under P2 use k_val = the registered batch k unless the PLAN pre-commits to a smaller validation batch.
>
> **Q3. Variance ratios.** Any D (or D_null) below 1.0 is floored at 1.0 unless it is estimated from the null sd over the full dev window with a stated SE, and the verdict holds at D = 1. Reported effective observations may never exceed raw observations without that justification.
>
> **Q4. Breadth inputs.** ρ_resid × ρ_signal (or icc) must be calibrated from the measured dispersion of the per-period IC or spread on pre-dev data (ρ_bet = (N·sd(IC)² − 1)/(N − 1)), or set to the literal ρ̄ of the held bets. Average pairwise correlations of market-neutral residuals may not be used.
>
> **Q5. Winner's curse (P3).** Also report the posterior mean under a spike-and-slab prior whose null mass comes from `reports/trial_accounting/` (default 0.8).
>
> **Q6. Sleeve screens.** Use the one-factor inclusion integral (`research/power_audit_a1/sleeve_miss.py:pi_one_factor`), not independent binomials.
>
> **Q7. Evidence standard.** Size and false-pass Monte Carlo checks use a tolerance of max(3 SE, 20% relative), and at least one check per design must use the practitioner statistic (literal HAC or bootstrap), not the analytic SE. The amendment 3 claim "53/54 agree" is restated as "53/54 agree under the formulas' own model; practitioner-statistic size errors up to 2.3× nominal on monthly/weekly windows."
>
> **Q8.** plan_check applies the P2 0.30 floor.

## Files

Code is in `/Users/rytty/CCP/quant_v7/research/power_audit_a1/`:
- `sleeve_miss.py`
- `circularity.py`
- `effective_n.py`
- `figures.py`
- `common.py`
- `__init__.py`

Outputs are in `/Users/rytty/CCP/quant_v7/reports/power_audit_a1/`. The chart is `audit_a1_summary.png`.

| Topic | Files |
|---|---|
| Monte Carlo miss | `sleeve_miss.json`, `sleeve_miss_decomposition.csv` |
| Circularity | `circularity.json`, `circularity_classification.csv`, `noncircular_rechecks.csv` |
| Size checks | `hac_t_size_grid.csv`, `cbb_size.csv` |
| Effective N and specs | `effective_n.json`, `spec_sensitivities.csv`, `breadth_semantics.csv`, `floor_binding.csv` |
| Other checks | `winners_curse_check.csv`, `turnover_check.csv`, `kappa_check.csv`, `two_stage_heterogeneity.csv` |