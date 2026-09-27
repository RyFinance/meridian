"""Does data.binance.vision keep delisted symbols?  (listing metadata only, no prices read)

Workload C, research cycle 4 (2026-09-24). Uses only the public S3 bucket *listing* of
data.binance.vision (no downloads of price files, no account, no key). Checks:
  1. how many symbols have archived USD-M perpetual funding-rate / kline files, and spot klines;
  2. whether known delisted symbols (LUNA, FTT, SRM, WAVES, ...) are still in the archive, and the
     first/last month for which files exist;
  3. (best effort) the currently-trading USD-M set from the public exchangeInfo endpoint, so the
     archive-minus-live difference estimates how many dead symbols the archive retains.

Output: reports/survivorship_audit/binance_listing.json

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python research/survivorship_audit/binance_listing_check.py
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/survivorship_audit"
OUT.mkdir(parents=True, exist_ok=True)
BUCKET = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
UA = {"User-Agent": "quant_v7 research listing check"}
CALLS = {"n": 0}


def _get(url: str, timeout: int = 30) -> str:
    CALLS["n"] += 1
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def list_prefixes(prefix: str, max_pages: int = 10) -> list[str]:
    """Return child 'directories' under prefix (S3 CommonPrefixes), following pagination."""
    out, marker = [], ""
    for _ in range(max_pages):
        q = {"delimiter": "/", "prefix": prefix}
        if marker:
            q["marker"] = marker
        xml = _get(BUCKET + "?" + urllib.parse.urlencode(q))
        pref = re.findall(r"<CommonPrefixes><Prefix>([^<]+)</Prefix></CommonPrefixes>", xml)
        out += [p[len(prefix):].strip("/") for p in pref]
        trunc = "<IsTruncated>true</IsTruncated>" in xml
        if not trunc:
            break
        nm = re.search(r"<NextMarker>([^<]+)</NextMarker>", xml)
        marker = nm.group(1) if nm else (pref[-1] if pref else "")
        time.sleep(0.2)
    return out


def list_months(prefix: str) -> list[str]:
    xml = _get(BUCKET + "?" + urllib.parse.urlencode({"delimiter": "/", "prefix": prefix}))
    keys = re.findall(r"<Key>([^<]+\.zip)</Key>", xml)
    months = sorted({m for k in keys for m in re.findall(r"(\d{4}-\d{2})\.zip$", k)})
    return months


DELISTED_PROBES = {
    # symbol: (what happened, approx. delisting date) -- from public memory, treated as hypotheses
    "LUNAUSDT": ("Terra collapse", "2022-05"),
    "FTTUSDT": ("FTX collapse; perp delisted", "2022-11"),
    "SRMUSDT": ("Serum, FTX-linked; delisted", "2022-11/2023"),
    "WAVESUSDT": ("delisted from Binance", "2024-06"),
    "BTSUSDT": ("BitShares delisted", "2022/2023"),
    "ANCUSDT": ("Anchor (Terra) delisted", "2022-05"),
    "OMGUSDT": ("delisted", "2024-06"),
    "XEMUSDT": ("NEM delisted", "2024-06"),
    "BZRXUSDT": ("bZx delisted", "2021/2022"),
}


def main() -> None:
    res: dict = {"bucket": BUCKET, "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    um_funding = list_prefixes("data/futures/um/monthly/fundingRate/")
    um_klines = list_prefixes("data/futures/um/monthly/klines/")
    spot_klines = list_prefixes("data/spot/monthly/klines/")
    res["n_symbols"] = {"um_fundingRate": len(um_funding), "um_klines": len(um_klines),
                        "spot_klines": len(spot_klines)}
    res["n_usdt_symbols"] = {"um_fundingRate": sum(s.endswith("USDT") for s in um_funding),
                             "um_klines": sum(s.endswith("USDT") for s in um_klines),
                             "spot_klines": sum(s.endswith("USDT") for s in spot_klines)}

    probes = {}
    for sym, (what, when) in DELISTED_PROBES.items():
        row = {"event": what, "approx_delisting": when,
               "in_um_fundingRate_archive": sym in um_funding,
               "in_um_klines_archive": sym in um_klines,
               "in_spot_klines_archive": sym in spot_klines}
        if row["in_um_fundingRate_archive"]:
            m = list_months(f"data/futures/um/monthly/fundingRate/{sym}/")
            row["um_funding_months"] = [m[0], m[-1], len(m)] if m else []
        if row["in_spot_klines_archive"]:
            m = list_months(f"data/spot/monthly/klines/{sym}/1d/")
            row["spot_1d_months"] = [m[0], m[-1], len(m)] if m else []
        probes[sym] = row
    res["delisted_probes"] = probes

    for sym in ("BTCUSDT", "ETHUSDT"):
        m = list_months(f"data/futures/um/monthly/fundingRate/{sym}/")
        res[f"{sym}_funding_months"] = [m[0], m[-1], len(m)] if m else []

    # other archived datasets that matter for PIT design (existence only)
    res["um_monthly_datasets"] = list_prefixes("data/futures/um/monthly/")
    res["um_daily_datasets"] = list_prefixes("data/futures/um/daily/")

    # Best effort: currently trading USD-M symbols (may be geo-blocked, HTTP 451)
    try:
        info = json.loads(_get("https://fapi.binance.com/fapi/v1/exchangeInfo"))
        live = {s["symbol"] for s in info.get("symbols", [])
                if s.get("status") == "TRADING" and s.get("contractType") == "PERPETUAL"}
        dead = sorted(set(um_funding) - live)
        res["live_perpetual_trading_now"] = len(live)
        res["archived_funding_symbols_not_trading_now"] = len(dead)
        res["share_archive_not_trading_now"] = round(len(dead) / max(1, len(um_funding)), 3)
        res["examples_not_trading_now"] = dead[:60]
    except Exception as e:  # noqa: BLE001
        res["exchangeInfo_error"] = f"{type(e).__name__}: {str(e)[:160]}"

    res["http_calls"] = CALLS["n"]
    (OUT / "binance_listing.json").write_text(json.dumps(res, indent=2))
    print(json.dumps({k: v for k, v in res.items() if k != "examples_not_trading_now"}, indent=1))


if __name__ == "__main__":
    main()
