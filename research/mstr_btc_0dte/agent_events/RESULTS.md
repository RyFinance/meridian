# P1/P5 purchase-announcement rules — holdout result (registered): FAILED

Plan/gates: `GATES_ADDENDUM.md` (registered 2026-10-17T00:11:42, before the run).
Runner: `event_study.py` (run once; live SEC fetches, no cache). Gate computation: `gate_p1p5.py`
(registered `gate_computation` entry 2026-10-17T00:14:55, one no-result crash amendment
00:15:12) → `gate_p1p5.json`. Costs: 3 bp/side + $0.005/share each side
(pre-split $0.0005 pseudo-share). Entry = close of first MSTR session at/after EDGAR acceptance.

## Primary statistic (as registered): **FAIL**

| | value | required |
|---|---|---|
| P5 holdout n | 85 events (27 no-leverage episodes) | — |
| P5 holdout net mean | **+1.23%** per 5-session window | > 0 ✓ |
| Control: unconditional overlapping 5-session mean, holdout sessions | **+1.88%** (946 sessions) | — |
| Excess mean | **−0.66%** | > 0 ✗ |
| Bootstrap 2.5% quantile of excess (10k draws, seed 20261017) | **−3.28%** | > 0 ✗ |
| **PASS iff q025 > 0 AND net mean > 0** | **✗ FAIL** | |

Robustness to the control reading (disclosed before running): under the *daily*-return control
(+0.388%/day, the reading used by `event_study.py`'s own `ordinary_mstr_benchmark.csv`), the
excess is +0.84% and q025 is **−1.79%** — still a fail. The verdict does not hinge on which
control definition is used.

Secondary P1 (reported only): holdout n=85, net mean −0.58%, control +0.39%, excess **−0.96%**,
q025 **−1.96%** — also negative.

## The dev→holdout flip, again

- Dev (2020–2022, n=21): P5 excess **+2.94%** (event mean +3.85% vs control +0.91%); P1 excess −1.39%.
- Holdout (2023–2026, n=85): P5 excess −0.66%; P1 excess −0.96%.
- The dev P5 point estimate (the reason the rule was frozen) did not survive, matching the C1/C2
  and short-vol pattern: small-sample dev edge, holdout regression to below the control.

## Reported-only detail (none of this changes the verdict)

- Per-year P5 net means: 2023 +11.6% (t 2.75), 2024 +9.7% (t 1.67), 2025 −1.4%, 2026 −1.8%.
  The pre-2025 years beat the sample mean; 2025–26 are flat-to-negative, consistent with the
  events adding nothing beyond MSTR drift (and MSTR drifting badly in 2026).
- Cost sensitivity: event means survive to 20 bp/side (P5 holdout +0.88%/window), i.e. the trades
  are not cost-killed at the trade level — they simply do not beat unconditional long exposure.
- Episodes: 27 holdout episodes, +61.9% compound net for a single-unit book, max drawdown −78.8%.
  As a timing book this is worse than the benchmark's own compounding with comparable pain.
- BTC-regime split (holdout P5): BTC-up prior-5d +1.97% (n=36), down/flat +1.28% (n=40),
  path-unavailable −2.0% (n=9). Every bucket at/below the +1.88% control — no regime saves it.
- Funding label (holdout P5): ATM-only +0.86% (n=66), ATM+convertible −1.45% (n=13), cash n=4
  +13.6% (tiny n, ignored).

## Outcome per plan

FAIL → recorded in the graveyard (`../REPORT.md`); no re-runs on this window. The purchase-announcement
family (P1/P5) is closed on 2023+. Note for the record: the 2023+ "event windows are better than
ordinary MSTR sessions" hypothesis is now measured, one-shot, and rejected; event count 106
(dev 21 / holdout 85), zero source-fetch failures (`event_source_failures.csv` empty).
