#!/usr/bin/env python3
"""Research-only test of BTC off-hours moves versus US BTC-proxy O->C returns.

This is deliberately split into two stages.  `--stage dev` reads only dates through
2022-12-30 and writes exploratory diagnostics.  `--stage validate` refuses to run
unless given a frozen rule file, and then evaluates only 2023 onward.  No orders,
brokerage interfaces, or external downloads are used.

Input data are local, pre-existing research files.  The core BTC signal is known
before the US opening auction: the latest 1-minute BTC close at or before 09:28
America/New_York, divided by the latest close at or before 15:59 New York time on
the preceding session for that instrument.  The one-minute close convention avoids
using a still-forming 09:29/09:30 candle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


OUT = Path(__file__).resolve().parent
ROOT = Path("/Users/rytty/CCP")
BTC_PATH = ROOT / "BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet"
MSTR_YF_PATH = ROOT / "quant_v7/research/mstr_btc_0dte/mstr_daily_yf.parquet"
SEC_PRICE_DIR = ROOT / "quant_v7/data/sec_insider/prices"

DEV_END = pd.Timestamp("2022-12-30")
VAL_START = pd.Timestamp("2023-01-01")
BTC_TOLERANCE = pd.Timedelta(minutes=5)
NYSE_TZ = "America/New_York"
BASE_BP_PER_SIDE = 3.0
PER_SHARE_FEE = 0.005

# These are deliberately conservative proxy-start conventions, not IPO dates:
# all are well after the respective business/pivot date, except MSTR whose BTC
# treasury began 2020-08-11.  IBIT is excluded because its 2024 inception leaves
# no pre-2023 development history under this protocol.
UNIVERSE_STARTS = {
    "MSTR": "2020-08-12",
    "MARA": "2020-08-12",
    "RIOT": "2020-08-12",
    "CLSK": "2021-01-04",
    "COIN": "2021-04-14",
}
BASKETS = {
    "MSTR": ["MSTR"],
    "MARA": ["MARA"],
    "RIOT": ["RIOT"],
    "CLSK": ["CLSK"],
    "COIN": ["COIN"],
    "MINERS": ["MARA", "RIOT", "CLSK"],
    "ALL_PROXIES": ["MSTR", "MARA", "RIOT", "CLSK", "COIN"],
}


def localize_market_time(dates: pd.Series, hour: int, minute: int) -> pd.Series:
    """Turn date-only NYSE session dates into timezone-aware UTC timestamps."""
    dt = pd.to_datetime(dates).dt.normalize() + pd.Timedelta(hours=hour, minutes=minute)
    return dt.dt.tz_localize(NYSE_TZ).dt.tz_convert("UTC")


def read_equity(name: str) -> pd.DataFrame:
    if name == "MSTR":
        raw = pd.read_parquet(MSTR_YF_PATH).reset_index()
        # The index name is Date in the local YF artifact.
        raw = raw.rename(columns={
            "Date": "date", "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        })
        raw["splits"] = 0.0  # split metadata not retained in this local artifact
    else:
        raw = pd.read_parquet(SEC_PRICE_DIR / f"{name}.parquet")
    keep = ["date", "open", "high", "low", "close", "volume", "splits"]
    raw = raw[[c for c in keep if c in raw.columns]].copy()
    raw["date"] = pd.to_datetime(raw["date"]).dt.normalize()
    for col in ("open", "high", "low", "close", "volume"):
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    if "splits" not in raw:
        raw["splits"] = 0.0
    raw = raw.sort_values("date").drop_duplicates("date", keep="last")
    raw = raw.loc[raw["date"] >= pd.Timestamp(UNIVERSE_STARTS[name])].copy()
    # Prices must be usable at both auctions; zero-volume/stale rows are excluded.
    raw = raw.loc[(raw["open"] > 1) & (raw["close"] > 1) & (raw["volume"] > 0)].copy()
    raw["name"] = name
    raw["prev_date"] = raw["date"].shift(1)
    raw["prev_close"] = raw["close"].shift(1)
    raw["gap"] = raw["open"] / raw["prev_close"] - 1.0
    raw["oc_gross"] = raw["close"] / raw["open"] - 1.0
    return raw


def read_btc() -> tuple[pd.DataFrame, dict]:
    btc = pd.read_parquet(BTC_PATH, columns=["timestamp", "close"])
    # The parquet source uses microsecond precision; merge_asof requires an
    # exact dtype match with the nanosecond timestamps made from NYSE dates.
    btc["timestamp"] = pd.to_datetime(btc["timestamp"], utc=True).astype("datetime64[ns, UTC]")
    btc["close"] = pd.to_numeric(btc["close"], errors="coerce")
    raw_rows = len(btc)
    btc = btc.dropna(subset=["timestamp", "close"]).sort_values("timestamp")
    dupes = int(btc["timestamp"].duplicated().sum())
    # Retain the last record at a duplicated timestamp only if a future refresh
    # introduces duplicates. Current file has none (reported in provenance).
    btc = btc.drop_duplicates("timestamp", keep="last")
    meta = {
        "path": str(BTC_PATH),
        "raw_rows": raw_rows,
        "rows_after_clean": len(btc),
        "duplicate_timestamps_removed": dupes,
        "start_utc": str(btc["timestamp"].min()),
        "end_utc": str(btc["timestamp"].max()),
    }
    return btc, meta


def merge_btc_asof(left: pd.DataFrame, btc: pd.DataFrame, target_col: str, out_prefix: str) -> pd.DataFrame:
    left = left.copy()
    left["_merge_row"] = np.arange(len(left))
    right = btc.rename(columns={"timestamp": f"{out_prefix}_ts", "close": f"{out_prefix}_px"})
    valid = left.loc[left[target_col].notna()].sort_values(target_col).copy()
    matched = pd.merge_asof(
        valid,
        right.sort_values(f"{out_prefix}_ts"),
        left_on=target_col,
        right_on=f"{out_prefix}_ts",
        direction="backward",
        tolerance=BTC_TOLERANCE,
    )
    result = left.set_index("_merge_row")
    matched = matched.set_index("_merge_row")
    result[f"{out_prefix}_ts"] = matched[f"{out_prefix}_ts"]
    result[f"{out_prefix}_px"] = matched[f"{out_prefix}_px"]
    result[f"{out_prefix}_age_min"] = (
        (result[target_col] - result[f"{out_prefix}_ts"]).dt.total_seconds() / 60.0
    )
    return result.reset_index(drop=True)


def build_panel() -> tuple[pd.DataFrame, dict]:
    btc, btc_meta = read_btc()
    frames = []
    for name in UNIVERSE_STARTS:
        eq = read_equity(name)
        # previous session 15:59 and current session 09:28.  For first traded
        # session `prev_date` is null and drops out naturally.
        eq["btc_prev_target"] = localize_market_time(eq["prev_date"], 15, 59)
        eq["btc_open_target"] = localize_market_time(eq["date"], 9, 28)
        eq = merge_btc_asof(eq, btc, "btc_prev_target", "btc_prev")
        eq = merge_btc_asof(eq, btc, "btc_open_target", "btc_open")
        eq["btc_off"] = eq["btc_open_px"] / eq["btc_prev_px"] - 1.0
        # A split date can create a mechanical gap diagnostic; it never enters
        # the executable rule, but omit it from underreaction statistics.
        eq["valid_gap_diag"] = eq["splits"].fillna(0).eq(0) & eq["gap"].abs().lt(0.50)
        frames.append(eq)
    panel = pd.concat(frames, ignore_index=True).sort_values(["date", "name"])
    panel = panel.replace([np.inf, -np.inf], np.nan)
    panel["valid_signal"] = (
        panel["btc_off"].notna()
        & panel["btc_prev_age_min"].le(BTC_TOLERANCE / pd.Timedelta(minutes=1))
        & panel["btc_open_age_min"].le(BTC_TOLERANCE / pd.Timedelta(minutes=1))
    )
    input_paths = {"btc": str(BTC_PATH), "mstr": str(MSTR_YF_PATH)}
    input_paths.update({name: str(SEC_PRICE_DIR / f"{name}.parquet") for name in UNIVERSE_STARTS if name != "MSTR"})
    provenance = {
        "input_paths": input_paths,
        "btc": btc_meta,
        "panel_rows": len(panel),
        "panel_date_start": str(panel["date"].min().date()),
        "panel_date_end": str(panel["date"].max().date()),
        "valid_signal_rows": int(panel["valid_signal"].sum()),
        "invalid_signal_rows": int((~panel["valid_signal"]).sum()),
        "btc_target_max_age_minutes": {
            "prev_close": float(panel["btc_prev_age_min"].max()),
            "open": float(panel["btc_open_age_min"].max()),
        },
    }
    return panel, provenance


def net_trade_return(open_px: pd.Series | float, close_px: pd.Series | float, bp_per_side: float) -> pd.Series | float:
    """Long O->C return after $0.005/share + bp auction cost per side."""
    fee = PER_SHARE_FEE
    bp = bp_per_side / 10_000.0
    return ((np.asarray(close_px) * (1.0 - bp) - fee) / (np.asarray(open_px) * (1.0 + bp) + fee)) - 1.0


def perf_from_daily(daily: pd.DataFrame, date_col: str = "date") -> dict:
    """Daily zero-filled strategy returns; all statistics use tradeable sessions."""
    r = daily["portfolio_ret"].to_numpy(dtype=float)
    invested = daily["n_legs"].to_numpy(dtype=int) > 0
    wealth = np.cumprod(1.0 + r)
    running_peak = np.maximum.accumulate(np.r_[1.0, wealth])[:-1]
    dd = wealth / running_peak - 1.0
    sample_days = len(daily)
    trade_days = int(invested.sum())
    total_legs = int(daily["n_legs"].sum())
    if sample_days and np.std(r, ddof=1) > 0:
        sharpe = float(np.mean(r) / np.std(r, ddof=1) * np.sqrt(252.0))
    else:
        sharpe = np.nan
    years = max(sample_days / 252.0, 1e-12)
    compound = float(wealth[-1] - 1.0) if len(wealth) else np.nan
    ann_return = float((wealth[-1] ** (1.0 / years)) - 1.0) if len(wealth) else np.nan
    win_rate = float((daily.loc[invested, "portfolio_ret"] > 0).mean()) if trade_days else np.nan
    return {
        "sample_start": str(pd.Timestamp(daily[date_col].min()).date()) if sample_days else None,
        "sample_end": str(pd.Timestamp(daily[date_col].max()).date()) if sample_days else None,
        "sessions": sample_days,
        "trade_days": trade_days,
        "position_legs": total_legs,
        "exposure_pct": 100.0 * trade_days / sample_days if sample_days else np.nan,
        "net_compound_pct": 100.0 * compound,
        "annualized_return_pct": 100.0 * ann_return,
        "annualized_sharpe": sharpe,
        "max_drawdown_pct": 100.0 * float(np.min(dd)) if len(dd) else np.nan,
        "win_rate_pct": 100.0 * win_rate if not math.isnan(win_rate) else np.nan,
        "mean_trade_day_ret_bp": 10_000.0 * float(daily.loc[invested, "portfolio_ret"].mean()) if trade_days else np.nan,
        "median_trade_day_ret_bp": 10_000.0 * float(daily.loc[invested, "portfolio_ret"].median()) if trade_days else np.nan,
    }


def make_strategy_daily(
    panel: pd.DataFrame,
    names: Iterable[str],
    threshold: float,
    side: str = "long",
    bp_per_side: float = BASE_BP_PER_SIDE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Equal-weight only names that are live and have the common BTC signal."""
    names = list(names)
    # Keep every eligible equity session in the return series.  A missing/stale
    # BTC observation is an explicit no-trade (zero return), not a conveniently
    # omitted calendar day.
    x = panel.loc[panel["name"].isin(names)].copy()
    # Do not extend a backtest beyond the BTC source's last usable observation.
    # Any occasional unusable observation *inside* the covered sample remains a
    # zero-return no-trade in the daily series.
    usable_dates = x.loc[x["valid_signal"], "date"]
    if usable_dates.empty:
        raise ValueError(f"No usable BTC signal dates for {names}")
    x = x.loc[(x["date"] >= usable_dates.min()) & (x["date"] <= usable_dates.max())].copy()
    if side != "long":
        raise ValueError("This research deliberately permits long-only rules; no naked short candidate.")
    x["signal"] = x["valid_signal"] & x["btc_off"].ge(threshold)
    x["net_ret"] = net_trade_return(x["open"], x["close"], bp_per_side)
    x["net_ret"] = x["net_ret"].where(x["signal"])
    # A date can include fewer names early in the historical sample; equal
    # weights are re-normalized across names actually tradable that day.
    grouped = x.groupby("date", sort=True)
    daily = grouped.agg(
        portfolio_ret=("net_ret", "mean"),
        n_legs=("net_ret", lambda s: int(s.notna().sum())),
        mean_btc_off=("btc_off", "mean"),
    ).reset_index()
    daily["portfolio_ret"] = daily["portfolio_ret"].fillna(0.0)
    trades = x.loc[x["signal"], ["date", "name", "btc_off", "gap", "oc_gross", "open", "close", "net_ret"]].copy()
    return daily, trades


def rule_metric_row(panel: pd.DataFrame, basket: str, threshold: float, bp_per_side: float = BASE_BP_PER_SIDE) -> dict:
    daily, trades = make_strategy_daily(panel, BASKETS[basket], threshold, bp_per_side=bp_per_side)
    out = {"basket": basket, "threshold_pct": 100.0 * threshold, "bp_per_side": bp_per_side}
    out.update(perf_from_daily(daily))
    # Granular leg count and leg-level win rate make basket-size changes clear.
    out["leg_win_rate_pct"] = 100.0 * float((trades["net_ret"] > 0).mean()) if len(trades) else np.nan
    return out


def underreaction_diagnostics(panel: pd.DataFrame) -> pd.DataFrame:
    """Descriptive OLS slopes; never used as an executable opening-auction filter."""
    rows = []
    for name in UNIVERSE_STARTS:
        x = panel.loc[
            (panel["name"] == name)
            & panel["valid_signal"]
            & panel["valid_gap_diag"]
            & panel["btc_off"].ge(0.01)
        ].dropna(subset=["gap", "oc_gross", "btc_off"])
        if len(x) >= 10 and x["btc_off"].std() > 0:
            gap_slope = np.polyfit(x["btc_off"], x["gap"], 1)[0]
            oc_slope = np.polyfit(x["btc_off"], x["oc_gross"], 1)[0]
        else:
            gap_slope = oc_slope = np.nan
        rows.append({
            "name": name,
            "n_btc_off_ge_1pct": len(x),
            "mean_btc_off_pct": 100.0 * x["btc_off"].mean(),
            "mean_gap_pct": 100.0 * x["gap"].mean(),
            "mean_oc_pct": 100.0 * x["oc_gross"].mean(),
            "gap_slope_on_btc_off": gap_slope,
            "oc_slope_on_btc_off": oc_slope,
            "mean_gap_plus_oc_pct": 100.0 * (x["gap"] + x["oc_gross"]).mean(),
        })
    return pd.DataFrame(rows)


def write_csv(frame: pd.DataFrame, filename: str) -> None:
    frame.to_csv(OUT / filename, index=False, float_format="%.10g")


def run_dev() -> None:
    panel, provenance = build_panel()
    dev = panel.loc[panel["date"] <= DEV_END].copy()
    diagnostics = underreaction_diagnostics(dev)
    thresholds = [0.0, 0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05]
    grid = pd.DataFrame([
        rule_metric_row(dev, basket, threshold)
        for basket in BASKETS
        for threshold in thresholds
    ])
    grid = grid.sort_values(["annualized_sharpe", "net_compound_pct"], ascending=False)
    write_csv(diagnostics, "dev_underreaction_diagnostics.csv")
    write_csv(grid, "dev_open_to_close_grid.csv")
    # Minimal, reproducible summary of panel quality and date boundaries.
    provenance["development_cutoff"] = str(DEV_END.date())
    provenance["development_rows"] = len(dev)
    provenance["development_valid_signal_rows"] = int(dev["valid_signal"].sum())
    provenance["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (OUT / "dev_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print("Development-only outputs written:")
    print(OUT / "dev_underreaction_diagnostics.csv")
    print(OUT / "dev_open_to_close_grid.csv")
    print(OUT / "dev_provenance.json")
    print(grid.head(20).to_string(index=False))


def validate_rule(panel: pd.DataFrame, rule: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    expected = {"id", "basket", "threshold", "side", "execution", "costs"}
    missing = expected.difference(rule)
    if missing:
        raise ValueError(f"Frozen rule missing required fields: {sorted(missing)}")
    if rule["side"] != "long":
        raise ValueError("Only long rules are permitted in this research run.")
    if rule["basket"] not in BASKETS:
        raise ValueError(f"Unknown basket: {rule['basket']}")
    cost = rule["costs"]
    if cost.get("per_share_fee") != PER_SHARE_FEE or cost.get("auction_bp_per_side") != BASE_BP_PER_SIDE:
        raise ValueError("Frozen baseline cost must match the research protocol constants.")
    x = panel.loc[panel["date"] >= VAL_START].copy()
    daily, trades = make_strategy_daily(x, BASKETS[rule["basket"]], float(rule["threshold"]), bp_per_side=BASE_BP_PER_SIDE)
    metrics = perf_from_daily(daily)
    metrics.update({"id": rule["id"], "basket": rule["basket"], "threshold_pct": 100.0 * float(rule["threshold"])})
    return daily, trades, metrics


def adjacent_robustness(panel: pd.DataFrame, rule: dict) -> pd.DataFrame:
    x = panel.loc[panel["date"] >= VAL_START].copy()
    threshold = float(rule["threshold"])
    # Adjacent values are fixed around the selected signal threshold, rather than
    # being optimized on validation.  Minimum threshold is zero.
    nearby_thresholds = sorted({max(0.0, threshold - 0.005), threshold, threshold + 0.005})
    rows = []
    for t in nearby_thresholds:
        for bp in (BASE_BP_PER_SIDE, BASE_BP_PER_SIDE + 1.0, BASE_BP_PER_SIDE + 3.0):
            daily, _ = make_strategy_daily(x, BASKETS[rule["basket"]], t, bp_per_side=bp)
            row = {"id": rule["id"], "threshold_pct": 100.0 * t, "bp_per_side": bp}
            row.update(perf_from_daily(daily))
            rows.append(row)
    return pd.DataFrame(rows)


def run_validate(frozen_path: Path) -> None:
    frozen = json.loads(frozen_path.read_text())
    if not isinstance(frozen, list) or not frozen or len(frozen) > 3:
        raise ValueError("Frozen rule file must be a non-empty list of at most three rules.")
    panel, provenance = build_panel()
    baseline_rows = []
    annual_rows = []
    subperiod_rows = []
    robustness_rows = []
    all_trades = []
    all_daily = []
    for rule in frozen:
        daily, trades, metric = validate_rule(panel, rule)
        baseline_rows.append(metric)
        d = daily.copy()
        d["id"] = rule["id"]
        all_daily.append(d)
        t = trades.copy()
        t["id"] = rule["id"]
        all_trades.append(t)
        for year, y in daily.assign(year=daily["date"].dt.year).groupby("year"):
            row = {"id": rule["id"], "period": str(year)}
            row.update(perf_from_daily(y))
            annual_rows.append(row)
        # Fixed, ex-ante date blocks: regime split instead of selecting periods
        # around outcomes.  The final block is partial because BTC ends Aug-2026.
        for label, start, end in [
            ("2023", "2023-01-01", "2023-12-31"),
            ("2024", "2024-01-01", "2024-12-31"),
            ("2025", "2025-01-01", "2025-12-31"),
            ("2026_to_btc_end", "2026-01-01", "2026-12-31"),
        ]:
            z = daily.loc[(daily["date"] >= start) & (daily["date"] <= end)]
            if len(z):
                row = {"id": rule["id"], "period": label}
                row.update(perf_from_daily(z))
                subperiod_rows.append(row)
        robustness_rows.append(adjacent_robustness(panel, rule))
    write_csv(pd.DataFrame(baseline_rows), "validation_metrics.csv")
    write_csv(pd.DataFrame(annual_rows), "validation_annual.csv")
    write_csv(pd.DataFrame(subperiod_rows), "validation_subperiods.csv")
    write_csv(pd.concat(robustness_rows, ignore_index=True), "validation_cost_and_adjacent_robustness.csv")
    write_csv(pd.concat(all_trades, ignore_index=True), "validation_trades.csv")
    write_csv(pd.concat(all_daily, ignore_index=True), "validation_daily_returns.csv")
    provenance.update({
        "validation_start": str(VAL_START.date()),
        "frozen_rule_path": str(frozen_path),
        "frozen_rule_sha256": hashlib.sha256(frozen_path.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    })
    (OUT / "validation_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(pd.DataFrame(baseline_rows).to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("dev", "validate"), required=True)
    parser.add_argument("--frozen", type=Path, help="Required for --stage validate")
    args = parser.parse_args()
    if args.stage == "dev":
        if args.frozen:
            raise SystemExit("Development stage does not accept a frozen rules file.")
        run_dev()
    else:
        if not args.frozen:
            raise SystemExit("Validation requires --frozen PATH.")
        run_validate(args.frozen)


if __name__ == "__main__":
    main()
