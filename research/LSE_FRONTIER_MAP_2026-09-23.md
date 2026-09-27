# LSE research frontier map — 2026-09-23

Sources:
- the catalog `data/lse_catalog_20260917.json` (22,966 series);
- three audits run this session:
  - `reports/lse_audit/` — reference and event datasets;
  - `reports/lse_audit_market/` and `research/lse_audit_market/classification_20260923.json` — market data;
  - the yield pull QA, `data/bond_yields/manifest.json`;
- the project ledger (`research/RESEARCH_LEDGER_2026-09-23.md`, `research/preregistrations.jsonl`).

No strategy return was computed for this map.

## Data-semantics rules

Anyone using LSE data must apply these:

- **Stock and ETF bars include extended hours, in UTC, bar-start.** This holds for intraday bars as well as `1d`. Rebuild official 09:30–16:00 ET sessions from intraday bars (`research/forward/prices.py`: ETFs within 3 bps, single stocks within about 32 bps because of auction prints).
- **Stocks are current listings only.** SIVB, FRC, TWTR and CELG are absent, and the 127 non-live names all stopped trading after 2026-04-13. Every stock cross-section is survivor-biased.
- **Ticker reuse is real.** BBBY's financial history is spliced onto a different company. Key on CIK, never on ticker.
- **Stock prices are split-adjusted. Dividend amounts are not.**
- **Stock intraday depth varies by name.** The catalog's mean history is 8.8 years; AAPL and JPM have 1-minute data back to 2005, but many names start much later. Check each name; do not assume 2003.
- **FX bars are quote-derived** (volume always 0), UTC. EUR/USD daily bars exist before the catalog's stated 2009 start.
- **Economics series are revised final values, not vintages.** `macro_series` gives Dec-2014 payrolls as 274K; the first print was 252K. Only the economic calendar's `actual`/`consensus` fields are point-in-time safe. `previous` is revised on 21% of rows.
- **Calendar timestamps:**
  - US rows are stamped one hour after true UTC; other regions look like UTC.
  - They must be aligned before any intraday use (see `research/fx_news/PLAN.md`).
  - The calendar was bulk-loaded on 2025-12-10.
- **Bond yields are constant-maturity series.** No vintages; each follows its own local business calendar; there are stray weekend rows.
  - Errors: IN2Y 2010-02-24/26 and MX10Y three days are misprints; JP10Y has zero placeholders.
  - Shared hole: KR10Y, TR10Y and ZA10Y are missing 2012-11 → 2017-01.
  - Late starts: short tenors for BR, ZA and TR begin only in 2025-07; MX has no short tenor.
- **Credit indices are total-return or price index levels, not spreads.**
  - Coverage: USD/EUR/GBP IG and HY, daily from 2010.
  - Access: only through `macro_series` with `dataset="credit_indices"`. `get_history` and `macro_search` cannot find them.
- **Options are OPRA trade prints only**, from 2014, reached only through `/export` (5 jobs an hour, 2.5M rows, silent truncation).
  - There is no bid/ask and no OI.
  - The live chain (from 2026-06-11) has last-trade IV and greeks only.
- **Insider trades** are shallow (about 12–18 months) and heavily duplicated, bulk-loaded in 2026-01. They also contain an unused Senate-trading subtype.
- **company_profiles and stock_fundamentals** are current snapshots, not point-in-time.

## Family classification

| Family | What it is | Prior project use | Class |
|---|---|---|---|
| US stock prices / volume (S&P 500 names) | daily and intraday OHLCV, survivor-biased | momentum, reversal, ML, PEAD, insider universe | **SPENT** |
| Other ~3,500 US stocks, extended-hours structure | intraday OHLCV, including pre/post market | none | GENUINELY UNTESTED but **UNSUITABLE for trust**: survivor-biased with no delisted names; thin early history |
| OPRA stock options (100 names) | trade prints | H1–H4, IV changes | **SPENT** |
| OPRA options, other ~3,000 underlyings / aggregate breadth | trade prints | none | PARTIALLY USED; per-name work UNSUITABLE (no quotes/OI) |
| Index options SPY/QQQ/IWM | trade prints | 1-day put writing | PARTIALLY USED |
| ES/NQ intraday | 1m/30m futures, 2016+ | I1–I4, LETF | **SPENT** |
| GC/SI intraday | 1m futures, 2016+ | none | UNTESTED, low prior (price-only) |
| Other futures (68) | mostly 2025–26 | none | **UNSUITABLE** (too short) |
| FX, G10 carry, value, momentum, session | spot and forward points | fx_carry_vol, multiasset, fx_session | **SPENT** |
| FX, EM crosses (TRY, ZAR, MXN, PLN, HUF, CZK, THB, SGD, CNH) | quote bars, 2009+ | none | PARTIALLY USED (asset used, EM breadth not) |
| FX intraday around scheduled news | 1m quotes plus the point-in-time calendar | none | **GENUINELY UNTESTED** ← chosen |
| Economic calendar, growth surprises | actual vs consensus | macro_surprise (country ETFs, monthly): failed | **SPENT** for that use |
| Economic calendar, inflation surprises | actual vs consensus | excluded by macro_surprise | **GENUINELY UNTESTED** |
| Economic calendar, central-bank decisions | 1,507 decisions, 200 surprises, 20 regions | excluded by macro_surprise | **GENUINELY UNTESTED** |
| Economic calendar, `previous` revisions | revision flags | none | UNTESTED, low prior |
| Economics series (14,911) | revised final values | none | **UNSUITABLE** point-in-time (except daily market series) |
| Government yields, multi-country (`bonds`, 1990+) | constant-maturity yields | multiasset constructed-bond sleeves (G10 10Y) | PARTIALLY USED. Using yields to choose *other* assets is untested, but short-tenor coverage is only 9–10 of 14 economies |
| Credit indices (USD/EUR/GBP IG/HY) | total-return levels, 2010+ | none | **GENUINELY UNTESTED** (time series; low breadth) |
| Corporate bonds (192) | prices, 2020+ | none | UNSUITABLE (short; not retail-tradable) |
| Dividends (with declaration_date) | point-in-time announcement timeline | only for adjustments | **GENUINELY UNTESTED** as events. Survivor-biased prices; the related OSAP predictors (initiations, omissions) have already been viewed |
| Stock splits | effective date only | adjustment plumbing | UNSUITABLE for announcement studies |
| Financial reports, income statements | accepted_date with seconds | fundamentals F1–F3 | **SPENT** for those signals |
| Financial reports, balance / cashflow / growth / ratios | point-in-time via accepted_date | none | UNTESTED in the project, but contaminated: their OSAP analogues were already viewed. Survivor-biased |
| Filing *timing* (after-hours, Friday, late) | accepted_date | none | UNTESTED; accepted_date time zone unverified |
| Insider trades (LSE) | 12–18 months, duplicated | SEC Form 4 used instead | UNSUITABLE; Senate subtype is FORWARD-ONLY scale |
| COT | weekly, release_date | cot, crowding | **SPENT** |
| Crypto altcoins (56) | quote/trade bars | BTC/ETH trend only | UNTESTED; survivor-biased |
| Live options chain / flow (2026+) | last-trade IV and greeks | none | FORWARD ONLY |

## Why FX intraday news continuation was chosen

1. **New information.**
   - Point-in-time consensus for inflation releases and central-bank decisions has never been used.
   - Growth-release consensus was used once, at a monthly horizon in country ETFs.
   - The mechanism here (post-announcement price discovery through order flow; Evans and Lyons 2008) and the instrument are both untested.
2. **No survivorship.** Currencies do not delist.
3. **Power.** Roughly 1,000 event-windows a year across six currencies, so a clean result either way is likely. Monthly country or bond signals give 14 or fewer bets a month.
4. **Uses LSE-unique data.** 1-minute FX from 2009 plus the calendar's consensus field.
5. **Tradable at retail cost.** Majors, post-release spreads after 15 minutes; about 1 bp a side assumed, stressed to 3.

The strongest runners-up, kept for later:
- central-bank decision surprises at multi-day horizons (delayed overshooting): genuinely new but only ~90–150 tradable events;
- credit-index risk signals: time series, low breadth;
- cross-country yields for choosing other assets: coverage gaps, and an ambiguous currency sign in USD-priced ETFs.
