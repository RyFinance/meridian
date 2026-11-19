"""Forward paper test mstr_btc_offth_v1 (see SHARES_FORWARD_PLAN.md). Commands:

    PYTHONPATH=. .venv/bin/python -m research.mstr_btc_0dte.forward_off register
    PYTHONPATH=. .venv/bin/python -m research.mstr_btc_0dte.forward_off decide       # any NYSE session, before 09:25 ET
    PYTHONPATH=. .venv/bin/python -m research.mstr_btc_0dte.forward_off close        # before 16:00 ET
    PYTHONPATH=. .venv/bin/python -m research.mstr_btc_0dte.forward_off evaluate

Same rules/costs/sim discipline as forward.py (mstr_btc_monday_v1), but the decision is
made every NYSE session and traded only when |BTC off-hours move| >= THRESH (1%).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from research.forward import nyse, registry
from research.mstr_btc_0dte.forward import _get, _log_sim, _sleep_until, _sim, btc_close_at, mstr_fallback_px
from research.mstr_btc_0dte.forward import NOTIONAL, SIM_ACCOUNT, SYMBOL, UA  # noqa: F401 (frozen shared constants)

ET = ZoneInfo("America/New_York")
H = Path(__file__).parent
STRATEGY = "mstr_btc_offth_v1"
THRESH = 0.01
DECIDE_AT, DECIDE_LATEST = dt.time(9, 25, 0), dt.time(9, 29, 30)
ORDER_AT, CLOSE_AT = dt.time(9, 30, 20), dt.time(15, 59, 0)


def frozen_spec() -> dict:
    names = ["forward_off.py", "forward.py", "costs.py", "SHARES_FORWARD_PLAN.md"]
    code = {f"research/mstr_btc_0dte/{n}": registry.sha256_file(H / n) for n in names}
    code.update({f"research/forward/{n}": registry.sha256_file(H.parents[0] / "forward" / n)
                 for n in ("nyse.py", "registry.py", "prices.py", "evaluate.py")})
    return {"strategy": STRATEGY, "thresh": THRESH, "notional_usd": NOTIONAL,
            "btc_source": "coinbase BTC-USD 1m close", "decision_time": "09:25 ET",
            "code_sha256": code}


def current_spec_hash() -> str:
    return registry.spec_hash(frozen_spec())


def decide(dry: bool, day: dt.date | None = None) -> None:
    day = day or dt.datetime.now(ET).date()
    if not nyse.is_session(day):
        print(f"{day}: not a NYSE session; no decision")
        return
    t_dec = dt.datetime.combine(day, DECIDE_AT, ET)
    _sleep_until(t_dec.astimezone(dt.timezone.utc) + dt.timedelta(seconds=3))
    if dt.datetime.now(ET).time() > DECIDE_LATEST and not dry:
        print(f"{dt.datetime.now(ET)}: past {DECIDE_LATEST} ET; decision window missed")
        return
    prev = nyse.previous_session(day)
    p0, p1 = btc_close_at(nyse.close_utc(prev)), btc_close_at(t_dec)
    r = _safe_log(p0, p1)
    d = 0 if abs(r) < THRESH else (1 if r > 0 else -1)
    payload = {"btc_source": "coinbase BTC-USD 1m close", "btc_prev_close_px": p0, "btc_0925_px": p1,
               "btc_log_ret": r, "abs_thresh": THRESH, "traded": bool(d), "direction": d,
               "targets": {SYMBOL: float(d)} if d else {}, "notional_usd": NOTIONAL,
               "prev_session": prev.isoformat(), "exit_utc": registry.iso_utc(nyse.close_utc(day))}
    print(json.dumps(payload, indent=2))
    if dry:
        return
    rec = registry.append(registry.DEFAULT_REGISTRY, "decision", strategy_id=STRATEGY,
                          spec_hash=current_spec_hash(), market_asof=prev.isoformat(),
                          intended_execution_utc=registry.iso_utc(nyse.open_utc(day)),
                          decision_key=day.isoformat(), payload=payload)
    print("recorded seq", rec["seq"])
    if d == 0:
        return
    _sleep_until(dt.datetime.combine(day, ORDER_AT, ET).astimezone(dt.timezone.utc))
    try:
        q = _sim("GET", "/api/prices", {"provider": "lse", "symbols": SYMBOL})
        px = float((q[0] if isinstance(q, list) else q).get("ask" if d > 0 else "bid") or 0)
    except Exception:
        px = 0.0
    try:
        qty = int(NOTIONAL // (px or mstr_fallback_px()))
        res = _sim("POST", "/api/sim/orders", body={"account_id": SIM_ACCOUNT, "symbol": SYMBOL,
                                                    "side": "buy" if d > 0 else "sell", "otype": "market", "qty": qty})
        _log_sim({"strategy": STRATEGY, "day": day.isoformat(), "event": "open", "qty": qty,
                  "direction": d, "quote": px, "result": res})
    except Exception as e:
        _log_sim({"strategy": STRATEGY, "day": day.isoformat(), "event": "open_failed", "error": repr(e)})
        print("sim order failed:", e)


def _safe_log(p0: float, p1: float) -> float:
    import math
    return math.log(p1 / p0) if p0 > 0 and p1 > 0 else 0.0


def _engine() -> str:
    import urllib.request
    for port in range(7799, 7819):
        try:
            h = _get(f"http://127.0.0.1:{port}/api/health", timeout=2)
            if isinstance(h, dict) and "ui_version" in h:
                return f"http://127.0.0.1:{port}"
        except Exception:
            continue
    raise RuntimeError("LSE Terminal engine not running on 127.0.0.1:7799-7818")


def close(dry: bool) -> None:
    day = dt.datetime.now(ET).date()
    if not nyse.is_session(day):
        print(f"{day}: not a NYSE session")
        return
    end = dt.datetime.combine(day, CLOSE_AT, ET) if nyse.session_close_time(day) == dt.time(16, 0) \
        else dt.datetime.combine(day, nyse.session_close_time(day), ET) - dt.timedelta(minutes=1)
    _sleep_until(end.astimezone(dt.timezone.utc))
    if dry:
        print("would close", SYMBOL, "on sim account", SIM_ACCOUNT)
        return
    try:
        res = _sim("POST", "/api/sim/close", {"account_id": SIM_ACCOUNT, "symbol": SYMBOL})
        _log_sim({"strategy": STRATEGY, "day": day.isoformat(), "event": "close", "result": res})
    except Exception as e:
        _log_sim({"strategy": STRATEGY, "day": day.isoformat(), "event": "close_failed", "error": repr(e)})
        print("sim close failed:", e)


def evaluate(out: Path | None) -> dict:
    import numpy as np
    from research.forward.evaluate import classify
    from research.forward.prices import default_pricebook
    from research.mstr_btc_0dte.costs import round_trip_return
    recs = registry.load_records(registry.DEFAULT_REGISTRY)
    live, _ = registry.live_decisions(recs)
    ds = [d for d in live if d["strategy_id"] == STRATEGY]
    counted, excluded, rows = [], [], []
    for d in ds:
        (excluded if (classify(d) or not d["payload"].get("traded")) else counted).append(d)
    book = default_pricebook()
    try:
        for d in counted:
            day = nyse.to_date(d["decision_key"])
            if day >= dt.datetime.now(ET).date() and dt.datetime.now(dt.timezone.utc) < nyse.close_utc(day) + dt.timedelta(minutes=15):
                continue
            px = book.get(SYMBOL, day, day)
            if day not in px.index or px.loc[day, "close"] is None:
                rows.append({"day": day.isoformat(), "status": "no official prices yet"})
                continue
            o, c = float(px.loc[day, "open"]), float(px.loc[day, "close"])
            dirn = int(d["payload"]["direction"])
            b, s = round_trip_return(dirn, o, c, NOTIONAL), round_trip_return(dirn, o, c, NOTIONAL, stress=True)
            rows.append({"day": day.isoformat(), "direction": dirn, "open": o, "close": c,
                         "gross": b["gross"], "net": b["net"], "stress_net": s["net"], "cost_usd": b["cost_usd"]})
    finally:
        book.close()
    scored = [r for r in rows if "net" in r]
    sessions = len([d for d in ds if d["payload"].get("traded") is not None])   # decisions incl. no-trade
    net = np.array([r["net"] for r in scored])
    summary = {"n_decisions": sessions, "n_traded": len(scored), "n_excluded": len(excluded)}
    if len(scored) >= 2:
        sd = net.std(ddof=1)
        summary.update(mean_net_bp=net.mean() * 1e4, t=net.mean() / sd * len(net) ** .5 if sd else None,
                       sharpe_ann=net.mean() / sd * 251 ** .5 if sd else None,
                       stress_mean_bp=float(np.mean([r["stress_net"] for r in scored])) * 1e4,
                       cum_pnl_usd=float(net.sum() * NOTIONAL), win=float((net > 0).mean()))
        summary["kill"] = summary["cum_pnl_usd"] <= -15_000
        summary["gate"] = ("pending (<104 sessions)" if sessions < 104 else
                           "PASS" if summary["t"] >= 1.65 and summary["stress_mean_bp"] > 0 and summary["sharpe_ann"] >= 0.5
                           else "FAIL")
    res = {"strategy": STRATEGY, "summary": summary, "trades": rows,
           "excluded": [{"key": d["decision_key"], "reasons": classify(d)} for d in excluded]}
    if out:
        out.write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))
    return res


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["register", "decide", "close", "evaluate"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--day", help="decide: override the date (dry runs only)")
    ap.add_argument("--out", type=Path, default=Path(__file__).parents[3] / "reports" / "forward" / "mstr_btc_offth_eval.json")
    a = ap.parse_args(argv)
    if a.day and not a.dry_run:
        raise SystemExit("--day is for dry runs only")
    if a.cmd == "register":
        rec = registry.append(registry.DEFAULT_REGISTRY, "spec_registration", strategy_id=STRATEGY,
                              spec_hash=registry.spec_hash(frozen_spec()), payload=frozen_spec())
        print("registered seq", rec["seq"], "spec_hash", rec["spec_hash"])
    elif a.cmd == "decide":
        decide(a.dry_run, nyse.to_date(a.day) if a.day else None)
    elif a.cmd == "close":
        close(a.dry_run)
    else:
        evaluate(a.out)


if __name__ == "__main__":
    main()
