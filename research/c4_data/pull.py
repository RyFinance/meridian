"""Cycle-4 raw data pulls (free, keyless). Downloads only; no returns are computed here.

  PYTHONPATH=. .venv/bin/python -m research.c4_data.pull {finra_daily|finra_si|binance|auctions}

Every file is written under data/c4/<source>/ and logged to data/c4/<source>/manifest.jsonl
(url, http status, bytes, sha256, fetched_at_utc).
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data" / "c4"
UA = {"User-Agent": "quant_v7-research/1.0 (non-commercial research)"}
_lock = threading.Lock()


def fetch(url: str, dest: Path, manifest: Path, retries: int = 3) -> int:
    if dest.exists() and dest.stat().st_size > 0:
        return 200
    for k in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                b = r.read()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b)
            rec = {"url": url, "status": 200, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(),
                   "file": str(dest.relative_to(ROOT)), "fetched_at_utc": dt.datetime.utcnow().isoformat() + "Z"}
            with _lock, manifest.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            return 200
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return e.code
            time.sleep(2 * (k + 1))
        except Exception:
            time.sleep(2 * (k + 1))
    return -1


def weekdays(a: dt.date, b: dt.date):
    d = a
    while d <= b:
        if d.weekday() < 5:
            yield d
        d += dt.timedelta(days=1)


def finra_daily():
    out = BASE / "finra_regsho"
    man = out / "manifest.jsonl"
    days = list(weekdays(dt.date(2018, 8, 1), dt.date(2026, 9, 24)))
    jobs = [(f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{d:%Y%m%d}.txt", out / f"CNMSshvol{d:%Y%m%d}.txt") for d in days]
    with cf.ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda j: fetch(j[0], j[1], man), jobs))
    print("finra_daily", {c: res.count(c) for c in set(res)})


def finra_si():
    out = BASE / "finra_si"
    man = out / "manifest.jsonl"
    days = list(weekdays(dt.date(2018, 1, 1), dt.date(2026, 9, 24)))
    days = [d for d in days if 10 <= d.day <= 17 or d.day >= 24]   # settlement dates cluster mid-month and month-end
    jobs = [(f"https://cdn.finra.org/equity/otcmarket/biweekly/shrt{d:%Y%m%d}.csv", out / f"shrt{d:%Y%m%d}.csv") for d in days]
    with cf.ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda j: fetch(j[0], j[1], man), jobs))
    print("finra_si", {c: res.count(c) for c in set(res)})


S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"


def s3_list(prefix: str, delimiter: bool = True) -> tuple[list[str], list[str]]:
    keys, prefixes, marker = [], [], ""
    while True:
        q = f"{S3}?prefix={prefix}" + ("&delimiter=/" if delimiter else "") + (f"&marker={marker}" if marker else "")
        for k in range(6):
            try:
                with urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=60) as r:
                    x = r.read().decode()
                break
            except Exception:
                time.sleep(3 * (k + 1))
        else:
            raise RuntimeError(f"s3 list failed: {q}")
        keys += re.findall(r"<Key>([^<]+)</Key>", x)
        prefixes += re.findall(r"<Prefix>([^<]+)</Prefix>", x)[1:] if delimiter else []
        if "<IsTruncated>true</IsTruncated>" not in x:
            break
        marker = (keys[-1] if keys else prefixes[-1])
    return keys, prefixes


def binance():
    out = BASE / "binance_um"
    man = out / "manifest.jsonl"
    _, syms = s3_list("data/futures/um/monthly/fundingRate/")
    syms = sorted({p.rstrip("/").split("/")[-1] for p in syms})
    (out).mkdir(parents=True, exist_ok=True)
    (out / "symbols_fundingRate.json").write_text(json.dumps(syms))
    jobs = []
    for s in syms:
        for kind, pre in (("fundingRate", f"data/futures/um/monthly/fundingRate/{s}/"),
                          ("klines_1d", f"data/futures/um/monthly/klines/{s}/1d/")):
            try:
                keys, _ = s3_list(pre)
            except Exception:
                keys = []
            for k in keys:
                if k.endswith(".zip"):
                    jobs.append((f"https://data.binance.vision/{k}", out / kind / s / k.split("/")[-1]))
    print("binance jobs", len(jobs), "symbols", len(syms))
    with cf.ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda j: fetch(j[0], j[1], man), jobs))
    print("binance", {c: res.count(c) for c in set(res)})


def auctions():
    out = BASE / "tsy_auctions"
    man = out / "manifest.jsonl"
    url = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query"
           "?page[size]=10000&page[number]={n}&sort=auction_date")
    n = 1
    while True:
        st = fetch(url.format(n=n), out / f"auctions_query_p{n}.json", man)
        if st != 200:
            print("auctions page", n, st)
            break
        d = json.loads((out / f"auctions_query_p{n}.json").read_text())
        tot = d.get("meta", {}).get("total-pages", 1)
        print("auctions page", n, "of", tot, "rows", len(d.get("data", [])))
        if n >= tot:
            break
        n += 1


if __name__ == "__main__" and sys.argv[1] != "binance_fast":
    {"finra_daily": finra_daily, "finra_si": finra_si, "binance": binance, "auctions": auctions}[sys.argv[1]]()


def binance_fast():
    """Same files as binance(), with the per-symbol S3 listing parallelised."""
    out = BASE / "binance_um"
    man = out / "manifest.jsonl"
    syms = json.loads((out / "symbols_fundingRate.json").read_text())
    syms = [s for s in syms if s.endswith("USDT")]

    def jobs_for(s):
        js = []
        for kind, pre in (("fundingRate", f"data/futures/um/monthly/fundingRate/{s}/"),
                          ("klines_1d", f"data/futures/um/monthly/klines/{s}/1d/")):
            try:
                keys, _ = s3_list(pre)
            except Exception:
                keys = []
            js += [(f"https://data.binance.vision/{k}", out / kind / s / k.split("/")[-1]) for k in keys if k.endswith(".zip")]
        return js

    with cf.ThreadPoolExecutor(12) as ex:
        jobs = [j for js in ex.map(jobs_for, syms) for j in js]
    print("binance_fast jobs", len(jobs), flush=True)
    with cf.ThreadPoolExecutor(12) as ex:
        res = list(ex.map(lambda j: fetch(j[0], j[1], man), jobs))
    print("binance_fast", {c: res.count(c) for c in set(res)}, flush=True)


if __name__ == "__main__" and sys.argv[1] == "binance_fast":
    binance_fast()
