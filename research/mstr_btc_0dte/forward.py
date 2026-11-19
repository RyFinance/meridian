"""Forward paper test mstr_btc_monday_v1 (see FORWARD_PLAN.md). Commands:

    PYTHONPATH=. .venv/bin/python -m research.mstr_btc_0dte.forward register      # once
    PYTHONPATH=. .venv/bin/python -m research.mstr_btc_0dte.forward decide        # Monday, starts before 09:25 ET
    PYTHONPATH=. .venv/bin/python -m research.mstr_btc_0dte.forward close         # Monday, before 16:00 ET
    PYTHONPATH=. .venv/bin/python -m research.mstr_btc_0dte.forward evaluate

`decide` and `close` sleep until their ET target time, so they can be launched early from any local timezone.
Add --dry-run to print without writing to the registry or the sim."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

from research.forward import nyse, registry

ET = ZoneInfo("America/New_York")
H = Path(__file__).parent
ROOT = registry.ROOT
REG = registry.DEFAULT_REGISTRY
SPEC = H / "forward_spec.json"
SIM_LOG = ROOT / "reports" / "forward" / "mstr_btc_monday_sim.jsonl"
STRATEGY = "mstr_btc_monday_v1"
SYMBOL, NOTIONAL, SIM_ACCOUNT = "MSTR", 100_000, 1717158
DECIDE_AT, DECIDE_LATEST = dt.time(9, 25, 0), dt.time(9, 29, 30)
ORDER_AT, CLOSE_AT = dt.time(9, 30, 20), dt.time(15, 59, 0)
UA = {"User-Agent": "quant_v7-forward/1.0"}


# -- spec -----------------------------------------------------------------------------

def frozen_spec() -> dict:
    code = {f"research/mstr_btc_0dte/{n}": registry.sha256_file(H / n) for n in ("forward.py", "costs.py")}
    spec = json.loads(SPEC.read_text())
    spec["code_sha256"] = code
    spec["plan_sha256"] = registry.sha256_file(H / "FORWARD_PLAN.md")
    return spec


def current_spec_hash() -> str:
    return registry.spec_hash(frozen_spec())


# -- data -----------------------------------------------------------------------------

def _get(url: str, timeout: float = 15):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.loads(r.read())


def btc_close_at(t: dt.datetime) -> float:
    """Coinbase BTC-USD close of the 1-minute candle that ENDS at t (i.e. starts at t - 1 min)."""
    start = (t - dt.timedelta(minutes=1)).astimezone(dt.timezone.utc)
    q = urllib.parse.urlencode({"granularity": 60, "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "end": t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    for attempt in range(5):
        rows = _get(f"https://api.exchange.coinbase.com/products/BTC-USD/candles?{q}")
        hit = [r for r in rows if int(r[0]) == int(start.timestamp())]
        if hit:
            return float(hit[0][4])
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"no Coinbase candle starting {start.isoformat()}")


# -- LSE sim ------------------------------------------------------------------------------

def _engine() -> str:
    for port in range(7799, 7819):
        try:
            h = _get(f"http://127.0.0.1:{port}/api/health", timeout=2)
            if isinstance(h, dict) and "ui_version" in h:
                return f"http://127.0.0.1:{port}"
        except Exception:
            continue
    raise RuntimeError("LSE Terminal engine not running on 127.0.0.1:7799-7818")


def _sim(method: str, route: str, query: dict | None = None, body: dict | None = None):
    url = _engine() + route + ("?" + urllib.parse.urlencode(query) if query else "")
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json", **UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode()
    return json.loads(text) if text else None


def _log_sim(event: dict) -> None:
    SIM_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(SIM_LOG, "a") as f:
        f.write(json.dumps({"logged_at_utc": registry.iso_utc(registry.utc_now()), **event}) + "\n")


def _sleep_until(t: dt.datetime) -> None:
    while (left := (t - dt.datetime.now(dt.timezone.utc)).total_seconds()) > 0:
        time.sleep(min(left, 30))


# -- commands ---------------------------------------------------------------------------

def register(dry: bool) -> None:
    spec = frozen_spec()
    h = registry.spec_hash(spec)
    payload = {"evaluation": {"type": "mstr_open_close", "instruments": [SYMBOL], "capital_usd": NOTIONAL,
                              "decision_rule": "monday_sessions", "execution": "open_to_close"}, "spec": spec}
    if dry:
        print(json.dumps(payload, indent=2), "\nspec_hash", h)
        return
    rec = registry.append(REG, "spec_registration", strategy_id=STRATEGY, spec_hash=h, payload=payload)
    print("registered seq", rec["seq"], "spec_hash", h)


def decide(dry: bool, day: dt.date | None = None) -> None:
    day = day or dt.datetime.now(ET).date()
    if day.weekday() != 0 or not nyse.is_session(day):
        print(f"{day}: not a Monday NYSE session; no decision")
        return
    t_dec = dt.datetime.combine(day, DECIDE_AT, ET)
    _sleep_until(t_dec.astimezone(dt.timezone.utc) + dt.timedelta(seconds=3))
    now_et = dt.datetime.now(ET)
    if now_et.time() > DECIDE_LATEST and not dry:
        print(f"{now_et}: past {DECIDE_LATEST} ET; decision window missed, nothing recorded")
        return
    prev = nyse.previous_session(day)
    p0, p1 = btc_close_at(nyse.close_utc(prev)), btc_close_at(t_dec)
    r = math.log(p1 / p0)
    d = (r > 0) - (r < 0)
    payload = {"btc_source": "coinbase BTC-USD 1m close", "btc_prev_close_px": p0, "btc_0925_px": p1,
               "btc_log_ret": r, "direction": d, "targets": {SYMBOL: float(d)}, "notional_usd": NOTIONAL,
               "prev_session": prev.isoformat(), "exit_utc": registry.iso_utc(nyse.close_utc(day))}
    print(json.dumps(payload, indent=2))
    if dry:
        return
    rec = registry.append(REG, "decision", strategy_id=STRATEGY, spec_hash=current_spec_hash(),
                          market_asof=prev.isoformat(), intended_execution_utc=registry.iso_utc(nyse.open_utc(day)),
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
        _log_sim({"day": day.isoformat(), "event": "open", "qty": qty, "direction": d, "quote": px, "result": res})
    except Exception as e:
        _log_sim({"day": day.isoformat(), "event": "open_failed", "error": repr(e)})
        print("sim order failed:", e)


def mstr_fallback_px() -> float:
    """The LSE quote was unavailable: size from the yfinance last price instead."""
    import yfinance as yf
    return float(yf.Ticker(SYMBOL).fast_info["last_price"])


def close(dry: bool) -> None:
    day = dt.datetime.now(ET).date()
    if day.weekday() != 0 or not nyse.is_session(day):
        print(f"{day}: not a Monday NYSE session")
        return
    end = dt.datetime.combine(day, CLOSE_AT, ET) if nyse.session_close_time(day) == dt.time(16, 0) \
        else dt.datetime.combine(day, nyse.session_close_time(day), ET) - dt.timedelta(minutes=1)
    _sleep_until(end.astimezone(dt.timezone.utc))
    if dry:
        print("would close", SYMBOL, "on sim account", SIM_ACCOUNT)
        return
    try:
        res = _sim("POST", "/api/sim/close", {"account_id": SIM_ACCOUNT, "symbol": SYMBOL})
        _log_sim({"day": day.isoformat(), "event": "close", "result": res})
    except Exception as e:
        _log_sim({"day": day.isoformat(), "event": "close_failed", "error": repr(e)})
        print("sim close failed:", e)


def evaluate(out: Path | None) -> dict:
    import numpy as np
    from research.forward.evaluate import classify
    from research.forward.prices import default_pricebook
    from research.mstr_btc_0dte.costs import round_trip_return
    recs = registry.load_records(REG)
    live, _ = registry.live_decisions(recs)
    ds = [d for d in live if d["strategy_id"] == STRATEGY]
    counted, excluded, rows = [], [], []
    for d in ds:
        (excluded if classify(d) else counted).append(d)
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
    net = np.array([r["net"] for r in scored])
    summary = {"n_counted": len(scored), "n_excluded": len(excluded)}
    if len(scored) >= 2:
        sd = net.std(ddof=1)
        summary.update(mean_net_bp=net.mean() * 1e4, t=net.mean() / sd * len(net) ** .5 if sd else None,
                       sharpe_ann=net.mean() / sd * 52 ** .5 if sd else None,
                       stress_mean_bp=float(np.mean([r["stress_net"] for r in scored])) * 1e4,
                       cum_pnl_usd=float(net.sum() * NOTIONAL), win=float((net > 0).mean()))
        summary["kill"] = summary["cum_pnl_usd"] <= -15_000
        summary["gate"] = ("pending (<104 Mondays)" if len(scored) < 104 else
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
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "forward" / "mstr_btc_monday_eval.json")
    a = ap.parse_args(argv)
    if a.day and not a.dry_run:
        raise SystemExit("--day is for dry runs only")
    if a.cmd == "register":
        register(a.dry_run)
    elif a.cmd == "decide":
        decide(a.dry_run, nyse.to_date(a.day) if a.day else None)
    elif a.cmd == "close":
        close(a.dry_run)
    else:
        evaluate(a.out)


if __name__ == "__main__":
    main()
