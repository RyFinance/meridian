# BAB-EQ — cycle-6 component spec

Status: draft by the FREEZE+SPEC agent, 2026-09-26, before any signal-conditioned, strategy, control or portfolio
return. Governed by FRAMEWORK.md, FRAMEWORK_ADDENDUM_1.md, A4 and A5 (ledgered). Style `bab`, engine class
`EQ` (country equity indices). Component 15 of k = 20 feasible components.

## Universe

Every row of `eval/candidate_list.csv` (snapshot `cycle6_eval_v1`) with `class = EQ` and `qa_status = PASS`, each only between its `first_date` and `last_date` (ADDENDUM-1 items 1, 4); 34 markets: EQ_AT, EQ_AU, EQ_BE, EQ_BR, EQ_CA, EQ_CH, EQ_CL, EQ_DE, EQ_DK, EQ_ES, EQ_FI, EQ_FR, EQ_HK, EQ_ID, EQ_IE, EQ_IL, EQ_IN, EQ_IT, EQ_JP, EQ_KR, EQ_MX, EQ_MY, EQ_NL, EQ_NO, EQ_NZ, EQ_PL, EQ_SE, EQ_SG, EQ_TH, EQ_TR, EQ_TW, EQ_UK, EQ_US, EQ_ZA. Instrument i is eligible at month-end t iff it has an FP beta at month-end t: ≥ 120 valid daily returns in the last 252 rows and ≥ 750 valid overlapping 3-day return pairs with the class benchmark in the last 1,260 rows (engine fp_betas), and beta > 0. The class portfolio is defined at t iff ≥ 4 instruments are eligible (FRAMEWORK §1). No instrument is added or removed by judgment.

Data-availability feasibility (research/cycle6/FEASIBILITY.md): 329 defined months (1999-05 .. 2026-09), max 33 eligible.

## Paper rules

Source: Frazzini & Pedersen (2014), accepted MS May 10, 2013 (MS pages; dossier §2).
- Beta: β̂ = ρ̂ σ̂_i/σ̂_m (Eq. 14, MS p. 17); "a 1-year rolling standard deviation for volatilities and a 5-year
  horizon for the correlation" (MS p. 17); "1-day log returns … and overlapping 3-day log returns" (MS p. 17).
- Minimum data: "at least 6 months (120 trading days)" for vol and "3 years (750 trading days)" for correlation (MS p. 17).
- Shrinkage: "we set w = 0.6 and β^XS = 1" (Eq. 15, MS p. 17).
- Legs: ranked on beta, w_H = k(z − z̄)^+, w_L = k(z − z̄)^− (Eq. 16, MS p. 19); "both portfolios are rescaled to
  have a beta of one at portfolio formation" (Eq. 17, MS p. 19); "rebalanced every calendar month" (MS p. 19).

## Declared defaults (paper-silent; researcher degrees of freedom)

- Returns: synthetic daily excess returns of the data pass (FRAMEWORK §3 constructions; not futures) — *alternative not tested*.
- Market for beta: equal-weighted daily average of eligible PASS instruments of the class (EQ countries) (ADDENDUM-1 item 10) — *alternative not tested*.
- 1-year vol window = 252 rows, 5-year correlation window = 1,260 rows of the class's union trading calendar (engine fp_betas counts rows, not the instrument's own days) — *alternative not tested*.
- Leg betas = Σ w·β̂ with shrunk betas (dossier §2); ties average rank — *alternative not tested*.
- Beta ≤ 0 → ineligible (engine bab_weights) — *alternative not tested*.

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

Tier **AQR-class** (FRAMEWORK §5): gross shadow vs `Equity indices Defensive` (eval/series/aqr_century_monthly.parquet) on identical months: n ≥ 60, ρ ≥ 0.65, 0.70 ≤ β ≤ 1.30, TE/σ_ref ≤ 0.90. **scale_convention: none** — the AQR benchmark is not ex-post vol-scaled (dossier §7); native units (beta-1 legs). Data-availability overlap with the benchmark: 321 months. Construct differs: AQR Defensive uses 36-month rolling monthly betas vs an EW index portfolio (declared, ADDENDUM-1 item 10). Unassessable = FAIL.

## Crash / bandwidth declaration (FRAMEWORK §4)

Bandwidth fraction 0.10; crash layer declared: intensity 0.2 per year, jump −6σ.

## Post-publication cutoff

`2011-01` — FP: NBER WP 16601 Dec 2010 (later candidate) -> 2011-01-01 (ADDENDUM-1 item 8).

## Inference

A4 §2 null-calibrated HAC t, one-sided (mean > 0), on the monthly net active series in the post-publication window;
B = 9,999 (FRAMEWORK §9 item 1); seed 20260940. POSITIVE iff fidelity passes AND p < 0.05/k = 0.05/20
= 0.0025 (FRAMEWORK §6). Intervals: A4 §6 studentised bootstrap-t, B = 499, 90% (95% if crash-declared and
< 120 months). Betas vs Ken French US Mkt−RF (monthly) and the US 10y synthetic excess return (A5 §D).

## Params

```json
{
 "schema": "cycle6-component-v1",
 "id": "BAB-EQ",
 "style": "bab",
 "class": "EQ",
 "engine_sha256": "e9cec9f0f81d15cc13968456abcbeb24fb84d85d1a29df29bc1e1eff95469422",
 "snapshot_manifest_sha256": "ba67379be094135e32557468710a078ea9ac6f0d87516fef331e7788b22d29be",
 "inputs": {
  "daily_excess": "eval/panels/daily_excess_EQ.parquet",
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
   "bab_bench": {
    "path": "eval/series/bab_benchmarks_daily.parquet",
    "market_id": "BAB_BENCH_EQ_EW",
    "frequency": "daily_raw"
   },
   "aqr_ref": {
    "path": "eval/series/aqr_century_monthly.parquet",
    "market_id": "Equity indices Defensive"
   }
  }
 },
 "universe": {
  "min_assets": 4
 },
 "signal": {
  "input_lag_months": {},
  "benchmark": "bab_bench",
  "beta_frequency": "daily",
  "vol_window_days": 252,
  "vol_min_days": 120,
  "corr_window_days": 1260,
  "corr_min_days": 750,
  "overlap_days": 3,
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
  "seed": 20260940,
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
