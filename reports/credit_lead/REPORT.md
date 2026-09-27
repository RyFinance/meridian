# LSE high-yield / investment-grade credit lead: development null

2026-09-23. **FAIL DEVELOPMENT. Validation stays locked.** The [plan](../../research/credit_lead/PLAN.md) was registered before any strategy/control return was computed. No trading, paid data, production change, commit or push.

## Information and source audit

LSE Terminal MCP exposed `USD_LIQ_HY` and `USD_LIQ_IG` as daily USD liquid corporate-bond **index levels** from 2010. The project's prior price research used LQD/IEF as an ML macro feature, but had not tested high-yield versus investment-grade index information. FX news was already selected in another researcher's frontier map, so this was an independent family. The credit levels have dates but no publication hour, provider source field or historical vintages. They cannot be treated as point-in-time spreads. The rule consequently leaves a full US trading session between the last credit observation and the monthly entry open.

The archived 2010–2020 development extract has 2,829 HY dates and 2,759 IG dates. Fifteen rows per series fall on weekends; only shared credit dates on the ETF trading calendar were eligible. Daily credit-index return correlation with adjusted HYG and LQD was 0.68 and 0.73, respectively: broad correspondence, not exact replication. Raw MCP replies and hashes are in the [data manifest](../../data/lse/credit_lead/manifest.json). ETF fills and marking used the existing adjusted official-session SPY, IEF, HYG and LQD bars; no 2021+ prices entered this run.

## Frozen test and result

At each month's first ETF open, use a credit HY/IG index-ratio change over 20 common observations ending no later than the previous month's second-to-last ETF trading day. Positive means 100% SPY for the month; otherwise 100% IEF. Base turnover cost was 3 bp per side, stressed to 9 bp. Development was January 2012 through December 2020: 108 decisions and 2,264 marked open-to-open days. All 108 decisions had fresh credit data. The observed SPY exposure was 52.96%, used for the static matched control.

| Development measure | Credit rule | Exposure-matched static mix | Fixed 50/50 | SPY momentum control | HYG/LQD control |
|---|---:|---:|---:|---:|---:|
| Net annualized mean | 7.65% | **9.62%** | 9.28% | 6.06% | 7.04% |
| Net Sharpe | 0.73 | **1.26** | 1.29 | 0.50 | 0.67 |
| Maximum drawdown | −20.6% | −16.0% | −14.9% | −20.6% | −23.3% |

The protocol gates the **active** daily return against the exposure-matched control, not the raw portfolio Sharpe. That active return was **−1.97% annualized with Sharpe −0.21**, against the frozen required Sharpe **+0.60**. Stress-cost active mean was **−2.75% annualized**. The credit rule exceeded SPY-momentum and HYG/LQD controls by 1.59% and 0.61% annualized, but paired block-bootstrap p-values were 0.304 and 0.366. The reverse-allocation placebo had 0.80 raw Sharpe; it is a placebo, not a replacement candidate. Removing the best contiguous 12 or 24 months left active Sharpe negative (−0.47 and −0.39).

Five thousand registered 12-month-or-longer circular shifts produced **P(full development pass | null) = 2.22% ± 0.21 percentage points**. Fully **75.8%** of shift worlds equaled or exceeded the observed active Sharpe. The custom null engine matched independent daywise return/cost arithmetic exactly in a run-time assertion. A null with low false-pass frequency does not help a real rule that failed by this margin.

## Decision

Preserve the failed result. Do not reverse, threshold, change the horizon, switch index families or fit weights to rescue it. Do not unlock 2021+ validation. The source's missing as-of vintages and publication hour would be additional obstacles even if the development result had passed. The next experiment, if any, should use a genuinely different event or flow information family with stronger timestamp provenance.
