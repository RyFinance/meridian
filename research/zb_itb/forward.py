"""Forward paper test zb_itb_v1 (see FORWARD_PLAN.md). Paper only: no orders anywhere.

    PYTHONPATH=. .venv/bin/python -m research.zb_itb.forward register   # once
    PYTHONPATH=. .venv/bin/python -m research.zb_itb.forward run        # NYSE days, launch ~09:05 ET
    PYTHONPATH=. .venv/bin/python -m research.zb_itb.forward evaluate   # any time after 10:35 ET

`run` reads ZB=F 60m bars (yfinance), records d = sign(ln(P_09:00 / P_prev16:00)) before 09:29:30 ET.
`evaluate` scores d * ln(ITB 09:30 bar close / open) from yfinance 60m. --dry-run writes nothing."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics as st
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from research.forward import nyse, registry

ET = ZoneInfo("America/New_York")
H = Path(__file__).parent
ROOT = registry.ROOT
REG = registry.DEFAULT_REGISTRY
STRATEGY = "zb_itb_v1"
DECIDE_FROM, DECIDE_BY, T_IN = dt.time(9, 15), dt.time(9, 29, 30), dt.time(9, 30)
COSTS_BP_SIDE = (2, 5)


def frozen_spec() -> dict:
    return {"strategy_id": STRATEGY, "plan_sha256": registry.sha256_file(H / "FORWARD_PLAN.md"),
            "code_sha256": {"research/zb_itb/forward.py": registry.sha256_file(H / "forward.py")},
            "rule": "NYSE sessions: d=sign(ln(ZB=F 60m close@09:00 ET / close@16:00 ET prev session)); d*ITB 09:30->10:30 ET",
            "gate": {"final_n": 250, "pass": "gross t>=1.65 AND net@2bp/side mean>0", "kill": "cum net@2bp/side <= -8%"}}


def _bars(sym: str, period: str = "7d"):
    import yfinance as yf
    d = yf.download(sym, period=period, interval="60m", auto_adjust=False, progress=False)
    d.columns = d.columns.get_level_values(0)
    d.index = d.index.tz_convert(ET)
    return d


def _bar_close_ending(d, end: dt.datetime):
    """Close of the 60m bar that starts at end-60m (i.e. ends at `end`)."""
    import pandas as pd
    t = pd.Timestamp(end - dt.timedelta(hours=1))
    return float(d.loc[t, "Close"]) if t in d.index else None


def signal(day: dt.date) -> dict:
    prev = nyse.previous_session(day)
    zb = _bars("ZB=F")
    p0 = _bar_close_ending(zb, dt.datetime.combine(prev, dt.time(16, 0), ET))
    p1 = _bar_close_ending(zb, dt.datetime.combine(day, dt.time(9, 0), ET))
    d = 0 if not (p0 and p1) or p1 == p0 else (1 if p1 > p0 else -1)
    return {"prev_session": prev.isoformat(), "zb_p0_prev1600": p0, "zb_p1_0900": p1, "d": d}


def register(dry: bool) -> None:
    spec = frozen_spec(); h = registry.spec_hash(spec)
    payload = {"evaluation": {"type": "etf_window", "instruments": ["ITB"], "capital_usd": 10000,
                              "decision_rule": "nyse_sessions", "execution": "09:30-10:30 ET"}, "spec": spec}
    if dry:
        print(json.dumps(payload, indent=2), "\nspec_hash", h); return
    rec = registry.append(REG, "spec_registration", strategy_id=STRATEGY, spec_hash=h, payload=payload)
    print("registered seq", rec["seq"], h)


def run(dry: bool) -> None:
    day = dt.datetime.now(ET).date()
    if not nyse.is_session(day):
        print(f"{day}: not an NYSE session"); return
    while dt.datetime.now(ET).time() < DECIDE_FROM:
        time.sleep(20)
    sig = None
    while dt.datetime.now(ET).time() < DECIDE_BY:
        try:
            sig = signal(day)
            if sig["zb_p1_0900"] is not None:
                break
        except Exception as e:  # noqa: BLE001 - retry until the deadline
            sig = {"error": repr(e)}
        time.sleep(30)
    now = registry.utc_now()
    if dt.datetime.now(ET).time() >= DECIDE_BY and not dry:
        print("past the decision deadline; missed", sig); return
    t_in = dt.datetime.combine(day, T_IN, ET)
    payload = {"targets": {"ITB": float(sig.get("d", 0) if sig else 0)}, "signal": sig,
               "source_decided_at_utc": registry.iso_utc(now), "entry_et": t_in.isoformat(),
               "exit_et": dt.datetime.combine(day, dt.time(10, 30), ET).isoformat()}
    if dry:
        print("would record", json.dumps(payload, indent=2)); return
    rec = registry.append(REG, "decision", strategy_id=STRATEGY, spec_hash=registry.spec_hash(frozen_spec()),
                          market_asof=sig.get("prev_session") if sig else None,
                          intended_execution_utc=registry.iso_utc(t_in.astimezone(dt.timezone.utc)),
                          decision_key=day.isoformat(), payload=payload)
    print("recorded seq", rec["seq"], payload["targets"])


def evaluate(out: Path) -> dict:
    from research.forward.evaluate import classify
    import pandas as pd
    recs = registry.load_records(REG)
    live, _ = registry.live_decisions(recs)
    mine = [d for d in live if d["strategy_id"] == STRATEGY]
    itb = _bars("ITB", "60d") if mine else None
    rows = []
    for d in mine:
        day = nyse.to_date(d["decision_key"])
        if classify(d):
            rows.append({"day": d["decision_key"], "excluded": classify(d)}); continue
        k = d["payload"]["targets"].get("ITB", 0)
        if not k:
            rows.append({"day": d["decision_key"], "no_trade": True}); continue
        t = pd.Timestamp(dt.datetime.combine(day, T_IN, ET))
        if itb is None or t not in itb.index or dt.datetime.now(ET) < dt.datetime.combine(day, dt.time(10, 35), ET):
            continue
        g = k * math.log(float(itb.loc[t, "Close"]) / float(itb.loc[t, "Open"]))
        rows.append({"day": d["decision_key"], "d": k, "gross": g, **{f"net_{c}bp": g - 2 * c / 1e4 for c in COSTS_BP_SIDE}})
    sc = [r for r in rows if "gross" in r]
    s = {"n": len(sc)}
    if len(sc) >= 2:
        g = [r["gross"] for r in sc]; sd = st.stdev(g)
        s.update(gross_mean_bp=st.mean(g) * 1e4, t=st.mean(g) / sd * len(g) ** .5 if sd else None,
                 hit=sum(x > 0 for x in g) / len(g),
                 long_only_net2_mean_bp=(st.mean([r["net_2bp"] for r in sc if r["d"] > 0]) * 1e4 if any(r["d"] > 0 for r in sc) else None),
                 **{f"cum_net_{c}bp_pct": sum(r[f"net_{c}bp"] for r in sc) * 100 for c in COSTS_BP_SIDE})
        s["kill"] = s["cum_net_2bp_pct"] <= -8
        s["gate"] = "pending" if len(sc) < 250 else ("PASS" if (s["t"] or 0) >= 1.65 and s["cum_net_2bp_pct"] > 0 else "FAIL")
    res = {"strategy": STRATEGY, "summary": s, "trades": rows}
    out.write_text(json.dumps(res, indent=2, default=str)); print(json.dumps(s, indent=2, default=str))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["register", "run", "evaluate"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "forward" / "zb_itb_eval.json")
    a = ap.parse_args()
    {"register": lambda: register(a.dry_run), "run": lambda: run(a.dry_run), "evaluate": lambda: evaluate(a.out)}[a.cmd]()
