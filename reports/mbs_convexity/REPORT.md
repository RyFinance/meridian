# MBS negative-convexity premium (A2): development result — FAIL

2026-09-23. Plan `research/mbs_convexity/PLAN.md`, registered 2026-09-23T23:16:05-0700 (sha256 `88b9c052…`).
Code `research/mbs_convexity/{core,evaluate}.py` and `research/struct_common.py`. Tests: `tests/test_mbs_convexity.py`
(3 pass). Numbers: `dev_results.json`. Validation (2017–2026) stays locked and will not be run.

## Rule (as registered)

- Long 1.0 MBB. Short a point-in-time Treasury hedge, h_IEF·IEF + h_SHY·SHY.
- The hedge comes from a no-intercept OLS on the prior 252 sessions, refit at each month's first session, with
  coefficients clipped to [0, 2].
- The remaining (1 − h) is financed at cash.
- Costs: base 3 bp per side on MBB and 2 bp on the hedge, plus 0.3% borrow; stress ×3 and 1.0% borrow.
- Development window: 2007-03-16 (+252-session warm-up; first live 2008-04-02) → 2016-12-30, 8.75 years.

## Result

| Book | Sharpe | Ann. mean | Max DD |
|---|---:|---:|---:|
| Gross | 0.49 | 1.29% | −4.1% |
| Base | **0.40** | 1.07% | −4.1% |
| Stress | 0.21 | 0.56% | −4.3% |

**Gate check:**

| Criterion | Value | Threshold | Result |
|---|---:|---:|---|
| Base Sharpe | 0.40 | 1.8/√T = 0.61 | fail |
| Stress mean | +0.56% | > 0 | pass |
| Bootstrap p | 0.043 | < 0.025 | fail |
| P(pass \| null) | 0.006 | — | reported |

**Selected: NO.**

**Diagnostics:**
- Betas: SPY 0.03, HYG 0.007. Alpha after betas: +0.74%/yr.
- Mean hedge: IEF 0.32, SHY 0.33.
- By year:
  - 2009 +6.7% (the post-crisis MBS spread compression dominates);
  - 2008 −1.4%, 2013 −1.0% (taper);
  - 2015–16 about zero.

## Interpretation

There is a small positive spread, but it is modest and concentrated in 2009, when the Fed bought MBS. That fits a
real but small, episodic convexity premium. It is not a stand-alone edge after costs at ETF granularity. Recorded
as a **dev FAIL**; do not re-specify, e.g. with a different hedge, TBA proxies or other windows.
