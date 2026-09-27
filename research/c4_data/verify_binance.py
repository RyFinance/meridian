"""Strict completeness check of the local Binance USD-M archive vs the S3 listing (listing errors raise, never []).

  PYTHONPATH=. .venv/bin/python -m research.c4_data.verify_binance
"""
from __future__ import annotations

import concurrent.futures as cf
import json

from research.c4_data.pull import BASE, s3_list

OUT = BASE / "binance_um"


def main():
    syms = [s for s in json.loads((OUT / "symbols_fundingRate.json").read_text()) if s.endswith("USDT")]

    def check(s):
        rows = []
        for kind, pre in (("fundingRate", f"data/futures/um/monthly/fundingRate/{s}/"),
                          ("klines_1d", f"data/futures/um/monthly/klines/{s}/1d/")):
            keys, _ = s3_list(pre)                       # raises RuntimeError after retries
            remote = {k.split("/")[-1] for k in keys if k.endswith(".zip")}
            local = {p.name for p in (OUT / kind / s).glob("*.zip")}
            rows.append({"symbol": s, "kind": kind, "remote": len(remote), "local": len(local),
                         "missing": sorted(remote - local), "extra": sorted(local - remote)})
        return rows

    def safe(s):
        try:
            return check(s)
        except Exception:
            return None

    with cf.ThreadPoolExecutor(3) as ex:
        out = dict(zip(syms, ex.map(safe, syms)))
    import time
    for rnd in range(4):                                   # serial second passes for throttled listings
        failed = [s for s, v in out.items() if v is None]
        for s in failed:
            time.sleep(2 + 3 * rnd)
            out[s] = safe(s)
    unverified = sorted(s for s, v in out.items() if v is None)
    res = [r for v in out.values() if v for r in v]
    miss = [r for r in res if r["missing"]]
    summary = {"symbols": len(syms), "remote_files": sum(r["remote"] for r in res), "local_files": sum(r["local"] for r in res),
               "rows_with_missing": len(miss), "missing_files": sum(len(r["missing"]) for r in miss),
               "unverified_symbols": unverified}
    (BASE / "binance_um" / "completeness_check.json").write_text(json.dumps({"summary": summary, "missing": miss}, indent=1))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
