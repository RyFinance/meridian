#!/usr/bin/env python3
"""Run the pre-registered M1/M2/M3 rules on the sealed period.

This script reads FROZEN_RULES.json rather than selecting parameters.  It is
research-only and has no brokerage/order functionality.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from mnav_core import (
    ROOT,
    SPLIT_DATE,
    add_time_long,
    build_panel,
    metrics,
    observations_from_filings,
    premium_trend_signal,
    save_observations,
    simulate_long_only,
)


DEV_END = pd.Timestamp("2022-12-30")
VALID_START = pd.Timestamp("2023-01-03")
VALID_END = pd.Timestamp("2026-08-10")
BASELINE = {"label": "baseline_3bp_plus_0.005", "bps": 3.0, "commission": 0.005}
DEV_MANIFEST = ROOT / "sec_source" / "dev_filings" / "MANIFEST.json"
HOLDOUT_MANIFEST = ROOT / "sec_source" / "holdout_filings" / "MANIFEST.json"
FROZEN_PATH = ROOT / "FROZEN_RULES.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_signal(panel: pd.DataFrame, rule: dict[str, object]) -> pd.Series:
    return premium_trend_signal(
        panel,
        premium_momentum_days=int(rule["premium_momentum_days_L"]),
        premium_sma_days=int(rule["premium_sma_days_S"]),
        btc_momentum_days=(
            int(rule["btc_momentum_days"]) if rule["btc_momentum_days"] is not None else None
        ),
    )


def previous_signal(signal: pd.Series, before: pd.Timestamp) -> bool:
    prior = signal.loc[signal.index < before]
    if prior.empty:
        return False
    return bool(prior.iloc[-1])


def run_one(
    panel: pd.DataFrame,
    signal: pd.Series,
    *,
    start_long: bool,
    bps: float = BASELINE["bps"],
    commission: float = BASELINE["commission"],
) -> tuple[dict[str, object], pd.Series, pd.DataFrame]:
    equity, trades = simulate_long_only(
        panel,
        signal,
        slippage_bps_each_side=bps,
        commission_per_actual_share=commission,
        start_long=start_long,
    )
    stat = add_time_long(metrics(equity, trades), equity, trades, panel, signal, start_long=start_long)
    return stat, equity, trades


def rows_for_period(
    *,
    label: str,
    panel: pd.DataFrame,
    full_signals: dict[str, pd.Series],
    rules: list[dict[str, object]],
    first_start_signal_from_full: bool,
) -> tuple[list[dict[str, object]], dict[str, pd.DataFrame]]:
    rows: list[dict[str, object]] = []
    trades_out: dict[str, pd.DataFrame] = {}
    for rule in rules:
        rule_id = str(rule["id"])
        signal = full_signals[rule_id].reindex(panel.index)
        start_long = previous_signal(full_signals[rule_id], panel.index[0]) if first_start_signal_from_full else False
        stat, _, trades = run_one(panel, signal, start_long=start_long)
        rows.append({"period": label, "strategy": rule_id, **stat})
        trades_out[rule_id] = trades
    return rows, trades_out


def calendar_subperiods(
    *,
    period: str,
    panel: pd.DataFrame,
    full_signals: dict[str, pd.Series],
    rules: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for year, year_panel in panel.groupby(panel.index.year):
        for rule in rules:
            rule_id = str(rule["id"])
            start_long = previous_signal(full_signals[rule_id], year_panel.index[0])
            stat, _, _ = run_one(
                year_panel,
                full_signals[rule_id].reindex(year_panel.index),
                start_long=start_long,
            )
            rows.append({"period": period, "year": int(year), "strategy": rule_id, **stat})
    return rows


def contiguous_missing_segments(panel: pd.DataFrame) -> pd.DataFrame:
    missing = panel[panel["btc_close_4pm_et"].isna()].copy()
    if missing.empty:
        return pd.DataFrame(columns=["start", "end", "mstr_sessions", "reason"])
    groups = (missing.index.to_series().diff().dt.days.gt(4)).cumsum()
    rows = []
    for _, group in missing.groupby(groups):
        rows.append(
            {
                "start": str(group.index.min().date()),
                "end": str(group.index.max().date()),
                "mstr_sessions": len(group),
                "reason": "No BTC quote no later than 16:00 ET within 15 minutes; signal held, no price fill",
            }
        )
    return pd.DataFrame(rows)


def split_sanity(panel: pd.DataFrame) -> pd.DataFrame:
    dates = panel.loc["2024-08-06":"2024-08-13"].copy()
    dates["incorrect_current_date_factor"] = np.where(dates.index < SPLIT_DATE, 10.0, 1.0)
    dates["incorrect_proxy_if_factor_applied_by_trade_date"] = (
        dates["mstr_close"]
        * dates["total_common_shares_reported"]
        * dates["incorrect_current_date_factor"]
        / (dates["btc_held"] * dates["btc_close_4pm_et"])
    )
    keep = [
        "mstr_close",
        "btc_close_4pm_et",
        "btc_held",
        "observation_filing_date",
        "observation_share_asof",
        "total_common_shares_reported",
        "split_factor_to_price_basis",
        "gross_btc_mnav_proxy",
        "incorrect_current_date_factor",
        "incorrect_proxy_if_factor_applied_by_trade_date",
    ]
    return dates[keep]


def main() -> None:
    frozen = json.loads(FROZEN_PATH.read_text())
    rules = frozen["rules"]
    if [rule["id"] for rule in rules] != ["M1", "M2", "M3"]:
        raise AssertionError("Frozen rule IDs/ordering unexpectedly changed")
    if frozen["status"] != "FROZEN BEFORE SEALED-VALIDATION RUN":
        raise AssertionError("Expected the frozen pre-validation specification")

    observations = observations_from_filings(DEV_MANIFEST) + observations_from_filings(HOLDOUT_MANIFEST)
    observations = sorted(observations, key=lambda x: x.filing_date)
    save_observations(observations, ROOT / "ALL_SEC_OBSERVATIONS.csv")
    panel = build_panel(observations, start="2020-08-01", end=str(VALID_END.date()))
    if panel.index.max() != VALID_END:
        raise AssertionError(f"Unexpected panel end {panel.index.max().date()}")
    panel.to_parquet(ROOT / "SEALED_PANEL.parquet")
    contiguous_missing_segments(panel).to_csv(ROOT / "BTC_SOURCE_GAPS.csv", index=False)
    split_sanity(panel).to_csv(ROOT / "SPLIT_SANITY_CHECK.csv")

    full_signals = {str(rule["id"]): make_signal(panel, rule) for rule in rules}
    pd.DataFrame(full_signals, index=panel.index).to_parquet(ROOT / "SEALED_SIGNALS.parquet")
    dev_panel = panel.loc[:DEV_END]
    valid_panel = panel.loc[VALID_START:VALID_END]
    if dev_panel.empty or valid_panel.empty:
        raise AssertionError("Expected both development and validation panels")

    dev_rows, _ = rows_for_period(
        label="development_2020_11_02_to_2022_12_30",
        panel=dev_panel,
        full_signals=full_signals,
        rules=rules,
        first_start_signal_from_full=False,
    )
    valid_rows, valid_trades = rows_for_period(
        label="sealed_2023_01_03_to_2026_08_10",
        panel=valid_panel,
        full_signals=full_signals,
        rules=rules,
        first_start_signal_from_full=True,
    )
    for rule_id, trades in valid_trades.items():
        trades.to_csv(ROOT / f"SEALED_TRADES_{rule_id}.csv", index=False)

    # Cost-consistent buy-and-hold comparison; this is descriptive, not a
    # fourth candidate rule.
    benchmarks = []
    for label, subset in [
        ("development_2020_11_02_to_2022_12_30", dev_panel),
        ("sealed_2023_01_03_to_2026_08_10", valid_panel),
    ]:
        always = pd.Series(True, index=subset.index)
        stat, _, _ = run_one(subset, always, start_long=True)
        benchmarks.append({"period": label, "strategy": "MSTR_buy_and_hold", **stat})
    summary = pd.DataFrame(dev_rows + valid_rows + benchmarks)
    summary.to_csv(ROOT / "DEV_VS_SEALED_SUMMARY.csv", index=False)

    sub_rows = calendar_subperiods(
        period="development", panel=dev_panel, full_signals=full_signals, rules=rules
    ) + calendar_subperiods(
        period="sealed", panel=valid_panel, full_signals=full_signals, rules=rules
    )
    # Add the same cost-consistent buy-and-hold for each standalone calendar
    # interval; it is re-entered/realized each year for clean subperiod tables.
    for period, subset in [("development", dev_panel), ("sealed", valid_panel)]:
        for year, year_panel in subset.groupby(subset.index.year):
            stat, _, _ = run_one(
                year_panel, pd.Series(True, index=year_panel.index), start_long=True
            )
            sub_rows.append({"period": period, "year": int(year), "strategy": "MSTR_buy_and_hold", **stat})
    pd.DataFrame(sub_rows).to_csv(ROOT / "SUBPERIOD_RESULTS.csv", index=False)

    # Predeclared transaction-cost stress; it does not select or replace M1–M3.
    cost_cases = [
        ("frictionless", 0.0, 0.0),
        ("baseline", 3.0, 0.005),
        ("moderately_higher", 4.0, 0.0075),
        ("double_baseline", 6.0, 0.01),
    ]
    cost_rows = []
    for rule in rules:
        rule_id = str(rule["id"])
        start_long = previous_signal(full_signals[rule_id], valid_panel.index[0])
        for label, bps, commission in cost_cases:
            stat, _, _ = run_one(
                valid_panel,
                full_signals[rule_id].reindex(valid_panel.index),
                start_long=start_long,
                bps=bps,
                commission=commission,
            )
            cost_rows.append(
                {
                    "strategy": rule_id,
                    "cost_case": label,
                    "slippage_bps_each_side": bps,
                    "commission_each_actual_share": commission,
                    **stat,
                }
            )
    pd.DataFrame(cost_rows).to_csv(ROOT / "SEALED_COST_SENSITIVITY.csv", index=False)

    # A source-gap sensitivity distinct from the frozen rule: it asks whether
    # the result depends on keeping exposure through the two unavailable-BTC
    # months.  This diagnostic exits to cash after any unavailable close and
    # resumes the already-frozen stance when source coverage returns; it never
    # imputes a BTC price and is not a candidate-selection exercise.
    gap_rows = []
    for rule in rules:
        rule_id = str(rule["id"])
        start_long = previous_signal(full_signals[rule_id], valid_panel.index[0])
        for label, signal in [
            ("frozen_hold_last_stance", full_signals[rule_id].reindex(valid_panel.index)),
            (
                "diagnostic_exit_during_unavailable_btc",
                full_signals[rule_id]
                .reindex(valid_panel.index)
                .where(valid_panel["btc_close_4pm_et"].notna(), False),
            ),
        ]:
            stat, _, _ = run_one(valid_panel, signal, start_long=start_long)
            gap_rows.append({"strategy": rule_id, "gap_handling": label, **stat})
    pd.DataFrame(gap_rows).to_csv(ROOT / "GAP_POLICY_SENSITIVITY.csv", index=False)

    # Share-class diagnostic: the frozen proxy uses both A+B as equal economic
    # claims.  Recompute with Class A only to check that that explicit
    # approximation is not the source of the validation result.  This does not
    # replace the frozen proxy or candidates.
    a_only_panel = panel.copy()
    a_only_panel["gross_btc_mnav_proxy"] = (
        a_only_panel["mstr_close"]
        * (a_only_panel["class_a_shares"] * a_only_panel["split_factor_to_price_basis"])
        / (a_only_panel["btc_held"] * a_only_panel["btc_close_4pm_et"])
    )
    a_only_panel["log_gross_btc_mnav_proxy"] = np.log(a_only_panel["gross_btc_mnav_proxy"])
    a_only_valid = a_only_panel.loc[VALID_START:VALID_END]
    share_rows = []
    for rule in rules:
        rule_id = str(rule["id"])
        a_signal = make_signal(a_only_panel, rule)
        a_start = previous_signal(a_signal, a_only_valid.index[0])
        stat, _, _ = run_one(a_only_valid, a_signal.reindex(a_only_valid.index), start_long=a_start)
        share_rows.append(
            {
                "strategy": rule_id,
                "proxy_share_basis": "diagnostic_Class_A_only",
                **stat,
            }
        )
    pd.DataFrame(share_rows).to_csv(ROOT / "SHARE_CLASS_SENSITIVITY.csv", index=False)

    # Post hoc fragility diagnostic, explicitly not a selection screen.  These
    # are neighboring grid points to the frozen M1/M2/M3 values.
    neighbor_specs = [
        ("N1_L10_S50_no_btc__same_as_M1", 10, 50, None),
        ("N2_L20_S50_no_btc__same_as_M2", 20, 50, None),
        ("N3_L40_S50_no_btc", 40, 50, None),
        ("N4_L20_S30_no_btc", 20, 30, None),
        ("N5_L20_S80_no_btc", 20, 80, None),
        ("N6_L20_S50_btc20__same_as_M3", 20, 50, 20),
        ("N7_L10_S50_btc20", 10, 50, 20),
        ("N8_L40_S50_btc20", 40, 50, 20),
        ("N9_L20_S30_btc20", 20, 30, 20),
        ("N10_L20_S80_btc20", 20, 80, 20),
    ]
    neighbor_rows = []
    for name, mom, sma, btc in neighbor_specs:
        signal = premium_trend_signal(
            panel,
            premium_momentum_days=mom,
            premium_sma_days=sma,
            btc_momentum_days=btc,
        )
        start_long = previous_signal(signal, valid_panel.index[0])
        stat, _, _ = run_one(valid_panel, signal.reindex(valid_panel.index), start_long=start_long)
        neighbor_rows.append(
            {
                "diagnostic_only": True,
                "name": name,
                "premium_momentum_days": mom,
                "premium_sma_days": sma,
                "btc_momentum_days": "none" if btc is None else btc,
                **stat,
            }
        )
    pd.DataFrame(neighbor_rows).to_csv(ROOT / "SEALED_ADJACENT_PARAMETER_DIAGNOSTIC.csv", index=False)

    # Independent algebraic check of the execution engine: with zero costs,
    # its M1 terminal NAV must equal the product of next-open returns on the
    # causal prior-close position vector.
    m1_signal = full_signals["M1"].reindex(valid_panel.index)
    m1_start = previous_signal(full_signals["M1"], valid_panel.index[0])
    audit_equity, audit_trades = simulate_long_only(
        valid_panel,
        m1_signal,
        slippage_bps_each_side=0.0,
        commission_per_actual_share=0.0,
        start_long=m1_start,
    )
    audit_position = m1_signal.shift(1, fill_value=m1_start).astype(float)
    audit_return = valid_panel["mstr_open"].shift(-1) / valid_panel["mstr_open"] - 1.0
    vector_terminal_nav = float((1.0 + audit_position.iloc[:-1] * audit_return.iloc[:-1]).prod())
    execution_audit = {
        "check": "frictionless M1 event-driven simulator equals causal next-open vector return",
        "initial_long": m1_start,
        "event_driven_terminal_nav": float(audit_equity.iloc[-1]),
        "vector_terminal_nav": vector_terminal_nav,
        "absolute_difference": float(abs(audit_equity.iloc[-1] - vector_terminal_nav)),
        "passed": bool(np.isclose(audit_equity.iloc[-1], vector_terminal_nav, rtol=1e-12, atol=1e-12)),
        "frictionless_transactions": int(len(audit_trades)),
    }
    if not execution_audit["passed"]:
        raise AssertionError("Execution-engine vector audit failed")
    (ROOT / "VALIDATION_EXECUTION_AUDIT.json").write_text(
        json.dumps(execution_audit, indent=2) + "\n"
    )

    run_manifest = {
        "frozen_rule_file": str(FROZEN_PATH),
        "frozen_rule_sha256": sha256(FROZEN_PATH),
        "frozen_amendment_file": str(ROOT / "FROZEN_RULES_AMENDMENT_01.json"),
        "frozen_amendment_sha256": sha256(ROOT / "FROZEN_RULES_AMENDMENT_01.json"),
        "validation_end": str(VALID_END.date()),
        "panel_start": str(panel.index.min().date()),
        "panel_end": str(panel.index.max().date()),
        "panel_sessions": len(panel),
        "btc_missing_4pm_sessions": int(panel["btc_close_4pm_et"].isna().sum()),
        "code_sha256": sha256(ROOT / "mnav_core.py"),
        "runner_sha256": sha256(Path(__file__)),
        "outputs": [
            "DEV_VS_SEALED_SUMMARY.csv",
            "SUBPERIOD_RESULTS.csv",
            "SEALED_COST_SENSITIVITY.csv",
            "SEALED_ADJACENT_PARAMETER_DIAGNOSTIC.csv",
            "GAP_POLICY_SENSITIVITY.csv",
            "SHARE_CLASS_SENSITIVITY.csv",
            "BTC_SOURCE_GAPS.csv",
            "SPLIT_SANITY_CHECK.csv",
            "VALIDATION_EXECUTION_AUDIT.json",
        ],
    }
    (ROOT / "SEALED_RUN_MANIFEST.json").write_text(json.dumps(run_manifest, indent=2) + "\n")

    print("SEALED VALIDATION COMPLETE")
    print(summary.to_string(index=False))
    print("\nCost sensitivity:")
    print(pd.DataFrame(cost_rows)[["strategy", "cost_case", "total_return", "cagr", "annualized_sharpe", "max_drawdown", "round_trips"]].to_string(index=False))
    print("\nAdjacent-parameter diagnostic:")
    print(pd.DataFrame(neighbor_rows)[["name", "total_return", "cagr", "annualized_sharpe", "max_drawdown", "round_trips"]].to_string(index=False))
    print("\nBTC-source gaps:")
    print(contiguous_missing_segments(panel).to_string(index=False))
    print("\nSource-gap sensitivity:")
    print(pd.DataFrame(gap_rows)[["strategy", "gap_handling", "total_return", "cagr", "annualized_sharpe", "max_drawdown", "round_trips"]].to_string(index=False))
    print("\nShare-class sensitivity:")
    print(pd.DataFrame(share_rows)[["strategy", "proxy_share_basis", "total_return", "cagr", "annualized_sharpe", "max_drawdown", "round_trips"]].to_string(index=False))
    print("\nSplit sanity check:")
    print(split_sanity(panel).to_string())


if __name__ == "__main__":
    main()
