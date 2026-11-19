"""Forward audit of the unchanged frozen P1 signal using local Binance BTC data.

This program intentionally evaluates exactly one rule and writes only the
source-overlap and forward-audit evidence described in PLAN.md.
"""

from __future__ import annotations

import glob
import json
import math
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
ROOT = RESEARCH.parents[1]
BTC_PRIMARY = ROOT.parent / "BTC-Acum" / "data" / "btc_usd_1m_candles_polymarket_arb.parquet"
BTC_BINANCE_DIR = ROOT / "data" / "binance_mstr_token"
MSTR_PATH = RESEARCH / "mstr_daily_yf.parquet"
NY = "America/New_York"
THRESHOLD = 0.02
BP_PER_SIDE = 3.0
FEE_PER_SHARE = 0.005
FORWARD_START = pd.Timestamp("2026-08-11")
FORWARD_END = pd.Timestamp("2026-09-30")


def minute_price_asof(series: pd.Series, target: pd.Timestamp) -> tuple[float, float]:
    """Return the latest raw-minute close <= target and its age in minutes."""
    loc = series.index.searchsorted(target, side="right") - 1
    if loc < 0:
        return np.nan, np.inf
    actual = series.index[loc]
    age = (target - actual).total_seconds() / 60.0
    if age > 5:
        return np.nan, age
    return float(series.iloc[loc]), age


def load_binance() -> pd.Series:
    parts = []
    for path in sorted(glob.glob(str(BTC_BINANCE_DIR / "BTCUSDT-1m-2026-*.zip"))):
        with zipfile.ZipFile(path) as archive:
            inner = archive.namelist()[0]
            part = pd.read_csv(archive.open(inner), header=None, usecols=[0, 4])
        part = part[pd.to_numeric(part[0], errors="coerce").notna()]
        part.columns = ["open_time", "close"]
        parts.append(part)
    raw = pd.concat(parts, ignore_index=True).drop_duplicates("open_time", keep="last")
    raw["ts"] = pd.to_datetime(raw["open_time"].astype("int64"), unit="ms", utc=True).dt.tz_convert(NY)
    return pd.Series(pd.to_numeric(raw["close"], errors="coerce").to_numpy(), index=raw["ts"]).dropna().sort_index()


def load_primary() -> pd.Series:
    raw = pd.read_parquet(BTC_PRIMARY, columns=["timestamp", "close"])
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True).dt.tz_convert(NY)
    return pd.Series(pd.to_numeric(raw["close"], errors="coerce").to_numpy(), index=raw["timestamp"]).dropna().sort_index()


def mstr_sessions() -> pd.DataFrame:
    d = pd.read_parquet(MSTR_PATH)[["Open", "Close"]].copy()
    d.index = pd.to_datetime(d.index).normalize()
    d = d.rename(columns={"Open": "open", "Close": "close"}).sort_index()
    d["prev_date"] = d.index.to_series().shift(1)
    return d


def time_on(date: pd.Timestamp, hour: int, minute: int) -> pd.Timestamp:
    return pd.Timestamp(date).tz_localize(NY) + pd.Timedelta(hours=hour, minutes=minute)


def signal_frame(source: pd.Series, dates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for date, row in dates.iterrows():
        prev = row.prev_date
        if pd.isna(prev):
            continue
        prior_px, prior_age = minute_price_asof(source, time_on(prev, 15, 59))
        open_px, open_age = minute_price_asof(source, time_on(date, 9, 28))
        off = open_px / prior_px - 1.0 if np.isfinite(prior_px) and np.isfinite(open_px) else np.nan
        rows.append(
            {
                "date": date,
                "btc_prev": prior_px,
                "btc_open": open_px,
                "prev_age_min": prior_age,
                "open_age_min": open_age,
                "btc_off": off,
                "selected": bool(np.isfinite(off) and off >= THRESHOLD),
                "mstr_open": float(row.open),
                "mstr_close": float(row.close),
            }
        )
    return pd.DataFrame(rows).set_index("date").sort_index()


def add_returns(frame: pd.DataFrame) -> pd.DataFrame:
    f = frame.copy()
    selected = f["selected"].astype(bool)
    f["gross"] = np.where(selected, f.mstr_close / f.mstr_open - 1.0, 0.0)
    f["net"] = 0.0
    f.loc[selected, "net"] = (
        (f.loc[selected, "mstr_close"] * (1.0 - BP_PER_SIDE / 10_000.0) - FEE_PER_SHARE)
        / (f.loc[selected, "mstr_open"] * (1.0 + BP_PER_SIDE / 10_000.0) + FEE_PER_SHARE)
        - 1.0
    )
    f["equity"] = (1.0 + f["net"]).cumprod()
    f["drawdown"] = f.equity / f.equity.cummax() - 1.0
    return f


def summarize(f: pd.DataFrame) -> dict[str, float | int | str]:
    active = f.loc[f.selected, "net"]
    trade_t = active.mean() / active.std(ddof=1) * math.sqrt(len(active)) if len(active) > 1 and active.std(ddof=1) > 0 else np.nan
    return {
        "eligible_sessions": len(f),
        "active_trades": int(f.selected.sum()),
        "mean_active_net_bp": float(active.mean() * 1e4) if len(active) else np.nan,
        "active_trade_t": float(trade_t),
        "net_compound": float(f.equity.iloc[-1] - 1.0) if len(f) else np.nan,
        "max_drawdown": float(f.drawdown.min()) if len(f) else np.nan,
        "first_date": str(f.index.min().date()) if len(f) else None,
        "last_date": str(f.index.max().date()) if len(f) else None,
    }


def main() -> None:
    sessions = mstr_sessions()
    binance = load_binance()
    primary = load_primary()
    b = signal_frame(binance, sessions)
    p = signal_frame(primary, sessions)

    overlap_dates = b.index.intersection(p.index)
    overlap = pd.DataFrame(
        {
            "primary_btc_off": p.loc[overlap_dates, "btc_off"],
            "binance_btc_off": b.loc[overlap_dates, "btc_off"],
            "primary_selected": p.loc[overlap_dates, "selected"],
            "binance_selected": b.loc[overlap_dates, "selected"],
        }
    ).dropna(subset=["primary_btc_off", "binance_btc_off"])
    # Only the intended pre-tail August overlap is a source-comparison set.
    overlap = overlap.loc[(overlap.index >= pd.Timestamp("2026-08-03")) & (overlap.index <= pd.Timestamp("2026-08-10"))]
    overlap["same_selection"] = overlap.primary_selected.eq(overlap.binance_selected)
    overlap.to_csv(HERE / "source_overlap.csv")

    forward = b.loc[(b.index >= FORWARD_START) & (b.index <= FORWARD_END)].copy()
    forward = add_returns(forward)
    forward.to_csv(HERE / "forward_sessions.csv")
    result = {
        "fixed_rule": "P1: BTC off-hours >= +2%, MSTR open-to-close, 3 bp + $0.005/share per side",
        "binance_coverage": [str(binance.index.min()), str(binance.index.max())],
        "overlap_sessions": len(overlap),
        "overlap_threshold_agreement": float(overlap.same_selection.mean()) if len(overlap) else np.nan,
        "overlap_max_abs_btc_off_difference_bp": float((overlap.primary_btc_off - overlap.binance_btc_off).abs().max() * 1e4) if len(overlap) else np.nan,
        "forward": summarize(forward),
        "source_transition_caveat": "Binance BTCUSDT perpetual is a different source from the original BTC minute file; this is a forward audit only.",
    }
    (HERE / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
