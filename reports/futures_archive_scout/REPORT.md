# Futures Contract-Level Archive Scout — Report (Cycle 5, Program B3)

*Written by the cycle-5 B3 agent. Saved by the director session.*

**Code:** `research/futures_archive_scout/probe.py` (keyless, `User-Agent: quant_v7-research/1.0`, no email/keys/accounts)
**Outputs:** `reports/futures_archive_scout/sources.json`, `reports/futures_archive_scout/sources.csv` (12 sources)
**Samples:** `data/futures_archive_scout/{binance,deribit,bitmex,eurex,ice,archive_org}/` — 13 files, 432 KB total (well under the 300 MB cap), plus `data/futures_archive_scout/manifest.json` (URL, HTTP status, byte counts, SHA-256, timestamp per fetch)
**No returns, roll yields, basis-return relations, or curve statistics were computed** — only HTTP status, contract identifiers/expiry labels, field names, and counts. A few raw JSON metadata blobs incidentally contain a live price field (BitMEX `instrument`, Deribit `get_last_settlements_by_currency`) because those exchanges don't expose a price-free metadata endpoint; those bytes are saved for provenance only, never read/differenced. No existing files edited, no commits/pushes, `bot/` and `reports/forward/` untouched.

## Source table

| Source | Keyless | Expiry ID | Contract chain confirmed | Survivorship | Coverage | Verdict |
|---|---|---|---|---|---|---|
| **Binance data.binance.vision** (COIN-M + USD-M delivery futures) | Yes — static S3 archive | Yes, `SYMBOL_YYMMDD` | BTCUSD_201225 sample downloaded; BTCUSDT quarterly chain 2021-03→2026-12 (24 contracts) enumerated | Yes — expired folders remain | 2020-09→present | **STRONG** |
| **Deribit dated futures** (public JSON-RPC) | Yes | Yes, explicit `expiration_timestamp` + `DDMMMYY` symbol | `get_instrument` confirmed live for BTC-30DEC16, BTC-29MAR19, BTC-25DEC20 | Yes — any historical symbol individually queryable; `get_last_settlements_by_currency` paginates via cursor | 2016-12→present | **STRONG** |
| **BitMEX dated futures** (REST + public S3 tick archive) | Yes | Yes, `listing/front/expiry/settle` fields | XBTZ14 (2014-11 listing, 2014-12 expiry) confirmed; 164 settled XBT-root instruments enumerated | Yes — `state:Settled` filter + day-indexed S3 archive | 2014-11→present | **STRONG** (settlement curve needs reconstruction from tick archive) |
| CME settlement site / DataMine / FTP | No | — | — | — | — | **BLOCKED** (403 confirmed again, no bypass) |
| ICE Report Center | Partially reachable, but reports look subscription-gated | Unknown | Not confirmed | Unknown | Unknown | **INCONCLUSIVE/LIKELY PAID** |
| Eurex automatic downloads | No — requires member agreement | — | — | — | — | **NOT FREE** |
| LME official prices | No — 403 | — | — | — | — | **BLOCKED** |
| Nasdaq Data Link CHRIS/OWF | No — 403 without API key; CHRIS is deprecated + continuous anyway | — | — | — | — | **NOT KEYLESS / DISQUALIFIED** |
| FRED / FRB | N/A | — | Hosts rates, not futures settlement data | — | — | **NOT APPLICABLE** |
| Internet Archive / Wayback | Yes, keyless | Case-by-case | Not a structured dataset | Unpredictable | Unbounded but unverified | **POSSIBLE BUT LABOR-INTENSIVE** |
| Kaggle datasets | Requires account (rule violation) | Rare | Mostly continuous/adjusted | Rarely addressed | Varies | **NOT PURSUED** |
| EIA NYMEX C1–C4 (already known) | Yes | Only via calendar rule, not stored per-row | Contract-**position**, not contract-**identifier** | N/A | 1983–2024-04 | **ALREADY QUARANTINED**, and note it doesn't strictly satisfy "contract identifier" even where genuine |

## Verdict

Yes, quant_v7 can get a genuine free, keyless, contract-by-expiry curve — but **only for crypto dated futures**, not for traditional-asset futures. Every traditional-exchange candidate (CME, LME, Nasdaq Data Link, Eurex, ICE) is either ToS-blocked, paywalled/member-gated, or key-gated. FRED/CFTC don't carry contract-level settlement data at all by design. The Internet Archive is legally usable but yields unstructured, per-snapshot HTML/PDF scraping, not an API — a real option only as a slow, manual follow-up.

**Asset classes and years available:** Bitcoin/Ethereum/altcoin dated and quarterly-delivery futures:
- **BitMEX**: 2014-11 → present (deepest history, inverse contracts, tick-level day-indexed archive)
- **Deribit**: 2016-12 → present (JSON-RPC, both quarterly and newer daily-expiring contracts)
- **Binance**: 2020-09 (COIN-M) / 2021-03 (USD-M) → present (quarterly only, cleanest daily-kline archive)

## Best 2 sources and ingestion plan

**1. Binance data.binance.vision (COIN-M + USD-M delivery futures)** — best balance of cleanliness and ease. Ingestion: enumerate contract folders via the S3 REST listing API (`?prefix=data/futures/{cm,um}/daily/klines/{SYMBOL}_&delimiter=/`), parse the `YYMMDD` expiry directly from the folder name, then bulk-download each contract's `1d` klines zip series (one HTTP GET per contract per day, small files, static and stable — no rate-limit issues observed). Store contract_id, expiry_date, and the OHLCV rows keyed by trade date; this gives a genuine per-contract curve suitable for term-structure/roll-chronology work once explicitly authorized to read price values (currently out of scope here).

**2. Deribit (public JSON-RPC API)** — best for depth (back to 2016) and for a second, structurally-independent product design (inverse, both quarterly and short-dated contracts). Ingestion: use `get_instruments(currency=BTC/ETH, kind=future, expired=true)` for the currently-listing/recently-expired set plus known historical symbol patterns (`{ASSET}-{DDMMMYY}`) for `get_instrument` lookups to backfill older expiries; use `get_last_settlements_by_currency(type=delivery)` with its `continuation` cursor to walk the full settlement history without guessing symbols. This corrects a finding in the earlier `reports/crypto_archive_scout/REPORT.md` (cycle-5 Program B1), which concluded Deribit's expired-instrument retention "looks shallow" based only on the `expired=true` filter — direct `get_instrument` lookups by name show individual contracts remain queryable back to at least 2016-12, and `get_last_settlements_by_currency`'s pagination gives real depth for reconstructing a settlement chronology.

BitMEX is a close third (arguably the single richest history, 2014+), but its 500-instrument REST cap and tick-level (not daily-settlement) S3 archive make it more engineering-intensive than the other two for a first pass; worth adding once the Binance/Deribit pipelines are working.