"""Read-only LSE macro_series pull of government yields and short rates (cycle-6 data pass).

Selection (fixed before any data were looked at beyond catalog metadata): every 'bonds' daily series from the
catalog discovery whose catalog first date is before 2020-01-01 for the target countries, plus the daily/monthly
short-rate 'economics' series listed in ECON. Series starting 2025-07-07 (≈14 months) are not pulled: they cannot
reach the 120-month floor and are recorded as such. Windows keep each call < 5000 rows; a call returning exactly
`limit` rows is flagged truncated. Stops after 3 consecutive failed calls.
"""
from __future__ import annotations

import json

from research.collectors import common as cc
from research.cycle6.data_rates.common import META, RAW, utc_now, write_json
from research.lse_mcp_client import Terminal, content_text

TARGET = {"US", "DE", "JP", "AU", "FR", "IT", "CH", "SE", "NO", "NZ", "ES", "NL", "BE", "AT", "DK", "GB", "CA"}
ECON = ["fdtr", "bojdtr", "japanintrat", "rbatctr", "ausbbsr", "australiaintrat", "szlttr", "swedenintrat",
        "swrratei", "norwayintrat", "nobrdep", "newzealanintrat", "nzocrs", "gbroiar", "ukbrbase", "cclr",
        "debrdisc", "germanyintrat", "franceintrat", "italyintrat", "austriaintrat", "belgiumintrat"]
# Responses are cut at ~60,000 characters (~1,150 rows) with a '... truncated' marker (first run, 19:47Z, which
# was mis-parsed as 3 failures and stopped by the guard). Windows are 4 calendar years; a truncated reply is split
# in half recursively.
WINDOWS = [(f"{y}-01-01", f"{y + 3}-12-31") for y in range(1960, 2027, 4)]
LIMIT = 5000


def main():
    cat = json.loads((META / "lse_discover.json").read_text())["series"]
    todo, skipped = [], []
    for s in cat:
        if s["dataset"] == "bonds" and s["country"] in TARGET:
            (todo if s["first"] < "2020-01-01" else skipped).append(s)
        elif s["dataset"] == "economics" and s["symbol"] in ECON:
            todo.append(s)
    calls, fails, data = [], 0, {}
    with Terminal() as t:
        st = content_text(t.call("terminal_status", {}, timeout=30))
        if "not running" in st.lower():
            write_json(META / "lse_pull.json", {"aborted": "terminal not running"}); return
        for s in todo:
            rows = []
            queue = [(a, b) for a, b in WINDOWS if not (b < s["first"] or a > s["last"])]
            while queue:
                a, b = queue.pop(0)
                args = {"symbol": s["symbol"], "dataset": s["dataset"], "start": a, "end": b, "limit": LIMIT,
                        "order": "asc"}
                if fails >= 3:
                    calls.append({**args, "skipped": "3 consecutive failures"}); continue
                t0 = utc_now()
                try:
                    res = t.call("macro_series", args, timeout=120); txt = content_text(res); err = bool(res.get("isError"))
                except Exception as e:  # noqa: BLE001
                    txt, err = f"EXCEPTION {e!r}", True
                n = None
                trunc = "... truncated" in txt[-300:]
                if not err and not trunc:
                    try:
                        got = json.loads(txt); n = len(got); rows += got
                    except Exception:  # noqa: BLE001
                        err = True
                fails = fails + 1 if err else 0
                rec = cc.write_snapshot("lse_mcp_series", f"{s['dataset']}_{s['symbol']}_{a}", txt.encode(), when=t0,
                                        ext="json", root=RAW, extra_meta={"tool": "macro_series", "arguments": args,
                                                                          "is_error": err})
                calls.append({**args, "err": err, "n": n, "truncated": trunc or n == LIMIT, "path": rec["path"],
                              "fetched_at_utc": rec["fetched_at_utc"]})
                if trunc and not err:
                    import pandas as _pd
                    da, db = _pd.Timestamp(a), _pd.Timestamp(b)
                    mid = da + (db - da) / 2
                    queue[:0] = [(a, f"{mid:%Y-%m-%d}"), (f"{mid + _pd.Timedelta(days=1):%Y-%m-%d}", b)]
            data[f"{s['dataset']}/{s['symbol']}"] = {"meta": s, "rows": rows}
    (RAW / "lse_series_combined.json").write_text(json.dumps(data))
    write_json(META / "lse_pull.json", {"previous_run_note": "19:47Z run: first 3 US5Y calls were truncated replies mis-parsed as errors; guard stopped the run; raw kept", "run_at_utc": utc_now().isoformat(), "n_calls": len(calls), "calls": calls,
                                        "not_pulled_short_history": [f"{s['dataset']}/{s['symbol']} first={s['first']}"
                                                                     for s in skipped]})
    print(len(calls), sum(1 for c in calls if c.get("err")), sum(1 for c in calls if c.get("truncated")))


if __name__ == "__main__":
    main()
