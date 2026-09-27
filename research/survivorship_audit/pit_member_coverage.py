"""How much of the point-in-time S&P 500 could the repo price if it also used the LSE vault's live stocks?

Workload C, research cycle 4 (2026-09-24). Names and dates only - NO prices or returns are read.
Uses the Wikipedia-ledger membership reconstruction from research/momentum_verification/membership.py
(frozen inputs in reports/momentum_verification_20260919/inputs) and compares, on selected dates:
  - members in the repo price cache (data/multiasset/stocks, today's 503 names)
  - members not in the cache but present as a ticker in the LSE catalog (live or recently delisted stock)
  - members found nowhere (acquired, bankrupt, or renamed - the ticker-change trap)
Output: reports/survivorship_audit/pit_member_coverage.csv (+ uncovered name lists in JSON)

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python research/survivorship_audit/pit_member_coverage.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from research.momentum_verification.membership import members_on, membership

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/survivorship_audit"

# a few well-known renames where the ledger's old ticker differs from today's (illustrative, not exhaustive)
KNOWN_RENAMES = {"FB": "META", "ANTM": "ELV", "FISV": "FI", "RTN": "RTX", "UTX": "RTX", "KORS": "CPRI",
                 "COG": "CTRA", "PKI": "RVTY", "FLT": "CPAY", "BLL": "BALL", "WLTW": "WTW", "ABC": "COR",
                 "HFC": "DINO", "DISCA": "WBD", "CTL": "LUMN", "HCP": "PEAK", "PEAK": "DOC", "VIAC": "PARA",
                 "TWTR": None, "ATVI": None, "SIVB": None, "FRC": None}


def main() -> None:
    snaps = membership()
    cache = {p.stem for p in (ROOT / "data/multiasset/stocks").glob("*.parquet")}
    cat = json.load(open(ROOT / "data/lse_catalog_20260917.json"))
    lse_stocks = {x["symbol"].replace(".", "-").upper() for x in cat if x["dataset"] == "stocks"}
    rows, lists = [], {}
    for d in ["2008-01-02", "2010-01-04", "2013-01-02", "2016-01-04", "2019-01-02", "2022-01-03", "2025-01-02"]:
        m = members_on(snaps, pd.Timestamp(d))
        in_cache = {t for t in m if t in cache}
        rest = m - in_cache
        renamed = {t for t in rest if KNOWN_RENAMES.get(t) in cache}
        in_lse = {t for t in rest - renamed if t in lse_stocks}
        nowhere = rest - renamed - in_lse
        rows.append({"date": d, "members": len(m), "in_repo_cache": len(in_cache),
                     "known_rename_in_cache": len(renamed), "only_in_lse_catalog": len(in_lse),
                     "not_found": len(nowhere),
                     "share_cache": round(len(in_cache) / len(m), 3),
                     "share_cache_plus_renames_plus_lse": round((len(in_cache) + len(renamed) + len(in_lse)) / len(m), 3)})
        lists[d] = {"only_in_lse_catalog": sorted(in_lse), "not_found": sorted(nowhere)}
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "pit_member_coverage.csv", index=False)
    (OUT / "pit_member_uncovered_names.json").write_text(json.dumps(lists, indent=1))
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
