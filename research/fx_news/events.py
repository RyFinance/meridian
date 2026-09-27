"""Scheduled-news events for the FX continuation study (research/fx_news/PLAN.md).

Every rule here is frozen by the plan:

* **Categories and FX direction** (+1 = the news implies the domestic currency appreciates):
  - policy: central-bank "interest rate decision" rows, dir +1 (a higher rate than consensus is hawkish);
  - inflation: CPI/HICP/PPI/PCE/RPI/inflation-rate rows, dir +1 (hotter inflation is hawkish);
  - growth: the frozen macro_surprise growth taxonomy (`signals.direction`), dir +1 or -1.
* **Vote** = dir × sign(actual − consensus); ties give 0.
* **Timestamps.** The calendar stamps are not UTC. The correction below was derived from published
  release schedules (payrolls 08:30 ET, Ifo 10:00 CET, AU labour force 11:30 AEST, …), never from
  prices. Rows loaded in the 2025-12-10 bulk batch are Europe/Berlin wall time for 2015 dates and a
  fixed UTC+1 from 2016 on. Rows loaded from 2025-12-31 on are UTC. Duplicate rows across the two
  batches collapse after correction.
* **Event group** = (target currency, true release minute). The net vote is the sum of votes;
  position = sign(net), and a zero net vote gives no trade.
"""
from __future__ import annotations

from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from research.macro_surprise.signals import CALENDAR, direction, normalise_name, parse_value

REGION_CCY = {"US": "USD", "GB": "GBP", "UK": "GBP", "JP": "JPY", "AU": "AUD", "CA": "CAD", "CH": "CHF",
              **{r: "EUR" for r in ("EA", "EU", "DE", "FR", "IT", "ES", "NL", "AT", "BE", "IE", "PT", "FI", "GR")}}
# pair, and +1 if the pair rises when the non-USD currency appreciates
PAIRS = {"EUR": ("EURUSD", +1), "GBP": ("GBPUSD", +1), "AUD": ("AUDUSD", +1),
         "JPY": ("USDJPY", -1), "CAD": ("USDCAD", -1), "CHF": ("USDCHF", -1)}
USD_BASKET = ["EUR", "GBP", "AUD", "JPY", "CAD", "CHF"]   # USD news: 1/6 in each pair

POLICY_INCLUDE = ("interest rate decision",)
POLICY_EXCLUDE = ("loan prime", "deposit facility", "lending facility", "overnight", "prime rate")
INFLATION_INCLUDE = ("inflation rate", "cpi", "hicp", "harmonised inflation", "ppi", "producer price",
                     "pce price", "core inflation", "retail price index", "rpi")
INFLATION_EXCLUDE = ("expectation", "import price", "export price", "house price", "home price",
                     "housing price", "wholesale", "raw material")
BULK_BATCH_END = pd.Timestamp("2025-12-31")   # created_at before this = the 2025-12-10 bulk load
BERLIN = ZoneInfo("Europe/Berlin")


def category(name: str) -> tuple[str | None, int]:
    s = name.lower()
    if any(k in s for k in POLICY_INCLUDE) and not any(k in s for k in POLICY_EXCLUDE):
        return "policy", 1
    if any(k in s for k in INFLATION_INCLUDE) and not any(k in s for k in INFLATION_EXCLUDE):
        return "inflation", 1
    d = direction(name)
    return ("growth", d) if d != 0 else (None, 0)


def true_utc(stamp: pd.Timestamp, created_at: pd.Timestamp) -> pd.Timestamp:
    if created_at >= BULK_BATCH_END:
        return stamp
    if stamp.year == 2015:
        return stamp.tz_localize(BERLIN, ambiguous="NaT", nonexistent="NaT").tz_convert("UTC").tz_localize(None)
    return stamp - pd.Timedelta(hours=1)


def releases(start: str, end: str) -> pd.DataFrame:
    """One row per classified, parseable release with a vote, dated by true UTC time in [start, end]."""
    e = pd.read_parquet(CALENDAR)
    e = e[e["region_code"].isin(REGION_CCY)].copy()
    e["ccy"] = e["region_code"].map(REGION_CCY)
    e["name"] = [normalise_name(a, b) for a, b in zip(e["event"], e["period_hint"])]
    cat = e["name"].map(category)
    e["category"] = [c for c, _ in cat]
    e["dir"] = [d for _, d in cat]
    e = e[e["category"].notna()]
    e["a"] = e["actual"].map(parse_value)
    e["c"] = e["consensus"].map(parse_value)
    e = e.dropna(subset=["a", "c"])
    stamp = pd.to_datetime(e["datetime"])
    created = pd.to_datetime(e["created_at"])
    e["t_utc"] = [true_utc(s, c) for s, c in zip(stamp, created)]
    e = e.dropna(subset=["t_utc"])
    e = e[stamp.loc[e.index].dt.strftime("%H:%M") != "00:00"]       # unknown release time
    e = e[(e["t_utc"] >= pd.Timestamp(start)) & (e["t_utc"] <= pd.Timestamp(end) + pd.Timedelta(days=1))]
    e = e.sort_values(["t_utc", "id"]).drop_duplicates(["ccy", "name", "t_utc", "a", "c"], keep="first")
    e["vote"] = e["dir"] * np.sign(e["a"] - e["c"])
    return e[["id", "region_code", "ccy", "name", "category", "dir", "actual", "consensus", "a", "c",
              "t_utc", "vote"]].reset_index(drop=True)


def event_groups(rel: pd.DataFrame) -> pd.DataFrame:
    """Aggregate releases to (currency, minute) groups with a net vote and a trade sign."""
    rel = rel.assign(t0=rel["t_utc"].dt.floor("min"))
    g = rel.groupby(["ccy", "t0"]).agg(net=("vote", "sum"), n=("vote", "size"),
                                       categories=("category", lambda x: ",".join(sorted(set(x))))).reset_index()
    g["sign"] = np.sign(g["net"]).astype(int)
    return g[g["sign"] != 0].sort_values("t0").reset_index(drop=True)
