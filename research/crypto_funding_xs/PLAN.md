# Crypto perpetual funding-rate cross-section (Binance USD-M): pre-registration (template v2)

Status: DRAFT until its hash is in `research/preregistrations.jsonl`. Written 2026-09-25 by the director, cycle 4,
experiment E1. Batch: E1 and E2 (`tsy_auction_demand`) are registered together, so k = 2 and α = 0.025.

**Registration order.** This PLAN is registered BEFORE the code, because the Binance archive is still downloading.
The code (`research/crypto_funding_xs/{core,evaluate}.py`) implements exactly this text. It is hash-registered in a
separate ledger entry before development runs. No funding, price or return of any perpetual has been computed or
viewed. Only file formats have been viewed: funding columns `calc_time`, `funding_interval_hours`,
`last_funding_rate`.

## 1. Mechanism

- Perpetual futures have no expiry. The funding rate transfers cash between longs and shorts every 8 h (4 h for some
  contracts) to tie the perp to spot.
- Persistent positive funding means leveraged long demand exceeds the arbitrage capital willing to short perps and
  hold spot. Shorts are paid for supplying leverage (the carry), and crowded longs are exposed to deleveraging.
- **Prediction:** in the cross-section, perps with the highest trailing funding underperform those with the lowest,
  once funding cash flows are counted.
- Literature:
  - Schmeling, Schrimpf & Todorov (2023, BIS WP), "Crypto carry": large and predictable carry, and crash risk when
    it unwinds;
  - He, Manela, Ross & von Wachter (2022), "Fundamentals of perpetual futures": large deviations and funding
    predictability;
  - practitioner "funding-rate arbitrage".
- **Direction (fixed):** long the lowest-funding quintile, short the highest-funding quintile. The reverse is never
  tested.
- **Knowledge contamination:** the director knows of the 2022 LUNA and FTX collapses and the broad 2022–25 weakness of
  altcoins against BTC. No cross-sectional funding result is known to the director for this sample.

## 2. Information and data

- **Source:** `https://data.binance.vision`, keyless: USD-M monthly `fundingRate` and `klines/1d` files for every
  archived symbol. Manifest: `data/c4/binance_um/manifest.jsonl`.
- **Survivorship:** the archive retains delisted contracts (LUNA, FTT, SRM verified), with 385 of 952 funding symbols
  no longer trading. Residual bias is about 0 (`reports/xsec_scout/REPORT.md`).
- **Point-in-time:**
  - funding rates are final at `calc_time`;
  - klines are UTC days (open 00:00);
  - there are no revisions.
- **Archive start:** 2020-01. The four months since the 2019-09 launch are missing; the development window starts in
  2020-01.

## 3. Universe, signal, construction (daily, UTC)

- **Symbols:** USDT-margined perps (the symbol ends in `USDT`). USDC and BUSD duplicates are excluded.
- **Exclusions:** index and non-crypto products whose base is BTCDOM, DEFI, FOOTBALL or BLUEBIRD. In validation,
  symbols first listed on or after 2025-01-01 whose base equals a US-listed equity ticker in the LSE stock catalog
  (tokenized stocks) are also excluded.
- **Eligibility on day t:** at least 60 days of klines before t, and a kline on day t−1.
- **Universe on day t:** the top 100 eligible perps by median daily quote volume over [t−30, t−1].
- **Signal S_i(t):** the sum of `last_funding_rate` over settlements with calc_time in [t − 7 d, t), divided by 7
  (a daily-equivalent rate). At least 10 settlements are required.
- **Portfolio at the open of day t (00:00 UTC):**
  - long the bottom quintile by S, short the top quintile;
  - equal weight within each leg, +0.5 gross long and −0.5 gross short, so dollar-neutral with gross 1.
- **Return for day t:**
  - each perp: close_t / open_t − 1;
  - minus funding paid, for settlements with calc_time in (t, t + 1 d]. Longs pay the rate × weight; shorts receive
    it.
- **Delisting:** if a held perp has no kline on day t, its day-t return is 0 in base. In stress it is an adverse 20%
  move (long −20%, short −20% through a +20% price move).
- **Costs:** turnover Σ|Δw| each day × cost per side. Base 7 bp, stress 20 bp. There is no borrow, since these are
  perps.

## 4. Windows

- **Development:** 2020-01-01 → 2022-12-31. Days on which the universe has fewer than 25 eligible perps are dropped
  from the series. The count is reported.
- **Validation (locked):** 2023-01-01 → 2026-08-31.
- **Annualisation:** 365, since crypto trades every day.

## 5. Controls and null

- **Gating null (mean-zero):** a mean-centred 21-day block bootstrap of the daily base series, 5,000 draws, seed
  20260925. P(pass | null) comes from the same bootstrap.
- **Placebo:** each day's signal is shuffled across the eligible universe (500 permutations). Its p, and the
  placebo's mean and sd, are reported.
- **Benchmarks for G1:** the equal-weight top-100 perp return (market) and BTCUSDT perp returns.

## 6. Gates

- **Development:** base Sharpe ≥ 1.8/√T (T = 3 years, so about 1.04), stress mean > 0, and bootstrap p < 0.025.
- **Validation (amendment 3, P2):** p < 0.05, stress mean > 0, and Sharpe ≥ 0.30.
- **Promotion:** guards G1–G7.
- **Implementation realism:** Binance is not available to US persons. Any promotion would need a venue the user can
  legally use. That is a G-level implementation flag recorded now.

## 7. Power

Sources: `research/power/examples/c4a_binance_funding_ls_daily.json`; `reports/power/c4a_binance_funding_ls_daily.txt`.

- SE(Sharpe): dev 0.61, val 0.55.
- Single-test MDE: Sharpe 1.21.
- Joint power at S = 0.7: 0.03 (current gates), 0.06 (amendment 3).
- **Verdict: INCAPABLE for a moderate edge.**

**Why it is still registered (amendment 3, P1).** It can only confirm a LARGE effect, and a large effect is plausible
a priori, because documented crypto carry and funding premia are an order of magnitude larger than equity anomalies.

| Scenario | Implied net Sharpe | Joint power (amendment 3) |
|---|---|---|
| IC 0.03, N = 100, ρ 0.2 | about 1.96 | 0.83 |
| IC 0.03, N = 50, ρ 0.3 | about 1.55 | 0.58 |
| IC ≤ 0.02 | ≤ 1.1 | ≤ 0.24 |

**A FAIL will be recorded as "FAIL, not certified (low power)"**; it does not show that no moderate edge exists.

## 8. Burden

- Crypto information family: 2 prior shots (crypto trend, time-series, spent).
- Project-wide: about 240 shots.

## 9. Rules

- **If development fails:** record it. No re-specification (quintile cut, lookback, rebalance frequency, universe
  size, leg subsets, sign).
- **If it passes:** freeze it, run an independent adversarial audit, and unlock only by a registered
  `VALIDATION_UNLOCK.md`.
