"""Run exactly one registered development experiment from a verified snapshot.

The parsers stop at each experiment's locked boundary before converting any
holdout price/factor cells to numbers. No validation or holdout return is made.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook

from research.amendment4 import calib

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "sol_beyond_menu"
PREREG = {
    "overnight_equity": ("PREREG_OVERNIGHT.md", "df3d65bf81ebf25250cdf98b7d78eafb77e3ab9797a42034874b812b629431cd"),
    "aggregate_short_interest": ("PREREG_SHORT_INTEREST.md", "d77e20027cb3f4be528a9631a07a9fb08f7c794c9d173e06ebc8d7256d32ba2d"),
    "factor_momentum": ("PREREG_FACTOR_MOMENTUM.md", "f8f4da097b12b17b46d6daa14f73d70b17d4a6b93871c6f2a9ea4376300e5b58"),
    "scheduled_fomc_risk": ("PREREG_FOMC_RISK.md", "a976ab95251fed2526343b936b6057077b2d09c95b0cc2332a4e72ec6d811d1f"),
}
CUTOFF = {"overnight_equity": "2014-12-31", "aggregate_short_interest": "2016-12-31",
          "factor_momentum": "2013-12-31", "scheduled_fomc_risk": "2012-12-31"}


def _spy_until(path: Path, cutoff: str) -> pd.DataFrame:
    rows = []
    with path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            if row["Date"] > cutoff:
                break
            rows.append({"date": pd.Timestamp(row["Date"]), "open": float(row["Open"]),
                         "close": float(row["Close"]), "dividend": float(row["Dividends"] or 0),
                         "split": float(row["Stock Splits"] or 0)})
    frame = pd.DataFrame(rows).set_index("date")
    if frame.empty or (frame["split"] != 0).any() or not frame.index.is_monotonic_increasing:
        raise ValueError("SPY input failed chronology/split checks")
    return frame


def _french_until(path: Path, cutoff_month: str) -> pd.DataFrame:
    rows = []
    with zipfile.ZipFile(path) as archive:
        with io.TextIOWrapper(archive.open(archive.namelist()[0]), encoding="utf-8-sig") as stream:
            for line in stream:
                cells = [cell.strip() for cell in line.split(",")]
                if not cells or len(cells[0]) != 6 or not cells[0].isdigit():
                    continue
                if cells[0] > cutoff_month:
                    break
                rows.append([pd.Period(cells[0], freq="M"), *[float(value) / 100 for value in cells[1:7]]])
    frame = pd.DataFrame(rows, columns=["month", "Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"])
    if frame.empty or frame.month.duplicated().any():
        raise ValueError("French factor chronology invalid")
    return frame.set_index("month")


def _sii_until(path: Path, cutoff_month: str) -> pd.Series:
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    header = [str(value) for value in next(rows)]
    date_col = header.index("date")
    signal_col = header.index("siiOutOfSample")
    values = {}
    for row in rows:
        month = pd.Period(row[date_col], freq="M")
        if month > pd.Period(cutoff_month, freq="M"):
            break
        if row[signal_col] not in (None, "NA", ""):
            values[month] = float(row[signal_col])
    workbook.close()
    return pd.Series(values, name="SII", dtype=float).sort_index()


def _spy_monthly(frame: pd.DataFrame) -> pd.Series:
    prev = frame.close.shift(1)
    daily = (frame.close + frame.dividend) / prev - 1
    daily = daily.dropna()
    return (1 + daily).groupby(daily.index.to_period("M")).prod() - 1


def overnight(view: Path) -> tuple[pd.DataFrame, int]:
    spy = _spy_until(view / "raw/spy_ohlc_1993_2022.csv", CUTOFF["overnight_equity"])
    prev = spy.close.shift(1)
    overnight_raw = (spy.open + spy.dividend - prev) / prev
    intraday_raw = (spy.close - spy.open) / spy.open
    frame = pd.DataFrame({"overnight_gross": overnight_raw, "intraday_gross": intraday_raw}).dropna()
    frame = frame.loc[frame.index <= pd.Timestamp(CUTOFF["overnight_equity"])]
    frame["active_gross"] = frame.overnight_gross - frame.intraday_gross
    frame["active_net"] = frame.active_gross - 0.0008
    frame["active_stress"] = frame.active_gross - 0.0016
    return frame, 252


def short_interest(view: Path) -> tuple[pd.DataFrame, int]:
    spy = _spy_until(view / "raw/spy_ohlc_1993_2022.csv", CUTOFF["aggregate_short_interest"])
    monthly = _spy_monthly(spy)
    ff = _french_until(view / "raw/french_ff5_monthly.zip", "201612")
    sii = _sii_until(view / "raw/rrz_sii_1973_2021.xlsx", "2016-12")
    data = pd.concat([monthly.rename("market_total"), ff.RF, sii], axis=1, join="inner").dropna()
    data["excess"] = data.market_total - data.RF
    first = pd.Period("2004-01", freq="M")
    last = pd.Period("2016-12", freq="M")
    output = []
    previous_signal = previous_control = 0.0
    for target in data.loc[first:last].index:
        formation = target - 1
        history = data.loc[:formation]
        pairs = pd.DataFrame({"x": history.SII.shift(1), "y": history.excess}).dropna()
        # Forecast regression uses pairs through t-1, as preregistered.
        pairs = pairs.iloc[:-1]
        if len(pairs) < 120 or len(history) < 120:
            raise ValueError(f"insufficient short-interest training at {target}")
        design = np.column_stack([np.ones(len(pairs)), pairs.x.to_numpy()])
        coeff = np.linalg.lstsq(design, pairs.y.to_numpy(), rcond=None)[0]
        predicted = coeff[0] + coeff[1] * history.SII.iloc[-1]
        baseline = history.excess.iloc[:-1].mean()
        variance = history.excess.iloc[-120:].var(ddof=1)
        if variance <= 0:
            raise ValueError("nonpositive forecast variance")
        signal_weight = float(np.clip(predicted / (3 * variance), -0.5, 1.5))
        control_weight = float(np.clip(baseline / (3 * variance), -0.5, 1.5))
        signal_turnover = abs(signal_weight - previous_signal)
        control_turnover = abs(control_weight - previous_control)
        output.append({"month": target, "market_excess": data.at[target, "excess"],
                       "signal_weight": signal_weight, "control_weight": control_weight,
                       "gross_difference": (signal_weight-control_weight) * data.at[target, "excess"],
                       "total_turnover": signal_turnover + control_turnover})
        previous_signal, previous_control = signal_weight, control_weight
    frame = pd.DataFrame(output).set_index("month")
    exposure = (frame.signal_weight - frame.control_weight).mean()
    frame["active_gross"] = frame.gross_difference - exposure * frame.market_excess
    frame["active_net"] = frame.active_gross - 0.0005 * frame.total_turnover
    frame["active_stress"] = frame.active_gross - 0.001 * frame.total_turnover
    return frame, 12


def factor_momentum(view: Path) -> tuple[pd.DataFrame, int]:
    factors = _french_until(view / "raw/french_ff5_monthly.zip", "201312")
    names = ["SMB", "HML", "RMW", "CMA"]
    factors = factors[names]
    prior = factors.rolling(12, min_periods=12).sum().shift(1)
    weights = np.sign(prior) / len(names)
    weights = weights.loc[pd.Period("1990-01", freq="M"):pd.Period("2013-12", freq="M")]
    factors = factors.loc[weights.index]
    if weights.isna().any().any() or len(weights) != 288:
        raise ValueError("factor momentum development window invalid")
    exposure = weights.mean(axis=0)
    dynamic = (weights * factors).sum(axis=1)
    static = (factors * exposure).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1)
    turnover.iloc[0] = weights.iloc[0].abs().sum()
    gross_exposure = weights.abs().sum(axis=1)
    frame = pd.DataFrame({"dynamic_gross": dynamic, "static_control": static,
                          "gross_exposure": gross_exposure, "turnover": turnover})
    frame["active_gross"] = dynamic - static
    frame["active_net"] = frame.active_gross - 0.001 * frame.gross_exposure - 0.0005 * frame.turnover
    frame["active_stress"] = frame.active_gross - 0.002 * frame.gross_exposure - 0.001 * frame.turnover
    return frame, 12


def scheduled_fomc_risk(view: Path) -> tuple[pd.DataFrame, int]:
    spy = _spy_until(view / "raw/spy_ohlc_1993_2022.csv", CUTOFF["scheduled_fomc_risk"])
    ff = _french_until(view / "raw/french_ff5_monthly.zip", "201212")
    event_dates = []
    with (view / "raw/scheduled_fomc_dates.csv").open(newline="") as stream:
        for row in csv.DictReader(stream):
            if row["date"] > CUTOFF["scheduled_fomc_risk"]:
                break
            event_dates.append(pd.Timestamp(row["date"]))
    events = pd.DatetimeIndex(event_dates)
    if events.empty or events.duplicated().any() or not events.is_monotonic_increasing:
        raise ValueError("FOMC event dates invalid")
    daily_total = (spy.close + spy.dividend) / spy.close.shift(1) - 1
    eligible = spy.loc["1994-01-01":"2012-12-31"].index
    if not events.isin(eligible).all():
        raise ValueError("scheduled FOMC event on a nontrading day")
    month = eligible.to_period("M")
    counts = pd.Series(1, index=eligible).groupby(month).sum()
    rf_daily = pd.Series([ff.at[m, "RF"] / counts[m] for m in month], index=eligible)
    excess = daily_total.loc[eligible] - rf_daily
    on = pd.Series(eligible.isin(events).astype(float), index=eligible)
    frame = pd.DataFrame({"market_excess": excess, "event": on})
    frame["active_gross"] = (frame.event - frame.event.mean()) * frame.market_excess
    frame["active_net"] = frame.active_gross - .0004 * frame.event
    frame["active_stress"] = frame.active_gross - .0008 * frame.event
    return frame, 252


def summarize(frame: pd.DataFrame, ppy: int, experiment: str) -> dict:
    x = frame.active_net.to_numpy(dtype=float)
    if not np.isfinite(x).all():
        raise ValueError("nonfinite development active returns")
    crash = (0.2 / 252, -6.0) if experiment == "scheduled_fomc_risk" else None
    inference = calib.calibrated_pvalues(x[None, :], overlap=1, B=159,
                                         seed=20260926 + list(PREREG).index(experiment),
                                         full=True, bandwidth_fraction=0.20, crash=crash)
    L = int(inference["L"])
    lrv = float(calib.obm_lrv(x, L + 1) if L > 16 else calib.nw_lrv(x, L))
    variance = float(x.var())
    D = max(1.0, lrv / variance) if variance > 0 else math.inf
    years = pd.Index(frame.index.year)
    yearly = frame.active_net.groupby(years).sum()
    total = float(yearly.sum())
    concentration = float(yearly.max() / total) if total > 0 else None
    sharpe = float(x.mean() / x.std(ddof=1) * math.sqrt(ppy)) if x.std(ddof=1) > 0 else math.nan
    stressed_mean = float(frame.active_stress.mean())
    threshold = 0.05 / len(PREREG)
    return {"experiment": experiment, "status": "DEVELOPMENT_ONLY", "n": len(x),
            "first": str(frame.index[0]), "last": str(frame.index[-1]),
            "mean_annualized": float(x.mean() * ppy), "active_sharpe": sharpe,
            "calibrated_p": float(inference["p"][0]), "a4_t": float(inference["t"][0]),
            "a4_ar_order": int(inference["ar_order"][0]), "a4_bandwidth": L,
            "effective_n": float(len(x) / D), "variance_inflation_D": D,
            "stress_mean_annualized": stressed_mean * ppy,
            "max_year_share_of_total_pnl": concentration,
            "largest_year": int(yearly.idxmax()), "yearly_active_pnl": {str(k): float(v) for k, v in yearly.items()},
            "positive_threshold": threshold,
            "positive": bool(float(inference["p"][0]) < threshold and stressed_mean > 0
                             and concentration is not None and concentration <= .40)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", choices=tuple(PREREG), required=True)
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument("--membership", type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get("QUANT_DATA_MANIFEST_SHA256"):
        raise RuntimeError("run through research.data_snapshot registered runner only")
    name, expected = PREREG[args.experiment]
    actual = hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f"preregistration changed: {args.experiment}")
    if args.membership != args.snapshot_root / "raw/universe.json":
        raise RuntimeError("unexpected universe artifact")
    membership = json.loads(args.membership.read_text())
    if membership["dataset_version"] != os.environ["QUANT_DATASET_VERSION"]:
        raise RuntimeError("universe version mismatch")
    lookup = {"overnight_equity": overnight, "aggregate_short_interest": short_interest,
              "factor_momentum": factor_momentum, "scheduled_fomc_risk": scheduled_fomc_risk}
    frame, ppy = lookup[args.experiment](args.snapshot_root)
    result = summarize(frame, ppy, args.experiment)
    result["manifest_sha256"] = os.environ["QUANT_DATA_MANIFEST_SHA256"]
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / f"{args.experiment}_dev.csv", float_format="%.12g")
    (OUT / f"{args.experiment}_result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "yearly_active_pnl"}, allow_nan=False))


if __name__ == "__main__":
    main()
