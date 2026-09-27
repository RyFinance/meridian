# SEAS-FI — cycle-6 component spec

Status: draft by the FREEZE+SPEC agent, 2026-09-26, before any signal-conditioned, strategy, control or portfolio
return. Governed by FRAMEWORK.md, FRAMEWORK_ADDENDUM_1.md, A4 and A5 (ledgered). Style `seas`, engine class
`FI` (10-year government bonds (one per country)). Component 18 of k = 20 feasible components.

## Universe

Every row of `eval/candidate_list.csv` (snapshot `cycle6_eval_v1`) with `class = FI` and `qa_status = PASS`, each only between its `first_date` and `last_date` (ADDENDUM-1 items 1, 4, 5); 12 markets: FI_CA_10Y, FI_CH_10Y, FI_DE_10Y, FI_ES_10Y, FI_FR_10Y, FI_IT_10Y, FI_JP_10Y, FI_NO_10Y, FI_NZ_10Y, FI_SE_10Y, FI_UK_10Y, FI_US_10Y. Instrument i is eligible at month-end t iff it has ≥ 1 same-calendar-month return among the prior 20 years (months t+1−12k, k=1..20) and a BSV sizing vol (≥ 12 monthly returns in the trailing 36 months); the class book additionally needs ≥ 12 months of its own unscaled past returns for the class vol target (engine bsv_builder). The class portfolio is defined at t iff ≥ 4 instruments are eligible (FRAMEWORK §1). No instrument is added or removed by judgment.

Data-availability feasibility (research/cycle6/FEASIBILITY.md): 372 defined months (1995-10 .. 2026-09), max 12 eligible.

## Paper rules

Sources: Baltussen, Swinkels & van Vliet (2021), SSRN Jan-2019 version (binding reference, ADDENDUM-1 item 7);
Keloharju, Linnainmaa & Nyberg (2016), NBER WP 20815 (secondary; dossier §§3–4).
- BSV signal: "the return on an asset in a certain month over the prior 20 years (requiring at least 12-months of
  data)" (App. A.I, p. 53). KLN: "at least five years of historical data" (§3, WP pp. 9–10).
- BSV weights: w = z_t(Rank(S) − (N_t+1)/2) (App. A.II, p. 54).
- BSV sizing: positions sized "by its simple 3-year rolling volatility estimate" (pp. 54–55), with a vol floor;
  each class targets "an ex-ante volatility of 10% per annum" using "a 10-year rolling window" (p. 55).
  Implemented with engine `signal.construction = "bsv"`.

## Declared defaults (paper-silent; researcher degrees of freedom)

- Returns: synthetic daily excess returns of the data pass (FRAMEWORK §3 constructions; not futures) — *alternative not tested*.
- Ties: average ranks (dossier §1) — *alternative not tested*.
- Minimum N = 4 per class (FRAMEWORK §1) — *alternative not tested*.
- Minimum history: BSV "at least 12-months of data" read as 12 months total, i.e. min_years = 1 same-month observation in the 20-year window (director decision) — *alternative not tested*.
- Class vol target estimated from the unscaled strategy's own trailing realised returns (class_vol_method strategy_realised; BSV 10-year window, 10% target, p. 55) — *alternative not tested*.
- Sizing-vol and class-vol minimum history = 12 months (BSV silent) — *alternative not tested*.
- Sizing-vol floor = max(10% cross-sectional quantile, 2.5% p.a.) — dossier §4 reading of BSV pp. 54–55 (0.25 applies to BAB betas, not used here) — *alternative not tested*.
- No cross-sectional demeaning (BSV silent; KLN demeans) — *alternative not tested*.
- BSV rank weights instead of KLN fixed 3-per-leg equal weights — *alternative not tested*.
- min_assets = 4 (FRAMEWORK §1 frozen; BSV requires 2) — *alternative not tested*.

## Costs

Base cost per side on traded notional (FRAMEWORK §2): EQ 2 bp, FI 2 bp, FX 3 bp, CM 6 bp (FI_UST/FI_OTHER keys = 2 bp,
the FI rate; present because FI_US_10Y is listed under both FI and FI_UST). Stress = 3× base. Traded notional against
drifted weights (ADDENDUM-1 item 11). Financing: excess returns are already net of the local short rate.

## Control

Mean of 100 calendar-shuffled books (month-of-year labels permuted within each year, one permutation per year shared by all instruments; seed 20260926), same weights, lag and costs (FRAMEWORK §4).

## Execution lag

Gross paper-fidelity shadow: signal at the month-end close t, held month t+1 close-to-close, no costs, paper scaling.
Net implementable: same weights executed at the close of each instrument's first trading day of month t+1, held to the
close of its first trading day of month t+2 (one-session lag, A5 G7; engine `panel.net_period_returns`), base costs
charged. A held position with a missing return contributes zero and is counted (`unpriced`).

## Fidelity benchmark

Tier **paper-stat, published metrics only** (ADDENDUM-1 item 7): BSV 2021 Table II (p. 42, SSRN Jan-2019 version), sample 1981-01..2011-12, Sharpe -0.09; |ΔSharpe| ≤ 0.30 and coverage ≥ 95% of the 372 paper months. BSV publishes no class mean/vol: `mean_ann`/`vol_ann` are null and the engine skips them (fidelity.paper_stat_tier). KLN Table 8 has no FI row. Data-availability coverage of the BSV sample (FEASIBILITY.md, current construction): 194/372 = 0.522 → fidelity FAIL (unassessable) is expected on coverage alone.

## Crash / bandwidth declaration (FRAMEWORK §4)

Bandwidth fraction 0.20; crash layer not declared.

## Post-publication cutoff

`2019-02` — BSV: SSRN 3325720 posted 2019-01-31 -> 2019-02-01 (ADDENDUM-1 item 8).

## Inference

A4 §2 null-calibrated HAC t, one-sided (mean > 0), on the monthly net active series in the post-publication window;
B = 9,999 (FRAMEWORK §9 item 1); seed 20260943. POSITIVE iff fidelity passes AND p < 0.05/k = 0.05/20
= 0.0025 (FRAMEWORK §6). Intervals: A4 §6 studentised bootstrap-t, B = 499, 90% (95% if crash-declared and
< 120 months). Betas vs Ken French US Mkt−RF (monthly) and the US 10y synthetic excess return (A5 §D).

## Params

```json
{
 "schema": "cycle6-component-v1",
 "id": "SEAS-FI",
 "style": "seas",
 "class": "FI",
 "engine_sha256": "e9cec9f0f81d15cc13968456abcbeb24fb84d85d1a29df29bc1e1eff95469422",
 "snapshot_manifest_sha256": "ba67379be094135e32557468710a078ea9ac6f0d87516fef331e7788b22d29be",
 "inputs": {
  "daily_excess": "eval/panels/daily_excess_FI10.parquet",
  "signal_inputs": {},
  "series": {
   "eq_beta_ref": {
    "path": "eval/series/kf_us_mkt_rf_monthly.parquet",
    "market_id": "KF_US_MKT_RF"
   },
   "bond_beta_ref": {
    "path": "eval/panels/daily_excess_FI10.parquet",
    "market_id": "FI_US_10Y",
    "frequency": "daily"
   }
  }
 },
 "universe": {
  "min_assets": 4
 },
 "signal": {
  "input_lag_months": {},
  "construction": "bsv",
  "years": 20,
  "min_years": 1,
  "sizing_vol_window_months": 36,
  "sizing_vol_min_months": 12,
  "sizing_vol_floor_quantile": 0.1,
  "sizing_vol_floor_abs": 0.025,
  "class_vol_target": 0.1,
  "class_vol_window_months": 120,
  "class_vol_min_months": 12,
  "class_vol_method": "strategy_realised"
 },
 "weights": {
  "rank_vol_scale": false
 },
 "costs": {
  "bp_per_side": {
   "EQ": 2,
   "FI": 2,
   "FI_UST": 2,
   "FI_OTHER": 2,
   "FX": 3,
   "CM": 6
  },
  "stress_multiplier": 3,
  "drift": true
 },
 "control": {
  "type": "calendar_shuffle",
  "n_books": 100,
  "seed": 20260926
 },
 "inference": {
  "B": 9999,
  "seed": 20260943,
  "crash": null,
  "bandwidth_fraction": 0.2,
  "overlap": 1,
  "ci_B": 499,
  "ci_level": 0.9,
  "ci_level_crash_short": 0.95,
  "k": 20
 },
 "post_pub_cutoff": "2019-02",
 "betas": [
  "eq_beta_ref",
  "bond_beta_ref"
 ],
 "fidelity": {
  "tier": "paper_stat",
  "paper": {
   "start": "1981-01",
   "end": "2011-12",
   "mean_ann": null,
   "vol_ann": null,
   "sharpe_ann": -0.09
  },
  "thresholds": {
   "coverage_min": 0.95,
   "mean_abs": 0.02,
   "mean_rel": 0.25,
   "vol_abs": 0.02,
   "vol_rel": 0.2,
   "sharpe_abs": 0.3
  }
 }
}
```
