"""Development-only BTC weekly-momentum conditioned MSTR weekend-gap screen."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
PANEL = HERE.parent / "premium" / "panel.parquet"
START = pd.Timestamp("2020-08-11")
END = pd.Timestamp("2022-12-30")


@dataclass(frozen=True)
class Metrics:
    lookback: int
    stress: float
    n_fridays: int
    n_trades: int
    mean_net_bp: float
    trade_t: float
    win_rate: float
    compounded: float
    max_drawdown: float
    y2021: float
    y2022: float


def weekend_trades(lookback: int, slippage_bp: float, commission: float) -> tuple[pd.DataFrame, Metrics]:
    d = pd.read_parquet(PANEL).copy()
    d.index = pd.to_datetime(d.index).normalize()
    d = d.sort_index()
    d["btc_return"] = d["btc"].pct_change(lookback)
    rows: list[dict[str, object]] = []
    index = list(d.index)
    for i, date in enumerate(index[:-1]):
        # Friday close signal; next listed session is the executable exit open.
        if date.weekday() != 4 or date < START or date > END:
            continue
        exit_date = index[i + 1]
        if exit_date > END:
            continue
        entry_px = float(d["mstr"].iloc[i])
        exit_px = float(d["mstr_open"].iloc[i + 1])
        signal = bool(d["btc_return"].iloc[i] > 0)
        if not (np.isfinite(entry_px) and np.isfinite(exit_px) and entry_px > 0 and exit_px > 0):
            continue
        gross = (exit_px / entry_px - 1.0) if signal else 0.0
        if signal:
            cost = 2.0 * (slippage_bp / 1e4) + commission / entry_px + commission / exit_px
        else:
            cost = 0.0
        rows.append(
            {
                "signal_date": date,
                "exit_date": exit_date,
                "signal": signal,
                "btc_return": float(d["btc_return"].iloc[i]),
                "gross": gross,
                "net": gross - cost,
            }
        )
    trades = pd.DataFrame(rows)
    selected = trades[trades.signal].copy()
    if selected.empty:
        raise ValueError("No selected weekend trades")
    selected["year"] = selected.signal_date.dt.year
    selected["equity"] = (1.0 + selected.net).cumprod()
    selected["drawdown"] = selected.equity / selected.equity.cummax() - 1.0
    annual = selected.groupby("year").net.apply(lambda x: (1.0 + x).prod() - 1.0)
    x = selected.net
    metrics = Metrics(
        lookback=lookback,
        stress=slippage_bp / 3.0,
        n_fridays=len(trades),
        n_trades=len(selected),
        mean_net_bp=float(x.mean() * 1e4),
        trade_t=float(x.mean() / x.std(ddof=1) * np.sqrt(len(x))),
        win_rate=float((x > 0).mean()),
        compounded=float(selected.equity.iloc[-1] - 1.0),
        max_drawdown=float(selected.drawdown.min()),
        y2021=float(annual.get(2021, np.nan)),
        y2022=float(annual.get(2022, np.nan)),
    )
    return selected, metrics


def main() -> None:
    output = []
    for lookback in (5, 10, 20):
        for stress, slippage, commission in ((1.0, 3.0, 0.005), (2.0, 6.0, 0.010)):
            _, metrics = weekend_trades(lookback, slippage, commission)
            row = asdict(metrics)
            row["stress"] = stress
            output.append(row)
    grid = pd.DataFrame(output).sort_values(["stress", "lookback"])
    path = HERE / "dev_grid.csv"
    grid.to_csv(path, index=False)
    print(grid.round(6).to_string(index=False))
    print(f"\nWrote development-only grid: {path}")


if __name__ == "__main__":
    main()
