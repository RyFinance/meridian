"""Check LSE session reconstruction against yfinance official opens/closes.

    PYTHONPATH=. .venv/bin/python -m research.forward.lse_check \
        --symbols GLD,SPY,AZO --dates 2026-09-17,2026-09-18,2026-09-21,2026-09-22 \
        --out reports/forward/lse_reconstruction_check.json

For each symbol/day it reports the yfinance official open/close, the LSE 30m
regular-session reconstruction, and the raw LSE 1d bar (extended hours, UTC
day), with differences in basis points. Small read-only MCP calls only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import numpy as np

from research.forward import nyse, registry
from research.forward.prices import LSESource, YFSource, parse_lse_csv


def _bps(a, b):
    if a is None or b is None or not np.isfinite(a) or not np.isfinite(b) or b == 0:
        return None
    return round(float((a / b - 1) * 1e4), 2)


def run(symbols: list[str], dates: list[dt.date], lse: LSESource, yfs: YFSource) -> dict:
    start, end = min(dates), max(dates)
    rows = []
    for sym in symbols:
        rth = lse.sessions(sym, start, end)
        daily = {}
        try:
            text = lse.fetcher(sym, "1d", start.isoformat(), (end + dt.timedelta(days=1)).isoformat(), 20)
            d1 = parse_lse_csv(text)
            daily = {t.date(): (float(o), float(c)) for t, o, c in zip(d1["time"], d1["open"], d1["close"])}
        except Exception as e:
            lse.errors[sym + ":1d"] = str(e)[:200]
        yf = yfs.sessions(sym, start - dt.timedelta(days=3), end)
        for day in dates:
            y_open = float(yf.loc[day, "open"]) if day in yf.index else None
            y_close = float(yf.loc[day, "close"]) if day in yf.index else None
            y_close = y_close if y_close is not None and np.isfinite(y_close) else None
            r = rth.loc[day] if day in rth.index else None
            d = daily.get(day)
            rows.append({
                "symbol": sym, "date": day.isoformat(),
                "yf_official_open": y_open, "yf_official_close": y_close,
                "lse_rth_open": float(r["open"]) if r is not None else None,
                "lse_rth_close": float(r["close"]) if r is not None else None,
                "lse_rth_complete": bool(r["complete"]) if r is not None else None,
                "lse_1d_open": d[0] if d else None, "lse_1d_close": d[1] if d else None,
                "rth_open_diff_bps": _bps(float(r["open"]) if r is not None else None, y_open),
                "rth_close_diff_bps": _bps(float(r["close"]) if r is not None else None, y_close),
                "lse_1d_open_diff_bps": _bps(d[0] if d else None, y_open),
                "lse_1d_close_diff_bps": _bps(d[1] if d else None, y_close),
            })
    def summary(key):
        vals = [abs(r[key]) for r in rows if r[key] is not None]
        return {"n": len(vals), "max_abs_bps": max(vals) if vals else None,
                "mean_abs_bps": round(float(np.mean(vals)), 2) if vals else None}
    return {"generated_at_utc": registry.iso_utc(registry.utc_now()), "rows": rows,
            "summary": {k: summary(k) for k in ("rth_open_diff_bps", "rth_close_diff_bps",
                                                  "lse_1d_open_diff_bps", "lse_1d_close_diff_bps")},
            "errors": {"lse": lse.errors, "yfinance": yfs.errors},
            "note": ("yf_official_* = exchange official open/close (auctions). lse_rth_* = LSE 30m bars filtered to "
                     "09:30-16:00 ET (first bar open, last bar close = last continuous trade). lse_1d_* = LSE daily "
                     "bar (UTC day, includes pre/after-hours): not a session price.")}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="GLD,SPY,AZO")
    ap.add_argument("--dates", default="2026-09-17,2026-09-18,2026-09-21,2026-09-22")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    lse, yfs = LSESource(), YFSource()
    try:
        result = run([s.strip() for s in args.symbols.split(",")], [nyse.to_date(d) for d in args.dates.split(",")], lse, yfs)
    finally:
        lse.close()
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
