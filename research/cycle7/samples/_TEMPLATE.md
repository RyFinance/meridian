# TEMPLATE -- not a sample (never ledgered; the runner refuses it)

Copy to `research/cycle7/samples/<SPEC>__<SAMPLE>.md` (e.g. `CARRY-FX__FX-EM.md`), fill in, then ledger its
SHA-256 in `research/cycle7_prereg_ledger.md` with ID `<SPEC>__<SAMPLE>` BEFORE running. The runner also requires
the snapshot manifest hash and the runner code hash to be ledgered, and the file to contain exactly one json block.

Fields:
- `spec_path` / `snapshot_root_rel`: repo-relative. `membership`: relative to the snapshot root (inside it).
- `input_map`: every spec input location must be covered. Keys: `daily_excess`, `signal_inputs.<name>`,
  `series.<name>`, or an original spec path (replaces every occurrence). Values: a path relative to the snapshot
  root; for `series.<name>` also `{"path": ..., "market_id": ...}`, or `null` for a diagnostic-only series
  (betas / fidelity reference) that the sample does not supply.
- `instrument_filter`: `class` (= spec class) and at most one of `include_market_ids` / `exclude_market_ids`
  (neither = every PASS row of the class). Optional `instrument_list_sha256` = sha256 of the sorted ids joined by
  `\n`; checked against the filtered list before any return is read.
- `month_window`: evaluated holding months `start <= m < end_exclusive` (null = open). The engine always runs on
  the full loaded history for warm-up.

```json
{
 "schema": "cycle7-sample-v1",
 "spec_id": "CARRY-FX",
 "spec_path": "research/cycle6/specs/CARRY-FX.md",
 "spec_sha256": "4b154993dfb8f9a1ec044b01778f0c9d4adbb3eb25bbc873b476944b24c017c3",
 "sample_id": "TEMPLATE",
 "snapshot_root_rel": "<store>/versions/<version>/view",
 "snapshot_manifest_sha256": "<64 hex>",
 "membership": "candidates.csv",
 "input_map": {
  "daily_excess": "panels/daily_excess_FX_EM.parquet",
  "signal_inputs.fx_foreign_rate": "signals/fx_foreign_rate_monthly_EM.parquet",
  "series.us_rate": "series/usd_rate_3m_monthly.parquet",
  "series.eq_beta_ref": "series/kf_us_mkt_rf_monthly.parquet",
  "series.bond_beta_ref": null,
  "series.century_carry": null
 },
 "instrument_filter": {"class": "FX", "exclude_market_ids": ["AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "NOK", "NZD", "SEK"]},
 "month_window": {"start": null, "end_exclusive": null},
 "seeds_offsets": [0, 1, 2, 3, 4],
 "cost_mult_sensitivity": 2
}
```
