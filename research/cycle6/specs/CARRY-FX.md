# CARRY-FX — cycle-6 component spec

Status: draft by the FREEZE+SPEC agent, 2026-09-26, before any signal-conditioned, strategy, control or portfolio
return. Governed by FRAMEWORK.md, FRAMEWORK_ADDENDUM_1.md, A4 and A5 (ledgered). Style `carry`, engine class
`FX` (G10 currencies vs USD). Component 14 of k = 20 feasible components.

## Universe

Every row of `eval/candidate_list.csv` (snapshot `cycle6_eval_v1`) with `class = FX` and `qa_status = PASS`, each only between its `first_date` and `last_date` (ADDENDUM-1 items 1, 4); 9 markets: FX_AUD, FX_CAD, FX_CHF, FX_EUR, FX_GBP, FX_JPY, FX_NOK, FX_NZD, FX_SEK. Instrument i is eligible at month-end t iff it has a month-end foreign 3m rate at t (and the US 3m rate at t). The class portfolio is defined at t iff ≥ 4 instruments are eligible (FRAMEWORK §1). No instrument is added or removed by judgment.

Data-availability feasibility (research/cycle6/FEASIBILITY.md): 626 defined months (1974-08 .. 2026-09), max 9 eligible.

## Paper rules

Source: Koijen, Moskowitz, Pedersen & Vrugt (2018), journal JFE 127, as transcribed in A5 §A and dossier §5.
- Carry1M: current end-month carry, "not the alternative 12-month smoother" (A5 §A).
- Weights: "w_t^i = z_t(rank(C_t^i) − (N_t+1)/2)" with z_t so that "the sum of the long and short positions
  equals 1 and −1" (Eq. 19, p. 207); next-month return Eq. 20 (p. 207); monthly rebalance.
- FX carry: (S−F)/F, which with covered parity equals (i* − i)/(1 + i) (Eq. 7, p. 201).

## Declared defaults (paper-silent; researcher degrees of freedom)

- Returns: synthetic daily excess returns of the data pass (FRAMEWORK §3 constructions; not futures) — *alternative not tested*.
- Ties: average ranks (dossier §1) — *alternative not tested*.
- Minimum N = 4 per class (FRAMEWORK §1) — *alternative not tested*.
- No per-asset vol scaling (`rank_vol_scale: false`, AMP fn 10 / KMVP Eq. 19) — *alternative not tested*.
- Rates: 3m local rate as known at month-end (official daily lag 1 obs, else OECD previous-month average; data-pass short-rate rule); US rate = the FX-carry input row with the latest observation date in the month (engine takes one US series) — *alternative not tested*.
- First return month: first month after ≥ 4 carry signals exist (dossier §5 suggestion) — *alternative not tested*.

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

Tier **paper-stat** (A5 §C tier (a), binding): KMVP Table 2 Panel A Carry1M (Currencies), p. 208: mean 0.0529, vol 0.0780, Sharpe 0.68, sample 1983-11..2012-09 (sample start = first instrument date; first return month paper-silent). Bands: |Δmean| ≤ max(2pp, 0.25|m|), |Δvol| ≤ max(2pp, 0.20 v), |ΔSharpe| ≤ 0.30, coverage ≥ 95%. Secondary (non-binding): AQR Century `Currencies Carry`, ρ < 0.35 flagged only. Data-availability coverage: 347/347 = 1.000.

## Crash / bandwidth declaration (FRAMEWORK §4)

Bandwidth fraction 0.10; crash layer declared: intensity 0.2 per year, jump −6σ.

## Post-publication cutoff

`2013-09` — KMVP: NBER WP 19325 Aug 2013 -> 2013-09-01 (A5 §C fixed date).

## Inference

A4 §2 null-calibrated HAC t, one-sided (mean > 0), on the monthly net active series in the post-publication window;
B = 9,999 (FRAMEWORK §9 item 1); seed 20260939. POSITIVE iff fidelity passes AND p < 0.05/k = 0.05/20
= 0.0025 (FRAMEWORK §6). Intervals: A4 §6 studentised bootstrap-t, B = 499, 90% (95% if crash-declared and
< 120 months). Betas vs Ken French US Mkt−RF (monthly) and the US 10y synthetic excess return (A5 §D).

## Params

```json
{
 "schema": "cycle6-component-v1",
 "id": "CARRY-FX",
 "style": "carry",
 "class": "FX",
 "engine_sha256": "e9cec9f0f81d15cc13968456abcbeb24fb84d85d1a29df29bc1e1eff95469422",
 "snapshot_manifest_sha256": "ba67379be094135e32557468710a078ea9ac6f0d87516fef331e7788b22d29be",
 "inputs": {
  "daily_excess": "eval/panels/daily_excess_FX.parquet",
  "signal_inputs": {
   "fx_foreign_rate": "eval/signals/fx_foreign_rate_monthly.parquet"
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
   "us_rate": {
    "path": "eval/series/usd_rate_3m_monthly.parquet",
    "market_id": "USD_RF_3M"
   },
   "century_carry": {
    "path": "eval/series/aqr_century_monthly.parquet",
    "market_id": "Currencies Carry"
   }
  }
 },
 "universe": {
  "min_assets": 4
 },
 "signal": {
  "input_lag_months": {},
  "kind": "fx",
  "foreign_rate": "fx_foreign_rate",
  "us_rate": "us_rate"
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
  "seed": 20260939,
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
 "post_pub_cutoff": "2013-09",
 "betas": [
  "eq_beta_ref",
  "bond_beta_ref"
 ],
 "fidelity": {
  "tier": "paper_stat",
  "paper": {
   "start": "1983-11",
   "end": "2012-09",
   "mean_ann": 0.0529,
   "vol_ann": 0.078,
   "sharpe_ann": 0.68
  },
  "thresholds": {
   "coverage_min": 0.95,
   "mean_abs": 0.02,
   "mean_rel": 0.25,
   "vol_abs": 0.02,
   "vol_rel": 0.2,
   "sharpe_abs": 0.3
  },
  "secondary_reference": "century_carry",
  "secondary_rho_flag": 0.35
 }
}
```
