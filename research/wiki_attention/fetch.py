"""Cache Wikimedia daily pageviews (per stock, via curl) and yfinance open/close prices."""
import json
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import yfinance as yf

from universe import UNIVERSE

BASE = Path(__file__).resolve().parent
CACHE = BASE / "cache"
PV_DIR = CACHE / "pv"
PV_DIR.mkdir(parents=True, exist_ok=True)
# Descriptive UA without personal contact details (not sent to any third party beyond Wikimedia).
UA = "quant_v7-wiki-attention-research/0.1 (academic research; pageviews cache)"
START, END = "20190101", "20261016"


def fetch_pv(ticker, title):
    out = PV_DIR / f"{ticker}.json"
    if out.exists():
        return True
    url = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/"
        f"all-access/user/{quote(title.replace(' ', '_'), safe='')}/daily/{START}/{END}"
    )
    for attempt in range(6):
        r = subprocess.run(
            ["curl", "-s", "-A", UA, "-w", "\n%{http_code}", url],
            capture_output=True, text=True, timeout=60,
        )
        time.sleep(1.0)
        body, _, code = r.stdout.rpartition("\n")
        if code == "200" and body.strip():
            items = json.loads(body).get("items", [])
            views = {it["timestamp"][:8]: it["views"] for it in items}
            out.write_text(json.dumps({"title": title, "views": views}))
            return True
        if code == "404":
            return False  # bad title: do not retry
        time.sleep(30 * (attempt + 1))  # back off on 429 rate limits
    return False


def main():
    ok, failed = [], []
    for t, title in UNIVERSE.items():
        (ok if fetch_pv(t, title) else failed).append(t)
    print(f"pageviews ok={len(ok)} failed={failed}")

    tickers = list(UNIVERSE) + ["SPY"]
    df = yf.download(tickers, start="2018-12-01", end="2026-10-18",
                     auto_adjust=True, progress=False, group_by="column")
    op = df["Open"].dropna(how="all")
    cl = df["Close"].dropna(how="all")
    op.to_pickle(CACHE / "open.pkl")
    cl.to_pickle(CACHE / "close.pkl")
    print("prices", op.shape, op.index.min().date(), op.index.max().date())
    print("missing price cols:", [c for c in tickers if c not in op.columns or op[c].isna().all()])


if __name__ == "__main__":
    main()
