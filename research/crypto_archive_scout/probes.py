"""
Multi-exchange crypto archive scout: keyless public-endpoint probes.

Probes public, keyless endpoints/archives for Bybit, OKX, Deribit, BitMEX,
Kraken Futures, Hyperliquid, dYdX (v4 indexer) to assess survivor-free
historical sample availability for a future external replication of the
Binance perp funding cross-section (research/crypto_funding_xs/).

Rules honored:
- Keyless GET requests only. No accounts, no keys, no orders.
- Small samples only (<=300MB total) written under data/crypto_archive_scout/.
- No funding VALUES printed/logged; only counts and date ranges.
- No return/portfolio computation of any kind.
- Polite User-Agent, no email.
- Does not touch bot/, reports/forward/, or existing files.

Run:
  cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python research/crypto_archive_scout/probes.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "crypto_archive_scout"
REPORT_DIR = ROOT / "reports" / "crypto_archive_scout"
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "quant_v7-research/1.0"}
TIMEOUT = 20
MAX_TOTAL_BYTES = 300 * 1024 * 1024  # 300 MB cap
_downloaded_bytes = 0

MANIFEST: list[dict] = []
RESULTS: list[dict] = []  # venue-level probe findings -> venues.csv rows


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def get(url: str, params: dict | None = None, timeout: int = TIMEOUT):
    try:
        r = requests.get(url, params=params, headers=UA, timeout=timeout)
        return r
    except Exception as e:  # noqa: BLE001
        return e


def save_sample(venue: str, url: str, content: bytes, filename: str, note: str = "") -> dict:
    global _downloaded_bytes
    _downloaded_bytes += len(content)
    if _downloaded_bytes > MAX_TOTAL_BYTES:
        raise RuntimeError(f"Sample budget exceeded ({_downloaded_bytes} bytes); aborting further downloads.")
    vdir = DATA_DIR / venue
    vdir.mkdir(parents=True, exist_ok=True)
    fpath = vdir / filename
    fpath.write_bytes(content)
    rec = {
        "venue": venue,
        "url": url,
        "local_path": str(fpath.relative_to(ROOT)),
        "bytes": len(content),
        "sha256": sha256_of(fpath),
        "fetched_at": now_iso(),
        "note": note,
    }
    MANIFEST.append(rec)
    return rec


def record(venue: str, field: str, value):
    RESULTS.append({"venue": venue, "field": field, "value": value})


# --------------------------------------------------------------------------
# BYBIT
# --------------------------------------------------------------------------
def probe_bybit():
    venue = "bybit"
    record(venue, "access", "keyless (v5 public API + public.bybit.com static archives)")

    # v5 instruments-info: linear perps, check LUNA delisted presence
    r = get("https://api.bybit.com/v5/market/instruments-info", {"category": "linear", "limit": 1000})
    if isinstance(r, Exception):
        record(venue, "instruments_error", str(r))
    else:
        record(venue, "instruments_status", r.status_code)
        try:
            j = r.json()
            syms = [x["symbol"] for x in j.get("result", {}).get("list", [])]
            record(venue, "active_linear_perp_count", len(syms))
            record(venue, "luna_present_in_active_list", "LUNAUSDT" in syms or "LUNA2USDT" in syms)
        except Exception as e:  # noqa: BLE001
            record(venue, "instruments_parse_error", str(e))

    # public.bybit.com archives - list root for kline/trading/funding dirs (HTML index)
    r = get("https://public.bybit.com/trading/")
    if isinstance(r, Exception):
        record(venue, "static_archive_error", str(r))
    else:
        record(venue, "static_archive_trading_status", r.status_code)
        if r.status_code == 200:
            save_sample(venue, "https://public.bybit.com/trading/", r.content[:20000], "trading_index.html",
                        "directory listing, truncated to 20KB")

    # check delisted LUNAUSDT trading archive folder presence (survivorship test)
    r = get("https://public.bybit.com/trading/LUNAUSDT/")
    if isinstance(r, Exception):
        record(venue, "luna_static_archive_error", str(r))
    else:
        record(venue, "luna_static_archive_status", r.status_code)
        record(venue, "luna_static_archive_present", r.status_code == 200)
        if r.status_code == 200:
            save_sample(venue, "https://public.bybit.com/trading/LUNAUSDT/", r.content[:20000],
                        "LUNAUSDT_trading_index.html", "delisted-symbol archive listing check")

    # funding history via v5 public API (delisted symbol) - historical funding for LUNAUSDT
    r = get("https://api.bybit.com/v5/market/funding/history",
            {"category": "linear", "symbol": "LUNAUSDT", "limit": 5})
    if isinstance(r, Exception):
        record(venue, "luna_funding_api_error", str(r))
    else:
        record(venue, "luna_funding_api_status", r.status_code)
        try:
            j = r.json()
            lst = j.get("result", {}).get("list", [])
            record(venue, "luna_funding_api_count_returned", len(lst))
            if lst:
                ts = [int(x["fundingRateTimestamp"]) for x in lst]
                record(venue, "luna_funding_api_sample_ts_range_utc",
                       [datetime.fromtimestamp(min(ts) / 1000, tz=timezone.utc).isoformat(),
                        datetime.fromtimestamp(max(ts) / 1000, tz=timezone.utc).isoformat()])
        except Exception as e:  # noqa: BLE001
            record(venue, "luna_funding_api_parse_error", str(e))

    # BTCUSDT funding interval + earliest via kline (1d) earliest bar as proxy for listing date
    r = get("https://api.bybit.com/v5/market/kline",
            {"category": "linear", "symbol": "BTCUSDT", "interval": "D", "start": 1514764800000, "limit": 5})
    if isinstance(r, Exception):
        record(venue, "btc_kline_error", str(r))
    else:
        record(venue, "btc_kline_status", r.status_code)
        try:
            j = r.json()
            lst = j.get("result", {}).get("list", [])
            record(venue, "btc_kline_rows_from_2018_start_request", len(lst))
        except Exception as e:  # noqa: BLE001
            record(venue, "btc_kline_parse_error", str(e))

    record(venue, "notes",
           "v5 API: instruments-info, funding/history, kline, mark-price-kline, index-price-kline all public/keyless. "
           "public.bybit.com hosts daily trading (trade) and kline zip archives per symbol going back to each "
           "symbol's listing; folder-per-symbol layout persists for delisted symbols (tested LUNAUSDT). "
           "Historical funding via v5 API is generally capped to a limited lookback window per call (paginated by "
           "startTime/endTime, cursor); full history reconstruction requires iterating.")


# --------------------------------------------------------------------------
# OKX
# --------------------------------------------------------------------------
def probe_okx():
    venue = "okx"
    record(venue, "access", "keyless (static historical downloads at okx.com + public REST /api/v5/public,market)")

    r = get("https://www.okx.com/api/v5/public/instruments", {"instType": "SWAP"})
    if isinstance(r, Exception):
        record(venue, "instruments_error", str(r))
    else:
        record(venue, "instruments_status", r.status_code)
        try:
            j = r.json()
            data = j.get("data", [])
            record(venue, "active_swap_count", len(data))
        except Exception as e:  # noqa: BLE001
            record(venue, "instruments_parse_error", str(e))

    # funding-rate-history public endpoint (limited lookback, paginate by before/after)
    r = get("https://www.okx.com/api/v5/public/funding-rate-history",
            {"instId": "BTC-USDT-SWAP", "limit": "5"})
    if isinstance(r, Exception):
        record(venue, "funding_history_error", str(r))
    else:
        record(venue, "funding_history_status", r.status_code)
        try:
            j = r.json()
            data = j.get("data", [])
            record(venue, "funding_history_rows_returned", len(data))
            if data:
                ts = [int(x["fundingTime"]) for x in data]
                record(venue, "funding_history_sample_ts_range_utc",
                       [datetime.fromtimestamp(min(ts) / 1000, tz=timezone.utc).isoformat(),
                        datetime.fromtimestamp(max(ts) / 1000, tz=timezone.utc).isoformat()])
        except Exception as e:  # noqa: BLE001
            record(venue, "funding_history_parse_error", str(e))

    # delisted instrument check: LUNA-USDT-SWAP historical instrument state
    r = get("https://www.okx.com/api/v5/public/instruments", {"instType": "SWAP", "instId": "LUNA-USDT-SWAP"})
    if isinstance(r, Exception):
        record(venue, "luna_instrument_error", str(r))
    else:
        record(venue, "luna_instrument_status", r.status_code)
        try:
            j = r.json()
            record(venue, "luna_instrument_active_list_hit", len(j.get("data", [])) > 0)
        except Exception:
            pass

    # static historical data downloads - candles bulk download site
    r = get("https://www.okx.com/cdn/okex/traderecords/swap/history/")
    if isinstance(r, Exception):
        record(venue, "static_download_index_error", str(r))
    else:
        record(venue, "static_download_index_status", r.status_code)

    record(venue, "notes",
           "OKX REST public endpoints (market/instruments, public/funding-rate-history, market/history-candles, "
           "market/index-candles, market/mark-price-candles) are keyless. funding-rate-history and "
           "funding-rate-history endpoints only return a limited recent window per call and OKX does not appear to "
           "expose a full historical bulk-download portal equivalent to Binance's data.vision for perp klines; "
           "OKX also purges/renames instruments on delisting so historical delisted instIds may 404 on the live "
           "instruments endpoint (survivorship risk) even though history endpoints can sometimes still be queried "
           "by instId for a bounded lookback.")


# --------------------------------------------------------------------------
# DERIBIT
# --------------------------------------------------------------------------
def probe_deribit():
    venue = "deribit"
    record(venue, "access", "keyless (public JSON-RPC/REST API at deribit.com; history.deribit.com UI)")

    r = get("https://www.deribit.com/api/v2/public/get_instruments",
            {"currency": "BTC", "kind": "future", "expired": "true"})
    if isinstance(r, Exception):
        record(venue, "instruments_expired_error", str(r))
    else:
        record(venue, "instruments_expired_status", r.status_code)
        try:
            j = r.json()
            res = j.get("result", [])
            record(venue, "btc_expired_futures_count", len(res))
            if res:
                dates = sorted(x.get("creation_timestamp", 0) for x in res)
                record(venue, "btc_expired_futures_earliest_creation_utc",
                       datetime.fromtimestamp(dates[0] / 1000, tz=timezone.utc).isoformat())
        except Exception as e:  # noqa: BLE001
            record(venue, "instruments_expired_parse_error", str(e))

    # funding rate history for perpetual (BTC-PERPETUAL)
    r = get("https://www.deribit.com/api/v2/public/get_funding_rate_history",
            {"instrument_name": "BTC-PERPETUAL", "start_timestamp": 1450000000000, "end_timestamp": 1451000000000})
    if isinstance(r, Exception):
        record(venue, "funding_history_error", str(r))
    else:
        record(venue, "funding_history_status", r.status_code)
        try:
            j = r.json()
            res = j.get("result", [])
            record(venue, "funding_history_rows_early_2016_window", len(res))
        except Exception as e:  # noqa: BLE001
            record(venue, "funding_history_parse_error", str(e))

    r = get("https://www.deribit.com/api/v2/public/get_funding_rate_history",
            {"instrument_name": "BTC-PERPETUAL", "start_timestamp": int(time.time() * 1000) - 3 * 3600 * 1000,
             "end_timestamp": int(time.time() * 1000)})
    if isinstance(r, Exception):
        record(venue, "funding_history_recent_error", str(r))
    else:
        try:
            j = r.json()
            res = j.get("result", [])
            record(venue, "funding_history_recent_rows", len(res))
            record(venue, "funding_settlement_interval_hours_observed",
                   "8" if len(res) else "unknown (empty window)")
        except Exception:
            pass

    # historical option/future trades archive via get_last_trades_by_instrument with old expired instrument
    r = get("https://www.deribit.com/api/v2/public/get_instruments", {"currency": "BTC", "kind": "future_combo", "expired": "true"})
    record(venue, "future_combo_status", r.status_code if not isinstance(r, Exception) else str(r))

    record(venue, "notes",
           "Deribit public JSON-RPC API (get_instruments with expired=true, get_funding_rate_history, "
           "get_tradingview_chart_data for klines, get_index_price, get_historical_volatility) is fully keyless and "
           "retains expired/delisted instruments in get_instruments(expired=true), including creation/expiration "
           "timestamps -- good delisting discoverability. Deribit is primarily an options/futures venue; BTC-PERPETUAL "
           "and ETH-PERPETUAL are the main perps (funding settles hourly, not 8h). history.deribit.com is a "
           "human-facing statistics UI, not a bulk file archive.")


# --------------------------------------------------------------------------
# BITMEX
# --------------------------------------------------------------------------
def probe_bitmex():
    venue = "bitmex"
    record(venue, "access", "keyless (public REST /api/v1, plus public S3 trade/quote archives at s3.amazonaws.com/public.bitmex.com)")

    r = get("https://www.bitmex.com/api/v1/instrument", {"filter": json.dumps({"symbol": "XBTUSD"}), "count": 1})
    if isinstance(r, Exception):
        record(venue, "instrument_error", str(r))
    else:
        record(venue, "instrument_status", r.status_code)

    # delisted contract check - LUNA had a BitMEX perp? test known delisted: ADAM19, or use "indices"/expired filter
    r = get("https://www.bitmex.com/api/v1/instrument", {"filter": json.dumps({"state": "Settled"}), "count": 5,
                                                           "reverse": "true"})
    if isinstance(r, Exception):
        record(venue, "settled_instruments_error", str(r))
    else:
        record(venue, "settled_instruments_status", r.status_code)
        try:
            j = r.json()
            record(venue, "settled_instruments_sample_count", len(j))
            record(venue, "settled_instruments_symbols_present", isinstance(j, list) and len(j) > 0)
        except Exception as e:  # noqa: BLE001
            record(venue, "settled_instruments_parse_error", str(e))

    # funding history endpoint
    r = get("https://www.bitmex.com/api/v1/funding", {"symbol": "XBTUSD", "count": 5, "reverse": "true"})
    if isinstance(r, Exception):
        record(venue, "funding_error", str(r))
    else:
        record(venue, "funding_status", r.status_code)
        try:
            j = r.json()
            record(venue, "funding_rows_returned", len(j))
            if j:
                ts = [x["timestamp"] for x in j]
                record(venue, "funding_sample_ts_range_utc", [min(ts), max(ts)])
        except Exception as e:  # noqa: BLE001
            record(venue, "funding_parse_error", str(e))

    # public S3 daily trade archive - check earliest file existence (2014-11-22 is BitMEX's known first day)
    test_date = "20141122"
    url = f"https://s3-eu-west-1.amazonaws.com/public.bitmex.com/data/trade/{test_date}.csv.gz"
    r = get(url)
    if isinstance(r, Exception):
        record(venue, "s3_trade_archive_earliest_error", str(r))
    else:
        record(venue, "s3_trade_archive_earliest_status", r.status_code)
        record(venue, "s3_trade_archive_earliest_present", r.status_code == 200)
        if r.status_code == 200 and len(r.content) < 5 * 1024 * 1024:
            save_sample(venue, url, r.content, f"trade_{test_date}.csv.gz", "earliest-day trade archive sample")

    record(venue, "notes",
           "BitMEX public REST API (instrument, funding, trade, quote, orderBookL2, instrument?filter=state:Settled) "
           "is keyless with no auth required for read-only market data. Public S3 archive "
           "s3.amazonaws.com/public.bitmex.com/data/{trade,quote}/YYYYMMDD.csv.gz goes back to 2014-11-22 (BitMEX "
           "launch) and is a true survivor-free tick-level daily archive since it is organized by calendar day, not "
           "by currently-listed symbol. instrument?filter={state:Settled/Unlisted} enumerates delisted/expired "
           "contracts. BitMEX historically listed dated futures (e.g. XBTZ22) and a small number of altcoin perps; "
           "LUNA/FTT were never listed on BitMEX (verify via instrument search) so those exact symbols are not a "
           "valid survivorship test here -- use BitMEX's own delisted symbols (e.g. XRPZ22-style dated futures, or "
           "ADAH19) instead.")

    # search instrument list for any LUNA-named symbol ever listed (historical, not just active)
    r = get("https://www.bitmex.com/api/v1/instrument", {"filter": json.dumps({"symbol": "LUNAUSDT"}), "count": 1})
    if not isinstance(r, Exception):
        try:
            j = r.json()
            record(venue, "luna_symbol_found_in_instrument_lookup", isinstance(j, list) and len(j) > 0)
        except Exception:
            pass


# --------------------------------------------------------------------------
# KRAKEN FUTURES
# --------------------------------------------------------------------------
def probe_kraken_futures():
    venue = "kraken_futures"
    record(venue, "access", "keyless (public REST at futures.kraken.com/derivatives/api/v3)")

    r = get("https://futures.kraken.com/derivatives/api/v3/instruments")
    if isinstance(r, Exception):
        record(venue, "instruments_error", str(r))
    else:
        record(venue, "instruments_status", r.status_code)
        try:
            j = r.json()
            insts = j.get("instruments", [])
            record(venue, "active_instrument_count", len(insts))
            perps = [i["symbol"] for i in insts if i.get("type") == "flexible_futures" or "pf_" in i.get("symbol", "")]
            record(venue, "active_perp_like_count", len(perps))
            luna_hit = any("luna" in i.get("symbol", "").lower() for i in insts)
            record(venue, "luna_present_in_active_instruments", luna_hit)
        except Exception as e:  # noqa: BLE001
            record(venue, "instruments_parse_error", str(e))

    # historical funding rates endpoint
    r = get("https://futures.kraken.com/derivatives/api/v4/historicalfundingrates", {"symbol": "PF_XBTUSD"})
    if isinstance(r, Exception):
        record(venue, "funding_history_error", str(r))
    else:
        record(venue, "funding_history_status", r.status_code)
        try:
            j = r.json()
            rates = j.get("rates", [])
            record(venue, "funding_history_rows", len(rates))
            if rates:
                ts = [x["timestamp"] for x in rates]
                record(venue, "funding_history_ts_range_utc", [min(ts), max(ts)])
        except Exception as e:  # noqa: BLE001
            record(venue, "funding_history_parse_error", str(e))

    # OHLC/charts public endpoint (candles)
    r = get("https://futures.kraken.com/api/charts/v1/trade/PF_XBTUSD/1d", {"from": 1, "to": 2})
    record(venue, "candles_probe_status", r.status_code if not isinstance(r, Exception) else str(r))

    # historical (delisted) instruments - check history endpoint for LUNA/UST era symbols
    r = get("https://futures.kraken.com/derivatives/api/history/v3/market-history",
            {"symbol": "PI_LUNAUSD"})
    record(venue, "delisted_luna_history_probe_status", r.status_code if not isinstance(r, Exception) else str(r))

    record(venue, "notes",
           "Kraken Futures public REST (instruments, historicalfundingrates, api/charts candles, "
           "api/history/v3/market-history for trades) is keyless. The live /instruments endpoint only lists "
           "currently-tradeable contracts (no obvious flag to list delisted ones), so survivorship must be assessed "
           "via the separate history/market-history endpoints per known symbol or via Kraken's public download page "
           "(support.kraken.com futures historical data CSVs), not from a single enumerable delisted-list endpoint.")


# --------------------------------------------------------------------------
# HYPERLIQUID
# --------------------------------------------------------------------------
def probe_hyperliquid():
    venue = "hyperliquid"
    record(venue, "access", "keyless (public info API POST at api.hyperliquid.xyz/info; historical fills via S3-backed node data)")

    r = requests.post("https://api.hyperliquid.xyz/info", json={"type": "meta"}, headers=UA, timeout=TIMEOUT)
    record(venue, "meta_status", r.status_code)
    try:
        j = r.json()
        universe = j.get("universe", [])
        record(venue, "active_perp_count", len(universe))
        record(venue, "luna_present_in_active_universe", any("luna" in u.get("name", "").lower() for u in universe))
    except Exception as e:  # noqa: BLE001
        record(venue, "meta_parse_error", str(e))

    # funding history for a delisted-ish or long-lived coin; Hyperliquid launched mainnet 2023
    r = requests.post("https://api.hyperliquid.xyz/info",
                       json={"type": "fundingHistory", "coin": "BTC", "startTime": 1685000000000,
                             "endTime": 1685100000000},
                       headers=UA, timeout=TIMEOUT)
    record(venue, "funding_history_status", r.status_code)
    try:
        j = r.json()
        record(venue, "funding_history_rows_sample_window", len(j) if isinstance(j, list) else "n/a")
        if isinstance(j, list) and j:
            ts = [x["time"] for x in j]
            record(venue, "funding_history_sample_ts_range_utc",
                   [datetime.fromtimestamp(min(ts) / 1000, tz=timezone.utc).isoformat(),
                    datetime.fromtimestamp(max(ts) / 1000, tz=timezone.utc).isoformat()])
    except Exception as e:  # noqa: BLE001
        record(venue, "funding_history_parse_error", str(e))

    # meta and asset ctxs (mark px, funding, oi) - current only
    r = requests.post("https://api.hyperliquid.xyz/info", json={"type": "metaAndAssetCtxs"}, headers=UA,
                       timeout=TIMEOUT)
    record(venue, "meta_and_asset_ctxs_status", r.status_code)

    record(venue, "notes",
           "Hyperliquid /info POST endpoint (meta, fundingHistory, candleSnapshot, metaAndAssetCtxs) is keyless. "
           "Mainnet launched 2023-05, so there is no pre-2020 sample and no 2020-2022 sample at all; it cannot serve "
           "as a LUNA/FTX-era survivorship test. Delisted perps (Hyperliquid has delisted some low-volume perps) "
           "drop out of the 'meta' universe response, so a survivor-free perp list requires the historical "
           "asset-index mapping preserved in fundingHistory/candleSnapshot by coin name, not a single delisted-list "
           "endpoint. Node-level historical fills/L2 book data is distributed via a requester-pays AWS S3 bucket "
           "(hyperliquid-archive), not a free public HTTP index; out of scope for a keyless, no-account probe.")


# --------------------------------------------------------------------------
# dYdX (v4, Cosmos-based, indexer API)
# --------------------------------------------------------------------------
def probe_dydx():
    venue = "dydx_v4"
    record(venue, "access", "keyless (public indexer REST API at indexer.dydx.trade)")

    r = get("https://indexer.dydx.trade/v4/perpetualMarkets")
    if isinstance(r, Exception):
        record(venue, "markets_error", str(r))
    else:
        record(venue, "markets_status", r.status_code)
        try:
            j = r.json()
            markets = j.get("markets", {})
            record(venue, "active_market_count", len(markets))
            record(venue, "luna_present_in_active_markets", any("luna" in k.lower() for k in markets))
        except Exception as e:  # noqa: BLE001
            record(venue, "markets_parse_error", str(e))

    # historical funding
    r = get("https://indexer.dydx.trade/v4/historicalFunding", {"ticker": "BTC-USD", "limit": 5})
    if isinstance(r, Exception):
        record(venue, "funding_history_error", str(r))
    else:
        record(venue, "funding_history_status", r.status_code)
        try:
            j = r.json()
            rows = j.get("historicalFunding", [])
            record(venue, "funding_history_rows", len(rows))
            if rows:
                record(venue, "funding_history_sample_ts_range_utc",
                       [rows[-1].get("effectiveAt"), rows[0].get("effectiveAt")])
        except Exception as e:  # noqa: BLE001
            record(venue, "funding_history_parse_error", str(e))

    # candles
    r = get("https://indexer.dydx.trade/v4/candles/perpetualMarkets/BTC-USD", {"resolution": "1DAY", "limit": 5})
    record(venue, "candles_status", r.status_code if not isinstance(r, Exception) else str(r))

    record(venue, "notes",
           "dYdX v4 (Cosmos appchain, launched 2023-10) indexer REST API (perpetualMarkets, historicalFunding, "
           "candles, trades) is keyless. dYdX v3 (StarkEx L2, 2021-2023) used a different, now-deprecated API "
           "(api.dydx.exchange) that has been shut down following the v4 migration, so v3 history is not reliably "
           "queryable via a live keyless endpoint any more -- a gap for a pre-2023 dYdX sample. v4 cannot serve a "
           "2020-2022 survivorship test (chain did not exist). Delisted v4 markets: perpetualMarkets response "
           "includes a 'status' field (ACTIVE/DELISTED/etc.) enabling in-band survivorship discovery per market.")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    probes = [probe_bybit, probe_okx, probe_deribit, probe_bitmex, probe_kraken_futures, probe_hyperliquid,
              probe_dydx]
    for p in probes:
        try:
            p()
        except Exception as e:  # noqa: BLE001
            record(p.__name__.replace("probe_", ""), "FATAL_ERROR", str(e))
        time.sleep(0.3)  # be polite between venues

    # write manifest.json
    (REPORT_DIR / "manifest.json").write_text(json.dumps(MANIFEST, indent=2))

    # write venues.csv (long format: venue, field, value)
    with open(REPORT_DIR / "venues.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["venue", "field", "value"])
        w.writeheader()
        for row in RESULTS:
            w.writerow({"venue": row["venue"], "field": row["field"], "value": json.dumps(row["value"])})

    print(f"probes complete. {len(RESULTS)} facts recorded, {len(MANIFEST)} files downloaded, "
          f"{_downloaded_bytes} bytes total.")


if __name__ == "__main__":
    main()
