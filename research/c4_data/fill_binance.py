"""Robust completion of the Binance USD-M USDT archive: persistent-backoff S3 listing (failures recorded, never
treated as empty), download of every missing zip, and a completeness report.

  PYTHONPATH=. .venv/bin/python -m research.c4_data.fill_binance
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import re
import time
import urllib.request

from research.c4_data.pull import BASE, S3, UA, fetch

OUT = BASE / "binance_um"
MAN = OUT / "manifest.jsonl"


def s3_keys(prefix: str, tries: int = 12) -> list[str] | None:
    keys, marker = [], ""
    while True:
        q = f"{S3}?prefix={prefix}&delimiter=/" + (f"&marker={marker}" if marker else "")
        x = None
        for k in range(tries):
            try:
                with urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=60) as r:
                    x = r.read().decode()
                break
            except Exception:
                time.sleep(min(60, 2 ** k))
        if x is None:
            return None
        keys += re.findall(r"<Key>([^<]+)</Key>", x)
        if "<IsTruncated>true</IsTruncated>" not in x:
            return keys
        marker = keys[-1]


def main():
    syms = [s for s in json.loads((OUT / "symbols_fundingRate.json").read_text()) if s.endswith("USDT")]
    prefixes = [(s, kind, pre) for s in syms for kind, pre in
                (("fundingRate", f"data/futures/um/monthly/fundingRate/{s}/"), ("klines_1d", f"data/futures/um/monthly/klines/{s}/1d/"))]

    def one(t):
        s, kind, pre = t
        ks = s3_keys(pre)
        if ks is None:
            return {"symbol": s, "kind": kind, "status": "LIST_FAILED"}
        remote = [k for k in ks if k.endswith(".zip")]
        miss = [k for k in remote if not (OUT / kind / s / k.split("/")[-1]).exists()]
        got = [fetch(f"https://data.binance.vision/{k}", OUT / kind / s / k.split("/")[-1], MAN) for k in miss]
        return {"symbol": s, "kind": kind, "status": "OK", "remote": len(remote), "missing_before": len(miss),
                "downloaded": sum(g == 200 for g in got), "failed": sum(g != 200 for g in got)}

    with cf.ThreadPoolExecutor(2) as ex:
        res = list(ex.map(one, prefixes))
    for rnd in range(3):
        bad = [i for i, r in enumerate(res) if r["status"] != "OK" or r.get("failed")]
        for i in bad:
            time.sleep(10)
            res[i] = one(prefixes[i])
    summ = {"prefixes": len(res), "list_failed": sum(r["status"] != "OK" for r in res),
            "missing_before": sum(r.get("missing_before", 0) for r in res), "downloaded": sum(r.get("downloaded", 0) for r in res),
            "download_failed": sum(r.get("failed", 0) for r in res),
            "unverified": [f'{r["symbol"]}:{r["kind"]}' for r in res if r["status"] != "OK"]}
    (OUT / "completeness_check.json").write_text(json.dumps({"summary": summ, "rows": res}, indent=1))
    print(json.dumps(summ))


if __name__ == "__main__":
    main()
