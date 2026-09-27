# Null-World Calibration Across the quant_v7 Registry (Workstream C1)

*Written by the C1 null-calibration agent (2026-09-23). Saved to disk by the main (director) session because the harness blocks subagents from writing report files.*

**Director's notes (2026-09-23 23:50 PDT).**
- The agent's counts predate the commodity_roll validation run. commodity_roll then reached validation and FAILED (0.21 vs 0.75; see `reports/commodity_roll/REPORT.md`). The full-pipeline record is therefore 0 of 2 post-amendment validations, and 0 of 11 overall.
- The letf_rebalancing flag is accepted: L2 (0.48 < 0.50) failed its gate, so its forward-only status carries no evidential weight.
- Principles P1, P2, P3 and P5 are registered as `research/PROTOCOL_AMENDMENT_2_2026-09-23.md`. P4 is adopted as a disclosure requirement, not a threshold.

**Code:** `research/null_lab2/` (`families.py`, `sim_params.py`, `synth.py`, `calibrate.py`, `flags.py`, `multiple_testing.py`, `build_gate_table.py`, `run_all.py`). **Tests:** `tests/test_null_lab2.py`, 14/14 pass. **Outputs:** `reports/null_lab2/{gate_table.csv, calibration.csv, flags.csv, multiple_testing.json, unified_gate_proposal.json}`. Full pipeline runs in ~53s CPU (well under the 15-minute budget), seed `20260924`, 2,000 draws/cell. No family's `evaluate.py` was run, no validation-window data was loaded, no existing file was edited.

## Headline findings

1. **The registry runs at least four different dev-gate designs with very different calibrated size.** The old flat-Sharpe-≥-0.5-no-null gate (14 families, all registered before 2026-09-23) false-passes **12.3% on average** (range 5.3–17.4%) of a true-zero-net-mean world, rising to **20.3%** once a small uncancelled exposure is added — matching `null_lab`'s own 10–19% finding almost exactly. Every post-amendment "new" archetype (bootstrap/shift/permutation, gated on p<α) is much better controlled: **2.6–5.1%** false-pass at zero-net-mean, close to nominal. The exception is the two families that *compute but don't gate on* P(pass|null) (`credit_lead`, `index_option_breadth`): their false-pass rate **triples, 4.6%→13.3%**, once a small residual exposure leak is present, because nothing in their registered pass criteria can catch it.
2. **No two-stage gate in the registry has even 35% power to catch a real net Sharpe-0.7 edge.** Across every family with a simulated dev+validation pair, joint power at SR=0.7 ranges **16–33%** (best: `fundamentals` 32.6%, `etf_hybrids` 32.5%, `tsy_month_end` 30.3%). A genuinely tradable edge at that level is *more likely to be missed than caught*.
3. **The registry-wide record is still statistically indistinguishable from all-null**, extended through this session's 17 new registrations: 91 gate-evaluable candidates, **16 actual dev passes vs 11.1 expected** under a zero-net-mean null (4.2 expected under a more realistic cost-drag null) — the same "not surprising" pattern `null_lab` found (9 vs 7.8, p=0.35). At the full dev+validation stage: **0 actual passes vs 0.08 expected** — the validation gate remains tight even as the dev gate leaks.
4. **`sector_month_end` and `fx_hedge_rebal`/`fx_news` demonstrate the "null answers the wrong question" pathology named in this workstream's brief**, at scale: their shift/permutation null references sit at active Sharpe ≈ **−0.97, −0.27, and −4.1 bp** respectively (not 0), because *any* random window/permutation in a cost-bearing calendar strategy loses money. A p<0.05 there shows "less bad than random," not "profitable." `sector_month_end`'s own dev Sharpe was −0.43 while its shift-null p was 0.038 — it still failed only because the separate Sharpe-threshold leg is binding.
5. **One process-level violation found:** `letf_rebalancing`'s L2 (dev Sharpe 0.48) never cleared its own registered 0.50 gate, yet the ledger classifies it "FORWARD ONLY" and recommends a forward test anyway — the only gate in the registry that was bypassed after failing.

## Gate table (`reports/null_lab2/gate_table.csv`, 35 rows / 91 candidates)

Extracted from every registered `PLAN.md` + `evaluate.py`/`core.py` with evaluable gate logic (momentum-family plans that gate on "beats SPMO both halves" rather than a Sharpe+null structure — `momentum_construction`, `vol_managed_momentum`, `residual_momentum`, `overlay_control`, `momentum_verification/momentum_lab` — were excluded from this table and counted separately in the multiple-testing accounting, task 4).

| Protocol | Families | Dev gate | Dev null | k-adjustment |
|---|---|---|---|---|
| pre-2026-09-23 (14 families) | options_signals, putwrite, cot, intraday, fx_carry_vol, insider, rebalancing, letf_rebalancing, iv_changes, pead_streak, auction_cycle, fundamentals, etf_hybrids, macro_surprise | flat Sharpe ≥ 0.5 | **none** | only at validation (α/k) |
| pre, single-stage | pead_2004_2014 (HAC t≥2.0), pead_portfolio (beat-benchmark+paired p), survivor_hybrid (Sharpe+CI+DSR@N=84), multiasset 17-sleeve inclusion (Sharpe≥0.30, k=17, no null), multiasset/crypto | mixed | mixed/none | none |
| post-2026-09-23, bootstrap (9) | japan_us_flow, structural_frontier A/B/C, vrp_putwrite, commodity_roll, mbs_convexity | active/absolute ≥1.8-2.4/√T | bootstrap p<α | yes (α/k) |
| post, shift (4) | credit_gate, etf_basis, tsy_month_end, sector_month_end | 1.8/√T | shift p<0.05 | n/a (k=1) |
| post, permutation (3) | policy_trend, fx_news, fx_hedge_rebal | 1.8/√T | permutation p<0.05 | fx_news only |
| post, **no p-gate** (2) | credit_lead, index_option_breadth | 1.8/√T + beat 2 controls | **reported, not gated** | n/a |

**Dev outcomes:** 16/91 candidates passed development (intraday I4, insider N3/N4, rebalancing R2/R3, etf_hybrids E1/E2, tsy_month_end M, commodity_roll, multiasset 5/17 sleeves, crypto both). **Validation:** only tsy_month_end reached validation among post-amendment families and **missed by 0.06 Sharpe** (0.69 vs 0.75 gate) despite shift-p≈0.005 and bootstrap-p≈0.004 — "strongest evidence to date; not validated," per the ledger, now quantitatively confirmed as the one dev pass with real statistical teeth. All pre-amendment dev-passing candidates (R2/R3, N3/N4, E1/E2) failed validation.

## Calibration results (`reports/null_lab2/calibration.csv`, 245 rows)

Mean P(pass dev) by archetype, and power (true net Sharpe = 0.3/0.5/0.7/1.0):

| Archetype | null(a) cost-drag | null(b) zero-net | null(c) drift | pow@0.3 | pow@0.5 | pow@0.7 | pow@1.0 |
|---|---:|---:|---:|---:|---:|---:|---:|
| OLD_ABS_NO_NULL (14 fam.) | 3.2% | **12.3%** | 20.3% | 31.9% | 49.4% | 68.8% | 87.8% |
| NEW_ACTIVE_BOOTSTRAP (7) | 0.4% | 2.6% | 3.7% | 11.2% | 26.3% | 45.9% | 73.2% |
| NEW_ACTIVE_SHIFT (4) | 0.7% | 4.3% | 4.6%* | 17.4% | 32.6% | 52.8% | 78.8% |
| NEW_ACTIVE_PERMUTATION (2) | 0.8% | 5.1% | 5.5%* | 17.7% | 31.6% | 51.7% | 76.0% |
| NEW_ACTIVE_NOPGATE (2) | 0.8% | 4.6% | **13.3%** | 16.3% | 29.9% | 51.3% | 74.4% |
| SLEEVE_INCLUSION (multiasset alone) | 4.8% | **19.4%** | 32.5% | 49.7% | 71.5% | 87.0% | 98.0% |
| DSR_SINGLE_STAGE (survivor_hybrid) | 0.0% | 0.0% | 0.0% | 0.0% | 0.1% | 0.4% | 1.9% |

\*shift/permutation world(c) = true SR 0, null reference decentred (documented approximation, see Limitations). κ (sampling-dispersion inflation) measured directly off simulated paths landed at 0.85–1.4 throughout, matching `null_lab`'s own established range — a useful cross-check that the synthetic series are behaving like this project's real engines.

## Inconsistency flags (`reports/null_lab2/flags.csv`, 46 rows: 29 high / 16 medium / 1 low)

Ranked by severity:
1. **[high] No dev-null test at all** — 16 candidate-groups (14 pre-amendment families + multiasset's two sleeve screens) gate development purely on a point-estimate Sharpe.
2. **[high] Systemic <50% (mostly <35%) validation power at SR=0.7** — affects every family with a real val stage.
3. **[high] Null answers the wrong question** — `sector_month_end` (ref. mean ≈ −0.97 SR) and `fx_news` (ref. mean ≈ −4.1 bp), both driven by turnover/cost drag baked into *any* randomized window, not the tested one.
4. **[high] Gate bypassed after failing** — `letf_rebalancing` L2 promoted to "forward" despite 0.48 < its own 0.50 gate.
5. **[medium] No family-size correction at dev** — 5 families with k≥4 (options_signals, insider, intraday, etf_hybrids, multiasset-17) screen multiple/many candidates with zero Bonferroni/Šidák adjustment anywhere in the *development* stage (only validation applies α/k).
6. **[medium] P(pass|null) reported but not gated** — `credit_lead`, `index_option_breadth`, registered the same week as siblings that *do* gate on p<α.
7. **[medium] Weakest bar in the registry** — multiasset's 17-candidate, Sharpe≥0.30, no-null sleeve screen (calibrated 19.4% false-pass at zero-net, vs. actual 5/17 passing — roughly what noise alone would produce for ~3 of the 5).
8. **[medium] Control not gated** — `fx_hedge_rebal` binds on absolute book Sharpe, not active-vs-C_USDSHORT, arguably in tension with protocol item A2.
9. **[low, informational]** `structural_frontier(A)` — the one clean case of the Bonferroni p-gate (p=0.023 vs 0.0167) correctly overriding a Sharpe pass (0.57 vs gate 0.52) — evidence the multiplicity correction is doing real work, not just adding friction.

## Multiple-testing accounting (`reports/null_lab2/multiple_testing.json`)

| Tier | n | Basis |
|---|---:|---|
| 1 — registered, gate-evaluable candidates | **91** | sum of family sizes in gate_table.csv |
| 2 — registered, non-standard-gate plans | 51 | momentum_construction(10)+vol_managed_momentum(5)+residual_momentum(4)+overlay_control(30, a control study)+momentum_verification/lab(2) |
| 3 — never preregistered (estimate) | 40–73 | return_search(20, cited in ledger), higher_sharpe/blend_sleeves/strategy_research/sleeve_blend(8–20), edge_*.py probes(4–10), crowding_unwind/downside_rotation(5–15), Codex fund-design follow-ups(3–8) |
| **Grand total** | **182–215** (point estimate 198) | vs. the ledger's stale pre-session **~111** |

**Tier-1 false-pass accounting:** actual dev passes **16** vs. expected **11.1** under zero-net-mean-null (**4.2** under a cost-drag null) — mildly elevated, driven mainly by the two weak-bar sleeve screens. At the full dev+validation stage: actual **0** vs. expected **0.08** — no anomaly; the validation gate is doing its job even where development leaks.

## Unified gate proposal (`reports/null_lab2/unified_gate_proposal.json`, NOT registered)

Five principles: (P1) the null must be mean-zero under H0 — shift/permutation nulls must be explicitly re-centred, not just "beaten"; (P2) Bonferroni α=0.05/k at the **workstream** batch level, matching what `structural_frontier` already does; (P3) keep the existing 1.8/√T (2.4/√T for k≥4) Sharpe gate — calibration confirms it already controls size well; (P4) require ≥50% joint dev+validation power at SR=0.7, computed and published *before* registration, given every current family falls short; (P5) P(pass|null) must be reported from the *same* null that produces the gating p-value — closing the `credit_lead`/`index_option_breadth` gap.

## Limitations

- **Synthetic, not empirical.** No real price series were used (barred by the hard constraints); vol/autocorrelation per family are documented, cited approximations (`sim_params.py`), not measurements. κ landing in `null_lab`'s own established 0.85–1.4 range is the main external check available.
- **Shift/permutation nulls approximated by a decentred reference distribution**, not literal signal-shifting on real data — validated once against a genuine nested block bootstrap in `test_bootstrap_quantile_matches_nested_bootstrap` (agreement within ~0.04–0.06 at α=0.05).
- **`multiasset/crypto`'s row has no numeric dev threshold** in the source plan text I could extract, so its simulated "100% false-pass" figure is a modeling artifact (no threshold ⇒ trivial pass), not a finding — flagged in code, excluded from headline claims.
- **Stress-cost leg** is modeled as a fixed 80bp annualized drag, not each family's actual stress/base cost differential.
- **Tier-3 unregistered-trial count is a bounded estimate**, not an audit of every ad hoc script; several named scripts (`higher_sharpe.py`, `blend_sleeves.py`) were not individually read in full.
- **multiasset's HAC-t-based holdout gate and pead_2004_2014's both-halves criterion** are approximated via a naive t-stat computed on the same autocorrelated synthetic path, not a literal Newey-West estimator.