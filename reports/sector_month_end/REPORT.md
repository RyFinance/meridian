# Month-end index extension in LQD / MBB / TIP (B1): development result — FAIL

2026-09-23. Plan `research/sector_month_end/PLAN.md`, registered 2026-09-23T23:16:05-0700 (sha256 `59212987…`).
Code `research/sector_month_end/{core,evaluate}.py`. Tests: `tests/test_sector_month_end.py` (3 pass). Numbers:
`dev_results.json`, `dev_daily_active.csv`. Validation (2015-01 → 2026-08) stays locked and will not be run.

This was a mechanism-informed follow-on to `tsy_month_end`, not independent corroboration. It asked whether the
month-end index-extension flow also shows up in corporate, MBS and TIPS index funds once their duration is hedged
out.

## Rule (as registered)

- For each sector ETF, hold the rate-hedged excess return over the last 3 sessions of each month.
  - Hedge: PIT IEF/SHY OLS, refit monthly.
  - Weights: `tsy_month_end.core.weights(sess, "last")`.
- The book is the equal-weight average over the live sectors.
- Control: average weight × hedged return (active = book − control).
- Development window: 2003-01-02 → 2014-12-31.

## Result

| Book | Active Sharpe | Active ann. |
|---|---:|---:|
| Gross | 0.24 | +0.42% |
| Base | **−0.43** | −0.76% |
| Stress | −1.70 | −3.12% |

- **Per sector (base):** LQD −0.19, MBB −0.93, TIP −0.41.
- **Active by year:** negative in 10 of 11 years (2004–2014).
- **Gate check:**

| Criterion | Value | Threshold | Result |
|---|---:|---:|---|
| Active Sharpe | −0.43 | 1.8/√T = 0.55 | **fail** |
| Stress active mean | −3.12% | > 0 | **fail** |
| Circular-shift p | 0.038 | < 0.05 | nominal pass |
| Bootstrap p | 0.99 | — | — |
| P(pass \| null) | 0.000 | — | — |

**Selected: NO.**

- **Placebo positions 3–15:** active Sharpe −0.43 to −1.52. The month-end window is the "least bad" of them, which is
  why the shift p is 0.038.
- **Quarter-end vs other months:** −7.9 vs −5.5 bp.
- **Correlation of monthly active with the TLT window:** −0.26.

## Interpretation

- The gross month-end spread is tiny (+0.4%/yr) and does not survive hedge-rebalancing and trading costs.
- **Null-design lesson.** The shift null had mean −0.96 and sd 0.31, because every shifted window pays costs. The
  null therefore tested "better than a random 3-day window", not "positive". A p of 0.038 alongside a negative
  Sharpe shows the null was not mean-zero under H0. This is flagged to the Workstream C gate-consistency review, and
  future shift nulls should be centred or paired with a mean-zero bootstrap.
- The Treasury month-end effect does not extend to credit, MBS or TIPS spread returns once duration is hedged. That
  is weakly consistent with a Treasury-index-specific flow, and it is not corroboration.

Recorded as a **dev FAIL**; do not re-specify.
