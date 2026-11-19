"""Interactive Brokers adapter (ib_async) with the same interface the trader uses for Alpaca.

Needs IB Gateway or TWS running and logged in, with the API enabled:
    paper: port 4002 (Gateway) / 7497 (TWS);  live: 4001 / 7496
Settings come from quant_v7/.env.alpaca-style file .env.ibkr (no secrets needed; login happens in Gateway):
    IBKR_MODE=paper           # or live (live also needs LIVE_CONFIRM=I-UNDERSTAND-REAL-MONEY)
    IBKR_HOST=127.0.0.1
    IBKR_PORT=4002
    IBKR_CLIENT_ID=17
Orders carry orderRef = our client order id, so duplicates and lookups work like Alpaca's client_order_id."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from live.zb_itb.broker import BrokerError, LIVE_PHRASE, load_env

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env.ibkr"
STATUS_MAP = {"Filled": "filled", "Cancelled": "canceled", "ApiCancelled": "canceled", "Inactive": "rejected",
              "Submitted": "accepted", "PreSubmitted": "accepted", "PendingSubmit": "pending_new", "ApiPending": "pending_new"}


class IBKR:
    def __init__(self, env: dict | None = None):
        from ib_async import IB
        env = env if env is not None else load_env(ENV_FILE)
        self.mode = env.get("IBKR_MODE", "paper").lower()
        if self.mode == "live" and env.get("LIVE_CONFIRM") != LIVE_PHRASE:
            raise BrokerError(f"live mode needs LIVE_CONFIRM={LIVE_PHRASE} in .env.ibkr")
        port = int(env.get("IBKR_PORT", 4002 if self.mode == "paper" else 4001))
        self.ib = IB()
        try:
            self.ib.connect(env.get("IBKR_HOST", "127.0.0.1"), port, clientId=int(env.get("IBKR_CLIENT_ID", 17)), timeout=15)
        except Exception as e:  # noqa: BLE001
            raise BrokerError(f"cannot reach IB Gateway/TWS on port {port}: {e!r}. Is it running, logged in, API enabled?")
        accts = self.ib.managedAccounts()
        if self.mode == "paper" and accts and not accts[0].startswith("D"):
            raise BrokerError(f"IBKR_MODE=paper but connected account {accts[0]} is not a paper (DU...) account")
        self.acct = accts[0] if accts else ""

    # --- helpers -------------------------------------------------------------------------------------------
    def _contract(self, sym):
        from ib_async import Stock
        c = Stock(sym, "SMART", "USD"); self.ib.qualifyContracts(c); return c

    def _val(self, tag, default=None):
        for v in self.ib.accountValues(self.acct):
            if v.tag == tag and v.currency in ("USD", "BASE", ""):
                return v.value
        return default

    def _as_order(self, t):
        o, s = t.order, t.orderStatus
        return {"id": str(o.orderId), "client_order_id": o.orderRef, "symbol": t.contract.symbol, "side": o.action.lower(),
                "type": {"MKT": "market", "STP": "stop", "LMT": "limit"}.get(o.orderType, o.orderType.lower()),
                "status": STATUS_MAP.get(s.status, s.status.lower()), "filled_qty": str(s.filled),
                "filled_avg_price": str(s.avgFillPrice) if s.avgFillPrice else None, "_trade": t}

    # --- interface used by trader.py ----------------------------------------------------------------------
    def account(self):
        self.ib.reqAccountUpdates(True, self.acct); self.ib.sleep(1)
        eq = float(self._val("NetLiquidation", 0) or 0)
        dtr = self._val("DayTradesRemaining", "-1")
        return {"equity": str(eq), "last_equity": str(eq), "buying_power": self._val("BuyingPower", "0"), "status": "ACTIVE",
                "trading_blocked": False, "pattern_day_trader": False,
                "daytrade_count": (3 - int(dtr)) if dtr not in (None, "-1") else 0, "shorting_enabled": True}

    def clock(self): return {"is_open": None}

    def calendar(self, day):
        from research.forward import nyse
        return [{"date": day}] if nyse.is_session(dt.date.fromisoformat(day)) else []

    def asset(self, sym):
        c = self._contract(sym)
        t = self.ib.reqMktData(c, genericTickList="236", snapshot=False); self.ib.sleep(2)
        shortable = getattr(t, "shortableShares", None) or 0; self.ib.cancelMktData(c)
        return {"symbol": sym, "tradable": True, "shortable": shortable > 0, "easy_to_borrow": shortable > 1000, "fractionable": False}

    def positions(self):
        return [{"symbol": p.contract.symbol, "qty": str(p.position), "avg_entry_price": str(p.avgCost)} for p in self.ib.positions(self.acct) if p.position]

    def position(self, sym): return next((p for p in self.positions() if p["symbol"] == sym), None)

    def orders(self, status="open", symbols=None):
        return [self._as_order(t) for t in self.ib.openTrades() if not symbols or t.contract.symbol == symbols]

    def order_by_client_id(self, cid):
        self.ib.reqAllOpenOrders(); self.ib.sleep(0.5)
        for t in list(self.ib.trades()):
            if t.order.orderRef == cid:
                return self._as_order(t)
        return None

    def submit(self, symbol, qty, side, type, time_in_force, client_order_id, stop_price=None, **_):
        from ib_async import MarketOrder, StopOrder
        tif = {"opg": "OPG", "day": "DAY"}[time_in_force]
        o = MarketOrder(side.upper(), float(qty), tif=tif) if type == "market" else StopOrder(side.upper(), float(qty), float(stop_price), tif=tif)
        o.orderRef = client_order_id; o.account = self.acct; o.outsideRth = False
        t = self.ib.placeOrder(self._contract(symbol), o); self.ib.sleep(1)
        return self._as_order(t)

    def cancel(self, order_id):
        for t in self.ib.openTrades():
            if str(t.order.orderId) == str(order_id):
                self.ib.cancelOrder(t.order); self.ib.sleep(0.5)

    def close_position(self, sym):
        p = self.position(sym)
        if not p: return None
        q = float(p["qty"]); from ib_async import MarketOrder
        o = MarketOrder("SELL" if q > 0 else "BUY", abs(q), tif="DAY"); o.orderRef = f"close-{dt.date.today()}"; o.account = self.acct
        t = self.ib.placeOrder(self._contract(sym), o); self.ib.sleep(1); return self._as_order(t)

    def latest_trade(self, sym):
        c = self._contract(sym); self.ib.reqMarketDataType(3)   # delayed is fine for sizing
        t = self.ib.reqMktData(c, snapshot=True); self.ib.sleep(2)
        px = t.last if t.last == t.last and t.last else t.close
        if not px or px != px: raise BrokerError(f"no price for {sym}")
        return float(px)
