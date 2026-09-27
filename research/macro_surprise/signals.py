"""Point-in-time country growth-surprise diffusion index from the LSE economic calendar.

Registered in research/macro_surprise/PLAN.md. Every rule here is fixed by that plan:

  * a release counts only if both `actual` and `consensus` parse to numbers in the same unit system;
  * an event is a growth release by keyword rule (EXCLUDE first, then NEGATIVE, then POSITIVE);
    anything unmatched is ignored;
  * vote = direction x sign(actual - consensus), in {-1, 0, +1};
  * the diffusion score of economy k at signal date t is sum(votes) / sqrt(n) over the n growth
    releases dated in [t - 91 calendar days, t - 1 calendar day] (calendar date as stamped, so no
    release from the signal date itself is used whatever the vendor's time zone);
  * an economy needs at least MIN_RELEASES votes in the window, otherwise its score is missing.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CALENDAR = ROOT / "data" / "lse" / "econ_calendar_us.parquet"

WINDOW_DAYS = 91
MIN_RELEASES = 10

# economy -> (ETF, calendar region codes). UK/EU are the 2025-26 codes for GB/EA in the same file.
ECONOMIES: dict[str, tuple[str, tuple[str, ...]]] = {
    "US": ("SPY", ("US",)),
    "JP": ("EWJ", ("JP",)),
    "GB": ("EWU", ("GB", "UK")),
    "EZ": ("EZU", ("EA", "EU", "DE", "FR", "IT", "ES", "NL", "AT", "BE", "IE", "PT", "FI", "GR", "SK")),
    "AU": ("EWA", ("AU",)),
    "CA": ("EWC", ("CA",)),
    "BR": ("EWZ", ("BR",)),
    "MX": ("EWW", ("MX",)),
    "KR": ("EWY", ("KR",)),
    "CN": ("MCHI", ("CN",)),
    "IN": ("INDA", ("IN",)),
    "ZA": ("EZA", ("ZA",)),
    "TR": ("TUR", ("TR",)),
    "ID": ("EIDO", ("ID",)),
}

EXCLUDE = (
    "inflation", "cpi", "ppi", "wpi", "rpi", "hicp", "ipca", "igp-", "ipc-", "price", "deflator",
    "earnings", "wage", "labour cost", "labor cost", "balance", "export", "import", "current account",
    "budget", "debt", "borrowing", "tax", "revenue", "interest rate", "rate decision",
    "lending rate", "loan prime", "prime rate", "repo rate", "reserve", "mlf", "auction", "yield",
    "bond", "mortgage", "lending", "loan", "credit", "money supply", "deposit", "financing",
    "inventor", "stocks change", "stock change", "rig count", "tic flows", "capital flows",
    "investment by foreigners", "foreign bond", "fdi", "foreign direct", "mpc vote",
    "quantitative easing", "participation rate", "tourist", "tourism", "cash balance", "liquidity",
    "speech", "minutes", "halifax", "rics", "nationwide housing",
)
NEGATIVE = ("unemploy", "jobless", "claimant", "job cuts")
POSITIVE = (
    "gdp", "pmi", "production", "output", "orders", "durable goods", "retail sales", "spending",
    "consumption", "personal income", "sales", "registrations", "payrolls", "employment", "employed",
    "job openings", "jolts", "jobs", "hours", "confidence", "sentiment", "optimism", "climate", "zew",
    "ifo", "tankan", "eco watchers", "current conditions", "expectations", "outlook", "business",
    "activity", "leading", "coincident", "utilization", "starts", "permits", "approvals",
    "construction", "housing market index", "manufacturing index", "tertiary industry",
    "all industry", "investment", "capex", "capital expenditure", "profits", "bsi",
    "gross domestic product", "gnp", "services index", "composite index", "industry index", "shipments",
    "job advertisements", "job ads", "job vacancies", "aggregate demand", "labor market conditions",
    "manufacturing prod", "distributive trades", "redbook", "ism ",
)

_MONTHS = r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)"
_SUFFIX = re.compile(rf"\s+({_MONTHS}(/\d+)?(-{_MONTHS})?|Q[1-4](/\d+)?|(JAN|FEB)-(JAN|FEB)|\d{{4}}(-\d{{2,4}})?)$")
_MULT = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def direction(name: str) -> int:
    """+1 growth-good-if-higher, -1 growth-good-if-lower, 0 not a growth release."""
    s = name.lower()
    if any(k in s for k in EXCLUDE):
        return 0
    if any(k in s for k in NEGATIVE):
        return -1
    if any(k in s for k in POSITIVE):
        return 1
    return 0


def normalise_name(event: str, period_hint) -> str:
    s = str(event).strip()
    if isinstance(period_hint, str) and period_hint and s.endswith(" " + period_hint):
        s = s[: -len(period_hint) - 1].strip()
    prev = None
    while prev != s:
        prev, s = s, _SUFFIX.sub("", s).strip()
    return s


def parse_value(x) -> float:
    """'252K' -> 252000, '-0.5%' -> -0.5, '$ 4.7B' -> 4.7e9. Unparseable -> nan."""
    if x is None:
        return np.nan
    s = str(x).strip().replace(",", "").replace(" ", "")
    s = re.sub(r"^[\$€£¥₹]|^(R\$|US\$|A\$|C\$)", "", s)
    s = re.sub(r"^(-?)[\$€£¥₹]", r"\1", s)
    s = re.sub(r"(?i)points$", "", s).rstrip("%")
    mult = 1.0
    if s and s[-1].upper() in _MULT:
        mult = _MULT[s[-1].upper()]
        s = s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return np.nan


def releases(upto: pd.Timestamp | None = None) -> pd.DataFrame:
    """One row per classified growth release with a vote. Dates are calendar dates as stamped."""
    e = pd.read_parquet(CALENDAR)
    region_to_econ = {r: k for k, (_, regs) in ECONOMIES.items() for r in regs}
    e = e[e["region_code"].isin(region_to_econ)].copy()
    e["economy"] = e["region_code"].map(region_to_econ)
    e["day"] = pd.to_datetime(e["date"])
    if upto is not None:
        e = e[e["day"] <= upto]
    e["name"] = [normalise_name(a, b) for a, b in zip(e["event"], e["period_hint"])]
    e["dir"] = e["name"].map(direction).astype(int)
    e["a"] = e["actual"].map(parse_value)
    e["c"] = e["consensus"].map(parse_value)
    e = e[(e["dir"] != 0) & e["a"].notna() & e["c"].notna()]
    # GB/UK and EA/EU overlap in 2025-26: keep one row per economy, day, region-free name and value
    e = e.sort_values(["day", "id"]).drop_duplicates(["economy", "day", "name", "a", "c"], keep="first")
    e["vote"] = e["dir"] * np.sign(e["a"] - e["c"])
    return e[["id", "economy", "region_code", "day", "datetime", "name", "dir", "actual", "consensus",
              "a", "c", "vote"]].reset_index(drop=True)


def diffusion(rel: pd.DataFrame, dates: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame]:
    """sum(votes)/sqrt(n) and n per economy over [t-91d, t-1d] for each signal date t."""
    score = pd.DataFrame(np.nan, index=dates, columns=list(ECONOMIES))
    count = pd.DataFrame(0, index=dates, columns=list(ECONOMIES))
    for k, g in rel.groupby("economy"):
        g = g.sort_values("day")
        days = g["day"].to_numpy()
        cum = np.r_[0.0, np.cumsum(g["vote"].to_numpy(float))]
        for t in dates:
            lo = np.searchsorted(days, np.datetime64(t - pd.Timedelta(days=WINDOW_DAYS)), side="left")
            hi = np.searchsorted(days, np.datetime64(t), side="left")  # strictly before t
            n = hi - lo
            count.loc[t, k] = n
            if n >= MIN_RELEASES:
                score.loc[t, k] = (cum[hi] - cum[lo]) / np.sqrt(n)
    return score, count
