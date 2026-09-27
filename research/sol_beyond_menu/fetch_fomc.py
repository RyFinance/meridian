"""Extract scheduled FOMC decision dates from official historical-year pages.

No market return is calculated. The event-date CSV is a generated input and
is frozen together with its source HTML and the pre-existing SPY source file.
"""
from __future__ import annotations

import csv
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/sol_beyond_menu/macro_raw"
PAGES = RAW / "fed_pages"
PAGES.mkdir(parents=True, exist_ok=True)
RETRIEVED = datetime.now(timezone.utc).isoformat()
MONTHS = {name: i for i, name in enumerate(("January", "February", "March", "April", "May", "June",
                                           "July", "August", "September", "October", "November", "December"), 1)}


def main() -> None:
    source_spy = ROOT / "data/sol_beyond_menu/raw/spy_ohlc_1993_2022.csv"
    shutil.copyfile(source_spy, RAW / "spy_ohlc_1993_2022.csv")
    shutil.copyfile(ROOT / "data/sol_beyond_menu/raw/french_ff5_monthly.zip", RAW / "french_ff5_monthly.zip")
    metadata = {}
    records = []
    for year in range(1994, 2020):
        url = f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{year}.htm"
        response = requests.get(url, timeout=40)
        response.raise_for_status()
        path = PAGES / f"{year}.html"
        path.write_bytes(response.content)
        headings = [h.get_text(" ", strip=True) for h in BeautifulSoup(response.content, "html.parser").select("h5")]
        dates = []
        for heading in headings:
            if "Meeting" not in heading or any(x in heading.lower() for x in ("unscheduled", "cancelled", "notation")):
                continue
            normalized = heading
            for full in MONTHS:
                normalized = re.sub(r"\b" + full[:3] + r"\b", full, normalized)
            normalized = re.sub(r"^([A-Za-z]+)/([A-Za-z]+)\s+(\d{1,2})-(\d{1,2})\s+",
                                r"\1 \3-\2 \4 ", normalized)
            match = re.match(r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:-(?:(January|February|March|April|May|June|July|August|September|October|November|December)\s+)?(\d{1,2}))?\s+Meeting\s+-\s+" + str(year) + r"$", normalized)
            if match is None:
                raise RuntimeError(f"unparsed scheduled meeting heading: {year} {heading}")
            month, first, end_month, second = match.groups()
            event = f"{year}-{MONTHS[end_month or month]:02d}-{int(second or first):02d}"
            dates.append(event)
            records.append({"date": event, "source_year": year, "heading": heading})
        if not 7 <= len(dates) <= 9:
            raise RuntimeError(f"unexpected scheduled meeting count in {year}: {len(dates)}")
        metadata[f"raw/fed_pages/{year}.html"] = {
            "source": "Federal Reserve historical FOMC materials", "source_identifier": url,
            "retrieved_at": RETRIEVED, "logical_as_of": f"{year}-12-31", "symbol": "FOMC_CALENDAR",
            "first_timestamp": None, "last_timestamp": None, "row_count": len(dates), "temporal": False
        }
    with (RAW / "scheduled_fomc_dates.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["date", "source_year", "heading"])
        writer.writeheader()
        writer.writerows(records)
    (RAW / "universe.json").write_text(json.dumps({"dataset_version": "sol_fomc_dev_v1",
        "members": ["SPY", "scheduled FOMC decision days"],
        "exclusions": ["intermeeting/unscheduled events", "conference calls", "notation votes", "cancelled meetings", "2013-2019 locked holdout"],
        "symbol_mappings": {"SPY": "SPDR S&P 500 ETF Trust", "FOMC": "last day of scheduled meeting"},
        "delistings": {"SPY": "none before source cutoff"}}, sort_keys=True, indent=2) + "\n")
    metadata["raw/spy_ohlc_1993_2022.csv"] = {
        "source": "Yahoo Finance via yfinance; exact copy of sol_beyond_menu_dev_v1 SPY input",
        "source_identifier": "https://query1.finance.yahoo.com/v8/finance/chart/SPY",
        "retrieved_at": RETRIEVED, "logical_as_of": "2022-12-30", "symbol": "SPY",
        "first_timestamp": "1993-01-29T00:00:00Z", "last_timestamp": "2022-12-30T00:00:00Z", "row_count": 7536
    }
    metadata["raw/french_ff5_monthly.zip"] = {
        "source": "Kenneth French Data Library archived July 2022 cut; exact copy of sol_beyond_menu_dev_v1 input",
        "source_identifier": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/Historical_Archives/08%202022%20Update/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip",
        "retrieved_at": RETRIEVED, "logical_as_of": "2022-07-31", "symbol": "FF5_RF",
        "first_timestamp": "1963-07-01T00:00:00Z", "last_timestamp": "2022-07-01T00:00:00Z", "row_count": 709
    }
    metadata["raw/scheduled_fomc_dates.csv"] = {
        "source": "Generated mechanically from frozen Federal Reserve historical-year pages",
        "source_identifier": "https://www.federalreserve.gov/monetarypolicy/fomc_historical_year.htm",
        "retrieved_at": RETRIEVED, "logical_as_of": "2019-12-31", "symbol": "FOMC_CALENDAR",
        "first_timestamp": records[0]["date"] + "T00:00:00Z",
        "last_timestamp": records[-1]["date"] + "T00:00:00Z", "row_count": len(records)
    }
    metadata["raw/universe.json"] = {
        "source": "Preregistered FOMC event universe", "source_identifier": None,
        "retrieved_at": RETRIEVED, "logical_as_of": "2019-12-31", "symbol": "UNIVERSE",
        "first_timestamp": None, "last_timestamp": None, "row_count": 2, "temporal": False
    }
    spec = {"dataset_version": "sol_fomc_dev_v1",
            "scopes": [{"name": "raw", "root": str(RAW.resolve()), "include": ["**/*"]}],
            "universe": {"membership_artifact": "raw/universe.json",
                         "exclusions": ["2013-2019 holdout", "unscheduled decisions"],
                         "symbol_mappings": {"SPY": "Yahoo SPY", "FOMC": "Fed scheduled decision date"},
                         "delistings": {"SPY": "none"}},
            "intermediate_artifacts": ["raw/scheduled_fomc_dates.csv"], "metadata": metadata}
    (ROOT / "research/sol_beyond_menu/fomc_freeze_spec.json").write_text(json.dumps(spec, indent=2) + "\n")
    print(json.dumps({"years": 26, "scheduled_dates": len(records), "first": records[0]["date"],
                      "last": records[-1]["date"], "retrieved_at": RETRIEVED}))


if __name__ == "__main__":
    main()
