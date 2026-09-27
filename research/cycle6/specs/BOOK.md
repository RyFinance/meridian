# BOOK — cycle-6 combined Styles-Everywhere book spec (schema cycle6-book-v1)

Status: draft by the FREEZE+SPEC agent, 2026-09-26, before any component, control or portfolio return. Rule fixed in
FRAMEWORK §7 and §9 item 3; weights per A5 §E. Must be ledgered before the first combined return.

## Sleeves

- **Candidates** = all 20 feasible components (FEASIBILITY.md): TSMOM-EQ, TSMOM-FI, TSMOM-FX, TSMOM-CM, XSMOM-EQ, XSMOM-FI, XSMOM-FX, XSMOM-CM, VAL-EQ, VAL-FI, VAL-FX, VAL-CM, CARRY-FI, CARRY-FX, BAB-EQ, BAB-FI, SEAS-EQ, SEAS-FI, SEAS-FX, SEAS-CM.
- **Inclusion (mechanical, engine-enforced):** `runner.load_sleeves` includes a candidate only if (i) its
  `metrics.json` exists under `components_root`, (ii) the trial ledger holds an `ok` row for that id whose spec hash
  equals the output's `run.spec_sha256`, and (iii) `metrics.fidelity.pass` is true. Fidelity FAIL, missing or
  mismatched outputs are excluded and reported in the book's `sleeves` block. POSITIVE status is not an inclusion
  criterion (FRAMEWORK §7). Each included sleeve enters as its **net implementable** monthly series (`net.csv` `ret`),
  with its `gross_exposure` used for the gross cap.
- **Core** = 60% SPY / 40% IEF, dividends reinvested (adjclose), monthly rebalanced, net excess of USD 3m cash
  (A5 §E), cost 2 bp per side (Sol's ETF defaults: 1 bp half-spread + 1 bp commission).

## Weights (A5 §E exactly; engine `book.build_book`)

At month-end t: trailing 60 monthly net excess returns of eligible sleeves (earlier months only, ≥ 60 common
observations); covariance shrunk 25% toward its diagonal; nonnegative equal-risk-contribution weights summing to one;
fallback normalised 1/σ from lagged individual vols (≥ 12 months, diagonal variances, ADDENDUM-1 item 11); else cash.
Scale to 10% annual ex-ante vol with the same covariance, capped at 2× gross notional/NAV. Cash earns
max(0, T-bill − 0.50 pp); financed exposure pays T-bill + 2 pp. T-bill = H.15 3-month CMT at the previous month-end.
Monthly rebalance at the next session (sleeve series are already lagged); no book-level trading cost beyond sleeve
costs (ADDENDUM-1 item 11). No expected-return input.

## Post-publication window

Latest `post_pub_cutoff` among the **included** components — computed dynamically by `runner.compute_book`
(`max` over included sleeves' metrics). If no component is included (core only), the fallback
`core.post_pub_cutoff` = 2019-02 (the latest cutoff among all candidates) applies — declared default, alternative not
tested.

## Inference and reporting

Book POSITIVE iff the post-publication net Sharpe's calibrated 90% interval excludes zero (FRAMEWORK §6; A4 §6,
B = 499, seed 20260946). A5 §E information-only: leverage for 12% total return from min(post-pub mean, one-sided 75%
stationary-block LCB; 10,000 draws, block 12, seed 20260925), cap 2×; MDD distribution from 10,000 paired
stationary-block 10-year paths (block 12, seed 20260925).

## Core start and warm-up (director decision 2026-09-26)

- The core sleeve enters from its **first defined month**, i.e. the first month in which both SPY and IEF are
  priced (IEF from 2002-07); no pre-inception proxy (A5 §E).
- Until 60 common monthly sleeve observations exist, the book uses the A5 §E fallback: normalised 1/σ weights from
  lagged individual vols (≥ 12 months); cash if none is available (A5 §E as written).

## Known engine gaps (reported, not repaired)

- A5 §E "actual instrument margin/borrow charges used if higher" is not modelled (financing spread only).
- A5 §E "if trend fails its primary gate, no Core Premia Book is evaluated" is superseded by FRAMEWORK §9 item 3;
  `book.py` has no trend-pass precondition.

## Params

```json
{
 "schema": "cycle6-book-v1",
 "id": "BOOK",
 "engine_sha256": "e9cec9f0f81d15cc13968456abcbeb24fb84d85d1a29df29bc1e1eff95469422",
 "snapshot_manifest_sha256": "ba67379be094135e32557468710a078ea9ac6f0d87516fef331e7788b22d29be",
 "components_root": "reports/cycle6_core_premia/components",
 "candidates": [
  "TSMOM-EQ",
  "TSMOM-FI",
  "TSMOM-FX",
  "TSMOM-CM",
  "XSMOM-EQ",
  "XSMOM-FI",
  "XSMOM-FX",
  "XSMOM-CM",
  "VAL-EQ",
  "VAL-FI",
  "VAL-FX",
  "VAL-CM",
  "CARRY-FI",
  "CARRY-FX",
  "BAB-EQ",
  "BAB-FI",
  "SEAS-EQ",
  "SEAS-FI",
  "SEAS-FX",
  "SEAS-CM"
 ],
 "core": {
  "daily_excess": "eval/series/core_etf_excess_daily.parquet",
  "markets": [
   "SPY",
   "IEF"
  ],
  "weights": [
   0.6,
   0.4
  ],
  "cost_bp_per_side": 2,
  "post_pub_cutoff": "2019-02"
 },
 "tbill": {
  "path": "eval/series/tbill_3m_daily.parquet",
  "market_id": "TB3M"
 },
 "book": {
  "cov_months": 60,
  "shrink": 0.25,
  "vol_target": 0.1,
  "gross_cap": 2.0,
  "cash_spread": 0.005,
  "financing_spread": 0.02,
  "fallback_min_obs": 12
 },
 "inference": {
  "ci_B": 499,
  "ci_level": 0.9,
  "seed": 20260946
 },
 "leverage_calc": {
  "target_total_ann": 0.12,
  "lcb_level": 0.75,
  "n_draws": 10000,
  "mean_block": 12,
  "seed": 20260925,
  "cap": 2.0
 },
 "mdd_sim": {
  "n_paths": 10000,
  "horizon_months": 120,
  "mean_block": 12,
  "seed": 20260925
 }
}
```
