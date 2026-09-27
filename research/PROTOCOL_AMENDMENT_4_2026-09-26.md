# Protocol Amendment 4: power and inference fixes

**FINAL — awaiting owner registration.** Not in `research/preregistrations.jsonl`; no force until the owner registers
it.

- **Scope:** applies to families registered after its hash is recorded. No earlier verdict is re-graded.
- **Supersedes:** `research/PROTOCOL_AMENDMENT_4_PROPOSAL_2026-09-25.md` (kept unchanged as the proposal record).
- **Evidence:**
  - the audits `reports/power_audit_a1/`, `reports/power_audit_a2/`;
  - the calibration study in `reports/amendment4/` (code `research/amendment4/`, tests `tests/test_amendment4.py`,
    17 pass).
- **Simulation effort:** every rate below is estimated with at least 20,000 simulated paths (40,000 for the size
  study) and inner calibration B = 159 or 499. All data are synthetic.

## 1. Gate on active returns, never raw exposure

**Rule.** Any design with directional exposure is gated, in both development and validation, on
`active = book − mean(exposure) × benchmark excess`. The mean exposure is taken over that window. If there are
several benchmarks, the matched controls are summed (`research/amendment4/active.py:active_series`). Event designs
gate only on the calendar-time portfolio.

**Evidence.** Long-only timing with zero skill, market Sharpe 0.4, 12 + 12 years daily:

| Gated series | Joint false pass | p-test rejection at 0.05 / 0.0125 |
|---|---|---|
| Raw returns, old test | 6.5% | — |
| Raw returns, new test | 5.2% | 26.0% / 9.3% |
| Active returns | **0.10%** | 4.8% / 1.17% |

## 2. Calibrated p-value (replaces the HAC t / 21-day block bootstrap)

**Procedure: the null-calibrated HAC t** (`research/amendment4/calib.py`).
1. **Statistic:** a Bartlett HAC t on the gated series. Bandwidth L = max(⌊4(n/100)^{2/9}⌋, 2H, ⌈0.10·n⌉), where H is
   the declared overlap horizon.
2. **Null model:** AR(p) on the demeaned series, with p ≤ max(3, 2H) chosen by BIC and Kilian bias-corrected
   (R = 50). Innovations are resampled from the residuals, which preserves skew and kurtosis.
3. **Calibration:** simulate B = 159 null series at the series' own length. The p-value is
   p = (1 + #{T* ≥ T})/(B + 1), and the test rejects if p ≤ α. With B + 1 = 160, α = 0.05 and 0.0125 are exact Monte
   Carlo levels.
4. **Crash-exposed designs** (carry, short volatility, credit, option selling) must declare a crash layer (default:
   intensity 0.2 per year, jump size −6σ) and use the larger of the plain and crash-layer p-values. A sample without a
   crash cannot reveal crash risk.
5. **Timing, trend or regime-prone designs** use bandwidth fraction 0.20. If such a design declares neither a crash
   layer nor the regime bandwidth, it gates at α/1.6.

**Size, actual ÷ nominal at α = 0.05 / 0.0125** (40,000 paths; Monte Carlo error on the 0.0125 ratio is about ±0.045):

| Scenario | New test | Old HAC t | Old bootstrap |
|---|---|---|---|
| Monthly iid, 10 years | 1.00 / 1.02 | 1.16 / 1.37 | 1.15 / 1.35 |
| Monthly AR(1) 0.3 | 1.02 / 1.13 | 1.44 / 2.15 | 1.44 / 1.96 |
| Monthly 3-month overlap | 1.08 / 1.32 | 1.54 / 2.23 | 1.59 / 2.33 |
| Weekly 4-week overlap, 5 years | 0.97 / 1.11 | 1.44 / 2.06 | 1.59 / 2.24 |
| Carry with crashes, **declared** crash layer | 0.88 / 0.78 | 1.56 / 2.35 | 1.59 / 2.41 |
| Carry with crashes, undeclared | 1.21 / 1.52 | same | same |
| Daily regimes of 180 days, ±0.5 Sharpe | 1.09 / 1.09 | 1.28 / 1.53 | 1.27 / 1.50 |
| Daily regimes of 180 days, ±1.0 Sharpe, bandwidth 0.20 | 1.17 / 1.36 | 1.98 / 3.26 | 1.90 / 2.96 |
| Monthly 6-month regimes | 1.14 / 1.21 | 1.39 / 1.92 | 1.41 / 1.88 |
| Daily iid / AR(1) 0.1 controls | 0.93–1.00 | 0.97–1.11 | 0.99–1.11 |

Every cell under the required settings is within **1.5× nominal**. The two default-setting misses (undeclared
crashes, 1.52×; ±1.0 regimes at bandwidth 0.10, 1.54×) are exactly why the declarations in points 4 and 5 are
mandatory.

**Power cost of the wider bandwidth** (10 years monthly, S 0.79, α 0.0125): power falls from 0.53 to 0.48, and to
0.42 at bandwidth 0.20.

**Dropped:** the proposal's Q2 (a registrable HAC t) and Q3 (the block-length rule). Q3 still leaves 1.41–1.60× /
1.94–2.96× in the problem cases.

## 3. The stress-cost check must bind

**Rule (validation).**
- The stress-cost series must itself pass the validation gate: calibrated p ≤ α/k_val on the stress series, AND
  stress Sharpe ≥ 0.30.
- The development stress rule (stress mean > 0) is unchanged.

**Rationale.** An edge counts only if it remains statistically certified after plausible cost misestimation. The rule
needs no new constant. It equals the base gate at zero drag and tightens smoothly as drag grows, whereas the current
rule is a step function that is inert until the drag exceeds the realised Sharpe.

**Operating characteristics.** Joint pass at true S = 0.7, 12 + 12 years monthly, by stress drag in Sharpe units:

| Rule | 0.1 | 0.2 | 0.3 | 0.4 | 0.5 | 0.7 |
|---|---|---|---|---|---|---|
| Current (stress mean > 0) | .507 | .507 | .507 | .503 | .479 | .252 |
| **This rule** | .429 | .344 | .257 | .179 | .113 | .025 |
| This rule at true S = 0.5 | .156 | .107 | .068 | .039 | .021 | .002 |

False pass at S = 0 is ≤ 0.1% under every rule.

## 4. Effective observations

Implemented as validators in `research/amendment4/validators.py` (unit-tested). `research/power` itself is unchanged.

**(a) Variance-ratio cap.**
- D < 1 is floored at 1, so effective observations never exceed raw observations.
- The only exception is a D estimated from the full development null with a stated SE; even then, the verdict must
  also be reported at D = 1.
- Evidence (20,000 paths, true D = 1): backing D out of one sample's bootstrap p gives D < 1 in 33% of paths, and the
  Newey-West ratio in 53%. The floor removes every such case.

**(b) Breadth-correlation semantics.**
- ρ_bet comes from IC dispersion, ρ_bet = (N·sd(IC)² − 1)/(N − 1), from spread dispersion, or from the literal mean
  correlation of the held bets. The market-neutral pairwise residual correlation raises an error.
- Evidence (20,000 paths; N 500, true ρ_bet 0.056, true effective N 17.3, true Sharpe 0.31):
  - the misread implies effective N 500 and Sharpe 1.55, which is 5.0× the truth; 100% of paths overstate by more
    than 50%;
  - the fix recovers the truth: median ratio 0.94, 90% range 0.85–1.05.

## 5. Power benchmark: realistic effects, stated plainly

- **Reference effects.** Plans report joint power at true net S = **0.25, 0.30 and 0.40** (the realistic post-decay
  range; the OSAP 2015+ mean is about 0.23) and at 0.7. Verdict bars are:
  - "detects large effects" if joint power at 0.7 is at least 50%;
  - "certifies realistic effects" if joint power at 0.4 is at least 50%.

- **Finding.** Under these gates (stress drag 0.1), **no design certifies S = 0.25–0.40.** This holds at every tested
  length and breadth.
  - Single series, event studies, 40–60-market panels and cross-sectional long-short all have the same power at the
    same net Sharpe.
  - With a stress drag of 0.1, S ≤ 0.40 never reaches 50% joint power, because the validation threshold is at least
    0.30 + drag.
  - With zero drag, S = 0.40 needs 37–45 years per window for 50% power (88–107 years for 80%), and S ≤ 0.30 never
    reaches 50%.
  - S = 0.7 reaches 50% at about 13–16 years per window and 80% at about 20–29 years.

**Joint power at S = 0.25 / 0.30 / 0.40 / 0.70** (stress drag 0.1; Monte Carlo agrees within 2.4 pp, and the analytic
is the conservative side):

| Design | 10 + 10 years | 15 + 15 years | 25 + 25 years |
|---|---|---|---|
| Monthly single series | .012 / .021 / .052 / .334 | .018 / .032 / .089 / .535 | .036 / .069 / .198 / .823 |
| Daily single series, or events at 500 or 5,000/yr | .011 / .018 / .044 / .288 | .017 / .030 / .080 / .490 | .032 / .062 / .174 / .783 |
| 40–60-market panel, correlation 0.2–0.4 | .010 / .017 / .043 / .292 | .015 / .027 / .073 / .486 | .023 / .042 / .120 / .668 (20 + 20) |
| Cross-sectional long-short | .011 / .018 / .045 / .291 | — | .031 / .060 / .170 / .775 |

**Consequence (stated plainly).** The discovery protocol can detect large edges (S ≳ 0.7) given 13+ years per
window. It cannot certify realistic post-decay premia. Those must be assessed as documented premia under
Amendment 5, with estimates and intervals, not discovery gates.

**Power inputs.** Power uses k_val = the registered batch k, unless the plan pre-commits a smaller validation batch.

## 6. How these rules apply to Amendment 5 post-publication estimates

Amendment 5 post-publication results (net mean, Sharpe, drawdowns, betas) are **estimates with calibrated confidence
intervals, never pass/fail gates**.

**Intervals.**
- Equal-tailed, from a studentised bootstrap-t (B = 499) under the section-2 null model, re-centred at the estimate.
- The Sharpe SE comes from the long-run variance of its influence function.
- Crash-exposed series add the declared crash layer.

**Coverage of the 90% interval** (20,000 paths per cell):

| Series | Window | Coverage |
|---|---|---|
| iid and AR(0.2) | 60–180 months | 0.888–0.901 |
| Crash-skewed | 120–180 months | 0.882–0.905 |
| Crash-skewed | 60 months | 0.857–0.870 (a one-sided miss) |

For windows under 120 months on crash-exposed series, report the 95% interval (coverage 0.916–0.928) or apply the
crash layer.

**Comparators:** HAC-normal covers 0.844–0.892; the 12-month block percentile interval covers 0.784–0.874. So the
calibrated interval replaces the block-percentile default for any **inferential** statement under Amendment 5. Point
estimates and fixed fidelity thresholds stay as Amendment 5 defines them; this section changes only how their
uncertainty is reported.

The section-1 active-series rule applies to any post-publication beta or alpha statement.

## Also adopted from the proposal

- **Winner's-curse reporting:** add a spike-and-slab posterior with null mass 0.8 (from `reports/trial_accounting/`).
- **Framework and reporting fixes:**
  - sleeve screens use the one-factor inclusion integral;
  - `plan_check` applies the 0.30 floor;
  - Monte Carlo evidence includes a practitioner-statistic size check per design;
  - Amendment 3's "53/54 agree" is restated as "under the formulas' own model".
- **Proposal Q9** (relaxing the k ≥ 4 development threshold) is **not adopted**. It is an owner decision and was not
  requested.
