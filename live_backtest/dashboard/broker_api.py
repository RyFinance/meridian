"""Desk routes for linking brokers and choosing the execution mode.

Reads (catalog, account snapshots) never send orders. The only writes are
saving / removing credentials and the mode selection -- orders are only ever
sent by a trading cycle (bot/run_cycle.py) through the risk gate.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException

from bot import broker_config
from brokers import NO_PUBLIC_API, REGIONS, REGISTRY, BrokerError

router = APIRouter(prefix="/api")

_ACCOUNT_CACHE: Dict[tuple, tuple[float, Dict[str, Any]]] = {}
ACCOUNT_TTL_S = 20.0


def _status(broker_id: str) -> Dict[str, Any]:
    cls = REGISTRY[broker_id]
    return {
        **cls.describe(),
        "linked": {env: broker_config.has_credentials(broker_id, env) for env in cls.envs},
        "arm_phrase": broker_config.arm_phrase(broker_id),
    }


@router.get("/brokers")
def brokers() -> Dict[str, Any]:
    return {
        "regions": [{"id": rid, "name": name, "brokers": ids, "no_public_api": NO_PUBLIC_API.get(rid, [])}
                    for rid, (name, ids) in REGIONS.items()],
        "brokers": {bid: _status(bid) for bid in REGISTRY},
        "mode": broker_config.describe_mode(),
    }


@router.post("/brokers/{broker_id}/link")
def link(broker_id: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    if broker_id not in REGISTRY:
        raise HTTPException(404, f"unknown broker {broker_id}")
    env = str(payload.get("env", "paper"))
    try:
        broker_config.save_credentials(broker_id, env, payload.get("fields") or {})
    except BrokerError as exc:
        raise HTTPException(400, str(exc)) from exc
    try:
        account = _fetch(broker_id, env, force=True)
    except Exception as exc:  # saved, but the first read failed: say why
        account = {"error": f"{type(exc).__name__}: {exc}"[:240]}
    return {"broker": _status(broker_id), "account": account}


@router.post("/brokers/{broker_id}/unlink")
def unlink(broker_id: str, payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    if broker_id not in REGISTRY:
        raise HTTPException(404, f"unknown broker {broker_id}")
    env = str(payload.get("env", "paper"))
    broker_config.delete_credentials(broker_id, env)
    _ACCOUNT_CACHE.pop((broker_id, env), None)
    return {"broker": _status(broker_id), "mode": broker_config.describe_mode()}


def _fetch(broker_id: str, env: str, force: bool = False) -> Dict[str, Any]:
    key = (broker_id, env)
    cached = _ACCOUNT_CACHE.get(key)
    if cached and not force and time.time() - cached[0] < ACCOUNT_TTL_S:
        return cached[1]
    started = time.perf_counter()
    broker = broker_config.build_broker(broker_id, env)
    try:
        account = broker.account().to_dict()
    finally:
        broker.close()
    account.update(broker=broker_id, env=env, latency_ms=int((time.perf_counter() - started) * 1000),
                   checked_at=time.time())
    _ACCOUNT_CACHE[key] = (time.time(), account)
    return account


@router.get("/brokers/{broker_id}/account")
def account(broker_id: str, env: str = "paper", refresh: bool = False) -> Dict[str, Any]:
    if broker_id not in REGISTRY:
        raise HTTPException(404, f"unknown broker {broker_id}")
    if not broker_config.has_credentials(broker_id, env):
        raise HTTPException(409, f"{REGISTRY[broker_id].name} ({env}) is not linked")
    try:
        return _fetch(broker_id, env, force=refresh)
    except Exception as exc:
        raise HTTPException(502, f"{type(exc).__name__}: {exc}"[:240]) from exc


@router.get("/mode")
def mode() -> Dict[str, Any]:
    return broker_config.describe_mode()


@router.post("/mode")
def set_mode(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    try:
        broker_config.select(
            mode=str(payload.get("mode", "sim")), broker_id=payload.get("broker"),
            env=str(payload.get("env", "paper")), capital_usd=payload.get("capital_usd"),
            confirm=str(payload.get("confirm", "")),
        )
    except BrokerError as exc:
        raise HTTPException(400, str(exc)) from exc
    return broker_config.describe_mode()


@router.get("/linked_account")
def linked_account() -> Dict[str, Any]:
    """The account behind the current mode (readonly / paper / live), if any."""
    sel = broker_config.load_selection()
    if sel.mode == "sim" or not sel.broker:
        return {"available": False, "mode": sel.mode}
    try:
        return {"available": True, "mode": sel.mode, **_fetch(sel.broker, sel.env)}
    except BrokerError as exc:
        return {"available": False, "mode": sel.mode, "error": str(exc)}
    except Exception as exc:  # network failures
        return {"available": False, "mode": sel.mode, "error": f"{type(exc).__name__}: {exc}"}


@router.get("/setup")
def setup_status() -> Dict[str, Any]:
    """Readiness checklist for the Setup page: each item says whether it is
    done and, if not, the one command or step that fixes it."""
    import platform
    import sys
    from pathlib import Path

    from bot.heartbeat import read_heartbeat_age_seconds
    from data.ingestion import RAW_DATA_DIR

    root = Path(__file__).resolve().parents[2]
    checks = []

    def check(key, label, ok, detail, fix=None, optional=False):
        checks.append({"id": key, "label": label, "ok": bool(ok), "detail": detail, "fix": None if ok else fix,
                       "optional": optional})

    py = sys.version_info
    check("python", "Python 3.11+", py >= (3, 11), f"{py.major}.{py.minor}.{py.micro}", "install Python 3.11 or newer")
    model = root / "models" / "pead_model_expanded.joblib"
    check("model", "Fitted model", model.exists(), "models/pead_model_expanded.joblib" if model.exists() else "missing",
          "git pull (the model ships with the repo)")
    env = root / ".env"
    check("env", "Settings file (.env)", env.exists(), ".env" if env.exists() else "not created", "scripts/setup.sh")
    bars = list(Path(RAW_DATA_DIR).glob("*.parquet"))
    newest = max((p.stat().st_mtime for p in bars), default=None)
    check("prices", "Price cache", len(bars) > 50,
          f"{len(bars)} tickers, refreshed {time.strftime('%Y-%m-%d', time.localtime(newest))}" if newest else "empty",
          "scripts/cycle.sh (first run downloads price history)")
    age = read_heartbeat_age_seconds()
    ran = age is not None and age != float("inf")
    check("cycle", "A cycle has run recently", ran and age < 4 * 86400,
          f"last heartbeat {age / 3600:.1f}h ago" if ran else "never", "scripts/cycle.sh")
    mac = platform.system() == "Darwin"
    if mac:
        from bot.launchd_control import get_operation_status
        try:
            sched = get_operation_status().get("operation_state", "UNKNOWN")
        except Exception as exc:  # launchctl unavailable
            sched = f"unavailable ({type(exc).__name__})"
        check("schedule", "Scheduled after each close", sched == "RUNNING", sched, "scripts/install_launchd.sh")
    else:
        check("schedule", "Scheduled after each close", False, platform.system(),
              "cron: 20 16 * * 1-5 cd <repo> && scripts/cycle.sh   (America/New_York)")
    linked = [f"{cls.name} ({env_})" for bid, cls in REGISTRY.items() for env_ in cls.envs
              if broker_config.has_credentials(bid, env_)]
    check("broker", "Broker linked", bool(linked), ", ".join(linked) or "none (simulator only)",
          "F2 Brokers → link a paper account", optional=True)
    mode = broker_config.describe_mode()
    ok_live, why = broker_config.live_allowed()
    check("live", "Live trading allowed", ok_live, "MERIDIAN_ALLOW_LIVE=yes" if ok_live else "off",
          "only if you want real orders: MERIDIAN_ALLOW_LIVE=yes in .env, then arm in F2", optional=True)
    env_now = lambda name, default: __import__("os").getenv(name) or None  # noqa: E731
    settings = [
        ("MERIDIAN_PORT", "8420", "Desk port (always 127.0.0.1)."),
        ("MERIDIAN_ALLOW_LIVE", "no", "yes allows arming live trading at all."),
        ("MERIDIAN_LIVE_MAX_ORDER_USD", "500", "Largest single live order; bigger approved sizes are clipped."),
        ("MERIDIAN_LAUNCHD_PREFIX", "com.meridian", "Names of the macOS scheduler jobs."),
        ("RESEARCH_USER_AGENT", "", "Contact string sent to SEC EDGAR by research scripts."),
    ]
    settings_rows = [{"name": n, "now": env_now(n, d) or (f"{d} (default)" if d else "not set"), "default": d or "—",
                      "what": w} for n, d, w in settings]
    for bid, cls in REGISTRY.items():
        for env_ in cls.envs:
            settings_rows.append({"name": f"MERIDIAN_{bid.upper()}_{env_.upper()}_*", "default": "—",
                                  "now": "linked" if broker_config.has_credentials(bid, env_) else "not set",
                                  "what": f"{cls.name} {env_} keys ({', '.join(f.name for f in cls.fields)}); or link in F2."})
    live_steps = []
    for bid, cls in REGISTRY.items():
        if "live" not in cls.can_trade:
            continue
        steps = [
            {"text": f"Link {cls.name} live keys", "how": f"F2 Brokers → {cls.name} → LIVE → {', '.join(f.label for f in cls.fields)}",
             "done": broker_config.has_credentials(bid, "live")},
            {"text": "Opt in: MERIDIAN_ALLOW_LIVE=yes", "how": ".env → MERIDIAN_ALLOW_LIVE=yes, then restart the desk",
             "done": ok_live},
            {"text": "Arm LIVE", "how": f'F2 → Execution mode → LIVE → pick {cls.name} → type "{broker_config.arm_phrase(bid)}"',
             "done": mode.get("mode") == "live" and mode.get("broker") == bid},
        ]
        if "paper" in cls.can_trade:
            steps.insert(0, {"text": "Practise on paper first", "how": f"F2 → link {cls.name} PAPER keys → mode BROKER PAPER",
                             "done": broker_config.has_credentials(bid, "paper")})
        live_steps.append({"id": bid, "name": cls.name, "regions": list(cls.regions), "note": cls.note, "steps": steps})
    return {
        "checks": checks,
        "settings": settings_rows,
        "live_setup": live_steps,
        "limits": {"max_position_pct": 0.05, "max_total_exposure_pct": 1.0, "max_drawdown_pct": 0.20,
                   "holding_days": 20, "live_max_order_usd": broker_config.live_max_order_usd()},
        "ready": all(c["ok"] for c in checks if not c["optional"]),
        "mode": mode,
        "root": root.name,
        "platform": platform.system(),
        "port": int(__import__("os").getenv("MERIDIAN_PORT", "8420")),
    }


@router.get("/linked_accounts")
def linked_accounts() -> Dict[str, Any]:
    """Every linked broker environment (paper and live), read-only."""
    rows = []
    for broker_id, cls in REGISTRY.items():
        for env in cls.envs:
            if not broker_config.has_credentials(broker_id, env):
                continue
            try:
                rows.append({"available": True, "name": cls.name, **_fetch(broker_id, env)})
            except Exception as exc:  # one bad link must not hide the others
                rows.append({"available": False, "name": cls.name, "broker": broker_id, "env": env,
                             "error": f"{type(exc).__name__}: {exc}"[:200]})
    return {"accounts": rows}


@router.get("/fills")
def fills(limit: int = 50) -> Dict[str, Any]:
    """Fills of the active ledger, newest first: where each one executed
    (simulator, broker paper or broker live), the broker order id and size."""
    import json

    sel = broker_config.load_selection()
    path = broker_config.ledger_path(sel)
    rows = []
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                opening = r.get("event") == "open"
                mode = r.get("mode") or "sim"
                rows.append({
                    "ts": r.get("ts"), "ticker": r.get("ticker"),
                    "side": ("BUY" if r.get("direction") == "long" else "SHORT") if opening
                    else ("SELL" if r.get("direction") == "long" else "COVER"),
                    "price": r.get("fill_price") if opening else r.get("exit_price"),
                    "qty": r.get("qty"), "notional": r.get("notional"),
                    "pnl": None if opening else r.get("realized_pnl"),
                    "venue": "sim" if mode in ("sim", "paper") and not r.get("broker") else f"{r.get('broker')} {mode}",
                    "live": mode == "live", "order_id": r.get("order_id"), "backfill": bool(r.get("backfill")),
                })
    except OSError:
        pass
    rows.sort(key=lambda r: r["ts"] or 0, reverse=True)
    return {"ledger": path.name, "mode": sel.mode, "fills": rows[: max(1, min(limit, 500))]}


@router.post("/kill/engage")
def kill_engage(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """Stop all new entries now (scheduled exits still run)."""
    from bot.kill_switch import engage_kill_switch, read_kill_switch_status

    engage_kill_switch(str(payload.get("reason") or "engaged from the desk")[:200])
    return {"engaged": read_kill_switch_status().engaged}


@router.post("/kill/clear")
def kill_clear(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """Resume new entries. Needs the typed word, like arming live."""
    from bot.kill_switch import disengage_kill_switch, read_kill_switch_status

    if str(payload.get("confirm", "")).strip().upper() != "RESUME":
        raise HTTPException(400, 'type "RESUME" to clear the kill switch')
    disengage_kill_switch()
    return {"engaged": read_kill_switch_status().engaged}
