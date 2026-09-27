# Crypto perpetual funding-rate cross-section (cycle 4, E1): development FAIL (not certified, low power)

2026-09-25.
- **Plan:** `research/crypto_funding_xs/PLAN.md`, registered 03:16:21 PDT in batch cycle4_E1_E2 (k = 2, α = 0.025).
  The code was hash-registered at 04:14:10, before any perp return was computed.
- **Code:** `research/crypto_funding_xs/{core,evaluate}.py`.
- **Tests:** `tests/test_crypto_funding_xs.py` (4 pass).
- **Data:** 38,199 Binance archive files (`data/c4/binance_um`), with delisted contracts included.
- **Numbers:** `dev_results.json`, `dev_daily.csv`, `dev_weights.parquet`.
- **Validation:** 2023-01 → 2026-08 stays LOCKED and unviewed. It will not be run, because development was not
  selected.

## Result (development 2020-01 → 2022-12)

The universe had fewer than 25 eligible perps on 304 early days, which were dropped, leaving an effective T of 2.17
years.

| Book | Sharpe | Ann. mean | Max DD |
|---|---:|---:|---:|
| Gross | 1.90 | 53.3% | −18.8% |
| Base (7 bp) | **1.65** | 46.3% | −25.8% |
| Stress (20 bp, adverse 20% on delisting days) | 0.95 | 26.9% | −45.9% |

**Gate check:**

| Criterion | Value | Threshold | Result |
|---|---:|---:|---|
| Base Sharpe | 1.65 | 1.8/√2.17 = 1.22 | ✓ |
| Stress mean | +26.9% | > 0 | ✓ |
| Bootstrap p | **0.038** | < 0.025 (k = 2) | **✗** |

**Selected: NO.**

**Other evidence:**
- **P(pass | null):** 0.011 (bootstrap).
- **Placebo** (daily shuffle of the signal): p 0.002. The placebo mean is −1.92 (sd 0.69), because random sorts turn
  over heavily, so this placebo is not a mean-zero null (amendment 2, N1). It shows the sort beats random sorting; it
  is not a gate.
- **Decomposition** (per year): price 30.7%, funding received 22.6%; turnover 0.27 per day.
- **Betas:** equal-weight held universe 0.07, BTC −0.08. Alpha ≈ 44%/yr, so the result is not market beta.
- **By year:**

  | 2020 | 2021 | 2022 |
  |---:|---:|---:|
  | +15.6% | **+90.3%** | −5.6% |

  The result is one year: the 2021 leverage boom. It would fail G3 (concentration).

## Interpretation

- **Formally a FAIL.** The only miss is the batch-corrected p (0.038 against 0.025). A single registration would have
  used α = 0.05 and passed; the batch correction was fixed before any return.
- **Recorded as "FAIL, not certified (low power)"**, as pre-registered: the design was INCAPABLE for a moderate edge.
- **What it does show.** A funding-sorted book beat random sorting in 2020–2022, and it was not market beta. But its
  evidence is one year, and 2022 was negative.
- **What it does not show:** a persistent, tradable edge. It also carries a Binance jurisdiction flag: Binance is not
  available to US persons.
- **No re-specification.** No other quintile, lookback, universe, rebalance frequency or batch α.
- **Validation stays locked.** 2023–2026 has not been viewed. The honest route to evidence is a NEW forward-only
  registration of this exact frozen rule, if the user wants it. That is a user decision; it has not been done.
