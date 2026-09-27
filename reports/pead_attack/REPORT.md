# PEAD attack: selection skill or event exposure?

**Pre-registered:** `research/pead_attack/PLAN.md`, sha256 a0a4488b…, registered 2026-09-23T05:06:57-0700, before any placebo draw. **Exploratory amendment:** `PLAN_AMENDMENT_1.md`, registered 05:24:10, after the main results were seen and before its own run.

**Book under test:** the production PEAD book, 2× config (5% positions, 100% gross), 2021-08-11 → 2025-06-27. The engine re-executes the production rules and reproduces the recorded `sweep_wide_5p0` ledger trade for trade: 625/625 trades, P&L differences 0.0, all 4,903 gate decisions identical. Its marked excess Sharpe is 0.6999, exactly the published value.

*Written by the PEAD-attack agent. Saved to disk by the main (director) session because the harness blocks subagents
from writing report files.*

**Director verification:**
- The PLAN and amendment hashes on disk match their ledger entries.
- File times confirm the order: the plan at 05:06, then the main draws at 05:21, the amendment at 05:24, and its draws at 05:26.
- `tests/test_pead_attack.py` has 10 tests, all passing.

## Verdict

**The ranking is not distinguishable from random selection.** PEAD, as run in production, is an event-exposure product with a risk throttle. The one component that could make it an edge is not statistically established, and it is not PEAD.

| Primary test (registered) | Real | Random selection, same rules (P1, 10,000 draws) | p (one-sided) |
|---|---:|---:|---:|
| Marked excess Sharpe | **0.70** | mean 0.46, 95% band [0.06, 0.85] | **0.113** |

- **Registered classification: C, "exposure edge without model skill."** The book beats generic post-announcement long exposure: P3 p = 0.0001, and P1L CAPM-alpha p = 0.039. It does not beat random selection under its own rules.
  - The P1L leg does not survive Holm correction (0.156).
  - The P1L leg reverses in the latest holdout.
- **Minimum detectable effect:** the Sharpe gap the P1 null could detect is 0.32. The observed gap is 0.24, so this null neither proves nor rules out selection skill.

## 1. All books (same events, dates, capacity rules, costs and marking)

| Book | What changes | Sharpe mean [95%] | p Sharpe | p CAGR | p CAPM α | p FF5+UMD α | Vol | Gross |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **R, real** | — | **0.70** | — | 10.29% | 4.18% (t 1.15) | 4.48% (t 1.26) | 9.6% | 0.42 |
| P1 (primary) | model probabilities shuffled within date | 0.46 [0.06, 0.85] | **0.113** | 0.013 | 0.026 | 0.013 | 7.3% | 0.42 |
| P1L | P1, all long | 0.47 [0.24, 0.70] | 0.025 | 0.078 | 0.039 | 0.045 | 10.7% | 0.42 |
| P1G | shuffled over the whole window | 0.33 [−0.15, 0.79] | 0.064 | 0.005 | 0.014 | 0.011 | 7.0% | 0.43 |
| P2, SUE-sign only | every event, 5%, random order | 0.20 [−0.03, 0.43] | 0.0001 | 0.0001 | 0.0001 | 0.0001 | 10.8% | 0.69 |
| P3, all events long | every event, long, 5%, random order | 0.15 [−0.55, 0.39] | 0.0001 | 0.0003 | 0.0001 | 0.0001 | 14.2% | 0.62 |
| *P1W (exploratory)* | *shuffled within ISO week* | *0.32* | *0.037* | *0.003* | *0.006* | *0.003* | *7.3%* | *0.42* |
| *P1V (exploratory)* | *week × pre-event-vol tercile* | *0.37* | *0.048* | *0.006* | *0.010* | *0.006* | *7.3%* | *0.42* |

Notes on the table:
- **Holm correction** covers the 19 registered secondary tests.
  - P2 and P3 stay significant (0.002–0.004).
  - All P1, P1L and P1G tests are 0.06–0.16.
- **P3 and the kill switch:** 15% of P3 draws trip the production 20% kill switch. Excluding them, P3's Sharpe is 0.26 and p is still 0.0001.
- **Real CAGR** is the marked NAV with idle cash earning T-bills. The cash-basis figure was 8.16%.

## 2. Decomposition of the 6.70%/yr mean excess return (registered formulas, CAPM)

| Component | %/yr | Share |
|---|---:|---:|
| Market beta (0.352 × Mkt-RF) | 2.52 | 38% |
| Generic post-announcement premium (mean α, P1L) | 1.95 | 29% |
| SUE-sign direction under random selection (α P1 − α P1L) | −0.58 | −9% |
| Model selection residual (α_R − mean α P1) | 2.82 | 42% |

- **In Sharpe terms:** random selection under identical rules delivers 0.46 of the 0.70 (66%). The ranking adds 0.24 (34%), at p = 0.113.
- **FF5+UMD version:** the residual is 3.2%/yr.
- **SUE sign adds nothing:** −0.6%/yr. The event-level re-check agrees:
  - long-short spread in the production window: 3.6 bps, p = 0.73;
  - |SUE| ≥ 1 in SPY-excess units: p = 0.93.

## 3. Where the residual comes from

- **Timing: the model's scores time the market.**
  - The daily mean score has Spearman −0.69 with the market's prior 20-day return (post-hoc).
  - Removing that timing lowers the random books to 0.32–0.33 (P1W, P1G).
  - Ranking and timing together are marginal: p 0.037 (exploratory P1W) to 0.064 (registered P1G, Holm 0.156).
- **Volatility does not explain it** (Amendment 1).
  - The real book's picks have ordinary pre-event volatility: 1.74%/day, vs 1.81% for all events.
  - Volatility-matched random selection leaves the α gap at 3.5%/yr (vs 3.8% within-week).
- **What the "PEAD" filter actually ranks on** (post-hoc):
  - its calibrated probability has Spearman **−0.63** with the stock's own raw 20-day pre-event return;
  - −0.12 with SUE and −0.21 with |SUE|.
  - **It is a short-term-reversal / buy-the-dip filter on recent reporters, not an earnings-surprise ranker.**
- **Stability across the model's holdouts:**

| Holdout | Real Sharpe | P1 mean | p |
|---|---:|---:|---:|
| holdout_a | 0.70 | 0.35 | 0.115 |
| holdout_b | 1.06 | 0.37 | 0.043 |
| holdout_c (most recent) | 0.47 | 0.70 | 0.73 |

  - In holdout_c, generic long exposure (P1L) did 1.10.

## 4. Leakage audit of the production ML filter

| # | Check | Finding | Evidence |
|---|---|---|---|
| L1a | Features after entry | **Yes: `dollar_volume_rank` is a static 2026 rank.** Training uses the mean close×volume of each name's last 63 sessions, 2026-05-15 → 08-14; this matches ticker A to the dollar. Live scoring uses a near-identical 2026 file (Spearman 0.99995). The rank's drift from point-in-time predicts forward returns (quintiles 43 → 283 bps). **Impact on the book is small:** the model barely uses it (Spearman with the probability −0.004). Re-scoring with a point-in-time rank gives Sharpe 0.673 (−0.03), with 87% trade overlap. | `reports/run_pead_expanded_pipeline.py:56-68`; `earnings/features.py:37-39`; `bot/signal_pipeline.py:148-151` |
| L1b | Train vs live mismatch in pre-earnings returns | Training uses the market-adjusted return over a window ending **on** the effective date, so it includes the reaction day (verified). The live bot and the replay use the **raw** return strictly before the announcement. The two correlate at only 0.22. This is not look-ahead: entry is at the effective-date close, and the label is (t, t+20]. But the live model runs on inputs it was not trained on, and the raw inputs carry the market's move (section 3). | `signals/features.py:57`; `earnings/features.py:33-35`; `signals/labeling.py:72`; `bot/signal_pipeline.py:109-124`; `live_backtest/historical_providers.py:96-106` |
| L1c | Timing / other | No entry before the announcement day. The 7 events stamped 02–03h were never traded. SUE is causal (`shift(1)`). EPS estimates are not point-in-time vintages. | `earnings/signal.py:28-33`; `earnings/sue.py:53` |
| L2 | Labels overlapping evaluation | **None.** The last train label ends 2020-04-23, before validation starts on 2020-05-06. The last validation label ends 2021-08-10, before the replay starts on 2021-08-11. The margin is one day; the purge is 20 unique event dates. | `ml/validation.py:73-92` |
| L3 | Calibration on the evaluation period | **No.** An in-memory refit reproduces the cached model to 1.5e-13, with identical weights and b = 0.9608. The calibrator was fit on validation (2020-05-06 → 2021-07-13), the weights come from validation AUC, and the payoff ratio from train. | `bot/signal_pipeline.py:96-100`; `ml/ensemble.py:60-68`; `ml/calibration.py:60-93` |
| L4 | Survivorship | The universe is today's 503 names. 92 names that were index members during the window are missing, e.g. AAL, ATVI, CTLT, DFS. 57 real trades (9%) were in names not yet in the index, e.g. CRWD, DASH, VRT, DELL; they netted −$4,412. Every placebo shares this universe, so survivorship cancels in the p-values except through L1a. | `bot/earnings_watcher.py:81-95` |
| L5 | Selection on the evaluation window | The 2× sizing and the 503-name universe were both chosen by replaying this same window. The model design was iterated after viewing these holdouts. | `live_backtest/compare_configurations.py:42-52`; `bot/run_cycle.py:84-104`; `bot/earnings_watcher.py:86-93` |
| L6 | Replay ≠ live | The replay's 30-calendar-day price window leaves 2,241 of 7,192 events (31%, mostly January/February) unscorable. All of them are scorable with the live 45-day window. **The 0.70 is a book the live bot would not trade.** | `live_backtest/historical_providers.py:35`; `bot/signal_pipeline.py:66` |

Accounting quirk: `mtm_book` credits T-bill interest on the exit day (`research/pead_audit/mtm_audit.py:104-108`). Fixing it changes the Sharpe by −0.007.

## 5. Review of the earlier SUE placebo (`research/edge_sue_placebo.py`)

- **Reproduced exactly:**
  - event level: s2 9.68 bps, p 0.2918; s3 p 0.927;
  - portfolio level: long-short p 0.96, large-SUE p 0.553.
- **No leakage found.** Entry is at the next open after the reaction day (`edge_executable_probe.py:91,97`).
- **Weaknesses:**
  - s1 and s2 are the same test: rank correlation 1.0 across permutations, and no zero SUEs.
  - There is no +1 correction on the p-values (negligible).
  - It tests SUE, not the production filter.
  - 2% of events sit on single-event dates.
  - The minimum detectable s2 is about 10 bps, so its null is only loosely bounded.
- **Its conclusion stands and is sharpened here:** SUE carries no drift information in this universe.

## 6. The forward paper test

- **What it can tell us:** implementation fidelity: fills, costs, turnover, the data feed, and whether the marked NAV behaves like the replay.
- **What it cannot tell us:**
  - whether the book has an edge. Reaching 80% power to show Sharpe > 0 at 0.70 takes **12.6 years**. Separating the book from random selection unpaired takes **213 years**.
  - The current record is also too thin: 3 genuine forward events, a stale SUE feed, and a live candidate stream 31% larger than the replay's (L6).
- **A better comparison: paired, same candidate stream.** Run, with zero capital:
  - K ≥ 5 within-date random-selection shadow books, identical to P1 (this engine, fed nightly from the cycle log);
  - a week-shuffled shadow (P1W), to separate ranking from timing;
  - an all-long shadow (P1L).
- **Test the daily paired difference, not Sharpe levels.**
  - Correlation with a shadow is 0.82 and the tracking error 4.6%/yr, so about **12 years** are needed at the historical 3.3%/yr gap.
  - That is far better than 213, but still not a way to confirm an edge.
  - Use it as a **futility/kill monitor.** Pre-register a rule, e.g. retire the "edge" label if the paired gap is ≤ 0 after four earnings seasons.

## 7. What this means for PEAD's standing

- PEAD's 0.70 is not an edge beyond beta and generic post-announcement exposure:
  - about two thirds of its Sharpe is available to random selection under the same rules;
  - its CAPM alpha has t 1.15;
  - the remaining third is not significant, is a reversal/dip-timing effect fed by the train/live input mismatch, and was negative against random selection in the latest holdout.
- **It should lose the "best surviving strategy" label.** Any future PEAD claim must beat **P1**, not zero, SPY or the universe control. P1's mean Sharpe is 0.46.

## Files

Code, in `research/pead_attack/`:
- `inputs.py`, `engine.py`, `marking.py`, `common.py`
- `reproduce.py`, `placebo.py`, `analysis.py`, `amendment1.py`, `leakage.py`, `review_sue_placebo.py`
- tests: `tests/test_pead_attack.py`, 10 tests, passing

Results, in `reports/pead_attack/`:
- `results.json`, `pvalues.csv`, `decomposition.csv`, `amendment1.json`, `leakage.json`
- `reproduction.json`, `sue_placebo_review.json`, `real_book_daily.csv`
- `placebo_draws_{P1,P1L,P1G,P2,P3,P1W,P1V}.csv`, `inputs/`

Reproduce, from the repo root:
```
PYTHONPATH=. .venv/bin/python -m research.pead_attack.inputs
PYTHONPATH=. .venv/bin/python -m research.pead_attack.reproduce
PYTHONPATH=. .venv/bin/python -m research.pead_attack.placebo
PYTHONPATH=. .venv/bin/python -m research.pead_attack.analysis
```
