"""Audit of tsy_month_end: read-only LSE pulls (get_history TLT intraday, macro_series US10Y).

Uses the project's read-only MCP bridge (research.lse_mcp_client, whose whitelist excludes every
order/algo/account tool). Hard cap on MCP calls. Raw results cached under reports/audit_tsy/.

The MCP server truncates each answer at ~60k characters (~1,160 bars), so each call keeps the
bars it returns and the next call restarts at the last (possibly partial) ET day returned.
1h bars are used (clock-aligned, so the 15:00-16:00 ET bar's close is the last regular-session
trade, identical to the 15:30-16:00 30m bar's close) to cover more years within the call budget.

  PYTHONPATH=. .venv/bin/python -m research.audit_tsy.fetch_lse
"""
from __future__ import annotations

import datetime as dt
import io
import json
import sys
from pathlib import Path

import pandas as pd

from research.lse_mcp_client import Terminal, content_text

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "audit_tsy"
USED_BEFORE = 3          # terminal_status, one 30m probe, one truncated 30m call (first script run)
BUDGET = 60
calls = {"n": 0, "log": []}


def call(t: Terminal, name: str, args: dict) -> str:
    if USED_BEFORE + calls["n"] >= BUDGET - 2:          # keep 2 spare
        raise RuntimeError("MCP call budget exhausted")
    assert name in {"get_history", "macro_series"}
    calls["n"] += 1
    res = t.call(name, args, timeout=120)
    txt = content_text(res)
    calls["log"].append({"n": USED_BEFORE + calls["n"], "tool": name, "args": args,
                         "is_error": bool(res.get("isError")), "chars": len(txt),
                         "truncated": "truncated" in txt[-200:], "head": txt[:120]})
    return txt


def csv_block(txt: str, first_col: str) -> pd.DataFrame:
    lines = txt.strip().splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith(first_col + ",")), None)
    if start is None:
        return pd.DataFrame()
    body = [lines[start]] + [l for l in lines[start + 1:] if l[:1].isdigit() and l.count(",") == lines[start].count(",")]
    return pd.read_csv(io.StringIO("\n".join(body)))


def pull_bars(t, symbol, tf, start: dt.date, end: dt.date, max_calls: int) -> pd.DataFrame:
    frames, lo, used = [], start, 0
    while lo <= end and used < max_calls:
        hi = min(end, lo + dt.timedelta(days=299))
        txt = call(t, "get_history", {"symbol": symbol, "timeframe": tf, "start": lo.isoformat(),
                                      "end": (hi + dt.timedelta(days=1)).isoformat(), "limit": 5000,
                                      "provider": "lse"})
        used += 1
        df = csv_block(txt, "time")
        if df.empty:
            lo = hi + dt.timedelta(days=1)
            continue
        df["time"] = pd.to_datetime(df["time"], utc=True)
        et_day = df["time"].dt.tz_convert("America/New_York").dt.date
        if calls["log"][-1]["truncated"]:
            last = et_day.max()
            df = df[et_day < last]               # drop the partial last day, restart there
            lo = last
        else:
            lo = hi + dt.timedelta(days=1)
        frames.append(df)
        print(used, symbol, tf, df["time"].min(), df["time"].max(), len(df), flush=True)
    return pd.concat(frames, ignore_index=True).drop_duplicates("time").sort_values("time") if frames else pd.DataFrame()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with Terminal() as t:
        # 1) 10y yield, date level (LSE bonds dataset)
        ys = []
        for s, e in (("2002-12-01", "2014-12-31"), ("2015-01-01", "2026-09-22")):
            txt = call(t, "macro_series", {"symbol": "US10Y", "dataset": "bonds", "start": s, "end": e,
                                           "limit": 5000, "order": "asc"})
            (OUT / f"lse_US10Y_raw_{s[:4]}.txt").write_text(txt)
            ys.append(txt[:200])
        print(ys, flush=True)
        # 2) TLT 1h bars: validation window first, then development (backwards budget permitting)
        remaining = BUDGET - 2 - USED_BEFORE - calls["n"]
        val = pull_bars(t, "TLT", "1h", dt.date(2014, 12, 20), dt.date(2026, 9, 2), max_calls=remaining)
        if not val.empty:
            val.to_csv(OUT / "lse_TLT_1h_bars_val.csv", index=False)
        remaining = BUDGET - 2 - USED_BEFORE - calls["n"]
        dev = pd.DataFrame()
        if remaining > 0:
            dev = pull_bars(t, "TLT", "1h", dt.date(2007, 1, 1), dt.date(2014, 12, 31), max_calls=remaining)
            if not dev.empty:
                dev.to_csv(OUT / "lse_TLT_1h_bars_dev.csv", index=False)
    (OUT / "lse_mcp_call_log.json").write_text(json.dumps({"calls_this_script": calls["n"],
                                                           "calls_before_script": USED_BEFORE,
                                                           "total_mcp_calls": USED_BEFORE + calls["n"],
                                                           "log": calls["log"]}, indent=1, default=str))
    print("calls", calls["n"], "total", USED_BEFORE + calls["n"])


if __name__ == "__main__":
    try:
        main()
    finally:
        (OUT / "lse_mcp_call_log_partial.json").write_text(json.dumps(calls, indent=1, default=str))
        sys.stdout.flush()
