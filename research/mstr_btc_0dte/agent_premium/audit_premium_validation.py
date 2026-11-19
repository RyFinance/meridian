"""Independent audit of the two preregistered MSTR/BTC premium-momentum candidates.

Run from quant_v7 with:
    PYTHONPATH=. .venv/bin/python research/mstr_btc_0dte/agent_premium/audit_premium_validation.py

This deliberately imports the frozen implementation rather than searching more
parameters.  It excludes trades with a missing executable price from inferential
statistics, reports base and doubled cost/carry stress, and writes no source data.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1] / "premium"
SPEC = importlib.util.spec_from_file_location("premium_momentum", ROOT / "momo.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Could not load frozen premium-momentum implementation")
MOMO = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOMO)

CANDIDATES = {
    "M1": {"L": 40, "Z": 1.0, "HOLD": 5},
    "M2": {"L": 40, "Z": 1.5, "HOLD": 10},
}


def summarize(trades: pd.DataFrame) -> dict[str, float | int]:
    valid = trades.dropna(subset=["gross", "net"]).copy()
    net = valid["net"]
    equity = (1.0 + net).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    return {
        "all_rows": len(trades),
        "valid_trades": len(valid),
        "missing_execution_rows": len(trades) - len(valid),
        "mean_bp": net.mean() * 1e4,
        "trade_t": net.mean() / net.std(ddof=1) * np.sqrt(len(net)),
        "sum_net": net.sum(),
        "compound": equity.iloc[-1] - 1.0,
        "max_drawdown": drawdown.min(),
        "win_rate": (net > 0).mean(),
        "avg_calendar_days": valid["days"].mean(),
    }


def main() -> None:
    for name, params in CANDIDATES.items():
        for stress in (1.0, 2.0):
            trades = MOMO.run(
                **params,
                start="2023-01-01",
                end="2026-08-10",
                stress=stress,
            )
            valid = trades.dropna(subset=["gross", "net"]).copy()
            print(f"\n{name}; stress={stress:g}")
            print(pd.Series(summarize(trades)).round(6).to_string())
            annual = (
                valid.assign(year=valid.entry.dt.year)
                .groupby("year")["net"]
                .agg(["count", "mean", "sum"])
            )
            print("Annual trade-return sums:")
            print(annual.round(6).to_string())


if __name__ == "__main__":
    main()
