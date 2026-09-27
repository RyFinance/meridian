"""Acquire source inputs for the isolated beyond-menu development studies.

This script only retrieves and serializes data; it never calculates returns.
The predeclared latest permitted input date is 2022-12-30, and all later
observations are discarded without inspection.
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "sol_beyond_menu" / "raw"
OUT.mkdir(parents=True, exist_ok=True)
STAMP = datetime.now(timezone.utc).isoformat()


def save_bytes(name: str, url: str) -> None:
    response = requests.get(url, timeout=90)
    response.raise_for_status()
    (OUT / name).write_bytes(response.content)
    print(json.dumps({"file": name, "bytes": len(response.content), "retrieved_at": STAMP,
                      "source_identifier": url}))


def main() -> None:
    # Yahoo returns a MultiIndex even for one ticker in recent yfinance.
    frame = yf.download("SPY", start="1993-01-01", end="2022-12-31", auto_adjust=False,
                        actions=True, progress=False, threads=False)
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame = frame.reset_index()
    if frame.empty or frame["Date"].max() >= pd.Timestamp("2023-01-01"):
        raise RuntimeError("SPY date bound failed")
    frame.to_csv(OUT / "spy_ohlc_1993_2022.csv", index=False, float_format="%.12g")
    print(json.dumps({"file": "spy_ohlc_1993_2022.csv", "rows": len(frame),
                      "first": str(frame["Date"].min().date()), "last": str(frame["Date"].max().date()),
                      "retrieved_at": STAMP, "source_identifier": "Yahoo Finance / SPY"}))

    save_bytes("rrz_sii_1973_2021.xlsx",
               "https://drive.google.com/uc?export=download&id=1DgFLrH8YJHiKFgYVimeiaXmZrOf7H9OQ")
    save_bytes("french_ff5_monthly.zip",
               "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/Historical_Archives/08%202022%20Update/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip")
    save_bytes("ehsani_linnainmaa_wp25551.pdf",
               "https://www.nber.org/system/files/working_papers/w25551/w25551.pdf")


if __name__ == "__main__":
    main()
