# Edge Certification — Workstream C2 Report

*Written by the C2 edge-certification agent (2026-09-23). Saved to disk by the main (director) session because the harness blocks subagents from writing report files.*

**Director's note (2026-09-23).** Treat G7 (execution lag) for tsy_month_end with caution. The agent's one-bar lag shifts a calendar weight, and that is not the same as the audit's next-open execution test. The audit found open-to-open execution cuts the validation window return from 30.6 to 17 bp, so G7 = PASS here does not overrule the audit's execution caveat. The commodity_roll G1 result (alpha t 1.04) matches the director's own computation.

## Files delivered

- `research/certify/guards.py` — promotion-guard library (pure functions, G1–G7 + `certify()`)
- `tests/test_certify.py` — 20 unit tests on synthetic data, all passing
- `research/certify/scorecard.py` — trust scorecard builder (8 candidates × L0–L8)
- `reports/certify/scorecard.csv`, `reports/certify/scorecard.json` — the scorecard
- `reports/certify/guards_tsy_month_end.json`, `reports/certify/guards_commodity_roll.json` — guard results on the two named candidates

No existing file was edited. No `evaluate.py` was run. No trades, commits, or pushes.

---

## 1. Guard definitions and thresholds

| Guard | Condition | Threshold (module constant) |
|---|---|---|
| **G1 beta** | NW-HAC alpha t-stat vs all benchmarks jointly (lag 10 daily / 3 monthly, auto-detected) | `alpha_t >= 2.0` **and** `alpha >= 0.5 * mean_return` |
| **G2 reduced exposure** | Active return vs (a) `avg|exposure| × benchmark` and (b) a vol-matched benchmark | both: `IR > 0` and `t >= 2.0` |
| **G3 concentration** | top-5%-months P&L share | `< 0.50` |
| | max single-year P&L share | `< 0.35` |
| | leave-one-year-out min Sharpe | `>= 0.50 ×` full-period Sharpe |
| | monthly sign-test p | `< 0.05` |
| **G4 one asset** | max single-asset P&L share | `< 0.50` |
| | every leave-one-asset-out Sharpe | `> 0` (single-asset case → `"flag"`, not pass/fail) |
| **G5 null calibration** | `P(pass\|null)` | `<= 0.05`; flags if supplied null-distribution mean has `|mean| > 0.30` (catches shift nulls like a −0.96 mean Sharpe) |
| **G6 post-publication** | t-stat after `publication_date` | `>= 1.65`; flags `"insufficient post-pub data"` below 60 observations rather than failing |
| **G7 execution lag** | one-bar-lagged Sharpe / original Sharpe | `>= 0.60` |

Every guard returns `{"pass": True/False/"flag"/None, "reason": str, "threshold": ..., "value": ...}`; `pass=None` = NOT-RUN (inputs not supplied).

## 2. Tests

```
tests/test_certify.py -q  →  20 passed
```
Confirmed: a pure-beta series fails G1; a genuine iid alpha passes G1; a single-year-concentrated series fails G3 (and a well-spread iid series passes it); single-asset P&L is flagged (not pass/fail) in G4; a dominant asset fails G4; G5 flags a shifted null (mean −0.96) but not a centred one; G6 flags insufficient post-pub data and correctly passes/fails with enough data; G7 fails when lag destroys the signal and passes when it survives; `certify()` wires NOT-RUN correctly when optional inputs are omitted.

## 3. Guard results (dev)

**tsy_month_end** (`active`/`M` from `dev_daily.csv`+`validation_daily.csv`, TLT/SPY excess benchmarks via `cash_rates`, exposure via `core.weights(sess,"last")`):

| Guard | Result |
|---|---|
| G1 beta | **PASS** — alpha t=3.44, alpha_ann 3.15% vs 50% of mean 3.18% |
| G2 reduced exposure | **PASS** — exposure-matched IR 0.68/t 3.29; vol-matched IR 0.47/t 2.26 |
| G3 concentration | **FAIL** — top-5%-months share 60.1% (>50%); max-year 13.6% and LOYO ratio 0.91 both pass; sign-test p≈0 (matches audit's 0.59/0.54 top-5% figures) |
| G4 one asset | **flag** — single-instrument (TLT) strategy |
| G5 null calibration | **PASS** — val 0.017, dev 0.020 |
| G6 post-publication | **FAIL** — t=1.55 (<1.65); Sharpe 0.59 over n=1769 |
| G7 execution lag | **PASS** — lagged/original Sharpe ratio 100.6% |

**commodity_roll** (`base` column of `dev_daily.csv`, front-basket USO/UNG/GSG + SPY excess benchmarks, per-pair P&L re-derived with `core.pair_returns` on pre-truncated prices, all ≤2016-12-30):

| Guard | Result |
|---|---|
| G1 beta | **FAIL** — alpha t=1.04 (<2), alpha_ann 2.00% vs required 3.18% (50% of mean 6.35%); reconciles with dev_results.json's own `alpha_ann_after_betas` 0.02 |
| G2 reduced exposure | NOT-RUN — dollar-neutral spread book, no single-asset exposure to match |
| G3 concentration | **FAIL** — top-5%-months share 65.9% (>50%); max-year 27.7% and LOYO ratio 0.76 pass; sign-test p=0.10 |
| G4 one asset | **PASS** — max pair share 42.2% (crude); all leave-one-pair-out Sharpes positive |
| G5 null calibration | **PASS** — 0.006 |
| G6 post-publication | NOT-RUN — never published |
| G7 execution lag | **PASS** — lagged/original ratio 98.9% |

Reconciliation check: re-derived per-pair average vs the registered `dev_daily.csv` "base" column, max abs diff 0.0041, mean 1.8e-6 — confirms the truncated re-derivation is correct.

## 4. Trust scorecard (candidate × layer, file cited per cell)

Full table in `reports/certify/scorecard.csv`/`.json`. Summary:

| Candidate | L0 | L1 | L2 | L3 | L4 | L5 | L6 | L7 | L8 |
|---|---|---|---|---|---|---|---|---|---|
| tsy_month_end | PASS | PASS | PASS | PASS | **FAIL** | PARTIAL | PASS | PARTIAL | NOT-RUN |
| commodity_roll | PASS | PASS | PASS | NOT-RUN | NOT-RUN | NOT-RUN | NOT-RUN | NOT-RUN | NOT-RUN |
| spmo_gld_5050 | PARTIAL | FAIL | NOT-RUN | NOT-RUN | NOT-RUN | PARTIAL | PASS | NOT-RUN | NOT-RUN |
| pead | FAIL | NOT-RUN | NOT-RUN | FAIL | FAIL | FAIL | NOT-RUN | FAIL | NOT-RUN |
| mbs_convexity | PASS | FAIL | — | — | — | — | — | — | — |
| sector_month_end | PARTIAL | FAIL | — | — | — | — | — | — | — |
| fx_hedge_rebal | PASS | FAIL | — | — | — | — | — | — | — |
| letf_rebalancing (other, FORWARD-ONLY per ledger) | PARTIAL | FAIL | — | — | — | — | — | — | — |

(`—` = NOT-RUN, "dev failed, no further layer computed".)

## 5. Could anything be promoted beyond forward observation?

**No.** Under these guards:
- **tsy_month_end**: strongest evidence in the project (L0–L3 all pass, L6 reproduces on LSE data) but fails its own registered validation gate (L4) and is weakening post-publication (L7: t=1.55<1.65, last-36-months Sharpe 0.25). Correctly parked at forward observation.
- **commodity_roll**: passes L0–L2, but has no placebo/random-selection test (L3), its validation window is locked (L4), and its independent audit is only in progress (L5/L6 NOT-RUN). New finding from G1: once jointly regressed on the front-month commodity basket and SPY, alpha t-stat falls to 1.04 — the raw Sharpe leans partly on beta exposure not yet disentangled by an audit. Not promotable; audit must finish first.
- **SPMO/GLD**: correctly staying a benchmark, not an edge (L1 fail, L5 partial-negative verdict); its first forward decision is 2026-10-01, not yet reached.
- **PEAD**: fails nearly every layer (L0, L3, L4, L5, L7); confirmed not an edge.
- **mbs_convexity, sector_month_end, fx_hedge_rebal, letf_rebalancing**: all fail L1 (dev), nothing further computed.

## 6. Limitations

- G1–G7 numbers for tsy_month_end/commodity_roll are a fresh, independent cross-check using this library's own conventions (NW-HAC regression, sign-test, LOYO) — they are consistent with, but not identical to, the project's own registered dev/validation/audit numbers (e.g., my G3 top-5%-months share of 60.1%/65.9% vs the audit's reported 0.59/0.54 for tsy_month_end — same order, different sample window since mine uses the full dev+val concatenation).
- G5's "null distribution far from zero" flag for tsy_month_end used a synthetic distribution with the *reported* mean/sd (raw draws aren't persisted in `dev_results.json`/`validation_results.json`); this only affects the flag text, not the pass/fail on `null_pass_rate` itself.
- G2 for tsy_month_end was run on the raw `M` book return (not the already-control-netted `active` column), so its exposure-matched control is comparable to the project's own C_EXP; for commodity_roll G2 was skipped as inapplicable (dollar-neutral book).
- The scorecard's L0–L8 statuses are a curated read of existing report files, not new computation; PARTIAL is used where an audit ran but reached a mixed/negative verdict rather than a clean confirm or refute.
- commodity_roll's L5/L6 will change once its in-progress independent audit (`reports/audit_commodity_roll/`) produces a results file — at present only raw source pulls exist, no verdict.