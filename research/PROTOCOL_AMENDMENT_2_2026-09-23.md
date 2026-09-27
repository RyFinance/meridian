# Protocol amendment 2: null consistency and promotion guards

Status: DRAFT until its hash is in `research/preregistrations.jsonl`. Written 2026-09-23 by the director. It applies
to every family registered after it, and to every promotion decision. It does not re-grade any registered result.
Its evidence:
- `reports/null_lab2/` (gate calibration across 35 registered families and 91 candidates);
- `reports/certify/` (promotion guards and trust scorecard);
- `reports/future_lab2/` (forward power).

## N1. Mean-zero nulls (C1 P1)

- A gating null must have mean zero under H0, i.e. "no net edge".
- Shift and permutation nulls must report their own mean and sd. If |null mean| exceeds 0.10 annualised Sharpe, the
  family gates on a mean-centred block bootstrap of the same series instead. The shift or permutation p may then be
  reported, but it does not gate.
- Why: `sector_month_end` had a shift p of 0.038 at an active Sharpe of −0.43, because its null mean was −0.96.

## N2. Multiplicity at the workstream batch (C1 P2)

- The p threshold is 0.05/k, where k counts every candidate registered in the same workstream batch. The batch is
  written into each PLAN before any return is computed.
- Families registered minutes apart for the same program are one batch.

## N3. Sharpe gates unchanged (C1 P3)

- The development gate stays at 1.8/√T (2.4/√T per member of a family of k ≥ 4), with stress mean > 0 required in
  addition.
- Calibration shows 2.6–5.1% false passes at zero net mean, against 12.3% for the retired flat 0.5 gate.

## N4. Same-null P(pass | null), gated (C1 P5)

- P(pass | null) is computed from the same null that produces the gating p, and the family gates on it (≤ 0.05).
- Computing it without gating on it is not allowed (as in `credit_lead` and `index_option_breadth`).

## N5. Power disclosure (C1 P4, as disclosure)

- Each PLAN reports its simulated joint dev + validation power at true net Sharpe 0.5 and 0.7 before registration.
- If joint power at 0.7 is below 50%, a validation FAIL is recorded as "not certified (low power)", not as evidence
  of no edge. The status is still FAIL, and no re-specification is allowed.

## N6. Promotion guards (C2)

**Scope.** Nothing moves beyond FORWARD OBSERVATION without two things:
- a registered validation pass;
- `research.certify.guards.certify()` run with the candidate's natural benchmarks, and the results filed under
  `reports/certify/`.

**Guards** (thresholds are the module constants in `research/certify/guards.py`, sha256 in the ledger entry):

| Guard | Test | Pass condition |
|---|---|---|
| G1 | Beta | NW alpha t ≥ 2, and alpha ≥ 50% of the mean |
| G2 | Reduced exposure | Beats an exposure-matched control and a vol-matched control, each with t ≥ 2 |
| G3 | Concentration | Top 5% of months < 50% of P&L; max year < 35%; leave-one-year-out Sharpe ≥ 0.5× full; sign test p < 0.05 |
| G4 | One asset | Largest asset < 50% of P&L, and every leave-one-asset-out Sharpe > 0 |
| G5 | Null calibration | P(pass \| null) ≤ 0.05, from a mean-zero null |
| G6 | Post-publication | t ≥ 1.65 after the publication date, when a publication date exists |
| G7 | Execution lag | Sharpe with a one-bar execution lag ≥ 60% of the original. For calendar books the lag is the next-open execution test, not a shifted weight |

- Every guard must pass, except G4, which a single-asset strategy may carry as a flag.
- A candidate carrying a G4 flag also needs clean forward evidence under a registered forward rule before any capital
  decision. The user makes that decision.

## N7. Forward evidence

- Forward results count only through the anchored registry (`reports/forward/registry.jsonl`), evaluated by a
  sequential or fixed rule registered before the first forward window.
- The rule for `tsy_month_end_v1` is registered (`reports/future_lab2/proposed_forward_rule_tsy_month_end_v1.json`).
  It is a kill/confirm rule, and CONFIRM is not promotion.

## N8. Record correction (not a re-grade)

- `letf_rebalancing` L2 failed its registered 0.50 gate (0.48). Its "forward-only" status carries no evidential
  weight.
- Any forward test of it must be registered as a new trial.
