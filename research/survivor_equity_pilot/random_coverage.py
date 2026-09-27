"""Unbiased(-er) coverage estimate: random samples of delisted US stocks drawn from Tiingo's public
supported_tickers list (which has start/end dates but no prices without a key), tested against the
free Yahoo v8 chart endpoint. Plus universe-size counts (Tiingo list, FINRA CNMS local files).

The famous-name pilot is biased toward names someone would remember; this sample is not.
Presence / date-window checks only; no returns are computed.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.survivor_equity_pilot.random_coverage
"""
from __future__ import annotations

import json

import pandas as pd

from research.survivor_equity_pilot.chain import yahoo_chart
from research.survivor_equity_pilot.common import DATA_DIR, REPORT_DIR, ROOT
from research.survivor_equity_pilot.sources import load_tiingo

SEED = 20260925
N_PER_STRATUM = 50
EXCH = {"NYSE", "NASDAQ", "AMEX", "NYSE MKT", "NYSE ARCA", "BATS"}
OTC_END = {"PINK", "EXPM", "OTC", "OTCBB", "OTCQB", "OTCQX", "OTCGREY"}


def classify(y: dict, start: pd.Timestamp, end: pd.Timestamp) -> str:
    if not y.get("n"):
        return "NOT_FOUND"
    f, l = pd.Timestamp(y["first"]), pd.Timestamp(y["last"])
    if f > end:
        return "RECYCLED_AFTER_END"
    if abs((f - start).days) <= 45 and abs((l - end).days) <= 15:
        return "WINDOW_MATCH"
    if f <= end and l >= end - pd.Timedelta(days=15) and (f - start).days > 45:
        return "PARTIAL_WINDOW"
    return "WINDOW_MISMATCH"


def finra_universe() -> dict:
    files = sorted((ROOT / "data" / "c4" / "finra_regsho").glob("CNMSshvol*.txt"))
    per_year: dict[str, set] = {}
    last_seen: dict[str, str] = {}
    for p in files:
        d = p.stem[-8:]
        try:
            syms = pd.read_csv(p, sep="|", usecols=["Symbol"], dtype=str)["Symbol"].dropna()
        except Exception:  # noqa: BLE001
            continue
        per_year.setdefault(d[:4], set()).update(syms)
        for s in syms:
            last_seen[s] = d
    final = max(p.stem[-8:] for p in files)
    gone = pd.Series({s: d for s, d in last_seen.items() if d < "20260801"})
    return {"n_files": len(files), "first_file": files[0].stem[-8:], "last_file": final,
            "distinct_symbols_by_year": {y: len(s) for y, s in sorted(per_year.items())},
            "symbols_last_seen_by_year (disappeared before 2026-08)":
                gone.str[:4].value_counts().sort_index().to_dict(),
            "note": "CNMS symbols include ETFs, warrants, units, preferreds; symbol disappearance also "
                    "includes ticker changes, so this is an upper bound on delistings"}


def main() -> None:
    ti = load_tiingo()
    ti = ti[(ti["assetType"] == "Stock") & (ti["priceCurrency"] == "USD")].copy()
    ti["startDate"], ti["endDate"] = pd.to_datetime(ti["startDate"]), pd.to_datetime(ti["endDate"])
    ti = ti.dropna(subset=["startDate", "endDate"])
    dead = ti[ti["endDate"] < "2026-06-01"]
    counts = {
        "tiingo_us_stock_rows": len(ti),
        "tiingo_ended_before_2026_06": len(dead),
        "ended_by_year_and_final_exchange": dead.assign(y=dead["endDate"].dt.year)
            .pivot_table(index="y", columns="exchange", values="ticker", aggfunc="count", fill_value=0)
            .loc[2000:2026].to_dict(orient="index"),
    }
    win = dead[(dead["endDate"] >= "2008-01-01") & (dead["endDate"] <= "2023-12-31")
               & ((dead["endDate"] - dead["startDate"]).dt.days > 365)]
    strata = {"ended_on_exchange": win[win["exchange"].isin(EXCH)],
              "ended_on_otc": win[win["exchange"].isin(OTC_END)],
              # US bankruptcies: OTC ticker with the 5th-letter 'Q' (in-bankruptcy) suffix
              "ended_on_otc_Q_suffix": win[win["exchange"].isin(OTC_END) & win["ticker"].str.upper()
                                           .str.fullmatch(r"[A-Z]{3,4}Q")]}
    rows = []
    for name, df in strata.items():
        smp = df.sample(n=min(N_PER_STRATUM, len(df)), random_state=SEED)
        for _, r in smp.iterrows():
            y = yahoo_chart(r["ticker"].upper())
            c = classify(y, r["startDate"], r["endDate"])
            rows.append({"stratum": name, "ticker": r["ticker"].upper(), "tiingo_exchange": r["exchange"],
                         "tiingo_start": r["startDate"].date(), "tiingo_end": r["endDate"].date(),
                         "yahoo_http": y["http"], "yahoo_first": y.get("first"), "yahoo_last": y.get("last"),
                         "yahoo_name": y.get("longName"), "yahoo_exchange": y.get("exchange"), "class": c})
            print(name, r["ticker"], c, y.get("first"), y.get("last"), y.get("longName"))
    out = pd.DataFrame(rows)
    out.to_csv(REPORT_DIR / "random_sample_yahoo_coverage.csv", index=False)
    summ = {"seed": SEED, "strata_population": {k: len(v) for k, v in strata.items()},
            "class_counts": out.groupby(["stratum", "class"]).size().unstack(fill_value=0).to_dict(orient="index"),
            "universe_counts": counts, "finra_cnms_universe": finra_universe()}
    (REPORT_DIR / "random_coverage_summary.json").write_text(json.dumps(summ, indent=1, default=str))
    print(json.dumps(summ["class_counts"], indent=1))


if __name__ == "__main__":
    main()
