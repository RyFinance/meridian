"""Development-only evaluator for a BTC slow-trend / MSTR long-cash strategy.

The program intentionally refuses to write a grid outside the 2020--2022
development range.  Validation is run by a separately created frozen-rule
script after the rule selection is registered in FROZEN_RULES.md.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
PANEL_PATH = HERE.parent / "premium" / "panel.parquet"
DEV_START = pd.Timestamp("2020-08-11")
DEV_END = pd.Timestamp("2022-12-30")


@dataclass(frozen=True)
class Result:
    lookback: int
    stress: float
    days: int
    entries: int
    exits: int
    exposure: float
    total_return: float
    annualized_return: float
    sharpe: float
    max_drawdown: float
    annual_2021: float
    annual_2022: float


def load_panel() -> pd.DataFrame:
    data = pd.read_parquet(PANEL_PATH).copy()
    data.index = pd.to_datetime(data.index).normalize()
    if not {"btc", "mstr_open"}.issubset(data.columns):
        raise ValueError("The expected BTC 16:00 and MSTR official-open columns are missing")
    return data.sort_index()


def simulate(
    data: pd.DataFrame,
    lookback: int,
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    slippage_bp: float,
    commission_per_share: float,
) -> tuple[pd.DataFrame, Result]:
    """Simulate independent long/cash evaluation bounded at each period end.

    A signal known after the session-t close controls the position from the
    next open to the following open.  Resetting to cash at `start` and `end`
    makes development and validation independently executable and prevents a
    return after `end` from entering the reported interval.
    """

    d = data.copy()
    d["signal"] = (d["btc"] > d["btc"].rolling(lookback, min_periods=lookback).mean()).astype(int)
    records: list[dict[str, object]] = []
    indices = list(d.index)
    # i signal -> enter i+1 open -> exit i+2 open, so all prices / timing are known.
    for i in range(len(d) - 2):
        entry_date, exit_date = indices[i + 1], indices[i + 2]
        if entry_date < start or exit_date > end:
            continue
        entry_px = float(d["mstr_open"].iloc[i + 1])
        exit_px = float(d["mstr_open"].iloc[i + 2])
        if not (np.isfinite(entry_px) and np.isfinite(exit_px) and entry_px > 0 and exit_px > 0):
            continue
        records.append(
            {
                "signal_date": indices[i],
                "entry_date": entry_date,
                "exit_date": exit_date,
                "target": int(d["signal"].iloc[i]),
                "entry_px": entry_px,
                "exit_px": exit_px,
            }
        )
    trades = pd.DataFrame(records)
    if trades.empty:
        raise ValueError("No executable observations in requested period")

    previous_target = trades["target"].shift(fill_value=0)
    # One side of transaction cost for a cash<->long change at the entry auction.
    per_side_entry = slippage_bp / 1e4 + commission_per_share / trades["entry_px"]
    trades["sides"] = (trades["target"] - previous_target).abs()
    trades["gross"] = trades["target"] * (trades["exit_px"] / trades["entry_px"] - 1.0)
    trades["cost"] = trades["sides"] * per_side_entry
    # Standalone reporting closes any residual long at the endpoint.
    trades["terminal_exit"] = 0
    if int(trades.iloc[-1]["target"]) == 1:
        trades.loc[trades.index[-1], "cost"] += slippage_bp / 1e4 + commission_per_share / float(trades.iloc[-1]["exit_px"])
        trades.loc[trades.index[-1], "terminal_exit"] = 1
    trades["net"] = trades["gross"] - trades["cost"]
    trades["equity"] = (1.0 + trades["net"]).cumprod()
    trades["drawdown"] = trades["equity"] / trades["equity"].cummax() - 1.0
    trades["year"] = pd.to_datetime(trades["entry_date"]).dt.year

    annual = trades.groupby("year")["net"].apply(lambda x: (1.0 + x).prod() - 1.0)
    elapsed_years = max((pd.Timestamp(trades.iloc[-1]["exit_date"]) - pd.Timestamp(trades.iloc[0]["entry_date"])).days / 365.25, 1 / 365.25)
    result = Result(
        lookback=lookback,
        stress=slippage_bp / 3.0,
        days=len(trades),
        entries=int(((previous_target == 0) & (trades["target"] == 1)).sum()),
        exits=int(((previous_target == 1) & (trades["target"] == 0)).sum()) + int(trades["terminal_exit"].iloc[-1]),
        exposure=float(trades["target"].mean()),
        total_return=float(trades["equity"].iloc[-1] - 1.0),
        annualized_return=float(trades["equity"].iloc[-1] ** (1.0 / elapsed_years) - 1.0),
        sharpe=float(trades["net"].mean() / trades["net"].std(ddof=1) * np.sqrt(252)) if trades["net"].std(ddof=1) > 0 else np.nan,
        max_drawdown=float(trades["drawdown"].min()),
        annual_2021=float(annual.get(2021, np.nan)),
        annual_2022=float(annual.get(2022, np.nan)),
    )
    return trades, result


def main() -> None:
    data = load_panel()
    outcomes: list[dict[str, float | int]] = []
    for lookback in (20, 40, 60, 100, 150, 200):
        for stress, slippage_bp, commission in ((1.0, 3.0, 0.005), (2.0, 6.0, 0.010)):
            _, result = simulate(
                data,
                lookback,
                DEV_START,
                DEV_END,
                slippage_bp=slippage_bp,
                commission_per_share=commission,
            )
            row = asdict(result)
            row["stress"] = stress
            outcomes.append(row)
    output = pd.DataFrame(outcomes).sort_values(["stress", "lookback"])
    out_path = HERE / "dev_grid.csv"
    output.to_csv(out_path, index=False)
    print(output.round(6).to_string(index=False))
    print(f"\nWrote development-only grid: {out_path}")


if __name__ == "__main__":
    main()
