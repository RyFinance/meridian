"""Realistic per-trade costs for an intraday MSTR round trip (open -> close), long or short.

Per share / per dollar, as of 2026-10 (US retail-pro broker, IBKR Pro Fixed pricing):
  commission      $0.005/share per side, min $1.00, max 1% of trade value
  SEC Sec. 31     $27.80 per $1M of SALE proceeds (conservative; the rate is reset each fiscal year)
  FINRA TAF       $0.000166/share sold, max $8.30 per trade
  slippage        open fill: 3 bp vs official open (half-spread ~1 bp + auction/impact);
                  close fill: 1 bp vs official close (closing auction)
  borrow (short)  0: the short is opened and covered the same session, so no overnight borrow fee
Stress: slippage 10 bp per side and commission doubled.
A long sells at the close; a short sells at the open. Either way one side carries the SEC/TAF fees."""
from __future__ import annotations

COMMISSION_PER_SHARE = 0.005
COMMISSION_MIN = 1.00
SEC_RATE = 27.80e-6
TAF_PER_SHARE, TAF_MAX = 0.000166, 8.30
SLIP_OPEN_BPS, SLIP_CLOSE_BPS = 3.0, 1.0
STRESS_SLIP_BPS, STRESS_COMMISSION_MULT = 10.0, 2.0


def round_trip_return(direction: int, open_px: float, close_px: float, notional: float, stress: bool = False) -> dict:
    """Net return on `notional` for buying (direction=+1) or shorting (-1) at the open and reversing at the close."""
    so, sc = (STRESS_SLIP_BPS, STRESS_SLIP_BPS) if stress else (SLIP_OPEN_BPS, SLIP_CLOSE_BPS)
    cm = STRESS_COMMISSION_MULT if stress else 1.0
    shares = int(notional // open_px)
    if shares <= 0 or direction == 0:
        return {"shares": 0, "gross": 0.0, "net": 0.0, "cost_usd": 0.0}
    entry = open_px * (1 + direction * so / 1e4)          # pay up when buying, receive less when shorting
    exit_ = close_px * (1 - direction * sc / 1e4)
    pnl = direction * (exit_ - entry) * shares
    comm = sum(min(max(COMMISSION_PER_SHARE * cm * shares, COMMISSION_MIN), 0.01 * px * shares) for px in (entry, exit_))
    sale_px = exit_ if direction > 0 else entry
    regulatory = SEC_RATE * sale_px * shares + min(TAF_PER_SHARE * shares, TAF_MAX)
    net = pnl - comm - regulatory
    gross = direction * (close_px - open_px) * shares
    return {"shares": shares, "gross": gross / notional, "net": net / notional, "cost_usd": gross - net}
