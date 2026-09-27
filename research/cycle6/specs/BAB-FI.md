# BAB-FI — cycle-6 component spec

Status: draft by the FREEZE+SPEC agent, 2026-09-26, before any signal-conditioned, strategy, control or portfolio
return. Governed by FRAMEWORK.md, FRAMEWORK_ADDENDUM_1.md, A4 and A5 (ledgered). Style `bab`, engine class
`FI_UST` (US Treasury maturity buckets). Component 16 of k = 20 feasible components.

## Universe

Every row of `eval/candidate_list.csv` (snapshot `cycle6_eval_v1`) with `class = FI_UST` and `qa_status = PASS`, each only between its `first_date` and `last_date` (ADDENDUM-1 items 1, 4, 5); 4 markets: FI_US_10Y, FI_US_2Y, FI_US_30Y, FI_US_5Y. Instrument i is eligible at month-end t iff it has an FP monthly beta at month-end t: ≥ 12 monthly log returns in the last 12 months (vol) and ≥ 36 months in the last 60 (correlation) vs the equal-weighted universe, and beta > 0. The class portfolio is defined at t iff ≥ 4 instruments are eligible (FRAMEWORK §1). No instrument is added or removed by judgment.

Data-availability feasibility (research/cycle6/FEASIBILITY.md): 561 defined months (1980-01 .. 2026-09), max 4 eligible.

## Paper rules

Source: Frazzini & Pedersen (2014), accepted MS May 10, 2013 (MS pages; dossier §2), Treasury section.
- Monthly data: "If we only have access to monthly data, we use rolling 1 and 5-year windows and require at least
  12 and 36 observations" (MS pp. 16–17); fn 12: daily data not available for "U.S. Treasury bonds".
- Market: "an equally weighted portfolio of all bonds in the database" (MS p. 15).
- Beta β̂ = ρ̂ σ̂_i/σ̂_m (Eq. 14), shrinkage "w = 0.6 and β^XS = 1" (Eq. 15, MS p. 17).
- Legs Eq. 16 (MS p. 19), each rescaled "to have a beta of one at portfolio formation" (Eq. 17); monthly rebalance.

## Declared defaults (paper-silent; researcher degrees of freedom)

- Returns: synthetic daily excess returns of the data pass (FRAMEWORK §3 constructions; not futures) — *alternative not tested*.
- Leg betas = Σ w·β̂ with shrunk betas (dossier §2); ties average rank — *alternative not tested*.
- Beta ≤ 0 → ineligible (engine bab_weights) — *alternative not tested*.
- FP monthly-data method (MS pp. 16–17): 1-year vol and 5-year correlation windows on monthly log returns, minimum 12 and 36 observations, shrink 0.6 toward 1; benchmark = equal-weighted average of the eligible buckets' monthly returns (`ew_universe`, FP MS p. 15; ADDENDUM-1 item 10)
- Correlation on non-overlapping 1-month returns (overlap_months 1): FP's monthly fallback states no overlap — *alternative not tested*.
- 4 constant-maturity buckets (2/5/10/30y) instead of FP's 7 CRSP buckets — *alternative not tested*.

## Costs

Base cost per side on traded notional (FRAMEWORK §2): EQ 2 bp, FI 2 bp, FX 3 bp, CM 6 bp (FI_UST/FI_OTHER keys = 2 bp,
the FI rate; present because FI_US_10Y is listed under both FI and FI_UST). Stress = 3× base. Traded notional against
drifted weights (ADDENDUM-1 item 11). Financing: excess returns are already net of the local short rate.

## Control

Mean of 100 seeded random-rank placebo books (iid uniform signal on the SAME eligible set each month, same weight builder, lag and costs; seed 20260926) (FRAMEWORK §4; A5 §D).

## Execution lag

Gross paper-fidelity shadow: signal at the month-end close t, held month t+1 close-to-close, no costs, paper scaling.
Net implementable: same weights executed at the close of each instrument's first trading day of month t+1, held to the
close of its first trading day of month t+2 (one-session lag, A5 G7; engine `panel.net_period_returns`), base costs
charged. A held position with a missing return contributes zero and is counted (`unpriced`).

## Fidelity benchmark

Tier **paper-stat** (ADDENDUM-1 item 10): FP 2014 Table VI US Treasury BAB (MS p. T6): mean 0.0204, vol 0.0243, Sharpe 0.81, sample 1952-01..2012-03 (>10y bucket missing 1962-08..1971-12). Bands as FRAMEWORK §5. Data-availability coverage: 386/723 = 0.534 → fidelity FAIL (unassessable) is expected on coverage alone.

## Crash / bandwidth declaration (FRAMEWORK §4)

Bandwidth fraction 0.10; crash layer declared: intensity 0.2 per year, jump −6σ.

## Post-publication cutoff

`2011-01` — FP: NBER WP 16601 Dec 2010 (later candidate) -> 2011-01-01 (ADDENDUM-1 item 8).

## Inference

A4 §2 null-calibrated HAC t, one-sided (mean > 0), on the monthly net active series in the post-publication window;
B = 9,999 (FRAMEWORK §9 item 1); seed 20260941. POSITIVE iff fidelity passes AND p < 0.05/k = 0.05/20
= 0.0025 (FRAMEWORK §6). Intervals: A4 §6 studentised bootstrap-t, B = 499, 90% (95% if crash-declared and
< 120 months). Betas vs Ken French US Mkt−RF (monthly) and the US 10y synthetic excess return (A5 §D).

## Params

```json
{
 "schema": "cycle6-component-v1",
 "id": "BAB-FI",
 "style": "bab",
 "class": "FI_UST",
 "engine_sha256": "e9cec9f0f81d15cc13968456abcbeb24fb84d85d1a29df29bc1e1eff95469422",
 "snapshot_manifest_sha256": "ba67379be094135e32557468710a078ea9ac6f0d87516fef331e7788b22d29be",
 "inputs": {
  "daily_excess": "eval/panels/daily_excess_FI_UST.parquet",
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
  "benchmark": "ew_universe",
  "beta_frequency": "monthly",
  "vol_window_months": 12,
  "vol_min_months": 12,
  "corr_window_months": 60,
  "corr_min_months": 36,
  "overlap_months": 1,
  "log_returns": true,
  "shrink_w": 0.6
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
  "type": "random_rank",
  "n_books": 100,
  "seed": 20260926
 },
 "inference": {
  "B": 9999,
  "seed": 20260941,
  "crash": {
   "intensity_per_year": 0.2,
   "jump_sd": -6
  },
  "bandwidth_fraction": 0.1,
  "overlap": 1,
  "ci_B": 499,
  "ci_level": 0.9,
  "ci_level_crash_short": 0.95,
  "k": 20
 },
 "post_pub_cutoff": "2011-01",
 "betas": [
  "eq_beta_ref",
  "bond_beta_ref"
 ],
 "fidelity": {
  "tier": "paper_stat",
  "paper": {
   "start": "1952-01",
   "end": "2012-03",
   "mean_ann": 0.0204,
   "vol_ann": 0.0243,
   "sharpe_ann": 0.81
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
