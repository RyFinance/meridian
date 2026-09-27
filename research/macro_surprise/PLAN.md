# Macro-surprise country rotation: pre-registration

Written 2026-09-23, before any strategy, control or signal-return statistic was computed. Code
before registration: `research/macro_surprise/signals.py` (signal only) and a price pull
(`data/macro_surprise/`, manifest with sha256). Data QA that ran before this plan and saw no
returns: event-name taxonomy, number parsing, release counts per economy and month, the
cross-sectional dispersion of the signal, and ETF price completeness.

## Why this information set

Every earlier trial in `research/preregistrations.jsonl` used prices, volumes, option prints,
positioning, filings, accounting or event *dates*. The economic calendar's `actual` and
`consensus` fields have never been used: I4 and the auction study read only release dates.
Macro surprises (actual minus the pre-release consensus) are information about the economy
relative to expectations. They are not a transformation of the ETF price paths.

## Mechanism

Global investors process foreign macro news slowly and with home bias; consensus forecasters
adjust with a lag. A run of better-than-expected growth data then continues to be reflected
in a country's equity prices and currency over the following weeks. The claim is continuation
(under-reaction), and the direction is fixed here: **more positive growth surprises predict higher
subsequent USD returns of that country's equity ETF relative to other countries.** If this
fails, the reverse sign is not tested.

Related literature on fundamental/macro momentum across countries: Brooks (2017) *A Half Century
of Macro Momentum* (AQR); Scotti (2016, JME) on real-time surprise aggregation. Those papers
motivate the direction; they did not choose any parameter below.

## Data

- Calendar: `data/lse/econ_calendar_us.parquet` (LSE vault, 2015-01-01 onward). Field `actual`
  is the first print (`actual_revised` is set on 0.0007% of rows). Spot checks against the
  known US payrolls consensus for Jan-Mar 2015, May-Jun 2020 and Jan-Feb 2024 match.
- The file was bulk-loaded in 2025-12, so point-in-time consensus cannot be fully verified; this
  is a stated limitation.
- Time stamps: US rows sit one hour after UTC; other regions look like UTC. The signal uses only
  releases whose stamped calendar date is **before** the signal date, so no time-zone reading
  can leak a release from the signal day or later.
- Prices: yfinance total-return adjusted daily bars (`adj_open`, `adj_close`). SPY, EWJ, EWU, EWA,
  EWC, EWZ, EWW and EWY from `data/etf_hybrids/`; EZU, MCHI, INDA, EZA, TUR and EIDO from
  `data/macro_surprise/`, pulled 2026-09-23. No missing sessions against the SPY calendar since
  2014-10.
- Cash: prior observed 13-week bill (`data/multiasset/rates/IRX.parquet`), accrued over elapsed
  calendar days (`research/return_search/run.cash_rates`).

## Universe (14 economies, fixed)

| Economy | ETF | Calendar region codes |
|---|---|---|
| US | SPY | US |
| Japan | EWJ | JP |
| UK | EWU | GB, UK |
| Euro area | EZU | EA, EU, DE, FR, IT, ES, NL, AT, BE, IE, PT, FI, GR, SK |
| Australia | EWA | AU |
| Canada | EWC | CA |
| Brazil | EWZ | BR |
| Mexico | EWW | MX |
| Korea | EWY | KR |
| China | MCHI | CN |
| India | INDA | IN |
| South Africa | EZA | ZA |
| Turkey | TUR | TR |
| Indonesia | EIDO | ID |

Inclusion rule, applied before any return: at least 200 calendar rows in 2015 and a US-listed
country ETF trading before 2015. Russia meets the calendar rule but is excluded because its ETFs
(RSX, ERUS) were halted and delisted in 2022 and yfinance no longer serves them. This is a known
survivorship exclusion. Argentina, Saudi Arabia and Singapore fail the 2015 count rule.
UK and EU are the 2025-26 codes for GB and EA in the same file.

## Signal (as implemented in `signals.py`)

1. **Growth releases.** An event name (period suffix removed) is classified by keyword, checking
   three lists in order. Any **EXCLUDE** keyword makes it not a growth release: prices and
   inflation, wages and earnings, trade and current account, fiscal items, policy rates, credit,
   money and loans, inventories, flows, housing prices, participation rate. Otherwise any
   **NEGATIVE** keyword gives direction −1: unemployment, jobless, claimant, job cuts. Otherwise
   any **POSITIVE** keyword gives +1: GDP, PMI, production, orders, sales, spending, payrolls,
   employment, confidence, sentiment, business and consumer surveys, activity indices, housing
   starts and permits, investment, and so on. Unmatched names are ignored. The exact keyword
   lists are in `signals.py` and are frozen by this plan's hash of that file.
2. **Vote.** For a growth release with numeric `actual` A and `consensus` C, the vote is
   direction × sign(A − C). Numbers are parsed with K/M/B/T multipliers; %, currency symbols
   and "Points" are stripped. Rows missing either number are dropped. Duplicates are dropped by
   economy, day, name and values; they arise from the GB/UK and EA/EU overlap in 2025-26.
3. **Window.** For signal date t, the window is releases with stamped date in [t − 91 days, t − 1 day].
4. **Score.** z_k,t = (sum of votes) / sqrt(n), where n is the number of votes. It is missing if
   n < 10. Scaling by sqrt(n) gives every economy unit variance under a no-information null.
   A plain mean vote would put low-count economies in the tails mechanically: in pre-registration
   QA the mean-vote dispersion was 0.10 for the US and 0.33 for Indonesia. This choice was made
   from signal-only QA; no returns were seen.

## Portfolios

Signal dates are the last NYSE session of each month (SPY calendar). An economy is eligible at t
if z is non-missing and its ETF has a close on t and at least 64 sessions of history. With N
eligible economies, k = floor(N / 3). Ties are broken by the fixed table order.

- **M1 — long-short (primary information test).** Long the top-k economies by z and short the
  bottom-k. Each leg is 100% of NAV, weighted within the leg by inverse 63-session volatility of
  daily adjusted-close log returns ending at t.
- **M2 — long-only tilt (implementable form).** The M1 long leg alone, 100% of NAV.

Controls. These are not candidates: they are reported and used in the gates below.
- **C_EW:** equal weight across all eligible economies, 100% NAV, the same monthly schedule.
- **C_MOM:** the M1 construction ranked on each ETF's 63-session adjusted total return ending at
  t. This checks that M1 is not three-month country price momentum.

Execution: the book is decided at the close of t and traded at the next session's `adj_open`.
Units are held until the next rebalance open. Daily mark-to-market uses `adj_close`, with
overnight P&L on old units before the trade. There is no leverage beyond the 100/100 long-short
book.

## Costs and financing

| | Base | Stress |
|---|---|---|
| Trading, per side on traded notional (including initial entry and final liquidation) | 10 bps | 30 bps |
| Short borrow, per year on short market value (calendar days) | 1.0% | 5.0% |
| Short proceeds and cash | Cash balance earns the bill rate | The short-proceeds portion earns nothing |

Returns are daily, net, marked to market. Excess returns are measured against the same bill
accrual. Taxes are excluded.

## Windows

- **Development:** signal dates 2015-04-30 → 2020-11-30. Returns from the 2015-05-01 open to the
  2020-12-31 close, with final liquidation charged. The dev run truncates prices and the
  calendar at 2020-12-31 before computing anything.
- **Validation (locked):** signal dates 2020-12-31 → 2026-08-31. Returns from the 2021-01-04 open
  to the last available close (2026-09-18), with final liquidation. The run refuses to start
  unless `research/macro_surprise/VALIDATION_UNLOCK.md` is registered in
  `research/preregistrations.jsonl` with a matching hash. Validation runs once, only for
  candidates selected by the development gate.
- These ETF price paths were seen in earlier trials with other signals (multiasset, etf_hybrids,
  return_search). The calendar surprise fields were not.

## Gates

**Development → validation**
- M1 is selected if all of these hold:
  - net base excess Sharpe ≥ 0.50;
  - stress mean excess return > 0;
  - the intercept of M1's daily excess return regressed on C_MOM's daily excess return is > 0
    (point estimate, Newey-West 10 lags reported).
- M2 is selected only if M1 is selected **and** M2's dev net base excess Sharpe exceeds C_EW's.

**Validation pass (run once)**
- M1 passes if all of these hold:
  - net base excess Sharpe ≥ 0.75;
  - stress mean excess > 0;
  - one-sided circular block bootstrap p < 0.025 (21-session blocks, 5,000 draws, seed 20260923);
  - intercept on C_MOM > 0.
- M2 passes if all of these hold:
  - the daily active return M2 − C_EW has a one-sided bootstrap p < 0.025;
  - the stress active mean is > 0.
- α = 0.05 / 2 (two candidates, Bonferroni).
- A pass means a frozen forward paper test, not capital. A fail is recorded and not re-specified:
  no other window, lookback, threshold, weighting, keyword list or sign.

## Reported for every book

- CAGR, excess Sharpe (gross, base, stress), volatility, max drawdown, turnover, cost drag
- Beta and alpha to SPY (Newey-West)
- Year-by-year returns
- Per-economy P&L contribution, and time spent long and short per economy
- Correlation with C_MOM and C_EW
- Deflated-Sharpe probability at 110 project trials
- Bootstrap Sharpe interval

## Trial count

2 candidates (M1, M2), plus 2 controls that are not candidates. The project ledger grows by 2.

## Known biases and limits

- Short sample: 67 development months. A true Sharpe of 0.6 has a standard error of about 0.4
  here, so a development failure is weak evidence against the mechanism, and a pass is weak
  evidence for it.
- 14 economies, 4 per leg: concentrated. Emerging-market ETFs are volatile, which is why weights
  are inverse-volatility.
- Consensus point-in-time quality cannot be fully verified (vendor backfill in 2025-12).
- 2025-26 feed change: consensus coverage falls, region codes change and ES/SG rows appear. This
  affects the validation tail only; the mapping is fixed above.
- USD ETF returns combine local equity and currency. That is intended, but the result cannot be
  attributed to either leg.
- Russia excluded (see Universe).
