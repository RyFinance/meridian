# Strategy research survey: 18 web-research agents, 2026-10-17

Research only; nothing here was tested. Constraint: US retail account, $200–300. Agents mostly read abstracts and secondary sources, so every figure needs checking against the original paper.

## Tier 1: real long-run evidence and feasible at this size, but slow or modest
| Method | Evidence | Fit |
|---|---|---|
| Trend following via managed-futures ETF (DBMF/KMLM/CTA) | Time-series momentum back to 1880 (Hurst, Ooi & Pedersen). DBMF: +21.6% (2022), −8.9% (2023), +7.2% (2024), +13.8% (2025). | Fractional shares; diversifier, not a quick profit |
| Factor ETFs: value/momentum/low-vol/country value, rebalanced annually | Asness-Moskowitz-Pedersen; Frazzini-Pedersen BAB Sharpe 0.78 (1926–2012). Country-ETF anomalies survive costs with annual rebalancing (mean alpha 0.44%/mo). Decay: McLean & Pontiff, −58% after publication. | Feasible; returns of a few % a year over index |
| T-bills / money market | 3.5–4% (2026) | Baseline every idea must beat |

## Tier 2: plausible and testable with our tools, edge unproven
| Method | Evidence | Notes |
|---|---|---|
| **Kalshi favorite-longshot bias** (sell or avoid sub-10¢ longshots) | Bürgi, Deng & Whelan (UCD WP2025/19), ~300k Kalshi contracts: sub-10¢ buyers lose >60%. Bias shrinking over time. | Small-capital friendly. Kalshi taker fee ≈ 0.07·P·(1−P) per contract. Workspace already has `polymarket_arb`. |
| Kalshi/Polymarket BTC price-range contracts vs options-implied probabilities (Deribit/IBIT) | No rigorous study found; BSIC notes thin liquidity | Testable: options-implied density vs contract prices |
| Insider cluster buys (Form 4), buyback announcements | 21-day abnormal return 3.8% for cluster buys (1986–2016); buyback CAR 1.1%, fading by 2023–24 | Our own insider test failed validation (small-cap beta) |
| Turn-of-month in SPY | Persists to 2024, <1 pt/yr | Thin |
| Intraday momentum, last 30 minutes (Baltussen et al. JFE 2021) | 60+ futures, 1974–2020 | Our ES/NQ test failed (2026-09) |

## Tier 3: dead, decayed, or not feasible at $200–300
- 0DTE buying (retail loses ~$358k/day; costs are ~60% of the loss).
- Short-dated premium selling on MSTR/IBIT (our tests).
- Put-writing needs full notional; option alphas near zero over the last ~15 years (Dew-Becker & Giglio 2025).
- Crypto funding/basis carry: Sharpe negative in 2025.
- ETF flows, Coinbase premium and CME open interest: only same-day correlations.
- MSTR flows (mNAV, ATM issuance, converts, index inclusion, MSCI): mechanisms are real, nothing tradable at this size.
- Leveraged-ETF decay: needs a margin account (≥$2k), borrow costs and squeeze risk.
- Retail "arbitrage": ETF premium, cross-exchange, SPAC, closed-end funds, Kalshi vs Polymarket gaps.
- Overnight premium: SPY futures 2–3am window ~0 since 2021 (NY Fed); NightShares ETFs closed in 2023.
- Calendar effects: Halloween, January, Santa, OPEX, pre-FOMC (vanished after 2015).
- Dealer gamma / GEX / max pain: no out-of-sample evidence.
- AI/LLM sentiment, WallStreetBets, Google Trends, congressional copy-trading: small, decaying, cost-bound.
- IPO, lockup, de-SPAC, Russell reconstitution, micro-caps: old evidence, shorting needed.
- Commodity/FX carry: real, but micro futures margin is too large; DBC/PDBC is the only access.

## Most promising next research direction
**Prediction markets (Kalshi), especially the favorite-longshot bias and crypto range contracts.** It is the only edge with large-sample recent evidence (2025), a structural reason (behavioural longshot demand plus fees), and contracts sized for a $200–300 account.

## Data and tools needed
1. Kalshi historical market data (public API; an account and API key help for depth and trades).
2. Kalshi fee schedule (official page).
3. Polymarket data (the workspace has `polymarket_arb`).
4. Deribit or IBIT option chains for implied probabilities. Deribit's public API is free; IBIT chains come via LSE.
5. Optional: options quotes with bid/ask (ORATS or ThetaData, ~$30–100/month) to verify any options idea properly.
