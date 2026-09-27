# Treasury auction demand surprise (cycle 4, E2): development FAIL

2026-09-25.
- **Plan:** `research/tsy_auction_demand/PLAN.md`, registered 03:16:21 PDT in batch cycle4_E1_E2 (k = 2).
- **Code:** `research/tsy_auction_demand/{core,evaluate}.py`.
- **Tests:** `tests/test_tsy_auction_demand.py` (3 pass).
- **Numbers:** `dev_results.json`, `dev_daily.csv`, `dev_events.csv`.
- **Validation:** 2013–2026 stays locked and will not be run.

**Pre-registered power (amendment 3):** DECISIVE, with 0.59 joint power at a true Sharpe of 0.7 and a single-test
MDE of Sharpe 0.54. This failure is therefore informative: a moderate-or-larger version of this effect is unlikely in
2000–2012.

## Result (development: 515 nominal note/bond auctions, 2000–2012)

| Book | Sharpe | Ann. mean |
|---|---:|---:|
| Gross | −0.23 | −0.37% |
| Base | **−0.42** | −0.70% |
| Stress | −0.81 | −1.34% |

**Gate check:**

| Criterion | Value | Threshold | Result |
|---|---:|---:|---|
| Base Sharpe | −0.42 | 0.50 | ✗ |
| Stress mean | −1.34% | > 0 | ✗ |
| Bootstrap p | 0.92 | < 0.025 | ✗ |

**Selected: NO.**

**Other evidence:**
- **P(pass | null):** 0.026 (bootstrap).
- **Placebo** (w shuffled within tenor): p 0.42. The placebo mean is −0.48, sd 0.26; its negative level comes from
  costs. The real book is no better than a random assignment of demand surprises.
- **Event level:** mean −3.8 bp per unit w (week-clustered t −0.8).
- **By tenor:** no consistent sign. The 10-year is +9 bp (n 99); the 3-year is −25 bp (n 57).
- **Weak vs strong demand:** mean 5-day yield change after weak-demand auctions −4.1 bp, after strong-demand auctions
  −5.2 bp. That is no difference, and it is the wrong sign for the hypothesis.
- **Descriptive control:** being long duration after every auction has Sharpe 1.42 in 2000–2012. That is the secular
  fall in yields (duration beta), not an auction effect.

## Interpretation

At a 5-day horizon, bid-to-cover surprises carried no information about the post-auction path of yields. This was a
well-powered test. The dealer-inventory mechanism may work through dealer takedown share or the pre-auction
concession instead, but those are different measures, and testing them now would be re-specification. **SPENT.**
