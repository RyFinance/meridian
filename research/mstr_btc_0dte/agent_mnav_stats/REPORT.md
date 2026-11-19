# Independent statistical audit — frozen gross-BTC-mNAV rules

## Verdict

**The sealed replay is economically promising but does not yet support a
statistically defensible claim of risk-adjusted superiority, timing alpha, or
mNAV-specific alpha.** It is accurate to say that the pre-frozen rules made
positive *modeled net* returns in the sealed window and had much smaller
*realized* drawdowns than a cost-matched MSTR buy-and-hold position. It is not
accurate to call that evidence of confirmed alpha or confirmed Sharpe
outperformance.

This conclusion is additionally conditional on the separate timestamp,
filing-availability, and source-data causality audit. This report deliberately
does not alter or certify those mechanics.

## Scope and reproducibility

Only artifacts listed in
[`../agent_mnav/AUTHORITATIVE_ARTIFACTS.md`](../agent_mnav/AUTHORITATIVE_ARTIFACTS.md)
were read. In particular, no `HOLDOUT_*`, `forward_m1.py`, or other concurrent
files were used. `run_stats_audit.py` recreates the frozen next-open,
long/cash simulator from the sealed panel and signals, then asserts that its
M1/M3 baseline results equal the attributable published result to numerical
precision.

The sealed sample is 903 regular MSTR sessions, **2023-01-03 through
2026-08-10**. The frozen baseline is 3 bp slippage on every entry/exit plus
$0.005 per actual share, including final forced liquidation. Cash earns zero,
just as in the source simulator; no borrow is involved because all strategies
are long/cash only.

The sole added comparator is deliberately fixed before its calculation:
**long MSTR when its close exceeds its own 50-session SMA, otherwise cash**;
trade next open with the identical cost model. It is a simple price-only
benchmark, not a parameter sweep. Fifty sessions was chosen once because it
is the common trend horizon already frozen in M1/M3.

Run:

```bash
cd /Users/rytty/CCP/quant_v7
PYTHONPATH=. .venv/bin/python research/mstr_btc_0dte/agent_mnav_stats/run_stats_audit.py
```

Outputs:

- `PERFORMANCE_REPLICATION.csv`
- `BLOCK_BOOTSTRAP_COMPARISONS.csv`
- `HAC_MEAN_DIFFERENTIALS.csv`
- `HAC_SINGLE_FACTOR_ALPHA.csv`
- `HAC_MEAN_VS_ZERO_CASH.csv`
- `SELECTION_CONTEXT.json`

## Exact baseline-cost replay

| Rule | Net total return | CAGR | Ann. Sharpe | Max drawdown | Round trips | Long exposure |
|---|---:|---:|---:|---:|---:|---:|
| M1: 10d gross-premium momentum + 50d proxy trend | +534.2% | 67.0% | 1.148 | -47.0% | 37 | 36.0% |
| M3: 20d proxy trend + 20d BTC regime | +392.5% | 55.7% | 1.078 | -44.0% | 32 | 31.0% |
| MSTR buy-and-hold, same costs | +582.3% | 70.5% | 1.046 | -84.5% | 1 | 100.0% |
| MSTR close > 50-session SMA, same costs | +177.6% | 32.8% | 0.764 | -56.8% | 30 | 51.5% |

So the observed record has an economically meaningful risk trade-off: M1/M3
gave up some raw return relative to buy-and-hold but cut the realized peak to
trough loss by about 38–41 percentage points. That is a useful descriptive
result, not a confidence interval for future drawdown.

The attributable mNAV run also reports that M1 and M3 remain net positive
under **double** the baseline modeled friction (6 bp each side and $0.01 per
actual share): respectively +519.5% and +382.7% total return. This establishes
that the reported replay is not a few-basis-point artifact of the stated
transaction model; it does not cover market impact, fill quality, or future
liquidity changes.

## Serial-dependence-aware comparison with buy-and-hold

I jointly resampled all return series using a circular moving-block bootstrap:
20,000 fixed-seed replications with 5-, 20-, and 60-session blocks. The common
date blocks preserve each pair's same-day association and serial structure
inside the block. The 20- and 60-session results below are representative; all
5-session intervals also span zero. Percentile intervals quantify sample
uncertainty and are **not** multiple-testing-adjusted p-values.

| Comparison | Observed Δ Sharpe | 95% CI, 20-day blocks | 95% CI, 60-day blocks |
|---|---:|---:|---:|
| M1 minus MSTR buy-and-hold | +0.102 | [-0.709, +0.955] | [-0.771, +1.083] |
| M3 minus MSTR buy-and-hold | +0.032 | [-0.793, +0.813] | [-0.733, +0.886] |
| M1 minus simple MSTR-50SMA | +0.385 | [-0.413, +1.295] | [-0.458, +1.259] |
| M3 minus simple MSTR-50SMA | +0.314 | [-0.316, +1.005] | [-0.231, +0.925] |

Every relevant interval includes zero. The full-return comparison is also not
favorable to the timing rules: M1's annualized arithmetic daily-mean return is
22.0 percentage points lower than buy-and-hold (Newey–West p=0.556 with a
60-session bandwidth); M3's is 32.6 points lower (p=0.353). Thus the realized
Sharpe advantages are point estimates with very wide uncertainty, not an
established improvement.

A one-factor diagnostic tells the same story. Regressing daily strategy return
on daily MSTR buy-and-hold return gives M1 beta 0.480 and annualized intercept
+25.9%, but a 60-session Newey–West alpha p=0.274; M3 beta is 0.393,
annualized intercept +23.4%, p=0.166. These positive point alphas are not
statistically distinguishable from zero.

## Is there demonstrated mNAV value beyond simple MSTR trend?

Not yet. Relative to the fixed MSTR-50SMA comparator, M1/M3 have positive
point estimates for full-return and Sharpe differences, but the block-bootstrap
intervals above both contain zero.

In a beta-adjusted diagnostic against that simple trend portfolio, M1's
annualized intercept is +36.1% (HAC-20 p=0.074; HAC-60 p=0.080) and M3's is
+25.2% (p=0.092 at 20 lags; p=0.038 at 60 lags). That isolated M3 60-lag value
is not robust to reasonable bandwidth choice, is unadjusted for multiple
comparisons, and comes after a 27-variant development search. It therefore
cannot support an mNAV-specific alpha claim.

For context only, the strategies' mean return versus the source simulator's
zero-cash return assumption has HAC-60 p=0.021 for M1 and p=0.050 for M3.
Those are not selection-adjusted and say nothing about performance versus
MSTR, a simple trend rule, or a risk-adjusted passive portfolio.

## Selection and inference caveats

- M1 was the **highest-Sharpe choice in a 27-variant development grid**;
  M3 ranked seventh. The grid contains 22 positive-Sharpe and 16
  positive-total-return variants. Those variants are correlated, so treating
  them as 27 independent tests would be wrong, but reporting unadjusted
  inference as if no search occurred would also be wrong.
- The sealed window was not used to select M1/M3 according to the frozen
  protocol. That separation is valuable, but a single 3.6-year MSTR regime is
  still too small and path-dependent to establish a general risk-adjusted edge.
- Moving-block bootstrap supports uncertainty quantification for returns and
  Sharpe. It does **not** provide a reliable frequentist confidence interval
  for maximum drawdown, which is a path extreme; drawdown comparisons above
  are descriptive.
- All figures depend on the frozen daily execution model, available daily
  pricing, and zero return on cash. They do not establish capacity, impact,
  real-world auction fill quality, tax treatment, or a live executable edge.

## Narrow statement that is justified

> Conditional on the separate data-timing/causality audit, the pre-frozen M1
> and M3 long/cash rules produced positive net modeled returns on the sealed
> 2023-01-03 to 2026-08-10 replay after 3 bp per-side slippage and $0.005 per
> actual share, and they had materially smaller **realized** maximum drawdowns
> than cost-matched MSTR buy-and-hold. This is a promising, cost-robust
> risk-control/timing hypothesis. It is **not** statistically established
> alpha, statistically established Sharpe outperformance, or demonstrated
> incremental value from mNAV beyond a simple MSTR trend rule.

Accordingly, this track can be retained for a genuinely independent future
sample or paper-trading observation, but it should not be promoted as the
requested confirmed profitable edge.
