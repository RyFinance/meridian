# TSMOM-FI on FI-DEEP (cycle 7 sample)

Frozen spec `TSMOM-FI` (cycle-6 ledger) run unchanged on a new sample. Sample filter (FRAMEWORK §2): Every PASS FI row of the frozen FI-DEEP candidate list (cycle-6 FI 10y markets with daily pre-1993 history). Evaluated holding months < 1993-04 (cycle-6 TSMOM-FI first month).
Series used only for betas/fidelity are not supplied (null). Instruments (6): FI_CA_10Y, FI_DE_10Y, FI_JP_10Y, FI_SE_10Y, FI_UK_10Y, FI_US_10Y.

```json
{
 "schema": "cycle7-sample-v1",
 "spec_id": "TSMOM-FI",
 "spec_path": "research/cycle6/specs/TSMOM-FI.md",
 "spec_sha256": "188d8cc948c7f49d9428c01f322387a787f717abd223c8fbc1f98ae4b629409b",
 "sample_id": "FI-DEEP",
 "snapshot_root_rel": "data/cycle7/snapshot_store/versions/cycle7_fi_deep_v1/view",
 "snapshot_manifest_sha256": "a7387d19fd5ba59825ea2769b694599cd70c2e9ae6159f7e9232e43be365bd09",
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
   "FI_CA_10Y",
   "FI_DE_10Y",
   "FI_JP_10Y",
   "FI_SE_10Y",
   "FI_UK_10Y",
   "FI_US_10Y"
  ],
  "instrument_list_sha256": "4a39b8010d24d7a42b40fb434d1e837efc41854a3a552802a6e49670b2039b6f"
 },
 "month_window": {
  "start": null,
  "end_exclusive": "1993-04"
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
