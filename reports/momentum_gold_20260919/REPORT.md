# Momentum + gold: research result and forward specification

**Fixed 50% SPMO / 50% GLD, monthly rebalance, no leverage.** Net simulated CAGR is 19.91% with 1.03 excess Sharpe over 2020–September 2026, and 17.98% with 1.06 Sharpe over 2017–September 2026. Maximum daily marked drawdown is 18.74%.

## Exact implementation

At the close of the first trading session each month, set equal dollar targets in SPMO and GLD. Execute at the next session open. Hold actual adjusted units between rebalances, so weights drift naturally. No trend filter, forecasts, leverage, fitted allocation weights, or individual-stock universe. The ETF return histories include embedded fund expenses and distributions. Base costs are 5bps per side of traded notional; stress is 15bps per side. Final liquidation is charged. Figures are before personal taxes and any account-specific currency-conversion fees.

SPMO is an actual momentum fund, with inception in October 2015; [Invesco fund information](https://www.invesco.com/us/financial-products/etfs/holdings?audienceType=Institutional&ticker=SPMO). GLD tracks gold less fund expenses; [SPDR fund information](https://www.spdrgoldshares.com/usa/gld/). The prices used here are adjusted daily fund histories from Yahoo, not reconstructed current-member stock portfolios. This portfolio itself is simulated, not an actual managed account track record.

## Results

| Portfolio / period | Net CAGR | Excess Sharpe | Max drawdown |
|---|---:|---:|---:|
| momentum_gold, 2017–2019 | 13.52% | 1.27 | -10.42% |
| momentum_gold, 2020–2026-09-17 | 19.91% | 1.03 | -18.74% |
| momentum_gold, 2017–2026-09-17 | 17.98% | 1.06 | -18.74% |
| market_gold, 2017–2019 | 12.40% | 1.36 | -11.03% |
| market_gold, 2020–2026-09-17 | 16.48% | 0.93 | -20.39% |
| market_gold, 2017–2026-09-17 | 15.29% | 0.98 | -20.39% |

Tripling modeled transaction costs leaves the later-period result at **19.83% CAGR / 1.03 Sharpe**. An independently written ledger reconciles daily NAV to within 1e-10 and all dollar P&L within $0.000001. Adding a $1 fee per order to the 5bps proportional charge on a $100,000 paper account yields 19.89% CAGR / 1.03 Sharpe.

The unmodified SPMO fund returned 21.75% annually / 0.84 Sharpe with a 30.95% drawdown over the same 2020–2026 window. The equal allocation gives up some return for lower volatility and drawdown. It is not the highest raw-return portfolio tested.

## Calendar-year total returns

| Year | Momentum/gold | Market/gold control |
|---|---:|---:|
| 2017 | 20.68% | 16.95% |
| 2018 | -0.84% | -2.80% |
| 2019 | 22.20% | 24.86% |
| 2020 | 27.50% | 23.07% |
| 2021 | 8.97% | 11.56% |
| 2022 | -5.12% | -9.37% |
| 2023 | 15.46% | 19.52% |
| 2024 | 36.81% | 26.14% |
| 2025 | 44.55% | 39.28% |
| 2026 through Sep 17 | 12.65% | 6.89% |

## What this supports, and what it does not

Later-period excess-Sharpe 95% interval from a 20-session block bootstrap: **0.35 to 1.75**. The annual arithmetic active return over 50% SPY / 50% GLD is 3.13%, with HAC t=1.58 and a 95% interval of -0.75% to 7.01%. That does not establish significant unique alpha above the simpler diversified control.

This was a follow-up hypothesis after three other fund designs were tested. The simple equal weights were recorded before this run and not optimized, but these years had already been examined in the broader project. This is a reproducible historical candidate with genuine traded-fund inputs, not an untouched holdout or proven future edge. Results may depend on the strong equity-momentum and gold regimes in this sample. SPMO does not supply a pre-2015 live record.

The original stock strategy remains provisional: a membership filter materially weakened it; missing removed stocks prevent a full point-in-time universe validation. No attempt was made to reinterpret that result as clean proof.

## All preceding fixed fund designs, 2020–2026

| Design | Net CAGR | Excess Sharpe | Max drawdown |
|---|---:|---:|---:|
| vol_scaled | 14.34% | 0.73 | -21.76% |
| diversified_trend | 11.09% | 0.64 | -18.60% |
| defensive_rotation | 12.74% | 0.53 | -30.95% |
| passive_SPMO | 21.75% | 0.84 | -30.95% |
| passive_SPY | 15.24% | 0.67 | -33.72% |

## Forward paper work

The exact weights and timing are now frozen in [forward_paper_spec.json](forward_paper_spec.json). A registration event is recorded in an append-only paper event file, with zero orders or fills. The expected next scheduled decision is the October 1, 2026 NYSE close, followed by the October 2 open. Calendar/data availability must be checked at execution. No live order was placed, no broker strategy changed, and no background scheduler was started.

- [All results](results.json)
- [Independent ledger verification](independent_check.json)
- [Uncertainty](uncertainty.json)
- [Equity and drawdown chart](equity_and_drawdown.png)
