# Alternate-Futures Lab v2 (Workstream C4) — Report

*Written by the C4 alternate-futures agent (2026-09-23). Saved to disk by the main (director) session because the harness blocks subagents from writing report files.*

**Director's decision (2026-09-23).** The proposed SPRT for tsy_month_end_v1 was **registered** in `research/preregistrations.jsonl` before any forward window. Its internal 'PROPOSED, UNREGISTERED' status text is superseded by that ledger entry. Confirmation under the rule is not promotion.

## Headline decisions

**tsy_month_end_v1.** Under the proposed sequential rule (SPRT, W0 vs W2, α=0.05/β=0.2), a full **decade of forward data is unlikely to settle the question either way**:

| World | Median months to a decision | P(confirm by 10y) | P(kill by 10y) | Still undecided at 10y |
|---|---:|---:|---:|---:|
| W0 null | 61 mo (5.1y) | 0.8% | 58.7% | 40.5% |
| W1 pre-pub strength continues | 72 mo (6.0y) | 83.5% | 0.6% | 15.9% |
| **W2 post-pub strength continues** | 79 mo (6.6y) | **26.7%** | 11.4% | **61.9%** |
| W3 continuing 5y decay | 74 mo (6.2y) | 5.0% | 41.8% | 53.3% |
| W4 regime shift (vol×1.5) | 60 mo (5.0y) | 66.2% | 12.6% | 21.2% |
| W5 cost shock (+5bp/side) | 67.5 mo (5.6y) | 8.1% | 32.6% | 59.3% |

Fixed-sample 80%-power requirements confirm this: **~6 years (72 months)** of forward data would be needed to distinguish "no edge" from a world that behaves like the *pre*-publication sample (W0 vs W1), but **~23.5 years (282 months)** would be needed if the true future only ever looks like the thin *post*-publication sample (W0 vs W2) — the realistic case, given the audit's own read of the evidence. At the 10-year mark specified in this brief, fixed-sample power against W2 is only **49%**; the sequential rule's own confirm rate under W2 (26.7%) is even lower, because W2's post-pub mean (15.6bp/window net of cost) is barely above the SPRT's kill boundary given the historical noise (σ≈133bp/window). **Practically: this candidate cannot be confidently confirmed within a 10-year forward-observation horizon under its own best evidence (W2); it can more plausibly be killed (59% by 10y under W0) or confirmed only if the future reverts to pre-publication strength (W1, 84% by 10y) — which the audit already judges unlikely.**

**momentum_gold_v1.** Faster to resolve, but still slow relative to typical review cycles: under W2 ("later"/2020-2026 regime continues, +2.58%/yr active), the SPRT confirms 50.2% of paths within 10 years (median 63 months); fixed-sample 80% power needs **~14.5 years (174 months)**. Under W1 ("earlier"/2017-2019 regime, only +0.93%/yr active), confirmation is essentially out of reach on any realistic horizon (**~113 years**, 2.7% confirmed by 10y). The **frozen Bayesian rule** from `research/future_lab/` (its `spmo_gld` entry, directly applicable here) never once fires `kill_sharpe` or `revert_to_control` across any world in 4,000 simulated paths — a real blind spot, not a coding artifact: none of the six worlds here null the fund's *absolute* excess return over cash (only its edge *over the SPY/GLD control*), so its absolute Sharpe stays comfortably positive throughout, and the rule's only working lever turns out to be the drawdown boundary (which fires 63% of the time by 5 years under the vol×1.5 world, W4).

---

## 1. What was built

`research/future_lab2/` imports `research.future_lab.engines` (Politis–White block length, stationary bootstrap) and `research.future_lab.forward`/`.risk` (the frozen Bayesian rule, drawdown-by-month) but adds its own **explicit generative worlds** rather than resampling history alone:

| Module | Role |
|---|---|
| `tsy_world.py` | TLT book M, monthly ("window") units, 2003–2026 (284 months), from `reports/audit_tsy/c_months_{dev,val}.csv`'s `win_ex` column — reproduces `reports/audit_tsy/e_postpub.json`'s window-excess mean/t exactly (tested). Six worlds, net of the frozen spec's base cost (2bp/side). |
| `gold_world.py` | momentum_gold_v1, daily units, 2017–2026, from `reports/momentum_gold_20260919/{momentum,market}_gold_full_base.csv` (joint strategy/control/turnover draws preserve their ≈0.89–0.94 correlation). |
| `rule.py` | A generic Wald SPRT (vectorised, log-likelihood-ratio boundaries `A=ln((1-β)/α)`, `B=ln(β/(1-α))`), fixed-sample power/months-needed, t-stat/Sharpe distribution machinery, and a thin wrapper that reuses `forward.rule_decisions` for the frozen Bayesian rule. |
| `run.py` | Orchestration; writes `reports/future_lab2/`. |

Seed **20260924**, n_paths = 10,000 (TLT, 120-month horizon) / 4,000 (gold, 2,520-day horizon), runtime **8.2 s** (well under budget). Tests: `tests/test_future_lab2.py`, **17 passed** (`.venv/bin/python -m pytest tests/test_future_lab2.py -q`), including exact reproduction of the audit's window-excess figures, a frozen-code hash check on `tsy_month_end_v1`'s core/evaluate files, and an SPRT type-I/type-II error check against synthetic Normal data.

**World construction** (both candidates use the same six ideas, adapted to each candidate's own data):
- **W0 null** — mean forced to the true no-edge level (TLT: −4bp/window, the base cost still paid on zero gross edge; gold: strategy mean shifted to equal its control's).
- **W1/W2** — TLT: block-bootstrap of the pre-/post-publication sub-samples as observed. Gold has no publication event, so W1/W2 use the report's own "earlier" (2017–19) / "later" (2020–26) split as the closest analogue — flagged explicitly as a substitution, not a discovery-date split.
- **W3 decay** — linear decay of the mean to the null level over 60 months, using the *current*-regime pool's own demeaned shape/vol.
- **W4 regime shift** — deviations from the historical mean scaled ×1.5 (vol×1.5), mean unchanged. TLT's stock-bond correlation-flip clause is not separately modelled (book M carries no explicit equity leg; empirically, 2022 — the real correlation-flip year — was one of validation's *better* years per `reports/audit_tsy/REPORT.md` §6).
- **W5 cost shock** — TLT: extra 10bp/window (2×5bp) on top of the post-pub world; gold: extra 5bp × that day's own historical turnover, charged to both legs.

## 2. Distribution of forward t-stat / Sharpe (selected checkpoints)

**TLT, window-excess Sharpe (annualised √12), net of base cost:**

| World | 12m Sharpe p50 [p05,p95] | 60m | 120m |
|---|---|---|---|
| W0 | −0.12 [−1.80, 1.55] | −0.11 [−0.81, 0.59] | −0.10 [−0.60, 0.38] |
| W1 | 1.04 [−0.57, 2.87] | 0.97 [0.23, 1.71] | 0.94 [0.42, 1.48] |
| W2 | 0.39 [−1.39, 2.20] | 0.40 [−0.33, 1.15] | 0.40 [−0.11, 0.92] |
| W3 | 0.36 [−1.45, 2.10] | 0.15 [−0.62, 0.87] | 0.01 [−0.50, 0.53] |
| W4 | 0.57 [−1.10, 2.33] | 0.53 [−0.20, 1.24] | 0.52 [0.01, 1.03] |
| W5 | 0.15 [−1.71, 1.90] | 0.14 [−0.59, 0.88] | 0.14 [−0.37, 0.66] |

**momentum_gold_v1, active-vs-control Sharpe (annualised √252):**

| World | 12m p50 [p05,p95] | 60m | 120m | P(Sharpe>0) @120m |
|---|---|---|---|---|
| W0 | −0.03 [−1.46, 1.53] | 0.00 [−0.67, 0.70] | −0.005 [−0.47, 0.47] | 49.2% |
| W1 (earlier) | 0.28 [−1.18, 1.72] | 0.27 [−0.37, 0.88] | 0.27 [−0.17, 0.72] | 84.3% |
| W2 (later) | 0.56 [−0.97, 2.26] | 0.57 [−0.13, 1.29] | 0.57 [0.08, 1.06] | 97.2% |
| W5 (cost shock) | 0.59 [−0.96, 2.23] | 0.59 [−0.09, 1.28] | 0.57 [0.11, 1.06] | 97.6% |

Full tables: `reports/future_lab2/tsy_dist.csv`, `reports/future_lab2/gold_dist.csv`.

## 3. Sequential-rule operating characteristics

**TLT proposed SPRT** — full table `reports/future_lab2/tsy_sprt.csv`; **momentum_gold_v1** analogous SPRT (monthly active return, mu0=0, mu1=later-regime mean 25.8bp/mo, σ=137bp/mo) in `gold_sprt.csv`; and the **frozen Bayesian rule** (`spmo_gld` entry of `reports/future_lab/monitoring_rule_spec.json`, applied to gold's simulated daily paths) in `gold_frozen_rule.csv`. Selected rows:

| Candidate | World | P(confirm by 10y) | P(kill by 10y) | Median months |
|---|---|---:|---:|---:|
| gold SPRT | W0 null | 2.5% | 75.6% | 47 |
| gold SPRT | W2 later | 50.2% | 17.9% | 63 |
| gold SPRT | W5 cost shock | 50.9% | 16.3% | 63 |
| gold frozen rule (60m) | W0 | promote 4.3%, kill_dd 13.5% | | 24 |
| gold frozen rule (60m) | W2 | promote **29.9%**, kill_dd 18.4% | | 34 |
| gold frozen rule (60m) | W4 (vol×1.5) | promote 8.6%, kill_dd **63.0%** | | 16 |

`kill_sharpe` and `revert_to_control` are **0% in every world** for the frozen rule — see limitations.

## 4. Months needed for 80% power

| Test | Months | Years |
|---|---:|---:|
| TLT: W0 vs W1 (pre-pub) | 71.8 | 6.0 |
| TLT: W0 vs W2 (post-pub) | 281.8 | 23.5 |
| gold: W0 vs W1 (earlier) | 1355.6 | 113.0 |
| gold: W0 vs W2 (later) | 174.5 | 14.5 |

Monte Carlo check (4,000 paths at the analytic n) confirms the TLT W0-vs-W2 formula: 81.2% simulated vs 80% analytic target.

## 5. Proposed rule (unregistered)

`reports/future_lab2/proposed_forward_rule_tsy_month_end_v1.json` — a Wald SPRT on the monthly window-excess return net of base cost: H0 mean = −0.0004 (kill), H1 mean = +0.001564 (confirm, the post-pub sample mean), σ=0.01326 (fixed, from the full 2003–2026 history), α=0.05, β=0.2, boundaries A=2.773 / B=−1.558. **PROPOSED, UNREGISTERED** — becomes pre-specified only once its `sha256` is registered in `research/preregistrations.jsonl` before 2026-09-24. The director decides whether to register it.

## Limitations — what forward data cannot tell us

- **The worlds are hand-specified, not discovered.** They cannot contain a regime, shock, or structural break absent from the 2003–2026 (TLT) / 2017–2026 (gold) samples they're built from — only explicit, named alternatives to that history (a mean shift, a linear decay, a ×1.5 variance scale, an extra cost). A genuinely novel future (e.g., TLT delisted, a Fed policy regime with no analogue since 2003) is outside what any of this can represent.
- **σ is treated as fixed and known**, estimated once from history and never re-estimated on forward data — standard for a pre-registerable rule, but wrong by construction under W4 (true σ is 1.5× the assumed value there), which silently changes the rule's *actual* error rates away from the nominal 5%/20%.
- **The SPRT only ever distinguishes two points** (μ0 vs μ1). It is not a test of "is there any edge" — a real but different-sized edge (e.g. W3's decaying edge, or gold's W1) can and does drift toward KILL well before 10 years even though "no edge" is false, simply because it doesn't look like the specific H1 the rule was built against.
- **The frozen Bayesian rule's blind spot is real, not incidental**: for a diversified, positive-expected-return fund like momentum_gold_v1, "no edge over the control" and "as good as backtested" look nearly identical to a rule that only tests absolute Sharpe and IR-vs-control drift — the original `research/future_lab/` report already flagged this; this lab's simulation confirms `kill_sharpe`/`revert_to_control` essentially never fire, so `kill_drawdown` is doing almost all the actual work.
- **Circularity.** Every prior, σ, and boundary here is estimated from the same history the rule will later judge; applying it back to that history is a consistency check, not independent validation.
- **W1/W2 for momentum_gold_v1 are a substitution**, not a true pre-/post-discovery split (no publication event exists for this fund construction) — treat those two rows as "if the future looks like 2017–19" / "if it looks like 2020–26," not as a discovery-adjusted read.
- **This is not evidence of an edge.** It is a map of how long confirmation or falsification would take under stated assumptions, nothing more — consistent with `research/future_lab/`'s own framing, which this workstream deliberately extends rather than replaces.

### Files
- Code: `/Users/rytty/CCP/quant_v7/research/future_lab2/{__init__.py,tsy_world.py,gold_world.py,rule.py,run.py}`
- Tests: `/Users/rytty/CCP/quant_v7/tests/test_future_lab2.py` (17 passed)
- Outputs: `/Users/rytty/CCP/quant_v7/reports/future_lab2/{results.json,manifest.json,tsy_dist.csv,tsy_sprt.csv,gold_dist.csv,gold_sprt.csv,gold_frozen_rule.csv,decision_time_distributions.png,proposed_forward_rule_tsy_month_end_v1.json}`

No existing files were edited (verified via `git status`); no trades, commits, or pushes were made.