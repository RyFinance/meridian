"""Presence/absence-only check (NO return computation, per the task's hard constraint) of
free price coverage for a sample of delisted/bankrupt/acquired tickers, via yfinance. This
is the survivorship question: does ANY free source carry prices for issuers EDGAR still
covers (EDGAR is survivor-free) after they stop trading? Cross-references the repo's own
prior finding (research/data_scout/build_vendor_matrix.py: LSE vault has no candles for
SIVB/TWTR/FRC/CELG).

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.edgar_scout.delisted_price_probe
"""
from __future__ import annotations

import json

import yfinance as yf

from research.edgar_scout.cik_sample import DELISTED_TICKERS
from research.edgar_scout.common import DATA_DIR

# a couple of live controls, to make sure the probe method itself works
CONTROLS = ["AAPL", "MSFT"]


def has_history(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="max", auto_adjust=False)
        n = len(hist)
        return {"ticker": ticker, "n_rows": n, "first": str(hist.index.min()) if n else None,
                "last": str(hist.index.max()) if n else None, "has_data": n > 0}
    except Exception as e:  # noqa: BLE001 -- probe script, record and continue
        return {"ticker": ticker, "error": str(e), "has_data": False}


def main() -> None:
    out = {}
    for label, ticker in {**DELISTED_TICKERS, "CONTROL_AAPL": "AAPL", "CONTROL_MSFT": "MSFT"}.items():
        r = has_history(ticker)
        out[label] = r
        print(label, ticker, "->", "DATA" if r.get("has_data") else "NO DATA", r.get("n_rows"),
              r.get("last"))
    (DATA_DIR / "delisted_price_probe.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
