# Data scout: the cheapest credible data for quant_v7

**Date:** 2026-09-23. **Scope:** individual researcher, ~$100k account, macOS.
**Inputs:**
- `research/RESEARCH_LEDGER_2026-09-23.md`;
- `data/lse_catalog_20260917.json`;
- a small read-only probe of the LSE vault and terminal (about 20 metered calls, at most 5 rows each, 0 bytes billed; see §2);
- vendor pages, all read on 2026-09-23 (see §8).

Nothing was bought, no account or trial was created, and no terms were accepted. The user makes every
purchase. No key or token appears in any file here.

*This report was written by the data-scout agent and saved to disk by the main (director) session,
because the harness blocks subagents from writing report files. The text is unchanged.*

---

## 0. Recommendation

| Rank | Obtain | Cost | Fixes |
|---|---|---|---|
| **1** | **Sharadar Bundle, Full History, personal licence** (sharadar.com) | **$499/yr**, or $69 month-to-month | Survivorship-free US prices from 1998, including ~12k delisted companies. Also: S&P 500 add/remove history; corporate actions and delisting reasons; as-reported fundamentals keyed to the SEC filing date; 13F holdings from 2013; 8-K events. Runs natively on macOS. |
| **2** | **ORATS near-end-of-day backfill, individual licence** | **$599 one-off** (~500 GB); optional $99/mo for forward days | US options from 2007: NBBO bid/ask taken 14 minutes before the close, open interest, volume, greeks and the underlying price at the snapshot. Delisted underlyings are kept. |
| 3 | Free public sets: SEC Financial Statement Data Sets, SEC 13F data sets, FINRA short interest, FINRA Reg SHO short volume, SEC fails-to-deliver | $0 | A second source for fundamentals and 13F; short interest and fails as new information |
| 4 | Reconciliation samples, bought after ranks 1–2 (see §6): three full-market Cboe DataShop EOD days (~$150, third-party price); IVolatility spot checks (~$20); optionally one HistoricalOptionData Level 1 year ($230) | ~$170–$400 | Independent checks on ORATS |
| 5 (runner-up for equities) | Norgate Platinum | $630/yr, plus a Windows VM | Only if Russell 1000/3000 point-in-time membership (from Jul-1990) is needed, or as a second equity vendor. The licence requires deleting the data when the subscription lapses. |

**Core cost:**
- **about $1,100 in year one** (≈1.1% of the account);
- **about $1,300–1,500 including reconciliation**;
- **if you buy only one thing, buy Sharadar**: it attacks the project's largest blocker, and it also carries fundamentals and 13F.

**Skip:**
- **CRSP, Compustat, I/B/E/S, OptionMetrics.** WRDS gives individual accounts only to members of subscribing institutions. No retail route was found. CRSP now belongs to Morningstar (acquisition completed 2026-02-02).
- **QuantConnect bulk data.** About 5× the cost for the same equity coverage, and no index membership.
- **Massive (formerly Polygon.io) or FirstRate for equities.** No index membership, and daily bars can include extended-hours trades, the same flaw as the vault.
- **Databento for now.** Worth it only if intraday NBBO or raw OPRA open interest becomes necessary.
- **EODHD options.** History starts only in Q4-2023.
- **Point-in-time consensus estimates.** No credible retail source was found (Zacks and I/B/E/S history are institutional or quote-on-request).

**What the money buys:**
- correct measurement where the project now has biased measurement;
- two project-unviewed windows:
  - stocks, 1998 to 2003-08, about 5.5 years;
  - options, 2007 to 2014-05, about 7.4 years;
- new information classes: open interest, executable option spreads, 13F holdings, short interest.

It does **not** buy new independent history for any hypothesis already tested (§5).

---

## 1. What the project needs, from the ledger

| Limitation | Ledger rows affected | Data that removes it |
|---|---|---|
| The stock cache holds only today's S&P 500 names. Removed names are missing: 23% of 2019 members, 50% of 2008 members. Survivorship inflated momentum CAGR by about 16 points. | #22–#26 momentum; #18 insider; #19 fundamentals; #30 reversal; PEAD universe | Delisted-inclusive daily prices, point-in-time S&P 500 membership, corporate actions |
| Fundamentals exist for current names only | #19 fundamentals (2015+ validation locked) | Point-in-time fundamentals for dead firms, with filing dates |
| Options are trade prints only: no bid/ask, no open interest; history starts 2014-06 | #6 H1–H4; #7 V1–V3; #8 put-writing | EOD NBBO, open interest, greeks/IV; pre-2014 history |
| No institutional, short or borrow information | none yet (new) | 13F, short interest, fails-to-deliver, borrow fees |

---

## 2. The LSE vault and terminal (probed 2026-09-23)

Probe outputs:
- `reports/data_scout/lse_probe_20260923*.json`, from the vault REST API via `research/data_scout/probe_lse_vault.py`;
- `reports/data_scout/lse_mcp_probe_20260923.json`, from the terminal MCP. Only read-only tools were used, and the paper broker was not touched.

| Question | Answer | Evidence |
|---|---|---|
| Delisted equities? | **No.** | `/candles` returns 404 "no candle data" for SIVB, TWTR, FRC and CELG; the ledger already found ATVI and ANSS missing. `get_history SIVB` gives the same 404, and `search_instruments` returns nothing for SIVB, Activision, Twitter or Bed Bath. The catalog's 127 non-live stocks all stopped trading **after 2026-04-13**, i.e., after the vault's live feed began; nothing delisted earlier exists. |
| Point-in-time index constituents? | **No.** | The vault lists its valid reference datasets: bond_yields, company_profiles, cot, dividends, economic_calendar, financial_reports, insider_trades, stock_fundamentals, stock_splits. There is none for constituents, delistings, open interest, option quotes, short interest or institutional holdings. |
| Historical option bid/ask or open interest? | **No.** | Options exist only as OPRA trade prints since 2014-06-02, one row per contract per day of OHLCV. They are served through `/export` only: 5 jobs an hour, and a job stops silently at 2.5M rows. The `options_chain` reference table (1.60M rows) runs only from **2026-06-11** and holds last-trade IV and greeks. `options_flow` starts 2026-06-26 and `options_flow_1m` 2026-01-02; both are prints. The earliest non-live option underlying ends 2025-12-31. |
| Live options chain via MCP? | **IV and greeks, but no bid/ask and no OI.** | Coordinator probe, SPY 2026-09-25 puts. Fields: ticker, strike, expiry, last_price, volume_today, premium_today, underlying_price, dte, iv, delta, gamma, theta, vega, rho, last_trade_at, updated_at. Rows can be days stale. A call without an expiry returns []. The engine's chain route takes no as-of date. |
| Point-in-time fundamentals? | Current names only. | `financial_reports` carries `accepted_date`, but SIVB and TWTR return 0 rows; `company_profiles` and `stock_fundamentals` are 8,304-row snapshots of today. |
| Corporate actions? | **Dividends do include delisted payers.** | FRC and ATVI rows exist; the earliest FRC row returned is 2018. `stock_splits` has 46.8k rows (delisted coverage not probed). Dividend amounts are not split-adjusted (`data/lse_vault.py`). |
| Daily bars? | UTC calendar-day bars that include extended hours. | Already documented in `data/lse_vault.py`. |
| Provenance (inference, **unverified**) | Probably Massive/Polygon data. | The vault's stock history starts 2003-09-10 and its option prints 2014-06-02, and option tickers use the `O:` OSI prefix. Massive's history also starts on 10 Sep 2003. If so, the vault has *filtered out* delisted names that its upstream holds. |

**Would forward daily collection of the LSE chain support new research?** Only narrowly:
- **What it gives:** a free, forward-only panel of IV and greeks on about 900 underlyings.
- **Why the IV is weak:** it is computed from the *last trade*, so it carries bid-ask bounce and staleness. Rows must be filtered to `last_trade_at` = today with `volume_today` > 0.
- **Usable for:** ATM IV level and term structure, and coarse skew on liquid names (SPY and the top ~100 stocks).
- **Not usable for:**
  - executable prices or transaction costs;
  - anything that needs open interest (positioning, OI change, put/call OI, dealer gamma);
  - out-of-the-money wings and illiquid strikes, where prints are sparse.

For forward option research, ORATS's $99/mo daily file, or extending the existing yfinance recorder (`research/putwrite/record_quotes.py`, which already captures bid, ask, OI and IV), gives strictly more. The LSE chain is best kept as an independent IV cross-check.

---

## 3. Candidates by need

Every row has full columns in `vendor_matrix.csv`:
- coverage and delisted handling;
- point-in-time status and timestamp quality;
- licence, price and API;
- pitfalls, verification status and source URLs.

### 3.1 Survivorship-free US equity prices with membership

| Vendor | Delisted | Point-in-time membership | Price | Deciding issue |
|---|---|---|---|---|
| **Sharadar** | ~12k delisted companies; permaticker; delist reasons in ACTIONS | S&P 500 add/remove table. Sharadar's docs say 1998+, QuantRocket says 1957+; no Russell. | $499/yr | Best value. macOS-native. No CRSP-style delisting return. |
| Norgate Platinum | 25k delisted (1950–2022 count), complete from late 1992 | **S&P 500 from 1957; Russell 1000/2000/3000 from Jul-1990** | $630/yr | Needs Windows. Data must be deleted when the subscription lapses. Fundamentals are current only. |
| EODHD | 26k delisted US tickers, mostly from 2000 | Standard API is thin before ~2012–15 (a 2008 snapshot lists 436 names). S&P Global add-on: $29.99/mo, ≤12 years. | ~$1,000/yr for all-in-one | Membership too short; fundamentals are restated |
| Tiingo | permaTicker | none | $300/yr | No membership |
| Massive | present in daily files; renames stitched by hand | none | $29–$199/mo | Close may include extended-hours trades |
| QuantConnect (AlgoSeek) | yes, 1998+ | none | $2,136 + $600 + tier fee | Cost |
| FirstRate | 7k+ delisted, 2000+ | none | not shown | Extended-hours trades in bars |
| Stooq | no | no | free; API key since Mar-2026 | Survivor-biased |
| CRSP | yes, with delisting returns | yes | institutional only | Not accessible |

### 3.2 Point-in-time fundamentals and estimates

- **Sharadar SF1:**
  - Use only the as-reported dimensions (ARQ/ART/ARY). The MR dimensions are restated and leak lookahead.
  - `datekey` is the 10-K/10-Q *filing date*, with no time of day.
  - This is conservative for signals, but wrong as the event date for earnings-reaction studies: the 8-K earnings release comes first.
- **SEC Financial Statement Data Sets:**
  - Free, 2009-Q1 onward, every XBRL filer including ones later delisted. Small filers join around 2011.
  - They carry filing and acceptance timestamps. The field names `filed`/`accepted` come from memory; check the readme.
  - Main work: CIK→ticker mapping for dead firms (Sharadar's TICKERS table solves it), inconsistent tags, amendments. The SEC disclaims accuracy.
- **Tiingo** (`asReported=true`) is a fallback, but the add-on price is not public.
- **Point-in-time consensus estimates and revisions:**
  - No credible retail source. Zacks history (annual EPS from 1979) is sold through sales or WRDS; I/B/E/S through LSEG or WRDS. S&P Capital IQ runs about $30k+/yr (industry estimate, unverified).
  - Consequence: consensus-based SUE cannot be extended backwards. Time-series SUE (seasonal random walk) from Sharadar or SEC EPS is the only option.

### 3.3 Options with bid/ask and open interest

| Vendor | History | Quote timing | OI / greeks | Delisted underlyings | Price |
|---|---|---|---|---|---|
| **ORATS** | 2007+ | NBBO ~15:46 ET, with stock price at the snapshot | yes / yes (plus smoothed IV) | kept | **$599 one-off**; $99/mo forward |
| HistoricalOptionData (DeltaNeutral) | 2002+ (SPX 1990) | EOD; time **not stated** | L1 has OI; greeks at L2+ | kept | $1,150 (L1), $1,495 (L2), $2,035 (L3); one year L1 $230; no refunds after access |
| Cboe DataShop EOD Summary | 2012+ | NBBO at 15:45 **and** EOD, plus OHLC, VWAP, OI | IV/greeks are a paid add-on | yes | $50 a full-market day (capped $300/mo); $1,500/yr; $7,200 for the archive; $6 per underlying-day; third-party figures, unverified |
| IVolatility | 2005+ | EOD NBBO | yes | not stated | $0.40 per ticker-day. A 100-name, 19-year cross-section would cost ~$190k; fine for spot checks. |
| Databento OPRA | 2013-04+ | CBBO-1m, a minute NBBO | OI in the statistics schema | definitions per day | $199/mo Standard includes 16+ years of L0 and 1 year of L1; older NBBO pay-as-you-go; $125 free credit |
| Massive Options Advanced | trades since 2014; quote depth "5+ yrs" | tick | OI and greeks via snapshots only (history unclear) | — | $199/mo |
| EODHD options | Q4-2023+ | EOD | yes | ? | $29.99/mo |
| OptionMetrics | 1996+ | EOD | yes | yes | institutional only |

### 3.4 Other information that is genuinely new to the project

| Source | Cost | What it would unlock | Caveat |
|---|---|---|---|
| 13F: SEC structured data sets from 2013-07, or Sharadar SF3 | $0 / bundled | Institutional ownership level, change and breadth; crowding at the stock level; ownership of delisted names | 45-day lag, so use the filing date. Values are in $000s through 2022. **OSAP's Breadth/DelBreadth were already viewed in the edge graveyard.** |
| FINRA short interest, twice monthly | $0 | Short-interest level and change, days-to-cover; crowding and short-squeeze risk features | Use the publication date, about 7 business days after settlement. Online grid covers 5 rolling years; listed-name archive depth is unverified. **OSAP ShortInterest and IO_ShortInterest have been viewed.** |
| FINRA Reg SHO daily short volume, 2009-08+ | $0 | Off-exchange short-volume ratio | Not short interest; dominated by market-maker activity; weak prior |
| SEC fails-to-deliver, 2004+ | $0 | Settlement-stress events | Complete only from 2008-09-16 (before that, only balances ≥ 10k shares) |
| Borrow fees | $0, forward only | Short-leg feasibility and costs | No retail history exists. IBKR's FTP file is current-only, so collect daily from now (FORWARD ONLY). Institutional history (S&P/Markit) is out of reach. |
| ETF flows | $0, coarse | Monthly fund flows from N-PORT (2019-10+, public only for each quarter's third month) | Daily creations/redemptions need paid data (ETF Global, Bloomberg; price unverified) or forward scraping of issuer shares-outstanding files. The LETF AUM family is already FORWARD ONLY. |
| Listing events | $0 | Nasdaq Trader symbol directory | Current-only, with no archive; must be collected forward. The Daily List archive from 1999 is a paid product. |

---

## 4. Which ledger families each purchase honestly reopens

Terms used below:
- **Audit** = re-measure an already-classified result with correct data. It may confirm or kill the verdict. It is **not** a new trial and must not be re-specified.
- **Validation** = run a spec frozen before this data arrived.
- **New** = new information, registered before first look.

| # | Family (ledger class) | With Sharadar | With ORATS | Honest status |
|---|---|---|---|---|
| 23 | Momentum verification (infrastructure) | **Completed**: removed names, 23–50% of past members, now have prices | — | Infrastructure |
| 22, 24–26 | Stock momentum variants (SPENT) | Survivorship-free re-measurement | — | **Audit only.** Verdicts can only be confirmed or worsened; no variant may be re-tuned. |
| 19 | Fundamentals F1–F3 (PARTIALLY USED; 2015+ locked) | **Run the locked 2015+ validation on a delisted-inclusive universe, as written** | — | **Validation**, the single cleanest reopening. New fundamental signals (profitability, accruals, asset growth) would be new trials, and their 2015+ OSAP performance is already known. |
| 18 | Insider N1–N4 (SPENT, validation FAIL) | Re-measure on a survivorship-free universe | — | Audit only |
| 1 | PEAD (parameters SPENT) | Survivorship audit of the 2004–2014 pre-registration (already FAIL) | — | Audit. A 1998–2003 extension is unviewed by the project but has low power, no consensus SUE, and literature contamination. Only as a pre-registered confirmation of the *frozen* rule. |
| 30 | Reversal (INCOMPLETE, not a trial) | Can be run once, cleanly, pre-registered | — | New trial on viewed years. Short-term reversal's 2015+ OSAP performance is known. |
| 6, 7 | Options H1–H4, V1–V3 (SPENT, 2014–2026) | — | The frozen specs, quote-based, on **2007-01 → 2014-05** | **Validation on project-unviewed years.** Re-running on 2014–2026 with quotes is a contaminated new trial, not evidence. The literature (OptionMetrics era) has seen 2007–2014. |
| 8 | Put-writing (PARTIALLY USED) | — | Weekly and monthly index puts with real spreads, 2007–2026 | New, but single-series and low-power; CBOE PUT-index literature exists |
| — | New option information (OI, executable spreads) | — | OI change, put/call OI, spread-aware costs for any option strategy | **New.** Register before the first look. The OSAP option predictors (SmileSlope, CPVolSpread, dVolCall, OptionVolume) were already viewed in the edge graveyard. |
| — | New ownership information | 13F (SF3), 8-K events | — | New; OSAP breadth predictors already viewed |
| 12, 29 | LETF, SPMO/GLD (FORWARD ONLY) | no change | no change | Still forward only |

**Measurement upgrades every future study gets:** delisted-inclusive universes, correct index membership, as-reported fundamentals and executable option costs.

---

## 5. What new data cannot fix

1. **Viewed history stays viewed.** Every hypothesis already tested on 2003–2026 stocks or 2014–2026 options keeps its selection bias under better data. A cleaner re-run of a chosen idea on the same months measures that idea more accurately; it does not un-choose it. About 111 trials remain on the books, and any deflated Sharpe must still count them.
2. **Published anomalies.** The edge graveyard has already seen every OSAP predictor's in-sample, pre-publication and post-publication returns. That includes short-interest, 13F-breadth, option-skew, option-volume and analyst-revision predictors. New data on those predictors is contaminated whatever the vendor.
3. **The unviewed windows are short and old.**
   - Stocks, 1998–2003-08: about 5.5 years, dominated by the dot-com cycle.
   - Options, 2007–2014-05: about 7.4 years, dominated by 2008.
   - They suit a one-shot validation of frozen rules. They are too short for discovery.
4. **Regime.** No historical dataset tells whether 2024–26 behaviour persists. Forward paper evidence (PEAD 3 events, SPMO/GLD 0 fills) remains the binding constraint.
5. **Delisting returns.** Sharadar and Norgate give the last traded price, not CRSP's DLRET.
   - Performance delistings (bankruptcy, delisted to OTC) will be biased upward unless a rule is imposed. Shumway (1997) found about −30% for NYSE/AMEX performance delistings (from memory, unverified here).
   - The residual bias must be bounded by sensitivity runs.
6. **Consensus-based SUE before 2015**: unaffordable (§3.2).
7. **Historical borrow costs and short availability**: unavailable at retail, so any short-leg backtest keeps an assumed borrow cost.
8. **Capacity and costs for a $100k account**: unchanged. Option spreads will mostly make things look *worse* than the print-based tests.

---

## 6. Acceptance tests to run before trusting any purchased dataset

Write the results to `reports/data_audit_<vendor>_<date>/`. Freeze a hashed snapshot of the raw download first, and record the licence terms.

### A. Survivorship coverage against index history

1. **Membership count.** Rebuild S&P 500 membership daily from 1998. Expect 500 companies, 500–506 securities. Flag any day outside that range.
2. **Price coverage.** Every member-day needs a price.
   - Gate: ≥ 99.5% of member-days priced overall.
   - **100% for the removed names** the current cache misses (23% of 2019 members, 50% of 2008).
3. **Three-way diff of add/remove dates.** Compare the vendor against `data/survivorship.py` (Wikipedia) and `fja05680/sp500`. Spot-check every disagreement against an S&P DJI announcement. Distinguish the announcement date from the effective date.
4. **Named-case check.** For each name, confirm the vendor has prices up to its final session and its removal from the S&P 500 at the right date:

   | Name | Event | Timing |
   |---|---|---|
   | SIVB | failed bank | halted 2023-03-10 |
   | FRC | failed bank | seized 2023-05-01 |
   | TWTR | cash takeover, $54.20 | closed 2022-10-27 |
   | ATVI | cash takeover, $95.00 | closed 2023-10-13 |
   | CELG | stock, cash and CVR | closed 2019-11-20 |
   | ANSS | cash and stock | closed 2025-07 |

   The deal terms above are from memory; verify them.
5. **Delisted counts by year.** Compare the vendor's delistings per year and reason with Nasdaq/NYSE delisting counts from any public summary. No sudden gaps.

### B. Delisting returns

6. For every delisted member, classify the final event from ACTIONS: acquisition-cash, acquisition-stock, bankruptcy or regulatory.
   - **Cash mergers:** the final close should be within 2% of the deal price.
   - **Stock mergers:** the acquirer leg must be traceable.
7. **Performance delistings.**
   - Check whether any OTC continuation prices exist (SIVBQ, FRCB).
   - Run every backtest three ways: last price; last price −30% for performance delistings; −100% for performance delistings.
   - Report the spread between the three.

### C. Corporate actions

8. **Splits.** Check the vendor's split factor and date for a known list: AAPL 7:1 (2014-06-09) and 4:1 (2020-08-31); TSLA 5:1 (2020-08-31) and 3:1 (2022-08-25); NVDA 4:1 (2021-07-20) and 10:1 (2024-06-10); GOOGL 20:1 (2022-07-18). These dates are from memory; verify them.
9. **Adjusted-close continuity.** The return from the adjusted close must equal (unadjusted close + dividend)/previous unadjusted close within 1 bp on 99.9% of days. Investigate the rest.
10. **Spin-offs.** GEHC (2023-01-04) and GEV (2024-04-02): the parent's adjustment factor must equal the spun value.
11. **Ticker reuse and renames.** FB→META (2022-06-09), plus any recycled symbol: histories must not splice two companies. Key on permaticker, CIK or FIGI, never the ticker.

### D. Timestamps and point-in-time audits

12. **Filing dates.** For 200 random fundamentals rows, compare `datekey` or `filed` with the EDGAR acceptance datetime.
    - Gate: 0 rows usable before acceptance.
    - Acceptances after 17:30 ET usually carry the next business day's filing date; availability must start on the next trading day.
13. **Immutability.** Download the fundamentals twice, ≥ 2 weeks apart. As-reported (AR) history rows must be byte-identical, apart from new filings. Any changed history is a point-in-time failure.
14. **Latency.** Plot filing date minus period end. 10-Q is usually ≤ 45 days, 10-K ≤ 90. Rows *before* the period end are placeholders; drop them, as `research/fundamentals/signals.py` already does.
15. **Options timing.**
    - Confirm the snapshot time (ORATS ~15:46 ET; HistoricalOptionData unstated).
    - Confirm whether OI on day t is t−1's close. OCC reports OI with a one-day lag.
    - The underlying price used must be taken at the snapshot, not the 16:00 close.

### E. Cross-vendor reconciliation samples

16. **Equities.**
    - For survivors, Sharadar `closeunadj` against the project's official-session closes (`yf_2003_2015`, intraday-built session bars). Gate: median absolute difference < 1 bp; below 5 bp on 99% of rows.
    - **Do not** reconcile against the LSE `1d` close; it includes extended hours.
17. **Fundamentals.** Sharadar SF1 against SEC Financial Statement Data Sets for 100 random filings × 5 fields (revenue, net income, EPS diluted, shares, total assets). Gate: ≥ 98% exact or < 0.5% apart.
18. **Options, against the project's own OPRA prints (free).**
    - For the 100 names from 2014–2026, ORATS daily volume against the LSE `options_1d` volume. Expect ≥ 95% of contract-days to agree within 5%.
    - The share of LSE last prints inside ORATS's [bid, ask] should be high. Report it; don't gate on it, because the timing differs.
19. **Options, against an exchange source.** Buy three full-market Cboe DataShop EOD Summary days (e.g., 2012-06-15, 2016-06-15, 2020-06-15; about $150).
    - Compare ORATS's ~15:46 NBBO with Cboe's 15:45 NBBO.
    - Gate: median mid difference ≤ ½ tick on liquid series; OI identical on ≥ 99% of series.
    - A few IVolatility ticker-days ($0.40 each) can cover pre-2012 dates.

### F. Options-specific sanity checks

20. Crossed or locked quotes (bid > ask) should be ≈ 0. Zero-bid share by moneyness should look sensible.
21. **Put-call parity** on European SPX, using the vendor's rate and dividend inputs. Residuals should sit within the spread.
22. **Non-standard deliverables** (adjusted options after splits, special dividends or mergers) must be flagged or excluded.
23. **Chain completeness.** Underlyings and contracts per day should be non-decreasing through time, with no missing trading days. Compare with OCC/OPRA listed-series counts where available.
24. **Delisted underlyings.** Option chains must exist up to each underlying's last trading day (TWTR 2022, ATVI 2023).

### G. Gates and provenance

25. The dataset is **accepted** only if A2, D12, D13, E16 and E17 (equities) or D15, E18 and E19 (options) pass.
26. Record in the audit folder:
    - the licence terms, including what happens on lapse (Norgate: delete);
    - the purchase date and the raw-file hashes.
27. Register any study that uses the data in `research/preregistrations.jsonl` **before** the first look at the new windows (1998–2003, 2007–2014).

---

## 7. Unverified items to confirm before paying

- **Sharadar:**
  - personal-licence terms on cancellation (delete or keep?);
  - S&P 500 table start date (1998 per sharadar.com, 1957 per QuantRocket);
  - SF1 start date (1998 per sharadar.com, 1990 per QuantRocket).
- **ORATS:**
  - whether OI is prior-day;
  - individual-licence redistribution and retention terms.
- **HistoricalOptionData:** snapshot time and licence.
- **Cboe DataShop:** prices come from a third-party review dated 2026-09-13.
- **Norgate:** 6-month prices.
- **FINRA:** start of the listed-stock short-interest archive.
- **FirstRate:** bundle price.
- **Databento:** $/GB for older CBBO-1m; ask their free cost API before subscribing.
- **LSE vault:**
  - the upstream-vendor inference;
  - whether the `options_chain` snapshots can be exported;
  - delisted coverage in `stock_splits`.
- **Memory-sourced facts** (deal terms, split dates, Shumway −30%, SEC `filed`/`accepted` field names): verify during the acceptance tests.

---

## 8. Sources (all accessed 2026-09-23)

**Equities and fundamentals**
- Sharadar: https://sharadar.com/subscribe · https://sharadar.com/fundamentals · https://sharadar.com/prices · https://sharadar.com/docs/sp500 · https://sharadar.com/docs/actions · https://www.quantrocket.com/sharadar/ · https://www.quantrocket.com/pricing/data/sharadar/
- Norgate: https://norgatedata.com/stockmarketpackages.php · https://norgatedata.com/data-content-tables.php · https://norgatedata.com/data-package-faq.php · https://norgatedata.com/faq.php · https://pypi.org/project/norgatedata/
- EODHD: https://eodhd.com/pricing · https://eodhd.com/financial-apis/delisted-stock-companies-data-2 · https://eodhd.com/financial-apis-blog/reworked-sp-500-historical-constituents · https://eodhd.com/lp/spglobal · https://eodhd.com/lp/us-stock-options-api
- Tiingo: https://www.tiingo.com/about/pricing · https://www.tiingo.com/documentation/fundamentals
- Massive: https://massive.com/pricing · https://massive.com/options · https://massive.com/knowledge-base/categories/data-coverage · https://polygon.io/knowledge-base/article/does-polygon-offer-pre-market-and-after-hours-data · https://github.com/shinathan/polygon.io-stock-database
- QuantConnect: https://www.quantconnect.com/docs/v2/lean-cli/datasets/quantconnect/us-equity · https://www.quantconnect.com/data/algoseek-us-equities · https://www.quantconnect.com/data/algoseek-us-equity-options · https://www.quantconnect.com/pricing/
- FirstRate: https://firstratedata.com/stock-data · https://firstratedata.com/cb/1/complete · https://firstratedata.com/bundle/all
- Stooq: https://github.com/pydata/pandas-datareader/issues/1012
- CRSP and WRDS: https://wrds-www.wharton.upenn.edu/pages/about/wrds-account-types/ · https://newsroom.morningstar.com/news/news-details/2026/Morningstar-Completes-Acquisition-of-CRSP-and-Extends-Relationship-with-Vanguard/default.aspx · https://www.crsp.org/research/crsp-us-stock-databases/
- Compustat, Zacks, OptionMetrics: https://costbench.com/software/financial-data-terminals/sp-capital-iq/ · https://zacksdata.com/consensus/faq/ · https://optionmetrics.com/united-states/ · https://wrds-www.wharton.upenn.edu/pages/about/data-vendors/optionmetrics/
- Point-in-time pitfalls (secondary): https://pickuma.com/for-dev/financial-modeling-prep-vs-sharadar-fundamental-data-api/

**Options**
- ORATS: https://orats.com/near-eod-data · https://orats.com/data-api · https://orats.com/university/historical-data
- HistoricalOptionData: https://historicaloptiondata.com/ · https://historicaloptiondata.com/faq/ · https://historicaloptiondata.com/historical-options-prices/
- Cboe DataShop: https://datashop.cboe.com/option-eod-summary · https://stockmarketstack.com/tools/cboe-datashop (third-party prices)
- IVolatility: https://www.ivolatility.com/data-download-intro/
- Databento: https://databento.com/pricing · https://databento.com/blog/introducing-new-opra-pricing-plans · https://databento.com/docs/schemas-and-data-formats/statistics

**Free and public**
- SEC: https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets · https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets · https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data · https://catalog.data.gov/dataset/form-n-port-data-sets
- FINRA: https://www.finra.org/finra-data/browse-catalog/equity-short-interest · https://www.finra.org/sites/default/files/Equity_Short_Interest_Data_File_Download_API.pdf · https://www.finra.org/finra-data/browse-catalog/short-sale-volume-data/daily-short-sale-volume-files · https://developer.finra.org/docs/reg-sho-daily-short-sale-volume
- Nasdaq Trader: https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs · https://www.nasdaqtrader.com/Trader.aspx?id=dailylistpd
- S&P 500 membership: https://github.com/fja05680/sp500 · https://www.spglobal.com/spdji/en/media-center/news-announcements/
- Borrow fees: https://www.iborrowdesk.com/ · https://community.portfolio123.com/t/historical-data-on-ib-short-lending-fee-and-share-availability/58254

**Project data and probes:** `data/lse_catalog_20260917.json` · `reports/data_scout/lse_probe_20260923.json` · `lse_probe_20260923_followup.json` · `lse_probe_20260923_dividends.json` · `lse_mcp_probe_20260923.json`

---

## 9. Files

- `reports/data_scout/REPORT.md`: this file, written to disk by the main session.
- `reports/data_scout/vendor_matrix.csv`: 30 sources × 17 columns, with the access date on every row.
- `reports/data_scout/lse_probe_20260923.json`, `…_followup.json`, `…_dividends.json`: vault probe results.
- `reports/data_scout/lse_mcp_probe_20260923.json`: terminal MCP probe results.
- `research/data_scout/probe_lse_vault.py`: the tiny read-only vault probe.
- `research/data_scout/build_vendor_matrix.py`: generates the CSV.
