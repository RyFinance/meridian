"""Forward-only Binance USD-M snapshot collector for research/crypto_funding_xs (see its PLAN.md).

Public, KEYLESS endpoints only (fapi.binance.com: exchangeInfo, fundingRate, klines, premiumIndex).
No account, no order endpoint, no API key is ever touched. Intended run window: about 00:00-00:05
UTC, once per day, matching the frozen rule's "daily rebalance at 00:00 UTC". This module does not
schedule itself and does not touch bot/, launchd or cron -- it is invoked manually or by whatever the
user chooses to wire up later.

Every fetch is written as an immutable, timestamped, content-hashed JSON envelope under
    data/forward_crypto/raw/YYYY-MM-DD/<endpoint>[.<symbol>].<HHMMSS>.<sha256 prefix>.json
and a file is NEVER overwritten (the writer refuses if the exact path already exists; a re-run at a
different second, or with different content, produces a different, additional file). There is no
update-in-place and no backfill path: a day that was not collected stays uncollected.

Geo-blocking: Binance returns HTTP 451 to US IPs for many endpoints. This module treats 451
specially (`GeoBlocked`) and records the finding rather than retrying through a VPN or any other
circumvention -- none is used here or anywhere in this project. If 451 is observed from the
machine that will actually run daily collection, research/forward_crypto/targets.py's docstring
and this project's PLAN discussion describe the data.binance.vision archive fallback (lagged,
prospective-but-delayed) and its implications for the recording window.

    PYTHONPATH=. .venv/bin/python -m research.forward_crypto.collector --probe
    PYTHONPATH=. .venv/bin/python -m research.forward_crypto.collector --collect --limit 15
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "forward_crypto" / "raw"
BASE = "https://fapi.binance.com"
UA = "quant_v7-forward-crypto-research/1 (+keyless, read-only, no VPN)"
TIMEOUT = 15
RETRIES = 3             # transient network / truncated-read retries only; never retries a 451
KLINES_DAYS = 30       # matches core.VOL_LOOKBACK's trailing window (see targets.py)
FUNDING_DAYS = 7        # matches core.SIG_DAYS


class GeoBlocked(RuntimeError):
    """HTTP 451: Binance refuses this location. Never retried with a VPN or any other bypass."""


class CollectorError(RuntimeError):
    pass


def _get(path: str, params: dict | None = None, timeout: float = TIMEOUT, retries: int = RETRIES) -> bytes:
    """requests, not urllib: urllib's chunked-transfer reader was observed to raise IncompleteRead
    intermittently through this environment's egress proxy even though the server sent a complete,
    well-formed response (verified byte-for-byte against curl and requests). requests' urllib3
    backend did not reproduce that truncation in testing; retried here anyway for genuine transience."""
    import requests

    url = f"{BASE}{path}"
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params={k: v for k, v in (params or {}).items() if v is not None},
                                headers={"User-Agent": UA}, timeout=timeout)
        except requests.RequestException as e:
            last_err = e
            time.sleep(0.5 * (attempt + 1))
            continue
        if resp.status_code == 451:
            raise GeoBlocked(f"{path}: HTTP 451 (Binance geo-blocks this location for these endpoints). "
                             "Not circumvented -- no VPN or proxy is used by this collector.")
        if resp.status_code != 200:
            raise CollectorError(f"{path}: HTTP {resp.status_code}: {resp.text[:300]!r}")
        return resp.content
    raise CollectorError(f"{path}: failed after {retries} attempts: {last_err!r}")


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _write_raw(day_dir: Path, name: str, raw: bytes, fetched_at: dt.datetime) -> Path:
    """One immutable snapshot file: an envelope of {endpoint, fetched_at_utc, sha256_of_body, body}.
    Refuses to overwrite an existing path (append-only by construction, not by discipline)."""
    day_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256_bytes(raw)
    fname = f"{name}.{fetched_at.strftime('%H%M%S')}.{digest[:16]}.json"
    path = day_dir / fname
    if path.exists():
        raise CollectorError(f"refusing to overwrite existing snapshot {path}")
    body = json.loads(raw)
    envelope = {"endpoint": name, "fetched_at_utc": fetched_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "sha256_of_raw_body": digest, "body": body}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(envelope, indent=1))
    tmp.rename(path)  # atomic within the same directory; still O_EXCL-checked above
    return path


# -- endpoint fetchers (each returns the written path) ---------------------------------------------

def fetch_exchange_info(day_dir: Path, fetched_at: dt.datetime | None = None) -> tuple[Path, dict]:
    fetched_at = fetched_at or utc_now()
    raw = _get("/fapi/v1/exchangeInfo")
    path = _write_raw(day_dir, "exchangeInfo", raw, fetched_at)
    return path, json.loads(raw)


def fetch_funding_rate(day_dir: Path, symbol: str, fetched_at: dt.datetime | None = None,
                       days: int = FUNDING_DAYS) -> Path:
    fetched_at = fetched_at or utc_now()
    start = int((fetched_at - dt.timedelta(days=days)).timestamp() * 1000)
    raw = _get("/fapi/v1/fundingRate", {"symbol": symbol, "startTime": start, "limit": 1000})
    return _write_raw(day_dir, f"fundingRate.{symbol}", raw, fetched_at)


def fetch_klines(day_dir: Path, symbol: str, fetched_at: dt.datetime | None = None,
                 days: int = KLINES_DAYS) -> Path:
    """1d klines; `limit` gives a few days of slack so the still-forming candle for "today" can be
    dropped downstream (targets.py only uses klines whose open_time < the decision day)."""
    fetched_at = fetched_at or utc_now()
    raw = _get("/fapi/v1/klines", {"symbol": symbol, "interval": "1d", "limit": days + 5})
    return _write_raw(day_dir, f"klines.{symbol}", raw, fetched_at)


def fetch_premium_index(day_dir: Path, symbol: str | None = None, fetched_at: dt.datetime | None = None) -> Path:
    """Fallback for the day's open price if the day's own kline has not yet formed at collection time."""
    fetched_at = fetched_at or utc_now()
    raw = _get("/fapi/v1/premiumIndex", {"symbol": symbol} if symbol else None)
    return _write_raw(day_dir, f"premiumIndex{'.' + symbol if symbol else ''}", raw, fetched_at)


def usdt_perp_symbols(exchange_info: dict) -> list[str]:
    """Every currently-TRADING USDT-margined perpetual. Universe/eligibility filtering (top-100 by
    volume, exclusions, min history) happens downstream in targets.py, which reuses the frozen
    core.py constants -- this just gives the full candidate list plus onboardDate (delistings are
    caught by a symbol dropping off this list on a later day; that is what "prospective" means)."""
    out = []
    for s in exchange_info.get("symbols", []):
        if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING":
            out.append(s["symbol"])
    return sorted(out)


def collect(now: dt.datetime | None = None, limit: int | None = None, sleep_s: float = 0.15,
           out_root: Path = RAW_DIR) -> dict:
    """One snapshot round: exchangeInfo, then per-symbol fundingRate + klines + premiumIndex.

    `limit` caps the symbol list -- use it for smoke tests / to stay rate-limit-friendly; the daily
    production run (not scheduled by this file) would pass `limit=None` for every USDT perp.
    Returns a summary dict; also writes a `_manifest.<HHMMSS>.json` in the day's directory."""
    now = now or utc_now()
    day = now.date().isoformat()
    day_dir = out_root / day
    result = {"fetched_at_utc": now.isoformat(), "day": day, "blocked": False, "block_reason": None,
              "files": [], "symbols": [], "errors": {}}
    try:
        ei_path, ei = fetch_exchange_info(day_dir, now)
    except GeoBlocked as e:
        result["blocked"] = True
        result["block_reason"] = str(e)
        _write_manifest(day_dir, now, result)
        return result
    result["files"].append(str(ei_path.relative_to(ROOT)))
    symbols = usdt_perp_symbols(ei)
    if limit is not None:
        symbols = symbols[:limit]
    result["symbols"] = symbols
    for sym in symbols:
        try:
            for fetcher in (fetch_funding_rate, fetch_klines, fetch_premium_index):
                p = fetcher(day_dir, sym, now)
                result["files"].append(str(p.relative_to(ROOT)))
                time.sleep(sleep_s)
        except GeoBlocked as e:
            result["blocked"] = True
            result["block_reason"] = str(e)
            break
        except CollectorError as e:
            result["errors"][sym] = str(e)
    _write_manifest(day_dir, now, result)
    return result


def _write_manifest(day_dir: Path, now: dt.datetime, result: dict) -> None:
    manifest = {"day": result["day"], "fetched_at_utc": result["fetched_at_utc"], "n_symbols": len(result["symbols"]),
                "n_files": len(result["files"]), "errors": result["errors"], "blocked": result["blocked"],
                "block_reason": result["block_reason"]}
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / f"_manifest.{now.strftime('%H%M%S')}.json").write_text(json.dumps(manifest, indent=1))


def probe(now: dt.datetime | None = None) -> dict:
    """Single keyless call to check reachability/geo-block status without writing a full snapshot."""
    now = now or utc_now()
    try:
        raw = _get("/fapi/v1/exchangeInfo")
        body = json.loads(raw)
        return {"ok": True, "blocked": False, "server_time_ms": body.get("serverTime"),
                "n_symbols_total": len(body.get("symbols", [])), "fetched_at_utc": now.isoformat()}
    except GeoBlocked as e:
        return {"ok": False, "blocked": True, "reason": str(e), "fetched_at_utc": now.isoformat()}
    except CollectorError as e:
        return {"ok": False, "blocked": False, "reason": str(e), "fetched_at_utc": now.isoformat()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe", action="store_true", help="one exchangeInfo call; report reachable/blocked, write nothing")
    ap.add_argument("--collect", action="store_true", help="write a full snapshot round for today (UTC)")
    ap.add_argument("--limit", type=int, default=None, help="cap the symbol list (smoke tests)")
    ap.add_argument("--out", type=Path, default=RAW_DIR)
    args = ap.parse_args(argv)
    if args.probe:
        print(json.dumps(probe(), indent=2))
        return 0
    if args.collect:
        r = collect(limit=args.limit, out_root=args.out)
        print(json.dumps(r, indent=2))
        return 1 if r["blocked"] else 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
