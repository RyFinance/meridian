# TSMOM-CM — cycle-6 component spec

Status: draft by the FREEZE+SPEC agent, 2026-09-26, before any signal-conditioned, strategy, control or portfolio
return. Governed by FRAMEWORK.md, FRAMEWORK_ADDENDUM_1.md, A4 and A5 (ledgered). Style `tsmom`, engine class
`CM` (commodities). Component 4 of k = 20 feasible components.

## Universe

Every row of `eval/candidate_list.csv` (snapshot `cycle6_eval_v1`) with `class = CM` and `qa_status = PASS`, each only between its `first_date` and `last_date` (ADDENDUM-1 items 1, 4); 12 markets: CM_BRENT, CM_COPPER, CM_CORN, CM_GASOLINE, CM_GOLD, CM_NATGAS, CM_PALLADIUM, CM_PLATINUM, CM_SILVER, CM_SOYBEANS, CM_WHEAT, CM_WTI. Instrument i is eligible at month-end t iff it has ≥ 756 valid daily excess-return observations through the month-end close of t (vol min_obs) and a monthly excess return in each of months t−11..t. The class portfolio is defined at t iff ≥ 3 instruments are eligible (FRAMEWORK §1). No instrument is added or removed by judgment.

Data-availability feasibility (research/cycle6/FEASIBILITY.md): 227 defined months (2007-11 .. 2026-09), max 12 eligible.

## Paper rules

Source: Moskowitz, Ooi & Pedersen (2012), transcribed in A5 §A and Sol's component-1 prereg (A5-C1,
ledgered `7fd50331…`). Rules as binding text (A5-C1 "Paper provenance and exact rule"):
- Signal: "sign of the contract's cumulative **excess return** over the immediately preceding 12 months"
  (A5-C1; MOP §2.4 p.233, §3.2 pp.233–234). Includes month t, skips none.
- Position: "`sign_i,t × 0.40 / σ_i,t`" with σ "formed from information through the decision close" (A5-C1; MOP Eq. 5 p.236).
- Aggregation: "the **equal average** of these instrument returns across all historically available eligible
  instruments" (A5-C1).
- Volatility: EW mean-centred squared daily excess returns, "annualized by 261", decay "`δ=60/61`" (A5 §A).
- Warm-up: "At least **756 valid earlier daily observations**" — a researcher default, not a paper parameter (A5-C1).
- Rebalance: one-month holding, monthly rebalance (A5 §A).

## Declared defaults (paper-silent; researcher degrees of freedom)

- Returns: synthetic daily excess returns of the data pass (FRAMEWORK §3 constructions; not futures) — *alternative not tested*.
- Exact zero sign → flat but counted in N (A5-C1 declared default) — *alternative not tested*.
- No floor/cap on 0.40/σ in the gross shadow (A5-C1) — *alternative not tested*.
- Instrument with a missing month inside the 12-month window is ineligible that month — *alternative not tested*.

## Costs

Base cost per side on traded notional (FRAMEWORK §2): EQ 2 bp, FI 2 bp, FX 3 bp, CM 6 bp (FI_UST/FI_OTHER keys = 2 bp,
the FI rate; present because FI_US_10Y is listed under both FI and FI_UST). Stress = 3× base. Traded notional against
drifted weights (ADDENDUM-1 item 11). Financing: excess returns are already net of the local short rate.

## Control

Exposure-matched always-long control: same instruments, same 0.40/σ scaling, lag and costs; active = net − m̄·control, m̄ = mean over the window of book/control net exposure (FRAMEWORK §4; A4 §1; ADDENDUM-1 item 11).

## Execution lag

Gross paper-fidelity shadow: signal at the month-end close t, held month t+1 close-to-close, no costs, paper scaling.
Net implementable: same weights executed at the close of each instrument's first trading day of month t+1, held to the
close of its first trading day of month t+2 (one-session lag, A5 G7; engine `panel.net_period_returns`), base costs
charged. A held position with a missing return contributes zero and is counted (`unpriced`).

## Fidelity benchmark

Tier **AQR-class** (FRAMEWORK §5): gross shadow vs `TSMOM^CM` (eval/series/aqr_tsmom_monthly.parquet) on identical months: n ≥ 60, ρ ≥ 0.65, 0.70 ≤ β ≤ 1.30, TE/σ_ref ≤ 0.90. **scale_convention: none** — the AQR benchmark is not ex-post vol-scaled (dossier §7); native units (40%/σ positions). Data-availability overlap with the benchmark: 222 months. Unassessable = FAIL.

## Crash / bandwidth declaration (FRAMEWORK §4)

Bandwidth fraction 0.20; crash layer not declared.

## Post-publication cutoff

`2011-01` — MOP 2011-01-01 (A5 §C fixed date; FRAMEWORK §4).

## Inference

A4 §2 null-calibrated HAC t, one-sided (mean > 0), on the monthly net active series in the post-publication window;
B = 9,999 (FRAMEWORK §9 item 1); seed 20260929. POSITIVE iff fidelity passes AND p < 0.05/k = 0.05/20
= 0.0025 (FRAMEWORK §6). Intervals: A4 §6 studentised bootstrap-t, B = 499, 90% (95% if crash-declared and
< 120 months). Betas vs Ken French US Mkt−RF (monthly) and the US 10y synthetic excess return (A5 §D).

## Params

```json
{
 "schema": "cycle6-component-v1",
 "id": "TSMOM-CM",
 "style": "tsmom",
 "class": "CM",
 "engine_sha256": "e9cec9f0f81d15cc13968456abcbeb24fb84d85d1a29df29bc1e1eff95469422",
 "snapshot_manifest_sha256": "ba67379be094135e32557468710a078ea9ac6f0d87516fef331e7788b22d29be",
 "inputs": {
  "daily_excess": "eval/panels/daily_excess_CM.parquet",
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
   },
   "aqr_ref": {
    "path": "eval/series/aqr_tsmom_monthly.parquet",
    "market_id": "TSMOM^CM"
   }
  }
 },
 "universe": {
  "min_assets": 3
 },
 "signal": {
  "input_lag_months": {},
  "lookback_months": 12,
  "target_vol": 0.4
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
  "type": "always_long"
 },
 "inference": {
  "B": 9999,
  "seed": 20260929,
  "crash": null,
  "bandwidth_fraction": 0.2,
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
 "vol": {
  "com_days": 60,
  "annualisation": 261,
  "min_obs": 756,
  "lag_obs": 0
 },
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
