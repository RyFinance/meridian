"""Scout A: tiny yfinance probes for structural-premium candidate ETFs (2026-09-23).

Pure data-existence/QA probe. Does NOT compute any strategy/spread/signal returns.
For each ticker: first trade date, last date, row count, whether dividends are
present/nonzero, and a tiny sample of the earliest and latest rows (Close only)
to eyeball gaps/splits. Output: data/scout_A/yfinance_probe_20260923.json

Run: PYTHONPATH=. .venv/bin/python research/scout_A/pull_yfinance_probe.py
"""
from __future__ import annotations

import json
from pathlib import Path

import yfinance as yf

OUT = Path(__file__).resolve().parents[2] / "data" / "scout_A" / "yfinance_probe_20260923.json"

TICKERS = [
    # commodity roll-yield funds
    "USO", "USL", "UNG", "UNL", "BNO", "DBC", "GSG", "DBO", "USCI",
    # commodity futures month-code test tickers (yfinance continuous/contract style)
    "CLZ25.NYM", "CL=F", "GC=F",
    # TIPS / breakeven
    "TIP", "STIP", "IEF", "SHY",
    # EM local-currency bond carry
    "EMLC", "EMB", "LQD",
    # MBS
    "MBB", "GOVT",
    # muni
    "MUB",
    # currency carry ETFs
    "FXA", "FXY", "FXE", "FXB", "FXF", "UUP",
]


def probe(t: str) -> dict:
    try:
        tk = yf.Ticker(t)
        hist = tk.history(period="max", auto_adjust=False, actions=True)
        if hist.empty:
            return {"ticker": t, "ok": False, "rows": 0, "note": "empty history"}
        divs = hist["Dividends"] if "Dividends" in hist.columns else None
        nonzero_divs = int((divs > 0).sum()) if divs is not None else 0
        splits = hist["Stock Splits"] if "Stock Splits" in hist.columns else None
        nonzero_splits = int((splits != 0).sum()) if splits is not None else 0
        first = hist.index[0]
        last = hist.index[-1]
        # sample first/last 3 rows, Close + dividend only
        head = hist[["Close", "Dividends"]].head(3)
        tail = hist[["Close", "Dividends"]].tail(3)
        return {
            "ticker": t,
            "ok": True,
            "rows": int(len(hist)),
            "first_date": str(first.date()),
            "last_date": str(last.date()),
            "nonzero_dividend_rows": nonzero_divs,
            "nonzero_split_rows": nonzero_splits,
            "head_close": [round(float(x), 4) for x in head["Close"].tolist()],
            "tail_close": [round(float(x), 4) for x in tail["Close"].tolist()],
        }
    except Exception as e:  # noqa: BLE001
        return {"ticker": t, "ok": False, "error": str(e)[:300]}


def main() -> None:
    res = {}
    for t in TICKERS:
        res[t] = probe(t)
        print(t, res[t].get("ok"), res[t].get("rows"), res[t].get("first_date"), res[t].get("error", ""))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, default=str))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
