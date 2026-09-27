"""Archive raw TLT closes and corporate actions for option strike/payoff alignment."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/lse/structural_frontier"


def main() -> None:
    path = OUT / "TLT_spot_raw_2014_2022.parquet"
    if path.exists():
        raise SystemExit("Source archive already exists; no replacement")
    raw = yf.download("TLT", start="2014-05-01", end="2023-01-03",
                      auto_adjust=False, actions=True, progress=False, threads=False)
    if isinstance(raw.columns, pd.MultiIndex):
        raw = raw.xs("TLT", axis=1, level="Ticker")
    data = raw.reset_index().rename(columns={"Date": "date", "Adj Close": "adj_close",
                                             "Close": "close", "Open": "open", "High": "high",
                                             "Low": "low", "Volume": "volume", "Dividends": "dividends",
                                             "Stock Splits": "stock_splits", "Capital Gains": "capital_gains"})
    if data.empty or data.date.duplicated().any() or data.date.max() > pd.Timestamp("2022-12-30"):
        raise RuntimeError("Bad raw TLT spot extent")
    data.to_parquet(path, index=False)
    manifest = {"source": "yfinance TLT auto_adjust=False actions=True; official-session raw and adjusted closes",
                "rows": len(data), "first": str(data.date.min()), "last": str(data.date.max()),
                "nonzero_dividend_dates": int((data.dividends > 0).sum()),
                "nonzero_split_dates": int((data.stock_splits > 0).sum()),
                "sha256": sha256(path.read_bytes()).hexdigest()}
    (OUT / "TLT_spot_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
