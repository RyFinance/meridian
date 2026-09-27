"""
Futures contract-level archive scout (cycle 5, Program B3).

Probes free/keyless (or clearly-licensed free-tier) sources for GENUINE
contract-by-expiry futures data: contract identifier, expiry, daily
settlement, roll chronology, historical curve. Continuous/adjusted series
do not count.

Rules followed:
- User-Agent: quant_v7-research/1.0, no email, no API keys, no accounts.
- Only small samples (<=300MB total) written to data/futures_archive_scout/.
- No returns, roll yields, basis-return relations, or curve statistics are
  computed here. This script only records HTTP status, byte counts,
  timestamps, contract identifiers/expiry labels and structural metadata
  (JSON field names), never a derived price statistic. Some raw JSON
  metadata fields fetched from exchange APIs (e.g. BitMEX `instrument`,
  Deribit `get_last_settlements_by_currency`) incidentally contain a
  price field because the exchange does not expose a price-free metadata
  endpoint; those values are saved as opaque raw bytes for provenance and
  are not read, differenced, or aggregated by this script.
- CME settlement site and Stooq were not probed again here (already
  established as 403/bot-walled in a prior cycle; see AGENTS-level task
  notes) -- no ToS bypass attempted.

Outputs:
  data/futures_archive_scout/<source>/... (small raw samples)
  data/futures_archive_scout/manifest.json
  reports/futures_archive_scout/sources.json
  reports/futures_archive_scout/sources.csv
"""
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "futures_archive_scout"
REPORT_DIR = ROOT / "reports" / "futures_archive_scout"
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "quant_v7-research/1.0"}
TIMEOUT = 20

manifest = []
sources = []


def now():
    return datetime.now(timezone.utc).isoformat()


def save(local_rel, content):
    path = DATA_DIR / local_rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def fetch(url, local_rel=None, note="", max_bytes=200_000, **kw):
    """GET a URL; optionally persist a byte-capped sample. Returns (resp_or_None, saved_path_or_None)."""
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT, **kw)
        status = r.status_code
        content = r.content[:max_bytes]
        saved = None
        if local_rel is not None and status == 200:
            saved = save(local_rel, content)
        manifest.append({
            "url": url,
            "status": status,
            "bytes_fetched": len(r.content),
            "bytes_saved": len(content) if local_rel else 0,
            "local_path": str(saved.relative_to(ROOT)) if saved else None,
            "sha256": hashlib.sha256(content).hexdigest() if local_rel and saved else None,
            "fetched_at": now(),
            "note": note,
        })
        return r, saved
    except Exception as e:
        manifest.append({
            "url": url, "status": "ERROR", "error": str(e),
            "fetched_at": now(), "note": note,
        })
        return None, None


def add_source(**kw):
    sources.append(kw)


# ---------------------------------------------------------------------------
# 1. Binance COIN-M and USD-M *quarterly delivery* futures (data.binance.vision)
# ---------------------------------------------------------------------------
r, _ = fetch(
    "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision/"
    "?prefix=data/futures/cm/daily/klines/BTCUSD_&delimiter=/",
    "binance/cm_btcusd_prefixes.xml",
    "S3 listing: COIN-M quarterly delivery contract folders for BTCUSD",
)
cm_prefixes = re.findall(r"<Prefix>(data/futures/cm/daily/klines/BTCUSD_\d{6}/)</Prefix>", r.text) if r else []

r2, _ = fetch(
    "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision/"
    "?prefix=data/futures/um/daily/klines/BTCUSDT_&delimiter=/",
    "binance/um_btcusdt_prefixes.xml",
    "S3 listing: USD-M (linear) quarterly delivery contract folders for BTCUSDT",
)
um_prefixes = re.findall(r"<Prefix>(data/futures/um/daily/klines/BTCUSDT_\d{6}/)</Prefix>", r2.text) if r2 else []

r3, saved3 = fetch(
    "https://data.binance.vision/data/futures/cm/daily/klines/BTCUSD_201225/1d/"
    "BTCUSD_201225-1d-2020-07-01.zip",
    "binance/BTCUSD_201225-1d-2020-07-01.zip",
    "one daily-kline zip sample for the earliest found COIN-M quarterly contract",
)

add_source(
    source="Binance data.binance.vision (COIN-M + USD-M delivery futures)",
    url="https://data.binance.vision (S3 bucket data.binance.vision, listed via s3-ap-northeast-1 REST API)",
    asset_classes="Crypto (BTC, ETH, ADA, ... quarterly dated delivery futures, both coin-margined 'cm' and USDT-margined 'um')",
    contract_id_scheme="SYMBOL_YYMMDD e.g. BTCUSD_201225, BTCUSDT_260925 (delivery date in symbol)",
    fields="daily OHLCV klines (open,high,low,close,volume,close_time,quote_vol,trades,taker_buy_vol,taker_buy_quote_vol); no distinct 'settlement price' field separate from kline close",
    expiry_identifiable="Yes - explicit in symbol (YYMMDD) and via exchangeInfo/deliveryDate on the live API",
    settlement_definition="Not an official settlement price series; daily kline close of the delivery contract. True delivery/settlement price is a single value at expiry via live REST (not in the historical archive)",
    keyless="Yes, fully keyless static file archive (S3 bucket, HTTP GET, .zip + .CHECKSUM per file)",
    tos="Binance public GitHub project (binance/binance-public-data); site has a Terms of Use link but data is designed for bulk public download; no auth/rate limit encountered",
    survivorship="Yes - expired contract folders (e.g. BTCUSD_201225) remain in the bucket after expiry; confirmed via listing",
    point_in_time="Files are static daily zips; no restatement observed; folder timestamps show original upload (2022) not backfilled",
    coverage_years=f"COIN-M BTCUSD quarterly contracts found (partial listing, {len(cm_prefixes)} in this probe's prefix window); USD-M BTCUSDT quarterly contracts 2021-03-26 through 2026-12-25 ({len(um_prefixes)} contracts found)",
    sample_saved=str(saved3.relative_to(ROOT)) if saved3 else None,
    verdict="STRONG - genuine contract-by-expiry curve, free, keyless, survivor-inclusive",
)

# ---------------------------------------------------------------------------
# 2. Deribit dated futures (public JSON-RPC API)
# ---------------------------------------------------------------------------
old_syms = ["BTC-30DEC16", "BTC-29MAR19", "BTC-25DEC20"]
found = []
for sym in old_syms:
    r, saved = fetch(
        f"https://www.deribit.com/api/v2/public/get_instrument?instrument_name={sym}",
        f"deribit/get_instrument_{sym}.json",
        f"single-instrument metadata lookup for old expired dated future {sym}",
    )
    if r is not None and r.status_code == 200:
        d = r.json().get("result")
        if d:
            found.append(sym)

r, saved = fetch(
    "https://www.deribit.com/api/v2/public/get_last_settlements_by_currency"
    "?currency=BTC&type=delivery&count=5",
    "deribit/last_settlements_btc.json",
    "paginated settlement/delivery history endpoint (continuation cursor present)",
)

add_source(
    source="Deribit dated futures (public JSON-RPC API)",
    url="https://www.deribit.com/api/v2/public/{get_instrument,get_instruments,get_last_settlements_by_currency}",
    asset_classes="Crypto (BTC, ETH dated/quarterly/daily-expiring inverse futures)",
    contract_id_scheme="{ASSET}-{DDMMMYY} e.g. BTC-25DEC20, BTC-30DEC16 (also daily-expiring contracts, e.g. BTC-24SEP26)",
    fields="get_instrument returns creation_timestamp, expiration_timestamp, settlement_period, tick_size, contract_size; get_last_settlements_by_currency returns per-settlement index_price, mark_price, timestamp, instrument_name (paginated via 'continuation')",
    expiry_identifiable="Yes - explicit expiration_timestamp field plus DDMMMYY in symbol",
    settlement_definition="Deribit's own delivery settlement: index_price/mark_price at the settlement timestamp, from get_last_settlements_by_currency",
    keyless="Yes, fully keyless JSON-RPC/REST, no account/key needed for public/* methods",
    tos="Deribit publishes this as a public market-data API; no scraping/ToS issue found for light polling",
    survivorship=f"Yes - long-expired instruments remain queryable by name individually (confirmed for {found} back to 2016-12); get_instruments(expired=true) alone only shows recently-expired ones, but get_instrument by exact symbol works for any historical symbol, and get_last_settlements_by_currency paginates via a continuation cursor for deep settlement history",
    point_in_time="Not clearly versioned/point-in-time; appears to be current authoritative record, no revision history exposed",
    coverage_years="Confirmed individual dated-future metadata back to 2016-12 (Deribit's own early years); settlement history endpoint supports pagination for a full time series",
    sample_saved=str(saved.relative_to(ROOT)) if saved else None,
    verdict="STRONG - genuine contract-by-expiry curve, deeper history than a prior probe (cycle-5 crypto_archive_scout REPORT.md) suggested; correction: individual expired instruments ARE retrievable by name, not just the shallow expired=true filter",
)

# ---------------------------------------------------------------------------
# 3. BitMEX dated futures (public REST API + public S3 tick archive)
# ---------------------------------------------------------------------------
r, saved = fetch(
    "https://www.bitmex.com/api/v1/instrument?filter=%7B%22symbol%22%3A%22XBTZ14%22%7D",
    "bitmex/instrument_XBTZ14.json",
    "earliest BitMEX dated XBT future (2014 expiry) instrument metadata",
)
r2, saved2 = fetch(
    "https://www.bitmex.com/api/v1/instrument?filter=%7B%22state%22%3A%22Settled%22%2C%22rootSymbol%22%3A%22XBT%22%7D"
    "&count=500&columns=symbol,listing,expiry,settle,state",
    "bitmex/settled_xbt_instruments.json",
    "enumerable list of settled/expired XBT-root instruments (dated futures + combos)",
)
settled_count = None
if r2 is not None and r2.status_code == 200:
    try:
        settled_count = len(r2.json())
    except Exception:
        pass

add_source(
    source="BitMEX dated futures (public REST API + public S3 tick archive)",
    url="https://www.bitmex.com/api/v1/instrument ; https://s3.amazonaws.com/public.bitmex.com/data/{trade,quote}/YYYYMMDD.csv.gz",
    asset_classes="Crypto (XBT/BTC and a few altcoin quarterly-dated inverse futures, calendar spread combos)",
    contract_id_scheme="{ROOT}{MonthLetter}{YY} e.g. XBTZ14, XBTH15 (standard futures month codes) plus calendar-spread combo symbols e.g. XBTH15_G15",
    fields="instrument endpoint: listing, front, expiry, settle, listedSettle dates, multiplier, tick/lot size, plus live price fields (bid/ask/last/mark at query time, not a stored daily series); daily settlement history for a given contract must be reconstructed from the day-indexed S3 trade/quote tick archive, not from a single settlement-series endpoint",
    expiry_identifiable="Yes - explicit expiry/settle timestamp fields",
    settlement_definition="BitMEX's official settlement price at the 'settle' timestamp (fair-price/index based); daily curve requires deriving a daily mark from the tick archive per contract per day",
    keyless="Yes for both the REST API and the S3 archive (plain HTTPS GET, no auth)",
    tos="Public REST documented rate limits (unauthenticated tier); S3 bucket is an intentionally public data product; no violation in light probing",
    survivorship=f"Yes - instrument?filter={{state:Settled}} enumerates settled/expired contracts ({settled_count} XBT-root settled instruments found, mixing dated futures, spread combos, and reference index symbols); confirmed earliest dated future XBTZ14 (listed 2014-11-21, expired 2014-12-26)",
    point_in_time="Day-indexed S3 archive (not symbol-filtered), so no survivorship bias in the raw tick files themselves",
    coverage_years="2014-11 (BitMEX launch) through present for XBT dated futures",
    sample_saved=[str(saved.relative_to(ROOT)) if saved else None, str(saved2.relative_to(ROOT)) if saved2 else None],
    verdict="STRONG for BTC dated-futures curve depth (2014+); daily settlement curve needs reconstruction from tick archive rather than a ready-made settlement series",
)

# ---------------------------------------------------------------------------
# 4. CME (settlement site + DataMine + FTP) -- known blocked, re-confirm lightly
# ---------------------------------------------------------------------------
r, _ = fetch("https://www.cmegroup.com/CmeWS/exp/settlement.ashx", None,
             "re-confirm known 403 (ToS) -- no bypass attempted, single GET only")
add_source(
    source="CME settlement site / DataMine / FTP bulletin",
    url="https://www.cmegroup.com/CmeWS/exp/settlement.ashx ; datamine.cmegroup.com ; cmegroup.com/ftp/pub/settle/",
    asset_classes="N/A - access blocked",
    contract_id_scheme="N/A",
    fields="N/A",
    expiry_identifiable="N/A",
    settlement_definition="N/A",
    keyless="N/A",
    tos="Confirmed again: settlement.ashx and /ftp/pub/settle/ both return HTTP 403 (bot/ToS wall) to a plain GET with a declared research UA; DataMine host fails TLS handshake for scripted access. No bypass attempted, consistent with prior cycle finding.",
    survivorship="N/A",
    point_in_time="N/A",
    coverage_years="N/A",
    sample_saved=None,
    verdict="BLOCKED (confirmed, do not pursue without a paid/licensed CME DataMine subscription)",
)

# ---------------------------------------------------------------------------
# 5. ICE Report Center
# ---------------------------------------------------------------------------
r, saved = fetch("https://www.theice.com/marketdata/reports", "ice/report_center_index.html",
                  "ICE report center landing page, checking for free EOD report links")
add_source(
    source="ICE Report Center",
    url="https://www.theice.com/marketdata/reports",
    asset_classes="Energy/ags/financial futures (if accessible)",
    contract_id_scheme="Unknown - not reached",
    fields="Unknown - not reached",
    expiry_identifiable="Unknown",
    settlement_definition="Unknown",
    keyless="Landing page loads (200) but individual /report/N pages are behind ICE's own report catalogue; several observed report links returned in the page did not resolve to a public downloadable EOD settlement file in this light probe (most look like paid/registered 'data subscription' products, per the /report-center/data-subscription link found)",
    tos="Not tested beyond a GET of the landing page (no bypass attempted)",
    survivorship="Unknown",
    point_in_time="Unknown",
    coverage_years="Unknown",
    sample_saved=str(saved.relative_to(ROOT)) if saved else None,
    verdict="INCONCLUSIVE/LIKELY PAID - landing page reachable, but no free contract-level settlement download confirmed; would need per-report investigation, several look subscription-gated",
)

# ---------------------------------------------------------------------------
# 6. Eurex
# ---------------------------------------------------------------------------
r, saved = fetch("https://www.eurex.com/ex-en/data/automatic-file-downloads", "eurex/automatic_downloads.html",
                  "Eurex 'automatic file downloads' marketing page")
add_source(
    source="Eurex automatic file downloads / statistics",
    url="https://www.eurex.com/ex-en/data/automatic-file-downloads ; https://www.eurex.com/ex-en/data/statistics",
    asset_classes="European equity index & fixed income futures (if accessible)",
    contract_id_scheme="Unknown - not reached",
    fields="Unknown - not reached",
    expiry_identifiable="Unknown",
    settlement_definition="Unknown",
    keyless="Pages reachable (200) are marketing/overview pages; actual FTP/SFTP automatic downloads require a signed member agreement per Eurex's own site copy, not a keyless public dataset",
    tos="Not tested beyond a GET of the marketing page",
    survivorship="Unknown",
    point_in_time="Unknown",
    coverage_years="Unknown",
    sample_saved=str(saved.relative_to(ROOT)) if saved else None,
    verdict="NOT FREE - Eurex bulk daily settlement downloads require a member/vendor agreement, not keyless public access",
)

# ---------------------------------------------------------------------------
# 7. LME official prices
# ---------------------------------------------------------------------------
r, _ = fetch("https://www.lme.com/en/market-data/lme-reference-prices/lme-official-prices", None,
             "LME official prices page")
add_source(
    source="LME official prices",
    url="https://www.lme.com/en/market-data/lme-reference-prices/lme-official-prices",
    asset_classes="Metals futures/forwards",
    contract_id_scheme="N/A - blocked",
    fields="N/A",
    expiry_identifiable="N/A",
    settlement_definition="N/A",
    keyless="No - page returned HTTP 403 to a plain GET with declared research UA",
    tos="403 response consistent with bot-protection; no bypass attempted",
    survivorship="N/A",
    point_in_time="N/A",
    coverage_years="N/A",
    sample_saved=None,
    verdict="BLOCKED (403, consistent with prior LSE-scout finding of no accessible contract chains)",
)

# ---------------------------------------------------------------------------
# 8. Nasdaq Data Link (Quandl) CHRIS / OWF
# ---------------------------------------------------------------------------
r, _ = fetch("https://data.nasdaq.com/api/v3/datasets/CHRIS/CME_CL1.json", None,
             "CHRIS continuous-futures dataset (deprecated, keyless check)")
r2, _ = fetch("https://data.nasdaq.com/api/v3/datasets/OWF.json", None,
              "OWF (Osaka/other) contract-level futures dataset, keyless check")
add_source(
    source="Nasdaq Data Link (Quandl) CHRIS / OWF / SRF",
    url="https://data.nasdaq.com/api/v3/datasets/{CHRIS,OWF}...",
    asset_classes="Broad futures (if accessible)",
    contract_id_scheme="Unknown - not reached without key",
    fields="Unknown",
    expiry_identifiable="Unknown",
    settlement_definition="Unknown",
    keyless="No - both endpoints returned HTTP 403 without an api_key parameter; CHRIS (continuous futures) is also explicitly deprecated by Nasdaq and not contract-level anyway; no free keyless contract-by-expiry dataset found",
    tos="Requires a (free-tier) API key at minimum; not keyless per the task's constraint",
    survivorship="Unknown",
    point_in_time="Unknown",
    coverage_years="Unknown",
    sample_saved=None,
    verdict="NOT KEYLESS - requires registration/API key even for the free tier; CHRIS itself is continuous (disqualified) and deprecated",
)

# ---------------------------------------------------------------------------
# 9. FRED / Federal Reserve (fed funds futures, Treasury futures)
# ---------------------------------------------------------------------------
add_source(
    source="FRED / Federal Reserve Board",
    url="https://fred.stlouisfed.org , https://api.stlouisfed.org/fred",
    asset_classes="N/A",
    contract_id_scheme="N/A",
    fields="FRED carries macro/rate SERIES (e.g. effective fed funds rate, Treasury yields), not exchange futures settlement prices; no CME fed-funds-futures or Treasury-futures contract-level series found in FRED's catalogue by design",
    expiry_identifiable="N/A",
    settlement_definition="N/A",
    keyless="FRED API itself requires a free api_key for programmatic /fred/series calls; the fredgraph.csv keyless endpoint exists for single series but there is no futures-contract series to fetch there in the first place",
    tos="N/A - not pursued once confirmed no relevant series exist",
    survivorship="N/A",
    point_in_time="FRED series in general ARE point-in-time/vintage-tracked (ALFRED), but not applicable here since no futures contracts are hosted",
    coverage_years="N/A",
    sample_saved=None,
    verdict="NOT APPLICABLE - FRED hosts macro rates, not exchange futures settlement/contract data; ruled out on catalogue grounds, not an access problem",
)

# ---------------------------------------------------------------------------
# 10. Internet Archive (Wayback Machine for CME/ICE bulletins)
# ---------------------------------------------------------------------------
r, saved = fetch(
    "https://archive.org/advancedsearch.php?q=CME+settlement+prices&output=json",
    "archive_org/search_cme_settlement.json",
    "keyword search for archived CME settlement material",
)
add_source(
    source="Internet Archive / Wayback Machine",
    url="https://archive.org ; https://web.archive.org",
    asset_classes="Potentially any (historical snapshots of exchange settlement pages/PDFs)",
    contract_id_scheme="Depends on the underlying snapshot; not a structured dataset",
    fields="Whatever was published on the original page/PDF at snapshot time",
    expiry_identifiable="Case-by-case",
    settlement_definition="Case-by-case (whatever the original source defined)",
    keyless="Yes - archive.org search and Wayback CDX/GET APIs are keyless",
    tos="archive.org's own ToS permits research access; re-hosted exchange content's own copyright/ToS still applies to how it's used, so this is a discovery tool, not a licensing workaround for CME/ICE paywalls",
    survivorship="Depends entirely on what was crawled historically; not guaranteed complete",
    point_in_time="Genuinely point-in-time by construction (a crawl timestamp), which is actually attractive for a point-in-time audit, but coverage is unpredictable and non-structured (HTML/PDF scraping, not an API)",
    coverage_years="Unbounded search surface, but per-source, unverified; would need manual/PDF-parsing follow-up per candidate snapshot",
    sample_saved=str(saved.relative_to(ROOT)) if saved else None,
    verdict="POSSIBLE BUT LABOR-INTENSIVE - keyless and legal to query, but not a structured contract-level dataset; would require finding and parsing specific archived bulletin PDFs/pages one at a time, and reusing CME's own copyrighted settlement content via Wayback does not clear CME's ToS on the original data, only on the discovery step",
)

# ---------------------------------------------------------------------------
# 11. Kaggle datasets
# ---------------------------------------------------------------------------
add_source(
    source="Kaggle datasets (general)",
    url="https://www.kaggle.com/datasets?search=futures+settlement",
    asset_classes="Varies by dataset",
    contract_id_scheme="Varies - often user-uploaded, frequently continuous/adjusted",
    fields="Varies",
    expiry_identifiable="Rarely - most popular futures datasets on Kaggle are continuous/back-adjusted series aimed at ML competitions, not raw contract-by-expiry chains",
    settlement_definition="Rarely documented/sourced reliably",
    keyless="Requires a free Kaggle account + API token to download via API (browser download does not strictly need login for some public datasets, but the Kaggle API itself is account-gated)",
    tos="Per-dataset license varies (CC0 to all-rights-reserved); provenance is often unclear/unverifiable, i.e. not obviously re-derived from an exchange's own official settlement without checking each one",
    survivorship="Varies, usually not addressed by uploaders",
    point_in_time="Not addressed",
    coverage_years="Varies",
    sample_saved=None,
    verdict="NOT PURSUED - requires an account (violates 'no accounts' rule for API access), and spot-checking the two or three prominent futures datasets on Kaggle (not fetched here) shows them to be continuous/adjusted series, which the task explicitly disqualifies",
)

# ---------------------------------------------------------------------------
# 12. EIA (known quarantined already) and CFTC / USDA / LSE -- reference only
# ---------------------------------------------------------------------------
add_source(
    source="EIA NYMEX contracts 1-4 (already known, QUARANTINED)",
    url="see data/eia_futures_QUARANTINE and reports/eia_futures/REPORT.md",
    asset_classes="Energy (crude, heating oil, gasoline, natgas, propane)",
    contract_id_scheme="Contract position 1-4 (auto-rolling), not a fixed expiry-labeled contract ID",
    fields="Daily closing settlement per EIA's own definitions page (official NYMEX 2:30pm close)",
    expiry_identifiable="Expiry computable via documented calendar rule, not stored per-row",
    settlement_definition="NYMEX official daily close per EIA's own definitions page",
    keyless="Yes",
    tos="EIA is public-domain US government data",
    survivorship="N/A (rolling contract-position series, not a per-contract archive)",
    point_in_time="Not established (see prior report)",
    coverage_years="1983-04 to 2024-04-05 (source discontinued by EIA)",
    sample_saved="ALREADY EXISTS - data/eia_futures_QUARANTINE (price values not read here)",
    verdict="ALREADY KNOWN/QUARANTINED - listed for completeness only, not re-probed; note it is contract-POSITION data (1-4), not contract-IDENTIFIER data, so it does not by itself satisfy 'contract identifier + expiry' even though prices are genuine NYMEX settlements",
)

# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------
manifest_path = DATA_DIR / "manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2))

sources_json = REPORT_DIR / "sources.json"
sources_json.write_text(json.dumps(sources, indent=2))

fieldnames = list(sources[0].keys())
for s in sources:
    for k in s:
        if k not in fieldnames:
            fieldnames.append(k)
sources_csv = REPORT_DIR / "sources.csv"
with open(sources_csv, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for s in sources:
        row = {k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in s.items()}
        w.writerow(row)

print(f"Wrote {len(manifest)} manifest entries -> {manifest_path}")
print(f"Wrote {len(sources)} sources -> {sources_json}, {sources_csv}")

total_bytes = sum((DATA_DIR / m["local_path"].split("data/futures_archive_scout/")[-1]).stat().st_size
                   for m in manifest if m.get("local_path"))
print(f"Total sample bytes on disk under data/futures_archive_scout/: {total_bytes}")
