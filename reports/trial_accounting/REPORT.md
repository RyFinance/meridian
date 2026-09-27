# Research-Trial Historian — quant_v7, research cycle 4 (2026-09-24)

*Written by the cycle-4 trial-historian agent (2026-09-24). Saved by the director session. Director's note: commodity_roll then failed validation (0.21 vs 0.75), so its forward count is 0. The one genuine forward decision (tsy_month_end_v1, seq 3) was recorded on 2026-09-25 04:58Z.*

## What was built

- `research/trial_accounting/{meff.py, data_sources.py, family_data.py, series_config.py, build.py}` — read-only build pipeline
- `reports/trial_accounting/{families.csv (52 rows), trials.csv (269 rows), summary.json}`
- `tests/test_trial_accounting.py` (6 tests, all pass) — M_eff estimator correctness/bounds on synthetic series, non-overlapping-series handling, and the preregistrations.jsonl parser
- Run with `cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.trial_accounting.build`. No `evaluate.py` was run, no validation window was opened, no new returns were computed — every number below is drawn from CSVs/JSON/prose already on disk, or from a monthly-aggregated correlation of already-existing return series.

## Headline count

| | low | high | point |
|---|---:|---:|---:|
| Tier 1 (registered, gate-evaluable) | 98 | 98 | 98 |
| Tier 2 (registered, non-standard gate) | 51 | 51 | 51 |
| Tier 3 (never preregistered, estimate) | 73 | 109 | ~91 |
| **This workstream's grand total** | **222** | **258** | **~240** |

Tier 1 is 91 (null_lab2's count) **+7** for `pead_attack`, a registered family (permutation-placebo primary test) that null_lab2's gate_table.csv correctly excludes because it isn't a Sharpe dev/val gate, but which is still a registered trial family. Tier 3 is null_lab2's 40–73 **+30** (see reconciliation below) plus small refinements (return_search 20→23 from an exact file glob) and 3 non-comparable rows (a live paper-bot config, one crashed/incomplete run, one meta-study) that arguably shouldn't be counted as "shots" at all — excluding those three, the comparable range is **~219–255, point ~237**.

## Family table (condensed — full 52 rows in `families.csv`)

| family_id | info family | strategy | n_reg | dev/val/fwd | class |
|---|---|---|---:|---|---|
| tsy_month_end(M) | calendar/flow | time-series timing | 1 | 1/0/1 | FORWARD OBSERVATION |
| commodity_roll | commodity roll | spread/relative value | 2 | 1/0/0 | SPENT |
| insider(N1-N4) | insider transactions | cross-sectional selection | 4 | 2/0/0 | SPENT |
| rebalancing(R1-R3) | calendar/flow | time-series timing | 3 | 2/0/0 | SPENT |
| multiasset(17-sleeve) | price momentum | time-series timing | 17 | 5/0/0 | SPENT |
| pead_attack | earnings events | event study | 7 | 0/0/0 | SPENT |
| pead_2004_2014 | earnings events | event study | 1 | 0/0/0 | SPENT |
| letf_rebalancing(L1-L2) | calendar/flow | time-series timing | 2 | 0/0/0 | FORWARD OBSERVATION *(disputed — see below)* |
| momentum_construction/vol_managed/residual/overlay_control | price momentum | portfolio construction | 10/5/4/30 | 0 dev passes each | SPENT |
| return_search / sleeve_blend_higher_sharpe / crowding_downside_rotation / etf_convergence-cluster / fx_session / pead_production_history (tier‑3) | price momentum / positioning / ETF structure / FX intraday / earnings events | mixed | 23/47/6/14/3/13 (disk counts) | never gated | SPENT |

**Process flag preserved from the prior audit:** `letf_rebalancing` L2 (dev Sharpe 0.48) never cleared its own registered 0.50 gate, yet is classified FORWARD ONLY — the one gate in the registry bypassed after failing (null_lab2 flags.csv, high severity).

## M_eff results

**Project-wide** (one representative series per family, 36 of 52 families have a usable return series on disk, pairwise-complete monthly correlation, eigenvalues floored at 0 and trace-renormalized):

| M (raw) | Cheverud | Nyholt | Li & Ji |
|---:|---:|---:|---:|
| 36 | 33.9 | 19.1 | 25.0 |

So even at the coarsest possible grain (one series per family), the registry's ~36 nominally distinct families behave like roughly **19–34 independent tests** depending on method — Li & Ji (the usual consensus choice) says **~25**.

**Within-family** (families with ≥2 series; selected):
- `insider(N1-N4)`: M=6 → Li‑Ji 4.0; `etf_hybrids(E1-E5)`: M=9 → Li‑Ji 4.0 (dev+validation stacked); `return_search`: M=7 → Li‑Ji 5.0; `rebalancing(R1-R3)`: M=5 → Li‑Ji 4.0; `tsy_month_end`/`commodity_roll`/`policy_trend`: M=2 → Li‑Ji 2.0 (dev and validation windows are ~disjoint in time, so correctly stay independent).
- **16 families have no return series on disk at all** for this analysis (e.g. `japan_us_flow`, `credit_lead`, `fx_news`, `index_option_breadth`, `fx_hedge_rebal`, `structural_frontier(A/B)`, `pead_streak`, `momentum_gold_fund_designs`, `reversal_research_20260921` [crashed, no data]) — full list in `summary.json`.

## Shots before result (Bonferroni / Holm-first-step / Šidák)

| key result | registered | headline p | shots in info family before | shots in project before | Bonferroni (family) | Šidák (family) | Bonferroni (project) | Šidák using project M_eff (Li‑Ji≈25) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **tsy_month_end** | 2026‑09‑23 22:31 | 0.006 (dev shift‑null) | 9 | 260 | 0.06 | 0.058 | 1.0 | 0.13 |
| **commodity_roll** | 2026‑09‑23 23:16 | 0.0064 (dev bootstrap) | 0 | 261 | 0.013 | 0.013 | 1.0 | 0.14 |
| **pead** (pead_attack P1) | 2026‑09‑23 05:07 | 0.113 | 31 | 241 | 1.0 | 0.99 | 1.0 | 0.94 |
| multiasset sleeves | 2026‑09‑18 11:52 | n/a — no p in the registered gate | 47 | 68 | — | — | — | — |
| insider N3/N4 | 2026‑09‑19 01:43 | n/a — pre-amendment gate has no dev null | 0 | 126 | — | — | — | — |
| rebalancing R2/R3 | 2026‑09‑19 03:17 | n/a — pre-amendment gate has no dev null | 4 | 136 | — | — | — | — |

Both nominal p-values that looked "strong" (tsy_month_end 0.006, commodity_roll 0.0064) **do not survive** any correction once the whole project's registered history is the reference class (Bonferroni → 1.0; Šidák using the project's own M_eff → 0.13–0.14, both well above 0.05). Even at the narrower same-information-family scale, tsy_month_end is only borderline (0.058–0.06) and commodity_roll barely survives (0.013). Both families also failed their subsequent validation stage on their own registered gates, which is the stronger and cleaner signal; this multiple-testing view is a second, independent reason for the same skepticism, not a new contradiction. PEAD's p=0.113 was never close to significant even before any correction. Holm's first step (treating this result as the smallest of k) is numerically identical to Bonferroni here because none of these families has a companion ordered p-value list on disk — genuine Holm needs the full ordered p-vector, which most families' Sharpe+null gates don't produce; this is disclosed as a limitation, not silently approximated as exact.

## Exhausted vs. untouched information families

All 14 information families identified have been touched at least once (none is "GENUINELY NEW" in the ledger's own sense). Status:

| Information family | n families | reg | informal (hi) | dev pass | val pass | fwd | status |
|---|---:|---:|---:|---:|---:|---:|---|
| price momentum | 11 | 73 | 52 | 7 | 0 | 0 | **EXHAUSTED** |
| earnings events | 8 | 18 | 24 | 0 | 0 | 3 | ACTIVE (forward-stage only, all backfill-tainted) |
| options prints | 6 | 13 | 0 | 0 | 0 | 0 | **EXHAUSTED** |
| calendar/flow | 5 | 11 | 0 | 4 | 0 | 1 | ACTIVE (1 genuine forward decision recorded, tsy_month_end, outcome unknown) |
| FX intraday | 4 | 4 | 3 | 0 | 0 | 0 | **EXHAUSTED** |
| credit spreads | 4 | 4 | 0 | 0 | 0 | 0 | **EXHAUSTED** |
| macro releases | 3 | 5 | 0 | 0 | 0 | 0 | **EXHAUSTED** |
| rates/duration | 3 | 6 | 0 | 0 | 0 | 0 | **EXHAUSTED** |
| positioning | 2 | 3 | 15 | 0 | 0 | 0 | **EXHAUSTED** |
| academic-anomaly replication | 2 | 4 | 1 | 0 | 0 | 0 | **EXHAUSTED** |
| ETF structure/basis | 1 | 0 | 14 | 0 | 0 | 0 | **EXHAUSTED** (never even registered) |
| commodity roll | 1 | 2 | 0 | 1 | 0 | 0 | **EXHAUSTED** |
| crypto trend | 1 | 2 | 0 | 2 | 0 | 0 | **EXHAUSTED** |
| insider transactions | 1 | 4 | 0 | 2 | 0 | 0 | **EXHAUSTED** |

**0 validation passes anywhere in the registry** (confirms null_lab2 exactly). The only information families with anything beyond "tested, failed, done" are `calendar/flow` (one recorded but unrealized forward decision) and `earnings events` (forward fills exist but are backfill/replay-tainted per the ledger's own count). **Every other information family is exhausted for honest re-testing on the data currently on disk.** For a genuinely new family the director would need a new dataset, not a new signal on an existing one — options quotes with bid/ask and OI, delisted-inclusive equities, or institutional holdings, per the ledger's own "what remains" section, none of which appears to have arrived since 2026‑09‑23.

## Reconciliation notes

- **With `FAMILY_TRIAL_LEDGER.md`** (the other agent, 9 economic-family rows): no conflicts found. That table's "≥10 construction variants" for equity momentum, "PEAD random-selection p=.113," "R2/R3 and Treasury M" dev passes, and the "one process-level violation" (letf_rebalancing) all match this build's finer-grained (52-row) breakdown. This build adds the two axes that table didn't carry (information_family × strategy_family as separate columns, plus numeric effective-tests bounds) rather than replacing it.
- **With `null_lab2`'s 91/51/40–73 (182–215, point 198):** tier 1 and tier 2 counts match exactly except for the disclosed `pead_attack` addition (+7). Tier 3 is reconciled cluster-by-cluster in `summary.json`'s `reconciliation` field. **Concrete finding this workstream adds:** `research/etf_convergence_spec_20260918.json`, `share_class_spec_20260918.json` and `liquidity_pressure_spec_20260918.json` all carry "written before any result" language and are dated 2026‑09‑18, but **none appears in `research/preregistrations.jsonl`** (grep-confirmed) — a shadow-registration pattern (self-declared intent to register that was never actually logged). Together with the same pattern for `fx_session_spec_20260918.json`, and a large (13-item) cluster of Aug‑18-dated PEAD development reports that pre-date the registration system by a month, that's **+30 trials** (14+3+13) outside null_lab2's own tier-3 narrative, which starts from `return_search` onward. This is additive to null_lab2's range, not a correction of it.
- **A genuine bug caught and fixed during this build:** an early version of the mtime-proxy logic accidentally let a 2026‑09‑18 `pead_audit/` folder mask the true 2026‑08‑18 dates of the PEAD pre-registration-era reports (max-mtime over a mis-scoped directory list). Fixed by excluding `pead_audit` from that family's directory list; the shots-before counts above reflect the corrected version.

## Ambiguity and limitations (please read before treating any number here as precise)

- **Tier 3 counts are estimates**, several file-glob-derived (return_search, etf_convergence cluster, pead_production_history — exact) and several still ranges inherited from null_lab2 (sleeve_blend/higher_sharpe 8–20, edge probes 4–10, crowding/downside 5–15, momentum fund designs 3–8) because those scripts screen internally (e.g. crowding_unwind's 14-market screen) in ways not fully auditable without reading every script in full.
- **M_eff is a monthly-sum approximation** across wildly heterogeneous source schemas (daily marks, multi-week option-cycle marks, NAV curves) reduced to a common grid purely for correlation structure, as instructed — it is not a performance measurement and should not be read as one. Pairwise-complete correlation on non-fully-overlapping series is not guaranteed PSD; negative eigenvalues were clipped and the matrix trace-renormalized (documented in `meff.py`), which is a standard but disclosed adjustment.
- **Holm-style adjustment is approximated** as a first-step bound (equivalent to Bonferroni for one result), since most families' gates don't produce an ordered per-candidate p-value list; true Holm needs that full vector.
- **The controlled classification vocabulary was extended by two labels** (`PARTIALLY USED`, `INFRASTRUCTURE/META`) beyond the six named in the task spec, because forcing the ledger's own long-standing 4th class or two tooling/meta-analysis rows into SPENT/INCOMPLETE would have been less accurate, not more.
- **`letf_rebalancing`'s FORWARD OBSERVATION classification is disputed** in this table (inherited flag, not resolved) — it's carried through as-is per "the table does not retroactively tighten any old gate."
- Everything here rests on file mtimes and content for undated/unregistered work, since git history has only 3 commits — per the task's own framing, this is the best available evidence, not a substitute for a real timestamped log.