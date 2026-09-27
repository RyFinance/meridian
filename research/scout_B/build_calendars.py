"""Workstream B scout: build reference calendars (OpEx, FOMC) as data facts only.

No strategy return, window return, or signal-conditional return is computed here.
Outputs go to data/scout_B/. Read-only against all existing repo files.

Run: PYTHONPATH=. .venv/bin/python research/scout_B/build_calendars.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from research.fx_news.events import true_utc
from research.vrp_putwrite.core import monthly_expiries

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "scout_B"
OUT.mkdir(parents=True, exist_ok=True)

TODAY = pd.Timestamp("2026-09-23")


def build_opex() -> pd.DataFrame:
    o = pd.read_parquet(ROOT / "data/lse/options_etf_1d/SPY.parquet", columns=["ts", "expiry"])
    last_print = o["ts"].max().tz_localize(None)
    exp = pd.Series(pd.to_datetime(o["expiry"].unique()))
    xs = monthly_expiries(exp)  # research/vrp_putwrite/core.py: 3rd Fri, pre-2015 Sat->Fri, Good-Fri Thu
    df = pd.DataFrame({"expiry_date": xs})
    df["year"] = df["expiry_date"].dt.year
    df["month"] = df["expiry_date"].dt.month
    df["dow"] = df["expiry_date"].dt.day_name()
    df["is_quarterly_triple_witching"] = df["month"].isin([3, 6, 9, 12])
    df["is_thursday_adj_good_friday"] = df["dow"] == "Thursday"
    df["realized"] = df["expiry_date"] <= last_print
    df["source"] = "data/lse/options_etf_1d/SPY.parquet expiry field; research/vrp_putwrite/core.py monthly_expiries()"
    df = df.sort_values("expiry_date").reset_index(drop=True)
    return df, last_print


def build_fomc() -> pd.DataFrame:
    e = pd.read_parquet(ROOT / "data/lse/econ_calendar_us.parquet")
    d = e[e["event"] == "Fed Interest Rate Decision"].copy()
    d["raw_datetime"] = pd.to_datetime(d["datetime"])
    d["created_at"] = pd.to_datetime(d["created_at"])
    d["t_utc"] = [true_utc(s, c) for s, c in zip(d["raw_datetime"], d["created_at"])]
    d = d.sort_values("t_utc").drop_duplicates(subset=["date"], keep="last")
    d["decision_date"] = d["t_utc"].dt.date
    d["decision_time_utc"] = d["t_utc"].dt.strftime("%H:%M")
    # rough ET display (EDT UTC-4 Mar-Nov, EST UTC-5 Nov-Mar) -- informational only
    d["year"] = d["t_utc"].dt.year
    out = d[["decision_date", "decision_time_utc", "actual", "previous", "consensus",
             "created_at", "year"]].reset_index(drop=True)
    out["source"] = ("data/lse/econ_calendar_us.parquet event=='Fed Interest Rate Decision'; "
                      "timestamp realigned with research/fx_news/events.py true_utc(); "
                      "cross-checked 2025-2026 dates against federalreserve.gov/monetarypolicy/fomccalendars.htm "
                      "on 2026-09-23 (exact match)")
    return out


def build_quarter_ends() -> pd.DataFrame:
    spy = pd.read_parquet(ROOT / "data/multiasset/etf/SPY.parquet", columns=["date"])
    d = pd.to_datetime(spy["date"]).sort_values().reset_index(drop=True)
    ym = d.dt.year * 100 + d.dt.month
    is_q_month = d.dt.month.isin([3, 6, 9, 12])
    last_of_month = ~ym.duplicated(keep="last")
    qe = d[is_q_month & last_of_month].reset_index(drop=True)
    out = pd.DataFrame({"quarter_end_trading_date": qe})
    out["source"] = "last trading date of Mar/Jun/Sep/Dec in data/multiasset/etf/SPY.parquet date column (yfinance official session calendar)"
    return out


def main() -> None:
    opex, last_print = build_opex()
    opex.to_csv(OUT / "opex_calendar.csv", index=False)

    fomc = build_fomc()
    fomc.to_csv(OUT / "fomc_calendar.csv", index=False)

    qe = build_quarter_ends()
    qe.to_csv(OUT / "quarter_end_dates.csv", index=False)
    print(f"Quarter-end trading dates: {len(qe)} ({qe['quarter_end_trading_date'].min()} - {qe['quarter_end_trading_date'].max()})")

    print(f"SPY options last print: {last_print}")
    print(f"OpEx rows: {len(opex)}  realized: {int(opex['realized'].sum())}  "
          f"quarterly among realized: {int((opex['realized'] & opex['is_quarterly_triple_witching']).sum())}")
    print(f"FOMC decision rows: {len(fomc)}  years: {fomc['year'].min()}-{fomc['year'].max()}")
    print(fomc.groupby('year').size())


if __name__ == "__main__":
    main()
