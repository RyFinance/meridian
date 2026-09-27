# Primary-dealer Treasury inventory → duration timing (cycle 5, experiment #1): development FAIL

2026-09-25.
- **Plan:** `research/pd_inventory/PLAN.md`, registered 13:24:14 PDT (batch k = 1).
- **Code:** `research/pd_inventory/{core,evaluate}.py`.
- **Tests:** `tests/test_pd_inventory.py` (2 pass).
- **Numbers:** `dev_results.json`, `dev_daily_active.csv`.
- **Validation:** 2012-07 → 2026-08 stays locked.

**Pre-registered power: DECISIVE at the 0.7 reference** (joint power 0.62; single-test MDE Sharpe 0.49).

## Result (development 1998-05 → 2012-06, 13.4 years)

| Series | Active Sharpe (vs exposure-matched control) | Raw Sharpe |
|---|---:|---:|
| Gross | 0.03 | 0.03 |
| Base | **0.01** (+0.06%/yr) | 0.01 |
| Stress | −0.02 | −0.03 |

**Gate check:**

| Criterion | Value | Threshold | Result |
|---|---:|---:|---|
| Active Sharpe | 0.01 | 0.49 | ✗ |
| Stress active mean | negative | > 0 | ✗ |
| Bootstrap p | 0.47 | < 0.05 | ✗ |

**Selected: NO.**

**Other evidence:**
- P(pass | null): 0.027.
- Reported shift null: p 0.42 (mean −0.03, sd 0.24).
- Mean position: −0.01.
- By year: 2008 +12% and 2009 −12% offset each other. No persistent sign.

## Interpretation

Relative inventory of long-dated coupons held by primary dealers carried no information about 10-year yield changes
over the following weeks in 1998–2012. The test was powered for S ≥ about 0.5, so a large effect is unlikely. A
small effect (S ≈ 0.3, the scout's decay-adjusted prior) cannot be excluded, and it could not have been certified
at any history length (proposal Q5). **SPENT.** No re-specification: no other buckets, lookbacks, instruments or sign.
