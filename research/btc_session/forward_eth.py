"""Forward paper test eth_cme_break_v1 (ETH twin of btc_cme_break_v1; see ETH_FORWARD_PLAN.md).

    PYTHONPATH=. .venv/bin/python -m research.btc_session.forward_eth register   # once
    PYTHONPATH=. .venv/bin/python -m research.btc_session.forward_eth run        # weekdays, launch before 16:59 ET
    PYTHONPATH=. .venv/bin/python -m research.btc_session.forward_eth evaluate

`run` records the decision before 17:00 ET, buys $10k ETH/USD on LSE sim account 1717158 at 17:00:05 ET and
sells it at 18:00:05 ET. Scoring uses Coinbase ETH-USD 1-minute closes, not sim fills. --dry-run writes nothing."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import subprocess
import time
from pathlib import Path

from research.forward import nyse, registry
from research.mstr_btc_0dte.forward import ET, _sim, _sleep_until, _get

H = Path(__file__).parent
ROOT = registry.ROOT
REG = registry.DEFAULT_REGISTRY
STRATEGY = "eth_cme_break_v1"
SIM_ACCOUNT, NOTIONAL, SYMBOL = 1717158, 10_000, "ETH/USD"
T_IN, T_OUT, DECIDE_BY = dt.time(17, 0), dt.time(18, 0), dt.time(16, 59, 30)
SIM_LOG = ROOT / "reports" / "forward" / "eth_cme_break_sim.jsonl"
COSTS_BP = (2, 5, 10)


def frozen_spec() -> dict:
    return {"strategy_id": STRATEGY, "plan_sha256": registry.sha256_file(H / "ETH_FORWARD_PLAN.md"),
            "code_sha256": {"research/btc_session/forward_eth.py": registry.sha256_file(H / "forward_eth.py")},
            "rule": "NYSE weekday sessions: long $10k ETH 17:00->18:00 ET; score ln(P18/P17) on Coinbase ETH-USD 1m closes",
            "gate": {"final_n": 250, "pass": "gross t>=1.65 AND net@5bp mean>0", "kill": "cum net@5bp <= -8%"}}


def eth_close_at(t: dt.datetime) -> float:
    """Coinbase ETH-USD close of the 1-minute candle that ENDS at t."""
    import urllib.parse
    start = (t - dt.timedelta(minutes=1)).astimezone(dt.timezone.utc)
    q = urllib.parse.urlencode({"granularity": 60, "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "end": t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    for attempt in range(5):
        rows = _get(f"https://api.exchange.coinbase.com/products/ETH-USD/candles?{q}")
        hit = [r for r in rows if int(r[0]) == int(start.timestamp())]
        if hit:
            return float(hit[0][4])
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"no Coinbase ETH candle starting {start.isoformat()}")


def _ensure_engine() -> bool:
    """LSE Terminal must be running for sim orders; launch it if it is not (up to 120 s)."""
    from research.mstr_btc_0dte.forward import _engine
    try:
        _engine(); return True
    except Exception:
        subprocess.run(["open", "-a", "LSE Terminal"], check=False)
        for _ in range(24):
            time.sleep(5)
            try:
                _engine(); return True
            except Exception:
                continue
    return False


def _coinbase_px() -> float:
    from research.mstr_btc_0dte.forward import _get
    return float(_get("https://api.exchange.coinbase.com/products/ETH-USD/ticker")["price"])


def _log(ev: dict) -> None:
    SIM_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(SIM_LOG, "a") as f:
        f.write(json.dumps({"logged_at_utc": registry.iso_utc(registry.utc_now()), **ev}) + "\n")


def register(dry: bool) -> None:
    spec = frozen_spec(); h = registry.spec_hash(spec)
    payload = {"evaluation": {"type": "btc_window", "instruments": ["ETH-USD"], "capital_usd": NOTIONAL,
                              "decision_rule": "nyse_weekdays", "execution": "17:00-18:00 ET"}, "spec": spec}
    if dry:
        print(json.dumps(payload, indent=2), "\nspec_hash", h); return
    rec = registry.append(REG, "spec_registration", strategy_id=STRATEGY, spec_hash=h, payload=payload)
    print("registered seq", rec["seq"], h)


def run(dry: bool) -> None:
    day = dt.datetime.now(ET).date()
    if day.weekday() > 4 or not nyse.is_session(day):
        print(f"{day}: not an NYSE weekday session"); return
    t_in = dt.datetime.combine(day, T_IN, ET); t_out = dt.datetime.combine(day, T_OUT, ET)
    if dt.datetime.now(ET).time() > DECIDE_BY and not dry:
        print("past the decision deadline; missed"); return
    payload = {"targets": {"ETH-USD": 1.0}, "notional_usd": NOTIONAL, "entry_et": t_in.isoformat(), "exit_et": t_out.isoformat()}
    if dry:
        print("would record", payload); return
    rec = registry.append(REG, "decision", strategy_id=STRATEGY, spec_hash=registry.spec_hash(frozen_spec()),
                          market_asof=day.isoformat(), intended_execution_utc=registry.iso_utc(t_in.astimezone(dt.timezone.utc)),
                          decision_key=day.isoformat(), payload=payload)
    print("recorded seq", rec["seq"])
    engine_ok = _ensure_engine()
    _sleep_until(t_in.astimezone(dt.timezone.utc) + dt.timedelta(seconds=5))
    try:
        if not engine_ok:
            raise RuntimeError("LSE Terminal engine unavailable")
        try:
            q = _sim("GET", "/api/prices", {"provider": "lse", "symbols": SYMBOL}); px = float(q[0]["ask"])
        except Exception:
            px = _coinbase_px()
        qty = round(NOTIONAL / px, 6)
        _log({"day": day.isoformat(), "event": "open", "qty": qty, "quote": px,
              "result": _sim("POST", "/api/sim/orders", body={"account_id": SIM_ACCOUNT, "symbol": SYMBOL, "side": "buy", "otype": "market", "qty": qty})})
    except Exception as e:
        _log({"day": day.isoformat(), "event": "open_failed", "error": repr(e)})
    _sleep_until(t_out.astimezone(dt.timezone.utc) + dt.timedelta(seconds=5))
    for attempt in range(4):
        try:
            if not any(p.get("symbol") == SYMBOL for p in (_sim("GET", "/api/sim/positions", {"account_id": SIM_ACCOUNT}) or [])):
                _log({"day": day.isoformat(), "event": "close_skipped_no_position"}); break
            _log({"day": day.isoformat(), "event": "close", "result": _sim("POST", "/api/sim/close", {"account_id": SIM_ACCOUNT, "symbol": SYMBOL})})
            break
        except Exception as e:
            _log({"day": day.isoformat(), "event": "close_failed", "attempt": attempt + 1, "error": repr(e)})
            time.sleep(15)


def evaluate(out: Path) -> dict:
    from research.forward.evaluate import classify
    recs = registry.load_records(REG)
    live, _ = registry.live_decisions(recs)
    rows = []
    for d in [d for d in live if d["strategy_id"] == STRATEGY]:
        if classify(d):
            rows.append({"day": d["decision_key"], "excluded": classify(d)}); continue
        day = nyse.to_date(d["decision_key"])
        t_in = dt.datetime.combine(day, T_IN, ET); t_out = dt.datetime.combine(day, T_OUT, ET)
        if dt.datetime.now(dt.timezone.utc) < t_out.astimezone(dt.timezone.utc) + dt.timedelta(minutes=5):
            continue
        try:
            g = math.log(eth_close_at(t_out) / eth_close_at(t_in))
        except Exception as e:
            rows.append({"day": d["decision_key"], "error": repr(e)}); continue
        rows.append({"day": d["decision_key"], "gross": g, **{f"net_{c}bp": g - c / 1e4 for c in COSTS_BP}})
    sc = [r for r in rows if "gross" in r]
    s = {"n": len(sc)}
    if len(sc) >= 2:
        import statistics as st
        g = [r["gross"] for r in sc]; sd = st.stdev(g)
        s.update(gross_mean_bp=st.mean(g) * 1e4, t=st.mean(g) / sd * len(g) ** .5 if sd else None,
                 hit=sum(x > 0 for x in g) / len(g), **{f"cum_net_{c}bp_pct": sum(r[f"net_{c}bp"] for r in sc) * 100 for c in COSTS_BP})
        s["kill"] = s["cum_net_5bp_pct"] <= -8
        s["gate"] = "pending" if len(sc) < 250 else ("PASS" if s["t"] >= 1.65 and s["cum_net_5bp_pct"] > 0 else "FAIL")
    res = {"strategy": STRATEGY, "summary": s, "trades": rows}
    out.write_text(json.dumps(res, indent=2, default=str)); print(json.dumps(s, indent=2, default=str))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["register", "run", "evaluate"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "forward" / "eth_cme_break_eval.json")
    a = ap.parse_args()
    {"register": lambda: register(a.dry_run), "run": lambda: run(a.dry_run), "evaluate": lambda: evaluate(a.out)}[a.cmd]()
