# EIA / Futures Data Specialist — Cycle 4 Report (Workload E)

*Written by the cycle-4 EIA specialist agent (2026-09-24). Saved by the director session. Price values remain QUARANTINED in data/eia_futures_QUARANTINE/: no return, spread or level statistic has been computed. Director's decision is recorded in research/RESEARCH_DIRECTION_2026-09-23.md, Cycle 4.*

## Scope and what I did

Per the CRITICAL NO-CONTAMINATION RULE, I downloaded raw EIA files to quarantine and computed **dates, non-null counts, dtypes, and textual metadata only**. At no point did this script or any exploratory command read, print, plot, or difference a price value, and no contango/backwardation was examined.

- Code: `research/eia_futures/download_and_coverage.py` (new file, `research/eia_futures/` did not exist before)
- Raw quarantined data: `data/eia_futures_QUARANTINE/raw/*.xls` (12 files, 7.8 MB) + `data/eia_futures_QUARANTINE/manifest.json` (URL, fetch time UTC, SHA-256, byte size, HTTP status per file)
- Coverage/metadata outputs: `reports/eia_futures/series_table.json`, `coverage_by_year.json`, `all_contracts_present.json`, `individual_file_crosscheck.json`, `contents_metadata.json`
- No existing file was edited. No commits, no pushes, `bot/` and `reports/forward/registry.jsonl` untouched. All requests used `User-Agent: quant_v7-research/1.0` with no email address, no API key, no account created.

## 1. Series table

Two free, keyless bulk workbooks carry everything needed (each sheet also has a matching single-series `hist_xls` file, which I downloaded separately and cross-checked byte-for-byte on dates/counts — identical):

| Commodity | Delivery point | Sourcekey (C1–C4) | Units | First date (C1) | Last date (all) | N obs (C1) | Discontinuity |
|---|---|---|---|---|---|---|---|
| Crude oil, light-sweet (WTI) | Cushing, OK | RCLC1 / RCLC2 / RCLC3 / RCLC4 | $/barrel | 1983-04-04 (C1); C3 starts 1983-03-30 | **2024-04-05** | 10,183 | None in spec; EIA stopped publishing the whole table after 2024-04-05 |
| Gasoline, conventional/RFG | NY Harbor | EER_EPMR_PE1..4_Y35NY_DPG | $/gal | 1985-01-02 | 2006-12-29 | 4,845 | Retired — NYMEX replaced this contract with RBOB |
| Gasoline, RBOB | NY Harbor | EER_EPMRR_PE1..4_Y35NY_DPG | $/gal | 2005-10-03 | 2024-04-05 | 4,609 | Successor to conventional gasoline; overlap Oct 2005–Dec 2006 |
| No. 2 heating oil | NY Harbor | EER_EPD2F_PE1..4_Y35NY_DPG | $/gal | 1980-01-02 | 2024-04-05 | 9,894 | **Not flagged by EIA.** The NYMEX contract itself was re-specified from #2 heating oil to ULSD around 2013; EIA kept the same sourcekey/description across that change (public CME contract history, not something read from the price values here) |
| Propane | Mont Belvieu, TX | EER_EPLLPA_PE1..4_Y44MB_DPG | $/gal | 1993-12-21 | 2009-09-18 | 3,361 | Discontinued 2009-09-18 |
| Natural gas | Henry Hub | RNGC1 / RNGC2 / RNGC3 / RNGC4 | $/MMBtu | 1993-12-20 (C4) / 1994-01-13 (C1) | 2024-04-05 | 7,496 | None in spec |
| Natural gas spot (not futures) | Henry Hub | RNGWHHD | $/MMBtu | 1997-01-07 | 2026-09-22 (still live) | 5,692 | Separate series; kept for reference only |

**Settlement/source, verbatim from EIA's own definitions page** (`.../TblDefs/pet_pri_fut_tbldef2.asp` and the NG equivalent):
> "The futures prices shown are the official daily closing prices at 2:30 p.m. from the trading floor of the New York Mercantile Exchange (NYMEX)."
> Sources — Petroleum: "Crude oil futures: New York Mercantile Exchange (NYMEX)." Natural gas: "Futures Prices: New York Mercantile Exchange (NYMEX)."

Two corrections to the task brief's assumptions:
- **Source is NYMEX directly**, not "NYMEX via Reuters/Refinitiv" — Refinitiv is cited only for the separate Henry Hub **spot** series, not the futures.
- **The whole table was discontinued on 2024-04-05** ("Futures prices after April 5, 2024, are not available" — EIA's own header text). This is a hard ceiling on the data regardless of window choice.
- **Publication lag**: the workbook itself carries no per-row publish timestamp, so I cannot measure trading-date→publish-date lag from the archive alone. The Contents sheet shows the table's current release cadence as weekly (Release Date 2026-09-23, Next Release Date 2026-09-30). I did not attempt to verify historical lag via Wayback Machine snapshots (out of scope for a dates/counts-only check); this is a genuine gap, not an assumption I'm asserting as fact.

## 2. Expiry mapping (from EIA's own definitions page, calendar rules only)

- **Crude oil (RCLC):** "Contract 1" expires the 3rd business day before the 25th calendar day of the month preceding delivery; if the 25th is a non-business day, trading ends the 3rd business day before the business day preceding the 25th.
- **Natural gas (RNGC):** expires 3 business days before the 1st calendar day of the delivery month.
- **Gasoline / heating oil / propane:** expires the last business day of the month preceding delivery.
- In all cases, "the delivery month for Contract 1 is the calendar month following the trade date," and after a contract expires, "Contract 1 for the remainder of that calendar month is the second following month." In other words, **EIA's contract-position labels (1–4) already auto-roll**: "Contract 1" is defined as whichever delivery month is nearest and unexpired on that date. A held-contract return series can therefore be reconstructed purely from these calendar rules plus the contract-position series, without ever inspecting a price:
  1. Compute each delivery month's expiry date algorithmically from the rules above (pure calendar arithmetic, no data).
  2. Reading "Contract 1" day-over-day already yields a "paper-rolled, zero-slippage" front-month series — the discontinuity from one delivery month to the next occurs invisibly at each expiry.
  3. A deferred-position series (e.g., Contract 4) is constructed the same way from Contract 4's column.
  4. This is the free, zero-cost version of what USL/UNL/USO/UNG try to approximate with real trading and fees. It is **not** itself a tradable series — it has no bid/ask, no volume, no margin data (see §6 limitations).

## 3. Coverage

- **Duplicate dates: zero** in every one of the 25 parsed series (bulk and individual files agree exactly on row counts, first/last dates, and byte-identical structure).
- **Contract-1 coverage is strong and broadly usable** for crude oil (generally >92–97% of that sheet's trading days per year) and natural gas (generally >93–97%).
- **Far-contract (C2–C4) coverage is materially weaker for the refined products and propane.** Per-year non-null ratios for heating oil, propane, and conventional gasoline C2/C3/C4 frequently sit at **65–85%** through the 1990s–2000s (vs. crude oil's high-90s%), and C2–C4 for these three commodities simply do not exist before ~1994 (NYMEX had not yet listed those delivery months). Crude oil is the standout: contracts 1–4 all listed from 1983–1985 with the best fill rate of any commodity here.
- **"All four contracts present on the same date"** (first/last date, count):

| Commodity | All-4-present window | N dates |
|---|---|---|
| Crude oil (WTI) | 1985-01-02 → 2024-04-05 | 9,158 |
| Gasoline, conventional | 1994-01-31 → 2006-09-29 | 1,615 |
| Gasoline, RBOB | 2005-10-03 → 2024-04-05 | 4,547 |
| Heating oil | 1994-02-08 → 2024-04-05 | 5,465 |
| Propane | 1994-04-14 → 2009-09-18 | 2,128 |
| Natural gas | 1994-01-19 → 2024-04-05 | 7,149 |

- Full detail (per-series, per-year non-null counts and duplicate counts) is in `reports/eia_futures/coverage_by_year.json` (746 rows) and `series_table.json`.

## 4. Curve and roll reconstructability — what can and cannot be tested

- Contracts 1–4 span roughly the nearest **~4 delivery months**. USL/UNL (the frozen ETF claim's long leg) hold a **12-month strip** (equal-weighted contracts roughly 1–12 months out). **A 12-month strip cannot be replicated from this data at all** — there is no free EIA series for months 5–12.
- What the 1–4 data *can* test: a genuinely different, narrower economic object — the slope of the very front of the curve (e.g., Contract 1 vs. Contract 4, a ~3–4 month spread) rather than the front-vs-deferred-strip slope the ETF pair tested. This is a distinct hypothesis, not a replication.
- Given the far-contract coverage gaps found in §3, this is realistically only clean for **crude oil** and, with somewhat more caution, **natural gas**. Heating oil/propane/gasoline C2–C4 have too many missing-data stretches pre-2006 to support a reliable daily curve-slope construction without heavy forward-filling assumptions.

## 5. Contamination check

I grepped `research/`, `reports/`, `data/`, and all `.py` files repo-wide for `eia`, `NYMEX`, `RCLC`, `RNGC`, `pet_pri_fut`, `EER_EPD2F`, `dnav/pet`, `dnav/ng`, and for any curve/contract-level commodity data more generally.

- **The only prior mentions of EIA futures anywhere in the repo are two lines in `research/RESEARCH_DIRECTION_2026-09-23.md`** (lines 258 and 284), both describing it as an *unpulled, unverified future data idea* — explicitly noting the commodity_roll family is SPENT and any EIA curve work "must be a new, distinct registration."
- No script, notebook, report, or data file anywhere in the repo has ever fetched, parsed, or referenced these series, RCLC/RNGC/EER_ series IDs, or any other pre-2006 futures-curve source. `data/scout_A/` (from cycle 3) confirms contract-level curves were checked as "unavailable" on yfinance/LSE at the time, and no EIA fallback was ever pulled.
- **Verdict: the sample is genuinely never-viewed by quant_v7.** Nothing in this session computed a return, spread, or price statistic from it either — the quarantine is intact.

## 6. Clean-use design — usable, but only as a new registration, not a replication

**Not a stop, but not a replication either.** The frozen commodity_roll claim (long a 12-month strip / optimum-yield deferred position, short front-month, same commodity) **cannot be exactly reconstructed** from EIA contracts 1–4 — the strip leg has no free source. Any EIA-based test is necessarily a **different construction on a different, narrower slice of the curve**, and per the task brief and `RESEARCH_DIRECTION_2026-09-23.md`, that makes it a **new registered family with its own multiple-testing charge**, not evidence about the ETF result.

Outline for a frozen pre-registration (document only — not written to any PLAN.md here):

- **Universe / disjoint window:** crude oil (RCLC1–4), 1985-01-02 → 2005-12-31 (best coverage, no spec discontinuity); natural gas (RNGC1–4), 1994-01-19 → 2005-12-31. Both windows end strictly before the ETF study's first common date (2006-07-21 for DBC/GSG), so they are disjoint from anything already viewed. I would exclude heating oil/propane/gasoline from the primary test given their far-contract coverage gaps (§3), and treat them at most as a secondary/exploratory arm with that limitation disclosed up front.
- **Construction:** long Contract 4 (or the farthest reliably-covered contract), short Contract 1, same commodity, equal dollar, monthly reset at the first session's close — this mirrors the frozen claim's mechanics but on a ~3-4 month curve slope instead of a 12-month strip. This difference must be stated as the headline limitation, not buried.
- **Costs:** no bid/ask, volume, or margin data exists in this source for the 1980s–2000s NYMEX floor era, so realistic transaction-cost/liquidity assumptions cannot be estimated from EIA data itself. I would recommend deliberately wide, conservative stress costs (and explicit disclosure that the backtest is a research/diagnostic signal test, not a claim of tradability) rather than presenting any specific cost number as verified.
- **Gates:** independent development/validation split within the disjoint window (e.g., development 1985–1996, validation 1997–2005 for crude), matching the project's existing falsification-first structure, with its own bootstrap null and multiple-testing correction — separate from commodity_roll's spent budget.
- **Bias risk to flag for the director explicitly:** the director already knows the 2006–2026 ETF result (dev pass, validation fail). Any discretionary choice in this new design (which contract pair, which window split, which gate) is made with that hindsight, which is exactly the kind of researcher-degrees-of-freedom the project's falsification protocol exists to prevent. I'd recommend the construction rule and gates be frozen by someone/something that commits to them mechanically (e.g., "always contract 1 vs. contract 4, always the two commodities with adequate coverage, always split at the window midpoint") rather than tuned after any peek, and that this new family gets the same independent-audit treatment commodity_roll got.

## 7. Limitations

- Table discontinued 2024-04-05; irrelevant to a pre-2006 design but rules out any use of this specific EIA table for anything current.
- No liquidity/volume/bid-ask data at all — price-only, so realistic cost modeling for a 1980s–2000s NYMEX floor-trading test is not verifiable from this source.
- Far-contract (C2–C4) coverage for heating oil, propane, and gasoline is materially incomplete pre-2006 (often 65–85% fill vs. crude oil's >92%); crude oil is the strongest candidate by a wide margin, natural gas second.
- Heating oil's likely 2013 spec change (#2 heating oil → ULSD) is invisible in EIA's own series metadata — a user has to bring outside knowledge of the NYMEX contract history to know it happened. Irrelevant for a pre-2006 window, but a trap for any later extension of this data past 2013.
- "Official daily closing price... from the trading floor" describes an open-outcry-era methodology; whether that description held unchanged as NYMEX later became electronic-dominant is untested here — again moot for a pre-2006 design.
- Publication lag (trading date → EIA web-publish date) could not be measured from the static archive; I did not chase Wayback Machine snapshots to establish it.