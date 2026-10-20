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
    return {
        "checks": checks,
        "ready": all(c["ok"] for c in checks if not c["optional"]),
        "mode": mode,
        "root": root.name,
        "platform": platform.system(),
        "port": int(__import__("os").getenv("MERIDIAN_PORT", "8420")),
    }
