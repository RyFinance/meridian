# Gold recency and exposure audit

Decision: retain as a research benchmark and optional frozen paper observation; not a validated trading edge. Do not promote on full-period performance. No orders placed.

The fixed 50% SPMO / 50% GLD result reproduces independently, but is materially stronger in 2024–2026. Asset selection occurred after inspecting this history; pre-run registration does not remove that selection hindsight.

| Fresh-start/final-liquidation window | Net CAGR | Excess Sharpe | Max drawdown |
|---|---:|---:|---:|
| full | 17.98% | 1.06 | -18.74% |
| pre_2024 | 12.13% | 0.82 | -18.74% |
| pre_2025 | 14.96% | 0.98 | -18.74% |
| pre_2026 | 17.94% | 1.14 | -18.74% |
| 2020_2023 | 10.91% | 0.64 | -18.74% |
| 2022_2023 | 4.93% | 0.17 | -17.55% |
| recent | 34.69% | 1.55 | -13.63% |

All windows use daily marked NAV, fixed 50/50 targets, monthly first-session close decisions and next-session open fills, 5 bps per side including initial and final trading. Fund expenses are already in fund prices. These figures exclude investor taxes and assume fractional adjusted units. Earlier stress and $1-order-fee checks remain in the original report. Truncations and rolling windows are diagnostics on reused data, not untouched holdouts.

Gold close weight: average 49.93%, minimum 45.47%, maximum 56.58%. A 50% rebalance target is not a continuous 50% cap.

On an initial $100,000 over the full sample, gold contributed $169,575.68 and SPMO $226,910.79 of asset P&L. Gold represents 42.77% of gross asset dollar P&L. Deduct $657.00 trading costs and add $5.26 cash interest to reconcile net wealth. Dollar contributions reflect compounding and are not estimates of independent alpha.

Before 2024, the matched SPY/GLD control returned 11.28% at 0.80 Sharpe, versus 12.13% / 0.82 for SPMO/GLD. That small historical distinction does not establish a unique edge.

Earlier live-fund stress proxy: SPMO did not exist before 2015, so SPY/GLD is used only as a control. In 2005–2016, that control returned 8.54% annually, Sharpe 0.57, max drawdown −33.04%. In 2012–2015 it returned 2.05% annually, Sharpe 0.24; SPY alone returned 14.71% at 1.14 Sharpe. Gold can detract for years.

Independent issuer check: 2440 GLD daily closes from 2017-01-03 through 2026-09-17 match the input cache within 0.000572 bps. Issuer-close returns: 2024 26.66%; 2025 63.68%; 2026 through September 17 0.52%. The large recent gold gain is concentrated in 2025 in this frozen sample. Source: https://api.spdrgoldshares.com/api/v1/historical-archive?exchange=NYSE&lang=en&product=gld

Independent ledger maximum original NAV difference: 6.22e-15. Every window's asset P&L, interest, and fees reconcile to net wealth within $0.000001. Engine and causal-rule suite: 10 tests passed.

Rolling windows are monthly-ending fresh starts with initial/final costs. All results are saved in rolling_windows.csv. Summary:
{
  "36": {
    "min_cagr": 0.026704672229913573,
    "median_cagr": 0.14443437984970076,
    "min_sharpe": 0.12071687096000984,
    "median_sharpe": 0.9098288795072444
  },
  "60": {
    "min_cagr": 0.08495312298079938,
    "median_cagr": 0.14770665161992969,
    "min_sharpe": 0.544679575291016,
    "median_sharpe": 0.8961397664727689
  }
}

Research screening rule from this audit: always show pre-2024, 2024-on, matched simple controls, rolling-window distribution, asset exposure and contribution before advancing a candidate. Keep recent performance visible, but never let it be the sole reason for selection. All already-seen periods remain contaminated for model selection; real confirmation requires genuinely future observations. No weight search was performed in this audit.

Additional audit: at 15 bps per side, pre-2024 CAGR is 12.07%, Sharpe 0.81; 2020–2023 CAGR 10.82%, Sharpe 0.63.
