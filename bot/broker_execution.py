"""Broker-backed execution: the simulator's ledger and accounting, with fills
from a real broker account (its paper/sandbox environment, or live).

Order of checks for every entry, after the risk gate approved it:
  1. the approval token is consumed (one decision funds one order)
  2. live only: MERIDIAN_ALLOW_LIVE=yes and the desk arm are re-read from disk
  3. live only: notional is clipped to MERIDIAN_LIVE_MAX_ORDER_USD
  4. whole shares: qty = floor(notional / price); under one share is refused
  5. market order, then wait up to 30 s for the fill
Exits always go through (a scheduled exit is risk-reducing), with the same
live re-check so a disarmed desk never sends an order.

Accounting is identical to PaperExecutionClient: the fill price and the
filled quantity define the position, and the same modeled round-trip cost is
charged on the close, so sim, paper and live numbers stay comparable.
"""
from __future__ import annotations

import math

from bot.execution import Direction, PaperExecutionClient, PaperFill, get_current_price
from bot.risk_gate import RiskGateDecision, consume_approval
from brokers import Broker, BrokerError

from bot import broker_config

FILL_TIMEOUT_S = 30.0


class BrokerExecutionClient(PaperExecutionClient):
    broker: Broker | None = None
    mode: str = "paper"

    def attach(self, broker: Broker, mode: str) -> "BrokerExecutionClient":
        if mode not in ("paper", "live"):
            raise ValueError("broker execution is only for paper or live mode")
        self.broker, self.mode = broker, mode
        return self

    def _guard_live(self) -> None:
        if self.mode == "live":
            ok, why = broker_config.live_is_armed(self.broker.id)
            if not ok:
                raise PermissionError(f"live order blocked: {why}")

    def _price(self, ticker: str) -> float:
        quote = None
        try:
            quote = self.broker.quote(ticker)
        except Exception:
            quote = None
        return float(quote) if quote and quote > 0 else get_current_price(ticker)

    def _fill(self, ticker: str, side: str, qty: int):
        result = self.broker.submit_market(ticker, side, qty)
        if not result.filled:
            result = self.broker.wait_for_fill(result.order_id, timeout_s=FILL_TIMEOUT_S)
        if not result.filled:
            raise BrokerError(f"{self.broker.name} order {result.order_id} for {ticker} not filled "
                              f"within {FILL_TIMEOUT_S:.0f}s (status {result.status}); reconcile at the broker")
        return result

    def place_order(self, ticker: str, direction: Direction, decision: RiskGateDecision, entry_date: str) -> PaperFill:
        if self.broker is None:
            raise RuntimeError("no broker attached")
        if not decision.allowed or not consume_approval(decision.approval_token):
            raise PermissionError(f"place_order for {ticker} rejected: no valid risk-gate approval "
                                  f"(reason={decision.reason}, detail={decision.detail!r})")
        if ticker in self.positions and self.positions[ticker].open:
            raise ValueError(f"{ticker} already has an open position")
        self._guard_live()

        notional = decision.size_fraction * self.nav()
        capped = None
        if self.mode == "live":
            cap = broker_config.live_max_order_usd()
            if notional > cap:
                capped, notional = notional, cap
        price = self._price(ticker)
        qty = math.floor(notional / price)
        if qty < 1:
            raise BrokerError(f"{ticker}: ${notional:,.2f} buys less than one share at ${price:,.2f}")

        side = "buy" if direction == "long" else "sell_short"
        result = self._fill(ticker, side, qty)
        filled_qty = int(result.filled_qty)
        fill_price = float(result.avg_fill_price)
        extra = {"broker": self.broker.id, "env": self.broker.env, "order_id": result.order_id, "qty": filled_qty}
        if capped is not None:
            extra["notional_before_live_cap"] = round(capped, 2)
        return self._record_open(ticker, direction, fill_price, filled_qty * fill_price,
                                 decision.size_fraction, entry_date, mode=self.mode, **extra)

    def close_position(self, ticker: str, exit_date: str, reason: str = "holding_period_exit") -> float:
        if self.broker is None:
            raise RuntimeError("no broker attached")
        position = self.positions.get(ticker)
        if position is None or not position.open:
            raise ValueError(f"no open position for {ticker}")
        self._guard_live()
        qty = max(1, round(position.notional / position.entry_price))
        side = "sell" if position.direction == "long" else "buy_to_cover"
        result = self._fill(ticker, side, qty)
        return self._record_close(ticker, float(result.avg_fill_price), exit_date, reason, mode=self.mode,
                                  broker=self.broker.id, env=self.broker.env, order_id=result.order_id,
                                  qty=int(result.filled_qty))
