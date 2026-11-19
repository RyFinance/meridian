# CARRY-FX on FX-EM (cycle 7 sample)

Frozen spec `CARRY-FX` (cycle-6 ledger) run unchanged on a new sample. Sample filter (FRAMEWORK §2): Every PASS FX row of the frozen FX-EM candidate list (currencies not in the cycle-6 FX universe; FRAMEWORK §3 exclusions applied at the data level per ADDENDUM-1). All months the spec defines.
Series used only for betas/fidelity are not supplied (null). Instruments (22): FX_ARS, FX_BRL, FX_CLP, FX_COP, FX_CZK, FX_DKK, FX_HUF, FX_IDR, FX_ILS, FX_INR, FX_ISK, FX_KRW, FX_MXN, FX_MYR, FX_PEN, FX_PHP, FX_PLN, FX_RUB, FX_SGD, FX_THB, FX_TRY, FX_ZAR.

```json
{
 "schema": "cycle7-sample-v1",
 "spec_id": "CARRY-FX",
 "spec_path": "research/cycle6/specs/CARRY-FX.md",
 "spec_sha256": "4b154993dfb8f9a1ec044b01778f0c9d4adbb3eb25bbc873b476944b24c017c3",
 "sample_id": "FX-EM",
 "snapshot_root_rel": "data/cycle7/snapshot_store/versions/cycle7_fx_em_v1/view",
 "snapshot_manifest_sha256": "93ef8e0f0fbe6aebbe0eb4bf82a4a50c2c19de4461b426b7c63f09808cbba0c3",
 "membership": "eval/candidate_list.csv",
 "input_map": {
  "daily_excess": "eval/panels/daily_excess_FX.parquet",
  "signal_inputs.fx_foreign_rate": "eval/signals/fx_foreign_rate_monthly.parquet",
  "series.eq_beta_ref": null,
  "series.bond_beta_ref": null,
  "series.us_rate": {
   "path": "eval/series/usd_rate_3m_monthly.parquet",
   "market_id": "USD_RF_3M"
  },
  "series.century_carry": null
 },
 "instrument_filter": {
  "class": "FX",
  "include_market_ids": [
   "FX_ARS",
   "FX_BRL",
   "FX_CLP",
   "FX_COP",
   "FX_CZK",
   "FX_DKK",
   "FX_HUF",
   "FX_IDR",
   "FX_ILS",
   "FX_INR",
   "FX_ISK",
   "FX_KRW",
   "FX_MXN",
   "FX_MYR",
   "FX_PEN",
   "FX_PHP",
   "FX_PLN",
   "FX_RUB",
   "FX_SGD",
   "FX_THB",
   "FX_TRY",
   "FX_ZAR"
  ],
  "instrument_list_sha256": "5cb4a22458f784f1d402ed75d3967b41db2b46fd881ca618a46cb433246a3578"
 },
 "month_window": {
  "start": null,
  "end_exclusive": null
 },
 "seeds_offsets": [
  0,
  1,
  2,
  3,
  4
 ],
 "cost_mult_sensitivity": 2
}
```
