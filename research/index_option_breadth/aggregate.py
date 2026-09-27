"""Source-only aggregation of LSE OPRA ETF option trade volume, no returns."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/lse/index_option_breadth"
SYMBOLS = ("SPY", "QQQ", "IWM")


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cutoff = pd.Timestamp("2019-12-31", tz="UTC")
    frames = []
    audit = {}
    for symbol in SYMBOLS:
        path = ROOT / f"data/lse/options_etf_1d/{symbol}.parquet"
        frame = pd.read_parquet(path, columns=["ts", "expiry", "opt_type", "osi", "volume"],
                                filters=[("ts", "<=", cutoff)])
        if frame.empty or frame.ts.max() > cutoff or not frame.opt_type.isin(["P", "C"]).all():
            raise RuntimeError(f"Invalid {symbol} time or type")
        if (frame.volume <= 0).any() or frame.duplicated(["ts", "osi"]).any():
            raise RuntimeError(f"Nonpositive/duplicated {symbol} contract volume")
        if not (frame.ts.dt.strftime("%H:%M") == "00:00").all():
            raise RuntimeError(f"Unexpected {symbol} daily timestamp convention")
        frame["date"] = frame.ts.dt.tz_localize(None).dt.normalize()
        dte = (pd.to_datetime(frame.expiry) - frame.date).dt.days
        selected = frame[(dte >= 7) & (dte <= 30)].copy()
        grouped = selected.groupby(["date", "opt_type"], observed=True).volume.sum().unstack(fill_value=0)
        if not {"P", "C"}.issubset(grouped.columns):
            raise RuntimeError(f"Incomplete put/call types for {symbol}")
        frames.append(grouped[["P", "C"]])
        audit[symbol] = {"source_rows": len(frame), "selected_rows": len(selected),
                         "source_dates": frame.date.nunique(), "selected_dates": len(grouped),
                         "first": frame.date.min().date().isoformat(),
                         "last": frame.date.max().date().isoformat(), "source_sha256": digest(path)}
    # A day must be present for all three ETFs; no forward filling of absent option volume.
    common = frames[0].index.intersection(frames[1].index).intersection(frames[2].index)
    summed = sum(f.reindex(common) for f in frames)
    daily = summed.rename(columns={"P": "put_volume", "C": "call_volume"}).reset_index()
    if (daily[["put_volume", "call_volume"]] <= 0).any().any():
        raise RuntimeError("Zero aggregate option volume")
    daily["week"] = daily.date.dt.to_period("W-SUN")
    weekly = daily.groupby("week").agg(put_volume=("put_volume", "sum"),
                                       call_volume=("call_volume", "sum"),
                                       option_days=("date", "nunique"))
    weekly["week_start"] = weekly.index.start_time
    weekly["week_end"] = weekly.index.end_time.normalize()
    weekly = weekly.reset_index(drop=True)[["week_start", "week_end", "put_volume", "call_volume", "option_days"]]
    daily = daily.drop(columns="week")
    dp, wp = OUT / "daily_2014_2019.parquet", OUT / "weekly_2014_2019.parquet"
    daily.to_parquet(dp, index=False)
    weekly.to_parquet(wp, index=False)
    manifest = {"source": "LSE OPRA options_1d per-contract trade OHLCV",
                "rule": "sum positive trade volume for P/C contracts with calendar DTE 7..30, common SPY/QQQ/IWM dates",
                "symbols": audit, "daily_rows": len(daily), "weekly_rows": len(weekly),
                "first_date": daily.date.min().date().isoformat(),
                "last_date": daily.date.max().date().isoformat(),
                "daily_sha256": digest(dp), "weekly_sha256": digest(wp)}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: manifest[k] for k in ("daily_rows", "weekly_rows", "first_date", "last_date", "symbols")}, indent=2))


if __name__ == "__main__":
    main()
