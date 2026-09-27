# Null-world lab: how often the project's machinery finds edges that are not there

2026-09-23. Code: `research/null_lab/`. Tests: `tests/test_null_lab.py` (21 pass). Outputs: this folder.
No trade was placed. No locked validation window was opened. No new data was pulled. No shared module
or earlier result was modified. The real macro-surprise signal was used only as raw material for
shifted, synthetic and permuted nulls, and the engine refuses it unshifted in its locked window.

*Written by the null-lab agent. Saved to disk by the main (director) session because the harness blocks subagents
from writing report files.*

## Headline numbers

Monte-Carlo size: 4,000 null worlds per config, 27 configs. Each world is a family of 3 independent
null candidates plus their composite: 432,000 candidate backtests, each at base and stress cost in
both windows. ± is one Monte-Carlo standard error. 0 of 4,000 means below 0.075% (95%, rule of three).

1. **Market-neutral engines, realised price path, one candidate, dev gate** (net Sharpe ≥ 0.5 and
   stress mean > 0):
   - country ETF long-short, SPY−IEF R2-type timing, stock reversal / AR(1) / permutation: **0–0.1%**;
   - stock book on shifted 12-1 momentum: **5.4 ± 0.4%**;
   - SPY−IEF shifted trend: **3.7 ± 0.3%**.

   Cost drag keeps most of these null Sharpes near −0.3. The two exceptions are persistent signals
   that pick up a structural drift: surviving winners in the stock universe, and stocks beating bonds.
2. **Full pipeline, one candidate** (dev gate, then validation with Sharpe ≥ 0.75, stress mean > 0
   and bootstrap p < 0.05/4): **0 of 4,000 in 20 of the 23 market-neutral configs**. The highest is
   0.83 ± 0.14%, for shifted momentum on bootstrapped paths. For a family of 4 the highest is 3.6%
   (same config); everywhere else it is 1.7% or less.
3. **Families, dev gate only.** For persistent stock signals, P(at least one of 4 passes) is **20%**
   on the real path and **57%** on bootstrapped paths. For the country engine it is 0.4% or less.
4. **Raw long-only timing** (SPY vs cash, the absolute Sharpe gate the project applied to long
   books):
   - **87–89%** of null signals pass dev and **8–10%** pass the whole pipeline. The gate is
     measuring SPY's 2015–26 Sharpe of 0.70–0.80, not the signal.
   - Gated against an exposure-matched SPY holding instead: 1.6–5.9% pass dev and 0.03% or less pass
     both.
5. **The 0.5 dev gate is not a 5% test.** Under a zero-mean null (a gross or cost-free signal) over
   5.7 years it false-passes **10–19%**, for κ between 0.95 and 1.38 (κ = null Sharpe sd × √years).
   It looked safe here only because costs pull most null means below zero.
6. **The record at development.**
   - 46 gated candidates. 9 recorded dev passes against **7.8 expected** if every candidate were
     null (p = 0.35).
   - 6 of the 9 passes are long-biased books. The null expects 6.7 such passes from beta and
     benchmark alone.
   - Market-neutral books: 3 passes against 1.0 expected (p = 0.08 at κ = 1; 0.37 at κ = 1.3). The
     three are R2 and R3, both inside the published paper's own sample, and the multi-asset book,
     which holds standard premia.
7. **The record at validation.**
   - **0 of 9** dev passes cleared validation. Had their dev Sharpes been true, 4.0 passes were
     expected (P(0 passes) = 0.002). The dev numbers were inflated.
   - Validation evidence for an edge, measured against each candidate's own null: Stouffer
     **p = 0.22**, Fisher 0.21.
   - The best single result is p = 0.078 (N4 against its random-stock control), which becomes 0.52
     after Šidák correction over 9 tests.
8. **Shrinkage.**
   - Across 30 dev→later pairs the slope of later Sharpe on dev Sharpe is 0.44 [0.16, 0.72]. An
     **all-null project gives 0.41 (90% range 0.12–0.70)** once candidates differ in cost and
     structure, so this slope is not evidence of an edge.
   - Gross Sharpes in the 11 core pairs give a slope of 0.79, with a bootstrap CI of [−0.02, 1.05].
     R2 and R3 carry it.
9. **Answer: there is no statistical evidence that any registered candidate had a real net edge.**
   - The one persistent *gross* signal is month-end rebalancing. R2 ran 0.90 → 0.76 gross and R3
     1.03 → 0.67.
   - Net of costs, its validation p is 0.108 / 0.126, which is 0.64 / 0.70 after multiplicity. Its
     own report shows it vanishes with a one-day lag.
10. **Researcher degrees of freedom.** Keeping the best of k construction variants in development:
    - raises the development Sharpe by **+0.15 / +0.22 / +0.28** (k = 4 / 10 / 25; stock, shifted
      momentum), by +0.28 / +0.42 / +0.51 (stock, AR(1) signal) and by +0.24 / +0.34 / +0.41
      (country);
    - raises P(dev pass) from 10% to 21 / 28 / 34% (stock, shifted momentum) and from 1.3% to
      3.8 / 7.5 / 11% (stock, AR(1));
    - leaves the chosen variant's validation Sharpe unchanged (−0.17 to −0.18). Only 0.1% or less
      pass both stages.

    An untouched validation window absorbs the selection. A development-only result does not.
11. **Recommended gates for future registrations.** Past verdicts are unchanged.
    - **Per candidate:** net Sharpe ≥ **1.8/√T** (T in years). That is 0.75 at 5.7 years, 0.63 at
      8 and 0.51 at 12.
    - **Per member of a 4-candidate family:** ≥ **2.4/√T**, which is 1.02 at 5.7 years.
    - These assume a zero-mean null and κ = 1.08, the lab's 90th percentile. The worst case,
      κ = 1.38, needs 2.3/√T and 3.1/√T.
    - Long-biased books are gated on active return against an exposure-matched benchmark or control,
      never on absolute Sharpe.

## 1. What was built

| Module | Content |
|---|---|
| `generators.py` | Signal nulls, each over T periods: **(a)** circular shift by an offset in [m, T−m]; **(b)** per-asset AR(1), with a fixed effect fitted to the lag-1 and lag-L rank autocorrelations, or a binary latent AR(1) for timing, under the real NaN mask; **(c)** within-date permutation; also an MA(q) overlapping-window null. **(d)** Stationary block bootstrap of whole dates, mean block 21. |
| `engines.py` | Batched replicas of three registered engines. They run W worlds at once and loop over days or weeks. Each one's daily or weekly returns equal the project function's to ≤ 1e-15; tests enforce ≤ 1e-10. |
| `gates.py` | Dev and validation gates. `BootstrapP` gives the same p-values as the project's `block_bootstrap_p`: same algorithm and seed, computed from block sums, test-enforced. |
| `api.py` | `run_null(signal_builder, engine, gate, n_worlds, seed, path_builder=None, family_size=4, horizons=())`, plus `builders.{shift, ar1, ar1_series, permute, bootstrap_paths}`. |
| `run_lab.py`, `analyze.py`, `dof.py`, `record.py` | The grid, the summaries, the degrees-of-freedom simulation, and the record with its formal tests. |

| Engine | Project code replicated | Universe / windows / costs |
|---|---|---|
| Country ETF L/S | `macro_surprise.evaluate.target_books` (M1) + `simulate` + `COSTS` + `cash_rates` | 14 ETFs, month-end signals. Dev 2015-05 → 2020-12, val 2021-01 → 2026-09-18. Base 10 bp + 1% borrow; stress 30 bp + 5%, proceeds earn nothing. |
| Stock quintile L/S | `options_signals.evaluate.target_weights` + `backtest` + `COSTS` | The 100 OPRA names, weekly. Dev 2014-07 → 2019-12, val 2020-01 → 2026-09. |
| SPY vs cash | `return_search.run.execute` (etf, 5/15 bp) + `cash_rates` | Monthly decisions, same windows as the country engine. Also an "active" variant, net of an exposure-matched SPY holding. |
| SPY−IEF | `rebalancing.evaluate.backtest` (2/6 bp per side per leg) | Daily, R2/R3 windows: dev 2003-02 → 2014-12, val 2015 → 2026-09. |

Bootstrap p-values use each engine's registered settings: macro 21-day blocks with seed 20260923;
options 8-week blocks with seed 20260918; rebalancing 21-day blocks with seed 20260918. Families use
k = 4, so α = 0.0125.

### Using it for a new registration

```python
from research.null_lab.api import run_null, builders
from research.null_lab.engines import CountryEngine          # or StockEngine(), TimingEngine("spy_ief")
from research.null_lab.gates import Gate
eng = CountryEngine()
sig = builders.shift(my_signal_panel, min_offset=LOOKBACK + HOLD + margin)   # (a); also builders.ar1 / permute
paths = builders.bootstrap_paths(len(eng.cal), 21, split=eng.windows["dev"].end_day)   # (d), optional
res = run_null(sig, eng, Gate(k=n_candidates), n_worlds=2000, seed=1, path_builder=paths)
res["candidate"]["p_pass_dev"], res["candidate"]["p_pass_both"], res["family"]["p_any_pass_dev"]
```

Report "P(pass dev | null) = x ± se over N worlds" next to the result. A new engine only needs
`.run(signals, paths) -> {(window, cost): returns}` and `.periods`. Add an exactness test against
the registered code.

## 2. Null calibration (`calibration.csv`)

Dev window ≈ 5.5–5.7 years, except SPY−IEF at 11.9. Probabilities are per candidate except in the
family columns.

| Config | Engine | Signal null | Path | Dev SR mean ± sd | κ | P(dev) % | P(val gate) % | P(both) % | Family: P(any dev) % | Family: P(any both) % |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| C1 | Country ETF L/S | (a) shift ≥12m | real | −0.35 ± 0.38 | 0.90 | 0 | 0.80 | 0 | 0 | 0 |
| C2 | Country ETF L/S | (a) shift ≥12m | (d) boot | −0.34 ± 0.40 | 0.94 | 0.15 ± 0.06 | 0.03 | 0 | 0.40 | 0 |
| C3 | Country ETF L/S | (b) AR(1) φ=.60 | real | −0.33 ± 0.37 | 0.89 | 0 | 0.03 | 0 | 0.03 | 0 |
| C4 | Country ETF L/S | (b) AR(1) | (d) boot | −0.31 ± 0.41 | 0.97 | 0.15 ± 0.06 | 0 | 0 | 0.43 | 0 |
| C5 | Country ETF L/S | (c) permute | real | −0.45 ± 0.39 | 0.93 | 0 | 0 | 0 | 0 | 0 |
| C6 | Country ETF L/S | (c) permute | (d) boot | −0.43 ± 0.39 | 0.92 | 0 | 0 | 0 | 0 | 0 |
| S1 | Stock quintile L/S | (a) shift 12-1 mom ≥64w | real | −0.04 ± 0.43 | 1.02 | 5.40 ± 0.36 | 0 | 0 | 19.8 | 0.03 |
| S2 | Stock quintile L/S | (a) shift 12-1 mom ≥64w | (d) boot | +0.16 ± 0.54 | 1.26 | 24.4 ± 0.68 | 1.93 | 0.83 ± 0.14 | 57.5 | 3.55 |
| S3 | Stock quintile L/S | (a) shift 1m rev ≥52w | real | −0.46 ± 0.40 | 0.93 | 0 | 0 | 0 | 0 | 0 |
| S4 | Stock quintile L/S | (a) shift 1m rev ≥52w | (d) boot | −0.52 ± 0.45 | 1.05 | 0 | 0.10 | 0 | 0.03 | 0 |
| S5 | Stock quintile L/S | (b) AR(1) φ=.97 | real | −0.29 ± 0.41 | 0.97 | 0.10 ± 0.05 | 0.10 | 0 | 0.60 | 0 |
| S6 | Stock quintile L/S | (b) AR(1) φ=.97 | (d) boot | −0.29 ± 0.46 | 1.07 | 0.25 ± 0.08 | 0.30 | 0 | 1.23 | 0 |
| S7 | Stock quintile L/S | (c) permute mom | real | −1.26 ± 0.42 | 1.00 | 0 | 0 | 0 | 0 | 0 |
| I1 | SPY−IEF | (a) shift R2 ≥252d | real | −0.33 ± 0.22 | 0.77 | 0 | 0 | 0 | 0.05 | 0 |
| I2 | SPY−IEF | (a) shift R2 ≥252d | (d) boot | −0.33 ± 0.26 | 0.91 | 0.07 ± 0.04 | 0 | 0 | 0.15 | 0 |
| I3 | SPY−IEF | (b) AR(1) φ=.59 | real | −0.40 ± 0.24 | 0.82 | 0 | 0 | 0 | 0 | 0 |
| I4 | SPY−IEF | (b) AR(1) φ=.59 | (d) boot | −0.39 ± 0.27 | 0.94 | 0 | 0 | 0 | 0.15 | 0 |
| I5 | SPY−IEF | (a) shift trend ≥315d | real | +0.08 ± 0.22 | 0.77 | 3.70 ± 0.30 | 0.62 | 0 | 11.1 | 0 |
| I6 | SPY−IEF | (a) shift trend ≥315d | (d) boot | +0.10 ± 0.24 | 0.83 | 5.35 ± 0.36 | 6.50 | 0.30 ± 0.09 | 15.1 | 1.65 |
| T1 | SPY vs cash (raw) | (a) shift TSMOM ≥315d | real | +0.65 ± 0.13 | 0.31 | 89.4 ± 0.5 | 10.0 | 9.7 ± 0.5 | 99.7 | 27.8 |
| T2 | SPY vs cash (raw) | (a) shift TSMOM | (d) boot | +0.56 ± 0.40 | 0.95 | 55.1 ± 0.8 | 34.8 | 19.2 ± 0.6 | 68.1 | 29.9 |
| T3 | SPY vs cash (raw) | (b) AR(1) binary | real | +0.65 ± 0.16 | 0.37 | 86.6 ± 0.5 | 9.5 | 8.1 ± 0.4 | 99.7 | 22.9 |
| T4 | SPY vs cash (raw) | (b) AR(1) binary | (d) boot | +0.55 ± 0.40 | 0.95 | 53.3 ± 0.8 | 33.6 | 18.1 ± 0.6 | 64.8 | 28.0 |
| A1 | SPY vs cash − matched SPY | (a) shift TSMOM | real | −0.09 ± 0.33 | 0.80 | 1.60 ± 0.20 | 0 | 0 | 6.7 | 0 |
| A2 | SPY vs cash − matched SPY | (a) shift TSMOM | (d) boot | −0.05 ± 0.36 | 0.85 | 5.90 ± 0.37 | 0.38 | 0.03 ± 0.03 | 16.9 | 0.05 |
| A3 | SPY vs cash − matched SPY | (b) AR(1) binary | real | −0.19 ± 0.33 | 0.78 | 1.85 ± 0.21 | 0.10 | 0 | 7.1 | 0 |
| A4 | SPY vs cash − matched SPY | (b) AR(1) binary | (d) boot | −0.09 ± 0.38 | 0.90 | 4.88 ± 0.34 | 0.30 | 0 | 13.8 | 0.05 |

How to read the table:
- **κ ≈ 0.8–1.0 on the real path and up to 1.26–1.38 on bootstrapped stock paths.** The iid rule
  SE ≈ 1/√T holds on average, but is 25–40% too optimistic for persistent stock signals.
- **The dev/val null correlation is about 0**, except S1 at 0.21 and C1 at 0.18. Under a null,
  validation is an independent draw, so P(both) ≈ P(dev) × P(val gate).
- **Stress gate.** With 5% borrow and no rebate, stress costs about 1.2 Sharpe on the country
  engine. There the stress condition, not the 0.5 threshold, is what binds.
- **Survivorship tilt.** Shifted 12-1 momentum is persistently long the universe's long-run winners,
  such as NVDA and TSLA. On the same engine that lifts the null mean from −0.29 (AR(1), S5) to
  −0.04 (S1), and to +0.16 on bootstrapped paths (S2). In this survivor-biased 100-name universe,
  any signal correlated with survival earns that tilt for free.

## 3. Best of N null candidates (`best_of_n.csv`)

Dev Sharpe of the best of N independent null candidates on the realised path. "Mix" draws each
candidate from a random market-neutral engine (country, stock, SPY−IEF, matched SPY timing),
roughly the project's own mix.

| N | Mix: mean | Mix: 95th | Stock shifted mom: mean / 95th | Stock AR(1): mean / 95th | Country AR(1): mean / 95th |
|---:|---:|---:|---:|---:|---:|
| 1 | −0.34 | 0.36 | −0.04 / 0.58 | −0.29 / 0.40 | −0.32 / 0.29 |
| 4 | 0.12 | 0.57 | 0.39 / 0.80 | 0.13 / 0.63 | 0.06 / 0.49 |
| 20 | 0.44 | 0.81 | 0.66 / 1.01 | 0.48 / 0.86 | 0.36 / 0.71 |
| 111 | **0.69** | **1.01** | 0.89 / 1.07 | 0.77 / 1.14 | 0.59 / 0.82 |

The project's best market-neutral dev Sharpe, R3's 0.82, is what the best of about 111 null trials
typically looks like. In z terms it is 2.84, Šidák p = 0.10 over the 46 gated candidates.

The country shift null has only 114 admissible offsets, so its best-of-111 is degenerate; the table
uses the AR(1) null there. The number of distinct shift nulls per config: country 114, stock momentum
511, stock reversal 535, daily timing 5,084–5,462.

## 4. Window length and recommended thresholds (`horizon_thresholds.csv`, `recommended_gates.csv`)

The null Sharpe sd scales as κ/√T. Across all market-neutral configs and horizons of 1–12 years,
κ has median 0.95, 90th percentile 1.08 and maximum 1.38. The gates below make the false-pass
probability 5% per candidate (Bonferroni 5%/4 for a family member) under a **zero-mean** null. That
gives no credit for cost drag, because that credit depends on the candidate.

| Window T (years) | 3 | 4 | 5 | 5.7 | 8 | 10 | 12 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Per candidate, κ = 1.08: 1.78/√T | 1.03 | 0.89 | 0.80 | **0.75** | 0.63 | 0.56 | 0.51 |
| Family of 4, κ = 1.08: 2.43/√T | 1.40 | 1.21 | 1.09 | **1.02** | 0.86 | 0.77 | 0.70 |
| Per candidate, κ = 1.38 (worst) | 1.31 | 1.13 | 1.01 | 0.95 | 0.80 | 0.72 | 0.66 |
| False-pass rate of today's 0.5 gate, κ = 0.95–1.38 | 18–27% | 15–23% | 12–21% | 10–19% | 7–15% | 5–13% | 3–11% |

Recommendations, for future registrations only:
1. Use SR_dev ≥ 1.8/√T per candidate, or 2.4/√T when k ≥ 4 candidates are registered together.
   For 5–6-year windows that means **0.75–0.8 and about 1.0**, not 0.5.
2. Keep the current validation gate (0.75 plus p < 0.05/k). It already holds the pipeline at or below
   0.8% per candidate in every market-neutral config.
3. Gate every long-biased book on its **active return against an exposure-matched benchmark or
   control**. Absolute Sharpe passed 87–89% of null SPY-timing signals.
4. Report run_null's P(pass | null) with its Monte-Carlo SE beside every result.
5. For shift nulls, set the minimum offset to at least **lookback + holding + margin**, as well as
   12 months (see §7).

## 5. The record against an all-null world (`record_candidates.csv`, `record_tests.json`)

46 candidates faced a development gate. Every number is copied from its results file, and
`record.verify()` re-reads the JSONs: 0 mismatches. Null centres:
- **Market-neutral books:** 0.
- **Long-biased books:** the registered control or benchmark (ETF hybrids B; insider random-stock
  control; streak C2), or the beta-implied premium (crypto against BTC; I4 = √(active share) × SPY
  Sharpe).

### The nine dev passes, verified from the files

| Candidate | Dev → validation net Sharpe | Validation null centre | Validation one-sided p for edge |
|---|---|---:|---:|
| I4 announcement day | 0.55 → −0.09 | 0.20 | 0.59 (bootstrap) |
| R2 threshold rebalancing | 0.74 → 0.63 | 0 | 0.108 (bootstrap) |
| R3 combined rebalancing | 0.82 → 0.45 | 0 | 0.126 (bootstrap) |
| E1 vol-managed momentum | 0.66 → 0.38 | 0.55 (B) | 0.961 (paired vs B) |
| E2 dual momentum | 0.57 → 0.44 | 0.55 (B) | 0.821 (paired vs B) |
| N3 opportunistic insider | 0.77 → 0.49 | 0.42 (control) | 0.161 (paired vs control) |
| N4 insider composite | 0.51 → 0.51 | 0.45 (control) | 0.078 (paired vs control) |
| Multi-asset book | 0.57 → −0.02 | 0 | 0.53 |
| Crypto trend, long-only | **1.24 → 0.40** | 0.18 (beta) | 0.32 (normal approximation) |

The ledger's "crypto trend 1.11 → 0.40" mixes two candidates. `crypto_tsmom_multi` went 1.11 → 0.17.
The registered hold-out candidate, `crypto_trend_long_only`, went 1.24 → 0.40, and its dev Sharpe
equals BTC buy-and-hold's 1.24.

### Formal tests (κ = 1; κ = 1.3 in brackets)

**Development-pass count.** The null distribution of each net dev Sharpe is N(centre − cost drag,
κ²/T).
- Expected passes: **7.8** [9.1]. Recorded: 9, Poisson-binomial p = 0.35 [0.59].
- Dev Sharpe ≥ 0.5 counted regardless of recorded gate: 12, p = 0.03 [0.15].
- Split by book type:
  - long-biased: 6 passes vs 6.7 expected;
  - market-neutral: 3 vs 1.0, p = 0.08 [0.37].

**Largest development z.** R3: net z 2.84, Šidák p over 46 = 0.10 [0.49]. Gross z 3.55, p = 0.009
[0.13]. Across all 46, gross z-scores combine to Stouffer p = 0.005 [0.024]. Several signals are
informative *before costs*, as the literature says: R1–R3, COT C1 (gross 0.94), I2, L1/L2 and put
writing. That is evidence of known gross effects, measured partly inside their papers' samples. It
is not evidence of tradable net edge.

**Validation.**
- **0 of 9** passes, with 4.0 expected if the dev Sharpes were true (P(0) = 0.002).
- Edge p-values: Stouffer **0.22**, Fisher 0.21.
- Minimum p = 0.078 (N4), Šidák over 9 = 0.52.
- Mean edge fell from +0.34 at dev to +0.09 at validation.

**Shrinkage**, measured as the slope of (later − centre) on (dev − centre), weights T_val.
- Core 11 pairs, net: 0.73 (model CI [0.04, 1.41]; bootstrap [0.00, 1.08]).
- Core 11 pairs, gross: 0.79 (bootstrap [−0.02, 1.05]). R2 and R3 drive it.
- Extended 30 pairs (adds liquidity pressure, share class, ETF convergence, FX session, multi-asset
  sleeves and PEAD): 0.44 [0.16, 0.72].
- Null benchmark from 30 null candidates drawn across the lab's heterogeneous market-neutral
  configs: median slope **0.41**, 5–95% [0.12, 0.70]. Cost drag persists across windows, so a net
  slope of about 0.4 is what an all-null project shows.

**Spread of true edges.** Var(dev − null mean) = 0.220 against a mean sampling variance of 0.158
at κ = 1:
- τ ≈ 0.25, so a 5.7-year dev Sharpe is 26% signal and 74% noise;
- at κ = 1.3, τ² < 0, so the spread is fully explained by noise.

**Verdict.** The dev-pass count, the validation results and the shrinkage are all consistent with
an all-null world once three things are accounted for: beta in long books, cost drag, and
multiplicity. Nothing in the record is statistical evidence that any registered candidate had a real
net edge. The closest is month-end rebalancing (R2/R3). Its gross effect persisted, but net
validation p is 0.11–0.13 before multiplicity, it depends on 2008 and 2020, and it fails with a
one-day lag.

## 6. Researcher degrees of freedom (`dof.json`)

Each world draws one null signal and builds 36 construction variants:
- **stock:** quantile {3, 5, 10} × smoothing {1, 4, 13} weeks × {equal, rank} weights × rebalance
  every {1, 4} weeks;
- **country:** smoothing {1, 2, 3} months × legs {n/4, n/3, n/2} × {inverse-vol, equal} × rebalance
  every {1, 2} months.

The researcher keeps the best dev Sharpe of k randomly chosen variants. 1,000 worlds per setting;
the average pairwise correlation of variant Sharpes is 0.88 (stock, shift), 0.64 (stock, AR(1)) and
0.63 (country).

| Setting | k | Best dev SR (mean / 95th) | Inflation vs k=1 | P(best passes dev) | Validation SR of chosen | P(pass both), α=.05/4 |
|---|---:|---|---:|---:|---:|---:|
| Stock, shifted momentum | 1 | 0.02 / 0.64 | — | 10.2 ± 1.0% | −0.17 | 0 |
| | 4 | 0.17 / 0.76 | +0.15 | 20.6 ± 1.3% | −0.18 | 0 |
| | 10 | 0.24 / 0.82 | +0.22 | 28.0 ± 1.4% | −0.17 | 0.1% |
| | 25 | 0.30 / 0.85 | +0.28 | 33.5 ± 1.5% | −0.17 | 0 |
| Stock, AR(1) φ=.8 + fixed effect | 1 / 4 / 10 / 25 | −0.28 / 0.00 / 0.14 / 0.23 (mean) | +0.28 / +0.42 / +0.51 (k = 4 / 10 / 25) | 1.3 / 3.8 / 7.5 / 11.1% | −0.22 to −0.18 | 0 |
| Country, shifted macro signal | 1 / 4 / 10 / 25 | −0.26 / −0.02 / 0.08 / 0.15 (mean) | +0.24 / +0.34 / +0.41 (k = 4 / 10 / 25) | 0.4 / 1.4 / 2.6 / 4.1% | −0.18 to −0.17 | 0 |

Choosing among 4–25 plausible constructions adds 0.15–0.5 of dev Sharpe and multiplies the
dev-pass rate by 3–10. It adds nothing in validation. Any dev-only number, including every
"development status: none" result in the ledger such as SPMO/GLD, should be discounted by at least
this much.

## 7. Methodology notes and limits

- **Shift leakage (found and fixed).** A circular shift is also a *lead*. With the specified
  12-month minimum, a 12-1 momentum signal led by 4–52 weeks contains the holding week's return,
  and those offsets scored Sharpes of +3 to +4.6. The lab therefore uses a minimum offset of at
  least lookback + hold + margin: 64 weeks for 12-1 momentum and 315 days for 252-day trend. Within
  the admissible range there is no consistent offset pattern.
- **Bootstrap design.** Whole dates are resampled within the dev region and within the validation
  region separately. Each window keeps its own drift and volatility regime; path order and the
  calendar link to the signal are destroyed. Cash rates and elapsed days stay on the real calendar.
- **Record tests are approximations.**
  - Null centres for long books use reported controls or betas.
  - Sharpe sampling noise is N(0, κ²/T) with κ from the lab.
  - Candidates within a family are correlated, and several dev windows overlap the samples of the
    papers they test (R1–R3, OSAP-derived work).
  - Validation p-values are heterogeneous: bootstrap, paired-vs-control, or normal approximation.

  All of these push toward finding *more* evidence of edge, not less, and none was found.
- **Scope.** Three engine types stand in for about 20 project engines. Intraday, options-writing,
  event and futures engines were not replicated. Their κ may differ, especially for fat-tailed
  short-volatility books (see `reports/forward_power`).
- **The universe.** The stock universe is the 100-name OPRA list, current and survivor-biased. The
  momentum-lab point-in-time panel was not used.
- **Survivorship in the country universe.** Russia is excluded from the country universe, as in the
  registered plan.
- **Macro validation window.** Null worlds used real prices through 2026-09-18. No unshifted
  macro-surprise signal was evaluated there; `CountryEngine.run` raises if one is passed.

## Files

- Code: `research/null_lab/{__init__, generators, engines, gates, api, run_lab, analyze, record, dof}.py`.
- Tests: `tests/test_null_lab.py`, 21 tests. They cover exactness against the macro-surprise,
  options, rebalancing and return-search engines; bootstrap-p identity; shift separation; the
  lock guard; and record verification.
- Results in `reports/null_lab/`:
  - `calibration.csv`, `best_of_n.csv`, `horizon_thresholds.csv`, `recommended_gates.csv`;
  - `record_candidates.csv`, `record_tests.json`, `dof.json`, `summary.json`;
  - `worlds/<config>.{json,npz}`: per-world, per-candidate Sharpes, stress means, p-values and pass
    flags;
  - `run_lab.log`, `dof.log`.
- Reproduce, about 14 + 6 minutes on 2 workers:
  `PYTHONPATH=. .venv/bin/python -m research.null_lab.run_lab --worlds 4000 --workers 2`, then
  `PYTHONPATH=. .venv/bin/python -m research.null_lab.dof`, then
  `PYTHONPATH=. .venv/bin/python -m research.null_lab.analyze`.
