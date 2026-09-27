# Japan cash-session information and the later US equity session

Registered 2026-09-23. One hypothesis and one directional specification. No signal/return relationship was calculated before this plan. The 2016–2020 Nikkei cash-session bar schedule and ES bar schedule were sampled for timestamp and scale checks only. This is an independent information family: none of the registered US intraday rules uses Asian cash-equity returns, and the multiasset book uses own-market overnight or slow asset-price signals.

## Mechanism and claim

Japan's completed cash equity session may carry global risk information that US futures have not fully incorporated by the US regular-session open. Test whether the sign of the same-calendar-date Nikkei cash-session return predicts the subsequent ES US regular-session return. This is an **incremental cross-market information** claim, so beating zero alone is insufficient: it must beat a control that uses ES's own overnight sign under identical fills and costs.

## Data, timing and exclusions

- Source: live LSE Terminal MCP `get_history`, 30-minute `JP225/USD` bars. Archive raw returned CSV and SHA-256. ES is the existing LSE 30-minute `data/lse/futures_30m/ES_F.parquet`; record its SHA-256 and independently match sampled MCP bars. The symbol is named `/USD` but its level is in Nikkei index points. Use percentage returns only; do not interpret index volume as executable shares.
- A Japan signal day requires exactly the ten 30-minute cash-session bars with UTC start labels 00:00, 00:30, 01:00, 01:30, 02:00, 03:30, 04:00, 04:30, 05:00, 05:30 (the 11:30–12:30 JST lunch break is empty); each must have finite positive OHLC and high ≥ max(open,close), low ≤ min(open,close). The open is the 00:00 bar open and the close is the 05:30 bar close, known at 06:00 UTC (15:00 JST). Reject any day with extra bars, including a later 24-hour feed regime, rather than silently changing the signal.
- ES bar labels are left edges. On the same US/New York date, enter at the 09:30 ET bar **open** and exit at the 15:30 ET bar **close** (16:00 ET). Both bars and the previous US session's 15:30 close must exist with finite positive OHLC. The Japan close always precedes entry by at least 7.5 hours, including DST. No future-day alignment or forward fill. Flat when Japan or US is closed or bars fail the audit.
- Continuous front-month ES can jump at contract rolls. Exclude the Thursday before the third Friday of March, June, September and December through the following Monday, matching `research/intraday/PLAN.md`. Reject any ES entry/exit day with a within-session open-to-close absolute return above 10% as a data-integrity failure; report exclusions without replacing returns.
- Current-symbol survivorship does not apply to a historical index and one futures contract, but the index's constituent history is embedded in the published level. Vendor historical corrections are possible; LSE gives no as-of vintage. The continuous futures series has no individual-contract roll/settlement audit. These are limitations on trust, not parameters to optimize.

## Frozen strategy and controls

- `J1`: position +1 ES notional per unit NAV when log(Nikkei cash close/open) > 0, −1 when < 0, flat at exactly zero. Same-day US RTH open-to-close return is `position × (ES_exit/ES_entry − 1)`.
- Base cost: 0.5 bp each side of ES notional, 1 bp for a round trip. Stress: 1.5 bp each side. Every nonflat day pays both sides, including consecutive same-sign days; no overnight position. Futures P&L is excess return; no fictitious cash carry. Commission/spread/slippage are an assumption, so any passing result requires later executable-fill audit.
- `C1`: position is the sign of ES from the previous US regular-session 16:00 close to today's 09:30 ET open, on **exactly the J1-eligible days**, with identical entry, exit and costs. This is the direct information control.
- `C2`: always-long ES RTH on the same eligible days, same costs. This quantifies exposure to the regular-session premium and is descriptive, not an alternate candidate.
- `P1`: circularly shift the Japan signs across eligible dates by at least 252 eligible sessions and at most N−252, preserving their distribution and serial structure while breaking alignment. 5,000 seeded worlds (seed 20260923); count the fraction clearing J1's development Sharpe and stress-mean gate, with Monte-Carlo SE. Use `research.null_lab.api.run_null` in development-only mode with an exactness test against direct return arithmetic. No validation prices are fed to this null.
- `P2`: negative Japan sign on the same dates (a prespecified directional placebo); report, do not promote or tune.

## Windows and gates

- **Development:** 2016-06-01 through 2020-12-31, every US session in that interval, with zero strategy return on ineligible days. No return from 2021 onward may be computed now.
- **Validation:** 2021-01-01 through 2026-09-17, locked. A separate registered unlock may run it only if all development gates pass, and only after auditing the 2026 change in Japan bar coverage. Do not modify the rule to accommodate that change after seeing returns.
- T is the development calendar length in years (days/365.25). Primary gate: J1 net base annualized excess Sharpe ≥ 1.8/√T and J1 stress-cost annualized mean > 0. Also require J1 minus C1 annualized net mean > 0 and a one-sided 21-day circular-block bootstrap p < 0.05 for this paired difference (5,000 draws, seed 20260923). A strategy that only beats zero has not established new information over ES's own overnight move.
- Report gross/base/stress annualized mean, Sharpe, max drawdown, trades, coverage, yearly net result, control differences, and P(pass | shift null) ± MC SE. Diagnostic only: best contiguous 12 and 24 months removed, and correlation of J1 and C1 daily returns. These diagnostics cannot rescue a failed gate.
- If any gate fails, preserve the null, leave validation locked, and do not tune signal, thresholds, assets, costs or dates. If all gates pass, freeze code and attack leakage, bar quality, factor exposure, concentration, regime dependence, and false discovery before any validation unlock.
