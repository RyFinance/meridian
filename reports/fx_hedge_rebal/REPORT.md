# Month-end FX hedge-rebalancing flow (B2): development result — FAIL

2026-09-23. Plan `research/fx_hedge_rebal/PLAN.md`, registered 2026-09-23T23:16:05-0700 (sha256 `7a18fb1b…`).
Code `research/fx_hedge_rebal/{core,evaluate}.py`. Tests: `tests/test_fx_hedge_rebal.py` (5 pass). Numbers:
`dev_results.json`, `dev_events.csv`. Validation (2021-01 → 2026-08) stays locked and will not be run.

## Rule (as registered; Melvin–Prins 2015 mechanism)

- On the last weekday of each month (D), for EUR, GBP, AUD, JPY and CAD:
  - rel = US minus foreign month-to-date equity index return, using closes strictly before D;
  - position = sign(rel), i.e. long the foreign currency if US equities outperformed, because foreign
    investors must sell USD to rebalance their hedges.
- Hold from 08:00 to 16:00 Europe/London on D. Prices come from LSE 1-minute FX (5-minute look-back).
- Costs: base 1 bp per side, stress 3 bp.
- Development: month-ends 2015-01 → 2020-12, 360 valid events.

## Result

| Book | Sharpe | Mean per event |
|---|---:|---:|
| Gross | 0.40 | +2.6 bp |
| Base | **0.09** | +0.6 bp |
| Stress | −0.52 | −3.4 bp |

**Gate check:**

| Criterion | Value | Threshold | Result |
|---|---:|---:|---|
| Base Sharpe | 0.09 | 1.8/√T = 0.72 | fail |
| Stress mean | −3.4 bp | > 0 | fail |
| Permutation p | 0.18 | < 0.05 | fail |
| P(pass \| null) | 0.001 | — | — |

**Selected: NO.**

- **Hit rate:** 55.6%.
- **Per pair (bp per event):** GBP 4.7, JPY 3.4, CAD 3.1, AUD 0.9, EUR 0.8.
- **By year (bp):**

  | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 |
  |---:|---:|---:|---:|---:|---:|
  | +3.6 | −5.1 | +12.0 | +0.9 | +4.9 | −0.8 |

- **Quarter-end vs other months:** 0.7 vs 3.5 bp. That is the opposite of the mechanism, which predicts larger
  quarter-end flows.
- **By |rel| tercile:** 2.3 / −0.1 / 5.6 bp, which is not monotone.
- **Control C_USDSHORT** (always short USD in the window): Sharpe 0.29.

## Interpretation

- The gross sign is right, but the effect is about 2.6 bp per event. That is about one round-trip spread, and it is
  not significant.
- The quarter-end pattern goes the wrong way for the hedge-rebalancing story.
- The published effect (Melvin & Prins, 2015, sample to 2012) is not visible in the 2015–2020 intraday data at
  tradeable size.

Recorded as a **dev FAIL**; do not re-specify, e.g. with other windows, thresholds or a fix-time focus.
