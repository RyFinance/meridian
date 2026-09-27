# FX continuation after scheduled macro and policy news: pre-registration

Written 2026-09-23, before any directional or strategy return was computed.

Before registration, only these ran:
- data pulls: `data/fx_1m/`, see its manifest;
- data QA: FX gaps and stale runs; calendar timestamp alignment from published release schedules;
- one direction-free timing check: the mean **absolute** 1-minute FX return around corrected release
  times, over the development years only. Its result is recorded below.

Code frozen with this plan: `research/fx_news/events.py` and `evaluate.py`.
Tests: `tests/test_fx_news.py`.

## Why this is new

See `research/LSE_FRONTIER_MAP_2026-09-23.md` and the ledger.
- The project has never used intraday FX around scheduled news.
- It has never used the calendar's consensus field for inflation releases or central-bank rate
  decisions: `macro_surprise` excluded both.
- The only related trial, `macro_surprise`, used growth surprises at a monthly horizon in country
  equity ETFs. It failed, with a contemporaneous rank IC of +0.12 and a forward IC of −0.02.

This plan tests a different mechanism, horizon and instrument.

## Mechanism and direction (fixed)

- **Mechanism.** Macro news reaches exchange rates partly through order flow that arrives over the
  following hours (Evans & Lyons 2008, *JFE*). Dealers and real-money accounts rebalance after the
  initial quote jump. If the incorporation is gradual, the currency keeps moving in the news
  direction after the first 15 minutes.
- **Direction.** News that is hawkish or strong for the domestic currency means:
  - a policy rate above consensus;
  - inflation above consensus;
  - growth releases better than consensus (using the frozen `macro_surprise` taxonomy, including
    negative-direction series such as unemployment and claims).

  Such news predicts **further appreciation of that currency**, measured from release+15 min to exit.
- **If this fails, the reverse sign is not tested.**

## Data

- **FX.**
  - Source: the LSE vault, 1-minute bars, quote-derived, UTC, bar-start, stored in `data/fx_1m/`.
  - Pairs: EUR/USD, GBP/USD, AUD/USD, USD/JPY, USD/CAD, USD/CHF.
  - Timing: a price "at t" is the close of the bar ending at t. If the bar at t is missing, the
    close of the last bar within 5 minutes before t is used (F2 exits look back up to 3 days, to
    cover weekends).
- **Calendar.**
  - Source: `data/lse/econ_calendar_us.parquet`, 2015-01 → 2026-09.
  - Timestamps corrected as in `events.true_utc`. The correction comes from published schedules
    (payrolls 08:30 ET, Ifo 10:00 CET, AU labour force 11:30 AEST, JP GDP 08:50 JST, and so on):
    - rows from the 2025-12-10 bulk load: Europe/Berlin wall time for 2015, fixed UTC+1 from 2016;
    - rows from the live feed (created from 2025-12-31): UTC.
    - Duplicate rows across batches collapse.
    - Rows stamped 00:00, i.e. with no release time, are dropped.
- **Currencies.**
  - US news → an equal-weight USD basket against EUR, GBP, AUD, JPY, CAD and CHF.
  - Euro-area news (EA/EU/DE/FR/IT/ES/NL/AT/BE/IE/PT/FI/GR) → EUR/USD.
  - GB/UK → GBP/USD; JP → USD/JPY; AU → AUD/USD; CA → USD/CAD.
  - CH has almost no calendar history and is excluded.
  - Other regions have no pair and are excluded.

## Events and signal (as in `events.py`)

1. **Classification.** Each release is classified as policy (`interest rate decision`, excluding
   loan-prime, deposit, lending and overnight facilities), inflation (CPI, HICP, PPI, PCE, RPI or
   inflation-rate names, excluding expectations, import/export, house and wholesale prices) or growth
   (the frozen macro_surprise taxonomy). Anything else is ignored.
2. **Vote** = direction × sign(actual − consensus). Only numeric actual and consensus count.
3. **Event group** = currency × true release minute. The net vote is the sum of the votes; the trade
   is sign(net vote). Zero net: no trade.
4. **Candidates.** Both enter at the price at t0 + 15 minutes, 1 unit of notional per event group.
   - **F1:** exit at t0 + 120 minutes.
   - **F2:** exit at t0 + 1,440 minutes (24 hours; the Friday close if that falls on a weekend).
5. **Accounting.** Positions from different events may overlap; each event's P&L counts separately.
   Daily P&L is the sum of event P&L by exit date, weekend exits booked to the preceding Friday. The
   Sharpe is annualised over all weekdays in the window, with zero days included, and is
   scale-free. Overnight financing is ignored at these horizons.

## Costs

| | Per side, per unit notional | Round trip |
|---|---:|---:|
| Base | 1.0 bp | 2 bp |
| Stress | 3.0 bp | 6 bp |

Entry at +15 minutes avoids the widest post-release spreads. Retail major-pair all-in costs are
roughly 0.3–0.6 bp a side.

## Controls and nulls

- **C_REACT:** trade the sign of the currency's own move from t0 to t0 + 15 minutes (reaction
  momentum), with the same windows. This tests whether the surprise sign adds anything beyond price
  continuation.
- **C_ALL:** long the news currency after every release. This tests for a generic post-release drift.
- **Permutation null:** 2,000 shuffles of trade signs within currency × category-set strata. Timing,
  volatility and exposure are kept; only the link to the surprise is broken. This gives the one-sided
  p-value and P(pass | null) for the development gate.

## Windows

- **Development:** events with t0 in 2015-01-01 → 2020-12-31 (6.0 years).
- **Validation (locked):** 2021-01-01 → 2026-09-16.
  - The run refuses to start without `research/fx_news/VALIDATION_UNLOCK.md` registered.
  - It runs once, only for selected candidates.
- The project has never used FX 1-minute data or this calendar at intraday resolution. The dev-year
  timing check used absolute returns only.

## Gates (protocol amendment 2026-09-23)

**Development**, applied to each of F1 and F2:
- net base daily Sharpe ≥ **1.8/√T**, with T in years of weekdays (T = 6.0 gives 0.735);
- stress mean > 0;
- permutation p < 0.05.

**Validation**, applied to each selected candidate:
- net base Sharpe ≥ 0.75;
- stress mean > 0;
- one-sided block-bootstrap p < 0.025 (21-day blocks);
- permutation p < 0.025.

α = 0.05/2 for the two candidates. A pass means a frozen forward registry test only, never capital.
A fail is recorded; no horizon, entry lag, taxonomy, cost or sign is re-specified.

## Reported

- Per candidate: events; mean net bp per event; hit rate; daily Sharpe (gross, base, stress);
  bootstrap p; permutation p and P(pass | null).
- Control comparisons, and the correlation of the surprise sign with the reaction sign.
- By currency, category and year.
- Gross continuation by reaction-size quintile.

## Known limits

- **Consensus cannot be fully verified as point-in-time**; the file was bulk-loaded. First-print
  `actual` is verified (payrolls check).
- **Quotes may be mid or one-sided.** A constant spread cancels; a spread widening after releases
  would be missed. Stress costs cover about 3× normal.
- **Developed-market policy surprises are rare** (about 30 groups), so policy contributes little.
- **Entry at +15 minutes assumes automated execution.**
- **Growth and inflation releases often coincide** (5% of groups are mixed); the net vote handles it.

## Pre-registration QA results (filled in before registration; no directional statistic computed)

- **FX data.** Checked per pair-year from 2015 to 2026.
  - Clean: no duplicates, monotonic timestamps, no volume field, no stale runs of 30 minutes or more
    in active hours.
  - Missing active-hours minutes are 0–1.75% a year.
  - Spike-and-revert ticks over 0.5% are rare, except AUD/USD 2021–2025 at 20–65 a year. They are
    symmetric noise and are not filtered.
  - The first USD/CHF pull failed on network timeouts for 2017–2026. It was re-run until complete
    before registration. See `data/fx_1m/manifest.json`.
- **Timestamp alignment, from release schedules** (`tests/test_fx_news.py`):
  - corrected payrolls fall at 08:30 ET in more than 97% of cases;
  - corrected JP GDP falls at 08:50 JST in more than 90%.
- **Direction-free volatility profile** (`reports/fx_news/qa_timestamp_profile.json`). It measures
  the mean |1-minute return| of the traded pair around corrected t0, over 2015–2020 only.
  - The peak is at **minute 0** for EUR (1.8× the local median), GBP (4.5×), AUD (6.9×), CAD (6.1×)
    and USD, measured on EUR/USD (3.0×).
  - JPY releases barely move USD/JPY: 1.1–1.3× at minute 0 for every release time. Its peaks sit
    at fixed clock times whatever the release time: 00:54 UTC, the Tokyo fix at 09:55 JST, and
    06:00 UTC. That shows the corrected times are right and Japanese data carries little immediate
    information.
  - JPY stays in the event set, as planned.
