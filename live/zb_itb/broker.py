"""Minimal Alpaca REST client (trading v2 + IEX latest trade) and a fake broker for dry runs.

Keys come from quant_v7/.env.alpaca (gitignored, chmod 600), never from code or logs:
    ALPACA_KEY_ID=...
    ALPACA_SECRET_KEY=...
    ALPACA_MODE=paper            # or live
    LIVE_CONFIRM=                # must be I-UNDERSTAND-REAL-MONEY when ALPACA_MODE=live
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env.alpaca"
URLS = {"paper": "https://paper-api.alpaca.markets", "live": "https://api.alpaca.markets"}
DATA_URL = "https://data.alpaca.markets"
LIVE_PHRASE = "I-UNDERSTAND-REAL-MONEY"


class BrokerError(RuntimeError):
    pass


def load_env(path: Path = ENV_FILE) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("ALPACA_KEY_ID", "ALPACA_SECRET_KEY", "ALPACA_MODE", "LIVE_CONFIRM"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


class Alpaca:
    def __init__(self, env: dict | None = None):
        env = env if env is not None else load_env()
        self.mode = env.get("ALPACA_MODE", "paper").lower()
        if self.mode not in URLS:
            raise BrokerError(f"ALPACA_MODE must be paper or live, got {self.mode!r}")
        if self.mode == "live" and env.get("LIVE_CONFIRM") != LIVE_PHRASE:
            raise BrokerError(f"live mode needs LIVE_CONFIRM={LIVE_PHRASE} in .env.alpaca")
        if not env.get("ALPACA_KEY_ID") or not env.get("ALPACA_SECRET_KEY"):
            raise BrokerError(f"missing ALPACA_KEY_ID / ALPACA_SECRET_KEY in {ENV_FILE}")
        self.base = URLS[self.mode]
        self.s = requests.Session()
        self.s.headers.update({"APCA-API-KEY-ID": env["ALPACA_KEY_ID"], "APCA-API-SECRET-KEY": env["ALPACA_SECRET_KEY"],
                               "User-Agent": "quant_v7-zb_itb/1.0"})

    def _req(self, method: str, url: str, **kw):
        for attempt in range(4):
            try:
                r = self.s.request(method, url, timeout=15, **kw)
            except requests.RequestException as e:
                err = e; time.sleep(2 * (attempt + 1)); continue
            if r.status_code in (429, 500, 502, 503, 504):
                err = BrokerError(f"{r.status_code} {r.text[:200]}"); time.sleep(2 * (attempt + 1)); continue
            if r.status_code == 404 and method == "DELETE":
                return None
            if r.status_code >= 400:
                raise BrokerError(f"{method} {url.split('.markets')[-1]} -> {r.status_code}: {r.text[:300]}")
            return r.json() if r.content else None
        raise BrokerError(f"{method} {url} failed after retries: {err!r}")

    def get(self, path, **params): return self._req("GET", self.base + path, params=params)
    def post(self, path, body): return self._req("POST", self.base + path, json=body)
    def delete(self, path, **params): return self._req("DELETE", self.base + path, params=params)

    def account(self): return self.get("/v2/account")
    def clock(self): return self.get("/v2/clock")
    def calendar(self, day: str): return self.get("/v2/calendar", start=day, end=day)
    def asset(self, sym): return self.get(f"/v2/assets/{sym}")
    def positions(self): return self.get("/v2/positions") or []
    def position(self, sym):
        try:
            return self.get(f"/v2/positions/{sym}")
        except BrokerError as e:
            if "404" in str(e) or "position does not exist" in str(e):
                return None
            raise
    def orders(self, status="open", symbols=None):
        p = {"status": status, "limit": 100, "nested": "false"}
        if symbols: p["symbols"] = symbols
        return self.get("/v2/orders", **p) or []
    def order_by_client_id(self, cid):
        try:
            return self.get("/v2/orders:by_client_order_id", client_order_id=cid)
        except BrokerError as e:
            if "404" in str(e): return None
            raise
    def submit(self, **body):
        try:
            return self.post("/v2/orders", body)
        except BrokerError as e:
            # a POST whose response timed out is retried by _req; Alpaca already has it (2026-10-23 ITB stop)
            if "client_order_id must be unique" in str(e) and body.get("client_order_id"):
                o = self.order_by_client_id(body["client_order_id"])
                if o:
                    return o
            raise
    def cancel(self, order_id): return self.delete(f"/v2/orders/{order_id}")
    def close_position(self, sym): return self.delete(f"/v2/positions/{sym}")
    def latest_trade(self, sym):
        return self._req("GET", f"{DATA_URL}/v2/stocks/{sym}/trades/latest", params={"feed": "iex"})["trade"]["p"]


class FakeBroker:
    """In-memory stand-in for dry runs and tests: fills opg/market orders at a given price."""
    mode = "dry-run"

    def __init__(self, equity=25_000.0, px=95.0, shortable=True, daytrades=0):
        self.eq, self.px, self.shortable, self.dt = equity, px, shortable, daytrades
        self._orders, self._pos, self.log = {}, None, []

    def account(self):
        return {"equity": str(self.eq), "last_equity": str(self.eq), "buying_power": str(self.eq * 4), "cash": str(self.eq),
                "status": "ACTIVE", "trading_blocked": False, "pattern_day_trader": False, "daytrade_count": self.dt,
                "shorting_enabled": True, "multiplier": "4"}
    def clock(self): return {"is_open": False}
    def calendar(self, day): return [{"date": day, "open": "09:30", "close": "16:00"}]
    def asset(self, sym): return {"symbol": sym, "tradable": True, "shortable": self.shortable, "easy_to_borrow": self.shortable}
    def positions(self): return [self._pos] if self._pos else []
    def position(self, sym): return self._pos if self._pos and self._pos["symbol"] == sym else None
    def orders(self, status="open", symbols=None):
        live = ("new", "accepted")
        return [o for o in self._orders.values() if (o["status"] in live) == (status == "open")]
    def order_by_client_id(self, cid): return next((o for o in self._orders.values() if o["client_order_id"] == cid), None)
    def submit(self, **b):
        o = {"id": f"fake{len(self._orders)}", "status": "accepted", "filled_avg_price": None, "filled_qty": "0", **b}
        if b.get("type") in ("market",):
            o.update(status="filled", filled_avg_price=str(self.px), filled_qty=str(b["qty"]),
                     filled_at=datetime.now(timezone.utc).isoformat())
            q = float(b["qty"]) * (1 if b["side"] == "buy" else -1)
            if self._pos and self._pos["symbol"] == b["symbol"]:
                q += float(self._pos["qty"])
            self._pos = {"symbol": b["symbol"], "qty": str(q), "avg_entry_price": str(self.px)} if q else None
        self._orders[o["id"]] = o; self.log.append(("submit", b)); return o
    def cancel(self, oid): self._orders[oid]["status"] = "canceled"; self.log.append(("cancel", oid))
    def close_position(self, sym): self.log.append(("close", sym)); self._pos = None; return {"status": "accepted"}
    def latest_trade(self, sym): return self.px
