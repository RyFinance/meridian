# Japan-hours information to US regular-session ES: development null

2026-09-23. **FAIL DEVELOPMENT. Validation remains locked.** No trades, production changes, commits, pushes or paid data.

## What was new

The prior ledger seriously tested own-market ES/NQ intraday rules, daily multiasset and ETF prices, FX carry, COT, macro surprises, and other families. It did **not** test completed Asia-hours Japanese equity-index pricing as a predictor of the later US regular session. This was a new **information source and clock**, not a changed momentum lookback or weight. Live LSE MCP `search_instruments` and `get_history` confirmed `JP225/USD` 30-minute history alongside ES 30-minute history. The local ES file matched a fresh MCP sample on all 46 bars and OHLC values for 2018-06-04.

The information is less clean than its label suggests. `JP225/USD` is an indicative Nikkei-linked quote, with ten cash-hour bars on 72 dates absent from the independently retrieved `^N225` exchange-date set. LSE and `^N225` daily closes differ by median 9.1 bp, 95th percentile 49.7 bp, and maximum 242.5 bp on 1,112 common dates. The 2026 feed sample also had 46 bars (24-hour coverage) instead of ten. The pre-return [amendment](../../research/japan_us_flow/PLAN_AMENDMENT_1.md) froze an official-date mask and did not use Yahoo prices as the signal. The original [plan](../../research/japan_us_flow/PLAN.md) and amendment were entered in `research/preregistrations.jsonl` at 13:04 and 13:06 Pacific, before the first return calculation. The raw LSE responses and hashes are archived under `data/lse/japan_us_flow/`.

## Frozen test

On dates with ten exact LSE Japan cash-hour bars and an independent `^N225` trading-date record, go long ES from the 09:30 ET bar open to the 15:30 ET bar close if the Japan 09:00–15:00 JST LSE quote rose; short if it fell. Charge 0.5 bp per side, or 1.5 bp in stress. Exclude the existing intraday plan's ES roll window. The direct control takes the sign of ES's own prior-16:00-to-09:30 move, with the same eligible dates, fills and costs. An always-long same-hours control and reversed-Japan-sign placebo are descriptive. Development is 2016-06-01 through 2020-12-31. No 2021+ Japan input was loaded.

The development gate was net excess Sharpe ≥ **0.841** (1.8/√4.583 years), positive stressed annual mean, positive J1-minus-own-overnight annual mean and paired one-sided 21-day block-bootstrap p < 0.05. The null used 5,000 circular shifts of the Japan signs by at least 252 eligible sessions, with the existing null-lab API in development-only mode. An exactness assertion checked the engine against direct return arithmetic.

## Result

| Measure, 2016-06–2020-12 | J1 Japan sign | ES own-overnight sign | Always long ES |
|---|---:|---:|---:|
| Net annualized mean | **3.75%** | −0.87% | 1.55% |
| Net excess Sharpe | **0.30** | −0.07 | 0.12 |
| Max drawdown | −28.7% | −27.4% | −21.1% |

J1 gross Sharpe was 0.48; 3× cost stress reduced its annualized mean to **−0.75%** and Sharpe to −0.06. There were 1,025 eligible trades across 1,145 ES full-session dates. J1's net annualized mean exceeded the own-overnight control by 4.62%, but the paired block-bootstrap p was **0.166**. The reversal placebo had Sharpe −0.66. Removing the best contiguous 12 months changed J1's net Sharpe to −0.64; removing the best 24 months changed it to −1.12. These are diagnostics, not gates or post-hoc variants.

Under the registered shift null, **1.28% ± 0.16 percentage points** of worlds cleared the Sharpe-plus-stress development gate. The observed J1 Sharpe was at least matched by **15.7%** of shift worlds. The null pass rate describes the gate's false-positive frequency on this price path; J1 itself did not pass. The weak positive raw result does not establish incremental Japanese information, especially given the indicative quote source and uncertain execution costs.

## Integrity and next action

- The input was archived before returns: 11,835 LSE Japan 30-minute rows from 2016-06 through 2020-12, plus an independent official-date snapshot. The run manifest records SHA-256 for Japan, date mask and ES inputs. Of 1,184 LSE Japan dates, 72 were rejected for lacking an official session and two for the wrong bar schedule. There were no bad Japan OHLC bars among accepted dates. The source has no point-in-time vendor-vintage history, and continuous ES lacks an individual-contract roll/settlement audit.
- This is a **null result**. Do not rescue it with a different Japanese proxy, threshold, time slice, direction, cost or control inside the same trial. Leave 2021+ validation locked. Any future cross-market study needs an independently timestamped, exchange-faithful source and a new information mechanism registered before returns. The current project priority remains clean forward evidence and genuinely different information, not another price-rule variation.
- Reproduce: `PYTHONPATH=. .venv/bin/python -m research.japan_us_flow.evaluate`. The existing null-lab suite passed 21/21 after adding development-only support, and the ES MCP/local sample matched exactly.
