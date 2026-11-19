"""Development-only return analysis for the SEC issuance event ledger.

The parquet read is predicate-filtered through 2023-12-29.  This program will
raise if any later price reaches memory, so it cannot inspect the sealed
2024–26 period while choosing a rule.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
DAILY = HERE.parents[1] / "mstr_daily_yf.parquet"
CUTOFF = pd.Timestamp("2023-12-29")
SLIPPAGE_BP = 3.0
COMMISSION = 0.005
SHORT_BORROW_ANNUAL = 0.30
HORIZONS = (1, 3, 5)
RNG = np.random.default_rng(20261017)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_dev_prices() -> pd.DataFrame:
    """Read only the development partition from parquet, then prove the cap."""
    raw = pd.read_parquet(DAILY, filters=[("Date", "<=", CUTOFF)])
    if "Date" in raw.columns:
        raw = raw.set_index("Date")
    raw.index = pd.DatetimeIndex(raw.index).normalize()
    raw = raw.sort_index()
    if raw.empty or raw.index.max() > CUTOFF:
        raise RuntimeError(f"development price fence violated: max={raw.index.max() if len(raw) else None}")
    required = {"Open", "Close"}
    if not required.issubset(raw.columns):
        raise RuntimeError(f"daily data missing {required - set(raw.columns)}")
    return raw.loc[:, ["Open", "Close"]].astype(float)


def entry_location(acceptance_utc: str, dates: pd.DatetimeIndex) -> int | None:
    timestamp = pd.Timestamp(acceptance_utc).tz_convert("America/New_York")
    local_day = timestamp.tz_localize(None).normalize()
    before_open_cutoff = (timestamp.hour, timestamp.minute, timestamp.second) < (9, 25, 0)
    eligible = dates[dates >= local_day] if before_open_cutoff else dates[dates > local_day]
    if len(eligible) == 0:
        return None
    return int(dates.get_loc(eligible[0]))


def directional_return(open_price: float, close_price: float, direction: str, sessions: int,
                       slippage_bp: float = SLIPPAGE_BP, commission: float = COMMISSION,
                       borrow_annual: float = SHORT_BORROW_ANNUAL) -> tuple[float, float]:
    """Net return on one share of capital, with directionally adverse execution."""
    slip = slippage_bp / 10_000.0
    if direction == "long":
        entry = open_price * (1.0 + slip) + commission
        exit_value = close_price * (1.0 - slip) - commission
        return exit_value / entry - 1.0, 0.0
    if direction == "short":
        sale_proceeds = open_price * (1.0 - slip) - commission
        cover = close_price * (1.0 + slip) + commission
        borrow = borrow_annual * sessions / 252.0
        # Normalize to gross entry notional, which is the capital posted for
        # an unlevered short.  Borrow is an explicit reduction to the return.
        return (sale_proceeds - cover) / (open_price * (1.0 - slip)) - borrow, borrow
    raise ValueError(direction)


def event_windows(events: pd.DataFrame, dates: pd.DatetimeIndex, horizon: int) -> set[pd.Timestamp]:
    blocked: set[pd.Timestamp] = set()
    for _, event in events.iterrows():
        loc = entry_location(event.acceptance_utc, dates)
        if loc is None or loc + horizon - 1 >= len(dates):
            continue
        blocked.update(dates[loc: loc + horizon])
    return blocked


def controls_for_event(daily: pd.DataFrame, blocked: set[pd.Timestamp], event_entry: int,
                       horizon: int, direction: str) -> np.ndarray:
    dates = pd.DatetimeIndex(daily.index)
    target_weekday = dates[event_entry].weekday()
    values: list[float] = []
    for loc in range(0, len(dates) - horizon + 1):
        span = dates[loc: loc + horizon]
        if dates[loc].weekday() != target_weekday or any(day in blocked for day in span):
            continue
        value, _ = directional_return(
            float(daily.iloc[loc].Open), float(daily.iloc[loc + horizon - 1].Close), direction, horizon
        )
        values.append(value)
    return np.asarray(values, dtype=float)


def stats(values: np.ndarray) -> dict[str, float | int]:
    if len(values) == 0:
        return {"n": 0, "mean": np.nan, "median": np.nan, "t_stat": np.nan, "ci_low": np.nan, "ci_high": np.nan}
    if len(values) == 1:
        return {"n": 1, "mean": float(values[0]), "median": float(values[0]), "t_stat": np.nan, "ci_low": float(values[0]), "ci_high": float(values[0])}
    bootstrap = RNG.choice(values, size=(25_000, len(values)), replace=True).mean(axis=1)
    standard_error = values.std(ddof=1) / np.sqrt(len(values))
    return {
        "n": int(len(values)),
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "t_stat": float(values.mean() / standard_error) if standard_error > 0 else np.nan,
        "ci_low": float(np.quantile(bootstrap, 0.025)),
        "ci_high": float(np.quantile(bootstrap, 0.975)),
    }


def main() -> None:
    daily = load_dev_prices()
    ledger = pd.read_csv(HERE / "event_ledger.csv")
    dev = ledger.loc[ledger["sample"] == "development_2020_2023"].copy()
    if not (pd.to_datetime(dev.filing_date) <= CUTOFF).all():
        raise RuntimeError("event ledger development fence violated")
    direction_by_family = {"convertible_initial": "long", "common_atm_initial": "short"}
    dev["direction"] = dev.family.map(direction_by_family)
    if dev.direction.isna().any():
        raise RuntimeError("unknown family direction")

    dates = pd.DatetimeIndex(daily.index)
    trades: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    controls_rows: list[dict[str, object]] = []
    for family, family_events in dev.groupby("family", sort=True):
        direction = direction_by_family[family]
        for horizon in HORIZONS:
            # A control cannot overlap *any* retained issuance event, even
            # one from the other issuance family.
            blocked = event_windows(dev, dates, horizon)
            family_trades: list[dict[str, object]] = []
            for _, event in family_events.iterrows():
                entry = entry_location(event.acceptance_utc, dates)
                if entry is None or entry + horizon - 1 >= len(dates):
                    continue
                exit_loc = entry + horizon - 1
                net_return, borrow = directional_return(
                    float(daily.iloc[entry].Open), float(daily.iloc[exit_loc].Close), direction, horizon
                )
                controls = controls_for_event(daily, blocked, entry, horizon, direction)
                control_mean = float(controls.mean()) if len(controls) else np.nan
                row = {
                    "event_id": event.event_id,
                    "family": family,
                    "direction": direction,
                    "horizon_sessions": horizon,
                    "acceptance_utc": event.acceptance_utc,
                    "entry_date": dates[entry].date().isoformat(),
                    "exit_date": dates[exit_loc].date().isoformat(),
                    "entry_open": float(daily.iloc[entry].Open),
                    "exit_close": float(daily.iloc[exit_loc].Close),
                    "net_return": net_return,
                    "borrow_return_cost": borrow,
                    "same_weekday_controls_n": int(len(controls)),
                    "same_weekday_control_mean": control_mean,
                    "matched_excess_return": net_return - control_mean,
                }
                trades.append(row)
                family_trades.append(row)
                controls_rows.append(
                    {
                        "event_id": event.event_id,
                        "family": family,
                        "direction": direction,
                        "horizon_sessions": horizon,
                        "entry_date": dates[entry].date().isoformat(),
                        "controls_n": int(len(controls)),
                        "controls_mean": control_mean,
                        "controls_median": float(np.median(controls)) if len(controls) else np.nan,
                    }
                )
            returns = np.asarray([row["net_return"] for row in family_trades], dtype=float)
            excesses = np.asarray([row["matched_excess_return"] for row in family_trades], dtype=float)
            positive_profit = returns[returns > 0.0]
            max_profit_share = float(positive_profit.max() / positive_profit.sum()) if len(positive_profit) else np.nan
            return_stats = stats(returns)
            excess_stats = stats(excesses)
            passes = (
                len(returns) >= 5
                and return_stats["mean"] > 0.0
                and excess_stats["mean"] > 0.0
                and max_profit_share <= 0.50
            )
            summaries.append(
                {
                    "family": family,
                    "direction": direction,
                    "horizon_sessions": horizon,
                    **{f"return_{k}": v for k, v in return_stats.items()},
                    **{f"excess_{k}": v for k, v in excess_stats.items()},
                    "max_positive_profit_share": max_profit_share,
                    "selection_screen_pass": bool(passes),
                }
            )
    trades_frame = pd.DataFrame(trades)
    summary_frame = pd.DataFrame(summaries).sort_values(["family", "horizon_sessions"])
    controls_frame = pd.DataFrame(controls_rows)
    trades_frame.to_csv(HERE / "development_event_trades.csv", index=False)
    controls_frame.to_csv(HERE / "development_matched_controls.csv", index=False)
    summary_frame.to_csv(HERE / "development_candidate_summary.csv", index=False)
    manifest = {
        "price_file": str(DAILY),
        "price_sha256": sha256(DAILY),
        "development_cutoff": CUTOFF.date().isoformat(),
        "development_rows_read": int(len(daily)),
        "development_price_first_date": dates.min().date().isoformat(),
        "development_price_last_date": dates.max().date().isoformat(),
        "slippage_bp_each_side": SLIPPAGE_BP,
        "commission_per_share_each_side": COMMISSION,
        "short_borrow_annual": SHORT_BORROW_ANNUAL,
        "horizons_sessions": list(HORIZONS),
        "qualifying_rules": summary_frame.loc[summary_frame.selection_screen_pass, ["family", "horizon_sessions"]].to_dict("records"),
    }
    (HERE / "development_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(summary_frame.to_string(index=False))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
