"""Coverage-only survivorship audit of the repo's equity/crypto price caches.

Workload C, research cycle 4 (2026-09-24). NO RETURN LOOKING: this script reads only
dates, row counts, ticker lists and catalog metadata. It never computes a return, a signal
or any signal->return relationship.

Outputs (reports/survivorship_audit/):
  stock_coverage.json          - per-cache name counts, first/last dates, first-date histogram
  sp500_removal_reasons.csv    - S&P 500 removals by year and coarse reason (metadata only)
  pit_coverage_by_year.csv     - point-in-time S&P 500 members priced by the cache, by year

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python research/survivorship_audit/stock_coverage.py
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/survivorship_audit"
OUT.mkdir(parents=True, exist_ok=True)


def _dates_of(path: Path) -> pd.Series:
    d = pd.read_parquet(path, columns=None)
    for col in ("date", "timestamp", "Date", "time", "ts"):
        if col in d.columns:
            return pd.to_datetime(d[col], utc=True, errors="coerce").dropna()
    if isinstance(d.index, pd.DatetimeIndex):
        return pd.Series(d.index)
    raise ValueError(f"no date column in {path}")


def cache_summary(folder: Path) -> dict:
    files = sorted(folder.glob("*.parquet"))
    rows = []
    for p in files:
        try:
            dt = _dates_of(p)
        except Exception as e:  # noqa: BLE001 - record and continue
            rows.append({"ticker": p.stem, "error": str(e)[:120]})
            continue
        if len(dt) == 0:
            rows.append({"ticker": p.stem, "n": 0})
            continue
        rows.append({"ticker": p.stem, "n": int(len(dt)),
                     "first": dt.min().date().isoformat(), "last": dt.max().date().isoformat()})
    df = pd.DataFrame(rows)
    ok = df.dropna(subset=["first"]) if "first" in df else df.iloc[0:0]
    first_years = Counter(int(x[:4]) for x in ok["first"]) if len(ok) else {}
    last = ok["last"].value_counts().head(3).to_dict() if len(ok) else {}
    return {
        "folder": str(folder.relative_to(ROOT)),
        "n_files": len(files),
        "n_with_dates": int(len(ok)),
        "earliest_first_date": ok["first"].min() if len(ok) else None,
        "latest_first_date": ok["first"].max() if len(ok) else None,
        "most_common_last_dates": last,
        "first_date_year_histogram": dict(sorted(first_years.items())),
        "names_ending_before_2026_06": sorted(ok.loc[ok["last"] < "2026-06-01", "ticker"].tolist()) if len(ok) else [],
    }


def lse_catalog_summary() -> dict:
    cat = json.load(open(ROOT / "data/lse_catalog_20260917.json"))
    out = {}
    for ds in ("stocks", "crypto", "etf", "futures", "index"):
        rows = [x for x in cat if x["dataset"] == ds]
        live = [x for x in rows if x.get("live") == 1]
        dead = [x for x in rows if x.get("live") != 1]
        fy = Counter(str(x.get("first_tick", ""))[:4] for x in rows)
        dead_last = sorted(str(x.get("last_tick", ""))[:10] for x in dead)
        out[ds] = {
            "n_total": len(rows), "n_live": len(live), "n_not_live": len(dead),
            "first_tick_year_histogram": dict(sorted(fy.items())),
            "not_live_last_tick_min": dead_last[0] if dead_last else None,
            "not_live_last_tick_max": dead_last[-1] if dead_last else None,
        }
    return out


REASON_PATTERNS = [
    ("acquired_or_merged", r"acqui|merg|bought|takeover|purchas"),
    ("spin_or_restructure", r"spin|split off|separat|reorgani|restructur|conver"),
    ("bankruptcy_or_distress", r"bankrupt|chapter 11|delist|insolv|default|receivership|fail"),
    ("market_cap_or_eligibility", r"market cap|capitaliz|eligib|index rebal|rebalanc|float|liquidity|size"),
]


def removal_reasons() -> pd.DataFrame:
    ev = pd.read_csv(ROOT / "reports/momentum_verification_20260919/membership_events.csv")
    ev["date"] = pd.to_datetime(ev["date"], errors="coerce", format="mixed")
    ev = ev.dropna(subset=["date"])
    rem = ev[ev["removed"].notna()].copy()

    def cls(s: str) -> str:
        s = str(s).lower()
        for name, pat in REASON_PATTERNS:
            if re.search(pat, s):
                return name
        return "other_or_blank"

    rem["reason_class"] = rem["reason"].map(cls)
    rem["year"] = rem["date"].dt.year
    tab = rem.pivot_table(index="year", columns="reason_class", values="removed",
                          aggfunc="count", fill_value=0)
    tab["total_removed"] = tab.sum(axis=1)
    return tab


def pit_coverage_by_year() -> pd.DataFrame:
    cov = pd.read_csv(ROOT / "reports/momentum_verification_20260919/membership_coverage.csv",
                      parse_dates=["date"])
    cov["year"] = cov["date"].dt.year
    g = cov.groupby("year").agg(members=("members", "mean"), priced=("priced_members", "mean"),
                                uncovered=("uncovered", "mean"))
    g["priced_share"] = g["priced"] / g["members"]
    return g.round(3)


def main() -> None:
    caches = [ROOT / "data/raw", ROOT / "data/multiasset/stocks", ROOT / "data/stocks_raw_2014",
              ROOT / "data/raw_legacy", ROOT / "data/lse/candles_1d", ROOT / "data/multiasset/crypto"]
    summary = {"caches": [cache_summary(c) for c in caches if c.exists()]}
    summary["lse_catalog_20260917"] = lse_catalog_summary()

    # Universe-selection provenance (text only)
    sel = (ROOT / "reports/universe_selection.txt").read_text()[:400]
    rk = pd.read_csv(ROOT / "reports/universe_ranking.csv")
    summary["universe_selection"] = {
        "reports/universe_selection.txt": sel.split("\n")[0],
        "reports/universe_ranking.csv_rows": int(len(rk)),
        "ranking_lookback_bars": int(rk["n_bars"].mode().iloc[0]),
        "note": "Ranking = current Wikipedia S&P 500 list x 63-day dollar volume computed 2026-08-18: "
                "today-selected, i.e. look-ahead for any historical test.",
    }
    exp = (ROOT / "data/expanded_universe_all_tickers.txt").read_text().replace(",", "\n").split()
    summary["expanded_universe"] = {"n_tickers_all": len(exp),
                                    "log": "reports/expanded_universe_ingestion_log.txt: 428 new tickers, "
                                           "OHLCV 427/428 from 2015-01-02, earnings 418/428 (2026-08-18)"}

    rr = removal_reasons()
    rr.to_csv(OUT / "sp500_removal_reasons.csv")
    tot = rr.drop(columns="total_removed").sum()
    summary["sp500_removals_2000_2026"] = {
        "by_reason_total": tot.astype(int).to_dict(),
        "share": (tot / tot.sum()).round(3).to_dict(),
        "per_year_mean_2011_2026": float(rr.loc[2011:2026, "total_removed"].mean()),
        "caveat": "Wikipedia change-ledger reason text classified by regex; ~400 rows; thin before 2011.",
    }
    pc = pit_coverage_by_year()
    pc.to_csv(OUT / "pit_coverage_by_year.csv")
    summary["pit_sp500_priced_share_by_year"] = pc["priced_share"].to_dict()

    (OUT / "stock_coverage.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps({k: (v if k != "caches" else [{kk: c[kk] for kk in ("folder", "n_files", "earliest_first_date", "latest_first_date", "most_common_last_dates", "first_date_year_histogram")} for c in v]) for k, v in summary.items()}, indent=1, default=str)[:9000])


if __name__ == "__main__":
    main()
