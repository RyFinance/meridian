"""Forward-only evaluator over the registry.

A decision COUNTS only if all of these hold:
  * the chain verifies (and matches any anchors supplied);
  * it was recorded (registry time) strictly before its intended execution time,
    which is also before any outcome (the first mark is at or after execution);
  * the source's own decision time, when given, is before execution and not
    after the registry time;
  * the market data it claims (market_asof) was final before it was recorded;
  * it is not voided and carries none of the excluding flags (backfill,
    decided_after_execution, decided_under_earlier_code, ...).
Everything else is listed with its reasons and never mixed into the statistics.

Targets strategies are simulated from the counted decisions only: fills at the
official open (next_open) or close, the spec's per-side cost in bps on traded
notional plus its per-order fee, daily marks at official closes, dividends
credited in cash on the ex-date. PEAD decisions are evaluated per trade: entry
at the official close of the decision day, exit at the official close 20
business days later, 10 bps round trip.

Usage (manual, read-only except --out):
    PYTHONPATH=. .venv/bin/python -m research.forward.evaluate [--registry PATH]
        [--asof YYYY-MM-DD] [--price-source lse|yfinance] [--anchors FILE] [--out FILE]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from research.forward import nyse, registry
from research.forward.prices import PriceBook, default_pricebook

EXCLUDING_FLAGS = {"recorded_after_execution", "decided_after_execution", "decided_under_earlier_code",
                   "ledger_fill_is_backfill", "allowed_but_no_ledger_fill", "as_of_not_a_session", "backfill",
                   "filled_after_execution_time"}
MIN_SESSIONS_FOR_STATS = 20
TRADING_DAYS = 252


# -- classification -------------------------------------------------------------------

def classify(decision: dict) -> list[str]:
    """Reasons a decision does not count (empty list = counts)."""
    reasons = []
    recorded = registry.parse_utc(decision["recorded_at_utc"])
    execution = registry.parse_utc(decision["intended_execution_utc"])
    if recorded >= execution:
        reasons.append("recorded_after_execution")
    source = decision["payload"].get("source_decided_at_utc")
    if source:
        source_t = registry.parse_utc(source)
        if source_t >= execution:
            reasons.append("source_decided_after_execution")
        if source_t > recorded:
            reasons.append("source_time_after_registry_time")
    asof = decision.get("market_asof")
    if asof:
        day = nyse.to_date(asof)
        if nyse.is_session(day) and nyse.close_utc(day) > recorded:
            reasons.append("market_asof_not_final_when_recorded")
    for flag in decision["payload"].get("flags") or []:
        if flag in EXCLUDING_FLAGS and flag not in reasons:
            reasons.append(flag)
    return reasons


# -- statistics -----------------------------------------------------------------------

def risk_free(dates: list[dt.date]) -> tuple[pd.Series, str]:
    try:
        from research.options_signals.signals import french_daily

        rf = french_daily()["rf"].sort_index()
        idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
        out = rf.reindex(idx.union(rf.index)).ffill().reindex(idx).fillna(0.0)
        return pd.Series(out.to_numpy(), index=dates), f"Ken French daily RF, last published {rf.index.max().date()}, carried forward"
    except Exception as e:  # no rate file: say so rather than invent one
        return pd.Series(0.0, index=dates), f"rf = 0 (French file unavailable: {e!r})"


def return_stats(returns: pd.Series, rf: pd.Series | None = None, seed: int = 20260923) -> dict:
    r = returns.dropna()
    n = int(len(r))
    out: dict = {"sessions": n}
    if n == 0:
        out["status"] = "no marked sessions"
        return out
    nav = (1 + r).cumprod()
    out["total_return"] = float(nav.iloc[-1] - 1)
    out["max_drawdown"] = float((nav / nav.cummax().clip(lower=1.0) - 1).min())
    if n < 2:
        out["status"] = "one session: no dispersion estimate"
        return out
    ex = r - (rf.reindex(r.index).fillna(0.0) if rf is not None else 0.0)
    sd = float(ex.std(ddof=1))
    mean = float(ex.mean())
    out["ann_return_arith"] = float(r.mean() * TRADING_DAYS)
    out["ann_vol"] = float(r.std(ddof=1) * math.sqrt(TRADING_DAYS))
    if sd > 0:
        sr_d = mean / sd
        se_d = math.sqrt((1 + 0.5 * sr_d ** 2) / n)
        out["excess_sharpe"] = sr_d * math.sqrt(TRADING_DAYS)
        out["excess_sharpe_se_iid"] = se_d * math.sqrt(TRADING_DAYS)
        out["excess_sharpe_ci95_iid"] = [(sr_d - 1.96 * se_d) * math.sqrt(TRADING_DAYS),
                                         (sr_d + 1.96 * se_d) * math.sqrt(TRADING_DAYS)]
        out["mean_t_stat"] = mean / sd * math.sqrt(n)
    if n >= 60 and sd > 0:
        rng = np.random.default_rng(seed)
        x = ex.to_numpy()
        block = 10
        draws = []
        for _ in range(2000):
            starts = rng.integers(0, n, size=math.ceil(n / block))
            ix = ((starts[:, None] + np.arange(block)) % n).ravel()[:n]
            b = x[ix]
            s = b.std(ddof=1)
            if s > 0:
                draws.append(b.mean() / s * math.sqrt(TRADING_DAYS))
        out["excess_sharpe_ci95_block_bootstrap"] = np.quantile(draws, [0.025, 0.975]).tolist()
    out["status"] = ("ok" if n >= MIN_SESSIONS_FOR_STATS else
                     f"descriptive only: {n} sessions < {MIN_SESSIONS_FOR_STATS}; the interval is not meaningful")
    return out


def sessions_needed(sharpe: float, t: float = 2.0) -> int | None:
    """Sessions for an annual Sharpe `sharpe` to reach t standard errors (iid)."""
    if not sharpe or sharpe <= 0:
        return None
    return int(math.ceil((t / (sharpe / math.sqrt(TRADING_DAYS))) ** 2))


# -- targets simulation -----------------------------------------------------------------

def _rebalance(units: dict, cash: float, prices: dict, targets: dict, cost_bps: float, fee: float):
    nav = cash + sum(units[s] * prices[s] for s in units)
    symbols = sorted(set(units) | set(targets))
    old = {s: units.get(s, 0.0) * prices[s] for s in symbols}
    lo, hi = 0.0, nav
    for _ in range(80):
        guess = (lo + hi) / 2
        delta = {s: targets.get(s, 0.0) * guess - old[s] for s in symbols}
        cost = sum(abs(v) for v in delta.values()) * cost_bps / 1e4 + sum(abs(v) > 1e-7 for v in delta.values()) * fee
        spend = sum(delta.values()) + cost
        if spend <= cash + 1e-9 and guess * sum(targets.values()) + cost <= nav + 1e-9:
            lo = guess
        else:
            hi = guess
    guess = lo
    delta = {s: targets.get(s, 0.0) * guess - old[s] for s in symbols}
    orders = [s for s in symbols if abs(delta[s]) > 1e-7]
    cost = sum(abs(delta[s]) for s in symbols) * cost_bps / 1e4 + len(orders) * fee
    new_units = {s: (targets.get(s, 0.0) * guess) / prices[s] for s in symbols}
    new_cash = cash - sum(delta.values()) - cost
    fills = [{"symbol": s, "price": prices[s], "notional": delta[s], "units_after": new_units[s]} for s in orders]
    return {s: u for s, u in new_units.items() if abs(u) > 0}, new_cash, cost, fills


def simulate_targets(decisions: list[dict], ev: dict, pricebook: PriceBook, asof: dt.date,
                     cost_bps: float, targets_field: str = "targets") -> dict:
    """Daily NAV from counted decisions only. Starts at the first execution."""
    execs = []
    for d in decisions:
        targets = d["payload"].get(targets_field)
        if not targets:
            continue
        exec_day = nyse.to_date(d["payload"]["execution_date"])
        execs.append((exec_day, d["payload"]["execution"], targets, d["seq"]))
    execs.sort()
    if not execs or execs[0][0] > asof:
        return {"status": "no counted decision has been executed yet", "fills": [], "daily": []}
    start = execs[0][0]
    symbols = sorted({s for _, _, t, _ in execs for s in t})
    px = {s: pricebook.get(s, start, asof) for s in symbols}
    capital = float(ev["capital_usd"])
    fee = float(ev.get("fee_per_order_usd") or 0.0)
    units: dict[str, float] = {}
    cash = capital
    last_close: dict[str, float] = {}
    daily, fills, skipped = [], [], []
    pending = list(execs)
    total_cost = 0.0

    def price(sym, day, field):
        df = px[sym]
        if day in df.index:
            v = df.loc[day, field]
            if v is not None and np.isfinite(v):
                return float(v), df.loc[day, f"{field}_source"]
        return None, None

    for day in nyse.sessions_between(start, asof):
        for sym in list(units):
            df = px[sym]
            if day in df.index:
                split = df.loc[day, "split"]
                if split and np.isfinite(split) and split > 0:
                    units[sym] *= float(split)
                div = df.loc[day, "dividend"]
                if div and np.isfinite(div):
                    cash += units[sym] * float(div)
        day_cost = 0.0
        for when in ("open", "close"):
            due = [e for e in pending if e[0] == day and (e[1] == "next_open") == (when == "open")]
            for e in due:
                pending.remove(e)
                prices, missing = {}, []
                for sym in set(units) | set(e[2]):
                    p, _ = price(sym, day, when)
                    (prices.__setitem__(sym, p) if p is not None else missing.append(sym))
                if missing:
                    skipped.append({"seq": e[3], "date": day.isoformat(), "reason": f"no official {when} for {missing}"})
                    continue
                units, cash, cost, f = _rebalance(units, cash, prices, e[2], cost_bps, fee)
                day_cost += cost
                total_cost += cost
                fills += [{"seq": e[3], "date": day.isoformat(), "at": when, **x,
                           "price_source": px[x["symbol"]].loc[day, f"{when}_source"]} for x in f]
        stale = []
        value = cash
        for sym, u in units.items():
            p, _ = price(sym, day, "close")
            if p is None:
                p = last_close.get(sym)
                stale.append(sym)
            if p is None:
                return {"status": f"no official close for {sym} on {day} and none earlier", "fills": fills, "daily": daily}
            last_close[sym] = p
            value += u * p
        daily.append({"date": day.isoformat(), "nav": value, "cash": cash, "cost": day_cost, "stale_marks": stale})
    frame = pd.DataFrame(daily).set_index("date")
    prev = frame["nav"].shift(1)
    prev.iloc[0] = capital
    frame["return"] = frame["nav"] / prev - 1
    return {"status": "ok", "start": start.isoformat(), "end": frame.index[-1], "fills": fills,
            "skipped_executions": skipped, "total_cost_usd": total_cost, "final_nav": float(frame["nav"].iloc[-1]),
            "stale_mark_sessions": int(sum(bool(s) for s in frame["stale_marks"])),
            "daily": frame.reset_index().to_dict("records"), "_returns": frame["return"]}


def evaluate_targets(strategy_id: str, spec_reg: dict, counted: list[dict], pricebook: PriceBook,
                     asof: dt.date) -> dict:
    ev = spec_reg["payload"]["evaluation"]
    out = {"type": "targets", "n_counted_decisions": len(counted)}
    runs = {"base": ev["cost_per_side_bps"]}
    if ev.get("stress_cost_per_side_bps") is not None:
        runs["stress"] = ev["stress_cost_per_side_bps"]
    for label, bps in runs.items():
        sim = simulate_targets(counted, ev, pricebook, asof, bps)
        returns = sim.pop("_returns", None)
        if returns is not None:
            dates = [nyse.to_date(d) for d in returns.index]
            rf, rf_note = risk_free(dates)
            stats = return_stats(pd.Series(returns.to_numpy(), index=dates), rf)
            stats["risk_free"] = rf_note
            sim["stats"] = stats
        out[label] = sim
    if ev.get("benchmark_targets"):
        bench = simulate_targets(counted, ev, pricebook, asof, ev["cost_per_side_bps"], targets_field="benchmark_targets")
        b_ret = bench.pop("_returns", None)
        out["benchmark"] = {"targets": ev["benchmark_targets"], "status": bench["status"]}
        base_ret = None
        if out["base"].get("status") == "ok":
            base_ret = pd.Series([r["return"] for r in out["base"]["daily"]], index=[r["date"] for r in out["base"]["daily"]])
        if b_ret is not None and base_ret is not None:
            dates = [nyse.to_date(d) for d in b_ret.index]
            out["benchmark"]["stats"] = return_stats(pd.Series(b_ret.to_numpy(), index=dates))
            active = (base_ret - b_ret).dropna()
            n = len(active)
            act = {"sessions": n, "total_active_return_sum": float(active.sum())}
            if n >= 2 and active.std(ddof=1) > 0:
                m, s = float(active.mean()), float(active.std(ddof=1))
                act.update({"ann_active_mean": m * TRADING_DAYS, "t_iid": m / s * math.sqrt(n),
                            "ann_active_ci95_iid": [(m - 1.96 * s / math.sqrt(n)) * TRADING_DAYS,
                                                    (m + 1.96 * s / math.sqrt(n)) * TRADING_DAYS]})
            out["active_vs_benchmark"] = act
    for label in runs:
        out[label].pop("daily", None) if len(out[label].get("daily", [])) > 400 else None
    return out


# -- PEAD per-trade -----------------------------------------------------------------------

def _pead_trade(d: dict, pricebook: PriceBook, asof: dt.date, cost_bps: float, holding: int,
                entry_day: dt.date, entry_field: str) -> dict:
    p = d["payload"]
    sym = p["ticker"]
    sign = 1.0 if p["direction"] == "long" else -1.0
    exit_day = (pd.Timestamp(nyse.to_date(p["as_of_date"])) + pd.offsets.BDay(holding)).date()
    last = min(exit_day, asof)
    if entry_day > asof:
        return {"ticker": sym, "status": "not yet entered", "entry_date": entry_day.isoformat()}
    df = pricebook.get(sym, entry_day, max(last, entry_day))
    if entry_day not in df.index or df.loc[entry_day, entry_field] is None:
        return {"ticker": sym, "status": f"no official {entry_field} on {entry_day}"}
    entry = float(df.loc[entry_day, entry_field])
    closes = df[[x <= last for x in df.index]]["close"].dropna()
    if closes.empty:
        return {"ticker": sym, "status": "no close after entry"}
    mark_day, mark = closes.index[-1], float(closes.iloc[-1])
    divs = float(df[[entry_day < x <= last for x in df.index]]["dividend"].sum())
    gross = sign * ((mark + divs) / entry - 1)
    cost = cost_bps / 2 / 1e4 * (1 + mark / entry)
    fill = p.get("fill") or {}
    return {"ticker": sym, "direction": p["direction"], "entry_date": entry_day.isoformat(), "entry_at": entry_field,
            "entry_price": entry, "entry_source": df.loc[entry_day, f"{entry_field}_source"],
            "exit_date": exit_day.isoformat(), "mark_date": str(mark_day), "mark_price": mark,
            "status": "closed" if mark_day >= exit_day else "open (marked)", "dividends_per_share": divs,
            "net_return": gross - cost, "gross_return": gross,
            "bot_fill_price": fill.get("price"),
            "bot_fill_vs_official_bps": (fill["price"] / entry - 1) * 1e4 if fill.get("price") and entry_field == "close" else None}


def evaluate_pead(spec_reg: dict, decisions: list[tuple[dict, list[str]]], pricebook: PriceBook, asof: dt.date) -> dict:
    ev = spec_reg["payload"]["evaluation"]
    cost, holding = float(ev["round_trip_cost_bps"]), int(ev["holding_business_days"])
    counted, late = [], []
    for d, reasons in decisions:
        if not d["payload"].get("allowed"):
            continue
        entry_day = nyse.to_date(d["payload"]["as_of_date"])
        if not reasons:
            counted.append(_pead_trade(d, pricebook, asof, cost, holding, entry_day, "close"))
        elif set(reasons) <= {"recorded_after_execution", "source_decided_after_execution", "decided_after_execution",
                              "filled_after_execution_time"}:
            t0 = max(registry.parse_utc(d["recorded_at_utc"]), registry.parse_utc(d["payload"]["source_decided_at_utc"]))
            day = t0.astimezone(nyse.ET).date()
            nxt = day if (nyse.is_session(day) and t0 < nyse.open_utc(day)) else nyse.next_session(day)
            late.append({"reasons": reasons, **_pead_trade(d, pricebook, asof, cost, holding, nxt, "open")})

    def summary(trades):
        rets = [t["net_return"] for t in trades if "net_return" in t]
        s = {"n_trades": len(rets), "n_closed": sum(1 for t in trades if t.get("status") == "closed")}
        if rets:
            s["mean_net_return"] = float(np.mean(rets))
            s["hit_rate"] = float(np.mean([r > 0 for r in rets]))
        if len(rets) >= 2:
            from scipy import stats as st

            sd = float(np.std(rets, ddof=1))
            half = st.t.ppf(0.975, len(rets) - 1) * sd / math.sqrt(len(rets))
            s["mean_ci95_t"] = [s["mean_net_return"] - half, s["mean_net_return"] + half]
        s["status"] = "ok" if len(rets) >= 30 else f"descriptive only: {len(rets)} trades (need ~30+ for a usable interval)"
        return s

    return {"type": "pead_events", "counted_trades": counted, "counted_summary": summary(counted),
            "late_repriced_trades": late, "late_repriced_summary": summary(late),
            "late_repriced_note": "NOT forward-clean evidence: decisions recorded after their intended fill, "
                                  "re-priced at the first official open after the later of the bot's and the "
                                  "registry's timestamps, to show what an executable version would have earned."}


def missed_decisions(spec_reg: dict, decisions: list[dict], asof: dt.date) -> list[str]:
    """Scheduled decision dates since registration with no record at all.
    Skipping a month is selection too, so gaps are reported, never filled in."""
    ev = spec_reg["payload"]["evaluation"]
    if ev.get("decision_rule") != "first_session_of_month":
        return []
    registered = registry.parse_utc(spec_reg["recorded_at_utc"])
    have = {d["decision_key"] for d in decisions}
    out, y, m = [], registered.year, registered.month
    while (y, m) <= (asof.year, asof.month):
        day = nyse.first_session_of_month(y, m)
        if registered < nyse.close_utc(day) and day <= asof and day.isoformat() not in have:
            out.append(day.isoformat())
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


# -- driver -------------------------------------------------------------------------------

def evaluate(path: Path, asof: dt.date, pricebook: PriceBook | None = None, anchors=(),
             pead_pricebook: PriceBook | None = None) -> dict:
    """`pricebook` prices targets strategies; `pead_pricebook` (default: the same)
    prices single-stock PEAD trades, where the official auction open/close can
    differ from the last regular-session trade by 10-30 bps
    (reports/forward/lse_reconstruction_check.json), so `main` prefers yfinance there."""
    report = registry.verify_chain(path, anchors=anchors)
    out = {"registry": str(path), "asof": asof.isoformat(), "verify": report.to_dict(),
           "generated_at_utc": registry.iso_utc(registry.utc_now())}
    if not report.ok:
        out["status"] = "REGISTRY DOES NOT VERIFY: nothing evaluated"
        return out
    records = registry.load_records(path)
    live, voided = registry.live_decisions(records)
    specs = registry.registered_specs(records)
    by_hash = {(r["strategy_id"], r["spec_hash"]): r for regs in specs.values() for r in regs}
    out["strategies"] = {}
    own_book = pricebook is None
    pricebook = pricebook or default_pricebook()
    try:
        for sid, regs in specs.items():
            ds = [d for d in live if d["strategy_id"] == sid]
            classified = [(d, classify(d)) for d in ds]
            counted = [d for d, r in classified if not r]
            entry = {"spec_hashes": [r["spec_hash"] for r in regs], "n_decisions": len(ds),
                     "n_counted": len(counted), "n_voided": sum(1 for d in voided if d["strategy_id"] == sid),
                     "excluded": [{"seq": d["seq"], "key": d["decision_key"], "reasons": r} for d, r in classified if r]}
            spec_reg = regs[-1]
            kind = spec_reg["payload"]["evaluation"]["type"]
            if kind == "targets":
                entry["missed_scheduled_decisions"] = missed_decisions(spec_reg, ds, asof)
                per_spec = {}
                for reg in regs:
                    mine = [d for d in counted if d["spec_hash"] == reg["spec_hash"]]
                    if mine:
                        per_spec[reg["spec_hash"][:12]] = evaluate_targets(sid, by_hash[(sid, reg["spec_hash"])], mine,
                                                                           pricebook, asof)
                entry["results"] = per_spec or {"status": "no counted decisions yet"}
                bt = spec_reg["payload"].get("spec", {})
                entry["power_note"] = ("sessions needed for a 2-SE Sharpe at 0.8 (the pre-2024 backtest level): "
                                       f"{sessions_needed(0.8)} (~{sessions_needed(0.8) / TRADING_DAYS:.1f} years)") if bt else None
            elif kind == "mstr_open_close":
                entry["results"] = "scored by research.mstr_btc_0dte.forward evaluate (open-to-close round trips)"
            elif kind == "pead_events":
                entry["results"] = evaluate_pead(spec_reg, classified, pead_pricebook or pricebook, asof)
            out["strategies"][sid] = entry
        out["price_sources"] = {"targets": pricebook.sources_used(),
                                "pead": (pead_pricebook or pricebook).sources_used()}
        out["price_errors"] = pricebook.errors()
        out["status"] = "ok"
    finally:
        if own_book:
            pricebook.close()
    return out


def _default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, (dt.date, pd.Timestamp)):
        return str(o)
    return str(o)


def main(argv=None):
    ap = argparse.ArgumentParser(description="forward-only evaluation of the registry")
    ap.add_argument("--registry", type=Path, default=registry.DEFAULT_REGISTRY)
    ap.add_argument("--asof", default=None, help="last session to mark (default: last completed session)")
    ap.add_argument("--price-source", choices=["auto", "lse", "yfinance"], default="auto",
                    help="auto: LSE 30m regular-session reconstruction for ETF targets, yfinance official "
                         "auction prices for single-stock PEAD trades; each falls back to the other")
    ap.add_argument("--anchors", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    now = registry.utc_now()
    if args.asof:
        asof = nyse.to_date(args.asof)
    else:
        today = now.astimezone(nyse.ET).date()
        asof = today if nyse.is_session(today) and now >= nyse.close_utc(today) else nyse.previous_session(today)
    from research.forward.prices import LSESource, YFSource

    lse, yfs = LSESource(), YFSource()
    targets_pref = "lse" if args.price_source in ("auto", "lse") else "yfinance"
    pead_pref = "yfinance" if args.price_source in ("auto", "yfinance") else "lse"
    book, pead_book = PriceBook(targets_pref, lse, yfs), PriceBook(pead_pref, lse, yfs)
    try:
        result = evaluate(args.registry, asof, book, registry.load_anchors(args.anchors), pead_pricebook=pead_book)
    finally:
        lse.close()
    text = json.dumps(result, indent=2, default=_default, allow_nan=True)
    if args.out:
        args.out.write_text(text)
    print(text if len(text) < 20000 else text[:20000] + "\n... (truncated; use --out)")
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
