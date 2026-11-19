# TSMOM-CM on CM-NEW (cycle 7 sample)

Frozen spec `TSMOM-CM` (cycle-6 ledger) run unchanged on a new sample. Sample filter (FRAMEWORK §2): Every PASS CM row of the frozen CM-NEW candidate list (commodities not in the cycle-6 CM set). All months the spec defines.
Series used only for betas/fidelity are not supplied (null). Instruments (16): CM_ALUMINIUM, CM_CARBON_CCA, CM_CARBON_EUA, CM_COCOA, CM_COFFEE, CM_COTTON, CM_HEATINGOIL, CM_LEAD, CM_LEANHOGS, CM_LIVECATTLE, CM_NICKEL, CM_PROPANE, CM_SOYBEANOIL, CM_SUGAR, CM_TIN, CM_ZINC.

```json
{
 "schema": "cycle7-sample-v1",
 "spec_id": "TSMOM-CM",
 "spec_path": "research/cycle6/specs/TSMOM-CM.md",
 "spec_sha256": "6bd6f56b5119f10e18b2d32837152cce65c977e2ebd668d6576bb73217e3ebdd",
 "sample_id": "CM-NEW",
 "snapshot_root_rel": "data/cycle7/snapshot_store/versions/cycle7_cm_new_v1/view",
 "snapshot_manifest_sha256": "de67e9f2b10bd49687f7801de7029f60c9ca08ad47ea0fbb0544eeddbb8d628f",
 "membership": "eval/candidate_list.csv",
 "input_map": {
  "daily_excess": "eval/panels/daily_excess_CM.parquet",
  "series.eq_beta_ref": null,
  "series.bond_beta_ref": null,
  "series.aqr_ref": null
 },
 "instrument_filter": {
  "class": "CM",
  "include_market_ids": [
   "CM_ALUMINIUM",
   "CM_CARBON_CCA",
   "CM_CARBON_EUA",
   "CM_COCOA",
   "CM_COFFEE",
   "CM_COTTON",
   "CM_HEATINGOIL",
   "CM_LEAD",
   "CM_LEANHOGS",
   "CM_LIVECATTLE",
   "CM_NICKEL",
   "CM_PROPANE",
   "CM_SOYBEANOIL",
   "CM_SUGAR",
   "CM_TIN",
   "CM_ZINC"
  ],
  "instrument_list_sha256": "c5ca4df365b256e75bb54b96a96d45665acbc0613bf7daa1ff02a42e5fa163de"
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
