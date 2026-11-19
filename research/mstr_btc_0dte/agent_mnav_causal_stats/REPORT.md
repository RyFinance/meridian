# Causal 15:59 M1 statistical check

This companion reruns **only** the frozen M1 rule after the timestamp audit:
the 16:00 ET decision uses the last fully completed BTC minute (the bar
starting 15:59 ET), rather than the non-causal close of the bar starting at
16:00 ET.  All other inputs and mechanics are held fixed: the SEC
observations, share/split handling, 10-day premium momentum plus 50-day proxy
trend rule, next-MSTR-open execution, 3 bp adverse slippage per side, and
$0.005 per actual MSTR share per side.

The run starts after the development window and covers the sealed
2023-01-03 through 2026-08-10 sample (903 MSTR sessions).  It exactly matches
the causal audit's M1 result before reporting inference.

| Strategy | Net return | CAGR | Sharpe | Realized max DD | Round trips | Long exposure |
|---|---:|---:|---:|---:|---:|---:|
| Causal M1 | +532.01% | +66.88% | 1.146 | -46.97% | 36 | 36.10% |
| MSTR buy/hold, same costs | +582.31% | +70.47% | 1.046 | -84.46% | 1 | 100.00% |
| MSTR close > 50-day SMA, same costs | +177.55% | +32.78% | 0.764 | -56.79% | 30 | 51.50% |

M1's daily mean return remains positive versus zero cash under a
Newey--West test: annualized arithmetic mean +70.13%, HAC-60 t=2.293,
two-sided p=0.0218.  That test is **not selection-adjusted**, so it is not a
confirmation of an economic edge.

The appropriate comparative claims remain unproven:

- Its 20-day moving-block-bootstrap Sharpe difference is +0.100 versus
  buy/hold (95% interval -0.713 to +0.957) and +0.383 versus the fixed
  MSTR-50SMA rule (-0.415 to +1.296).
- HAC-60 mean-return differentials are -22.07 percentage points annually
  versus buy/hold (p=0.557) and +21.72 points versus MSTR-50SMA (p=0.411).

Thus the causal record supports a **positive, cost-robust, lower-drawdown
paper timing hypothesis**, not statistically established alpha, relative
Sharpe superiority, or confirmed incremental mNAV value.

Run it from the repository root:

```bash
PYTHONPATH=. .venv/bin/python \
  research/mstr_btc_0dte/agent_mnav_causal_stats/run_causal_stats.py
```

Outputs: `CAUSAL_PERFORMANCE.csv`, `CAUSAL_HAC.csv`, and
`CAUSAL_BLOCK_BOOTSTRAP.csv`.
