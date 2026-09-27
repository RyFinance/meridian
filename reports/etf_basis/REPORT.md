# Bond-ETF liquidity provision (HYG/LQD vs own iBoxx index): development FAIL, validation not run

- **Plan:** `research/etf_basis/PLAN.md`, registered with code hashes before any return.
- **Tests:** `tests/test_etf_basis.py` (3 pass).
- **Development:** 2012-01 → 2017-12, effective after the 250+250-observation warm-up.

| | Gross | Base (3 bp) | Stress (10 bp) |
|---|---:|---:|---:|
| B: long after basis z ≤ −2, 5 sessions, HYG + LQD | Sharpe 0.86 | 0.71 | 0.37 |
| C_REV: own-price reversal trigger | 0.73 | 0.64 | 0.42 |

- **Exposure:** average position 0.27 (HYG) and 0.26 (LQD).
- **Active return vs exposure-matched (B − C_EXP):**
  - Sharpe **0.34**, +0.75%/yr; stress −0.22%/yr;
  - gate 0.74: **FAIL**.
- **B − C_REV:** +0.82%/yr (Sharpe 0.35).
- **Circular-shift null (500):**
  - null active Sharpe −0.18 ± 0.39; 95th percentile 0.50, 99th 0.74;
  - **p = 0.10**; P(pass | null) = 1.4%.
- **Per trigger, 5-session forward return, descriptive:**
  - HYG +50.3 bp (146 trigger days) against +10.8 bp unconditional;
  - LQD +0.2 bp (133) against +9.2 bp.
- **Active return by year:** 2014 +2.3% and 2016 +2.0% (energy-credit stress); other years about
  zero.

**Reading.**
- A weak, HY-only, stress-concentrated sign of liquidity-provision returns. It is within the null
  band at development and does not survive stress costs.
- **Not a survivor.** The HYG-only pattern is a post-hoc observation.
- A HY-only liquidity-provision rule would have to be registered as a new, forward-only candidate.
  The big stress episodes (2018 Q4, 2020, 2022) sit in the locked validation window and must not be
  used to choose it.

**Classification:** bond-ETF basis reversion (HYG + LQD, z ≤ −2, 5 days) is **SPENT**. Do not
re-specify the threshold, hold or pair.
