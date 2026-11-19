# MSTR versus IBIT option-IV relative value: feasibility review

**Decision: infeasible under the requested protocol; no strategy is approved, frozen, or validated.**  There is no defensible net-profit or out-of-sample result to report.  This is a negative research result, not an indication that the hypothesis is false.

Two independent problems stop the study:

1. **Chronology.** IBIT was launched on 2024-01-05 and listed on Nasdaq on 2024-01-11 ([BlackRock annual report](https://www.blackrock.com/us/individual/literature/annual-report/ibit-1231.pdf)).  Nasdaq's notice for IBIT options is dated 2024-11-19 ([Nasdaq regulatory alert](https://www.nasdaqtrader.com/MicroNews.aspx?id=ORA2024-58)); a later NYSE filing says its exchange began listing/trading IBIT options on 2024-11-22 ([NYSE American filing](https://www.nyse.com/publicdocs/nyse/markets/nyse-american/rule-filings/filings/2025/SR-NYSEAMER-2025-45.pdf)).  There can therefore be no IBIT-option development sample in 2020--2022 or 2023.  A 2020--23 development / 2024--26 validation split is impossible, not merely small.
2. **Executable quote data.** No local IBIT option quotes or contract-definition file exists.  The available local MSTR option files are OHLCV print/candle data, not NBBO quote data.  They do not contain bid, ask, bid/ask size, quote conditions, quote exchange, IV, Greeks, or a contemporaneous underlying quote.  Bid/ask crossing, quote-staleness checks, vega matching, and conservative costs consequently cannot be measured for either leg.

No options were traded and no brokerage or market-data account was accessed for this review.

## Navigation limitation

The project's graph navigation CLI/wiki artifact was unavailable for this track.  Per the task instruction, the review used narrowly targeted local schema, coverage, and filename inspection rather than broad raw-file browsing.  The reproducible read-only queries are in [`inventory.sql`](inventory.sql).

## Local data inventory

| Local asset | Stored coverage and size | Fields relevant to this question | Assessment |
|---|---:|---|---|
| `data/lse/options_mstr/MSTR.parquet` | 1,729,096 rows; 83,952 OSI contracts; 318 expiries; stored `ts` from `2020-01-01 16:00:00-08` to `2026-09-15 17:00:00-07` | `ts`, `underlying`, `expiry`, `opt_type`, `strike`, `osi`, `open`, `high`, `low`, `close`, `volume` | Good contract identifiers and trade-bar coverage; **not usable for executable IV or bid/ask costs**.  The repository's MSTR puller describes it as per-contract OPRA *prints*, which is consistent with the schema. |
| `data/lse/options_mstr/1m/chunk_*.parquet` | 3,169,293 rows; 55,479 OSI contracts; 293 expiries; stored `ts` from `2020-08-17 06:32:00-07` to `2026-09-14 12:59:00-07` | Same OHLCV/OSI fields as above (plus a Pandas index field) | Minute granularity does not turn trade bars into quotes.  No bid/ask, size, quote timestamp, or IV/Greeks. |
| `research/mstr_btc_0dte/mstr_daily_yf.parquet` | 1,728 rows; `Date` from 2019-12-02 to 2026-10-16 | daily stock OHLCV | Useful only as a daily underlying reference; no executable intraday bid/ask. |
| `research/mstr_btc_0dte/mstr_stock_1m_lse.parquet` | 76,120 rows; stored `ts` from 2026-04-29 to 2026-09-16 | minute stock OHLCV | Too late and contains no quote fields. |
| `research/btc_session/ibit_1m_lse.parquet` | 73,539 rows; one symbol (`IBIT`); `ts` from 2026-04-28 08:00:00 to 2026-09-16 23:59:00 | `ts`, `symbol`, OHLCV | It is only an **underlying** bar file, with no option contract/quote fields.  The stored timestamp is timezone-naive and the file's Parquet metadata does not identify a data vendor. |
| Local option directories searched | `data/lse/options_mstr`, `data/lse/options_etf_1d`, `data/lse/options_1d`, and targeted `quant_v7` filename/manifest checks | `options_etf_1d` contains only IWM/QQQ/SPY; the `options_1d` manifest/universe has no IBIT or BTC-ETF entry | No local IBIT option-chain source was found.  This result does not claim that no such commercial data exists; only that it is absent from the supplied workspace. |

The Parquet key/value metadata on the three relevant market files contains standard Arrow/Pandas schema metadata, not a market-data vendor, capture method, or quote provenance.  This means even a future use of the existing bars needs separate lineage documentation.

## Why the required test cannot be repaired with the bars

An IV-spread backtest needs a contemporaneous price for a particular contractual right at which it could actually have been bought or sold.  OHLCV prints provide neither side of the market, can be stale, and may reflect a single small trade.  Reconstructing IV from `close` would create a **last-trade IV**, not an executable bid or ask IV; it would also invent the half-spread required by the mandate.  It is especially unsafe in thin MSTR strikes and during a Bitcoin move.

The required chronology additionally prevents the requested conventional protocol:

| Interval | Required role | What exists for IBIT options | Consequence |
|---|---|---|---|
| 2020--2022 | Development | IBIT did not exist | Zero observations |
| 2023 | Development | IBIT still did not exist | Zero observations |
| 2024-01 to 2024-11 | Validation start in the proposed premise | IBIT underlying traded, but listed IBIT options had not yet begun | No pairable option observations |
| 2024-11 onward | Earliest possible MSTR/IBIT listed-option overlap | No local IBIT option data; MSTR is prints-only | Cannot form or cost a signal |

Changing the study to "2025 development and 2026 validation" would be a distinct, explicitly amended protocol with much less development history.  It must not be described as a 2020--23-developed result, and it was not attempted here.

## Natural-predecessor check: rejected

No predecessor is silently substituted.

* **GBTC:** it is a closer spot-bitcoin trust economically, but does not solve the option-history issue.  An NYSE filing states that the exchange obtained authority to trade GBTC options on 2024-11-22 ([NYSE Arca filing](https://www.nyse.com/publicdocs/nyse/markets/nyse-arca/rule-filings/filings/2025/SR-NYSEARCA-2025-07_Am._3.pdf)).  It therefore cannot provide 2020--23 listed-option development observations either.
* **BITO:** it began in October 2021 and has options, but it is not a clean replacement for IBIT.  Its sponsor says it invests in Bitcoin futures and swaps rather than Bitcoin directly, can distribute monthly, and carries futures roll, collateral, margin, and tracking-basis effects ([ProShares fund page](https://www.proshares.com/our-etfs/strategic/bito)).  IBIT is a spot-Bitcoin trust, with a different basket/creation-redemption process; in-kind creations/redemptions were only authorized in July 2025 according to BlackRock's annual report.  MSTR is an operating company with equity-specific news, capital-structure, issuance, and mNAV risks.  A MSTR--BITO study would be a different futures-basis/ETF-distribution strategy, not a validation of MSTR--IBIT relative value.  No local timestamped BITO option NBBO/definitions are available in any case.

These distinctions matter even if the funds' daily correlations appear high: the option surface prices the underlying's own jump, carry, corporate-action, and liquidity risks.  Treating any of them as interchangeable would manufacture apparent relative value.

## What a viable future study would require

The minimum data source must be a reproducible historical OPRA-NBBO provider with point-in-time definitions.  Two documented examples are:

* [Databento's OPRA documentation](https://databento.com/blog/opra-data): historical options from 2023-03-28 onward, top-of-book `MBP-1`, historical definitions, and event timestamps.
* [Polygon's options data documentation](https://polygon.io/docs/options/getting-started) and [quote flat-file description](https://polygon.io/docs/flat-files/options/quotes/2022/11): OPRA-based options quotes with bid/ask and nanosecond timestamps.

Those references identify potentially reproducible commercial acquisition paths; no external data was downloaded, licensed, or used in this report.  Before research restarts, archive the vendor, entitlement, query/API version, retrieval date, checksums, and an immutable raw-data manifest.

For **both** MSTR and IBIT, collect from the first IBIT option listing date forward:

1. Every valid NBBO update and/or a deterministic synchronized snapshot around the permitted signal time, including exchange/event/receive timestamp, bid and ask price, bid and ask size, quote conditions, and cancellation/correction information.
2. Point-in-time option definitions: OSI/OCC symbol, underlying, call/put, strike, expiration, multiplier, settlement style, exercise style, and all adjusted-contract/corporate-action history.  Include MSTR's split history and multiply-adjusted options.
3. Contemporaneous underlying NBBO and corporate-action/borrow data for MSTR and IBIT, a risk-free curve/dividend treatment, and the actual brokerage commission/regulatory-fee schedule.
4. A conservative fill model: buys at ask and sales at bid, never mid; reject crossed/locked/stale quotes; require sufficient displayed size; log unfilled signals.  This automatically includes half-spread rather than estimating it from trades.
5. Assignment and hedge records: close American-style short structures before the assignment window (for example, 14 calendar days to expiration), or explicitly simulate exercise/delivery and stock/ETF hedges.  Each hedge must use its next executable underlying quote plus **3 bp per side** of auction/underlying notional, never a free close.

## Pre-registration boundary and a future-only rule template

**No rule is frozen for validation now.**  Freezing a MSTR/IBIT rule without data that can calculate the signal and cost its execution would be cosmetic rather than scientific.  There are therefore no development or holdout returns, trade counts, Sharpe ratios, or net-P&L claims in this report.

If an amended, post-2024-only research project is authorized after the required data are acquired, the following **single** bounded-risk template can be preregistered before touching the later holdout.  It is intentionally a template, not evidence of edge:

1. At 15:45 ET, use only same-expiry, 28--42-DTE contracts for which the MSTR and IBIT NBBOs and underlyings are no more than five seconds old.  On each chain choose the call nearest +0.50 Black--Scholes delta and the put nearest -0.50 delta, using the executable bid/ask-derived IV and the contemporaneous underlying midpoint.  Form the signal from the log of the two ATM straddle mid-IVs, with a 60-trading-day rolling mean and standard deviation calculated strictly through the prior close.
2. When the standardized log-IV ratio first exceeds +2.0 (or is below -2.0), trade only the corresponding **defined-risk** pair: a winged MSTR iron fly versus a long IBIT straddle (or the symmetric bounded short-IBIT/long-MSTR form), vega-matched from entry quotes.  Cross each option leg at bid/ask, add at least $1.00/contract/side plus actual regulatory charges, and do not substitute midpoint fills.  No naked short option is permitted.
3. Exit at the first of a zero-cross of the signal, 14 calendar DTE, 10 trading days, a defined-loss stop, or an unfillable/stale quote.  Rehedge only when net dollar delta exceeds a predeclared capital fraction, use the next underlying executable quote plus 3 bp per side, and record rejected fills.  Define capital as the greater of broker initial requirement and the complete defined maximum expiry loss (including long-option premium) plus a 25% stress reserve; report return only on that capital.

This is not a recommendation to use the thresholds; it merely illustrates the data, signal timing, cost, assignment, and capital rules that a real test would have to obey.  The `+/-2`, 60-day, 28--42-DTE, and 14-DTE choices must be locked before the eventual holdout and not tuned on it.  Because IBIT's option history begins only late 2024, even this amended study cannot substantiate the original 2020--23 development premise.

## Risk assessment

* A high MSTR IV relative to IBIT can be rational compensation for company leverage, mNAV/issuance events, convertibles, equity earnings risk, stock-borrow stress, and discontinuous Bitcoin moves.  It is not proof of a mean-reverting mispricing.
* Vega matching at entry does not neutralize gamma, skew, jump risk, or volatility-of-volatility.  The two surfaces can permanently reprice relative to one another.
* MSTR contract liquidity may be sparse exactly when the spread is extreme.  Print bars can make a stale contract look profitable; NBBO size and stale-quote rules are essential.
* A long IBIT option leg does not make a short MSTR straddle safe.  Defined-risk wings, worst-case capital, assignment treatment, and stress tests are required.
* MSTR corporate actions and ETF creation/redemption/friction regimes can invalidate naïve historical contract matching.  The time-varying 2025 shift to in-kind IBIT baskets is one example of a structural break.

## Artifacts

* [`REPORT.md`](REPORT.md) — this evidence-backed feasibility decision.
* [`inventory.sql`](inventory.sql) — read-only DuckDB inventory used to verify schemas and coverage.

All artifacts are confined to `research/mstr_btc_0dte/agent_ivspread/`.
