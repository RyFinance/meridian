# LSE index-option put/call volume breadth: development null

2026-09-23. **FAIL DEVELOPMENT. Validation stays locked.** The [plan](../../research/index_option_breadth/PLAN.md) was registered before any signal or control return was calculated. [Machine-readable results](dev_results.json) contain the frozen plan hash, source hashes, controls, null distributions and annual diagnostics.

## Information and source audit

This tested a market-wide 7–30-calendar-day put/call **trade-volume** balance across SPY, QQQ and IWM options. Earlier stock-option studies tested individual-stock flow, IV changes and skew; the earlier index-option study tested short-dated put writing. Neither tested this aggregate order-flow measure as a predictor of subsequent equity exposure. The LSE historical archive contains contract-day OPRA OHLCV, not quotes, buyer/seller direction, opening/closing flags or open interest. Its `ts` is the trade date normalized to midnight UTC, not the time at which that day's total volume became known. A completed Monday–Sunday week was therefore used only at the following week's first ETF open.

The source audit found 1,407 common 2014–2019 option dates, no duplicate `(ts, osi)` rows, positive volumes and C/P types. Aggregation produced 292 source weeks; the final week begins 2019-12-30, has only two 2019 sessions and is **never used as a development signal**. Its Sunday `week_end` label falls in 2020, but its archived component rows stop at 2019-12-31. All 235 development decisions had eligible prior-week data and a full, separate 52-week historical median. Historical volume definitions and archive completeness have no as-of vendor vintage, a remaining provenance limitation.

## Frozen rule and development result

For a previous week above its preceding 52-week median log put/call ratio, hold IEF; otherwise hold SPY for the coming week. The development window was 2015-07-06 through 2019-12-31: 235 weekly decisions, 1,131 daily adjusted open-to-next-open marks and 51.37% SPY exposure. Base costs were 3 bp per side of turnover, stress costs 9 bp. An independent daywise return-and-cost calculation matched the reusable null engine exactly.

| Development measure | Option-volume rule | Exposure-matched static mix | Fixed 50/50 | SPY weekly trend | VIX weekly change |
|---|---:|---:|---:|---:|---:|
| Net annualized mean | **−1.70%** | **8.08%** | 7.94% | 2.66% | −0.23% |
| Net Sharpe | **−0.17** | **1.28** | 1.29 | 0.27 | −0.02 |

The preregistered target was **C0-active net Sharpe ≥ +0.85**, stress-cost active mean > 0 and positive mean versus both simple timing controls. Observed C0-active Sharpe was **−1.21**, with **−9.78% annualized** active mean; at stress cost its active mean was **−11.84%**. The rule also trailed the SPY-trend and VIX-change controls by 4.36% and 1.47% annually. The one-sided paired 21-day block-bootstrap p-values for superiority to C0, C1 and C2 were 0.999, 0.836 and 0.610. Active return was negative in every development calendar year. Removing the best contiguous 12 or 24 months left active Sharpe at −1.56 and −1.79.

Five thousand registered ≥52-week circular shifts gave **P(full development pass | null) = 0.76% ± 0.12 percentage points**; **99.16%** matched or exceeded the observed C0-active Sharpe. This is evidence against the frozen directional rule, not evidence for a rescued signal. The reverse-allocation placebo had raw Sharpe 1.50, but was specified as a placebo and is not eligible for promotion or tuning.

## Decision

Preserve the null. Do not reverse the sign, alter expiries, reweight underlyings, change the median or holding period, or unlock 2020+ validation. The concurrent FX-news and macro-surprise work belongs to other researchers and was not reproduced here. No trading, paid data, production change, commit or push occurred.
