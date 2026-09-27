# Public Market-Structure / Positioning / Crypto Data Scout — Report

*Written by the cycle-4 public-data scout agent (2026-09-24). Saved by the director session.*

Code in `research/public_scout/` (`probes.py`, `build_manifest.py`, `build_outputs.py`), samples in `data/public_scout/` (13 MB, manifest with URL/sha256/fetch-time in `data/public_scout/MANIFEST.json`), outputs in `reports/public_scout/datasets.json` (24 datasets, full detail per the required fields) and `reports/public_scout/ranking.csv`. No returns were computed anywhere; price/kline downloads were used only for coverage and delisted-symbol checks. No existing files were edited; `bot/`, `reports/forward/registry.jsonl`, and the SEC/EDGAR territory were untouched.

## Dataset table (top of ranking.csv; full 24 rows in the CSV)

| Rank | Dataset | Statistical power | Mechanism | PIT | Survivorship | Independent obs | Realism | Independence from prior research |
|---|---|---|---|---|---|---|---|---|
| 1 | FINRA Reg SHO daily short-sale volume | 5 | 3 | 5 | 4 | 5 | 4 | 5 |
| 2 | Binance USD-M perpetual funding rate | 4 | 4 | 5 | 5 | 3 | 5 | 5 |
| 3 | FINRA bi-monthly short interest (bulk CDN file) | 4 | 4 | 5 | 4 | 4 | 4 | 5 |
| 4 | TreasuryDirect auction **results** (bid-to-cover, tail, indirect/direct) | 3 | 4 | 5 | 5 | 3 | 4 | 4 |
| 5 | CFTC Traders in Financial Futures (TFF) | 3 | 3 | 5 | 4 | 3 | 4 | 3 |
| 6-7 | Binance OI/metrics, premium-index klines | 3 | 3 | 4 | 3 | 3 | 4 | 4-5 |
| 8+ | Ken French/AQR, Wikipedia pageviews, legacy/disaggregated/CIT COT, FRED/ALFRED, World Bank, OECD/BIS, Coin Metrics, OKX/Bybit/Deribit, ETF flows, klines-only, USDA/NOAA | 1-3 | — | — | — | — | — | — |
| excluded | MSCI EOD (account-gated), stooq (bot check), CME settlements (ToS-prohibited scraping) | 0 | — | — | — | — | — | — |

## Survivorship verdicts

- **Binance delisted-symbol retention: CONFIRMED POSITIVE.** Live-fetched LUNAUSDT funding-rate files through May 2022 (the collapse, rates to −1.0%/8h) with a clean 404 from June 2022 onward; FTTUSDT and SRMUSDT (FTX-ecosystem) both have funding data through Nov/Dec 2022. Binance's public archive does **not** prune delisted symbols — the opposite of quant_v7's own crypto vault, whose `PLAN_CRYPTO.md` states outright "the vault lists only coins alive today (no LUNA, FTT and so on)." This is the single most useful finding: a free, survivorship-resistant crypto source exists where the project's in-repo one is biased.
- **FINRA symbol coverage vs. free prices:** not survivorship-biased by construction (each day's file lists whatever traded that day; delisted names remain in their historical files). The risk is only in *pairing* — use a point-in-time universe (as `momentum_verification` already built), not the current S&P list.
- Archive-retention boundaries are not product-launch boundaries: Binance USD-M futures data (klines/funding/metrics) only goes back to **January 2020** on `data.binance.vision` even though BTCUSDT perpetuals launched September 2019 — four months are simply not archived at that endpoint.

## Contamination notes (most important corrections to the task's own assumptions)

1. **FINRA Reg SHO history is not 2009.** FINRA states it began publishing short-volume data 2009-11-09, but the actually-fetchable `cdn.finra.org` flat-file archive starts **2018-08-01** (bisected empirically: 2018-07-31 = 403, 2018-08-01 = 200). Anything claiming 2009+ daily short-volume coverage from this endpoint is wrong.
2. **FINRA's own "OTC-only before June 2021" claim is contradicted by the bulk short-interest file.** `shrt{date}.csv` already contains NYSE/NNM/ARCA/AMEX/BZX rows back to at least 2018-01, not just OTC. Likely explanation: pre-2021 exchange self-reported feeds are already folded into this bulk archive even though FINRA's retrospective description says otherwise. Flag for re-verification before trusting pre-2021 exchange-listed coverage for a specific name.
3. **FINRA's keyless `api.finra.org` short-interest query API is stale** (record counts collapse to 0 for every 2023+ settlement date tried) — use the CDN bulk file instead, which is current through 2026-08.
4. **Exchange-listed FINRA short interest via API requires auth** (`consolidatedShortInterest` returned HTTP 401) — not keyless, contrary to the task's premise.
5. **CFTC disaggregated report's 2006-2009 retroactive window** could not be located under the annual-ZIP naming convention (all 404); the report's 2010+ files work fine. Not resolved, flagged rather than assumed unavailable.
6. **stooq**: confirmed JS proof-of-work bot challenge, not bypassed, per instructions.
7. **CME settlements**: explicit 403 stating scripted access violates their Data Terms of Use — no further requests made.
8. **MSCI**: redirects toward a login-gated export tool — not pursued (no accounts).
9. Treasury `bidToCoverRatio` (the auction "surprise" metric) is empty in spot checks through 1998 and reliably populated by 2000 — usable history for a result-surprise signal is ~2000-2026, not the full 1980s+ date history.

## Ranking (top 3 recommended families)

**1. FINRA short-selling pressure (Reg SHO daily short volume + bi-monthly short interest).** Universe: all NMS/OTC symbols in the daily/bi-monthly files, paired with quant_v7's point-in-time equity universe. Timing: daily file same evening (~1-2h after close, confirmed via Last-Modified header); bi-monthly file ~7 business days after each settlement date (confirmed: the 2026-09-15 settlement was still unpublished 7 business days later). Expected effective sample: ~2,000+ trading days since 2018-08 × thousands of names for short volume (daily cadence, high cross-sectional correlation reduces the true independent count materially below the nominal >2M symbol-days/year); ~24 settlement dates/year × thousands of names since ~2018-01 for short interest (coarser cadence, more direct crowding measure). Explicitly flagged as the project's own next-cycle priority and genuinely untested.

**2. Binance perpetual funding-rate crowding/carry.** Universe: liquid USD-M perpetuals (start with the ~30-150 symbols with real volume, not all 952 folders). Timing: funding settles every 8h, final/non-revised. Expected effective sample: ~6.7 years (2020-01 on) × 3 settlements/day × a modest number of *quasi-independent* clusters (majors/L1s/DeFi/memes) — nominal breadth is large but crypto's common-beta correlation caps true independence; confirmed survivorship-resistant, which is the strongest asset it has.

**3. Treasury auction result surprises (bid-to-cover, tail, indirect/direct/primary-dealer share).** Universe: 2/3/5/7/10/20/30-year note and bond auctions, paired with already-in-repo IEF/TLT/SHY. Timing: results published same day, confirmed live (today's 2026-09-24 7-year note auction already showed full results after the 1:00pm ET competitive close). Expected effective sample: ~2000-2026 (bid-to-cover reliably populated) × ~30-36 note auctions/year plus bonds — on the order of 1,000+ events, a real power increase over the already-**SPENT** `auction_cycle` family (Sharpe −0.23/0.03/−0.18), which used only the announced calendar and explicitly never looked at auction outcomes. This is genuinely distinct information on a calendar the project has already spent, exactly as `RESEARCH_DIRECTION_2026-09-23.md` anticipated.

**Deprioritized despite technical novelty:** all CFTC COT variants carry heavy family-fatigue (two prior COT trials both failed: `research/cot` Sharpe 0.25/0.33/0.05 and the crowding-unwind test at 0.09 net); Ken French/AQR are "well-known factors" overlapping the project's already-extensive, SPENT momentum/value work; Wikipedia pageviews has a plausible but well-mined attention mechanism and a real article-continuity survivorship risk around M&A/rebrands.