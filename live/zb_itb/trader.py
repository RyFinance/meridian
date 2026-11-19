"""Live/paper trader for the ZB-overnight -> ITB first-hour rule (research/zb_itb/verify/VERIFICATION.md).

The same frozen ZB signal is routed to two independent Alpaca paper accounts:

    ITB  -> ITB  (1x homebuilders ETF)
    NAIL -> NAIL (3x daily homebuilders ETF)

    PYTHONPATH=. .venv/bin/python -m live.zb_itb.trader status
    PYTHONPATH=. .venv/bin/python -m live.zb_itb.trader enter      # launchd ~09:14 ET
    PYTHONPATH=. .venv/bin/python -m live.zb_itb.trader exit       # launchd ~10:29 ET
    PYTHONPATH=. .venv/bin/python -m live.zb_itb.trader failsafe   # launchd 15:50 ET
    add --dry-run to run against in-memory fake brokers (no keys, no orders).

Each account has its own key file:
    quant_v7/.env.alpaca.itb
    quant_v7/.env.alpaca.nail
Paper vs live is chosen only by ALPACA_MODE in those files (live also needs LIVE_CONFIRM).
Safety: KILL file stops new entries; drawdown guard writes KILL; protective stop on every position; failsafe flatten;
PDT guard (< $25k equity: no 4th day trade in 5 days); shorts only if shortable + easy to borrow; whole shares only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from live.zb_itb.broker import Alpaca, BrokerError, FakeBroker

ET = ZoneInfo("America/New_York")
H = Path(__file__).parent
CFG = json.loads((H / "config.json").read_text())
JOURNAL, STATE, KILL = H / "journal.jsonl", H / "state.json", H / "KILL"
SYM = CFG["symbol"]

# Stable default for older callers/tests; the live config overrides this with two accounts.
ACCOUNTS: dict[str, dict] = dict(CFG.get("accounts") or {
    "ITB": {
        "symbol": SYM,
        "env": ".env.alpaca",
        "start_equity_usd": CFG.get("virtual_capital_usd") or 2000,
        "virtual": True,
        "legacy": True,
    }
})
for _name, _acct in ACCOUNTS.items():
    _acct.setdefault("symbol", SYM)
    _acct.setdefault("env", ".env.alpaca")
    _acct.setdefault("start_equity_usd", CFG.get("virtual_capital_usd") or 2000)
    _acct.setdefault("gap_cushion_pct", 1.0)


def now_et() -> dt.datetime:
    return dt.datetime.now(ET)


def at(t: str, day: dt.date | None = None) -> dt.datetime:
    hh, mm, ss = (int(x) for x in t.split(":"))
    return dt.datetime.combine(day or now_et().date(), dt.time(hh, mm, ss), ET)


def sleep_until(t: dt.datetime, dry: bool) -> None:
    if dry: return
    while (rem := (t - now_et()).total_seconds()) > 0:
        time.sleep(min(rem, 30))


def log(event: str, **kw) -> dict:
    rec = {"ts_et": now_et().isoformat(timespec="seconds"), "event": event, **kw}
    with open(JOURNAL, "a") as f:
        f.write(json.dumps(rec, default=str) + "\n")
    print(json.dumps(rec, default=str), flush=True)
    return rec


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(s: dict) -> None:
    STATE.write_text(json.dumps(s, indent=2))


def account_names() -> list[str]:
    return list(ACCOUNTS)


def account_cfg(name: str) -> dict:
    return ACCOUNTS[name]


def account_symbol(name: str) -> str:
    return str(account_cfg(name).get("symbol") or SYM)


def account_start_equity(name: str) -> float:
    return float(account_cfg(name).get("start_equity_usd") or 0.0)


def account_state(name: str) -> dict:
    return dict((load_state().get("accounts") or {}).get(name) or {})


def update_account_state(name: str, **kw) -> None:
    st = load_state()
    a = st.setdefault("accounts", {}).setdefault(name, {})
    a.update(kw)
    save_state(st)


def cid(day: dt.date, tag: str, mode: str, account: str | None = None) -> str:
    prefix = f"zbitb-{account.lower()}-" if account else "zbitb-"
    return f"{prefix}{mode}-{day.isoformat()}-{tag}"[:48]


def get_broker(dry: bool, account: str | None = None):
    """BROKER=alpaca (default) or ibkr for the legacy single-account path.

    When account is supplied (the dual-account path), always use that account's
    own Alpaca key file. There is no cross-account fallback.
    """
    if dry:
        if account:
            return FakeBroker(equity=account_start_equity(account) or 25_000.0)
        return FakeBroker()
    import os
    from live.zb_itb.broker import ROOT, load_env
    if account:
        cfg = account_cfg(account)
        env = load_env(ROOT / str(cfg.get("env") or ".env.alpaca"))
        return Alpaca(env)
    choice = (os.environ.get("BROKER") or load_env(ROOT / ".env.broker").get("BROKER", "alpaca")).lower()
    if choice == "ibkr":
        from live.zb_itb.broker_ibkr import IBKR
        ib_env = load_env(ROOT / ".env.ibkr")
        try:
            return IBKR(ib_env)
        except BrokerError as e:
            # paper only: keep the paper record going on Alpaca while IB Gateway isn't set up. Live never falls back.
            if ib_env.get("IBKR_MODE", "paper").lower() == "paper" and (ROOT / ".env.alpaca").exists():
                log("broker_fallback", from_broker="ibkr", to_broker="alpaca-paper", reason=str(e)[:200])
                b = Alpaca()
                if b.mode != "paper":
                    raise BrokerError("fallback refused: Alpaca is not in paper mode")
                return b
            raise
    return Alpaca()


def virtual_on(mode: str) -> bool:
    """Legacy paper virtual balance. Dual accounts are real $2k paper accounts and set virtual=false."""
    return mode in ("paper", "dry-run") and bool(CFG.get("virtual_capital_usd"))


def virtual_commission(shares: float) -> float:
    """Round-trip commission the virtual account is charged (IBKR Pro Tiered approx: max($0.35, $0.0035/sh) + ~$0.0005/sh fees, per order)."""
    c = CFG.get("virtual_commission") or {}
    per = max(c.get("min_per_order", 0.35), c.get("per_share", 0.0035) * shares) + c.get("extra_per_share", 0.0005) * shares
    return round(2 * per, 4)


def virtual_fees(shares: float, price: float) -> float:
    """All-in round-trip fees a live IBKR account would pay: commissions both sides + SEC fee ($27.80/$1M sold)
    + FINRA TAF ($0.000166/share sold, max $8.30). One side of every round trip is a sale (the exit of a long, the entry of a short)."""
    sold = shares * price
    return round(virtual_commission(shares) + 27.80e-6 * sold + min(0.000166 * shares, 8.30), 4)


def virtual_equity(mode: str) -> float:
    return float(load_state().get(f"virtual_equity_{mode}", CFG.get("virtual_capital_usd") or 0))


def drawdown_guard(acct: dict, mode: str, account: str | None = None) -> bool:
    """Track high-water equity per account/mode; write KILL if equity falls max_drawdown_pct below it."""
    st = load_state(); key = f"hw_{mode}"; eq = float(acct["equity"])
    if account:
        a = st.setdefault("accounts", {}).setdefault(account, {})
        # per-account high-water starts at that account's first seen equity, never the legacy single-account value
        hw = a.get(key, eq)
        a[key] = max(float(hw), eq)
    else:
        st[key] = max(st.get(key, eq), eq)
    save_state(st)
    hw = float((st.get("accounts", {}).get(account, {}) if account else st).get(key, eq))
    dd = (eq / hw - 1) * 100
    if dd <= -CFG["max_drawdown_pct"]:
        KILL.write_text(f"drawdown {dd:.1f}% from high-water {hw:.2f} on {now_et().date()}\n")
        log("kill_drawdown", account=account, equity=eq, high_water=hw, drawdown_pct=round(dd, 2))
        return False
    return True


def regime_corr(day: dt.date, dry: bool) -> float | None:
    """Past-only 60-day correlation of daily ITB vs TLT returns (adjusted closes before `day`).
    The edge needs homebuilders to trade WITH bonds (research/zb_itb/verify/VERIFICATION.md section 8). None if data fails."""
    if dry:
        return 0.5
    try:
        import numpy as np, yfinance as yf
        px = yf.download(["ITB", "TLT"], period="6mo", auto_adjust=True, progress=False)["Close"]
        px = px[px.index.date < day].dropna()
        r = np.log(px).diff().dropna().tail(CFG.get("regime_window_days", 60))
        return float(r["ITB"].corr(r["TLT"])) if len(r) >= 40 else None
    except Exception:  # noqa: BLE001
        return None


def signal(day: dt.date, dry: bool) -> dict:
    if dry:
        return {"d": 1, "zb_p0_prev1600": 115.0, "zb_p1_0900": 115.4, "prev_session": "dry"}
    from research.zb_itb.forward import signal as frozen_signal   # same frozen rule as the forward test
    return frozen_signal(day)


def journal_rows() -> list[dict]:
    if not JOURNAL.exists():
        return []
    out = []
    for line in JOURNAL.read_text().splitlines():
        try: out.append(json.loads(line))
        except ValueError: pass
    return out


def sim_offset(name: str) -> float:
    """Net P&L of this account's simulated trades (event sim_trade). The desk shows broker equity + this, and the
    trader sizes and applies the short rule off the same number."""
    reb = str(account_cfg(name).get("rebased_on") or "")      # new paper account already holds sims up to this day
    return round(sum(float(r.get("net_pl") or 0) for r in journal_rows()
                     if r.get("event") == "sim_trade" and r.get("account") == name
                     and (not reb or str(r.get("day") or r.get("ts_et", ""))[:10] > reb)), 2)


def _minute_bars(b, sym: str, day: dt.date) -> list[dict]:
    """Alpaca SIP 1-minute bars 09:30-10:29 ET (fetch after ~10:45 ET; the free plan withholds the last 15 minutes)."""
    from live.zb_itb.broker import DATA_URL
    start, end = at("09:30:00", day), at("10:30:00", day)
    r = b._req("GET", f"{DATA_URL}/v2/stocks/{sym}/bars", params={
        "timeframe": "1Min", "start": start.isoformat(), "end": end.isoformat(), "feed": "sip", "limit": 1000, "adjustment": "raw"})
    return [x for x in (r.get("bars") or []) if dt.datetime.fromisoformat(x["t"].replace("Z", "+00:00")) < end]


def simulate_fill(name: str, b, sym: str, day: dt.date, d: int, qty: int, why: str, signal_rec: dict | None = None) -> dict | None:
    """Paper force-fill: book `qty` shares the broker never filled as if they had, using the live rules on real 1m bars
    (entry at the 09:30 open, 3% stop filled at the stop price, else out at 10:30, IBKR-style fees)."""
    if qty < 1 or not d:
        return None
    bars = _minute_bars(b, sym, day)
    if not bars:
        log("warn", account=name, symbol=sym, reason="force-fill simulation: no minute bars", day=str(day)); return None
    entry = float(bars[0]["o"]); stop = round(entry * (1 - d * CFG["protective_stop_pct"] / 100), 2)
    lo, hi = min(float(x["l"]) for x in bars), max(float(x["h"]) for x in bars)
    stopped = lo <= stop if d > 0 else hi >= stop
    exit_px = stop if stopped else float(bars[-1]["c"])
    gross = round(d * qty * (exit_px - entry), 2); fees = round(virtual_fees(qty, entry), 2)
    rec = log("sim_trade", ts_et=at("10:30:00", day).isoformat(timespec="seconds"), simulated=True, account=name, symbol=sym, day=str(day), side="buy" if d > 0 else "sell", qty=qty,
              entry_price=entry, exit_price=exit_px, stop_price=stop, stopped=stopped, window_low=lo, window_high=hi,
              signal=signal_rec, gross_pl=gross, fees=fees, net_pl=round(gross - fees, 2), ret_pct=round(d * (exit_px / entry - 1) * 100, 3),
              reason=f"SIMULATED force fill: {why}. Live rules on Alpaca SIP 1m bars (09:30 open, 3% stop, 10:30 exit, IBKR-style fees). The broker never saw these shares.")
    return rec


def _simulate_shortfalls(day: dt.date, dry: bool) -> None:
    """After the session: any shares the plan called for but the paper broker didn't fill (auction misses, slow late
    fills, buying-power or shorting limits) are booked as a simulated trade."""
    rows = [r for r in journal_rows() if str(r.get("ts_et", ""))[:10] == day.isoformat()]
    for name in account_names():
        mine = [r for r in rows if r.get("account") == name]
        if any(r.get("event") == "sim_trade" for r in mine):
            continue
        plan = next((r for r in reversed(mine) if r.get("event") in ("entry_submitted", "sim_intent")), None)
        if not plan:
            continue
        target = int(plan.get("target_qty") or plan.get("qty") or 0)
        filled = 0 if plan["event"] == "sim_intent" else int(max([float(r.get("qty") or 0) for r in mine if r.get("event") == "entry_filled"] or [0]))
        short = target - filled
        if short < 1:
            continue
        why = plan.get("reason") if plan["event"] == "sim_intent" else f"paper broker filled {filled} of {target} shares"
        try:
            simulate_fill(name, get_broker(dry, name), account_symbol(name), day, 1 if plan.get("side") == "buy" else -1, short, why, plan.get("signal"))
        except Exception as ex:  # noqa: BLE001
            log("error", account=name, cmd="simulate_fill", error=f"{type(ex).__name__}: {str(ex)[:240]}")


def _entry_ref(b, sym: str) -> float:
    try:
        return float(b.latest_trade(sym))
    except Exception:  # noqa: BLE001
        import yfinance as yf
        return float(yf.Ticker(sym).history(period="5d")["Close"].iloc[-1])


def _prepare_entry(name: str, b, day: dt.date, sig: dict, d: int, dry: bool) -> dict | None:
    """Eligibility check, sizing, and MOO submission for one account. Returns a pending entry dict."""
    cfg = account_cfg(name); sym = account_symbol(name); mode = b.mode
    if b.order_by_client_id(cid(day, "entry", mode, name)):
        log("skip", account=name, symbol=sym, reason="entry already submitted today"); return None
    existing = b.position(sym)
    if existing and float(existing.get("qty", 0)) != 0:
        log("skip", account=name, symbol=sym, reason="position already open", qty=existing.get("qty")); return None
    acct = b.account()
    if cfg.get("virtual") and virtual_on(mode):
        acct = {**acct, "broker_equity": acct.get("equity"), "equity": str(virtual_equity(mode))}
    if acct.get("trading_blocked") or acct.get("status") != "ACTIVE":
        log("skip", account=name, symbol=sym, reason="account not tradable", status=acct.get("status")); return None
    broker_eq = float(acct["equity"])
    sim = sim_offset(name) if b.mode == "paper" else 0.0
    eq = round(broker_eq + sim, 2)                      # desk equity: broker + simulated fills
    if not drawdown_guard({**acct, "equity": str(eq)}, mode, name):
        return None
    broker_short_ok = True
    if d < 0:
        if CFG["side_mode"] == "long_only" or (CFG["side_mode"] == "auto" and eq < CFG.get("short_min_equity_usd", 2000)):
            log("skip", account=name, symbol=sym, reason=f"short signal, long-only until equity >= ${CFG.get('short_min_equity_usd', 2000):,.0f}", equity=eq, signal=sig)
            return None
        asset = b.asset(sym)
        if broker_eq < 2000 or not acct.get("shorting_enabled") or not asset.get("shortable") or not asset.get("easy_to_borrow"):
            if b.mode != "paper":
                log("skip", account=name, symbol=sym, reason="cannot short", equity=broker_eq, asset=asset, shorting_enabled=acct.get("shorting_enabled")); return None
            broker_short_ok = False
    if eq < 25_000 and (int(acct.get("daytrade_count") or 0) >= 3 or acct.get("pattern_day_trader")):
        log("skip", account=name, symbol=sym, reason="PDT guard: equity < $25k and 3 day trades used in 5 days", daytrade_count=acct.get("daytrade_count")); return None
    ref = _entry_ref(b, sym)
    notional = min(eq * CFG["max_fraction_of_equity"], CFG["max_notional_usd"] or 1e18)
    cushion = 1 + float(cfg.get("gap_cushion_pct", 1.0)) / 100
    qty = math.floor(notional / (ref * cushion))
    if qty < 1:
        log("skip", account=name, symbol=sym, reason="size < 1 share", equity=eq, ref_price=ref); return None
    target = qty
    if not broker_short_ok:                             # paper: the broker can't short this account, simulate it whole
        log("sim_intent", account=name, symbol=sym, side="sell", qty=target, target_qty=target, ref_price=ref, equity=eq,
            broker_equity=broker_eq, signal=sig, reason=f"broker can't short (equity ${broker_eq:,.2f}); simulated in full")
        return None
    qty = min(target, math.floor(min(broker_eq * CFG["max_fraction_of_equity"], CFG["max_notional_usd"] or 1e18) / (ref * cushion)))
    if qty < 1:
        log("sim_intent", account=name, symbol=sym, side="buy" if d > 0 else "sell", qty=target, target_qty=target, ref_price=ref,
            equity=eq, broker_equity=broker_eq, signal=sig, reason="broker equity too small for one share; simulated in full")
        return None
    if now_et() >= at(CFG["opg_deadline_et"]) and not dry:
        log("skip", account=name, symbol=sym, reason="missed MOO deadline", signal=sig); return None
    side = "buy" if d > 0 else "sell"
    o = b.submit(symbol=sym, qty=str(qty), side=side, type="market", time_in_force="opg",
                 client_order_id=cid(day, "entry", mode, name))
    log("entry_submitted", account=name, symbol=sym, mode=mode, side=side, qty=qty, target_qty=target, ref_price=ref, equity=eq,
        broker_equity=broker_eq, signal=sig, order_id=o.get("id"))
    return {"broker": b, "name": name, "symbol": sym, "mode": mode, "side": side, "qty": qty,
            "ref": ref, "d": d, "order": o}


def _qty_within_buying_power(err: str, qty: int, force: bool = False) -> int | None:
    """From an Alpaca 403 "insufficient buying power" body, the share count that fits (2% cushion for price moves).
    None when buying power is far below the cost (an open order still holds it, so waiting helps), unless force."""
    try:
        body = json.loads(err[err.index("{"):])
        bp, cost = float(body["buying_power"]), float(body["cost_basis"])
    except (ValueError, KeyError, TypeError):
        return None
    if cost <= 0 or qty < 1:
        return None
    if bp < 0.5 * cost and not force:
        return None
    return min(qty - 1, int(bp * 0.98 / (cost / qty)))


def _finalize_entries(entries: dict[str, dict], day: dt.date, dry: bool) -> None:
    """Wait for the opening auction, recover a late fill if needed, and place protective stops for every account."""
    if not entries:
        return
    if not dry:
        sleep_until(at(CFG["fill_check_et"]), dry)

    pending: dict[str, dict] = {}
    for name, e in entries.items():
        o = e.get("order") or {}
        if not dry:
            o = e["broker"].order_by_client_id(cid(day, "entry", e["mode"], name)) or o
            e["order"] = o
        if o.get("status") != "filled":
            pending[name] = e

    if not dry and pending:
        for name, e in list(pending.items()):
            if now_et() >= at(CFG["late_entry_cutoff_et"]):
                break
            b = e["broker"]; o = e.get("order") or {}
            if o.get("status") in ("new", "accepted", "pending_new", "partially_filled"):
                try: b.cancel(o["id"])
                except Exception as ex: log("warn", account=name, reason="cancel failed", error=str(ex)[:160])
            # An open opening-auction order keeps its buying power reserved, so a late order sent too soon is
            # rejected (2026-10-22 NAIL: 3 of 71 filled, late entry 403 "insufficient buying power").
            # Wait for it to settle, then top up only the unfilled shares.
            for _ in range(15):
                oo = b.order_by_client_id(cid(day, "entry", e["mode"], name)) or o
                if oo.get("status") not in ("new", "accepted", "pending_new", "partially_filled", "pending_cancel"):
                    break
                time.sleep(2)
            o = oo
            remaining = int(e["qty"] - float(o.get("filled_qty") or 0))
            if remaining < 1:
                pending.pop(name, None); continue
            for attempt in range(4):
                try:
                    lo = b.submit(symbol=e["symbol"], qty=str(remaining), side=e["side"], type="market", time_in_force="day",
                                  client_order_id=cid(day, "entry-late", e["mode"], name))
                    log("late_entry_submitted", account=name, symbol=e["symbol"], reason="MOO not (fully) filled",
                        qty=remaining, moo_filled=o.get("filled_qty"))
                    break
                except Exception as ex:  # noqa: BLE001
                    if "insufficient buying power" in str(ex) and attempt < 3:
                        fit = _qty_within_buying_power(str(ex), remaining, force=attempt >= 1)
                        if fit is None:          # the auction order's reservation hasn't cleared yet: wait
                            time.sleep(3); continue
                        if fit < 1:
                            log("error", account=name, symbol=e["symbol"], cmd="entry-late", error=str(ex)[:240])
                            pending.pop(name, None); break
                        # the price ran past the 09:15 sizing price (2026-10-30 NAIL: 58 sh sized at 32.27 cost
                        # 1981 vs 1942 buying power), so buy what the account can afford
                        log("warn", account=name, symbol=e["symbol"], reason="late entry resized to buying power",
                            qty_from=remaining, qty_to=fit)
                        remaining = fit; continue
                    log("error", account=name, symbol=e["symbol"], cmd="entry-late", error=str(ex)[:240])
                    pending.pop(name, None); break
        for _ in range(60):
            if not pending or now_et() >= at(CFG["late_entry_cutoff_et"]):
                break
            for name in list(pending):
                e = pending[name]
                o = e["broker"].order_by_client_id(cid(day, "entry-late", e["mode"], name))
                if o and o.get("status") == "filled":
                    e["order"] = o
                    pending.pop(name, None)
            if pending:
                time.sleep(3)

    for name, e in entries.items():
        try:
            b, sym, mode, o = e["broker"], e["symbol"], e["mode"], e.get("order") or {}
            if not dry:
                o = b.order_by_client_id(cid(day, "entry", mode, name)) or o
                if o.get("status") != "filled":
                    late = b.order_by_client_id(cid(day, "entry-late", mode, name))
                    if late:
                        o = late
                e["order"] = o
            if o.get("status") != "filled":
                if o.get("status") in ("new", "accepted", "pending_new", "partially_filled"):
                    try: b.cancel(o["id"])
                    except Exception: pass
                    if not dry:
                        time.sleep(2)
                pos = b.position(sym)            # the position, not the order status, is the source of truth
                if not pos or float(pos.get("qty", 0)) == 0:
                    log("skip", account=name, symbol=sym, reason="entry not filled", order_status=o.get("status")); continue
                o = {"filled_avg_price": pos.get("avg_entry_price"), "filled_qty": str(abs(float(pos["qty"])))}
                log("warn", account=name, symbol=sym, reason="order status said unfilled but a position exists; protecting it", qty=pos.get("qty"))
            fill = float(o.get("filled_avg_price") or e["ref"]); fq = float(o.get("filled_qty") or e["qty"])
            if not dry:
                pos = b.position(sym)            # auction + late top-up: protect the whole position
                if pos and float(pos.get("qty", 0)) != 0:
                    fq = abs(float(pos["qty"])); fill = float(pos.get("avg_entry_price") or fill)
            log("entry_filled", account=name, symbol=sym, side=e["side"], qty=fq, fill_price=fill)
            update_account_state(name, last_qty=fq, last_px=fill)
            stop_px = round(fill * (1 - e["d"] * CFG["protective_stop_pct"] / 100), 2)
            so = b.submit(symbol=sym, qty=str(int(fq)), side="sell" if e["d"] > 0 else "buy", type="stop", stop_price=str(stop_px),
                          time_in_force="day", client_order_id=cid(day, "stop", mode, name))
            log("stop_placed", account=name, symbol=sym, stop_price=stop_px, order_id=so.get("id"))
        except Exception as ex:  # noqa: BLE001
            log("error", account=name, cmd="finalize_entry", error=str(ex)[:300])


def cmd_status(dry: bool) -> None:
    out = {"mode": "dry-run" if dry else "live", "kill_file": KILL.exists(), "config": CFG, "accounts": {}}
    for name in account_names():
        try:
            b = get_broker(dry, name); a = b.account(); sym = account_symbol(name); asset = b.asset(sym)
            out["accounts"][name] = {
                "symbol": sym, "mode": b.mode, "equity": a.get("equity"), "last_equity": a.get("last_equity"),
                "buying_power": a.get("buying_power"), "status": a.get("status"), "trading_blocked": a.get("trading_blocked"),
                "pattern_day_trader": a.get("pattern_day_trader"), "daytrade_count": a.get("daytrade_count"),
                "shorting_enabled": a.get("shorting_enabled"), "multiplier": a.get("multiplier"),
                "asset": {k: asset.get(k) for k in ("tradable", "shortable", "easy_to_borrow", "fractionable")},
                "positions": b.positions(), "open_orders": len(b.orders()),
            }
        except Exception as ex:  # noqa: BLE001
            out["accounts"][name] = {"error": f"{type(ex).__name__}: {str(ex)[:240]}"}
    print(json.dumps(out, indent=2, default=str))


def cmd_enter(dry: bool) -> None:
    day = now_et().date(); names = account_names()
    brokers: dict[str, object] = {}
    for name in names:
        try:
            brokers[name] = get_broker(dry, name)
        except Exception as ex:  # noqa: BLE001
            log("error", account=name, cmd="enter", error=f"{type(ex).__name__}: {str(ex)[:240]}")
    if not brokers:
        log("skip", reason="no usable broker accounts"); return
    if not dry:
        try:
            if not next(iter(brokers.values())).calendar(day.isoformat()):
                log("skip", reason="market closed today", day=day); return
        except Exception as ex:  # noqa: BLE001
            log("error", cmd="enter", reason="calendar check failed", error=str(ex)[:240]); return
    if KILL.exists():
        log("skip", reason="KILL file present", detail=KILL.read_text().strip()); return

    # 1) One frozen signal for all accounts.
    sleep_until(at(CFG["signal_ready_et"]), dry)
    sig = None
    while True:
        try:
            sig = signal(day, dry)
            if sig.get("zb_p1_0900") is not None or dry: break
        except Exception as e:  # noqa: BLE001
            sig = {"error": repr(e)}
        if now_et() >= at(CFG["opg_deadline_et"]) - dt.timedelta(seconds=60): break
        time.sleep(20)
    d = int(sig.get("d", 0) or 0) if sig else 0
    if d == 0:
        log("skip", reason="no signal", signal=sig); return

    # 1b) Regime switch is common to both accounts.
    if CFG.get("regime_filter", False):
        rc = regime_corr(day, dry)
        if rc is None:
            log("warn", reason="regime correlation unavailable; trading without the switch today")
        elif rc <= CFG.get("regime_min_corr", 0.0):
            log("skip", reason=f"regime off: 60d corr(ITB,TLT) {rc:.2f} <= {CFG.get('regime_min_corr', 0.0):.2f}", regime_corr=round(rc, 3), signal=sig); return
        else:
            log("regime_ok", regime_corr=round(rc, 3))

    # 2) Submit the same direction to every account, sized off that account's own equity.
    entries: dict[str, dict] = {}
    for name, b in brokers.items():
        try:
            e = _prepare_entry(name, b, day, sig, d, dry)
            if e:
                entries[name] = e
        except Exception as ex:  # noqa: BLE001
            log("error", account=name, cmd="prepare_entry", error=f"{type(ex).__name__}: {str(ex)[:300]}")

    # 3) Confirm fills and place stops after the auction.
    _finalize_entries(entries, day, dry)


def flatten(b, reason: str, symbol: str, account: str | None = None, realized_if_flat: bool = False) -> float:
    """Cancel orders and close the position. Returns the P&L of the closed position (broker's unrealized P&L at close),
    or, with realized_if_flat, today's realized round trip when the position is already gone (stopped out)."""
    for o in b.orders(symbols=symbol):
        b.cancel(o["id"]); log("order_canceled", account=account, symbol=symbol, order_id=o["id"], type=o.get("type"), reason=reason)
    pos = b.position(symbol)
    if not pos:
        # Already flat: the stop may have closed today's trade before the exit ran (2026-10-28 NAIL logged $0 for a
        # −$64 stop-out). Book the round trip's realized P&L from today's fills.
        pl = _realized_today(b, symbol) if realized_if_flat else 0.0
        log("flat", account=account, symbol=symbol, reason=reason, realized_pl=round(pl, 2) if pl else 0.0)
        return pl
    # Alpaca releases shares held by a just-canceled stop a moment later; a close sent too soon gets 403
    # "insufficient qty available" (2026-10-22 NAIL). Retry until the hold clears.
    for attempt in range(15):
        try:
            b.close_position(symbol); break
        except BrokerError as ex:
            if "insufficient qty" not in str(ex) or attempt == 14:
                raise
            time.sleep(2)
    log("close_submitted", account=account, symbol=symbol, reason=reason, qty=pos.get("qty"), avg_entry=pos.get("avg_entry_price"), unrealized_pl=pos.get("unrealized_pl"))
    try:
        return float(pos.get("unrealized_pl") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _realized_today(b, symbol: str) -> float:
    """Realized P&L of today's (ET) fills in symbol: sells minus buys. 0 unless the fills net to a closed round trip."""
    today = now_et().date(); cash = qty = 0.0
    try:
        orders = b.orders(status="closed", symbols=symbol)
    except BrokerError:
        return 0.0
    for o in orders:
        q, px = float(o.get("filled_qty") or 0), o.get("filled_avg_price")
        ts = o.get("filled_at") or o.get("submitted_at")
        if not q or px is None or not ts or o.get("symbol", symbol) != symbol:
            continue
        if dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(ET).date() != today:
            continue
        s = 1.0 if o.get("side") == "sell" else -1.0
        cash += s * q * float(px); qty -= s * q
    return cash if abs(qty) < 1e-9 else 0.0


def _update_virtual_exit(name: str, b, pl: float) -> None:
    cfg = account_cfg(name)
    if not (cfg.get("virtual") and virtual_on(b.mode)):
        return
    if not pl:
        return
    st = load_state(); k = f"virtual_equity_{b.mode}"
    fee = virtual_fees(abs(float(account_state(name).get("last_qty", 0))), float(account_state(name).get("last_px", 0)))
    st[k] = round(float(st.get(k, CFG["virtual_capital_usd"])) + pl - fee, 2); save_state(st)
    log("virtual_equity_adjust", account=name, trade_pl=round(pl, 2), commission=fee, equity=st[k])


def cmd_exit(dry: bool) -> None:
    sleep_until(at(CFG["exit_et"]), dry)
    for name in account_names():
        try:
            b = get_broker(dry, name); sym = account_symbol(name)
            pl = flatten(b, "scheduled 10:30 exit", sym, name, realized_if_flat=True)
            if not dry:
                time.sleep(10)
                if b.position(sym):
                    log("warn", account=name, symbol=sym, reason="position still open after close; retrying")
                    pl += flatten(b, "exit retry", sym, name)
            _update_virtual_exit(name, b, pl)
            a = b.account()
            log("day_end_equity", account=name, symbol=sym, equity=a.get("equity"), last_equity=a.get("last_equity"), trade_pl=round(pl, 2))
        except Exception as ex:  # noqa: BLE001
            log("error", account=name, cmd="exit", error=f"{type(ex).__name__}: {str(ex)[:300]}")


def _network_error(ex: Exception) -> bool:
    s = str(ex)
    return "failed after retries" in s or "ConnectionError" in s or "NameResolution" in s or "timed out" in s.lower()


def cmd_failsafe(dry: bool) -> None:
    for name in account_names():
        # launchd runs a missed job when the Mac wakes, often before Wi-Fi is back (2026-10-19/21/26: DNS failures).
        # Keep trying for ~10 minutes before giving up.
        for attempt in range(20):
            try:
                b = get_broker(dry, name); sym = account_symbol(name)
                if b.position(sym) or b.orders(symbols=sym):
                    log("failsafe_triggered", account=name, symbol=sym)
                    pl = flatten(b, "15:50 failsafe", sym, name)
                    _update_virtual_exit(name, b, pl)
                else:
                    log("failsafe_ok", account=name, symbol=sym)
                break
            except Exception as ex:  # noqa: BLE001
                if _network_error(ex) and attempt < 19 and not dry:
                    time.sleep(30); continue
                log("error", account=name, cmd="failsafe", error=f"{type(ex).__name__}: {str(ex)[:300]}")
                break
    if not dry:
        _simulate_shortfalls(now_et().date(), dry)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["status", "enter", "exit", "failsafe"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.dry_run:   # keep dry runs out of the real journal/state/kill files
        JOURNAL, STATE, KILL = H / "journal_dryrun.jsonl", H / "state_dryrun.json", H / "KILL_dryrun"
    try:
        {"status": cmd_status, "enter": cmd_enter, "exit": cmd_exit, "failsafe": cmd_failsafe}[a.cmd](a.dry_run)
    except BrokerError as e:
        log("error", cmd=a.cmd, error=str(e)); raise SystemExit(2)
