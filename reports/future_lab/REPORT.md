# Simulated-futures lab: path risk, sequence dependence, forward-test design

Code: `research/future_lab/` · run: `PYTHONPATH=. .venv/bin/python -m research.future_lab.run` (seed 20260923, 142 s,
peak about 2 GB) · tests: `tests/test_future_lab.py` (19 passed) · numbers: `results.json` and the CSVs beside this file ·
frozen rule: `monitoring_rule_spec.json` (sha256 `0cf8986f…ebf79`).

*Written by the future-lab agent. Saved to disk by the main (director) session because the harness blocks subagents
from writing report files.*

**This quantifies uncertainty and path risk in history already observed. It is not new evidence of an edge.** Every
resampler reuses the same 3.9 years (PEAD, 2021-08 → 2025-06) or 9.7 years (SPMO/GLD, 2017-01 → 2026-09). None of
them can produce a regime, crash or structural break that the sample does not contain.

## Decisions first

1. **PEAD (2× and live 2.5%).** The risk is being no better than the control, not losing money.
   - Path risk is small. Over 5 years:
     - P(max drawdown > 20%): 4% at 2×, about 0% at 2.5%;
     - P(NAV < 50%): about 0, even with 2× leverage on top.
   - P(behind the no-model control after 3 years): 30% at 2×, 22% at 2.5%.
   - Extra slippage erases the edge. At 11.4 turns a year, +10 bps a side raises that probability to 48% / 40%;
     +25 bps raises it to 75% / 72%.
   - **The selection edge comes from one episode.** Remove the best 24 months of active return (2021-10 → 2023-10) and
     the IR against the control falls from 0.30 to −1.29. Across the rest of the sample, which includes the latest
     20 months, selection lost 4.9%/yr against the control. Only 2% of stationary-bootstrap histories are this
     concentrated.
   - Forward data needed for 80% power:
     - to reject Sharpe 0 at the backtest's 0.70: 9–11 years (13 under iid);
     - to beat the control: 60–80 years at 2×, 28–37 years at 2.5%.
   - **A forward test can catch PEAD failing. It cannot confirm PEAD.**
2. **SPMO/GLD 50/50.** The absolute result depends on 2023–25, and so does the edge over SPY/GLD.
   - Five-year path risk:
     - P(max drawdown > 20%): 11–19% under the bootstraps, 40% under the GARCH alternative;
     - P(max drawdown > 30%): 0.2–1.1% under the bootstraps, 16% under GARCH;
     - P(NAV < 50%) at 1×: 0%, or 0.8% under GARCH; at 2×: 0.1–0.2%, or 6.7% under GARCH.
   - P(behind SPY/GLD after 3 years): 18–24%.
   - Remove 2023-10 → 2025-10: CAGR 17.7% → 10.8%, Sharpe 1.04 → 0.65.
   - Remove 2023-07 → 2025-07: IR against SPY/GLD 0.48 → 0.10; active return 2.5% → 0.5%/yr.
   - Gold's run lifts SPY/GLD by as much (its CAGR falls 15.1% → 9.1% without its best 24 months). **What is specific
     to SPMO/GLD is the 2023–25 momentum stretch.**
   - Forward data needed for 80% power:
     - to reject Sharpe 0: 44 months at the bootstrap standard error, up to 111 months across methods (68 under iid);
     - to beat SPY/GLD: 20–29 years.
3. **Controls.**
   - SPY/GLD, P(5-year max drawdown > 20%): 15–41%.
   - SPY over 5 years:
     - P(max drawdown > 20%): 56–69%;
     - P(max drawdown > 30%): 14–41%;
     - P(NAV < 50%) at 2× leverage: 5–13%. The 2005–2026 window gives 16–21%.
4. **The sample window matters more than the method.** Adding 2005–2016, which includes 2008, raises SPY/GLD's
   P(5-year max drawdown > 30%) from 1% to 15%, and SPY's unlevered ruin from 0% to 3%. The spread between methods
   (table 2a) is the model uncertainty within one window. It is not the full uncertainty.
5. **Monitoring.** The frozen Bayesian rule (section 5) kills clear failures:
   - if true Sharpe is 0, it stops 36–48% of paths by 24 months and 91–100% by 60 (kill or revert to control);
   - drawdowns beyond history are caught;
   - it almost never promotes. Promotion by 60 months: PEAD 2× 0%, live PEAD 7%, SPMO/GLD 25%, and only if the
     candidate is exactly as good as backtested.
   - Register it in `research/preregistrations.jsonl` before 2026-09-24 (PEAD) and 2026-10-02 (SPMO/GLD). This lab
     did not write to that file.

## 1. What was built

| Engine | Detail |
|---|---|
| Stationary bootstrap (SB, primary) | Politis–Romano, geometric blocks. Expected length from Politis–White (2004/2009): the maximum over each column's returns **and absolute returns**, since returns alone give 1–10 days and would destroy volatility clustering. Result: 44 days (PEAD panel), 83 (2017–26), 143 (2005–26). |
| Circular block | Fixed Politis–White circular-block length: 51 / 95 / 164 days. |
| Regime (vol tercile) | Causal SPY 63-day trailing vol, using returns up to t−1. Fixed terciles of the 2003–2026 history (11.5% / 15.6%). A fitted daily Markov chain simulates the regime path; mean durations are 45 / 28 / 76 days (2017–26). Rows come from a stationary bootstrap inside the current regime's own subsample. |
| Regime (drawdown) | Two states, SPY more or less than 10% below its 252-day high at t−1. Mean durations 117 / 19 days. |
| FHS GJR-GARCH-t | GJR(1,1) with variance targeting and a Student-t likelihood, fitted to each series' excess return. Standardised residual vectors are drawn jointly by date. The asymmetry is rescaled to the residuals' own skew so the fitted persistence holds. |

- **Joint.** Every draw takes a whole date: strategy, controls, SPY, T-bill rate and turnover together. This keeps the
  correlations (PEAD with its universe control, 0.91; SPMO/GLD with SPY/GLD, 0.93).
- **Seeded.** No IID Gaussian draws anywhere.
- **Inputs:**
  - PEAD: the marked NAVs in `reports/pead_audit/wide_5p0_curves.csv` and `wide_2p5_curves.csv` (`mtm_rf`, excess
    over `rf_index`). Control: `universe_control`. Turnover comes from the sweep ledgers, 11.4×/yr (2×) and 6.9×/yr
    (2.5%).
  - SPMO/GLD and SPY/GLD: the audited ledgers `momentum_gold_full.csv` and `market_gold_full.csv`. The initial-purchase
    and final-liquidation days are dropped. Turnover is 0.31×/yr and 0.28×/yr. T-bills from `cash_rates`.
  - SPY: the local yfinance cache.
  - The 2005–2026 sensitivity panel uses a simplified SPY/GLD mix (first-session-close rebalance). It tracks the
    audited ledger at daily correlation 0.99998 and within 0.04 pp of CAGR.
- No LSE Terminal data was needed.
- **FHS credibility check.** Median simulated path volatility must reach at least 60% of history:
  - it passes for SPY, SPY/GLD and SPMO/GLD (77–90%);
  - it **fails for PEAD** (26–32%). PEAD's volatility is driven by exposure and its standardised residual kurtosis
    is 33.
  - FHS is therefore excluded from PEAD's method ranges and charts. It is still reported in the CSVs.

## 2. Path risk (5,000 paths × 5 years per method)

### 2a. Headline

Figures are for the stationary bootstrap, with the [min–max] across credible methods.

| | 5y CAGR p5 / p50 / p95 | 5y excess Sharpe p5 / p50 / p95 | P(5y DD > 20%) | P(5y DD > 30%) | Longest underwater, median / p95 (yrs) | P(3y behind control) |
|---|---|---|---|---|---|---|
| PEAD 2× (vs universe control) | 3.7 / 10.4 / 17.3% | 0.07 / 0.71 / 1.37 | 3.8% [0.9–4.6] | 0.1% [0–0.1] | 1.0 / 2.6 | 30% [25–30] |
| PEAD 2.5% live (vs universe control) | 3.8 / 7.9 / 12.1% | 0.09 / 0.74 / 1.40 | 0% [0–0.1] | 0% | 0.9 / 2.1 | 22% [18–22] |
| SPMO/GLD (vs SPY/GLD) | 8.2 / 17.7 / 28.5% | 0.49 / 1.06 / 1.67 | 12.5% [10.5–40.0] | 0.5% [0.2–16.2] | 0.9 / 2.0 | 18% [18–24] |
| SPY/GLD (vs SPY) | 6.6 / 15.2 / 24.4% | 0.40 / 0.99 / 1.60 | 41% [15–41] | 0.9% [0.6–12.7] | 0.9 / 2.2 | 50% [49–56] |
| SPY (vs T-bills) | 4.2 / 15.5 / 26.1% | 0.19 / 0.76 / 1.44 | 69% [56–69] | 41% [14–41] | 1.0 / 2.8 | 7% [6–10] |
| *SPY/GLD, 2005–26 window* | 2.3 / 11.5 / 21.2% | 0.14 / 0.79 / 1.41 | 41% [32–42] | 15% [5–16] | 1.2 / 3.1 | 47% [47–52] |
| *SPY, 2005–26 window* | −2.3 / 11.8 / 21.9% | −0.05 / 0.63 / 1.30 | 65% [64–82] | 41% [32–42] | 1.2 / 4.0 | 15% [15–18] |

### 2b. CAGR at 1, 3 and 5 years

Stationary bootstrap, p5 / p50 / p95, with P(max drawdown > 20%) in brackets.

| | 1 year | 3 years | 5 years |
|---|---|---|---|
| PEAD 2× | −4.1 / 10.6 / 26.8% (0.1%) | 1.7 / 10.3 / 19.4% (2.0%) | 3.7 / 10.4 / 17.3% (3.8%) |
| PEAD 2.5% | −1.3 / 8.1 / 17.4% (0%) | 2.6 / 7.9 / 13.3% (0%) | 3.8 / 7.9 / 12.1% (0%) |
| SPMO/GLD | −2.5 / 17.6 / 42.6% (1.5%) | 5.5 / 17.7 / 31.9% (7.5%) | 8.2 / 17.7 / 28.5% (12.5%) |
| SPY/GLD | −3.8 / 15.5 / 36.6% (8.8%) | 3.9 / 15.3 / 27.0% (27.8%) | 6.6 / 15.2 / 24.4% (41.3%) |
| SPY | −9.7 / 16.2 / 40.3% (18.9%) | 0.9 / 15.7 / 29.2% (51.7%) | 4.2 / 15.5 / 26.1% (69.2%) |

### 2c. Leverage

Constant daily leverage L on each series' own NAV. The borrowed (L−1)×NAV is financed at T-bill + 1.5%. This is
conservative for PEAD, whose average gross exposure is 25–42%: an account could scale PEAD without borrowing.

| | P(NAV < 50% within 5y), 1× | 1.5× | 2× | P(5y DD > 30%) at 2× | Median 5y CAGR at 2× |
|---|---|---|---|---|---|
| PEAD 2× | 0% | 0% [0–0.04] | 0.1% [0.04–0.14] | 26% [14–26] | 14.7% |
| PEAD 2.5% | 0% | 0% | 0% | 1.0% [0.1–1.7] | 10.3% |
| SPMO/GLD | 0% [0–0.8] | 0% [0–3.0] | 0.2% [0.1–6.7] | 60% [55–65] | 30.6% |
| SPY/GLD | 0% [0–0.8] | 0% [0–2.5] | 0.4% [0.2–5.4] | 60% [51–62] | 25.6% |
| SPY | 0.02% [0–3.4] | 2.0% [0.8–7.5] | 10.9% [4.6–13.2] | 92% [76–92] | 24.0% |
| *SPY, 2005–26* | 2.8% [0.6–5.0] | 12.1% [6.4–12.1] | 20.7% [15.7–20.7] | 91% [82–94] | 17.2% |

### 2d. Cost shocks

Stationary bootstrap. For PEAD the shock is charged to the strategy only: its controls are counterfactual placements,
so the shock stands for single-name execution cost. For SPMO/GLD, both SPMO/GLD and SPY/GLD pay it.

| | Turnover/yr | Drag at +10 / +25 bps a side | Median 5y CAGR: base / +10 / +25 | Median 5y Sharpe: base / +10 / +25 | P(3y behind control): base / +10 / +25 |
|---|---|---|---|---|---|
| PEAD 2× | 11.4× | 1.14 / 2.85%/yr | 10.4 / 9.1 / 7.3% | 0.71 / 0.59 / 0.41 | 30 / 48 / 75% |
| PEAD 2.5% | 6.9× | 0.69 / 1.73%/yr | 7.9 / 7.1 / 6.0% | 0.74 / 0.62 / 0.43 | 22 / 40 / 72% |
| SPMO/GLD | 0.31× | 0.03 / 0.08%/yr | 17.7 / 17.7 / 17.6% | 1.06 / 1.06 / 1.05 | 18 / 18 / 18% |
| SPY/GLD | 0.28× | 0.03 / 0.07%/yr | 15.2 / 15.2 / 15.2% | 0.99 | 50 / 50 / 51% |

**PEAD's historical edge over its control, about 1.0–1.2%/yr, is smaller than the +10 bps/side shock.**

### 2e. No edge over the control

Each candidate's mean is shifted to its control's; the stationary bootstrap is otherwise unchanged. This shows what
the path risk looks like without the historical outperformance.

| Candidate | Shift | P(3y behind control) | Median 5y CAGR | P(5y DD > 20%) |
|---|---|---|---|---|
| PEAD 2× | −1.2%/yr | 49% | 9.0% | 5.9% |
| SPMO/GLD | −2.5%/yr | 54% | 14.9% | 18% |

Drawdown and ruin risk barely change. As in the historical sample, it is dominated by the shared market exposure.

**Model uncertainty.**
- Medians agree across methods to within 1–2 CAGR points: every method recentres on the same history.
- Tails do not agree:
  - The regime bootstraps give milder SPY and SPY/GLD tails: P(DD > 30%) is 14–17% against SB/CB's 39–41%. Causal
    regime labels lag a crash, so a regime switch splices blocks and breaks up the historical crash sequence. The
    regimes are not safer.
  - FHS gives the heaviest tails, because it is the only method that can produce volatility regimes and drawdowns
    beyond the sample's worst.
  - The bootstrap drawdown curves (`drawdown_distributions.png`) have cliffs at the historical worst drawdowns: SPY
    −34% (2020) and SPMO/GLD −18.7%. The bootstraps mostly replay the one crash they have seen.

## 3. Ordering and single-sequence dependence

Terminal wealth is exactly invariant to reordering: a product of fixed daily returns does not depend on order. Across
2,000 permutations of monthly regime episodes, the largest deviation was below 1e-14. What moves is the path.

| 2,000 regime-episode permutations | PEAD 2× | PEAD 2.5% | SPMO/GLD | SPY/GLD | SPY |
|---|---|---|---|---|---|
| Episodes (median length) | 13 (62 days) | 13 | 33 (62 days) | 33 | 33 |
| Max DD: actual / p5 / median | −12.8 / −15.0 / −12.8% | −8.4 / −9.1 / −8.4% | −18.7 / −22.3 / −17.5% | −20.4 / −23.3 / −18.2% | −33.7 / −35.0 / −28.3% |
| CAGR, first 3 years: actual (p5–p95) | 11.8% (5.8–13.8) | 8.2% (4.9–9.6) | 14.0% (7.7–29.3) | 12.9% (5.7–24.8) | 15.0% (2.6–27.3) |
| Active return vs control, first 3 years: actual (p5–p95) | +11.1% (−2.3 to +12.3), 92nd pct | +6.3% (−0.4 to +7.4), 89th pct | +3.0% (−1.9 to +18.0) | −5.3% (−18.6 to +25.5) | — |
| Share of orderings where the section 5 kill rule fires | 0.4% | 8.2% | 7.4% | 6.6% | 3.8% |

**Best contiguous window removed.**
- The p column is the probability that a stationary-bootstrap history of the same length loses at least as much
  Sharpe/IR when its own best window is removed. A low p means the history is more concentrated than a stationary
  process with the same mean and volatility would give.
- Removing a best window always hurts, which is why the comparison is against the bootstrap and not against zero.

| Candidate | Window, chosen by | Dates | Full → removed | p |
|---|---|---|---|---|
| PEAD 2× | 24m, active vs control | 2021-10-21 → 2023-10-23 | IR 0.30 → **−1.29**; active +1.2 → −4.9%/yr | **0.02** |
| PEAD 2× | 12m, active | 2022-02-24 → 2023-02-24 | IR 0.30 → −0.45 | 0.10 |
| PEAD 2× | 24m, excess | 2022-10-03 → 2024-10-03 | CAGR 10.3 → 0.1%; Sharpe 0.70 → −0.13 | 0.36 |
| PEAD 2.5% | 24m, active | 2021-09-03 → 2023-09-06 | IR 0.44 → −0.83; active +1.0 → −1.7%/yr | 0.10 |
| PEAD 2.5% | 24m, excess | 2022-10-17 → 2024-10-17 | CAGR 7.8 → 1.2%; Sharpe 0.73 → −0.11 | 0.36 |
| SPMO/GLD | 24m, excess | 2023-10-05 → 2025-10-08 | CAGR 17.7 → 10.8%; Sharpe 1.04 → 0.65; IR 0.48 → 0.21 | 0.09 |
| SPMO/GLD | 24m, active vs SPY/GLD | 2023-07-18 → 2025-07-21 | IR 0.48 → **0.10**; active 2.5 → 0.5%/yr | 0.18 |
| SPMO/GLD | 12m, excess (the gold year) | 2025-01-28 → 2026-01-28 | CAGR 17.7 → 14.0%; IR unchanged (0.48 → 0.47) | 0.55 |
| SPY/GLD | 24m, excess | 2024-01-25 → 2026-01-28 | CAGR 15.1 → 9.1%; Sharpe 0.97 → 0.59 | 0.13 |
| SPY | 24m, excess | 2020-03-24 → 2022-03-22 | CAGR 15.1 → 8.5%; Sharpe 0.73 → 0.38 | 0.13 |

- **Relocation.** Each best window was moved to every 21-day offset of the remaining history.
  - SPMO/GLD's max drawdown stays between −17.7% and −18.7%, and the kill rule never fires. Its path risk does not
    depend on where the good run lands; its level does.
  - Relocating SPY's 2020–22 rebound leaves the crash without its recovery: max drawdown reaches −35% to −49%, and
    the drawdown kill fires in 55% of positions.
- **Verdict.**
  - PEAD's edge over its control is one episode, and it is unusual (p 0.02).
  - SPMO/GLD's edge over SPY/GLD is mostly one 24-month stretch (p 0.18, not unusual for a stationary process).
  - The 2025 gold year inflates both SPMO/GLD and its control roughly equally.

## 4. Forward-test design (extends `reports/forward_power/REPORT.md`)

- **Same convention:** one-sided 5%, 80% power, (1.645 + 0.842)² = 6.18. `tests/test_future_lab.py` reproduces that
  report's iid table exactly (Sharpe 0.5 → 24.7 years; 1.0 → 6.2).
- **Extension.** The iid standard error is replaced by k/√years:
  - k is the resampled standard error of the 5-year Sharpe (or IR) × √5.
  - The paired test uses the strategy-minus-control return, so the correlation enters directly:
    IR = (μs − μc)/√(σs² + σc² − 2ρσsσc).
- **k is below 1.** In these samples daily returns mean-revert slightly, so k is 0.8–0.9. Plan on the upper end of
  the range or on iid.

| | Backtest Sharpe | k (SB) [range] | Months to reject Sharpe 0 at Ŝ [range] (iid) | At Ŝ/2 | IR vs control | ρ | Months to beat control at IR [range] | At IR/2 | Assurance at 36 months: vs 0 / vs control |
|---|---|---|---|---|---|---|---|---|---|
| PEAD 2× | 0.70 | 0.87 [0.82–0.93] | 115 [103–132] (151) | 462 | 0.30 | 0.91 | 831 [712–969] | 3,325 | 42% / 20% |
| PEAD 2.5% | 0.73 | 0.88 [0.83–0.95] | 109 [95–125] (139) | 436 | 0.44 | 0.92 | 358 [330–439] | 1,433 | 44% / 26% |
| SPMO/GLD | 1.04 | 0.81 [0.80–1.28] | 44 [44–111] (68) | 178 | 0.48 | 0.93 | 237 [237–346] | 949 | 70% / 28% |
| SPY/GLD | 0.97 | 0.83 [0.83–1.25] | 54 [54–124] (79) | 216 | −0.07 (vs SPY) | 0.76 | never | never | 63% / 6% |
| SPY | 0.73 | 0.84 [0.81–1.27] | 100 [92–226] (140) | 399 | — | — | — | — | 45% / — |

- **Assurance** is the probability that a 36-month forward test ends significant, averaged over the backtest's own
  uncertainty about the true Sharpe.
- Taking the backtest at face value, a 3-year forward test has a 42–70% chance of confirming Sharpe > 0, and a
  20–28% chance of confirming an edge over the control.

## 5. Pre-specified monitoring rule

Frozen in `monitoring_rule_spec.json`. The evaluator is
`research.future_lab.forward.evaluate_from_spec(spec_path, name, daily_df)`. It refuses a spec whose sha256 no longer
matches, then applies the rule at each month-end.

**Inputs.** Daily net return, T-bill return and control return, taken only from `forward_start`. PEAD's forward start
is 2026-09-24, and backfilled ledger events are excluded. SPMO/GLD's is 2026-10-02, its first fill.

**Posterior.** Normal–normal on the annualised Sharpe or IR. The estimate is modelled as N(true, k²/years).
- **Futility prior** (used to kill or revert): N(0.5 × backtest, resampled SE of the backtest²). Killing a candidate
  therefore needs forward evidence against a haircut version of its own backtest.
- **Sceptical prior** (used to promote): N(0, (backtest/1.645)²), after Spiegelhalter et al. Only forward data can
  carry a promotion.

**Decisions.** Decisions are terminal. At each look they are checked in the order listed.

| Decision | Condition |
|---|---|
| KILL_DRAWDOWN | Running max drawdown since forward start is deeper than the 99th percentile of resampled running max drawdowns for that elapsed month. |
| KILL_SHARPE | From month 6: futility-posterior P(Sharpe > 0.30) < 10%. |
| REVERT_TO_CONTROL | From month 24: futility-posterior P(IR vs control > 0) < 10%; hold the control instead. |
| PROMOTE | From month 24: sceptical P(Sharpe > 0) ≥ 95%, and sceptical P(IR > 0) ≥ 90%, and no open implementation review. |
| END_NO_DECISION | Reached 60 months without any of the above. |

**Implementation reviews** (not automatic kills). Any of these opens a review:
- realised cost more than 25 bps a side above the assumption;
- turnover outside 0.5–1.5× of the backtest;
- a missing mark or fill.

| Parameters | Futility prior (Sharpe) | Sceptical sd | k | Drawdown kill at 1 / 6 / 12 / 24 / 36 / 60 months |
|---|---|---|---|---|
| PEAD 2× | N(0.35, 0.45²) | 0.43 | 0.87 | −8.2 / −13.4 / −16.6 / −20.0 / −21.6 / −23.7% |
| PEAD 2.5% | N(0.36, 0.45²) | 0.44 | 0.88 | −5.2 / −8.4 / −10.0 / −11.6 / −12.7 / −13.8% |
| SPMO/GLD | N(0.52, 0.26²) | 0.64 | 0.81 | −11.2 / −18.7 / −21.1 / −24.3 / −25.9 / −28.0% |

**Operating characteristics.** 4,000 stationary-bootstrap forward paths, with the candidate's mean shifted to each
scenario. Each cell is cumulative kill (Sharpe or drawdown) / revert / promote.

| True state | PEAD 2×, by 24m | PEAD 2×, by 60m | PEAD 2.5%, by 60m | SPMO/GLD, by 24m | SPMO/GLD, by 60m |
|---|---|---|---|---|---|
| As backtested (Sharpe 0.70 / 0.73 / 1.04) | 5.8 / 0.2 / 0% | 7.1 / 1.7 / 0% | 5.9 / 0.8 / 6.6% | 4.9 / 0 / 2.1% | 6.1 / 0 / 25.0% |
| Half the backtest Sharpe | 10.4 / 3.5 / 0% | 13.7 / 25.2 / 0% | 13.0 / 20.9 / 0% | 13.2 / 0.1 / 0% | 19.5 / 23.0 / 0% |
| No edge over the control | 7.8 / 0.6 / 0% | 9.6 / 5.5 / 0% | 9.5 / 4.6 / 0.5% | 8.6 / 0 / 0.3% | 10.8 / 0 / 3.5% |
| Sharpe 0 | 19.4 / 19.0 / 0% | 23.3 / 68.0 / 0% | 20.5 / 72.2 / 0% | 28.0 / 19.6 / 0% | 31.3 / 68.5 / 0% |

- **False kills.** When the candidate is exactly as backtested, the drawdown boundary produces false kills in about
  6% of paths over 60 months (1–8% across the bootstrap methods).
- **Under a GARCH-type future**, SPMO/GLD crosses its boundary 28.5% of the time. The boundary asks whether the
  candidate still behaves like its history. It does not ask whether the candidate is good.
- **Blind spot.** The rule cannot tell "as backtested" from "no edge over the control": PEAD reverts in only 5.5% of
  paths by 60 months, SPMO/GLD in 0%. The rule is for stopping failures, not for choosing between a candidate and its
  control.

## 6. What this cannot capture

- **Unobserved regimes.**
  - PEAD's sample (2021-08 → 2025-06) contains no crash of the 2008 or 2020 kind, so its low drawdown numbers are
    conditional on 2021–25.
  - The 2017–26 sample has one fast crash (2020) and one bear market (2022).
  - A structural break is not modelled: a stale SUE feed, a momentum crash, a gold reversal, rates back at zero,
    or a change in SPMO's index. The 2005–26 rows show how much one extra decade changes the tails.
- **Centred on realised means.**
  - Every as-observed number embeds the historical outperformance. That includes the 2023–25 run for SPMO/GLD, and a
    configuration selected on this window for PEAD (deflated-Sharpe probability 0.85).
  - Section 2e and the operating-characteristic scenarios show the alternatives.
- **Method artefacts.**
  - The regime bootstraps splice blocks at lagging label switches, which gives milder crash sequences.
  - FHS is not credible for PEAD.
  - k < 1 reflects mean reversion in this sample.
  - Monte Carlo error is about ±0.7 pp at 50% and ±0.3 pp at 5% (5,000 paths).
- **Circularity.** Priors, k and drawdown boundaries come from the same history the rule will judge. Applying the
  rule back to history (section 3) is only a consistency check.
- **Accounting simplifications.**
  - Leverage financing is charged on the full (L−1)×NAV.
  - The PEAD cost shock hits the strategy only.
  - Investor taxes are excluded.

## Files

- `research/future_lab/`:
  - `data.py`: joint panels and causal regimes;
  - `engines.py`: the five resamplers and Politis–White;
  - `paths.py`: path metrics;
  - `risk.py`: section 2;
  - `ordering.py`: section 3;
  - `forward.py`: power, the rule, the evaluator and spec hashing;
  - `run.py`: orchestration and charts.
- `tests/test_future_lab.py`.
- `reports/future_lab/`:
  - `REPORT.md`, `results.json`, `manifest.json` (input and code hashes);
  - `path_risk.csv`, `leverage_ruin.csv`, `cost_shocks.csv`, `ordering_summary.csv`, `forward_design.csv`,
    `oc_table.csv`;
  - `monitoring_rule_spec.json`;
  - `fan_charts.png`, `drawdown_distributions.png`.
