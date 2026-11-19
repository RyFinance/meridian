"""Shared loaders for agent_a extended-hours study. All series are indexed by minute END time
in America/New_York (a bar labelled 09:28 covers 09:28-09:29, so its close is the price at 09:29)."""
from __future__ import annotations

import glob
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

H = Path(__file__).parent
R = H.parent
Q = R.parents[1]
NY = "America/New_York"
DEV = ("2026-04-29", "2026-07-15")
TEST = ("2026-07-16", "2026-09-16")


def load_mstr() -> pd.DataFrame:
    base = pd.read_parquet(R / "mstr_stock_1m_lse.parquet")
    extra = [pd.read_parquet(f) for f in sorted(glob.glob(str(H / "stock_1m" / "*.parquet")))]
    d = pd.concat([base] + extra, ignore_index=True)
    d["ts"] = pd.to_datetime(d["ts"])
    if d.ts.dt.tz is not None:
        d["ts"] = d.ts.dt.tz_convert("UTC").dt.tz_localize(None)
    d = d.drop_duplicates("ts", keep="last").sort_values("ts")
    d["label"] = d.ts.dt.tz_localize("UTC").dt.tz_convert(NY)
    d["end"] = d["label"] + pd.Timedelta(minutes=1)
    d["date"] = d["label"].dt.tz_localize(None).dt.normalize()
    d["hm"] = d.label.dt.hour * 100 + d.label.dt.minute
    return d.reset_index(drop=True)


def _zips(pattern: str) -> pd.DataFrame:
    out = []
    for f in sorted(glob.glob(str(Q / "data" / "binance_mstr_token" / pattern))):
        with zipfile.ZipFile(f) as z:
            name = z.namelist()[0]
            df = pd.read_csv(z.open(name), header=None, usecols=[0, 4, 5])
        df = df[pd.to_numeric(df[0], errors="coerce").notna()]
        df.columns = ["open_time", "close", "volume"]
        out.append(df.astype(float))
    df = pd.concat(out).drop_duplicates("open_time")
    end = pd.to_datetime(df.open_time.astype("int64"), unit="ms", utc=True) + pd.Timedelta(minutes=1)
    s = pd.Series(df.close.values, index=end.dt.tz_convert(NY)).sort_index()
    full = pd.date_range(s.index[0], s.index[-1], freq="1min")
    return s.reindex(full).ffill()


def load_btc() -> pd.Series:
    return _zips("BTCUSDT-1m-2026-*.zip")


def load_perp() -> pd.Series:
    return _zips("MSTRUSDT-1m-2026-*.zip")


def load_daily() -> pd.DataFrame:
    y = pd.read_parquet(R / "mstr_daily_yf.parquet")[["Open", "Close"]]
    y.index = pd.to_datetime(y.index).normalize()
    return y


def at(series: pd.Series, ts) -> float:
    """Value of a ffilled minute series at timestamp ts (price as of ts)."""
    i = series.index.searchsorted(ts, side="right") - 1
    return float(series.iloc[i]) if i >= 0 else np.nan


def tstat(x) -> float:
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    return float(x.mean() / x.std(ddof=1) * np.sqrt(len(x))) if len(x) > 2 else np.nan
