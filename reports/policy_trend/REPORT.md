# Bond-market policy trend → equity-index selection: development FAIL, validation not run

Run 2026-09-23. Plan: `research/policy_trend/PLAN.md` (sha256 e0ffacb5…, registered
2026-09-23T14:27:32-0700, with code hashes), registered before any equity return. The frozen code hashes
were re-verified immediately before the single development run. Code: `research/policy_trend/`. Tests:
`tests/test_policy_trend.py` (6 pass). Output: `dev_results.json`, `dev_monthly_base.csv`,
`dev_P1_weights.csv`. The ledger grows by one trial (P1).

## Result (signal months 2011-07 → 2018-12, 90 months; futures-equivalent excess returns)

| Book | Gross Sharpe | **Net Sharpe (2 bp)** | Stress (6 bp) | Ann. mean | Vol | Max DD | t |
|---|---:|---:|---:|---:|---:|---:|---:|
| **P1: long most-easing / short most-tightening** | 0.07 | **0.03** | −0.07 | +0.2% | 7.5% | −19.4% | 0.07 |
| C_MOM: 6-month index momentum | −0.56 | −0.62 | −0.75 | −2.8% | — | −25.8% | −1.71 |
| C_RATE: long lowest yield levels | 0.29 | 0.25 | 0.18 | +2.1% | — | −8.7% | 0.70 |

**Gate:** the dev Sharpe must be ≥ 1.8/√7.5 = 0.657. It is 0.03: **FAIL**. The stress mean is negative
and the permutation p is 0.39. P1 is not selected, and validation (2019–2026) stays locked.

## Nulls and controls

| Null | p (P1 vs null) | Null Sharpe mean ± sd | P(pass gate \| null) |
|---|---:|---:|---:|
| Within-date permutation of z (2,000) | 0.39 | −0.08 ± 0.37 | 2.0% |
| Circular time-shift of the z panel, every offset ≥ 18 months (160) | 0.42 | −0.09 ± 0.34 | 1.3% |

- **Against the controls:** P1's alpha on C_MOM and C_RATE is −0.2%/yr. Its correlations are
  0.02 with C_MOM and 0.30 with C_RATE.
- P1 is statistically indistinguishable from its own nulls. The nulls are well calibrated: they pass
  the registered gate 1–2% of the time.

## Diagnostics (descriptive; nothing is re-specified)

- **By year:** −2.5%, −3.8%, +8.5%, +0.4%, −1.4%, −0.4%, +3.4%, −4.3% (2011 → 2018). No regime
  carries it.
- **By economy (contribution):**
  - India +8.2 and Indonesia +7.3 points;
  - China −8.6, Korea −2.4 and the euro area −2.2.
  - Effectively zero-sum.
- **Positioning:** the US was short in 32 of 90 months (rising yields from 2013 on); the euro area was
  long 28 times.
- **Not traded:** 6-month country-index momentum (C_MOM) again lost money (−0.62). The macro-surprise
  study also found 3-month country momentum reversing (−1.05). This is a post-hoc control
  observation, and the reversal family is heavily mined.

## What the failure teaches

- **Bond yields carry no forward information for equity-index selection here.** Six-month policy
  trends in short-dated yields told nothing about next-month relative equity returns across 10
  economies in 2011–2018.
- Together with the macro-surprise null, this says that **country equity markets price macro and
  monetary information from their own economies quickly.** Neither surprise flow nor bond-market
  trends leave a monthly drift.
- **Power caveat.** With 2–3 economies per leg, the standard error is about 0.37. A true Sharpe below
  about 0.4 could not have been detected. This is evidence against a large effect, not against a
  small one.

## Classification

Bond-market policy trend → country equity selection: **SPENT**. Do not re-specify the lookback,
scaling, universe, lag or sign. Multi-country yields as a *signal source* are now PARTIALLY USED.
Untested uses remain: FX, and bond-to-bond. The FX/bond carry and momentum families that already
exist must be taken into account for either.
