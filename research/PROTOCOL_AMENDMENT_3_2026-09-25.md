# Protocol amendment 3: power first, and a calibrated validation gate

Status: DRAFT until its hash is in `research/preregistrations.jsonl`. Written 2026-09-25 by the director. It applies
to families registered after it. It does not re-grade any registered result: every earlier FAIL stays a FAIL.

Evidence: `reports/power/REPORT.md` (the power calculator in `research/power/`, 53 of 54 Monte Carlo checks agree),
`reports/null_lab2/`, and `reports/trial_accounting/`.

## Why

- **The 0.75 absolute validation gate is an effect-size filter, not a test.** At a true net Sharpe of 0.7 its pass
  probability falls towards 0 as the window grows, so no history length gives 80% power.
- **Every registered two-stage family had 21–32% joint power at Sharpe 0.7.**
- **Validation misses were the likely outcome even for a real edge.** The winner's-curse-corrected dev estimates
  are tsy_month_end 0.20–0.45 and commodity_roll −0.39 to 0.48.
- **Breadth does not raise power at a fixed net Sharpe.** Power depends on years, κ and the gate. Breadth only
  raises the Sharpe that a given per-bet edge can reach. A parallel, independent package
  (`research/power_framework/`) reaches the same conclusion ("asset count does not multiply power").

## P1. Power check before registration (makes N5 binding)

- **Required inputs.** Every PLAN attaches a `research/power` design spec with every correlation parameter stated,
  plus the `plan_check` output (JSON sha256 in the ledger entry).
- **Verdicts:**
  - DECISIVE: joint power at 0.7 ≥ 50% and P(pass both | S=0) ≤ 5%;
  - MARGINAL: anything between DECISIVE and INCAPABLE;
  - INCAPABLE: joint power at 0.7 below 25%, or false-pass above 10%.
- **INCAPABLE designs are not registered**, unless the plan states that the test can only confirm a LARGE effect
  that is plausible a priori. It must also state the Sharpe that effect implies and the joint power at that Sharpe.
- **For any design that is not DECISIVE**, a validation FAIL is recorded as "FAIL, not certified (low power)".

## P2. Validation gate for new families (replaces the fixed 0.75 Sharpe)

Validation passes only if all of these hold:
1. One-sided p < 0.05/k_val on the validation window, where k_val is the number of candidates taken to validation
   together. The p comes from a mean-centred block bootstrap, or a HAC t, whichever the PLAN registers.
2. Stress-cost mean > 0.
3. Net base Sharpe ≥ 0.30 (an economic floor).
4. The promotion guards G1–G7 are reported. As before (amendment 2, N6), they must pass before anything moves beyond
   forward observation.

**Operating characteristics** on 12 + 11.6-year windows (`reports/power/validation_gate_oc.csv`):

| | Current 0.75 gate | This gate |
|---|---|---|
| Joint false pass at S = 0 | 0.08% | 0.25% |
| Joint power at S = 0.7 | 0.29 | 0.42 |

This is the uniformly most powerful test at its size. The development gate (1.8/√T, 2.4/√T for k ≥ 4, p < 0.05/k,
stress mean > 0) is unchanged.

## P3. Reporting

- Every result reports its winner's-curse-corrected estimate (conditional median-unbiased, and the N(0, 0.5²)
  posterior mean) alongside the raw estimate.
- Every result reports the burden context from `reports/trial_accounting/`: shots within the information family and
  project-wide, and the project M_eff (Li–Ji ≈ 25).

## P4. Template

New plans use `research/PLAN_TEMPLATE_v2.md`.
