# TSMOM-CM on CM-DEEP (cycle 7 sample)

Frozen spec `TSMOM-CM` (cycle-6 ledger) run unchanged on a new sample. Sample filter (FRAMEWORK §2): Every PASS CM row of the frozen CM-DEEP candidate list (cycle-6 CM markets with pre-2007 history + new series). Evaluated holding months < 2007-12 (cycle-6 TSMOM-CM first month).
Series used only for betas/fidelity are not supplied (null). Instruments (7): CM_GASOLINE, CM_GOLD, CM_HEATINGOIL, CM_NATGAS, CM_PROPANE, CM_SILVER, CM_WTI.

```json
{
 "schema": "cycle7-sample-v1",
 "spec_id": "TSMOM-CM",
 "spec_path": "research/cycle6/specs/TSMOM-CM.md",
 "spec_sha256": "6bd6f56b5119f10e18b2d32837152cce65c977e2ebd668d6576bb73217e3ebdd",
 "sample_id": "CM-DEEP",
 "snapshot_root_rel": "data/cycle7/snapshot_store/versions/cycle7_cm_deep_v1/view",
 "snapshot_manifest_sha256": "3db28c32308b52fa631ac3176ae1cdce77b8930fb7d503e1a513a57aff464e18",
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
   "CM_GASOLINE",
   "CM_GOLD",
   "CM_HEATINGOIL",
   "CM_NATGAS",
   "CM_PROPANE",
   "CM_SILVER",
   "CM_WTI"
  ],
  "instrument_list_sha256": "d47f2a4d595e4220a8d52a9f057b90370bd8e8398bc270b55a79d0fe224f5114"
 },
 "month_window": {
  "start": null,
  "end_exclusive": "2007-12"
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
