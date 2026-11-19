#!/usr/bin/env python3
"""Strictly causal post-primary-source extension audit for frozen mNAV M1.

This is intentionally an *extension audit*, not another parameter search.  It
does not alter any artifact under ``agent_mnav`` and it has no brokerage or
order-submission code.

Key conservative choices:
* The daily decision uses the close of the BTC minute bar *opened* at 15:59
  America/New_York.  Its documented end is 15:59:59.999, so it is completed
  no later than the MSTR 16:00 close.  A 16:00-labelled BTC bar is never used.
* The original BTC source supplies only sessions through 2026-08-10.  Binance
  BTCUSDT perpetual minute data supplies later 15:59 completed bars.  There is
  no interpolation or forward-filled BTC quote.
* Once the local Binance archive ends, the frozen rule's specified gap policy
  carries the prior stance while recording actual MSTR open-to-open results.
* SEC values come only from the authoritative, pre-existing ledger and become
  available on the first MSTR session strictly after the filing date.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


OUT = Path(__file__).resolve().parent
TRACK = OUT.parent / "agent_mnav"
PROJECT = OUT.parent
QUANT_V7 = PROJECT.parents[1]
CCP_ROOT = PROJECT.parents[2]
PRIMARY_BTC = CCP_ROOT / "BTC-Acum" / "data" / "btc_usd_1m_candles_polymarket_arb.parquet"
MSTR_DAILY = PROJECT / "mstr_daily_yf.parquet"
BINANCE_DIR = QUANT_V7 / "data" / "binance_mstr_token"
LEDGER = TRACK / "ALL_SEC_OBSERVATIONS.csv"
FROZEN = TRACK / "FROZEN_RULES.json"
AMENDMENT = TRACK / "FROZEN_RULES_AMENDMENT_01.json"

NY = "America/New_York"
SPLIT_DATE = pd.Timestamp("2024-08-08")
PRIMARY_LAST_SESSION = pd.Timestamp("2026-08-10")
EXTENSION_START = pd.Timestamp("2026-08-11")
BASELINE_BPS = 3.0
BASELINE_COMMISSION = 0.005


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(name: str, value: Any) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def to_jsonable(value: Any) -> Any:
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def mstr_prices() -> pd.DataFrame:
    price = pd.read_parquet(MSTR_DAILY).sort_index().copy()
    price.index = pd.DatetimeIndex(price.index).normalize()
    price.index.name = "date"
    return price[["Open", "Close"]].rename(columns={"Open": "mstr_open", "Close": "mstr_close"})


def exact_primary_1559(sessions: pd.DatetimeIndex) -> pd.DataFrame:
    """Read only exact 15:59 ET labelled primary bars, without fallback."""

    raw = pd.read_parquet(PRIMARY_BTC, columns=["timestamp", "close"]).dropna()
    raw = raw.sort_values("timestamp")
    if raw["timestamp"].duplicated().any():
        raise ValueError("Primary BTC input has duplicate timestamps")
    local = raw["timestamp"].dt.tz_convert(NY)
    take = (local.dt.hour == 15) & (local.dt.minute == 59)
    bars = raw.loc[take, ["timestamp", "close"]].copy()
    bars["date"] = bars["timestamp"].dt.tz_convert(NY).dt.tz_localize(None).dt.normalize()
    if bars["date"].duplicated().any():
        raise ValueError("Primary input has multiple 15:59 bars on one local date")
    result = bars.set_index("date")[["close"]].rename(columns={"close": "btc_primary_1559"})
    return result.reindex(sessions)


def exact_binance_1559(sessions: pd.DatetimeIndex) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Read completed Binance 15:59 ET BTCUSDT minute bars from local archives."""

    zips = sorted(BINANCE_DIR.glob("BTCUSDT-1m-*.zip"))
    if not zips:
        raise FileNotFoundError(f"No BTCUSDT minute archives in {BINANCE_DIR}")
    parts: list[pd.DataFrame] = []
    archive_info: list[dict[str, Any]] = []
    for zip_path in zips:
        frame = pd.read_csv(zip_path, compression="zip", usecols=["open_time", "close_time", "close"])
        frame["open_ts"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
        frame["close_ts"] = pd.to_datetime(frame["close_time"], unit="ms", utc=True)
        local = frame["open_ts"].dt.tz_convert(NY)
        take = (local.dt.hour == 15) & (local.dt.minute == 59)
        bars = frame.loc[take, ["open_time", "close_time", "open_ts", "close_ts", "close"]].copy()
        bars["date"] = bars["open_ts"].dt.tz_convert(NY).dt.tz_localize(None).dt.normalize()
        # A 15:59 bar must close at/before the 16:00 target.  This asserts our
        # intended "completed bar" convention instead of trusting the label.
        targets = (
            pd.DatetimeIndex(bars["date"]).tz_localize(NY).normalize() + pd.Timedelta(hours=16)
        ).tz_convert("UTC")
        if not (pd.DatetimeIndex(bars["close_ts"]) <= targets).all():
            raise ValueError(f"An allegedly completed 15:59 Binance bar exceeds 16:00 in {zip_path.name}")
        parts.append(bars)
        archive_info.append(
            {
                "file": zip_path.name,
                "sha256": sha256(zip_path),
                "raw_rows": int(len(frame)),
                "completed_1559_rows": int(len(bars)),
                "utc_open_min": str(frame["open_ts"].min()),
                "utc_open_max": str(frame["open_ts"].max()),
            }
        )
    all_bars = pd.concat(parts, ignore_index=True).sort_values("open_ts")
    if all_bars["open_time"].duplicated().any() or all_bars["date"].duplicated().any():
        duplicates = all_bars.loc[all_bars["date"].duplicated(keep=False), "date"].astype(str).tolist()
        raise ValueError(f"Duplicate Binance 15:59 date(s): {duplicates[:5]}")
    result = all_bars.set_index("date")[["close"]].rename(columns={"close": "btc_binance_1559"})
    return result.reindex(sessions), {"archives": archive_info}


def apply_sec_ledger(panel: pd.DataFrame) -> pd.DataFrame:
    ledger = pd.read_csv(LEDGER, parse_dates=["filing_date", "share_asof", "btc_asof"]).sort_values("filing_date")
    expected = {
        "filing_date",
        "share_asof",
        "class_a_shares",
        "class_b_shares",
        "btc_held",
    }
    missing = expected - set(ledger.columns)
    if missing:
        raise ValueError(f"Authoritative SEC ledger lacks {sorted(missing)}")
    out = panel.copy()
    for name in [
        "btc_held",
        "class_a_shares",
        "class_b_shares",
        "observation_filing_date",
        "observation_share_asof",
    ]:
        out[name] = np.nan if name not in {"observation_filing_date", "observation_share_asof"} else pd.NaT
    availability: list[dict[str, str]] = []
    for row in ledger.itertuples(index=False):
        filing = pd.Timestamp(row.filing_date).normalize()
        later = out.index[out.index > filing]
        if later.empty:
            continue
        available = later[0]
        mask = out.index >= available
        out.loc[mask, "btc_held"] = int(row.btc_held)
        out.loc[mask, "class_a_shares"] = int(row.class_a_shares)
        out.loc[mask, "class_b_shares"] = int(row.class_b_shares)
        out.loc[mask, "observation_filing_date"] = filing
        out.loc[mask, "observation_share_asof"] = pd.Timestamp(row.share_asof).normalize()
        availability.append(
            {
                "filing_date": str(filing.date()),
                "first_usable_mstr_close": str(available.date()),
                "share_asof": str(pd.Timestamp(row.share_asof).date()),
                "btc_asof": str(pd.Timestamp(row.btc_asof).date()),
            }
        )
    pd.DataFrame(availability).to_csv(OUT / "sec_availability_audit.csv", index=False)
    out["total_common_shares_reported"] = out["class_a_shares"] + out["class_b_shares"]
    out["split_factor_to_price_basis"] = np.where(out["observation_share_asof"] < SPLIT_DATE, 10.0, 1.0)
    out["total_common_shares_price_basis"] = out["total_common_shares_reported"] * out["split_factor_to_price_basis"]
    return out


def add_proxy(panel: pd.DataFrame, btc_column: str) -> pd.DataFrame:
    out = panel.copy()
    out["btc_close_1559"] = out[btc_column]
    out["gross_btc_mnav_proxy"] = (
        out["mstr_close"]
        * out["total_common_shares_price_basis"]
        / (out["btc_held"] * out["btc_close_1559"])
    )
    out["log_gross_btc_mnav_proxy"] = np.log(out["gross_btc_mnav_proxy"])
    return out


def frozen_m1_signal(panel: pd.DataFrame) -> pd.Series:
    """Exactly frozen M1: 10d gross-premium momentum + 50d proxy trend."""

    log_p = panel["log_gross_btc_mnav_proxy"]
    momentum = log_p - log_p.shift(10)
    above_sma = log_p > log_p.rolling(50).mean()
    valid = momentum.notna() & above_sma.notna()
    raw = (momentum > 0.0) & above_sma
    return raw.astype("boolean").where(valid).ffill().fillna(False).astype(bool)


def simulate_cash_rebased(
    panel: pd.DataFrame,
    signal: pd.Series,
    *,
    start_long: bool,
    slippage_bps_each_side: float = BASELINE_BPS,
    commission_per_actual_share: float = BASELINE_COMMISSION,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cash-rebased causal next-open M1 simulation with all entry/exit costs.

    The reset starts just before the first extension open.  If M1 was already
    long, this deliberately charges a new entry at that opening price; it is a
    conservative and easy-to-audit way to state standalone forward P&L.
    """

    signal = signal.reindex(panel.index).fillna(False).astype(bool)
    cash, shares = 1.0, 0.0
    slip = slippage_bps_each_side / 10_000.0
    rows: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    for i, (date, row) in enumerate(panel.iterrows()):
        desired = bool(start_long) if i == 0 else bool(signal.iloc[i - 1])
        price = float(row.mstr_open)
        # All extension dates occur after the 2024 split, but retain the
        # frozen actual-share convention for correctness if this is reused.
        commission = commission_per_actual_share / (10.0 if date < SPLIT_DATE else 1.0)
        was_long = shares > 0.0
        action = "hold_long" if was_long else "hold_cash"
        if desired and not was_long:
            execution = price * (1.0 + slip) + commission
            before = cash
            shares = cash / execution
            cash = 0.0
            action = "buy"
            trades.append(
                {
                    "date": date,
                    "side": "buy",
                    "mid_open": price,
                    "execution_price": execution,
                    "portfolio_before": before,
                    "portfolio_after": shares * price,
                }
            )
        elif not desired and was_long:
            execution = price * (1.0 - slip) - commission
            before = shares * price
            cash = shares * execution
            shares = 0.0
            action = "sell"
            trades.append(
                {
                    "date": date,
                    "side": "sell",
                    "mid_open": price,
                    "execution_price": execution,
                    "portfolio_before": before,
                    "portfolio_after": cash,
                }
            )
        nav = cash + shares * price
        rows.append(
            {
                "date": date,
                "nav": nav,
                "long_after_open": int(shares > 0.0),
                "signal_prior_close": int(desired),
                "signal_same_close": int(signal.iloc[i]),
                "execution_action": action,
                "btc_source": row.get("btc_source", "unknown"),
                "btc_close_1559": row.get("btc_close_1559", np.nan),
            }
        )
    # Fully realize at the last included open with the same cost model.
    if shares > 0.0:
        date = panel.index[-1]
        price = float(panel.iloc[-1].mstr_open)
        commission = commission_per_actual_share / (10.0 if date < SPLIT_DATE else 1.0)
        execution = price * (1.0 - slip) - commission
        before = shares * price
        cash = shares * execution
        trades.append(
            {
                "date": date,
                "side": "sell_forced_final_open",
                "mid_open": price,
                "execution_price": execution,
                "portfolio_before": before,
                "portfolio_after": cash,
            }
        )
        rows[-1]["nav"] = cash
        rows[-1]["long_after_open"] = 0
        rows[-1]["execution_action"] = str(rows[-1]["execution_action"]) + "+forced_final_sell"
    return pd.DataFrame(rows).set_index("date"), pd.DataFrame(trades)


def metrics(trace: pd.DataFrame, trades: pd.DataFrame) -> dict[str, Any]:
    equity = trace["nav"]
    with_start = pd.concat([pd.Series([1.0], index=[equity.index[0] - pd.Timedelta(nanoseconds=1)]), equity])
    daily = with_start.pct_change().dropna()
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1.0 / 365.25)
    vol = daily.std(ddof=1)
    return {
        "start": str(equity.index[0].date()),
        "end": str(equity.index[-1].date()),
        "sessions": int(len(equity)),
        "total_return": float(equity.iloc[-1] - 1.0),
        "cagr": float(equity.iloc[-1] ** (1.0 / years) - 1.0),
        "annualized_sharpe": float(np.sqrt(252.0) * daily.mean() / vol) if vol > 0 else np.nan,
        "max_drawdown": float((with_start / with_start.cummax() - 1.0).min()),
        "entry_trades": int((trades["side"] == "buy").sum()) if not trades.empty else 0,
        "exit_trades": int(trades["side"].astype(str).str.startswith("sell").sum()) if not trades.empty else 0,
        "round_trips": int(min((trades["side"] == "buy").sum(), trades["side"].astype(str).str.startswith("sell").sum())) if not trades.empty else 0,
        "time_long": float(trace["signal_prior_close"].mean()),
    }


def source_summary(compare: pd.DataFrame, name: str) -> dict[str, Any]:
    complete = compare.dropna(subset=["btc_primary_1559", "btc_binance_1559"])
    diff_bp = (complete["btc_binance_1559"] / complete["btc_primary_1559"] - 1.0) * 10_000.0
    common_returns = complete[["btc_primary_1559", "btc_binance_1559"]].pct_change().dropna()
    if len(common_returns) > 1:
        return_corr = float(common_returns.iloc[:, 0].corr(common_returns.iloc[:, 1]))
    else:
        return_corr = np.nan
    agreement = complete["m1_primary_signal"] == complete["m1_binance_hybrid_signal"]
    return {
        "window": name,
        "mstr_sessions": int(len(compare)),
        "primary_exact_1559_covered": int(compare["btc_primary_1559"].notna().sum()),
        "binance_exact_1559_covered": int(compare["btc_binance_1559"].notna().sum()),
        "joint_covered": int(len(complete)),
        "mean_binance_minus_primary_bp": float(diff_bp.mean()) if len(diff_bp) else np.nan,
        "median_binance_minus_primary_bp": float(diff_bp.median()) if len(diff_bp) else np.nan,
        "p95_abs_price_difference_bp": float(diff_bp.abs().quantile(0.95)) if len(diff_bp) else np.nan,
        "max_abs_price_difference_bp": float(diff_bp.abs().max()) if len(diff_bp) else np.nan,
        "btc_return_correlation": return_corr,
        "m1_signal_agreement_joint_sessions": float(agreement.mean()) if len(agreement) else np.nan,
        "m1_signal_disagreements_joint_sessions": int((~agreement).sum()) if len(agreement) else 0,
    }


def main() -> None:
    frozen = json.loads(FROZEN.read_text())
    rule = next((item for item in frozen["rules"] if item["id"] == "M1"), None)
    if rule is None or int(rule["premium_momentum_days_L"]) != 10 or int(rule["premium_sma_days_S"]) != 50:
        raise AssertionError("This audit must run only frozen M1 (L=10, S=50)")
    if rule["btc_momentum_days"] is not None:
        raise AssertionError("Frozen M1 unexpectedly contains a BTC regime filter")

    price = mstr_prices()
    primary = exact_primary_1559(price.index)
    binance, binance_provenance = exact_binance_1559(price.index)
    raw = price.join(primary).join(binance)
    raw["btc_combined_1559"] = np.where(
        raw.index <= PRIMARY_LAST_SESSION, raw["btc_primary_1559"], raw["btc_binance_1559"]
    )
    raw["btc_source"] = np.select(
        [
            (raw.index <= PRIMARY_LAST_SESSION) & raw["btc_primary_1559"].notna(),
            (raw.index > PRIMARY_LAST_SESSION) & raw["btc_binance_1559"].notna(),
        ],
        ["primary_1559", "binance_1559"],
        default="missing_no_fill",
    )
    combined = apply_sec_ledger(raw)
    combined = add_proxy(combined, "btc_combined_1559")
    combined["m1_signal"] = frozen_m1_signal(combined)

    # Create source-consistency signal paths using the same mNAV mechanics.
    primary_panel = add_proxy(apply_sec_ledger(price.join(primary)), "btc_primary_1559")
    primary_panel["m1_primary_signal"] = frozen_m1_signal(primary_panel)
    hybrid_btc = primary["btc_primary_1559"].copy()
    first_binance = binance["btc_binance_1559"].first_valid_index()
    if first_binance is None:
        raise ValueError("No Binance 15:59 coverage")
    hybrid_btc.loc[hybrid_btc.index >= first_binance] = binance.loc[hybrid_btc.index >= first_binance, "btc_binance_1559"]
    hybrid_panel = add_proxy(apply_sec_ledger(price.join(hybrid_btc.rename("btc_hybrid_1559"))), "btc_hybrid_1559")
    hybrid_panel["m1_binance_hybrid_signal"] = frozen_m1_signal(hybrid_panel)

    compare = raw.join(primary_panel[["m1_primary_signal"]]).join(hybrid_panel[["m1_binance_hybrid_signal"]])
    overlap_start = max(pd.Timestamp("2026-02-01"), first_binance)
    overlap = compare.loc[overlap_start:PRIMARY_LAST_SESSION].copy()
    overlap["binance_minus_primary_bp"] = (overlap["btc_binance_1559"] / overlap["btc_primary_1559"] - 1.0) * 10_000.0
    overlap["m1_signal_agrees"] = overlap["m1_primary_signal"] == overlap["m1_binance_hybrid_signal"]
    overlap.to_csv(OUT / "source_overlap_1559.csv")
    last_20 = overlap.tail(20)
    transition_summary = {
        "method": "Exact 15:59 America/New_York minute bars only. A bar is accepted only if its recorded close is no later than 16:00 ET; no 16:00-labelled source bar, fallback, interpolation, or BTC forward-fill is used.",
        "primary_last_usable_session": str(PRIMARY_LAST_SESSION.date()),
        "binance_first_usable_mstr_session": str(first_binance.date()),
        "full_overlap": source_summary(overlap, f"{overlap.index.min().date()} to {overlap.index.max().date()}"),
        "last_20_overlap_sessions": source_summary(last_20, f"{last_20.index.min().date()} to {last_20.index.max().date()}"),
        "binance_provenance": binance_provenance,
    }
    write_json("source_transition_summary.json", to_jsonable(transition_summary))

    forward = combined.loc[EXTENSION_START:].copy()
    if forward.empty:
        raise ValueError("No post-primary MSTR sessions are available")
    previous_signal = bool(combined.loc[combined.index < EXTENSION_START, "m1_signal"].iloc[-1])
    if forward.index[0] != EXTENSION_START:
        raise AssertionError(f"Expected forward extension to start {EXTENSION_START.date()}, got {forward.index[0].date()}")

    # Baseline result through all available MSTR daily prices.  The period after
    # the last Binance bar is retained exactly under frozen M1's documented gap
    # policy, so the report separately exposes source-observed and gap-tail P&L.
    full_trace, full_trades = simulate_cash_rebased(forward, forward["m1_signal"], start_long=previous_signal)
    full_trace.to_csv(OUT / "forward_daily_equity.csv")
    full_trades.to_csv(OUT / "forward_trades.csv", index=False)
    forward.to_parquet(OUT / "forward_panel.parquet")
    forward[["m1_signal", "btc_source", "btc_close_1559", "gross_btc_mnav_proxy"]].to_csv(OUT / "forward_signals.csv")

    observed_dates = forward.index[forward["btc_source"] == "binance_1559"]
    if observed_dates.empty:
        raise ValueError("No forward Binance observations after primary source cutoff")
    observed_end = observed_dates.max()
    observed_panel = forward.loc[:observed_end]
    observed_trace, observed_trades = simulate_cash_rebased(
        observed_panel, observed_panel["m1_signal"], start_long=previous_signal
    )
    observed_trace.to_csv(OUT / "forward_source_observed_daily_equity.csv")
    observed_trades.to_csv(OUT / "forward_source_observed_trades.csv", index=False)

    # Cost-consistent descriptive benchmark only, not another candidate or
    # selection input.  It makes clear whether the small forward segment merely
    # reflects a broadly rising MSTR tape.
    full_buy_hold_trace, full_buy_hold_trades = simulate_cash_rebased(
        forward,
        pd.Series(True, index=forward.index),
        start_long=True,
    )
    observed_buy_hold_trace, observed_buy_hold_trades = simulate_cash_rebased(
        observed_panel,
        pd.Series(True, index=observed_panel.index),
        start_long=True,
    )

    gap_start = observed_end + pd.Timedelta(days=1)
    # Business/exchange sessions are not all calendar days; locate the first
    # actual MSTR session after the observed Binance interval.
    later_sessions = forward.index[forward.index > observed_end]
    missing_tail = forward.loc[later_sessions] if len(later_sessions) else forward.iloc[0:0]
    summary = {
        "scope": "Frozen M1 forward source-transition extension only; no parameter search, no live orders.",
        "rule": {
            "id": "M1",
            "decision": "After MSTR close: 10-session gross-BTC-mNAV-proxy log momentum > 0 and proxy > its 50-session SMA.",
            "execution": "Next MSTR regular-session open; long/cash only.",
            "btc_cutoff": "Completed 15:59 ET BTC bar; 16:00-labelled minute bars excluded.",
        },
        "costs": {
            "slippage_bps_each_entry_or_exit": BASELINE_BPS,
            "commission_usd_per_actual_share_each_entry_or_exit": BASELINE_COMMISSION,
            "note": "Every extension entry/exit is executed at open*(1 +/- 3bp) +/- $0.005/share. The standalone extension rebases to cash just before its first opening execution and charges a new entry if the carried stance is long.",
        },
        "data_provenance": {
            "mstr_daily": {"path": str(MSTR_DAILY), "sha256": sha256(MSTR_DAILY)},
            "primary_btc": {"path": str(PRIMARY_BTC), "sha256": sha256(PRIMARY_BTC)},
            "sec_ledger": {"path": str(LEDGER), "sha256": sha256(LEDGER)},
            "frozen_rules": {"path": str(FROZEN), "sha256": sha256(FROZEN)},
            "frozen_amendment": {"path": str(AMENDMENT), "sha256": sha256(AMENDMENT)},
        },
        "coverage": {
            "primary_last_usable_1559_mstr_session": str(PRIMARY_LAST_SESSION.date()),
            "forward_first_session": str(forward.index.min().date()),
            "binance_observed_first_session": str(observed_dates.min().date()),
            "binance_observed_last_session": str(observed_end.date()),
            "binance_observed_mstr_sessions": int(len(observed_dates)),
            "binance_missing_mstr_sessions_within_forward_through_observed_end": int((forward.loc[:observed_end, "btc_source"] != "binance_1559").sum()),
            "available_mstr_last_session": str(forward.index.max().date()),
            "post_binance_missing_btc_mstr_sessions": int(len(missing_tail)),
            "post_binance_gap_first_mstr_session": str(missing_tail.index.min().date()) if not missing_tail.empty else None,
            "frozen_gap_policy": "No BTC price is filled after Binance ends; M1 carries its previously known stance and MSTR open-to-open P&L remains booked.",
        },
        "carried_stance_at_extension_start": previous_signal,
        "source_observed_baseline": metrics(observed_trace, observed_trades),
        "all_available_mstr_baseline_including_frozen_gap_tail": metrics(full_trace, full_trades),
        "cost_consistent_mstr_buy_and_hold_descriptive_benchmark": {
            "source_observed": metrics(observed_buy_hold_trace, observed_buy_hold_trades),
            "all_available_mstr": metrics(full_buy_hold_trace, full_buy_hold_trades),
            "note": "This is a descriptive benchmark, not a fourth rule or an optimization input.",
        },
        "gap_tail_mark_to_market_from_2026_09_30_open_to_final_open": float(
            full_trace["nav"].iloc[-1] / full_trace.loc[observed_end, "nav"] - 1.0
        ),
        "endpoint_note": "The simulator forces liquidation at the final included MSTR open under the same costs. Therefore an end date D includes open-to-open performance through D's open, not unknown performance after that open.",
    }
    write_json("forward_summary.json", to_jsonable(summary))


if __name__ == "__main__":
    main()
