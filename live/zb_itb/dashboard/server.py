"""ZB -> ITB trading desk dashboard backend (FastAPI + terminal canvas frontend).

Serves static/ at / and JSON under /api/. Read-only except account refresh
(which queries the broker) and never places orders.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys
import time
from functools import lru_cache
from itertools import groupby
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[3]
LIVE = ROOT / "live" / "zb_itb"
ET, PT = ZoneInfo("America/New_York"), ZoneInfo("America/Los_Angeles")
HOLDOUT_START = "2026-08-11"

sys.path.insert(0, str(ROOT))


def _jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def _cfg() -> dict:
    return json.loads((LIVE / "config.json").read_text())


def _journal_df() -> pd.DataFrame:
    j = pd.DataFrame(_jsonl(LIVE / "journal.jsonl"))
    if not j.empty:
        j["ts"] = pd.to_datetime(j.ts_et, utc=True).dt.tz_convert(ET)
        j["day"] = j.ts.dt.date
    return j


def _signals_df() -> pd.DataFrame:
    return pd.DataFrame(_jsonl(LIVE / "signals.log"))


# Research legs: same frozen ZB signal, two instruments. NAIL is the 3x homebuilders ETF.
LEGS = {
    "ITB": {"csv": "f3_trades_canonical.csv", "cost_bp": 2.0, "long_history": "long_history_panel.parquet"},
    "NAIL": {"csv": "f3_trades_canonical_NAIL.csv", "cost_bp": 5.0, "long_history": "long_history_panel_NAIL.parquet"},
}


def _leg(sym: str | None) -> str:
    s = (sym or "ITB").upper()
    return s if s in LEGS else "ITB"


def _backtest_df(sym: str = "ITB") -> pd.DataFrame:
    f = ROOT / "research/zb_itb/verify" / LEGS[_leg(sym)]["csv"]
    if not f.exists():
        return pd.DataFrame()
    b = pd.read_csv(f, parse_dates=["date"]).set_index("date")
    b = b[b.d.notna() & (b.d != 0)]
    b["gross"] = b.g_off.where(b.entry_off.notna(), b.g_h1)
    return b


def _scoreboard(name: str) -> dict:
    f = ROOT / f"reports/forward/{name}_eval.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _env_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            return v.strip().strip('"').strip("'")
    return None


def _accounts_cfg() -> dict:
    return _cfg().get("accounts") or {}


def _broker_meta() -> dict:
    accounts = _accounts_cfg()
    if accounts:
        modes = set()
        for cfg in accounts.values():
            path = ROOT / str(cfg.get("env") or ".env.alpaca")
            modes.add((_env_value(path, "ALPACA_MODE") or "paper").upper())
        mode = "PAPER" if modes == {"PAPER"} else "/".join(sorted(modes))
        return {"broker": "ALPACA", "mode": mode, "label": f"ALPACA · {mode} · {len(accounts)} ACCTS"}
    broker = (ROOT / ".env.broker").read_text().split("=", 1)[1].strip() if (ROOT / ".env.broker").exists() else "alpaca"
    mode = "PAPER"
    if broker.lower() == "ibkr" and (ROOT / ".env.ibkr").exists():
        for line in (ROOT / ".env.ibkr").read_text().splitlines():
            if line.startswith("IBKR_MODE="):
                mode = line.split("=", 1)[1].strip().upper() or "PAPER"
    return {"broker": broker.upper(), "mode": mode, "label": f"{broker.upper()} · {mode}"}


def _account_broker(name: str):
    """Build a read-only Alpaca client for one configured account, without exposing key material."""
    from live.zb_itb.broker import Alpaca, load_env
    cfg = _accounts_cfg()[name]
    env = load_env(ROOT / str(cfg.get("env") or ".env.alpaca"))
    return Alpaca(env)


def _sim_trades(j: pd.DataFrame, name: str) -> list[tuple[str, float]]:
    """(day, net P&L) of simulated trades for one account: sessions the desk missed (e.g. the Mac was off),
    rebuilt from market data and journaled as event=sim_trade. The broker never saw them."""
    if j.empty or "event" not in j.columns or "account" not in j.columns:
        return []
    x = j[(j.event == "sim_trade") & (j.account == name)]
    return [(str(r["day"]), float(r["net_pl"])) for _, r in x.iterrows() if pd.notna(r.get("net_pl"))]


def _sim_offset(j: pd.DataFrame, name: str, day: str, inclusive: bool = True, live: bool = False) -> float:
    """Simulated P&L to add to broker equity. After an account is moved to a new paper account opened at the
    simulated balance (config rebased_on), the new broker equity already holds every sim up to that day, so the
    live account and later days only add sims dated after it; earlier journal rows (old account) keep the old offset."""
    reb = str((_accounts_cfg().get(name) or {}).get("rebased_on") or "")
    after = bool(reb) and (live or day > reb)
    return float(sum(p for d, p in _sim_trades(j, name)
                     if (d <= day if inclusive else d < day) and (not after or d > reb)))


def _account_equity_rows(j: pd.DataFrame, name: str) -> pd.DataFrame:
    if j.empty or "event" not in j.columns:
        return pd.DataFrame()
    eq = j[j.event == "day_end_equity"].copy()
    if eq.empty:
        return eq
    mask = pd.Series(False, index=eq.index)
    if "account" in eq.columns:
        mask = mask | eq["account"].eq(name)
    if name == "ITB":
        # Legacy virtual rows predate account tags and are the ITB $2k account.
        legacy = pd.Series(True, index=eq.index)
        if "account" in eq.columns:
            legacy = legacy & eq["account"].isna()
        if "virtual" in eq.columns:
            legacy = legacy & eq["virtual"].eq(True)
        else:
            legacy = legacy & False
        mask = mask | legacy
    out = eq[mask].copy()
    if out.empty:
        return out
    out = out.sort_values("ts") if "ts" in out.columns else out
    rows = []
    for day, grp in out.groupby("day", sort=True):
        r = grp.iloc[-1]
        if pd.notna(r.get("equity")):
            sim = bool(r.get("simulated")) if pd.notna(r.get("simulated")) else False
            # broker rows don't know about simulated sessions; simulated rows already include them
            adj = 0.0 if sim else _sim_offset(j, name, str(day))
            rows.append({"date": str(day), "equity": round(float(r["equity"]) + adj, 2), "simulated": sim,
                         "trade_pl": (float(r["trade_pl"]) if pd.notna(r.get("trade_pl")) else None),
                         "commission": (float(r["commission"]) if pd.notna(r.get("commission")) else None)})
    return pd.DataFrame(rows)


def _account_curve(j: pd.DataFrame, name: str, equity: float, baseline: float) -> list[dict]:
    rows = _account_equity_rows(j, name)
    today = dt.datetime.now(ET).date()
    if rows.empty:
        start = (pd.Timestamp(today) - pd.offsets.BDay(1)).date()
        curve = [{"date": str(start), "equity": round(baseline, 2)}]
    else:
        first = pd.Timestamp(rows.iloc[0]["date"]).date()
        start = (first - pd.offsets.BDay(1)).date()
        curve = [{"date": str(start), "equity": round(baseline, 2)}]
        # pandas turns missing trade_pl/commission into NaN, which JSON can't carry (500 on 2026-10-22)
        curve += [{k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in r.items()}
                  for r in rows.to_dict("records")]
    # Mark-to-market with the live account, not just the last journal row.
    if curve[-1]["date"] == str(today):
        curve[-1]["equity"] = round(equity, 2)
    else:
        curve.append({"date": str(today), "equity": round(equity, 2)})
    # De-dupe by date, keeping the latest value.
    dedup: dict[str, float] = {}
    for p in curve:
        dedup[p["date"]] = p["equity"]
    return [{"date": d, "equity": v} for d, v in sorted(dedup.items())]


def _account_payload(name: str, j: pd.DataFrame) -> dict:
    cfg = _accounts_cfg().get(name) or {}
    sym = cfg.get("symbol") or _cfg().get("symbol", "ITB")
    baseline = float(cfg.get("start_equity_usd") or 2000)
    try:
        b = _account_broker(name)
        a = b.account()
        positions = b.positions()
        open_orders = b.orders()
        today_s = str(dt.datetime.now(ET).date())
        broker_equity = float(a.get("equity") or baseline)
        sim_pnl = _sim_offset(j, name, today_s, live=True)
        equity = broker_equity + sim_pnl
        last_equity = float(a.get("last_equity") or baseline) + _sim_offset(j, name, today_s, inclusive=False, live=True)
        curve = _account_curve(j, name, equity, baseline)
        rows = _account_equity_rows(j, name)
        today = dt.datetime.now(ET).date()
        day_rows = rows[rows["date"] == str(today)] if not rows.empty else rows
        if not day_rows.empty:
            r = day_rows.iloc[-1]
            # journal day P&L includes the virtual commission estimate, when present
            # simulated sessions carry their own P&L after fees; real sessions use the broker's equity change
            if bool(r.get("simulated")) and pd.notna(r.get("trade_pl")):
                comm = r.get("commission")
                day_pnl = float(r.get("trade_pl")) - (float(comm) if pd.notna(comm) else 0.0)
            else:
                day_pnl = equity - last_equity
        else:
            day_pnl = equity - last_equity
        total_pnl = equity - baseline
        peak = baseline; max_dd = 0.0
        for p in curve:
            peak = max(peak, p["equity"])
            max_dd = min(max_dd, p["equity"] / peak - 1)
        pos = [{"symbol": p.get("symbol"), "qty": p.get("qty"), "side": p.get("side"),
                "avg_entry_price": p.get("avg_entry_price"), "market_value": p.get("market_value"),
                "unrealized_pl": p.get("unrealized_pl")} for p in positions]
        return {
            "ok": True, "name": name, "symbol": sym, "mode": b.mode, "baseline": baseline,
            "equity": round(equity, 2), "last_equity": round(last_equity, 2),
            "broker_equity": round(broker_equity, 2), "simulated_pnl": round(sim_pnl, 2),
            "simulated_days": [d for d, _ in _sim_trades(j, name)],
            "cash": round(float(a.get("cash") or 0), 2), "buying_power": round(float(a.get("buying_power") or 0), 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl / baseline * 100, 3) if baseline else 0.0,
            "day_pnl": round(day_pnl, 2),
            "day_pnl_pct": round(day_pnl / (equity - day_pnl) * 100, 3) if (equity - day_pnl) else 0.0,
            "max_drawdown": round(max_dd, 4), "curve": curve,
            "positions": pos, "open_orders": len(open_orders), "status": a.get("status"),
            "trading_blocked": bool(a.get("trading_blocked")), "shorting_enabled": bool(a.get("shorting_enabled")),
            "account_last4": (str(a.get("account_number"))[-4:] if a.get("account_number") else None),
            "as_of": dt.datetime.now(ET).isoformat(),
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "name": name, "symbol": sym, "baseline": baseline,
                "error": f"{type(e).__name__}: {str(e)[:220]}"}


def _tstat(x: pd.Series) -> float | None:
    x = x.dropna()
    if len(x) < 2 or not x.std():
        return None
    return float(x.mean() / x.std() * np.sqrt(len(x)))


def _risk(net: pd.Series) -> dict:
    """Calendar-filled risk stats (no-trade days = 0) for a daily return series."""
    net = net.dropna()
    if net.empty:
        return {}
    cal = pd.bdate_range(net.index.min(), net.index.max())
    p = net.reindex(cal).fillna(0.0)
    tr = p[p != 0]
    eq = np.exp(p.cumsum())
    yrs = len(p) / 252.0
    maxdd = float((eq / eq.cummax() - 1).min())
    cagr = float(eq.iloc[-1] ** (1 / yrs) - 1) if yrs > 0 else 0.0
    sd = float(p.std())
    down = np.minimum(p.values, 0.0)
    dsd = float(np.sqrt((down ** 2).mean()))
    gains, losses = float(tr[tr > 0].sum()), float(-tr[tr < 0].sum())
    streak = max((len(list(g)) for k, g in groupby(tr < 0) if k), default=0)
    under = eq < eq.cummax()
    longest, cur = 0, 0
    for u in under:
        cur = cur + 1 if u else 0
        longest = max(longest, cur)
    return {
        "n_trades": int(len(tr)),
        "cagr": cagr,
        "vol": sd * math.sqrt(252),
        "sharpe": float(p.mean() / sd * math.sqrt(252)) if sd else 0.0,
        "sortino": float(p.mean() / dsd * math.sqrt(252)) if dsd else 0.0,
        "max_drawdown": maxdd,
        "calmar": float(cagr / abs(maxdd)) if maxdd else 0.0,
        "win_rate": float((tr > 0).mean()) if len(tr) else 0.0,
        "avg_win_bp": float(tr[tr > 0].mean() * 1e4) if (tr > 0).any() else 0.0,
        "avg_loss_bp": float(tr[tr < 0].mean() * 1e4) if (tr < 0).any() else 0.0,
        "profit_factor": float(gains / losses) if losses else 0.0,
        "worst_day_bp": float(tr.min() * 1e4) if len(tr) else 0.0,
        "var95_bp": float(np.quantile(tr, 0.05) * 1e4) if len(tr) else 0.0,
        "loss_streak": int(streak),
        "dd_days": int(longest),
        "final_equity": float(eq.iloc[-1]),
    }


def _slice(net: pd.Series) -> dict:
    return {"n": int(len(net)), "mean_bp": float(net.mean() * 1e4), "t": _tstat(net),
            "hit": float((net > 0).mean()) if len(net) else 0.0}


@lru_cache(maxsize=32)
def _edge_payload(root_s: str, cost_bp: float, sym: str = "ITB") -> dict:
    sym = _leg(sym)
    b = _backtest_df(sym)
    if b.empty:
        return {"ok": True, "empty": True}
    b = b.dropna(subset=["gross"]).copy()
    gross = b.gross
    net = gross - 2 * cost_bp / 1e4
    t = _tstat(net)

    hold = net[net.index >= pd.Timestamp(HOLDOUT_START)]
    costs = [{"bp": c, "mean_bp": float(gross.mean() * 1e4 - 2 * c), "t": _tstat(gross - 2 * c / 1e4)}
             for c in (0, 1, 2, 3, 5, 8, 13)]

    long_n, short_n = net[b.d > 0], net[b.d < 0]
    sides = {"long": {**_slice(long_n), "label": "LONG"}, "short": {**_slice(short_n), "label": "SHORT"}}

    wd = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    weekdays = [{"label": wd[i], **_slice(net[b.index.dayofweek == i])} for i in range(5)]

    mabs = b.m.abs()
    qs = mabs.quantile([0.2, 0.4, 0.6, 0.8]).tolist()
    edges = [0.0] + qs + [1e9]
    quintiles = []
    for i in range(5):
        mask = (mabs > edges[i]) & (mabs <= edges[i + 1])
        quintiles.append({"label": f"Q{i + 1}", "lo": float(edges[i] * 1e2), "hi": float(min(edges[i + 1], 9.99) * 1e2),
                          **_slice(net[mask.reindex(net.index).fillna(False).values])})

    halves = []
    for (y, hf), g in net.groupby([net.index.year, (net.index.month > 6)]):
        halves.append({"label": f"{y}H{1 if not hf else 2}", **_slice(g)})

    exits = [
        {"label": "official daily open", "mean_bp": float(net.mean() * 1e4), "t": t},
        {"label": "hourly bar open", "mean_bp": float((b.g_h1 - 2 * cost_bp / 1e4).mean() * 1e4),
         "t": _tstat(b.g_h1 - 2 * cost_bp / 1e4)},
    ]

    drop = net.sort_values().iloc[:-10] if len(net) > 10 else net
    holdout = {**_slice(hold), "start": HOLDOUT_START}

    eras = []
    p = ROOT / "research/zb_itb/verify" / LEGS[sym]["long_history"]
    if p.exists() and sym == "NAIL":
        # TLT pre-market proxy signal x NAIL 09:30->10:29 (Alpaca SIP), live regime switch applied, 5 bp/side.
        lh = pd.read_parquet(p)
        tr = (lh.d * lh.ret - 2 * LEGS["NAIL"]["cost_bp"] / 1e4)[lh.regime_corr > 0].dropna()
        for a, z in [(2017, 2019), (2020, 2023), (2024, 2026)]:
            x = tr[(tr.index >= str(a)) & (tr.index <= f"{z}-12-31")]
            eras.append({"label": f"{a}–{z}", **_slice(x)})
        eras_all = {"label": "ALL", **_slice(tr)}
        eras_note = "TLT pre-market proxy · NAIL 09:30→10:29 · regime switch on · 5 bp/side"
    elif p.exists():
        lh = pd.read_parquet(p)
        tr = (lh.gap * lh.b935_1030 - 2 * 3 / 1e4).dropna()
        for a, z in [(2010, 2014), (2015, 2019), (2020, 2023), (2024, 2026)]:
            x = tr[(tr.index >= str(a)) & (tr.index <= f"{z}-12-31")]
            eras.append({"label": f"{a}–{z}", **_slice(x)})
        eras_all = {"label": "ALL", **_slice(tr)}
        eras_note = "long-history panel · ITB 09:35→10:30 · 3 bp/side · no regime switch"
    else:
        eras_all, eras_note = {}, ""

    return {
        "ok": True, "empty": False, "cost_bp": cost_bp, "sym": sym,
        "n": int(len(net)), "start": str(net.index[0].date()), "end": str(net.index[-1].date()),
        "mean_bp": float(net.mean() * 1e4), "median_bp": float(net.median() * 1e4),
        "t": t, "hit": float((net > 0).mean()),
        "holdout": holdout,
        "costs": costs,
        "sides": sides,
        "weekdays": weekdays,
        "quintiles": quintiles,
        "halves": halves,
        "exits": exits,
        "drop10": {**_slice(drop), "removed_bp": float(net.sum() * 1e4 - drop.sum() * 1e4)},
        "eras": eras, "eras_all": eras_all, "eras_note": eras_note,
        "risk": {"all": _risk(net), "long_only": _risk(net.where(b.d > 0, 0.0))},
    }


@lru_cache(maxsize=4)
def _mc_payload(root_s: str, n_paths: int = 6000, sym: str = "ITB") -> dict:
    sym = _leg(sym)
    b = _backtest_df(sym).dropna(subset=["gross"])
    if b.empty:
        return {"ok": True, "empty": True}
    x = (b.gross - 2 * LEGS[sym]["cost_bp"] / 1e4).values
    rows = []
    for keep, label in [(1.0, "full edge"), (0.5, "half edge"), (0.25, "quarter edge"), (0.0, "no edge")]:
        rng = np.random.default_rng(7)
        y = x - x.mean() * (1 - keep)
        nb = 252 // 10
        starts = rng.integers(0, len(y), (n_paths, nb))
        idx = (starts[:, :, None] + np.arange(10)[None, None, :]).reshape(n_paths, nb * 10) % len(y)
        eq = np.exp(np.cumsum(y[idx], axis=1))
        dd = (eq / np.maximum.accumulate(eq, axis=1) - 1).min(axis=1)
        r = eq[:, -1] - 1
        rows.append({"label": label, "keep": keep, "median": float(np.median(r)),
                     "p5": float(np.quantile(r, 0.05)), "p95": float(np.quantile(r, 0.95)),
                     "p_loss": float(np.mean(r < 0)), "median_dd": float(np.median(dd)),
                     "p5_dd": float(np.quantile(dd, 0.05))})
    return {"ok": True, "sym": sym, "n_paths": n_paths, "horizon_days": 252, "rows": rows}


def _registry_spec(strategy_id: str) -> dict | None:
    recs = _jsonl(ROOT / "reports/forward/registry.jsonl")
    mine = [r for r in recs if r.get("strategy_id") == strategy_id and r.get("kind") == "spec_registration"]
    return mine[-1] if mine else None


def _forward_payload() -> dict:
    out = []
    for sid, name, label, cost in [
        ("zb_itb_v1", "zb_itb", "ITB · 09:30→10:30", 2),
        ("zb_rkt_v1", "zb_rkt", "RKT · 09:30→10:30", 5),
    ]:
        reg = _registry_spec(sid)
        ev = _scoreboard(name)
        summary = ev.get("summary", {})
        n = int(summary.get("n", 0) or 0)
        spec = (reg or {}).get("payload", {}).get("spec", {})
        gate = spec.get("gate", {})
        final_n = int(gate.get("final_n", 250) or 250)
        trades = ev.get("trades", [])
        key = f"net_{cost}bp"
        xs = [t[key] * 1e4 for t in trades if key in t]
        cum = float(summary.get(f"cum_net_{cost}bp_pct", 0.0) or 0.0)
        verdict = "collecting"
        if n:
            if summary.get("kill"):
                verdict = "killed"
            elif n >= final_n:
                verdict = "passed" if summary.get("gate") == "PASS" else "failed"
        out.append({
            "id": sid, "name": name, "label": label, "cost_bp": cost,
            "registered": bool(reg), "seq": (reg or {}).get("seq"),
            "registered_at": (reg or {}).get("recorded_at_utc"),
            "spec_hash": (reg or {}).get("spec_hash"),
            "rule": spec.get("rule"), "gate": gate,
            "n": n, "final_n": final_n, "progress": min(n / final_n, 1.0) if final_n else 0.0,
            "cum_net_pct": cum, "t": summary.get("t"), "hit": summary.get("hit"),
            "mean_bp": summary.get("gross_mean_bp"),
            "verdict": verdict,
            "first_decision": "2026-10-19" if sid == "zb_itb_v1" else None,
        })
    out.append(_nail_forward())
    return {"ok": True, "strategies": out}


def _nail_forward() -> dict:
    """NAIL has no registered spec of its own: its forward record is the live NAIL paper account,
    judged against the zb_itb_v1 gate. Trades and P&L come from the journal only."""
    j = _journal_df()
    n, cum = 0, 0.0
    if not j.empty and "account" in j.columns:
        fills = j[(j.event == "entry_filled") & (j.account == "NAIL")]
        n = int(fills.day.nunique()) if not fills.empty else 0
        rows = _account_equity_rows(j, "NAIL")
        if not rows.empty:
            base = float((_accounts_cfg().get("NAIL") or {}).get("start_equity_usd") or 2000)
            cum = (float(rows.iloc[-1]["equity"]) / base - 1) * 100
    final_n = 250
    return {
        "id": "nail_live", "name": "zb_nail", "label": "NAIL (3×) · 09:30→10:30 · live paper", "cost_bp": 5,
        "kind": "live", "registered": True, "seq": None, "registered_at": None, "spec_hash": None,
        "rule": "same frozen ZB signal as zb_itb_v1, traded in NAIL",
        "gate": {"pass": "judged with the zb_itb_v1 gate: n 250, gross t >= 1.65, net mean > 0",
                 "kill": "account drawdown >= 15% (trader kill switch)"},
        "n": n, "final_n": final_n, "progress": min(n / final_n, 1.0),
        "cum_net_pct": cum, "t": None, "hit": None, "mean_bp": None,
        "verdict": "collecting", "first_decision": "2026-10-20" if n == 0 else None,
    }



# ---------------------------------------------------------------- ITB vs NAIL (same ZB signal) --------------------
_NAIL_CACHE: dict = {}


def _bars_60m(sym: str) -> pd.DataFrame:
    """Frozen research cache + fresh yfinance 60m (refreshed at most every 30 min), ET index, de-duplicated."""
    cache = ROOT / "research/zb_itb/verify/yf_cache" / f"{sym.replace('=', '_')}_60m.parquet"
    frames = []
    if cache.exists():
        frames.append(pd.read_parquet(cache))
    key = ("fresh", sym)
    hit = _NAIL_CACHE.get(key)
    if not hit or (dt.datetime.now() - hit[0]).total_seconds() > 1800:
        try:
            import yfinance as yf
            f = yf.download(sym, period="60d", interval="60m", auto_adjust=False, progress=False)
            f.columns = f.columns.get_level_values(0)
            _NAIL_CACHE[key] = (dt.datetime.now(), f)
        except Exception:
            _NAIL_CACHE[key] = (dt.datetime.now(), pd.DataFrame())
    if not _NAIL_CACHE[key][1].empty:
        frames.append(_NAIL_CACHE[key][1])
    d = pd.concat(frames)
    d.index = pd.DatetimeIndex(d.index).tz_convert(ET)
    return d[~d.index.duplicated(keep="last")].sort_index()


def _first_hour(zb: pd.DataFrame, etf: pd.DataFrame) -> pd.DataFrame:
    """Frozen rule: d = sign(ZB close of bar starting 08:00 / bar starting 15:00 prev session); return = ETF 09:30 bar close/open."""
    first = etf[etf.index.time == dt.time(9, 30)]
    days = list(first.index.normalize()); rows = []
    for i in range(1, len(days)):
        D, prev = days[i], days[i - 1]
        t0, t1 = prev + pd.Timedelta(hours=15), D + pd.Timedelta(hours=8)
        if t0 not in zb.index or t1 not in zb.index:
            continue
        m = float(np.log(zb.loc[t1, "Close"] / zb.loc[t0, "Close"]))
        b = first.iloc[i]
        rows.append({"date": D.date().isoformat(), "m_bp": m * 1e4, "d": int(np.sign(m)), "r": float(np.log(b["Close"] / b["Open"]))})
    return pd.DataFrame(rows)


def _nail_payload(view: str, start_cap: float) -> dict:
    zb = _bars_60m("ZB=F")
    legs = {"ITB": (_first_hour(zb, _bars_60m("ITB")), 2.0), "NAIL": (_first_hour(zb, _bars_60m("NAIL")), 5.0)}
    out, daily = {}, None
    for name, (t, cost) in legs.items():
        t = t[t.d != 0].copy()
        if view == "long-only":
            t.loc[t.d < 0, "d"] = 0
        t["net"] = np.where(t.d != 0, t.d * t.r - 2 * cost / 1e4, 0.0)
        eq = start_cap * np.exp(t.net.cumsum())
        trd = t.net[t.d != 0]
        yrs = max((pd.Timestamp(t.date.iloc[-1]) - pd.Timestamp(t.date.iloc[0])).days / 365.25, 1e-9)
        out[name] = {
            "cost_bp_side": cost, "n_trades": int(len(trd)), "avg_bp": float(trd.mean() * 1e4), "win": float((trd > 0).mean()),
            "avg_win_bp": float(trd[trd > 0].mean() * 1e4), "avg_loss_bp": float(trd[trd < 0].mean() * 1e4),
            "cagr": float((eq.iloc[-1] / start_cap) ** (1 / yrs) - 1), "sharpe": float(t.net.mean() / t.net.std() * np.sqrt(252)),
            "max_drawdown": float((eq / eq.cummax() - 1).min()), "worst_day": float(trd.min()), "final_equity": float(eq.iloc[-1]),
            "curve": [{"date": a, "equity": round(float(b), 2)} for a, b in zip(t.date, eq)],
        }
        cols = t[["date", "m_bp", "d"]].copy(); cols[name + "_pct"] = np.where(t.d != 0, t.d * t.r, 0.0) * 100
        cols[name + "_usd"] = (np.exp(t.net) - 1) * start_cap
        daily = cols if daily is None else daily.merge(cols[["date", name + "_pct", name + "_usd"]], on="date", how="outer")
    daily = daily.sort_values("date", ascending=False).head(60)
    return {"ok": True, "view": view, "start_cap": start_cap, "legs": out,
            "daily": [{k: (None if (isinstance(v, float) and np.isnan(v)) else (round(v, 3) if isinstance(v, float) else v)) for k, v in r.items()} for r in daily.to_dict("records")],
            "last_date": out["ITB"]["curve"][-1]["date"] if out["ITB"]["curve"] else None}


def create_app(root: Path | None = None) -> FastAPI:
    global ROOT, LIVE
    if root is not None:
        ROOT = Path(root)
        LIVE = ROOT / "live" / "zb_itb"

    app = FastAPI(title="ZB -> ITB Desk")

    @app.middleware("http")
    async def _no_cache_static(request, call_next):   # no-cache-static: always revalidate, so UI edits show on reload
        resp = await call_next(request)
        if not request.url.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-cache"
        return resp
    static_dir = Path(__file__).resolve().parent / "static"

    @app.get("/api/health")
    def health():
        return {"ok": True, "root": str(ROOT), "now_et": dt.datetime.now(ET).isoformat()}

    @app.get("/api/config")
    def config():
        try:
            return {"ok": True, "config": _cfg(), **_broker_meta()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    _regime_cache: dict = {}

    @app.get("/api/regime")
    def regime():
        """Regime switch: past-only 60d corr(ITB, TLT). The trader skips when corr <= regime_min_corr. Cached 1h."""
        try:
            d = dt.datetime.now(ET).date()
            hit = _regime_cache.get("v")
            if not hit or hit[0] != d or (dt.datetime.now() - hit[2]).total_seconds() > 3600:
                from live.zb_itb.trader import regime_corr
                _regime_cache["v"] = (d, regime_corr(d, False), dt.datetime.now())
            cfg = _cfg(); rc = _regime_cache["v"][1]; thr = cfg.get("regime_min_corr", 0.0)
            return {"ok": True, "enabled": bool(cfg.get("regime_filter", False)), "corr": rc, "threshold": thr,
                    "window_days": cfg.get("regime_window_days", 60), "on": (rc is not None and rc > thr)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.get("/api/nail")
    def nail(view: str = "long+short", start_cap: float = 2000.0):
        try:
            return _nail_payload("long-only" if view.lower().startswith("long-o") else "all", float(start_cap))
        except Exception as e:
            return {"ok": False, "error": str(e)[:300]}

    _accounts_cache: dict = {"ts": 0.0, "payload": None}

    @app.get("/api/accounts")
    def accounts(refresh: bool = False):
        """Live ITB + NAIL paper accounts, each read with its own key file. Cached 10s to spare the broker API."""
        cfg = _accounts_cfg()
        if not cfg:
            return {"ok": False, "error": "no accounts configured"}
        now = time.time()
        if not refresh and _accounts_cache["payload"] and now - _accounts_cache["ts"] < 10:
            return _accounts_cache["payload"]
        try:
            j = _journal_df()
            out = {name: _account_payload(name, j) for name in cfg}
            dates = sorted({p["date"] for a in out.values() if a.get("ok") for p in a.get("curve", [])})
            daily = []
            for d in dates[-60:]:
                row = {"date": d}
                for name, a in out.items():
                    if not a.get("ok"):
                        continue
                    hit = next((p for p in a.get("curve", []) if p["date"] == d), None)
                    if hit:
                        row[name] = hit["equity"]
                        row[name + "_pnl"] = round(hit["equity"] - a["baseline"], 2)
                        row[name + "_pct"] = round((hit["equity"] / a["baseline"] - 1) * 100, 3) if a["baseline"] else 0.0
                daily.append(row)
            payload = {"ok": any(a.get("ok") for a in out.values()), "accounts": out,
                       "daily": daily, "last_date": dates[-1] if dates else None,
                       "broker": _broker_meta(), "fetched_et": dt.datetime.now(ET).isoformat()}
            _accounts_cache.update(ts=now, payload=payload)
            return payload
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}

    @app.get("/api/now")
    def now():
        try:
            from research.forward import nyse
            d = dt.datetime.now(ET).date()
            open_today = bool(nyse.is_session(d))
            nxt = nyse.next_session(d).isoformat() if not open_today else None
            return {"ok": True, "now_et": dt.datetime.now(ET).isoformat(),
                    "date": d.isoformat(), "weekday": d.strftime("%a"),
                    "market_open_today": open_today, "next_session": nxt}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.get("/api/journal")
    def journal(limit: int = 500):
        try:
            j = _journal_df()
            if j.empty:
                return {"ok": True, "rows": []}
            keep_cols = [c for c in j.columns if c not in ("ts", "day")]
            rows = []
            for _, r in j.tail(limit).iterrows():
                rec = {k: (v.isoformat() if hasattr(v, "isoformat") else (None if (isinstance(v, float) and math.isnan(v)) else v))
                       for k, v in r[keep_cols].items() if pd.notna(v) or v is None}
                rec["ts_et"] = r["ts"].isoformat() if "ts" in j.columns else None
                rec["day"] = str(r["day"]) if "day" in j.columns else None
                rows.append(rec)
            return {"ok": True, "rows": rows[::-1]}
        except Exception as e:
            return {"ok": True, "rows": [], "error": str(e)}

    @app.get("/api/signals")
    def signals(limit: int = 500):
        try:
            s = _signals_df()
            if s.empty:
                return {"ok": True, "rows": []}
            rows = s.tail(limit).to_dict(orient="records")
            return {"ok": True, "rows": rows[::-1]}
        except Exception as e:
            return {"ok": True, "rows": [], "error": str(e)}

    @app.get("/api/equity")
    def equity():
        try:
            j = _journal_df()
            if j.empty or "event" not in j.columns:
                return {"ok": True, "rows": []}
            eq = j[j.event == "day_end_equity"].copy()
            if "account" in eq.columns:
                itb = eq[eq["account"].eq("ITB")]
                legacy = pd.Series(True, index=eq.index)
                legacy = legacy & eq["account"].isna()
                if "virtual" in eq.columns:
                    legacy = legacy & eq["virtual"].fillna(False).astype(bool)
                else:
                    legacy = legacy & False
                eq = pd.concat([itb, eq[legacy]]).drop_duplicates()
            elif "virtual" in eq.columns and eq["virtual"].eq(True).any():   # legacy single account
                eq = eq[eq["virtual"].eq(True)]
            if "ts" in eq.columns:
                eq = eq.sort_values("ts")
            def _adj(r):
                if "simulated" in eq.columns and r.get("simulated") == True:  # noqa: E712 (NaN-safe)
                    return 0.0
                return _sim_offset(j, "ITB", str(r["day"]))
            rows = [{"ts_et": r["ts"].isoformat(), "day": str(r["day"]), "simulated": bool(r.get("simulated") == True),  # noqa: E712
                     "equity": float(r["equity"]) + _adj(r)} for _, r in eq.iterrows() if pd.notna(r.get("equity"))]
            return {"ok": True, "rows": rows}
        except Exception as e:
            return {"ok": True, "rows": [], "error": str(e)}

    @app.get("/api/scoreboard")
    def scoreboard(name: str = "zb_itb"):
        try:
            sb = _scoreboard(name)
            trades = sb.get("trades", [])
            key = "net_2bp" if name == "zb_itb" else "net_5bp"
            xs = [t[key] * 1e4 for t in trades if key in t]
            mu = 22.4 if name == "zb_itb" else 45.3
            sd = 110.0 if name == "zb_itb" else 230.0
            llr = None
            verdict = "collecting trades"
            if len(xs) >= 2:
                llr = float(((mu / 2) * sum(xs) - (mu / 2) ** 2 * len(xs) / 2) / sd ** 2)
                A_ = math.log(19)
                verdict = ("edge confirmed" if llr >= A_ else "edge gone" if llr <= -A_ else "still deciding")
            return {"ok": True, "name": name, "n_trades": len(xs),
                    "avg_bp": (sum(xs) / len(xs) if xs else None),
                    "cum_bp": (sum(xs) if xs else None),
                    "llr": llr, "verdict": verdict,
                    "label": "ITB forward test" if name == "zb_itb" else "RKT forward test"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.get("/api/signal")
    def signal(date: str | None = None):
        try:
            if date is None:
                d = dt.datetime.now(ET).date()
            else:
                d = dt.date.fromisoformat(date)
            from research.zb_itb.forward import signal as sigfn
            s = sigfn(d)
            return {"ok": True, "date": d.isoformat(), "signal": s}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.get("/api/backtest")
    def backtest(cost_bp: float = 2.0, view: str = "Long-only", start_cap: float = 1000.0, sym: str = "ITB"):
        try:
            b = _backtest_df(sym)
            if b.empty:
                return {"ok": True, "empty": True}
            net = b.gross - 2 * cost_bp / 1e4
            if view == "Long-only":
                net = net.where(b.d > 0, 0.0)
            eq = start_cap * np.exp(net.cumsum())
            yrs = (eq.index[-1] - eq.index[0]).days / 365.25
            cagr = float((eq.iloc[-1] / start_cap) ** (1 / yrs) - 1) if yrs > 0 else 0.0
            dd = float((eq / eq.cummax() - 1).min())
            trd = net[net != 0]
            win = float((trd > 0).mean()) if len(trd) else 0.0
            avg_win = float(trd[trd > 0].mean() * 1e4) if (trd > 0).any() else 0.0
            avg_loss = float(trd[trd < 0].mean() * 1e4) if (trd < 0).any() else 0.0
            sharpe = float(net.mean() / net.std() * np.sqrt(252)) if net.std() else 0.0
            curve = [{"date": str(idx.date()) if hasattr(idx, "date") else str(idx),
                      "equity": float(v)} for idx, v in eq.items()]
            mo = net.groupby(net.index.to_period("M")).sum() * 100
            monthly = [{"month": p.strftime("%b %y"), "pct": float(v)} for p, v in mo.items()]
            sel = b.gross[b.d > 0] if view == "Long-only" else b.gross
            return {"ok": True, "empty": False, "view": view, "cost_bp": cost_bp, "sym": _leg(sym),
                    "cagr": cagr, "sharpe": sharpe, "win_rate": win,
                    "max_drawdown": dd, "avg_win_bp": avg_win, "avg_loss_bp": avg_loss,
                    "final_equity": float(eq.iloc[-1]), "n_trades": int((net != 0).sum()),
                    "start": str(eq.index[0].date()) if hasattr(eq.index[0], "date") else str(eq.index[0]),
                    "end": str(eq.index[-1].date()) if hasattr(eq.index[-1], "date") else str(eq.index[-1]),
                    "curve": curve, "monthly": monthly,
                    "per_trade_bp": float((sel.mean() * 1e4) - 2 * cost_bp)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.get("/api/edge")
    def edge(cost_bp: float = 2.0, sym: str = "ITB"):
        try:
            return _edge_payload(str(ROOT), float(cost_bp), _leg(sym))
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.get("/api/forward")
    def forward():
        try:
            return _forward_payload()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.get("/api/background")
    def background():
        """The model's working memory: thesis, today's trace, evidence and open risks.

        Everything here is derived from the live signal, the canonical panel,
        the registered forward spec and the journal. No invented P&L.
        """
        try:
            from research.zb_itb.forward import signal as sigfn

            now = dt.datetime.now(ET)
            d = now.date()
            sig = sigfn(d)
            edge = _edge_payload(str(ROOT), 2.0)
            edge_n = _edge_payload(str(ROOT), 5.0, "NAIL")
            fwd = _forward_payload()
            cfg = _cfg()
            reg = _registry_spec("zb_itb_v1") or {}
            spec = ((reg.get("payload") or {}).get("spec") or {})
            gate = spec.get("gate") or {}

            p0 = sig.get("zb_p0_prev1600")
            p1 = sig.get("zb_p1_0900")
            dsig = int(sig.get("d") or 0)
            move_bp = (math.log(float(p1) / float(p0)) * 1e4) if (p0 and p1) else None
            tnow = now.time()

            def fnum(v, default=0.0):
                try:
                    return float(v)
                except Exception:
                    return default

            def fmt_bp(v):
                try:
                    return f"{float(v):+.1f} bp"
                except Exception:
                    return "—"

            # ── today's state ─────────────────────────────────────────────
            if p1 is None:
                phase = "awaiting"
                headline = "Waiting for the 09:00 print"
                detail = (f"The overnight ZB tape is the only new information. "
                          f"Prev 16:00 print {float(p0):.4f}. No position; no reason to guess before 09:00."
                          if p0 else "No prior ZB close. The model stands down until the 09:00 print.")
            elif dsig > 0:
                phase = "long"
                headline = "Long ITB + NAIL at the open"
                detail = (f"ZB printed {float(p1):.4f}, {fmt_bp(move_bp)} vs the prior 16:00 close. "
                          f"d = +1. Both paper accounts buy at 09:30 (ITB, and NAIL at 3×) and exit at 10:30.")
            elif dsig < 0:
                phase = "short"
                headline = "Short ITB + NAIL at the open"
                detail = (f"ZB printed {float(p1):.4f}, {fmt_bp(move_bp)} vs the prior 16:00 close. "
                          f"d = -1. Both paper accounts short at 09:30 and exit at 10:30, each "
                          f"subject to the ${fnum(cfg.get('short_min_equity_usd'), 2000):,.0f} equity floor.")
            else:
                phase = "flat"
                headline = "No trade"
                detail = "The log move is zero. d = 0 and the desk stays flat."

            if tnow >= dt.time(10, 30):
                session_state = "window closed"
                position = "flat"
            elif tnow >= dt.time(9, 30):
                session_state = "in window"
                position = ("long" if dsig > 0 else "short" if dsig < 0 else "flat")
            elif tnow >= dt.time(9, 15):
                session_state = "signal ready"
                position = "pending"
            elif tnow >= dt.time(9, 0):
                session_state = "computing"
                position = "flat"
            else:
                session_state = "pre-open"
                position = "flat"

            # ── trace ─────────────────────────────────────────────────────
            observe = ("Read the ZB 09:00 print. Compute m = 10^4 * ln(p1 / p0)."
                       if p1 is None else
                       f"ZB printed {float(p1):.4f}; m = {fmt_bp(move_bp)} vs {float(p0):.4f}.")
            decide = ("d = sign(m). Long ITB and NAIL if d = +1; short if d = -1 and equity >= "
                      f"${fnum(cfg.get('short_min_equity_usd'), 2000):,.0f}; flat if m = 0."
                      if p1 is None else
                      f"d = {dsig:+d}. " +
                      ("Long ITB + NAIL at the open." if dsig > 0 else
                       "Short ITB + NAIL at the open." if dsig < 0 else "Flat; no trade.") +
                      " The regime switch must be on (60d ITB/TLT corr > 0).")
            steps = [
                ("04:00", "WAIT", "The overnight ZB tape is the only new information. "
                                  "No position; no reason to guess before 09:00."),
                ("09:00", "OBSERVE", observe),
                ("09:15", "DECIDE", decide),
                ("09:30", "ENTER", f"Market-on-open at 09:30 (deadline 09:27) in both accounts: ITB and NAIL, "
                                   f"$2,000 each. Notional <= ${fnum(cfg.get('max_notional_usd'), 25000):,.0f}, "
                                   f"{fnum(cfg.get('protective_stop_pct'), 3):.1f}% protective stop."),
                ("10:30", "EXIT", "Flatten. The claim is a two-hour drift, not a rates view."),
                ("15:50", "FAILSAFE", "If anything is still open at 15:50, force flat."),
            ]
            bounds = [dt.time(4, 0), dt.time(9, 0), dt.time(9, 15),
                      dt.time(9, 30), dt.time(10, 30), dt.time(15, 50)]
            active = 0
            for i, b in enumerate(bounds):
                if tnow >= b:
                    active = i
            stream = []
            for i, (t, tag, text) in enumerate(steps):
                state = "done" if i < active else ("now" if i == active else "next")
                stream.append({"t": t, "tag": tag, "text": text, "state": state})
            upcoming = next((x for x in stream if x["state"] == "next"), None)
            next_label = (upcoming["t"] + " " + upcoming["tag"]) if upcoming else "session complete"

            # ── journal actions ───────────────────────────────────────────
            actions = []
            try:
                j = _journal_df()
                if not j.empty:
                    for _, r in j.tail(8).iterrows():
                        ev = str(r.get("event") or "event")
                        reason = (r.get("reason") or r.get("error") or r.get("note") or "")
                        if ev == "broker_fallback":
                            text = (f"Broker link fell back to {r.get('to_broker', 'alpaca-paper')}; "
                                    f"{r.get('from_broker', 'ibkr')} was unreachable. No order was sent.")
                        elif ev == "sim_trade":
                            text = (f"SIMULATED (Mac was off, no order sent): long {int(fnum(r.get('qty')))} {r.get('symbol')} "
                                    f"@ {fnum(r.get('entry_price')):.2f} open, out @ {fnum(r.get('exit_price')):.2f} at 10:30, "
                                    f"net ${fnum(r.get('net_pl')):+,.2f} after ${fnum(r.get('fees')):.2f} fees.")
                        elif ev == "day_end_equity":
                            text = (f"Marked end-of-day equity at ${fnum(r.get('equity')):,.2f}"
                                    + (" (simulated)." if r.get("simulated") == True else "."))  # noqa: E712
                        elif ev in ("enter", "entry", "fill", "exit"):
                            text = str(reason) if reason else "Execution event recorded."
                        else:
                            text = str(reason) if reason else "Event recorded."
                        acct_tag = r.get("account") if "account" in j.columns else None
                        if isinstance(acct_tag, str) and acct_tag:
                            text = f"[{acct_tag}] " + text
                        actions.append({
                            "t": (r["ts"].strftime("%H:%M") if "ts" in j.columns and pd.notna(r.get("ts")) else "—"),
                            "event": ev,
                            "text": text[:420],
                            "raw": {k: (v.isoformat() if hasattr(v, "isoformat") else
                                        (None if (isinstance(v, float) and math.isnan(v)) else v))
                                    for k, v in r.items() if pd.notna(v)},
                        })
                    actions = actions[::-1]
            except Exception:
                actions = []

            # ── evidence ledger ───────────────────────────────────────────
            hold = edge.get("holdout") or {}
            costs = {int(c.get("bp", -1)): c for c in (edge.get("costs") or [])}
            c8, c13 = costs.get(8, {}), costs.get(13, {})
            drop = edge.get("drop10") or {}
            eras_all = edge.get("eras_all") or {}
            halves = {e.get("label"): e for e in (edge.get("halves") or [])}
            itb = next((s for s in (fwd.get("strategies") or []) if s.get("name") == "zb_itb"), {})
            nail_f = next((s for s in (fwd.get("strategies") or []) if s.get("name") == "zb_nail"), {})
            n_risk = (edge_n.get("risk") or {}).get("all") or {}
            n_eras = edge_n.get("eras_all") or {}
            n_hold = edge_n.get("holdout") or {}
            f_n, f_final = int(itb.get("n") or 0), int(itb.get("final_n") or 250)

            def grade(t, mean):
                if mean is None:
                    return "info"
                if float(mean) <= 0:
                    return "fail"
                if t is not None and float(t) >= 2:
                    return "pass"
                return "warn"

            evidence = [
                {"label": "full sample", "value": fmt_bp(edge.get("mean_bp")),
                 "note": f"t {fnum(edge.get('t')):.2f} · n {int(edge.get('n') or 0)}",
                 "grade": grade(edge.get("t"), edge.get("mean_bp"))},
                {"label": "holdout", "value": fmt_bp(hold.get("mean_bp")),
                 "note": f"t {fnum(hold.get('t')):.2f} · n {int(hold.get('n') or 0)} · since {hold.get('start', '—')}",
                 "grade": grade(hold.get("t"), hold.get("mean_bp"))},
                {"label": "drop 10 best", "value": fmt_bp(drop.get("mean_bp")),
                 "note": f"t {fnum(drop.get('t')):.2f} · n {int(drop.get('n') or 0)}",
                 "grade": grade(drop.get("t"), drop.get("mean_bp"))},
                {"label": "13 bp / side", "value": fmt_bp(c13.get("mean_bp")),
                 "note": f"t {fnum(c13.get('t')):.2f} · cost stress · edge gone",
                 "grade": "fail"},
                {"label": "long history", "value": fmt_bp(eras_all.get("mean_bp")),
                 "note": f"t {fnum(eras_all.get('t')):.2f} · n {int(eras_all.get('n') or 0)} · 3 bp",
                 "grade": grade(eras_all.get("t"), eras_all.get("mean_bp"))},
                {"label": "forward test", "value": f"{f_n} / {f_final}",
                 "note": "first decision today" if f_n == 0 else itb.get("verdict", "collecting"),
                 "grade": "pending"},
                {"label": "NAIL full sample", "value": fmt_bp(edge_n.get("mean_bp")),
                 "note": f"t {fnum(edge_n.get('t')):.2f} · n {int(edge_n.get('n') or 0)} · 5 bp/side",
                 "grade": grade(edge_n.get("t"), edge_n.get("mean_bp"))},
                {"label": "NAIL holdout", "value": fmt_bp(n_hold.get("mean_bp")),
                 "note": f"t {fnum(n_hold.get('t')):.2f} · n {int(n_hold.get('n') or 0)}",
                 "grade": grade(n_hold.get("t"), n_hold.get("mean_bp"))},
                {"label": "NAIL 2017–26", "value": fmt_bp(n_eras.get("mean_bp")),
                 "note": f"t {fnum(n_eras.get('t')):.2f} · n {int(n_eras.get('n') or 0)} · TLT proxy, switch on",
                 "grade": grade(n_eras.get("t"), n_eras.get("mean_bp"))},
                {"label": "NAIL forward", "value": f"{int(nail_f.get('n') or 0)} / {int(nail_f.get('final_n') or 250)}",
                 "note": "live paper account · " + ("first decision today" if not nail_f.get("n") else "collecting"),
                 "grade": "pending"},
            ]

            # ── risks / questions ─────────────────────────────────────────
            h1 = halves.get("2024H1") or {}
            risks = [
                {"title": "Long-history replication fails",
                 "text": (f"2010–2019 is negative at 3 bp/side; the all-history mean is "
                          f"{fmt_bp(eras_all.get('mean_bp'))} (t {fnum(eras_all.get('t')):.2f}). "
                          f"This may be a modern rates regime, not a structural edge."),
                 "grade": "fail"},
                {"title": "Out-of-sample evidence is thin",
                 "text": (f"Holdout since {hold.get('start', '—')}: {fmt_bp(hold.get('mean_bp'))}, "
                          f"t {fnum(hold.get('t')):.2f}, n {int(hold.get('n') or 0)}. "
                          f"Directionally positive, not statistically decisive."),
                 "grade": "warn"},
                {"title": "Costs erase the edge",
                 "text": (f"At 13 bp/side the mean is {fmt_bp(c13.get('mean_bp'))} "
                          f"(t {fnum(c13.get('t')):.2f}); at 8 bp it is {fmt_bp(c8.get('mean_bp'))}. "
                          f"The edge is economically gone at the high end of the cost range."),
                 "grade": "fail"},
                {"title": "The early live regime was hostile",
                 "text": (f"2024H1: {fmt_bp(h1.get('mean_bp'))}, t {fnum(h1.get('t')):.2f}, "
                          f"n {int(h1.get('n') or 0)}. The model survived, but the first half-year was not smooth."),
                 "grade": "warn"},
                {"title": "Data dependency",
                 "text": "The signal needs the 09:00 ZB print. If it is missing or stale, d = 0 and the desk stands down.",
                 "grade": "info"},
                {"title": "Short leg execution",
                 "text": (f"{int((edge.get('sides') or {}).get('short', {}).get('n') or 0)} of "
                          f"{int(edge.get('n') or 0)} canonical trades are short. Borrow availability and live "
                          f"short fills are not modeled at 2 bp/side."),
                 "grade": "warn"},
                {"title": "NAIL is 3× leverage on the same bet",
                 "text": (f"NAIL nets {fmt_bp(edge_n.get('mean_bp'))}/trade at 5 bp/side, Sharpe "
                          f"{fnum(n_risk.get('sharpe')):.2f}, but its max drawdown is {fnum(n_risk.get('max_drawdown')) * 100:.0f}% "
                          f"(worst day {fnum(n_risk.get('worst_day_bp')):.0f} bp). Without the regime switch, 2020–23 drew down −73%. "
                          f"It is the same signal, not diversification."),
                 "grade": "warn"},
                {"title": "NAIL fills are wider",
                 "text": "NAIL trades thinner than ITB; the desk charges 5 bp/side and a 3% gap cushion on sizing. "
                         "If live slippage runs above ~15 bp/side the NAIL edge is mostly gone.",
                 "grade": "warn"},
                {"title": "One factor, one window",
                 "text": "One signal, two ETFs on the same sector, one two-hour holding period. ITB and NAIL move together; "
                         "there is no diversification between the accounts.",
                 "grade": "info"},
            ]
            questions = [
                "Why is 2010–2019 negative? Is the post-2024 edge a rates-regime artifact?",
                "Does the live OPG fill match the official open used in the canonical panel?",
                "Can the short leg be borrowed at a cost close to the 2 bp assumption?",
                "Does the forward sample hold above +10 bp after 250 trades?",
                "Should the long-history panel use 2 bp or 3 bp? The conclusion is cost-sensitive.",
                "Does NAIL's live slippage stay near 5 bp/side, so its 3× leverage keeps roughly 3× the ITB edge?",
            ]

            constraints = [
                {"k": "max notional", "v": f"${fnum(cfg.get('max_notional_usd'), 25000):,.0f}"},
                {"k": "max fraction", "v": f"{fnum(cfg.get('max_fraction_of_equity'), 1.0) * 100:.0f}% of equity"},
                {"k": "protective stop", "v": f"{fnum(cfg.get('protective_stop_pct'), 3):.1f}%"},
                {"k": "max drawdown", "v": f"{fnum(cfg.get('max_drawdown_pct'), 15):.1f}%"},
                {"k": "short floor", "v": f"${fnum(cfg.get('short_min_equity_usd'), 2000):,.0f} equity"},
                {"k": "accounts", "v": "ITB $2,000 · NAIL (3×) $2,000"},
                {"k": "cost model", "v": "ITB 2 bp/side · NAIL 5 bp/side"},
                {"k": "regime switch", "v": f"60d ITB/TLT corr > {fnum(cfg.get('regime_min_corr'), 0):.1f}"},
                {"k": "signal", "v": f"{cfg.get('signal_ready_et', '09:15:00')} ET"},
                {"k": "entry", "v": "09:30:00 ET · MOC deadline 09:27"},
                {"k": "exit", "v": f"{cfg.get('exit_et', '10:30:00')} ET"},
                {"k": "failsafe", "v": f"{cfg.get('failsafe_et', '15:50:00')} ET"},
            ]

            thesis = [
                "This is a cross-asset lead-lag, not a housing call. Overnight Treasury yields reprice the "
                "discount rate for homebuilders before ITB opens; ZB is the cleanest overnight proxy for the rate path.",
                "The desk measures the ZB move from the prior 16:00 close to the 09:00 print, takes its sign, "
                "and holds ITB from the 09:30 open to the 10:30 exit. One factor, one decision, one exit.",
                "The canonical sample is 2024-05 to 2026-10: 570 trades, +22.4 bp/trade net of 2 bp/side, t 5.18. "
                "That is the evidence the live desk is testing forward.",
                f"NAIL is the 3× version of the same trade, run in its own $2,000 paper account: "
                f"{fmt_bp(edge_n.get('mean_bp'))}/trade net of 5 bp/side, t {fnum(edge_n.get('t')):.2f}, "
                f"max drawdown {fnum(n_risk.get('max_drawdown')) * 100:.0f}%. Same signal, about 3× the P&L and 3× the pain.",
                "But the long-history replication is not supportive: 2010–2019 is negative at 3 bp, and the "
                "all-history mean is −0.4 bp. The edge may be regime-specific. The forward test, not the backtest, decides.",
            ]

            math_rows = [
                {"label": "overnight move", "expr": "m_t = 10^4 · ln( ZB_0900,t / ZB_1600,t-1 )"},
                {"label": "signal", "expr": "d_t = sign(m_t)"},
                {"label": "trade return", "expr": "r_t = d_t · ( ITB_1030,t / ITB_0930,t − 1 ) − 2c"},
                {"label": "NAIL leg", "expr": "r_t = d_t · ( NAIL_1030,t / NAIL_0930,t − 1 ) − 2·5bp  ≈ 3 · r_ITB"},
                {"label": "regime switch", "expr": "trade only if corr_60d( ITB , TLT ) > 0"},
                {"label": "sizing", "expr": "notional_t = min( equity_t , $25,000 )"},
                {"label": "stop", "expr": "stop_t = 3% below entry (long) / above entry (short)"},
                {"label": "expected edge", "expr": "E[r] = +22.4 bp/day · t = 5.18 · n = 570"},
            ]

            return {
                "ok": True,
                "generated_et": now.isoformat(),
                "today": {
                    "date": d.isoformat(), "weekday": now.strftime("%a"),
                    "phase": phase, "session_state": session_state,
                    "headline": headline, "detail": detail,
                    "p0": p0, "p1": p1,
                    "move_bp": move_bp, "d": dsig,
                    "position": position, "next": next_label,
                },
                "stream": stream,
                "thesis": thesis,
                "math": math_rows,
                "evidence": evidence,
                "constraints": constraints,
                "risks": risks,
                "questions": questions,
                "actions": actions,
                "research": [
                    "The canonical panel is deliberately modern (2024-05 → 2026-10, 570 trades). "
                    "The long-history panel goes back to 2010 but is a different construction; it is negative before 2020.",
                    "The live test is registered with a fixed gate: 250 trades, gross t >= 1.65 and net mean > 0; "
                    "kill if cumulative net at 2 bp/side <= -8%.",
                    "The rule is frozen. This page is a reasoning log, not a tuning surface.",
                ],
                "spec": {
                    "id": reg.get("strategy_id") or "zb_itb_v1",
                    "seq": reg.get("seq"),
                    "hash": (reg.get("spec_hash") or "")[:16],
                    "registered_at": reg.get("recorded_at_utc"),
                    "rule": spec.get("rule"),
                    "pass_gate": gate.get("pass"),
                    "kill": gate.get("kill"),
                    "forward": f"{f_n} / {f_final}",
                    "verdict": itb.get("verdict", "collecting"),
                    "nail_forward": f"{int(nail_f.get('n') or 0)} / {int(nail_f.get('final_n') or 250)}",
                },
            }
        except Exception as e:
            return {"ok": False, "error": str(e)[:300]}

    @app.get("/api/mc")
    def mc(sym: str = "ITB"):
        try:
            return _mc_payload(str(ROOT), 6000, _leg(sym))
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.get("/api/account")
    def account():
        try:
            sys.path.insert(0, str(ROOT))
            from live.zb_itb.trader import get_broker, virtual_on, virtual_equity
            cfg = _cfg(); name = cfg.get("default_account") or next(iter(_accounts_cfg()), "ITB")
            acct_cfg = _accounts_cfg().get(name) or {}
            b = get_broker(False, name) if _accounts_cfg() else get_broker(False)
            acct = b.account()
            jj = _journal_df()
            today_s = str(dt.datetime.now(ET).date())
            sim_now, sim_prev = _sim_offset(jj, name, today_s, live=True), _sim_offset(jj, name, today_s, inclusive=False, live=True)
            if sim_now and not acct_cfg.get("virtual"):
                acct = {**acct, "broker_equity": acct.get("equity"),
                        "equity": str(float(acct.get("equity") or 0) + sim_now),
                        "last_equity": str(float(acct.get("last_equity") or 0) + sim_prev), "simulated_pnl": round(sim_now, 2)}
            if acct_cfg.get("virtual") and virtual_on(b.mode):
                veq = virtual_equity(b.mode)
                start = float(cfg.get("virtual_capital_usd") or veq)
                prev = start
                j = _journal_df()
                if not j.empty and "virtual" in j.columns:
                    v = j[(j.event == "day_end_equity") & j["virtual"].eq(True)]
                    v = v[v.day < dt.datetime.now(ET).date()]
                    if not v.empty: prev = float(v.equity.iloc[-1])
                acct = {**acct, "broker_equity": acct.get("equity"), "broker_cash": acct.get("cash"), "broker_buying_power": acct.get("buying_power"),
                        "equity": str(veq), "last_equity": str(prev), "cash": str(veq), "buying_power": str(veq),
                        "virtual": True, "virtual_start": start}
            label = _broker_meta()["label"] + (f" · {name}" if _accounts_cfg() else "")
            if acct.get("virtual"):
                label += " · virtual $" + format(float(cfg.get("virtual_capital_usd") or 0), ",.0f")
            return {"ok": True, "account": acct, "account_name": name, "broker": label,
                    "fetched_et": dt.datetime.now(ET).isoformat()}
        except Exception as e:
            return {"ok": False, "error": str(e)[:240]}

    @app.get("/api/kill")
    def kill():
        try:
            return {"ok": True, "kill": (LIVE / "KILL").exists()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    else:
        @app.get("/")
        def root_page():
            return HTMLResponse("<h1>static dir missing</h1>")

    return app


app = create_app()


def _make_socket(host: str, port: int):
    """Dual-stack listener: macOS AF_INET6 sockets default to v6-only."""
    import socket as _socket

    family = _socket.AF_INET6 if ":" in host else _socket.AF_INET
    sock = _socket.socket(family, _socket.SOCK_STREAM)
    sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
    if family == _socket.AF_INET6:
        try:
            sock.setsockopt(_socket.IPPROTO_IPV6, _socket.IPV6_V6ONLY, 0)
        except OSError:
            pass
    sock.bind((host, port))
    return sock


def main() -> None:
    import uvicorn

    host = os.environ.get("HOST", "::")
    port = int(os.environ.get("PORT", "8502"))
    sock = _make_socket(host, port)
    print(f"ZB -> ITB terminal desk   http://localhost:{port}", flush=True)
    # The desk refreshes every 30s; access logs would grow without bound under
    # launchd. Keep startup/errors, drop the per-request noise.
    uvicorn.Server(uvicorn.Config(app, host=host, port=port, access_log=False)).run(sockets=[sock])


if __name__ == "__main__":
    main()
