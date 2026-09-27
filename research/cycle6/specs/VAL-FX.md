# VAL-FX — cycle-6 component spec

Status: draft by the FREEZE+SPEC agent, 2026-09-26, before any signal-conditioned, strategy, control or portfolio
return. Governed by FRAMEWORK.md, FRAMEWORK_ADDENDUM_1.md, A4 and A5 (ledgered). Style `value`, engine class
`FX` (G10 currencies vs USD). Component 11 of k = 20 feasible components.

## Universe

Every row of `eval/candidate_list.csv` (snapshot `cycle6_eval_v1`) with `class = FX` and `qa_status = PASS`, each only between its `first_date` and `last_date` (ADDENDUM-1 items 1, 4); 9 markets: FX_AUD, FX_CAD, FX_CHF, FX_EUR, FX_GBP, FX_JPY, FX_NOK, FX_NZD, FX_SEK. Instrument i is eligible at month-end t iff it has month-end spot and point-in-time CPI (foreign and US) at t and at every month t−66..t−54. The class portfolio is defined at t iff ≥ 4 instruments are eligible (FRAMEWORK §1). No instrument is added or removed by judgment.

Data-availability feasibility (research/cycle6/FEASIBILITY.md): 560 defined months (1980-02 .. 2026-09), max 9 eligible.

## Paper rules

Source: AMP (2013). "the 5-year change in purchasing power parity" (p. 937): log of the average spot rate
4.5–5.5 years ago over today's spot "minus the log difference in the change in CPI in the foreign country
relative to the U.S." (p. 937). Weights: AMP Eq. 1 (p. 938), $1 long/$1 short, monthly.

## Declared defaults (paper-silent; researcher degrees of freedom)

- Returns: synthetic daily excess returns of the data pass (FRAMEWORK §3 constructions; not futures) — *alternative not tested*.
- Ties: average ranks (dossier §1) — *alternative not tested*.
- Minimum N = 4 per class (FRAMEWORK §1) — *alternative not tested*.
- Missing month inside a signal window → ineligible (dossier §1) — *alternative not tested*.
- No per-asset vol scaling (`rank_vol_scale: false`, AMP fn 10 / KMVP Eq. 19) — *alternative not tested*.
- Spot orientation USD per unit foreign currency (dossier §1) — *alternative not tested*.
- CPI point-in-time: CPI of the latest release with available_date ≤ t (data-pass lag rule default_2m; latest vintage, not first release); `cpi_lag_months: 0` because the panel is already PIT — *alternative not tested*.
- FX_EUR uses German CPI (no euro-area CPI in the data pass) — *alternative not tested*.
- Averaging on month-end spot of months t−66..t−54; CPI change measured with the same window mean — *alternative not tested*.

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

Tier **AQR-class** (FRAMEWORK §5): gross shadow vs `VALLS_VME_FX` (eval/series/aqr_vme_monthly.parquet) on identical months: n ≥ 60, ρ ≥ 0.65, 0.70 ≤ β ≤ 1.30, TE/σ_ref ≤ 0.90. **scale_convention: none** — the AQR benchmark is not ex-post vol-scaled (dossier §7); native units ($1 long / $1 short). Data-availability overlap with the benchmark: 539 months. Unassessable = FAIL.

## Crash / bandwidth declaration (FRAMEWORK §4)

Bandwidth fraction 0.20; crash layer not declared.

## Post-publication cutoff

`2009-04` — AMP: SSRN 1363476 posted 2009-03-06 -> 2009-04-01 (ADDENDUM-1 item 8; dossier §6).

## Inference

A4 §2 null-calibrated HAC t, one-sided (mean > 0), on the monthly net active series in the post-publication window;
B = 9,999 (FRAMEWORK §9 item 1); seed 20260936. POSITIVE iff fidelity passes AND p < 0.05/k = 0.05/20
= 0.0025 (FRAMEWORK §6). Intervals: A4 §6 studentised bootstrap-t, B = 499, 90% (95% if crash-declared and
< 120 months). Betas vs Ken French US Mkt−RF (monthly) and the US 10y synthetic excess return (A5 §D).

## Params

```json
{
 "schema": "cycle6-component-v1",
 "id": "VAL-FX",
 "style": "value",
 "class": "FX",
 "engine_sha256": "e9cec9f0f81d15cc13968456abcbeb24fb84d85d1a29df29bc1e1eff95469422",
 "snapshot_manifest_sha256": "ba67379be094135e32557468710a078ea9ac6f0d87516fef331e7788b22d29be",
 "inputs": {
  "daily_excess": "eval/panels/daily_excess_FX.parquet",
  "signal_inputs": {
   "fx_spot": "eval/signals/fx_spot_monthly.parquet",
   "fx_cpi": "eval/signals/fx_cpi_pit_monthly.parquet"
  },
  "series": {
   "eq_beta_ref": {
    "path": "eval/series/kf_us_mkt_rf_monthly.parquet",
    "market_id": "KF_US_MKT_RF"
   },
   "bond_beta_ref": {
    "path": "eval/panels/daily_excess_FI10.parquet",
    "market_id": "FI_US_10Y",
    "frequency": "daily"
   },
   "aqr_ref": {
    "path": "eval/series/aqr_vme_monthly.parquet",
    "market_id": "VALLS_VME_FX"
   },
   "cpi_us": {
    "path": "eval/series/cpi_us_pit_monthly.parquet",
    "market_id": "US_CPI"
   }
  }
 },
 "universe": {
  "min_assets": 4
 },
 "signal": {
  "input_lag_months": {},
  "kind": "fx_ppp",
  "spot": "fx_spot",
  "cpi": "fx_cpi",
  "cpi_us": "cpi_us",
  "window_lo_months": 54,
  "window_hi_months": 66,
  "cpi_lag_months": 0
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
  "seed": 20260936,
  "crash": null,
  "bandwidth_fraction": 0.2,
  "overlap": 1,
  "ci_B": 499,
  "ci_level": 0.9,
  "ci_level_crash_short": 0.95,
  "k": 20
 },
 "post_pub_cutoff": "2009-04",
 "betas": [
  "eq_beta_ref",
  "bond_beta_ref"
 ],
 "fidelity": {
  "tier": "aqr_class",
  "reference": "aqr_ref",
  "scale_convention": "none",
  "thresholds": {
   "n_min": 60,
   "rho_min": 0.65,
   "beta_lo": 0.7,
   "beta_hi": 1.3,
   "te_ratio_max": 0.9
  }
 }
}
```
