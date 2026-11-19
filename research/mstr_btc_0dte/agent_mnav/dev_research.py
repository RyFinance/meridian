#!/usr/bin/env python3
"""Development-only exploration for a gross-BTC mNAV trend hypothesis.

Hard boundary: every pricing observation, filing observation, and simulated
return is on or before 2022-12-30.  This script deliberately does not load or
write a 2023+ performance result.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from mnav_core import (
    ROOT,
    add_time_long,
    build_panel,
    metrics,
    observations_from_filings,
    premium_trend_signal,
    save_observations,
    simulate_long_only,
)


DEV_START = "2020-08-01"
DEV_END = "2022-12-30"
BASELINE_SLIPPAGE_BPS = 3.0
BASELINE_COMMISSION = 0.005
MANIFEST = ROOT / "sec_source" / "dev_filings" / "MANIFEST.json"


def run() -> None:
    observations = observations_from_filings(MANIFEST, through="2022-12-31")
    if not observations or max(x.filing_date for x in observations) > "2022-12-31":
        raise AssertionError("Development filing boundary breached")
    ledger = save_observations(observations, ROOT / "DEV_SEC_OBSERVATIONS.csv")
    panel = build_panel(observations, start=DEV_START, end=DEV_END)
    if panel.index.max() > pd.Timestamp(DEV_END):
        raise AssertionError("Development price boundary breached")
    panel.to_parquet(ROOT / "DEV_PANEL.parquet")

    rows: list[dict[str, object]] = []
    # A deliberately small, predeclared trend family.  No one-day mean-revert
    # signals, shorts, or thresholds are considered.
    for momentum_days in (10, 20, 40):
        for sma_days in (30, 50, 80):
            for btc_momentum_days in (None, 20, 50):
                signal = premium_trend_signal(
                    panel,
                    premium_momentum_days=momentum_days,
                    premium_sma_days=sma_days,
                    btc_momentum_days=btc_momentum_days,
                )
                equity, trades = simulate_long_only(
                    panel,
                    signal,
                    slippage_bps_each_side=BASELINE_SLIPPAGE_BPS,
                    commission_per_actual_share=BASELINE_COMMISSION,
                )
                stat = add_time_long(metrics(equity, trades), equity, trades, panel, signal)
                rows.append(
                    {
                        "rule_family": "premium_momentum_and_trend",
                        "premium_momentum_days": momentum_days,
                        "premium_sma_days": sma_days,
                        "btc_momentum_days": btc_momentum_days if btc_momentum_days is not None else "none",
                        **stat,
                    }
                )
    grid = pd.DataFrame(rows).sort_values(
        ["annualized_sharpe", "cagr"], ascending=False, kind="stable"
    )
    grid.to_csv(ROOT / "DEV_GRID.csv", index=False)

    benchmark_signal = pd.Series(True, index=panel.index)
    benchmark_equity, benchmark_trades = simulate_long_only(
        panel,
        benchmark_signal,
        slippage_bps_each_side=BASELINE_SLIPPAGE_BPS,
        commission_per_actual_share=BASELINE_COMMISSION,
        start_long=True,
    )
    benchmark_stat = add_time_long(
        metrics(benchmark_equity, benchmark_trades),
        benchmark_equity,
        benchmark_trades,
        panel,
        benchmark_signal,
        start_long=True,
    )
    pd.DataFrame([benchmark_stat | {"strategy": "MSTR buy-and-hold, same execution/cost model"}]).to_csv(
        ROOT / "DEV_BENCHMARK.csv", index=False
    )

    audit = {
        "purpose": "development only; no 2023+ performance data loaded into this run",
        "development_price_start": str(panel.index.min().date()),
        "development_price_end": str(panel.index.max().date()),
        "source_filings": int(len(ledger)),
        "latest_source_filing_date": max(x.filing_date for x in observations),
        "source_manifest": str(MANIFEST),
        "mnav_definition": "MSTR close * total reported Class A+B shares / (explicitly disclosed BTC held * 16:00 ET BTC spot); gross-BTC proxy, not enterprise mNAV",
        "execution": "signal after close; position changed at next session open; 3 bp per side plus $0.005 actual share per side",
        "grid": {"premium_momentum_days": [10, 20, 40], "premium_sma_days": [30, 50, 80], "btc_momentum_days": [None, 20, 50]},
    }
    (ROOT / "DEV_AUDIT.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(f"Development panel: {panel.index.min().date()} through {panel.index.max().date()}, {len(panel)} sessions")
    print(f"Development observations: {len(ledger)}")
    print(grid.head(12).to_string(index=False))
    print(pd.DataFrame([benchmark_stat]).to_string(index=False))


if __name__ == "__main__":
    run()
