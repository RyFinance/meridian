# Protocol amendment 4: PROPOSAL (not registered)

Status: **PROPOSAL.** It is not in `research/preregistrations.jsonl` and has no force until the user approves it and
it is registered. Written 2026-09-25 by the director. It merges two independent audits of amendment 3 and the power
framework:
- `reports/power_audit_a1/REPORT.md` (a code and math audit);
- `reports/power_audit_a2/REPORT.md` (an independent Monte Carlo, written without reading `research/power`).

It would apply only to families registered after it. No historical result is re-graded.

## What the audits agree on

1. **Size control is sound for correctly gated series.**
   - Joint false pass under amendment 3 is 0.16–0.49% across iid, fat-tailed, stochastic-volatility, long-short,
     calendar-time event and daily-autocorrelated processes.
   - The cycle-4 operating characteristics (section 7) reproduce within 1.3 pp.
2. **The one cycle-4 Monte Carlo miss is resolved** (the 17-sleeve screen: 0.475 vs 0.507):
   - +1.1 pp is a real bias: the analytic treats sleeve inclusion as independent, but inclusion is correlated
     through the common factor. The exact one-factor integral gives 0.486.
   - About +2.0 pp is Monte Carlo noise (3k paths; 100k paths give 0.485–0.489).
   - It is not a coding, autocorrelation, Sharpe-estimator or gate-calibration error, and the direction is
     conservative.
3. **"53/54 agree" is weak evidence.** Every Monte Carlo check simulates the formula's own model, and 15 plug the
   formula's own SE or D into the test statistic. Size checks against practitioner statistics find real
   oversizing:
   - a literal HAC t: 1.3–2.3× nominal on monthly and weekly windows;
   - the block bootstrap on monthly AR(0.3) or crash-skewed series: 1.4–2× nominal.
4. **Specific defects:**
   - Long-only books gated on raw returns false-pass 6.5% (beta).
   - The stress leg is nearly inert until the cost drag exceeds the realised Sharpe.
   - D < 1 inputs let effective observations exceed raw ones; this flipped commodity_roll's verdict.
   - The breadth parameter can be misread as the average pairwise residual correlation, which overstates Sharpe up
     to 7×.
   - Power figures used k_val = 1 instead of the batch k.
   - The N(0, 0.5²) winner's-curse prior barely shrinks.
   - The retrospective "→ DECISIVE" labels for insider and etf_hybrids assumed the old dev gate; they are MARGINAL
     (about 0.28).
5. **Sharpe 0.7 is a convenience reference, not a principled one.**
   - The realistic post-decay effect is about 0.23–0.29.
   - At S = 0.23 the new gate has 3% joint power on 12 + 12 years, and 80% power is unreachable while the floor is
     0.30.
   - The protocol is therefore a large-effect detector. That is acceptable, but it must be stated honestly.

## Proposed rules

| # | Rule | Source |
|---|---|---|
| Q1 | **The gating series is net of an exposure-matched control** for any design with directional exposure, in both dev and validation. G2 becomes a gate. Event designs gate only on a calendar-time portfolio. | A2 4.1 |
| Q2 | **Registering the p-test.** A HAC t may be registered only if a synthetic Monte Carlo of ≥ 20,000 paths at the plan's own n, frequency, D and α shows its size is ≤ 1.25× nominal. Otherwise the plan uses the mean-centred block bootstrap. | A1 Q1 |
| Q3 | **Bootstrap validity.** The block length is at least max(n^⅓, 2(1+ρ̂₁)/(1−ρ̂₁)), estimated on dev only. If n < 180, \|skew\| > 1, or ρ̂₁ > 0.2, the plan shows the bootstrap's simulated size on its own spec. If it exceeds 1.25α, the gating α is scaled down to restore nominal size. | A2 4.2 |
| Q4 | **Validation stress leg:** stress-cost Sharpe ≥ 0.30 (the same economic floor as net). The dev stress rule (mean > 0) is unchanged. | A2 4.3 |
| Q5 | **Honest power reporting.** Joint power is reported at S = 0.25, 0.5 and 0.7. The verdict bars stay at 0.7. The plan states that 0.7 is a large-effect reference and that edges at or below 0.30 cannot be certified at any length. | A2 4.4 |
| Q6 | **Power inputs.** D < 1 is floored at 1 unless it is estimated from the full dev null with an SE, and the verdict must hold at D = 1. Effective observations may not exceed raw observations. ρ_bet comes from IC or spread dispersion, or from the literal ρ̄ of held bets, never from the pairwise correlation of market-neutral residuals. Power uses k_val = the batch k unless a smaller validation batch is pre-committed. | A1 Q2–Q4 |
| Q7 | **Winner's curse.** Also report a spike-and-slab posterior, with null mass 0.8 by default (from `reports/trial_accounting/`). | A1 Q5 |
| Q8 | **Framework fixes:** the sleeve-screen power uses the one-factor inclusion integral; `plan_check` applies the 0.30 floor; Monte Carlo evidence includes at least one practitioner-statistic size check per design; and the amendment-3 text "53/54 agree" is restated with that caveat. | A1 Q6–Q8 |
| Q9 (optional; user's decision) | For k ≥ 4, replace 2.4/√T with 1.8/√T plus p < 0.05/k. Family-wise false pass stays ≤ 0.25%, and per-candidate power at 0.7 rises by about 15 pp. | A2 4.5 |

## Net effect

- Q1, Q3 and Q4 tighten the rules where the audits found leaks: beta, under-coverage, and inert costs.
- Q9 loosens one redundant leg; it is optional.
- Q5 changes reporting only.
- Nothing here re-opens any failed family.

**Action for the user:** approve Q1–Q8, with or without Q9. The director then registers this file, renamed without
"PROPOSAL", together with the framework code fixes.
