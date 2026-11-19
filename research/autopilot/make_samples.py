"""Real-price sample reports on HYPOTHETICAL holdings (research samples only; nothing here is a recommendation).

1. Price snapshot: for every autopilot ticker, the cycle-8 frozen view ``proc/etf/<TICKER>.parquet`` column
   ``close`` (split-adjusted, not dividend-adjusted) and ``proc/fx_daily.parquet`` USDCAD, taking the last row on or
   before 2025-08-29 and on or before 2026-08-31 (the CSV carries the actual row date).  Frozen with
   ``research.data_snapshot`` under ``data/cycle9/autopilot_prices/store`` as ``autopilot_prices_20260831``.
2. Hypothetical holdings (``research/autopilot/examples/``): CAD 100,000 put at target on 2025-08-29 --
   shares = floor(target weight x 100,000 / CAD price), bought at close + declared half-spread, USD bought with
   the declared 0.10% conversion cost, remaining CAD left as cash (a negative remainder is the margin loan).  The
   positions are then carried unchanged to 2026-08-31 with no flows, but with the cash they would have produced:
   each month a margin loan accrues the cycle-8 margin rate (policy_cad of the previous month-end + 1.5%, /12), and
   the cycle-8 view's per-share distributions are paid as cash in the listing currency (USD-listed funds net of 15%
   US withholding; positive cash earns nothing).  The holdings file is dated 2026-08-31 so the report's freshness
   check applies to the report date.
3. Reports dated 2026-08-31 through the real CLI (``research.autopilot.cli.run``, verified snapshot mode) for all 8
   configs in ``tfsa`` plus P4@1.5 and P6a@1.25 in ``nonreg_margin``, and two refusal examples: STALE prices
   (report dated 2026-09-08, 8 days after the last price) and a TFSA holdings file showing a margin loan.  Every
   config carries the label ``LABEL``, which the report prints under its title.  All runs append to
   ``reports/cycle9/autopilot/samples/sample_paper_log.jsonl``.

Outputs are built in a temporary directory and then copied over the sample directory, so a re-run reproduces the
same bytes instead of appending duplicate log lines.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from research import data_snapshot
from research.autopilot import cli
from research.autopilot.config import CONFIGS, UNIVERSE, USDCAD, parse_config, target_weights
from research.autopilot.prices import freeze_price_csv
from research.autopilot.replay import owner_tolerances

REPO = Path(__file__).resolve().parents[2]
CYCLE8_STORE = REPO / "data" / "cycle8" / "snapshot_store"
CYCLE8_VERSION = "cycle8_v1"
STORE = REPO / "data" / "cycle9" / "autopilot_prices" / "store"
SOURCE_DIR = REPO / "data" / "cycle9" / "autopilot_prices" / "source"
VERSION = "autopilot_prices_20260831"
PRICE_CSV = "prices_20250829_20260831.csv"
EXAMPLES = Path(__file__).resolve().parent / "examples"
SAMPLES_OUT = REPO / "reports" / "cycle9" / "autopilot" / "samples"
LOG_NAME = "sample_paper_log.jsonl"

LABEL = "HYPOTHETICAL HOLDINGS — research sample, not a recommendation"
BUY_DATE = date(2025, 8, 29)
REPORT_DATE = date(2026, 8, 31)
STALE_REPORT_DATE = date(2026, 9, 8)
START_CAD = 100_000.0
TFSA_MARGIN_LOAN_CAD = 10_000.0
SAMPLES = [(c, "tfsa") for c in CONFIGS] + [("P4@1.5", "nonreg_margin"), ("P6a@1.25", "nonreg_margin")]
CLOSE_DECIMALS = 4
US_WITHHOLDING = 0.15          # on distributions of US-domiciled ETFs (treaty rate), deducted at source


# ------------------------------------------------------------------------------------------------ prices -----------
def price_rows(store: Path = CYCLE8_STORE) -> list[tuple[date, str, float, str]]:
    import pandas as pd  # local import: only the snapshot build needs pandas

    data_snapshot.verify(Path(store), CYCLE8_VERSION, source=False)
    proc = Path(store).resolve() / "versions" / CYCLE8_VERSION / "view" / "proc"
    rows = []
    for t in sorted(UNIVERSE):
        df = pd.read_parquet(proc / "etf" / f"{t}.parquet")
        for d in (BUY_DATE, REPORT_DATE):
            sub = df.loc[: pd.Timestamp(d)].dropna(subset=["close"])
            if sub.empty:
                raise ValueError(f"no {t} close on or before {d}")
            ts, last = sub.index[-1], sub.iloc[-1]
            if str(last["currency"]) != UNIVERSE[t]["ccy"]:
                raise ValueError(f"{t} quoted in {last['currency']}, expected {UNIVERSE[t]['ccy']}")
            rows.append((ts.date(), t, round(float(last["close"]), CLOSE_DECIMALS), UNIVERSE[t]["ccy"]))
    fx = pd.read_parquet(proc / "fx_daily.parquet")["USDCAD"].dropna()
    for d in (BUY_DATE, REPORT_DATE):
        sub = fx.loc[: pd.Timestamp(d)]
        rows.append((sub.index[-1].date(), USDCAD, round(float(sub.iloc[-1]), CLOSE_DECIMALS), "CAD"))
    return sorted(set(rows))


def price_csv_bytes(rows: list[tuple[date, str, float, str]]) -> bytes:
    lines = ["date,ticker,close,currency"] + [f"{d.isoformat()},{t},{c:.{CLOSE_DECIMALS}f},{ccy}"
                                             for d, t, c, ccy in rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


def freeze_prices(store: Path = STORE, source_dir: Path = SOURCE_DIR, version: str = VERSION) -> str:
    rows = price_rows()
    data = price_csv_bytes(rows)
    source_dir.mkdir(parents=True, exist_ok=True)
    path = source_dir / PRICE_CSV
    if path.exists() and path.read_bytes() != data:
        raise FileExistsError(f"{path} exists with different content")
    if not path.exists():
        path.write_bytes(data)
    c8 = data_snapshot.load_manifest(CYCLE8_STORE, CYCLE8_VERSION)
    keys = {f"proc/etf/{t}.parquet" for t in UNIVERSE} | {"proc/fx_daily.parquet"}
    retrieved = max(r["retrieved_at"] for r in c8["payload"]["records"] if r["key"] in keys)
    return freeze_price_csv(path, store, version,
                            source=("cycle-8 frozen view proc/etf/<TICKER>.parquet close (split-adjusted) and "
                                    "proc/fx_daily.parquet USDCAD; last row on/before 2025-08-29 and 2026-08-31"),
                            source_identifier=(f"data/cycle8/snapshot_store {CYCLE8_VERSION} manifest "
                                               f"{c8['manifest_sha256']}"),
                            retrieved_at=retrieved)


def prices_on(rows: list[tuple[date, str, float, str]], d: date) -> tuple[dict[str, tuple[float, str]], float]:
    px: dict[str, tuple[float, str]] = {}
    fx = None
    for rd, t, c, ccy in sorted(rows):
        if rd <= d:
            if t == USDCAD:
                fx = c
            else:
                px[t] = (c, ccy)
    if fx is None:
        raise ValueError(f"no USDCAD on or before {d}")
    return px, fx


# ------------------------------------------------------------------------------------------------ holdings ---------
def at_target_holdings(config_id: str, account_type: str, rows: list[tuple[date, str, float, str]],
                       nav: float = START_CAD, *, carry_income: bool = True) -> dict[str, Any]:
    """Hypothetical holdings: CAD ``nav`` at target on BUY_DATE, carried to REPORT_DATE with distributions and
    margin interest (``carry``; see the module docstring), dated REPORT_DATE."""
    cfg = parse_config({"config_id": config_id, "account_type": account_type, "owner_tolerance_pct": 50})
    p = cfg.params
    px, fx = prices_on(rows, BUY_DATE)
    positions: dict[str, int] = {}
    cad_cost = usd_cost = 0.0
    for t, w in sorted(target_weights(cfg).items()):
        close, ccy = px[t]
        rate = fx if ccy == "USD" else 1.0
        n = math.floor(w * nav / (close * rate) + 1e-9)
        if n <= 0:
            continue
        positions[t] = n
        cost = n * close * (1.0 + p["half_spread"][t])
        if ccy == "USD":
            usd_cost += cost
        else:
            cad_cost += cost
    cash = nav - cad_cost - usd_cost * fx / (1.0 - float(p["fx_cost"]))
    if account_type != "nonreg_margin" and cash < 0:
        raise ValueError(f"{config_id} {account_type}: at-target purchase would need borrowing")
    cash, cash_usd = carry(positions, cash) if carry_income else (cash, 0.0)
    h: dict[str, Any] = {"as_of": REPORT_DATE.isoformat(), "cash_cad": math.floor(max(cash, 0.0) * 100) / 100,
                         "cash_usd": math.floor(cash_usd * 100) / 100, "net_external_flow_cad": 0,
                         "positions": positions}
    if account_type == "nonreg_margin":
        h["margin_loan_cad"] = math.ceil(max(-cash, 0.0) * 100) / 100
    return h


def carry_inputs(store: Path = CYCLE8_STORE) -> tuple[dict[str, list[tuple[date, float]]], dict[date, float]]:
    """Per-share cash distributions (ex-date, amount; split-adjusted like ``close``) paid after BUY_DATE up to
    REPORT_DATE, and the cycle-8 monthly margin rate MRATE = (policy_cad at the previous month-end + 1.5%) / 12 for
    each month-end in the same window.  Both come from the verified cycle-8 view."""
    import pandas as pd  # local import: only the snapshot build needs pandas

    from research.cycle8.engine.sleeves import MARGIN_SPREAD

    data_snapshot.verify(Path(store), CYCLE8_VERSION, source=False)
    proc = Path(store).resolve() / "versions" / CYCLE8_VERSION / "view" / "proc"
    lo, hi = pd.Timestamp(BUY_DATE) + pd.Timedelta(days=1), pd.Timestamp(REPORT_DATE)
    divs = {}
    for t in sorted(UNIVERSE):
        d = pd.read_parquet(proc / "etf" / f"{t}.parquet").loc[lo:hi, "dividends"].fillna(0.0)
        divs[t] = [(ts.date(), float(v)) for ts, v in d.items() if v > 0]
    policy = pd.read_parquet(proc / "rates_monthly.parquet")["policy_cad"]
    policy.index = pd.DatetimeIndex(policy.index).to_period("M").to_timestamp("M")
    # month-ends strictly after the buy month (the loan is taken on BUY_DATE, two days before its month-end)
    months = pd.date_range(pd.Timestamp(BUY_DATE) + pd.offsets.MonthEnd(0) + pd.offsets.MonthEnd(1), hi, freq="ME")
    mrate = {}
    for m in months:
        prev = policy.loc[: m - pd.offsets.MonthEnd(1)].dropna()
        mrate[m.date()] = (float(prev.iloc[-1]) + MARGIN_SPREAD) / 12.0
    return divs, mrate


def carry(positions: dict[str, int], cad: float, inputs: tuple | None = None) -> tuple[float, float]:
    """Carry the net CAD balance (negative = margin loan) and USD cash from BUY_DATE to REPORT_DATE, month by month:
    a CAD loan accrues MRATE on the balance at the start of the month; then the month's distributions are paid in
    cash in the listing currency (USD-listed funds net of 15% US withholding).  Positive cash earns nothing
    (broker cash).  Returns (net CAD balance, USD cash)."""
    divs, mrate = inputs if inputs is not None else carry_inputs()
    usd = 0.0
    first = min(mrate)
    for m in sorted(mrate):
        if cad < 0:
            cad *= 1.0 + mrate[m]
        start = date(m.year, m.month, 1) if m != first else BUY_DATE + timedelta(days=1)
        for t, n in sorted(positions.items()):
            paid = sum(v for d, v in divs.get(t, []) if start <= d <= m) * n
            if UNIVERSE[t]["ccy"] == "USD":
                usd += paid * (1.0 - US_WITHHOLDING)
            else:
                cad += paid
    return cad, usd


def _json(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def example_files(rows: list[tuple[date, str, float, str]]) -> dict[str, bytes]:
    """Every config and holdings file of the samples, by file name (written to research/autopilot/examples)."""
    tol = owner_tolerances()
    files: dict[str, bytes] = {}
    for c, a in SAMPLES:
        files[f"config_{c}_{a}.json"] = _json({"config_id": c, "account_type": a, "owner_tolerance_pct": tol[c],
                                               "portfolio_id": f"sample|{c}|{a}", "label": LABEL})
        files[f"hypothetical_holdings_{c}_{a}.json"] = _json(at_target_holdings(c, a, rows))
    # refusal example 1: stale prices (report 8 days after the last price in the snapshot)
    stale = at_target_holdings("P4@1.0", "tfsa", rows)
    stale["as_of"] = STALE_REPORT_DATE.isoformat()
    files["config_P4@1.0_tfsa_refusal_stale.json"] = _json(
        {"config_id": "P4@1.0", "account_type": "tfsa", "owner_tolerance_pct": tol["P4@1.0"],
         "portfolio_id": "sample-refusal-stale|P4@1.0|tfsa", "label": LABEL})
    files["hypothetical_holdings_P4@1.0_tfsa_refusal_stale.json"] = _json(stale)
    # refusal example 2: a TFSA holdings file that shows a margin loan (TFSAs can never borrow)
    loan = at_target_holdings("P3@1.0", "tfsa", rows)
    loan["cash_cad"] = round(loan["cash_cad"] + TFSA_MARGIN_LOAN_CAD, 2)
    loan["margin_loan_cad"] = TFSA_MARGIN_LOAN_CAD
    files["config_P3@1.0_tfsa_refusal_margin.json"] = _json(
        {"config_id": "P3@1.0", "account_type": "tfsa", "owner_tolerance_pct": tol["P3@1.0"],
         "portfolio_id": "sample-refusal-tfsa-margin|P3@1.0|tfsa", "label": LABEL})
    files["hypothetical_holdings_P3@1.0_tfsa_refusal_margin.json"] = _json(loan)
    return files


# ------------------------------------------------------------------------------------------------ runs -------------
def sample_runs() -> list[dict[str, Any]]:
    runs = [{"config": f"config_{c}_{a}.json", "holdings": f"hypothetical_holdings_{c}_{a}.json", "out": a,
             "report_date": REPORT_DATE} for c, a in SAMPLES]
    runs.append({"config": "config_P4@1.0_tfsa_refusal_stale.json",
                 "holdings": "hypothetical_holdings_P4@1.0_tfsa_refusal_stale.json", "out": "refusals",
                 "report_date": STALE_REPORT_DATE})
    runs.append({"config": "config_P3@1.0_tfsa_refusal_margin.json",
                 "holdings": "hypothetical_holdings_P3@1.0_tfsa_refusal_margin.json", "out": "refusals",
                 "report_date": REPORT_DATE})
    return runs


def build(*, examples: Path = EXAMPLES, out: Path = SAMPLES_OUT, store: Path = STORE, version: str = VERSION,
          source_dir: Path = SOURCE_DIR, freeze: bool = True) -> dict[str, Any]:
    manifest_sha = freeze_prices(store, source_dir, version) if freeze else \
        data_snapshot.load_manifest(store, version)["manifest_sha256"]
    rows = price_rows()
    files = example_files(rows)
    examples.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (examples / name).write_bytes(data)
    results = []
    with tempfile.TemporaryDirectory(prefix="autopilot_samples_") as tmp:
        stage = Path(tmp) / "samples"
        log = stage / LOG_NAME
        for run in sample_runs():
            res = cli.run(config=examples / run["config"], holdings=examples / run["holdings"], price_store=store,
                          price_version=version, report_date=run["report_date"], out=stage / run["out"], log=log)
            results.append({"config": run["config"], "report": f"{run['out']}/{res.report_path.name}",
                            "status": res.status, "trades": len(res.summary["trades"]),
                            "refusal_reasons": res.summary["refusal_reasons"], "seq": res.entry["seq"]})
        out.mkdir(parents=True, exist_ok=True)
        shutil.copytree(stage, out, dirs_exist_ok=True)
    return {"manifest_sha256": manifest_sha, "runs": results}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m research.autopilot.make_samples",
                                 description="Freeze the real-price sample snapshot and write HYPOTHETICAL sample "
                                             "reports (research samples, not recommendations).")
    ap.parse_args(argv)
    res = build()
    print(f"{VERSION} manifest_sha256={res['manifest_sha256']}")
    for r in res["runs"]:
        print(f"  seq {r['seq']:>2} {r['status']:<8} trades={r['trades']:<2} {r['report']}"
              + (f"  ({r['refusal_reasons'][0][:100]})" if r["refusal_reasons"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
