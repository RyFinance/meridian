# crypto_funding_xs: the exact frozen claim (cycle 5, C1)

Documentation of an existing frozen object; nothing here changes it. The authoritative sources are the registered
files below. If this summary and the code ever disagree, the code wins.

## Hashes

| File | sha256 | Registered |
|---|---|---|
| research/crypto_funding_xs/PLAN.md | `ad64d6cf9a48ca3973498625fbcba0ec5c96af0f31b9f376fb271ca8011a0b51` | 2026-09-25T03:16:21-0700 |
| research/crypto_funding_xs/core.py | `f7811a55696aae0b4694874c564a0d0f08e14fc57d69ccdec7f157343b668f88` | 2026-09-25T04:14:10-0700 (code registration) |
| research/crypto_funding_xs/evaluate.py | `e9ef68b9797de7a8f35b7f6666467ae2911672a6deab9dfb3bb7abaa9321157e` | same |
| research/struct_common.py | `3535d7ff…` | same |
| data manifest at registration (first 38,199 lines of data/c4/binance_um/manifest.jsonl) | `dd4cc187bf2f…` | same |
| reports/crypto_funding_xs/dev_results.json (as run, 04:15 PDT) | `e1edbec6cb1b9c8ddd6652b159c3868d89a0ae9b66bc1770034c9afeff105657` | — |

## The hypothesis, exactly

| Element | Frozen value |
|---|---|
| Venue / products | Binance USD-M perpetuals whose symbol ends in `USDT`; delisted contracts included via data.binance.vision |
| Exclusions | Base in {BTCDOM, DEFI, FOOTBALL, BLUEBIRD}. In validation: symbols first listed ≥ 2025-01-01 whose base equals an LSE-catalog US stock ticker |
| Eligibility on day t | ≥ 60 days since the first kline; a kline exists on t−1; the signal is defined; median volume is defined |
| Universe | Top 100 eligible by the median daily quote volume over [t−30, t−1] (min_periods 15) |
| Funding signal | Σ `last_funding_rate` over settlements with calc_time in [t − 7 d, t), divided by 7. At least 10 settlements |
| Ranking | Ascending signal rank within the universe (ties broken by column order, method "first") |
| Legs | k = max(1, ⌊0.2·n⌋). LONG the k lowest-signal perps at +0.5/k each; SHORT the k highest at −0.5/k each. Dollar-neutral, gross 1 |
| Rebalance / execution | Daily, at the 00:00 UTC open of day t |
| Day-t return | Σ w·(close_t/open_t − 1) − Σ w·(funding with calc_time in (t, t+1d]), i.e. longs pay and shorts receive |
| Costs | Σ\|Δw\| × 7 bp (base) or 20 bp (stress). No borrow |
| Delisting | A held perp with no day-t kline earns 0 (base, gross) or an adverse 20% (stress) |
| Minimum universe | Days with fewer than 25 universe members are dropped |
| Development window | 2020-01-01 → 2022-12-31 (annualisation 365) |
| Validation window | 2023-01-01 → 2026-08-31: **LOCKED, UNVIEWED** |
| Development gate | Sharpe ≥ 1.8/√T; stress mean > 0; mean-centred 21-day block-bootstrap p < 0.025 (batch k = 2) |
| Validation gate | p < 0.05, stress mean > 0, Sharpe ≥ 0.30 (amendment 3) |
| Direction | Fixed: long low funding, short high funding. The reverse is never tested |

## Recorded outcome (as run)

- Sharpe 1.65 against the 1.22 gate; stress mean +26.9%/yr.
- Bootstrap p 0.038 against the 0.025 threshold: **development FAIL**.
- 2021 alone was +90%.

## Data-integrity defect found in cycle 5 (2026-09-25)

The development run completed at 04:15 PDT on an **incomplete archive**.
- **What was missing:** the parallel downloader (`binance_fast`) silently skipped the symbols whose S3 listing
  failed, which is 69 USDT symbols and 3,281 files.
- **Which of those matter for development:** 29 symbols have development-window files, including early perps such as
  XRP, LINK, LTC, TRX, XLM, ZEC, DASH and NEO.
- **When they arrived:** the serial downloader fetched them later, at 15:29–15:36 UTC.
- **Where this is handled:** `research/crypto_funding_xs/CORRECTED_DATA_REMEASUREMENT.md` (protocol amendment 1,
  section C: corrected data, unchanged spec, registered before the re-run, an audit rather than a new trial).
