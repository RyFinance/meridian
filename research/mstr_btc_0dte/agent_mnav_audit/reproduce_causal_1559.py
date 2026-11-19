#!/usr/bin/env python3
"""Read-only causal-cutoff reproduction for the frozen M1 audit.

This audit intentionally changes exactly one data-timing convention: a 1-minute
BTC candle stamped 16:00 is treated as the 16:00--16:01 bar, so its *close* is
not used in a decision made at 16:00 ET.  The replacement is the close of the
15:59--16:00 bar.  It preserves the frozen M1 rule, SEC observations, MSTR
prices, split logic, 3 bp/side slippage, and $0.005/actual-share commission.

The script reads only from ``agent_mnav`` and writes only
``CAUSAL_1559_M1.json`` next to this file.  It never executes the frozen
runner's ``main`` and therefore never rewrites its artifacts.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


AUDIT_ROOT = Path(__file__).resolve().parent
AGENT_ROOT = AUDIT_ROOT.parent / "agent_mnav"
sys.path.insert(0, str(AGENT_ROOT))

import mnav_core as core  # noqa: E402
import validate_frozen as frozen_runner  # noqa: E402


VALID_START = "2023-01-03"
VALID_END = "2026-08-10"
WARMUP_START = "2020-08-01"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def completed_bar_quotes(session_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Return the last fully completed BTC minute bar at 16:00 ET.

    The source's timestamps label minute starts.  A 15:59 timestamp therefore
    denotes the bar finishing at 16:00.  Staleness is measured from the actual
    bar end to the 16:00 cutoff, retaining the frozen <=15-minute policy.
    """

    raw = pd.read_parquet(core.BTC_1M, columns=["timestamp", "close"])
    raw = raw.dropna(subset=["timestamp", "close"]).sort_values("timestamp")
    stamps = pd.DatetimeIndex(raw["timestamp"])
    cutoff = (
        pd.DatetimeIndex(session_dates)
        .tz_localize("America/New_York")
        .normalize()
        + pd.Timedelta(hours=16)
    ).tz_convert("UTC")
    last_allowed_start = cutoff - pd.Timedelta(minutes=1)
    positions = stamps.searchsorted(last_allowed_start, side="right") - 1
    has_position = positions >= 0
    observed = pd.DatetimeIndex(
        [stamps[position] if valid else pd.NaT for position, valid in zip(positions, has_position)]
    )
    completed = observed + pd.Timedelta(minutes=1)
    lag_seconds = np.full(len(cutoff), np.nan)
    lag_seconds[has_position] = (cutoff[has_position] - completed[has_position]).total_seconds()
    usable = has_position & (lag_seconds <= 15 * 60)
    closes = np.full(len(cutoff), np.nan)
    closes[usable] = raw["close"].to_numpy()[positions[usable]]
    if not bool((completed[usable] <= cutoff[usable]).all()):
        raise AssertionError("Causal BTC cutoff unexpectedly selected an unfinished bar")
    return pd.DataFrame(
        {
            "btc_close_4pm_et": closes,
            "btc_lag_seconds": lag_seconds,
            "source_bar_start_utc": observed,
            "source_bar_end_utc": completed,
        },
        index=session_dates,
    )


def rebuilt_panel_with_causal_btc(panel: pd.DataFrame) -> pd.DataFrame:
    quotes = completed_bar_quotes(panel.index)
    rebuilt = panel.copy()
    rebuilt["btc_close_4pm_et"] = quotes["btc_close_4pm_et"]
    rebuilt["btc_lag_seconds"] = quotes["btc_lag_seconds"]
    rebuilt["gross_btc_mnav_proxy"] = (
        rebuilt["mstr_close"]
        * rebuilt["total_common_shares_price_basis"]
        / (rebuilt["btc_held"] * rebuilt["btc_close_4pm_et"])
    )
    rebuilt["log_gross_btc_mnav_proxy"] = np.log(rebuilt["gross_btc_mnav_proxy"])
    return rebuilt


def metric_subset(stat: dict[str, object]) -> dict[str, object]:
    fields = [
        "start",
        "end",
        "sessions",
        "total_return",
        "cagr",
        "annualized_sharpe",
        "max_drawdown",
        "entry_trades",
        "exit_trades",
        "round_trips",
        "time_long",
    ]
    return {field: stat[field] for field in fields}


def trade_keys(trades: pd.DataFrame) -> set[tuple[str, str]]:
    return {(pd.Timestamp(row.date).strftime("%Y-%m-%d"), str(row.side)) for row in trades.itertuples()}


def source_bar_examples(raw: pd.DataFrame, dates: pd.DatetimeIndex) -> list[dict[str, object]]:
    indexed = raw.set_index("timestamp").sort_index()
    examples: list[dict[str, object]] = []
    for date in dates:
        target = pd.Timestamp(date).tz_localize("America/New_York") + pd.Timedelta(hours=16)
        before = target.tz_convert("UTC") - pd.Timedelta(minutes=1)
        at = target.tz_convert("UTC")
        b15 = indexed.loc[before]
        b16 = indexed.loc[at]
        examples.append(
            {
                "date": str(pd.Timestamp(date).date()),
                "bar_1559_start_et": str(before.tz_convert("America/New_York")),
                "bar_1559_close": float(b15["close"]),
                "bar_1600_start_et": str(at.tz_convert("America/New_York")),
                "bar_1600_open": float(b16["open"]),
                "bar_1600_close": float(b16["close"]),
            }
        )
    return examples


def main() -> None:
    frozen = json.loads((AGENT_ROOT / "FROZEN_RULES.json").read_text())
    m1 = next(rule for rule in frozen["rules"] if rule["id"] == "M1")
    expected_rule = {
        "premium_momentum_days_L": 10,
        "premium_sma_days_S": 50,
        "btc_momentum_days": None,
    }
    if {key: m1[key] for key in expected_rule} != expected_rule:
        raise AssertionError("The audited frozen M1 rule is not the expected 10/50/no-BTC regime rule")
    frozen_costs = frozen["signal_and_execution"]["baseline_costs"]
    if (
        float(frozen_costs["slippage_bps_each_entry_or_exit"]) != frozen_runner.BASELINE["bps"]
        or float(frozen_costs["commission_usd_per_actual_share_each_entry_or_exit"])
        != frozen_runner.BASELINE["commission"]
    ):
        raise AssertionError("Runner baseline costs differ from frozen specification")

    observations = core.observations_from_filings(AGENT_ROOT / "sec_source/dev_filings/MANIFEST.json")
    observations += core.observations_from_filings(AGENT_ROOT / "sec_source/holdout_filings/MANIFEST.json")
    observations = sorted(observations, key=lambda observation: observation.filing_date)
    frozen_panel = core.build_panel(observations, start=WARMUP_START, end=VALID_END)
    causal_panel = rebuilt_panel_with_causal_btc(frozen_panel)

    frozen_signal = frozen_runner.make_signal(frozen_panel, m1)
    causal_signal = frozen_runner.make_signal(causal_panel, m1)
    frozen_valid = frozen_panel.loc[VALID_START:VALID_END]
    causal_valid = causal_panel.loc[VALID_START:VALID_END]
    frozen_start_long = frozen_runner.previous_signal(frozen_signal, frozen_valid.index[0])
    causal_start_long = frozen_runner.previous_signal(causal_signal, causal_valid.index[0])
    frozen_stat, _, frozen_trades = frozen_runner.run_one(
        frozen_valid, frozen_signal.reindex(frozen_valid.index), start_long=frozen_start_long
    )
    causal_stat, _, causal_trades = frozen_runner.run_one(
        causal_valid, causal_signal.reindex(causal_valid.index), start_long=causal_start_long
    )

    summary = pd.read_csv(AGENT_ROOT / "DEV_VS_SEALED_SUMMARY.csv")
    official = summary.loc[
        (summary["period"] == "sealed_2023_01_03_to_2026_08_10") & (summary["strategy"] == "M1")
    ].iloc[0]
    official_match = all(
        np.isclose(float(frozen_stat[field]), float(official[field]), rtol=0.0, atol=1e-12)
        for field in ("total_return", "cagr", "annualized_sharpe", "max_drawdown", "time_long")
    )
    if not official_match:
        raise AssertionError("Unmodified frozen-path reproduction does not match the declared sealed M1 summary")

    valid_difference = frozen_signal.reindex(frozen_valid.index) != causal_signal.reindex(causal_valid.index)
    changed_dates = frozen_valid.index[valid_difference]
    raw = pd.read_parquet(core.BTC_1M, columns=["timestamp", "open", "close"])
    input_hashes = {
        "FROZEN_RULES.json": sha256(AGENT_ROOT / "FROZEN_RULES.json"),
        "FROZEN_RULES_AMENDMENT_01.json": sha256(AGENT_ROOT / "FROZEN_RULES_AMENDMENT_01.json"),
        "mnav_core.py": sha256(AGENT_ROOT / "mnav_core.py"),
        "validate_frozen.py": sha256(AGENT_ROOT / "validate_frozen.py"),
        "mstr_daily_yf.parquet": sha256(core.MSTR_DAILY),
        "btc_usd_1m_candles_polymarket_arb.parquet": sha256(core.BTC_1M),
    }
    expected_hashes = {
        "FROZEN_RULES.json": "24a76236dcf954e8a2d89ed5b505291a89bac9ea28625acf453f841829ca88ba",
        "FROZEN_RULES_AMENDMENT_01.json": "6dafec5824ae7ea66cb35f471bd826a5e14b20fd7f8a0a28ecd51fc17285d1f8",
        "mnav_core.py": "a6d7f40ecd53f1b9b108ff1e78b1d8431d11bcc589806173258b887466a7b743",
        "validate_frozen.py": "29c72b2f0e8c571687009f73d2694e83435552e0134fbd19da5879490008287a",
        "mstr_daily_yf.parquet": frozen["source_snapshot"]["mstr_daily_yf_parquet"]["sha256"],
        "btc_usd_1m_candles_polymarket_arb.parquet": frozen["source_snapshot"]["btc_1m_polymarket_arb_parquet"]["sha256"],
    }

    deltas = {
        "total_return_fraction": float(causal_stat["total_return"] - frozen_stat["total_return"]),
        "total_return_percentage_points": float(
            100.0 * (causal_stat["total_return"] - frozen_stat["total_return"])
        ),
        "cagr_percentage_points": float(100.0 * (causal_stat["cagr"] - frozen_stat["cagr"])),
        "annualized_sharpe": float(
            causal_stat["annualized_sharpe"] - frozen_stat["annualized_sharpe"]
        ),
        "max_drawdown_percentage_points": float(
            100.0 * (causal_stat["max_drawdown"] - frozen_stat["max_drawdown"])
        ),
        "round_trips": float(causal_stat["round_trips"] - frozen_stat["round_trips"]),
    }
    payload = {
        "purpose": "Read-only causal 15:59 completed-bar audit of frozen M1; not a rule search or replacement candidate.",
        "intentional_change_only": {
            "old": "Use the close of a candle timestamped 16:00 ET.",
            "new": "Use the close of the last fully completed candle, timestamped no later than 15:59 ET.",
            "staleness": "Retains the <=15-minute frozen policy, measured from completed bar end to 16:00 ET.",
        },
        "held_fixed": {
            "m1_parameters": expected_rule,
            "sec_observations": "same cached 10-Q/10-K manifests and parser",
            "mstr_prices": "same pinned parquet",
            "share_and_split_logic": "same mnav_core build_panel fields",
            "execution": "same next-open simulator",
            "costs": {
                "slippage_bps_each_side": frozen_runner.BASELINE["bps"],
                "commission_usd_per_actual_share_each_side": frozen_runner.BASELINE["commission"],
            },
        },
        "input_hashes": input_hashes,
        "input_hashes_match_declared_or_sealed": {
            key: input_hashes[key] == expected_hashes[key] for key in input_hashes
        },
        "unmodified_frozen_path_matches_declared_sealed_summary": official_match,
        "frozen_1600_path": metric_subset(frozen_stat),
        "causal_1559_path": metric_subset(causal_stat),
        "causal_minus_frozen": deltas,
        "valid_btc_quote_days_frozen": int(frozen_panel["btc_close_4pm_et"].notna().sum()),
        "valid_btc_quote_days_causal": int(causal_panel["btc_close_4pm_et"].notna().sum()),
        "valid_signal_differences": {
            "count": int(valid_difference.sum()),
            "dates": [str(date.date()) for date in changed_dates],
        },
        "trade_key_changes": {
            "only_frozen": [list(key) for key in sorted(trade_keys(frozen_trades) - trade_keys(causal_trades))],
            "only_causal": [list(key) for key in sorted(trade_keys(causal_trades) - trade_keys(frozen_trades))],
        },
        "source_bar_examples_on_changed_signal_days": source_bar_examples(raw, changed_dates),
        "writes_only": str(AUDIT_ROOT / "CAUSAL_1559_M1.json"),
    }
    output = AUDIT_ROOT / "CAUSAL_1559_M1.json"
    output.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
