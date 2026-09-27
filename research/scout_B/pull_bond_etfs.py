"""Workstream B scout: pull raw OHLC + corporate actions for 8 bond ETFs, data facts only.

No return is computed. This only establishes: history start, row counts, ex-dividend date
counts/timing. Output: data/scout_B/bond_etfs/*.parquet (source archive) and
data/scout_B/bond_etf_exdiv.csv (ex-dividend date facts).

Run: PYTHONPATH=. .venv/bin/python research/scout_B/pull_bond_etfs.py
"""
from __future__ import annotations

import socket
socket.setdefaulttimeout(20)

from hashlib import sha256
import json
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "scout_B" / "bond_etfs"
OUT.mkdir(parents=True, exist_ok=True)

TICKERS = ["LQD", "AGG", "MBB", "TIP", "EMB", "HYG", "BND", "IEF"]


def pull(ticker: str) -> dict:
    raw = yf.download(ticker, start="2000-01-01", auto_adjust=False, actions=True,
                       progress=False, threads=False)
    if isinstance(raw.columns, pd.MultiIndex):
        raw = raw.xs(ticker, axis=1, level="Ticker")
    d = raw.reset_index().rename(columns={"Date": "date", "Adj Close": "adj_close", "Close": "close",
                                          "Open": "open", "High": "high", "Low": "low",
                                          "Volume": "volume", "Dividends": "dividends",
                                          "Stock Splits": "stock_splits"})
    if d.empty:
        raise RuntimeError(f"{ticker}: yfinance returned nothing")
    path = OUT / f"{ticker}.parquet"
    d.to_parquet(path, index=False)
    exdiv = d.loc[d["dividends"] > 0, ["date", "dividends"]].copy()
    exdiv["ticker"] = ticker
    return {
        "ticker": ticker,
        "first_date": str(d["date"].min().date()),
        "last_date": str(d["date"].max().date()),
        "rows": len(d),
        "n_exdiv": len(exdiv),
        "sha256": sha256(path.read_bytes()).hexdigest(),
    }, exdiv


def main() -> None:
    manifest = {"source": "yfinance auto_adjust=False actions=True, pulled 2026-09-23", "tickers": {}}
    exdiv_all = []
    for t in TICKERS:
        info, exdiv = pull(t)
        manifest["tickers"][t] = info
        exdiv_all.append(exdiv)
        print(t, info["first_date"], "->", info["last_date"], "rows", info["rows"], "exdiv", info["n_exdiv"])
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    exdiv_df = pd.concat(exdiv_all, ignore_index=True).sort_values(["ticker", "date"])
    exdiv_df["month"] = pd.to_datetime(exdiv_df["date"]).dt.month
    exdiv_df["day"] = pd.to_datetime(exdiv_df["date"]).dt.day
    exdiv_df.to_csv(ROOT / "data/scout_B/bond_etf_exdiv.csv", index=False)
    print("wrote", ROOT / "data/scout_B/bond_etf_exdiv.csv", len(exdiv_df), "rows")


if __name__ == "__main__":
    main()
