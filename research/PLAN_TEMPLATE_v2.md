# <family>: pre-registration (template v2; protocol amendments 2 and 3)

Status: DRAFT until its hash (and every code hash) is in `research/preregistrations.jsonl`. State what has been
viewed before writing, including knowledge contamination (literature, the edge-graveyard OSAP results, and sibling
trials).

## 1. Economic mechanism
Who pays whom, why it persists, key literature (sample and magnitude), and post-publication decay.

## 2. Information and data
- Source, point-in-time status, timestamps, publication delay, revisions.
- Survivorship: its direction relative to the hypothesis, using `reports/survivorship_audit/`.
- Manifest hashes.

## 3. Universe, signal, direction, construction
- Fixed direction; the reverse is never tested.
- Exact formulas.
- Timing and next-tradable execution.
- Holding period and rebalance.
- Weights, costs (base/stress), financing and borrow.

## 4. Windows
Development and validation (locked), both disjoint from anything viewed.

## 5. Controls, null, batch
- Exposure-matched controls.
- A mean-zero gating null (amendment 2, N1), with P(pass | null) from the same null (N4).
- Batch k and α = 0.05/k (N2).

## 6. Gates
- **Development:** Sharpe ≥ 1.8/√T (2.4/√T if k ≥ 4), stress mean > 0, p < α.
- **Validation (amendment 3, P2):** p < 0.05/k_val, stress mean > 0, Sharpe ≥ 0.30.
- **Promotion:** guards G1–G7.

## 7. Power (amendment 2 N5; amendment 3 P1; required before registration)

**Design spec.** `research/power/examples/<name>.json` (validated against `research/power/design_schema.json`),
sha256 `<…>`. Every correlation parameter is stated explicitly, with its source (own-null sd, published estimate, or
ASSUMPTION):
- time-series autocorrelation / long-run variance ratio D = … (source: …);
- cross-sectional / event / cross-market correlation ρ = …, and the cluster/concurrency structure … (source: …);
- skew and excess kurtosis of the tested series (required for carry and crash-prone books) = …;
- stress-cost drag in Sharpe units = (stress − base cost per year) / vol = …;
- batch k = … ⇒ α = 0.05/k = ….

**Command:** `PYTHONPATH=. .venv/bin/python -m research.power.plan_check <spec> --mc 2000`. Report:
`reports/power/<name>.json` (sha256 `<…>`).

| Quantity | Value |
|---|---|
| Raw observations (dev / val) | … / … |
| Effective observations after D and deff (dev / val) | … / … |
| SE of annualised Sharpe (dev / val) | … / … |
| MDE (80%, α), single test, all years: Sharpe and natural units | … |
| Joint dev+val power at true net Sharpe 0.3 / 0.5 / 0.7 / 1.0 | … |
| False pass: P(pass both \| S = 0); at an S = +0.05 leak | … ; … |
| Years for 80% joint power at 0.7 | … |
| Implied net Sharpe at the plan's stated primitives (IC, bp per event, …) and its joint power | … |
| **Verdict** (DECISIVE / MARGINAL / INCAPABLE) | … |

**Interpretation, fixed before any return is seen.**
- If the verdict is MARGINAL or INCAPABLE, a validation FAIL is recorded as "FAIL, not certified (low power)". It is
  not evidence of no edge. The status is still FAIL, and no re-specification is allowed.
- If the verdict is INCAPABLE, either state why the test is still worth running (e.g. it can only kill, or it can
  only confirm a large effect that is plausible a priori), or do not register it.
- Attach the plan_check scenario table covering the uncertain primitives (IC, ρ, costs, N).

## 8. Burden
- Shots in the information family and project-wide (`reports/trial_accounting/`).
- Sibling trials.

## 9. If development fails / passes
- **Fails:** record it. No sign reversal, horizon change, threshold tweak, universe tweak, subperiod rescue or
  parameter search.
- **Passes:** freeze it, then run an independent adversarial audit. Validation is unlocked only by a registered
  `VALIDATION_UNLOCK.md`.
