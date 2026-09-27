"""Fast, exact re-execution of the production decision rules (bot/run_cycle.run_cycle as driven by
live_backtest/run_historical_replay.py) for an arbitrary conviction score, size and direction per event.

Why not call run_cycle itself: one replay takes minutes and writes ledger/alert/heartbeat state; a
placebo needs thousands. Fidelity is instead proven by reproducing the recorded sweep_wide_5p0 ledger
trade for trade (tests/test_pead_attack.py::test_engine_reproduces_recorded_ledger and
research/pead_attack/run.py's reproduction gate, which aborts if any trade differs).

Rules re-executed, with the production function reused wherever one exists:
  exits first, every replay day: bot.position_manager.trading_days_elapsed >= 20 (business days), close at
      that day's close; P&L and the 10 bps round trip exactly as PaperExecutionClient.close_position;
      high-water mark updated after every close (bot/execution.py:299-336)
  candidates: events whose effective date is within [as_of - 3 calendar days, as_of]
      (historical_recently_reported), in the watcher's order (days_since ascending, then source row), skipping
      tickers with an open position and events already decided in an earlier cycle (run_cycle.py:270-284)
  highest conviction first: stable sort by score, descending (run_cycle.py:286)
  gate per candidate (bot/risk_gate.evaluate order): kill switch -> 20% cash-basis drawdown cap (engages the
      kill switch) -> breaker tier must be 'armed' -> size (bot: risk.kelly.fractional_kelly_size, quarter
      Kelly, cap 5%) must be > 0 -> risk.limits.check_risk_limits (daily realised loss 3%, per-position 5%,
      gross 100% of cash-basis NAV, computed after each placement)
  entry: notional = size x cash-basis NAV, filled at that day's close (bot/execution.py:281-283)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from bot.kill_switch import DEFAULT_MAX_DRAWDOWN_PCT, check_capital_drawdown_cap
from bot.position_manager import trading_days_elapsed
from earnings.labeling import HOLDING_PERIOD_DAYS
from risk.kelly import fractional_kelly_size
from risk.limits import RiskLimits, check_risk_limits
from risk.transaction_costs import ROUND_TRIP_COST_BPS_DEFAULT

START_CAPITAL = 100_000.0          # bot/run_cycle.STARTING_CAPITAL
LOOKBACK_DAYS = 3                   # bot/run_cycle.EARNINGS_LOOKBACK_DAYS
KELLY_MULT = 0.25                   # bot/risk_gate.evaluate default
PRODUCTION_LIMITS = RiskLimits(max_position_pct=0.05, max_total_exposure_pct=1.00)  # sweep_wide_5p0 == live bot


@dataclass
class Stream:
    """Everything that does not depend on the conviction score: calendar, tiers, prices, visibility."""
    dates: pd.DatetimeIndex
    armed: np.ndarray                 # bool per date
    px: np.ndarray                    # closes, dates x tickers (historical_close_price semantics)
    tickers: list[str]
    ev_ticker: np.ndarray             # int column per event
    ev_scorable: np.ndarray           # bool per event
    ev_key: np.ndarray                # int id of (ticker, announcement day) -- the bot's _event_key
    visible: list[np.ndarray]         # per date: event ids in watcher order
    exit_after: np.ndarray            # per entry date index: first date index with >= 20 elapsed business days
    events: pd.DataFrame = field(repr=False, default=None)

    @classmethod
    def build(cls, events: pd.DataFrame, calendar: pd.DataFrame, closes: pd.DataFrame,
              holding: int = HOLDING_PERIOD_DAYS) -> "Stream":
        dates = pd.DatetimeIndex(calendar.index)
        tickers = list(closes.columns)
        col = {t: j for j, t in enumerate(tickers)}
        ev = events.reset_index(drop=True)
        ev_date = pd.to_datetime(ev["date"]).to_numpy()
        visible = []
        for d in dates:
            floor = d - pd.Timedelta(days=LOOKBACK_DAYS)
            idx = np.flatnonzero((ev_date >= floor.to_datetime64()) & (ev_date <= d.to_datetime64()))
            days_since = (d - pd.to_datetime(ev_date[idx])).days
            order = np.lexsort((ev["row_order"].to_numpy()[idx], np.asarray(days_since)))
            visible.append(idx[order])
        iso = [str(x.date()) for x in dates]
        exit_after = np.full(len(dates), len(dates), dtype=int)
        for i in range(len(dates)):
            for j in range(i + 1, len(dates)):
                if trading_days_elapsed(iso[i], iso[j]) >= holding:
                    exit_after[i] = j
                    break
        keys = pd.factorize(ev["ticker"] + "|" + pd.to_datetime(ev["earnings_date_raw"]).dt.date.astype(str))[0]
        return cls(dates=dates, armed=(calendar["tier"].to_numpy() == "armed"), px=closes.to_numpy(dtype=float),
                   tickers=tickers, ev_ticker=ev["ticker"].map(col).to_numpy(), ev_scorable=ev["scorable"].to_numpy(bool),
                   ev_key=keys, visible=visible, exit_after=exit_after, events=ev)


def kelly_sizes(p: np.ndarray, b: float, limits: RiskLimits = PRODUCTION_LIMITS) -> np.ndarray:
    """Production sizing, via the production function, one scalar call per distinct probability."""
    out = np.full(len(p), np.nan)
    cache: dict[float, float] = {}
    for k, v in enumerate(p):
        if not np.isfinite(v):
            continue
        if v not in cache:
            cache[v] = float(fractional_kelly_size(v, b, KELLY_MULT, limits.max_position_pct))
        out[k] = cache[v]
    return out


@dataclass
class _Pos:
    open: bool
    sign: float
    entry_price: float
    entry_i: int
    size: float
    notional: float
    event: int


def simulate(stream: Stream, score: np.ndarray, size: np.ndarray, sign: np.ndarray,
             limits: RiskLimits = PRODUCTION_LIMITS, cost_bps: float = ROUND_TRIP_COST_BPS_DEFAULT,
             max_drawdown_pct: float = DEFAULT_MAX_DRAWDOWN_PCT, collect_decisions: bool = False) -> dict:
    """Replay the production rules. score: conviction (higher first; NaN = event never scorable),
    size: position fraction if approved (<= 0 -> no_conviction), sign: +1 long / -1 short."""
    n = len(stream.dates)
    one_way = cost_bps / 2 / 10_000.0
    positions: dict[int, _Pos] = {}
    realized, hwm, killed = 0.0, START_CAPITAL, False
    decided = np.zeros(stream.ev_key.max() + 1, dtype=bool)
    trades, decisions = [], []
    for i in range(n):
        # -- exits (position_manager.process_exits over the dict's insertion order) --
        exit_pnls = []
        for t, p in list(positions.items()):
            if p.open and stream.exit_after[p.entry_i] <= i:
                exit_price = float(stream.px[i, t])
                pct = p.sign * (exit_price - p.entry_price) / p.entry_price
                gross = p.notional * pct
                exit_notional = p.notional * (exit_price / p.entry_price) if p.entry_price else p.notional
                cost = (p.notional + exit_notional) * one_way
                pnl = gross - cost
                p.open = False
                realized += pnl
                hwm = max(hwm, START_CAPITAL + realized)
                exit_pnls.append(pnl)
                trades.append({"event": p.event, "ticker": stream.tickers[t], "sign": p.sign, "entry_i": p.entry_i,
                               "exit_i": i, "size_fraction": p.size, "notional": p.notional,
                               "fill_price": p.entry_price, "exit_price": exit_price, "realized_pnl": pnl, "cost": cost})
        daily_pnl = sum(exit_pnls)
        nav = START_CAPITAL + realized
        daily_pnl_pct = daily_pnl / nav if nav > 0 else 0.0
        # -- candidates, highest conviction first --
        cands = []
        for e in stream.visible[i]:
            t = stream.ev_ticker[e]
            if t in positions and positions[t].open:
                continue
            if decided[stream.ev_key[e]] or not np.isfinite(score[e]):
                continue
            cands.append(e)
        cands.sort(key=lambda e: score[e], reverse=True)
        for e in cands:
            decided[stream.ev_key[e]] = True
            t = stream.ev_ticker[e]
            reason = None
            if killed:
                reason = "kill_switch"
            elif check_capital_drawdown_cap(nav, hwm, max_drawdown_pct).breached:
                killed, reason = True, "drawdown_cap"
            elif not stream.armed[i]:
                reason = "circuit_breaker_halt"
            elif not size[e] > 0.0:
                reason = "no_conviction"
            else:
                exposure = (sum(p.notional for p in positions.values() if p.open) / nav) if nav > 0 else 1.0
                chk = check_risk_limits(float(size[e]), exposure, daily_pnl_pct, limits)
                if not chk.allowed:
                    reason = "risk_blocked"
            if collect_decisions:
                decisions.append((i, int(e), reason))
            if reason is None:
                price = float(stream.px[i, t])
                if t in positions:
                    p = positions[t]  # re-open keeps the dict slot, as from_ledger's assignment does
                    p.open, p.sign, p.entry_price, p.entry_i, p.size, p.event = True, float(sign[e]), price, i, float(size[e]), int(e)
                    p.notional = float(size[e]) * nav
                else:
                    positions[t] = _Pos(True, float(sign[e]), price, i, float(size[e]), float(size[e]) * nav, int(e))
    for t, p in positions.items():  # still open at the window's end: marked, no exit cost
        if p.open:
            trades.append({"event": p.event, "ticker": stream.tickers[t], "sign": p.sign, "entry_i": p.entry_i,
                           "exit_i": -1, "size_fraction": p.size, "notional": p.notional, "fill_price": p.entry_price,
                           "exit_price": np.nan, "realized_pnl": np.nan, "cost": np.nan})
    out = {"trades": pd.DataFrame(trades), "final_cash_nav": START_CAPITAL + realized, "killed": killed}
    if collect_decisions:
        out["decisions"] = decisions
    return out
