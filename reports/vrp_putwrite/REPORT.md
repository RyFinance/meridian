# Monthly SPY put writing: development FAIL, validation not run

- **Plan:** `research/vrp_putwrite/PLAN.md`, registered with code hashes before any return.
  Tests: `tests/test_vrp_putwrite.py` (4 pass).
- **Data:** local LSE OPRA prints (`data/lse/options_etf_1d/SPY.parquet`) and raw SPY closes.
  All 67 development cycles (2014-06 → 2019-12) had valid near-ATM entry prints.

| (development, per-cycle excess over T-bills) | Gross | Base (1% of premium) | Stress (5%) |
|---|---:|---:|---:|
| Sharpe | 0.74 | 0.72 | 0.63 |
| β on SPY | 0.50 | 0.50 | 0.50 |
| CAPM α / yr (NW t) | −0.03% (−0.02) | −0.18% (−0.11) | −0.81% (−0.49) |
| **Active vs 0.5 × SPY: Sharpe** | −0.01 | **−0.05** | −0.23 |
| Active bootstrap p | 0.52 | 0.56 | 0.71 |

- **Comparisons:**
  - control 0.5 × SPY: Sharpe 0.87;
  - hit rate 81%;
  - worst cycle −8.3%;
  - max drawdown −10.6%.
- **Insurance premium** (premium − payoff)/K: 0.44% per cycle (t 1.75). It is fully explained by
  the 0.5 delta earning the equity premium; there is no residual.
- **Gate:** active Sharpe must be ≥ 0.76. It is −0.05. **FAIL.** Deflated-Sharpe probability
  0.0007. Validation stays locked.

**Reading.** In 2014–2019, monthly at-the-money SPY put writing was a lower-volatility way to hold
half the equity market. It earned the equity premium and no separate volatility-insurance premium
after costs. Together with 1-day put writing (P1–P3) and VIX-futures carry (hold-out 0.29, −86%
drawdown), the index-volatility premium is **SPENT** for this project's instruments and costs. It
is not independent of equity beta.
