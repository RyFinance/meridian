# TSMOM-FI on FI-NEW (cycle 7 sample)

Frozen spec `TSMOM-FI` (cycle-6 ledger) run unchanged on a new sample. Sample filter (FRAMEWORK §2): Every PASS FI row of the frozen FI-NEW candidate list (10y government bonds not in the cycle-6 FI 10y universe; RU masked from 2022-03 per ADDENDUM-2). All months the spec defines.
Series used only for betas/fidelity are not supplied (null). Instruments (15): FI_BR_10Y, FI_CL_10Y, FI_CN_10Y, FI_GR_10Y, FI_HU_10Y, FI_ID_10Y, FI_IN_10Y, FI_KR_10Y, FI_MX_10Y, FI_MY_10Y, FI_NG_10Y, FI_RU_10Y, FI_SG_10Y, FI_TH_10Y, FI_TR_10Y.

```json
{
 "schema": "cycle7-sample-v1",
 "spec_id": "TSMOM-FI",
 "spec_path": "research/cycle6/specs/TSMOM-FI.md",
 "spec_sha256": "188d8cc948c7f49d9428c01f322387a787f717abd223c8fbc1f98ae4b629409b",
 "sample_id": "FI-NEW",
 "snapshot_root_rel": "data/cycle7/snapshot_store/versions/cycle7_fi_new_v1/view",
 "snapshot_manifest_sha256": "67aba1106c304193835f15354eca245e14cbc2c77da13325ecbe0cfe1ceffe4b",
 "membership": "eval/candidate_list.csv",
 "input_map": {
  "daily_excess": "eval/panels/daily_excess_FI10.parquet",
  "series.eq_beta_ref": null,
  "series.bond_beta_ref": null,
  "series.aqr_ref": null
 },
 "instrument_filter": {
  "class": "FI",
  "include_market_ids": [
   "FI_BR_10Y",
   "FI_CL_10Y",
   "FI_CN_10Y",
   "FI_GR_10Y",
   "FI_HU_10Y",
   "FI_ID_10Y",
   "FI_IN_10Y",
   "FI_KR_10Y",
   "FI_MX_10Y",
   "FI_MY_10Y",
   "FI_NG_10Y",
   "FI_RU_10Y",
   "FI_SG_10Y",
   "FI_TH_10Y",
   "FI_TR_10Y"
  ],
  "instrument_list_sha256": "ddd5e07c095ee87a2f5d2dcc53f832d0d08ea270735f30ca9668306d202e62bf"
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
