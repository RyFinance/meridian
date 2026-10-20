"""Which execution path a trading cycle uses, chosen per person in the desk.

  sim       built-in simulator: real prices, simulated fills (default)
  readonly  simulator trades; the linked broker account is shown alongside
  paper     orders go to the broker's paper / sandbox / demo account
  live      orders go to the real broker account

Live needs three separate things, all from the person running it:
  1. MERIDIAN_ALLOW_LIVE=yes in the environment (.env) -- off by default
  2. credentials for the broker's live environment
  3. the arm phrase typed in the desk ("LIVE ALPACA", ...) -- saved here and
     re-checked before every order, so disarming in the desk stops the next order
Live orders are also capped per order by MERIDIAN_LIVE_MAX_ORDER_USD (default
500). The risk gate, kill switch and circuit breaker apply in every mode.

Selections live in bot/state/broker.json; secrets in bot/state/brokers.local.json
(mode 600, git-ignored). Environment variables override stored secrets:
MERIDIAN_<BROKER>_<ENV>_<FIELD>, e.g. MERIDIAN_ALPACA_PAPER_KEY_ID.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from brokers import REGISTRY, Broker, BrokerError

STATE_DIR = Path(__file__).parent / "state"
SELECTION_PATH = STATE_DIR / "broker.json"
CREDENTIALS_PATH = STATE_DIR / "brokers.local.json"
SIM_LEDGER = STATE_DIR / "paper_ledger.jsonl"

MODES = ("sim", "readonly", "paper", "live")
DEFAULT_LIVE_MAX_ORDER_USD = 500.0


@dataclass
class Selection:
    mode: str = "sim"
    broker: Optional[str] = None
    env: str = "paper"  # which credentials readonly reads with; paper/live modes force their own
    capital_usd: float = 100_000.0  # starting capital of the broker ledger (sizes orders)
    armed_at: Optional[float] = None
    armed_phrase: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def arm_phrase(broker_id: str) -> str:
    return f"LIVE {broker_id.upper()}"


def live_allowed() -> tuple[bool, str]:
    if os.getenv("MERIDIAN_ALLOW_LIVE", "").strip().lower() != "yes":
        return False, "set MERIDIAN_ALLOW_LIVE=yes in .env to allow live trading"
    return True, ""


def live_max_order_usd() -> float:
    try:
        return float(os.getenv("MERIDIAN_LIVE_MAX_ORDER_USD", DEFAULT_LIVE_MAX_ORDER_USD))
    except ValueError:
        return DEFAULT_LIVE_MAX_ORDER_USD


# -- persistence ----------------------------------------------------------

def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def load_selection() -> Selection:
    try:
        raw = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Selection()
    sel = Selection(**{k: v for k, v in raw.items() if k in Selection.__dataclass_fields__})
    return sel if sel.mode in MODES else Selection()


def save_selection(sel: Selection) -> None:
    _write_private(SELECTION_PATH, json.dumps(sel.to_dict(), indent=2))


def _read_creds() -> Dict[str, Dict[str, Dict[str, str]]]:
    try:
        data = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def credentials(broker_id: str, env: str) -> Dict[str, str]:
    cls = REGISTRY[broker_id]
    stored = dict(_read_creds().get(broker_id, {}).get(env, {}))
    for f in cls.fields:
        value = os.getenv(f"MERIDIAN_{broker_id.upper()}_{env.upper()}_{f.name.upper()}")
        if value:
            stored[f.name] = value
    return stored


def has_credentials(broker_id: str, env: str) -> bool:
    cls = REGISTRY[broker_id]
    creds = credentials(broker_id, env)
    required = [f.name for f in cls.fields if not f.optional]
    return all(creds.get(name) for name in required) if required else env in _read_creds().get(broker_id, {})


def save_credentials(broker_id: str, env: str, values: Dict[str, str]) -> None:
    if broker_id not in REGISTRY:
        raise BrokerError(f"unknown broker {broker_id!r}")
    cls = REGISTRY[broker_id]
    if env not in cls.envs:
        raise BrokerError(f"{cls.name} has no {env} environment")
    clean = {f.name: str(values.get(f.name, "")).strip() for f in cls.fields if str(values.get(f.name, "")).strip()}
    missing = [f.label for f in cls.fields if not f.optional and not clean.get(f.name)]
    if missing:
        raise BrokerError(f"missing: {', '.join(missing)}")
    data = _read_creds()
    data.setdefault(broker_id, {})[env] = clean
    _write_private(CREDENTIALS_PATH, json.dumps(data, indent=2))


def delete_credentials(broker_id: str, env: str) -> None:
    data = _read_creds()
    data.get(broker_id, {}).pop(env, None)
    _write_private(CREDENTIALS_PATH, json.dumps(data, indent=2))
    sel = load_selection()
    if sel.broker == broker_id and (sel.mode in ("paper", "live") and sel.env == env or sel.mode == "readonly" and sel.env == env):
        save_selection(Selection())


def build_broker(broker_id: str, env: str) -> Broker:
    if broker_id not in REGISTRY:
        raise BrokerError(f"unknown broker {broker_id!r}")
    cls = REGISTRY[broker_id]
    broker = cls(credentials(broker_id, env), env)
    if broker_id == "questrade":
        # Questrade refresh tokens are single-use; keep the rotated one.
        def keep(token: str, _env=env) -> None:
            stored = credentials("questrade", _env)
            stored["refresh_token"] = token
            save_credentials("questrade", _env, stored)
        broker.on_refresh = keep
    return broker


# -- choosing a mode --------------------------------------------------------

def select(mode: str, broker_id: Optional[str] = None, env: str = "paper",
           capital_usd: Optional[float] = None, confirm: str = "") -> Selection:
    """Validate and save a new selection. Raises BrokerError with a message
    meant for the person (shown in the desk) when something is missing."""
    if mode not in MODES:
        raise BrokerError(f"mode must be one of {', '.join(MODES)}")
    current = load_selection()
    capital = float(capital_usd) if capital_usd else current.capital_usd
    if capital <= 0:
        raise BrokerError("capital must be positive")
    if mode == "sim":
        sel = Selection(mode="sim", capital_usd=capital)
        save_selection(sel)
        return sel
    if broker_id not in REGISTRY:
        raise BrokerError("pick a broker")
    cls = REGISTRY[broker_id]
    if mode in ("paper", "live"):
        env = mode
        if env not in cls.can_trade:
            raise BrokerError(f"{cls.name} does not accept API orders in {env} -- use read-only")
    if env not in cls.envs:
        raise BrokerError(f"{cls.name} has no {env} environment")
    if not has_credentials(broker_id, env):
        raise BrokerError(f"link {cls.name} ({env}) first")
    armed_at = armed_phrase = None
    if mode == "live":
        ok, why = live_allowed()
        if not ok:
            raise BrokerError(why)
        if confirm.strip().upper() != arm_phrase(broker_id):
            raise BrokerError(f'type "{arm_phrase(broker_id)}" to arm live trading')
        armed_at, armed_phrase = time.time(), arm_phrase(broker_id)
    sel = Selection(mode=mode, broker=broker_id, env=env, capital_usd=capital,
                    armed_at=armed_at, armed_phrase=armed_phrase)
    save_selection(sel)
    return sel


def live_is_armed(broker_id: str) -> tuple[bool, str]:
    """Re-read from disk on every live order: disarming in the desk wins."""
    ok, why = live_allowed()
    if not ok:
        return False, why
    sel = load_selection()
    if sel.mode != "live" or sel.broker != broker_id or sel.armed_phrase != arm_phrase(broker_id):
        return False, "live trading is not armed for this broker"
    return True, ""


def ledger_path(sel: Selection) -> Path:
    if sel.mode in ("paper", "live") and sel.broker:
        return STATE_DIR / f"ledger_{sel.broker}_{sel.mode}.jsonl"
    return SIM_LEDGER


def starting_capital(sel: Selection, default: float) -> float:
    return sel.capital_usd if sel.mode in ("paper", "live") else default


def build_execution_client(default_capital: float, ledger_override: Optional[Path] = None):
    """The client a trading cycle uses. An explicit ledger override (tests,
    replays) always gets the simulator."""
    from bot.execution import PaperExecutionClient

    sel = load_selection()
    if ledger_override is not None or sel.mode in ("sim", "readonly"):
        return PaperExecutionClient.from_ledger(starting_capital=default_capital,
                                                ledger_path=ledger_override or SIM_LEDGER)
    from bot.broker_execution import BrokerExecutionClient

    client = BrokerExecutionClient.from_ledger(starting_capital=sel.capital_usd, ledger_path=ledger_path(sel))
    client.attach(build_broker(sel.broker, sel.env), sel.mode)
    return client


def describe_mode() -> Dict[str, Any]:
    sel = load_selection()
    ok, why = live_allowed()
    return {
        **sel.to_dict(),
        "broker_name": REGISTRY[sel.broker].name if sel.broker in REGISTRY else None,
        "ledger": str(ledger_path(sel).name),
        "live_allowed": ok, "live_blocked_reason": why or None,
        "live_max_order_usd": live_max_order_usd(),
        "arm_phrase": arm_phrase(sel.broker) if sel.broker else None,
    }
