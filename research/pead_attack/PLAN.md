# PEAD attack: pre-registered portfolio placebo, decomposition and leakage audit

Written 2026-09-23. It is registered in `research/preregistrations.jsonl` **before** any placebo draw,
decomposition or new portfolio statistic is computed.

## 1. Question

Does the production PEAD book have any edge beyond:
- (a) market beta; and
- (b) generic exposure to recently announced stocks?

The test uses the actual production decision rules. The object under test is the recorded
`sweep_wide_5p0` book (2×, 5% positions, 100% gross, 2021-08-11 → 2025-06-27). Its published marked
excess Sharpe is 0.6999 (`reports/pead_audit`).

## 2. What was done before registration (reproduction and code review only)

- `review_sue_placebo.py`:
  - reproduces every published number of `research/edge_sue_placebo.py` exactly. The event-level
    values are s2 = 9.68 bps, p = 0.2918; s3 p = 0.927. The portfolio values are long-short full p = 0.96
    and large-SUE full p = 0.553.
  - No new statistic is output. Its two new event-level checks are gated behind `--extras` (see section 7).
- `inputs.py`:
  - rebuilds the replay's candidate stream from the pinned files: 7,192 visible events, 4,903 scorable;
  - uses the replay's own providers and `bot.signal_pipeline.build_feature_row`;
  - also stores a point-in-time-liquidity re-score (`pit_calibrated_proba`) for diagnostic D1. No book
    has been run on it.
- `reproduce.py`: the reproduction gate **passed**.
  - Re-scored probabilities equal the logged ones for all 4,903 candidates (max |diff| 3e-14).
  - The engine reproduces the recorded ledger **trade for trade**: 625 trades, identical tickers, dates
    and sides; fills, exits, notionals and P&L differ by 0.0.
  - All 4,903 gate decisions match, and so does the final cash NAV ($135,411.00).
  - `mtm_audit.mtm_book` on the engine ledger gives excess Sharpe 0.6998806 (published 0.6998806),
    CAPM alpha 4.18%/yr (t 1.15) and beta 0.352. The numpy marking equals `mtm_book` exactly.
- `tests/test_pead_attack.py`: 10 tests pass, all on synthetic data or reproduction.

No placebo draw has been run. No new portfolio statistic has been computed. This includes the real
book's CAGR and FF5+UMD alpha, and every P-family number.

Frozen input hashes (sha256):
- `reports/pead_attack/inputs/events.parquet` 22b11db8…bdac
- `closes_fill.parquet` b302f281…6cb4
- `calendar.parquet` 2eb74295…b238

`manifest.json` lists every source file hash, including the model joblib (3a05c06e…9992) and every
price file.

## 3. Books

Every book runs through `research/pead_attack/engine.py`. That engine is the production rules
re-executed, and it is proven identical to the recorded ledger. Every book also uses the same:
- 974 replay dates and circuit-breaker tiers;
- scorable event set, 3-day visibility window, and one decision per announcement;
- exits after 20 business days at the close;
- 10 bps round trip;
- 20% cash-drawdown kill switch;
- 3% daily-loss rule and 100% gross cap on cash-basis NAV;
- `mtm_book` marking, with idle cash at T-bills (French RF).

Only three per-event inputs vary: the conviction score (which sets the order), the size, and the
direction.

| Book | Score (order) | Size | Direction | Draws |
|---|---|---|---|---:|
| **R** real | model calibrated probability | production quarter-Kelly, 5% cap | sign(SUE) (long iff SUE > 0) | 1 |
| **P1** (primary) | model probabilities **permuted within effective date** over scorable events | Kelly of the permuted probability (the (p, size) pair moves together) | the event's own sign(SUE) | 10,000 |
| **P1L** | same permutations as P1 (same seeds, paired) | as P1 | **long every event** | 10,000 |
| **P1G** | model probabilities permuted over the **whole window** | as P1 | sign(SUE) | 10,000 |
| **P2** SUE-sign only | uniform conviction: i.i.d. U(0,1) key, so the order is random | fixed 5% | sign(SUE) | 10,000 |
| **P3** all events, no selection | uniform conviction, random key | fixed 5% | long | 10,000 |

What each book controls for:
- **P1** preserves each date's exact multiset of scores. The number of Kelly passes, the size
  distribution and the capacity use per date therefore match R in distribution. It isolates the
  cross-sectional information in the model's ranking.
- **P1L** is P1 with every position long: generic post-announcement long exposure at R's capacity and
  sizing profile.
- **P1G** also randomizes timing, i.e. when the model's scores are high.
- **P2** takes every scorable event under the production capacity rules, with no model.
- **P3** takes every scorable event, long, under the production capacity rules.

Other rules:
- Unscorable events stay unscorable in every book.
- Ties in P1/P1G scores are broken as in production: the watcher order (days since the effective date,
  then source row), then a stable sort.
- Seeds: `numpy.random.default_rng([20260923, family_id, draw])`, with family ids P1 = P1L = 1, P2 = 2,
  P3 = 3, P1G = 5. Draw indices run 0..9,999.

## 4. Statistics

Per book, over the 974 days:
- **S1 marked excess Sharpe (primary):** mean(r − rf) / sd × √252 of the daily marked return.
- **S2 CAGR** of the marked NAV, with idle cash at T-bills.
- **S3 CAPM alpha:** annualised intercept of (r − rf) on French Mkt-RF, with Newey-West (20) standard
  errors. This is the audit's regressor.
- **S4 FF5+UMD alpha:** the same, on `reports/momentum_verification_20260919/factor_inputs.csv`. That
  file covers the whole window.
- **Exposure-matched CAGR, for P2 and P3 only (secondary):** CAGR of rf + k·(r − rf), with
  k = R's average gross / the draw's average gross.
- **Descriptive only:**
  - the Sharpe in the three model holdout sub-windows (holdout_a/b/c starts from
    `split_time_disjoint_panel`);
  - trades, long share, average gross, and kill-switch trips;
  - for P1, the mean and volatility of the daily difference R − P1 and its correlation with R.

**p-value** (one-sided, "a placebo book did at least as well"):
p = (1 + #{placebo ≥ real}) / (N + 1).

The primary test is P1 × S1. The other 19 family × statistic p-values (S1–S4 × 5 families) are
secondary. Both raw and Holm-adjusted values are reported.

## 5. Decision rule (fixed now)

- **H1, model selection skill (primary):** P1 S1 p ≤ 0.05.
- **H2, edge beyond generic post-announcement exposure:** P3 S1 p ≤ 0.05 **and** P1L S3 p ≤ 0.05.
  Both conditions are unadjusted and both must hold.
- **Classification:**
  - A: H1 and H2 → selection edge;
  - B: H1 only → selection signal without edge over generic exposure;
  - C: H2 only → exposure edge without model skill;
  - D: neither → **event-exposure product**.
- **Beta:** R's CAPM alpha t-statistic is also reported. The edge-beyond-beta question needs
  alpha t ≥ 2; the already-published t is 1.15.
- **If H1 fails:** the report states the minimum detectable gap, i.e. the 95th percentile minus the
  median of P1 S1. This says whether the null is bounded or vacuous.

## 6. Decomposition (fixed formulas)

Let E_R be R's annualised mean excess return. It splits exactly into four parts, all in %/yr:

  E_R = β_R·mean(Mkt-RF)·252 + mean α(P1L) + [mean α(P1) − mean α(P1L)] + [α_R − mean α(P1)]

| Term | Formula | Meaning |
|---|---|---|
| Market beta | β_R·mean(Mkt-RF)·252 | market exposure |
| Generic post-announcement premium | mean α(P1L) | long exposure to recent reporters |
| SUE-sign direction | mean α(P1) − mean α(P1L) | value of the sign rule under random selection |
| Model selection residual | α_R − mean α(P1) | what the ranking adds |

The α are CAPM alphas. The same split is repeated with FF5+UMD alphas.

The Sharpe split is (S1_R − mean S1_P1) / S1_R, reported as "the fraction of 0.70 that is selection".

## 7. Diagnostics (secondary, pre-specified)

- **D1, point-in-time liquidity.**
  - The production feature `dollar_volume_rank` is a static rank from the last 63 sessions of 2026
    data (see section 8, L1).
  - The diagnostic re-scores every event with the rank of mean close×volume over the 63 sessions
    before the announcement day. The rest of the pipeline is unchanged (`pit_calibrated_proba`, already
    computed).
  - R's rules are then re-run on those scores. Report S1–S4, the S1 percentile within P1, and the trade
    overlap with R.
- **D2:** R with `mtm_book`'s exit-day idle-cash quirk removed (`exit_day_cash_fix`), reported as the
  change in S1.
- **D3, event-level extras for the old placebo** (`review_sue_placebo.py --extras`, same 10,000
  permutations):
  - |SUE| ≥ 1 selection in SPY-excess units;
  - the s2 long-short spread restricted to 2021-08-11..2025-06-27.
- **D4, forward power.**
  - Years for 80% power (one-sided 5%) for an unpaired forward Sharpe test, both vs 0 and vs a
    control.
  - The same for a **paired** comparison against a random-selection shadow book (P1-style). This uses
    the historical mean R − P1 gap and the tracking error.

## 8. Leakage audit (file:line evidence plus descriptive numbers; no new book)

- **L1, features after entry time.**
  - `dollar_volume_rank` provenance, in training (`reports/run_pead_expanded_pipeline.py`,
    `earnings/features.py`) and in serving (`bot/signal_pipeline.py`, `reports/universe_ranking.csv`).
  - The vintage of the SUE/EPS inputs.
  - The pre-earnings return windows in training vs serving.
  - Effective-date alignment.
  - Spearman correlation of the static rank with (i) the calibrated probability and (ii) the realised
    20-session forward return of scorable window events.
- **L2, label overlap:** the last label end date (event date + 20 residual-return sessions) of train
  and validation vs the replay start.
- **L3, calibration and weights:** the date ranges used to fit the ensemble, the ensemble weights, the
  isotonic calibrator and the Kelly payoff ratio.
- **L4, survivorship:**
  - the universe definition, and names whose price history starts after 2015-01 or ends before the
    window end;
  - whether any placebo is exposed to survivorship differently from R. All books share the universe, so
    only feature-mediated channels (L1) can bias the placebo p-value.
- **L5, selection on the evaluation window:** the configuration and universe choices made on this
  window (`live_backtest/compare_configurations.py`, `bot/run_cycle.py`, `bot/earnings_watcher.py`).
- **L6, replay fidelity:** the replay's 30-calendar-day trailing-return window
  (`historical_providers.py`) vs the live 45 (`bot/signal_pipeline.py`); count of events left
  unscorable.

## 9. Procedure, budget and amendments

- **Order:** `placebo.py`, then `analysis.py`, then `review_sue_placebo.py --extras`, then
  `leakage.py`, then REPORT.
- **Budget:** at most 4 worker processes. About 50k books at ≈0.05 s each is roughly 10–15 minutes.
- **If a bug is found after registration:** write an amendment and register it before any re-run. Keep
  the first results and report both.
- **Hard stops:** no production file is modified, and nothing under `bot/state` or `live_backtest/state`
  is written.
