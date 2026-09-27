# PEAD attack, Amendment 1: exploratory volatility-matched placebo and shadow-ensemble power

Registered 2026-09-23, after the PLAN.md results were seen. **Exploratory.** It does not change
PLAN.md's primary test, its decision rule or its classification.

## Why

- The registered results show the real book's selection differs from P1 random selection in risk,
  not only in average return:
  - annualised volatility 9.58%, vs a P1 mean of 7.26% (95th percentile 7.90%);
  - CAPM beta 0.352, vs a P1 mean of 0.276.
- The universe is today's S&P 500. High-volatility survivors carry upward-biased returns, because
  high-volatility failures are missing from the universe.
- A model that tilts toward volatile events can therefore earn a "selection residual" that is a risk or
  survivorship tilt, not information about which announcements drift.
- This amendment asks whether the residual survives matching on pre-event volatility.

## Added books (same engine, marking, statistics and p-value formula as PLAN.md)

| Book | Permutation block for the model's (probability, Kelly size) pairs | Direction | Draws |
|---|---|---|---:|
| **P1W** | effective-date ISO week | sign(SUE) | 5,000 |
| **P1V** | effective-date ISO week × pre-event-volatility tercile | sign(SUE) | 5,000 |

- **Pre-event volatility:** the standard deviation of daily close-to-close returns (`data/raw`) over the
  60 sessions strictly before the announcement day.
- **Terciles:** cut once over all scorable window events.
- **Seeds:** `default_rng([20260923, family_id, draw])`, with P1W = 11 and P1V = 12.
- **Reported for each book:** the S1–S4 p-values, placebo means, and mean volatility/beta.
- **Reading rule (fixed now, descriptive):**
  - if the real − mean-placebo CAPM-alpha gap under P1V is less than half the gap under P1W, the
    residual is described as mostly a volatility tilt;
  - otherwise it is described as not explained by volatility.

## D5 (descriptive): power of a forward shadow ensemble

- Store the daily excess returns of the first 200 P1 draws.
- For K in {1, 5, 20, 100, 200}, report:
  - the tracking error of R minus the mean of K shadow books;
  - the years needed for 80% one-sided 5% power at the historical mean gap.

## Code

`research/pead_attack/amendment1.py` imports the registered modules and leaves them unchanged.
