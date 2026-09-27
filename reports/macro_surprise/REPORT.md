# Macro-surprise country rotation: development FAIL, validation not run

Run 2026-09-23. Plan: `research/macro_surprise/PLAN.md` (sha256 f7d07348…, registered
2026-09-23T00:13:25-0700) and `PLAN_AMENDMENT_1.md` (8e83054b…, 00:13:40). Both were registered
before any return. Code: `research/macro_surprise/{signals,evaluate}.py`. Tests:
`tests/test_macro_surprise.py` (30 pass). Output: `reports/macro_surprise/dev/`, which holds
`results.json`, `selection.json`, the daily NAV of every book at gross, base and stress cost,
monthly targets, and the signal panel.

**Verdict: FAIL.** M1 has a net excess Sharpe of **−0.50** (gross −0.20, stress −1.39). It is
negative in 5 of 6 years, and its intercept on the momentum control is negative. `selected: []`,
so validation (2021–2026) stays locked. The ledger grows by 2 trials (M1, M2).

## What was new

This is the first use in the project of the economic calendar's `actual` versus `consensus`
fields: 47,789 classified growth releases across 14 economies, 2015–2026. Earlier trials used only
release *dates* (I4, auction cycle). The hypothesis was continuation: countries with more positive
growth surprises over the last 91 days outperform over the next month.

## Development, signals 2015-04 → 2020-11, returns 2015-05-01 → 2020-12-31 (5.7 years)

Daily marked NAV; next-open execution; 10 bps a side, 1% borrow (stress 30 bps, 5%, proceeds earn
nothing); excess over the 13-week bill.

| Book | Gross Sharpe | **Net Sharpe** | Stress | CAGR | Vol | Max DD | Turnover | Cost drag | 95% CI (net) | β SPY |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| M1 long-short (candidate) | −0.20 | **−0.50** | −1.39 | −4.5% | 10.1% | −29.7% | 20.5× | 3.1% | [−1.26, 0.22] | −0.02 |
| M2 long-only top third (candidate) | 0.36 | **0.31** | 0.21 | 5.3% | 20.1% | −39.4% | 9.8× | 1.0% | [−0.46, 1.17] | 0.91 |
| C_EW equal-weight 14 countries | 0.26 | 0.25 | 0.25 | 4.2% | 21.3% | −43.6% | 0.6× | 0.1% | [−0.53, 1.13] | 1.00 |
| C_MOM 3-month price momentum L/S | −0.81 | −1.05 | −1.71 | −14.0% | 14.3% | −61.3% | 23.5× | 3.4% | [−1.74, −0.38] | −0.04 |

**Gate checks**
- M1: needs Sharpe ≥ 0.50; got −0.50, **fail**. Needs stress mean > 0; got −14.3%/yr, **fail**. Needs
  intercept on C_MOM > 0; got −4.7%/yr, t −1.21, **fail**.
- M2 is not eligible, because M1 failed. For reference only: M2 − C_EW = +0.85%/yr, t 0.31,
  bootstrap p 0.37, and −0.98%/yr at stress cost. The long-only tilt is the equal-weight market
  plus noise.

**M1 by year (net):** 2015 −5.7%, 2016 −8.5%, 2017 −0.3%, 2018 −5.6%, 2019 −5.7%, 2020 +0.8%.

**M1 contribution by economy (net, arithmetic):**
- Losers: India −15.8%, Japan −13.8%, China −11.8%, Indonesia −7.5%.
- Winners: Canada +19.0%, Brazil +10.9%, US +8.3%.

No single name drives the loss. Canada was long in 27 of 68 months, a partly static tilt (Canadian
consensus is systematically low).

Correlations of daily net returns:
- M1 with C_MOM 0.04, and with C_EW −0.04. The signal is not price momentum under another name.
- M2 with C_EW 0.95.

## Why it failed: the news is real, and it is already priced

This was a signal-validity diagnostic, not a new trial. Each month, rank the 14 economies by the
surprise score:

| Rank correlation of the surprise score with… | Mean | Share of months > 0 |
|---|---:|---:|
| the same 91-day window's ETF return (contemporaneous) | **+0.12** | 72% |
| the next month's ETF return (the tradable claim) | **−0.02** | 48% |

The taxonomy and the calendar data measure something markets care about: countries with good
surprises had good returns *while the surprises arrived*. Nothing carries into the next month.
Country ETFs, including EM ETFs, absorb macro surprises as they are released. Under-reaction at a
monthly horizon is not present in 2015–2020 at the level of US-listed country funds. With a
5.7-year window the net interval [−1.26, 0.22] rules out a Sharpe of 0.5 for M1 at about the 95%
level, so this is a **bounded null**, not a vacuous one.

## Engine verification (before interpreting)

The control C_MOM lost about 12% a year gross in every year, which is extreme enough to suspect a
sign bug. I checked it three ways:

- **Static position:** a long-SPY/short-EWJ position from 2017-04-03 to 2017-12-29 gives an engine
  excess of −2.86%, against an independent open-to-close spread of −2.88%.
- **Period returns:** independent open-to-open period returns reproduce every book: C_MOM −11.9%/yr
  gross, M1 −2.1%, M2 +8.0% total. The engine gives −11.6%, −2.0% and consistent figures.
- **Signal:** the 63-day momentum rank IC against the next month is −0.10, negative in 67% of
  months.

The engine is right. Three-month country momentum reversed in this sample.

**Do not trade that reversal.** It is a post-hoc observation on a control, in a price-transformation
family that is heavily mined (reversal). It is not a registered hypothesis and not evidence of an
edge. Any use of it needs a new registration evaluated only on data after 2026-09-23.

## Limits

- Five-point-seven years, 14 economies, 4 per leg.
- The consensus history was bulk-loaded by the vendor in 2025-12. Payrolls spot checks match
  history, but full point-in-time quality is unverifiable.
- Russia is excluded (its ETFs were delisted in 2022).
- Release times: US rows are stamped one hour after UTC, other regions UTC. This is neutralised by
  using only releases dated before the signal day.
- This tests the continuation claim at a monthly horizon in USD country ETFs only. Intraday
  reactions, FX and bonds are untested. After this result their prior is low: the contemporaneous
  IC says surprises are priced quickly.

## Classification

Macro-surprise continuation in country equity ETFs is **SPENT**; do not re-specify the window,
scaling, keywords or sign. The calendar surprise fields as an information source are
**PARTIALLY USED**. They remain untested for FX and rates, where the prior is now low.
