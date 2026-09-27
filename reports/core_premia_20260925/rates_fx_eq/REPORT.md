# Core premia rates, FX and equity data layer

I've built the data layer and audit. By the prereg's mechanical conditions, a free-data universe is feasible for the equity and FX classes; bonds are thin (2 clean passes, 3 minor-defect reviews). I also wasted 54 of the 60 LSE MCP calls: the LSE Terminal app wasn't running, my script had no stop-on-failure check, and every call errored with no data returned. I didn't make any more MCP calls, so the LSE-only data (19 index series, JGB and Bund futures, a fresh pull of the forward points) was not pulled over MCP. Where they exist, I used the LSE vault files already on disk instead. The script now stops if the status call fails.

*Written by the rates/FX/equity data agent (2026-09-26). Saved by the director session.*

Everything is frozen as `core_premia_rates_fx_eq_acq_v1`, manifest SHA-256 `8b5e6205cf5fe8084914913e7d278103c302887d0bf3a44aa6c063452ff67e28` (297 files; `verify` passes against the live files). This is an acquisition snapshot, not the evaluation snapshot: no markets are selected. The selection needs its own dataset version later.

## Sources used
- **Official, keyless:**
  - Fed H.10 (daily FX, 23 currencies from 1971) and H.15 (US Treasury constant-maturity yields, 1M–30Y, from 1962).
  - Bank of England (UK par and zero-coupon 5/10/20y from 1982/1993, Bank Rate, SONIA, a 3M money-market series that ends in 2018).
  - Bundesbank (German par yields 1–30y, daily from 1997-08).
  - Japan MOF (JGB 1–40y from 1974).
  - Bank of Canada (2/5/10/long from 2001; 3M T-bill weekly).
  - Riksbank (Sweden 3M/2/5/10y from 1983–87; STIBOR, which ends in 2020, is kept).
  - Norges Bank (only from 2019).
  - SNB (Swiss yields, monthly, stale after 2025-07).
  - ECB (EUR/USD; euro-area AAA curve 3M/2Y/10Y from 2004).
  - OECD SDMX (monthly long-term, 3M interbank and call-money rates for about 50 areas).
- **Yahoo:** 110 tickers (index levels, country/bond/currency ETFs, CME continuous futures).
- **AQR TSMOM workbook:** frozen; I read only its dates and which class columns are filled (1985-01 to 2026-05). While finding the header row I did see a few rows of its return values; nothing uses them.

## Ranked results
Error is measured on monthly returns as TE/σ, the synthetic's tracking error against a real proxy divided by the proxy's volatility; lower is better. A 120-month floor applies to months after the 756-day warm-up that overlap AQR.

**Government bonds (10y)**

| Rank | Market | Daily from | AQR months after warm-up | Error vs proxy (TE/σ, corr) | Prereg status |
|---|---|---|---|---|---|
| 1 | US (H.15) | 1962 | 497 | 0.13 vs IEF (0.99); 0.16 vs ZN futures, non-roll months | Minor issue: 2 flat 5-day runs (2005, 2006) |
| 2 | UK (BoE par) | 1993 (zero curve from 1982) | 356 | 0.31 vs IGLT (0.95) | Pass |
| 3 | DE (Bundesbank) | 1997 | 310 | 0.37 vs EXHD.DE | Minor issue: 1 flat run; the ETF trades very little on Xetra |
| 4 | JP (MOF) | 1986 | 446 | 0.45 vs 2561.T (only 80 months) | Minor issue: 2 holiday gaps |
| 5 | CA (BoC) | 2001 | 269 | 0.54 vs XGB | Pass |
| 6 | FR | 1995 | 341 | 0.43 vs IBGM (multi-country ETF) | Fail: vendor series, no single-country ETF |
| 7 | IT | 2010 | 163 | 1.17 | Fail |

AU, CH, SE, NO, NZ, ES, the euro-area curve and 8 EM markets fail the prereg's "G7 only" rule; most EM series also have gaps and spikes. The 7y+10y average tracks IEF with TE/σ 0.13, and 20y+30y tracks TLT at 0.12.

**FX (H.10 spot plus short-rate differential)**

| Rank | Currency | Error (TE/σ) | Reference |
|---|---|---|---|
| 1 | JPY | 0.10 | FXY |
| 2 | EUR | 0.10 | 6E futures, non-roll months |
| 3 | AUD | 0.11 | 6A |
| 4 | CAD | 0.11 | 6C |
| 5 | NOK | 0.11 | LSE forward points |
| 6 | SEK | 0.11 | LSE forward points |
| 7 | CHF | 0.12 | 6S |
| 8 | GBP | 0.15 | FXB |
| 9 | NZD | 0.08 / 0.22 | forwards / futures |
| 10 | MXN | 0.20 | 6M (not G10) |

All 9 G10 currencies have at least 293 months after warm-up. Eight pass every condition; NZD is under review only because of its genuine 1984 devaluation and 5% of days without a rate differential. Against the LSE 1-week forward points, the rate-differential input is off by 0.16–0.47 percentage points a year on average (JPY worst, +0.45pp bias).

**Equity (country ETF against price index + estimated dividends, converted to USD)**

| Rank | Market | Error (TE/σ) |
|---|---|---|
| 1–4 | US S&P 500 / Dow / Russell / Nasdaq | 0.06 (S&P vs its total-return index 0.012; vs ES futures, non-roll months, 0.03) |
| 5 | DE | 0.15 |
| 6–8 | MX / FR / ES | 0.17–0.19 |
| 9–13 | BR, NZ, IT, CA, AT | 0.19–0.20 |
| 14–16 | KR, UK, CH | 0.22–0.24 |
| 17–19 | AU, SE, BE | 0.24–0.27 |
| 20–21 | IN, NL | 0.28 |
| 22 | TW | 0.30 |
| 23 | SG | 0.32 |
| 24–25 | HK, JP | 0.43–0.46 (JP vs Nikkei futures 0.23) |
| 26 | MY | 0.60 |
| 27 | CN | 0.84 (FXI holds H-shares, not the Shanghai index) |

Nineteen markets pass as provisional candidates. These fail the $5M daily-volume floor: ES, NL, SE, BE, AT, MY, TR, IL, NZ, ZA, DK, NO, PL.

**Carry inputs (daily curves with at least 2 tenors):**
- **Yes:** US, DE, JP, UK, CA, SE, euro-area AAA, and EM 2y/1y+10y from the LSE vault.
- **Norway:** only from 2019.
- **Only one daily tenor held locally:** FR, IT, ES, NZ (LSE has more, but it wasn't pulled).
- **Switzerland:** monthly and stale.
- **No daily 3M rate:** JP, AU. OECD monthly averages, lagged one month, fill in.

## What free data can't support
- **Contract-level futures or forwards** for rates, FX or equity indices. The Yahoo futures are one spliced front-month series with unadjusted roll jumps, so they serve only as overlap checks.
- **Daily FX before 1999 for euro-legacy currencies** (DEM, FRF, ITL and others). FRED is unreachable and H.10 doesn't carry them.
- **Any vintage or revision history.** ALFRED is unreachable. OECD rates are monthly averages, not month-end values, and get revised.
- **Daily yields before 1997 for DE, before 2001 for CA, and before 2010 for IT.** Only monthly OECD averages exist, which can't feed the daily volatility estimate.
- **Local-currency index total returns outside the US and DAX.** Dividends are estimated from ETF distributions. Country ETFs are unhedged USD and track MSCI indices, so their FX exposure differs from what AQR's futures carry.
- **Local cash rates for HKD, SGD, TWD, MYR, THB and LKR.** No excess return can be built in local currency.
- **Reliable LSE daily FX closes.** The existing LSE spot files have spurious prints of 15–31% daily moves in G10 pairs (USDCAD +31% on 2024-12-20), and the 1-week forward points spike.
- **Liquid single-country bond ETFs for FR, IT, ES, SE, NO, NZ.** The Xetra-listed German ETFs trade too thinly.
- **Blocked sources:** FRED, ALFRED and RBA time out; RBNZ returns 403; Stooq has a bot check, which I didn't bypass; MSCI requires a login.
- **The existing LSE vault files record no vendor retrieval time,** so they fail the "known before the next session" condition.

Nothing was committed or pushed, and bot/, reports/forward/, cron and launchd were not touched.

Files are in `/Users/rytty/CCP/quant_v7/`:
- Code: `research/core_premia_data/rates_fx_eq/` (acquisition modules, `build_tables.py`, `synthetic.py`, `audit.py`, `snapshot.py`)
- Data: `data/core_premia/rates_fx_eq/` (`raw`, `processed`, `synthetic`, `meta`)
- Snapshot store: `data/core_premia/snapshot_store_rates_fx_eq`
- Reports: `reports/core_premia_20260925/rates_fx_eq/`
  - `completeness.json`
  - `synthetic_error.csv`
  - `universe.csv` / `universe.json`
  - `carry_input_error_fx_forward_points.csv`
  - `dq_events.csv`
  - `summary.json`
  - `snapshot_freeze.json`