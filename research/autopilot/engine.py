"""Rebalancing engine (SPEC.md sections 4-6).

Valuation, targets, drift, band + calendar (+ margin leverage) decision, whole-share trade list (sells before buys,
buys rounded down so cash never goes negative, trades < CAD 100 skipped), FX needs, cost estimates, post-trade
risk checks, unit accounting for drawdown alerts, and refusals.

Everything here is a pure function of its arguments: no clock, no environment, no file or network I/O.  The CLI
(``research.autopilot.cli``) does the reading and writing.  Nothing produced here is a recommendation to trade and
nothing is formatted as a broker order.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from datetime import date
from typing import Any

from research.autopilot import SCHEMA_VERSION
from research.autopilot.config import (ACCOUNT_TYPES, CONFIGS, DECLARED, LETF_CONFIGS, NO_BORROW_ACCOUNTS, SLEEVES,
                                       UNIVERSE, USDCAD, Config, borrow_capacity_fraction, position_cap, recipe_for,
                                       target_gross, target_weights)
from research.autopilot.holdings import Holdings
from research.autopilot.paperlog import GENESIS
from research.autopilot.prices import PriceData

TOL = 1e-12          # float-noise tolerance for strict "> limit" tests (bands, caps)
SHARE_EPS = 1e-9     # added before flooring share counts so that 9.9999999999 -> 10
CASH_EPS = 1e-9      # a CAD/USD balance with |x| <= this is exactly zero
INITIAL_UNIT_VALUE = 100.0

DISCLAIMER = ("Research tool output only. Nothing in this report is a recommendation to trade. No order has been "
              "placed, sent or generated for any broker; the owner reads it and decides.")

TICKER_NOTES = {
    "RSSB": "RSSB: equity leg is global; the bond leg is US Treasuries (not Canadian bonds).",
    "RSST": "RSST: equity leg is US-only (S&P 500-like), stacked with managed futures.",
    "GDE": "GDE: equity leg is US-only, stacked with gold.",
    "SSO": "SSO: 2x daily-reset S&P 500 leveraged ETF; US-only equity; returns are path-dependent (daily reset).",
    "DBMF": "DBMF: USD-listed managed-futures replication ETF.",
}


class EngineError(ValueError):
    """Programming/usage error inside the engine (never raised for data problems; those are refusals)."""


@dataclass(frozen=True)
class EngineInputs:
    config: Config
    config_file: str
    config_sha256: str
    holdings: Holdings | None
    holdings_error: str | None
    holdings_file: str
    holdings_sha256: str | None
    prices: PriceData | None
    price_error: str | None
    price_version: str
    report_date: date
    expected_manifest_sha256: str | None = None     # optional owner pin (CLI --expect-manifest-sha256)


# ------------------------------------------------------------------------------------------------ small helpers --
def _r(x: float, nd: int) -> float:
    """Round for display/JSON; never returns -0.0 or a non-finite value."""
    if not math.isfinite(x):
        raise EngineError(f"non-finite value in engine output: {x!r}")
    v = round(float(x), nd)
    return 0.0 if v == 0 else v


def _money(x: float) -> float:
    return _r(x, 2)


def _w(x: float) -> float:
    return _r(x, 8)


def _clean(x: float) -> float:
    return 0.0 if abs(x) <= CASH_EPS else x


def effective_params(cfg: Config) -> dict[str, Any]:
    return copy.deepcopy(cfg.params) if cfg.supported else copy.deepcopy(DECLARED)


def is_quarter_end(report_date: date, params: dict[str, Any]) -> bool:
    """Quarter-end report = report date in a quarter-end month (Mar/Jun/Sep/Dec); see IMPLEMENTATION_NOTES.md."""
    return report_date.month in set(params["calendar_months"])


def gross_multiplier(ticker: str) -> float:
    return float(sum(UNIVERSE[ticker]["exp"].values()))


# ------------------------------------------------------------------------------------------------ prices -----------
def price_table(prices: PriceData, tickers: list[str], report_date: date,
                freshness_days: int) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Latest price on or before the report date for each ticker (+ USDCAD), with refusal reasons."""
    reasons: list[str] = []
    table: dict[str, dict[str, Any]] = {}
    if prices.max_date > report_date:
        future = sorted(t for t, rows in prices.series.items() if rows and rows[-1][0] > report_date)
        reasons.append(f"price file is future-dated: it contains prices dated up to {prices.max_date.isoformat()}, "
                       f"after the report date {report_date.isoformat()} (tickers {future})")
    for t in [*tickers, USDCAD]:
        row = prices.latest(t, report_date)
        what = "USD/CAD rate (USDCAD)" if t == USDCAD else f"price for {t}"
        if row is None:
            if t == USDCAD:
                reasons.append(f"missing USD/CAD rate: no USDCAD row on or before {report_date.isoformat()}")
            else:
                reasons.append(f"no {what} on or before {report_date.isoformat()} (held or target ticker)")
            continue
        d, close, ccy = row
        expected = "CAD" if t == USDCAD else UNIVERSE[t]["ccy"]
        if ccy != expected:
            reasons.append(f"{what} dated {d.isoformat()} is quoted in {ccy}; expected {expected}")
            continue
        age = (report_date - d).days
        if age > freshness_days:
            reasons.append(f"stale {what}: latest is {d.isoformat()}, {age} calendar days before the report date "
                           f"(limit {freshness_days})")
            continue
        table[t] = {"close": float(close), "ccy": ccy, "date": d.isoformat()}
    return table, reasons


# ------------------------------------------------------------------------------------------------ valuation --------
def value_state(shares: dict[str, int], px: dict[str, dict[str, Any]], fx: float, cad: float, usd: float,
                tickers: list[str]) -> dict[str, Any]:
    """Value a state.  ``cad`` is the net CAD balance (negative = margin loan), ``usd`` the USD cash balance."""
    rows = []
    etf = gross = 0.0
    sleeves = {s: 0.0 for s in SLEEVES}
    for t in tickers:
        n = int(shares.get(t, 0))
        p = px[t]
        pc = p["close"] * (fx if p["ccy"] == "USD" else 1.0)
        v = n * pc
        etf += v
        gross += v * gross_multiplier(t)
        for s in SLEEVES:
            sleeves[s] += v * float(UNIVERSE[t]["exp"][s])
        rows.append({"ticker": t, "shares": n, "close": p["close"], "ccy": p["ccy"], "price_date": p["date"],
                     "price_cad": pc, "value_cad": v})
    cash_assets = max(0.0, cad) + max(0.0, usd) * fx
    loan = max(0.0, -cad)
    nav = etf + cad + usd * fx
    assets = etf + cash_assets
    return {"rows": rows, "etf_value": etf, "cash_cad": max(0.0, cad), "cash_usd": usd, "loan_cad": loan,
            "net_cad": cad, "nav": nav, "assets": assets, "gross_exposure": gross, "sleeves": sleeves}


def _weights(state: dict[str, Any]) -> dict[str, float]:
    nav = state["nav"]
    return {r["ticker"]: r["value_cad"] / nav for r in state["rows"]}


# ------------------------------------------------------------------------------------------------ decision ---------
def band_decision(current: dict[str, float], target: dict[str, float], params: dict[str, Any], *,
                  quarter_end: bool, leverage: float | None = None,
                  target_leverage: float | None = None) -> dict[str, Any]:
    """Drift band + calendar (+ margin leverage) trigger.  Pure; weights are fractions of NAV."""
    rows = []
    band_hits, cal_hits = [], []
    for t in sorted(set(current) | set(target)):
        c, g = float(current.get(t, 0.0)), float(target.get(t, 0.0))
        d = c - g
        ad = abs(d)
        rel = ad / g if g > 0 else None
        abs_hit = ad > params["band_abs"] + TOL
        rel_hit = ad > params["band_rel_min_abs"] + TOL and (g <= 0 or ad > params["band_rel"] * g + TOL)
        cal_hit = quarter_end and ad > params["calendar_abs"] + TOL
        rows.append({"ticker": t, "current": c, "target": g, "drift": d, "rel_drift": rel,
                     "abs_trigger": abs_hit, "rel_trigger": rel_hit, "calendar_trigger": cal_hit})
        if abs_hit:
            band_hits.append(f"{t}: abs drift {d * 100:+.2f} pp > {params['band_abs'] * 100:.2f} pp")
        elif rel_hit:
            rel_txt = "target 0" if rel is None else f"{rel * 100:.1f}% of target"
            band_hits.append(f"{t}: relative drift {rel_txt} > {params['band_rel'] * 100:.0f}% and abs drift "
                             f"{d * 100:+.2f} pp > {params['band_rel_min_abs'] * 100:.2f} pp")
        if cal_hit:
            cal_hits.append(f"{t}: abs drift {d * 100:+.2f} pp > {params['calendar_abs'] * 100:.2f} pp")
    lev_hit = False
    lev_txt = None
    if leverage is not None and target_leverage is not None:
        lev_hit = abs(leverage - target_leverage) > params["margin_leverage_band"] + TOL
        lev_txt = (f"leverage (assets/equity) {leverage:.3f} vs target {target_leverage:.3f}: difference "
                   f"{leverage - target_leverage:+.3f} {'>' if lev_hit else '<='} "
                   f"{params['margin_leverage_band']:.2f}")
    triggers = []
    if band_hits:
        triggers.append({"kind": "band", "detail": band_hits})
    if cal_hits:
        triggers.append({"kind": "calendar", "detail": cal_hits})
    if lev_hit:
        triggers.append({"kind": "margin_leverage", "detail": [lev_txt]})
    return {"rows": rows, "quarter_end": quarter_end, "triggered": bool(triggers), "triggers": triggers,
            "leverage": leverage, "target_leverage": target_leverage, "leverage_check": lev_txt}


# ------------------------------------------------------------------------------------------------ trades -----------
def fund(pools: dict[str, float], ccy: str, amount: float, fx: float, fx_cost: float,
         cad_floor: float) -> tuple[dict[str, float], dict[str, Any] | None] | None:
    """Pay ``amount`` (in ``ccy``) from the cash pools; return (new pools, conversion) or None if unaffordable.

    Order: own-currency cash; then convert the other currency's cash (CAD may additionally be borrowed down to
    ``cad_floor`` in a margin account, 0 otherwise).  USD is never borrowed.  Conversion loses ``fx_cost``.
    """
    cad, usd = pools["CAD"], pools["USD"]
    keep = 1.0 - fx_cost
    if ccy == "CAD":
        short = amount - max(0.0, cad)
        if short <= CASH_EPS:
            return {"CAD": _clean(cad - amount), "USD": usd}, None
        usd_avail = max(0.0, usd)
        usd_needed = short / fx / keep
        if usd_needed <= usd_avail + CASH_EPS:
            take = min(usd_needed, usd_avail)
            return ({"CAD": min(cad, 0.0), "USD": _clean(usd - take)},
                    {"from": "USD", "to": "CAD", "amount_from": take, "amount_to": short,
                     "cost_cad": take * fx * fx_cost})
        got = usd_avail * keep * fx
        new_cad = min(cad, 0.0) - (short - got)
        if new_cad < cad_floor - CASH_EPS:
            return None
        conv = None if usd_avail <= 0 else {"from": "USD", "to": "CAD", "amount_from": usd_avail, "amount_to": got,
                                            "cost_cad": usd_avail * fx * fx_cost}
        return {"CAD": _clean(new_cad), "USD": _clean(usd - usd_avail)}, conv
    if ccy != "USD":
        raise EngineError(f"unknown currency {ccy!r}")
    short = amount - max(0.0, usd)
    if short <= CASH_EPS:
        return {"CAD": cad, "USD": _clean(usd - amount)}, None
    cad_needed = short * fx / keep
    new_cad = cad - cad_needed
    if new_cad < cad_floor - CASH_EPS:
        return None
    return ({"CAD": _clean(new_cad), "USD": _clean(min(usd, 0.0))},
            {"from": "CAD", "to": "USD", "amount_from": cad_needed, "amount_to": short,
             "cost_cad": cad_needed * fx_cost})


def build_trades(shares: dict[str, int], px: dict[str, dict[str, Any]], fx: float, nav: float,
                 target: dict[str, float], pools: dict[str, float], cad_floor: float,
                 params: dict[str, Any]) -> dict[str, Any]:
    """Full rebalance to target: sells first, then buys; whole shares, trade quantities rounded toward zero;
    buys are further rounded down to what the cash (and, in margin accounts, the borrowing capacity) can fund;
    trades below the minimum size are skipped.  Buys run USD-listed first so currency is converted one way only."""
    hs = params["half_spread"]
    commission = float(params["commission_cad"])
    min_trade = float(params["min_trade_cad"])
    fx_cost = float(params["fx_cost"])
    tickers = sorted(set(shares) | set(target))
    new_shares = {t: int(shares.get(t, 0)) for t in tickers}
    pools = dict(pools)
    trades: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    conversions: list[dict[str, Any]] = []

    def pcad(t: str) -> float:
        return px[t]["close"] * (fx if px[t]["ccy"] == "USD" else 1.0)

    def comm_ccy(t: str) -> float:
        return commission / fx if px[t]["ccy"] == "USD" else commission

    def record(side: str, t: str, q: int, note: str | None = None) -> None:
        p = px[t]
        rate = fx if p["ccy"] == "USD" else 1.0
        value = q * p["close"]
        spread = value * hs[t]
        trades.append({"side": side, "ticker": t, "shares": q, "est_price": p["close"], "ccy": p["ccy"],
                       "est_value_ccy": value, "est_value_cad": value * rate, "est_spread_cad": spread * rate,
                       "est_commission_cad": commission, "est_cost_cad": spread * rate + commission,
                       "note": note})

    # sells (tickers in sorted order)
    for t in tickers:
        cur = new_shares[t]
        g = float(target.get(t, 0.0))
        exact = g * nav / pcad(t)
        if cur <= 0 or cur <= exact:
            continue
        q = cur if g <= 0 else min(cur, math.floor(cur - exact + SHARE_EPS))
        if q <= 0:
            continue
        value_cad = q * pcad(t)
        if value_cad < min_trade:
            skipped.append({"side": "SELL", "ticker": t, "shares": q, "est_value_cad": value_cad,
                            "reason": f"below the CAD {min_trade:,.0f} minimum trade size"})
            continue
        proceeds = q * px[t]["close"] * (1.0 - hs[t]) - comm_ccy(t)
        if proceeds <= 0:
            skipped.append({"side": "SELL", "ticker": t, "shares": q, "est_value_cad": value_cad,
                            "reason": "estimated commission exceeds the proceeds"})
            continue
        pools[px[t]["ccy"]] = _clean(pools[px[t]["ccy"]] + proceeds)
        new_shares[t] = cur - q
        record("SELL", t, q)

    # buys: USD-listed first, then CAD-listed; within each, largest desired value first, ties by ticker.  Funding
    # USD buys first means USD cash is spent on USD buys before any CAD buy could convert it, so a run never converts
    # in both directions (CAD -> USD for one buy and USD -> CAD for another).
    cands = []
    for t in tickers:
        cur = new_shares[t]
        exact = float(target.get(t, 0.0)) * nav / pcad(t)
        if exact <= cur:
            continue
        desired = math.floor(exact - cur + SHARE_EPS)
        if desired > 0:
            cands.append((px[t]["ccy"] != "USD", -desired * pcad(t), t, desired))
    for _ccy, _neg, t, desired in sorted(cands):
        ccy = px[t]["ccy"]
        if desired * pcad(t) < min_trade:
            skipped.append({"side": "BUY", "ticker": t, "shares": desired, "est_value_cad": desired * pcad(t),
                            "reason": f"below the CAD {min_trade:,.0f} minimum trade size"})
            continue

        def outlay(q: int) -> float:
            return q * px[t]["close"] * (1.0 + hs[t]) + comm_ccy(t)

        def feasible(q: int) -> bool:
            return fund(pools, ccy, outlay(q), fx, fx_cost, cad_floor) is not None

        if feasible(desired):
            q = desired
        else:
            lo, hi = 0, desired - 1
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if feasible(mid):
                    lo = mid
                else:
                    hi = mid - 1
            q = lo if lo > 0 and feasible(lo) else 0
        if q * pcad(t) < min_trade or q <= 0:
            skipped.append({"side": "BUY", "ticker": t, "shares": desired, "est_value_cad": desired * pcad(t),
                            "reason": "insufficient cash to fund the minimum trade size without borrowing"
                            if cad_floor >= 0 else "insufficient cash and borrowing capacity"})
            continue
        funded = fund(pools, ccy, outlay(q), fx, fx_cost, cad_floor)
        assert funded is not None
        pools, conv = funded
        if conv is not None:
            conv["for"] = t
            conversions.append(conv)
        new_shares[t] += q
        record("BUY", t, q, None if q == desired else f"rounded down from {desired} shares to fit available cash")
    return {"trades": trades, "skipped": skipped, "conversions": conversions, "shares": new_shares,
            "pools": pools}


# ------------------------------------------------------------------------------------------------ risk checks ------
def risk_checks(state: dict[str, Any], cfg: Config, params: dict[str, Any], shares: dict[str, int]) -> list[dict]:
    """Post-trade checks (SPEC section 4/5).  Each check: name, ok, value, limit, detail."""
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, value: Any, limit: Any, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "value": value, "limit": limit, "detail": detail})

    nav = state["nav"]
    add("nav_positive", nav > 0, _money(nav), 0.0, "post-trade NAV must be positive")
    if nav <= 0:
        return checks
    negative = sorted(t for t, n in shares.items() if n < 0)
    add("no_negative_shares", not negative, negative, [], "shorts are never allowed")
    cad, usd = state["net_cad"], state["cash_usd"]
    if cfg.account_type in NO_BORROW_ACCOUNTS:
        add("no_borrowing_no_negative_cash", cad >= 0 and usd >= 0,
            {"cash_cad": _money(cad), "cash_usd": _money(usd)}, 0.0,
            f"{cfg.account_type} accounts can never borrow; cash may never go below 0")
    else:
        add("usd_cash_non_negative", usd >= 0, _money(usd), 0.0, "USD is never borrowed")
    gross = state["gross_exposure"] / nav
    cap = target_gross(cfg) + float(params["leverage_cap_addon"])
    add("leverage_cap", gross <= cap + TOL, _r(gross, 6), _r(cap, 6),
        "effective gross exposure / NAV <= config target gross + add-on")
    if cfg.account_type == "nonreg_margin":
        ratio = nav / state["assets"] if state["assets"] > 0 else 1.0
        floor = float(params["equity_assets_floor"])
        add("equity_assets_floor", ratio >= floor - TOL, _r(ratio, 6), _r(floor, 6),
            "margin account: equity / assets after trades")
    target = target_weights(cfg)
    worst = None
    breaches = []
    caps = {}
    for r in state["rows"]:
        w = r["value_cad"] / nav
        lim, rule = position_cap(r["ticker"], target, params)
        caps[r["ticker"]] = _r(lim, 6)
        if w > lim + TOL:
            breaches.append(f"{r['ticker']} {w * 100:.2f}% > {lim * 100:.2f}% ({rule})")
        if worst is None or w - lim > worst[1] - worst[2]:
            worst = (r["ticker"], w, lim)
    add("position_cap", not breaches, {"ticker": worst[0], "weight": _r(worst[1], 6)} if worst else None,
        {"max_position": float(params["max_position"]), "max_position_sso": float(params["max_position_sso"]),
         "one_ticket_cap_addon": float(params["one_ticket_cap_addon"]), "per_ticker": caps},
        "; ".join(breaches) if breaches else
        "largest position vs its cap (SSO: max_position_sso; XEQT.TO/ZAG.TO: target + one_ticket_cap_addon; "
        "others: max_position)")
    return checks


def recipe_cap_conflicts(cfg: Config, params: dict[str, Any]) -> list[str]:
    """Targets that by themselves exceed their single-position cap, so the config/account pair can never pass it.

    Since the SPEC section 4 change of 2026-09-29 (XEQT.TO/ZAG.TO capped at target + 5 pp) no default recipe
    conflicts; a conflict can only come from an override that tightens a cap below a target (e.g. max_position 0.60
    with P6a@1.25, whose recipe targets RSST at 61.875%)."""
    out = []
    kind = recipe_for(cfg.config_id, cfg.account_type)[2]
    target = target_weights(cfg)
    for t, w in sorted(target.items()):
        lim, rule = position_cap(t, target, params)
        if w > lim + TOL:
            out.append(f"the {cfg.config_id} {kind} recipe itself targets {t} at {w * 100:.2f}% of NAV, above its "
                       f"{lim * 100:.2f}% single-position cap ({rule}): this config/account combination cannot pass "
                       f"the cap with these parameters")
    return out


# ------------------------------------------------------------------------------------------------ paper log --------
def manifest_pin(chain: list[dict[str, Any]], dataset_version: str) -> tuple[str, int] | None:
    """(manifest SHA-256, seq) of the first paper-log entry that recorded a verified snapshot under
    ``dataset_version``.  A frozen version's content never changes, so every later run must see the same manifest."""
    for entry in chain:
        body = entry.get("body")
        prices = body.get("inputs", {}).get("prices") if isinstance(body, dict) else None
        if not isinstance(prices, dict) or prices.get("dataset_version") != dataset_version:
            continue
        sha = prices.get("manifest_sha256")
        if isinstance(sha, str) and sha:
            return sha, int(entry.get("seq", -1))
    return None


def log_head(chain: list[dict[str, Any]]) -> dict[str, Any]:
    """Where this run's entry will sit in the paper log: its seq and the entry_hash it chains after.  Recorded in the
    summary and the report so that a later truncation of trailing log lines is detectable from the outputs."""
    return {"seq": len(chain), "prev_entry_hash": chain[-1]["entry_hash"] if chain else GENESIS,
            "entries_before": len(chain)}


# ------------------------------------------------------------------------------------------------ unit ledger ------
def prior_state(chain: list[dict[str, Any]], portfolio_id: str,
                report_date: date) -> tuple[dict[str, Any] | None, str | None]:
    """Unit-ledger state carried by accepted paper-log entries of this portfolio dated before the report date.

    For a date with several accepted entries (same-day re-runs) the last one supersedes the others.  An accepted
    entry dated after the report date is a refusal (the ledger cannot be rewound)."""
    effective: dict[date, dict[str, float]] = {}
    later: list[date] = []
    for entry in chain:
        body = entry.get("body")
        if not isinstance(body, dict) or body.get("portfolio_id") != portfolio_id:
            continue
        if body.get("status") != "accepted":
            continue
        try:
            d = date.fromisoformat(body["report_date"])
            led = body["unit_ledger"]
            if not led.get("carried"):
                continue
            units, uv = float(led["units"]), float(led["unit_value"])
            if not (math.isfinite(units) and units > 0 and math.isfinite(uv) and uv > 0):
                raise ValueError("non-positive units")
        except (KeyError, TypeError, ValueError, AttributeError):
            return None, f"paper log entry seq {entry.get('seq')} for {portfolio_id} has a malformed unit ledger"
        if d > report_date:
            later.append(d)
        elif d < report_date:
            effective[d] = {"units": units, "unit_value": uv}
    if later:
        return None, (f"the paper log already holds an accepted report for {portfolio_id} dated "
                      f"{max(later).isoformat()}, after the report date {report_date.isoformat()}")
    if not effective:
        return None, None
    last = max(effective)
    return {"last_report_date": last.isoformat(), "units": effective[last]["units"],
            "unit_value": effective[last]["unit_value"],
            "peak": max(v["unit_value"] for v in effective.values()), "reports": len(effective)}, None


def unit_ledger(nav: float, flow: float, prior: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str | None]:
    """unit value = NAV / units; units change only with the declared net external flow (issued/redeemed at the
    unit value of the NAV excluding that flow)."""
    if prior is None:
        units = nav / INITIAL_UNIT_VALUE
        return {"initialised": True, "units_before": None, "units": units, "unit_value": nav / units,
                "net_external_flow_cad": flow, "flow_applied_cad": 0.0, "peak": nav / units,
                "prior_report_date": None}, None
    base = nav - flow
    if base <= 0:
        return None, (f"unit accounting impossible: NAV (CAD {nav:,.2f}) minus the declared net external flow "
                      f"(CAD {flow:,.2f}) is not positive")
    uv_ex_flow = base / prior["units"]
    units = prior["units"] + flow / uv_ex_flow
    uv = nav / units
    return {"initialised": False, "units_before": prior["units"], "units": units, "unit_value": uv,
            "net_external_flow_cad": flow, "flow_applied_cad": flow, "peak": max(prior["peak"], uv),
            "prior_report_date": prior["last_report_date"]}, None


def drawdown_alert(unit_value: float, peak: float, tolerance_pct: int, levels: dict[str, float]) -> dict[str, Any]:
    dd = max(0.0, 1.0 - unit_value / peak)
    tol = tolerance_pct / 100.0
    frac = dd / tol if tol > 0 else 0.0
    level = "NONE"
    for name in ("INFO", "WARNING", "BREACH"):
        if frac >= levels[name] - TOL:
            level = name
    return {"drawdown": _r(dd, 8), "tolerance": tol, "fraction_of_tolerance": _r(frac, 6), "alert": level,
            "thresholds": dict(levels),
            "policy": "Alerts never trigger automatic de-risking; the owner decides."}


# ------------------------------------------------------------------------------------------------ evaluation -------
def _config_block(inp: EngineInputs) -> dict[str, Any]:
    cfg = inp.config
    block: dict[str, Any] = {"file": inp.config_file, "sha256": inp.config_sha256, "config_id": cfg.config_id,
                             "account_type": cfg.account_type, "owner_tolerance_pct": cfg.owner_tolerance_pct,
                             "portfolio_id": cfg.portfolio_id, "overrides": copy.deepcopy(cfg.overrides),
                             "supported": cfg.supported, "error": cfg.error, "label": cfg.label}
    if cfg.supported:
        weights, loan, kind = recipe_for(cfg.config_id, cfg.account_type)
        block.update({"recipe_kind": kind, "recipe_weights": {t: float(w) for t, w in sorted(weights.items())},
                      "recipe_loan_fraction": float(loan), "target_gross": _r(target_gross(cfg), 6),
                      "uses_letf": cfg.config_id in LETF_CONFIGS and kind == "stacked",
                      "exposures": {s: float(v) for s, v in CONFIGS[cfg.config_id]["exposures"].items()}})
    return block


def _notes(cfg: Config, tickers: list[str]) -> list[str]:
    notes = []
    if cfg.supported and cfg.account_type in ACCOUNT_TYPES:
        _w_, _loan, kind = recipe_for(cfg.config_id, cfg.account_type)
        if kind == "stacked" and cfg.config_id in LETF_CONFIGS:
            notes.append(f"{cfg.config_id} stacked recipe uses a 2x daily-reset leveraged ETF (SSO).")
        if kind == "margin" and float(_loan) > 0:
            notes.append("Margin recipe: unlevered sleeves x L funded partly by a margin loan; margin interest is not "
                         "included in the cost estimates.")
    for t in tickers:
        if t in TICKER_NOTES:
            notes.append(TICKER_NOTES[t])
    return notes


def _position_rows(state: dict[str, Any], target: dict[str, float]) -> list[dict[str, Any]]:
    nav = state["nav"]
    return [{"ticker": r["ticker"], "shares": r["shares"], "close": r["close"], "ccy": r["ccy"],
             "price_date": r["price_date"], "value_cad": _money(r["value_cad"]),
             "weight": _w(r["value_cad"] / nav), "target": _w(target.get(r["ticker"], 0.0))}
            for r in state["rows"]]


def _state_block(state: dict[str, Any], target: dict[str, float]) -> dict[str, Any]:
    nav = state["nav"]
    return {"positions": _position_rows(state, target), "etf_value_cad": _money(state["etf_value"]),
            "cash_cad": _money(state["cash_cad"]), "cash_usd": _money(state["cash_usd"]),
            "margin_loan_cad": _money(state["loan_cad"]), "nav_cad": _money(nav),
            "assets_cad": _money(state["assets"]),
            "gross_exposure_over_nav": _r(state["gross_exposure"] / nav, 6),
            "leverage_assets_over_equity": _r(state["assets"] / nav, 6),
            "equity_over_assets": _r(nav / state["assets"], 6) if state["assets"] > 0 else None,
            "sleeve_exposure_over_nav": {s: _r(v / nav, 6) for s, v in state["sleeves"].items()}}


def _fx_block(conversions: list[dict[str, Any]], fx: float) -> dict[str, Any]:
    c2u = [c for c in conversions if c["from"] == "CAD"]
    u2c = [c for c in conversions if c["from"] == "USD"]
    return {"usdcad": fx,
            "cad_to_usd": {"usd_needed": _money(sum(c["amount_to"] for c in c2u)),
                           "cad_spent": _money(sum(c["amount_from"] for c in c2u)),
                           "est_cost_cad": _money(sum(c["cost_cad"] for c in c2u)),
                           "for": sorted({c["for"] for c in c2u})},
            "usd_to_cad": {"cad_needed": _money(sum(c["amount_to"] for c in u2c)),
                           "usd_spent": _money(sum(c["amount_from"] for c in u2c)),
                           "est_cost_cad": _money(sum(c["cost_cad"] for c in u2c)),
                           "for": sorted({c["for"] for c in u2c})},
            "any_conversion": bool(conversions)}


def evaluate(inp: EngineInputs, chain: list[dict[str, Any]]) -> dict[str, Any]:
    """Run the engine on already-loaded inputs and the validated paper-log chain; return the JSON summary."""
    cfg = inp.config
    rd = inp.report_date
    params = effective_params(cfg)
    reasons: list[str] = []
    h = inp.holdings
    P = inp.prices

    summary: dict[str, Any] = {
        "schema": SCHEMA_VERSION, "kind": "autopilot_rebalance_report", "disclaimer": DISCLAIMER,
        "report_date": rd.isoformat(), "portfolio_id": cfg.portfolio_id, "status": None,
        "refusal_reasons": [], "trades_emitted": False, "config": _config_block(inp), "params": params,
        "inputs": {
            "holdings": {"file": inp.holdings_file, "sha256": inp.holdings_sha256,
                         "as_of": h.as_of.isoformat() if h else None,
                         "net_external_flow_cad": h.net_external_flow_cad if h else None,
                         "error": inp.holdings_error},
            "prices": {"dataset_version": inp.price_version,
                       "manifest_sha256": P.manifest_sha256 if P else None,
                       "mode": P.mode if P else None, "files": dict(P.file_sha256) if P else {},
                       "max_date": P.max_date.isoformat() if P else None, "error": inp.price_error,
                       "expected_manifest_sha256": inp.expected_manifest_sha256,
                       "pinned_manifest_sha256": None, "pinned_by_seq": None},
            "usdcad": None},
        "paper_log": log_head(chain),
        "targets": None, "valuation": None, "decision": None, "trades": [], "skipped_trades": [], "fx": None,
        "costs": None, "post_trade": None, "checked_state": None, "checks": [], "unit_ledger": None,
        "drawdown": None, "notes": []}

    if not cfg.supported:
        reasons.append(f"unsupported configuration: {cfg.error}")
    if h is None:
        reasons.append(f"holdings file unparsable: {inp.holdings_error}")
    if P is None:
        reasons.append(inp.price_error or "price snapshot unavailable")
    target = target_weights(cfg) if cfg.supported else {}
    if cfg.supported:
        summary["targets"] = {t: _w(w) for t, w in sorted(target.items())}

    fresh = int(params["freshness_days"])
    if h is not None:
        age = (rd - h.as_of).days
        if age < 0:
            reasons.append(f"holdings file is future-dated: as-of {h.as_of.isoformat()} is after the report date "
                           f"{rd.isoformat()}")
        elif age > fresh:
            reasons.append(f"stale holdings file: as-of {h.as_of.isoformat()} is {age} calendar days before the "
                           f"report date (limit {fresh})")
        if cfg.account_type in NO_BORROW_ACCOUNTS and h.margin_loan_cad > 0:
            reasons.append(f"account constraint: {cfg.account_type} accounts can never borrow, but the holdings "
                           f"show a margin loan of CAD {h.margin_loan_cad:,.2f}")
        if cfg.account_type == "nonreg_margin" and not h.margin_loan_given:
            reasons.append("holdings file for a margin account must state margin_loan_cad (0 if none)")

    held = sorted(h.positions) if h is not None else []
    tickers = sorted(set(held) | set(target))
    summary["notes"] = _notes(cfg, tickers)
    px: dict[str, dict[str, Any]] = {}
    if P is not None:
        px, price_reasons = price_table(P, tickers, rd, fresh)
        reasons.extend(price_reasons)
        if USDCAD in px:
            summary["inputs"]["usdcad"] = {"rate": px[USDCAD]["close"], "date": px[USDCAD]["date"]}

    if P is not None:
        pin = manifest_pin(chain, inp.price_version)
        if pin is not None:
            summary["inputs"]["prices"].update(pinned_manifest_sha256=pin[0], pinned_by_seq=pin[1])
            if pin[0] != P.manifest_sha256:
                reasons.append(f"price snapshot version {inp.price_version!r} has manifest sha256 {P.manifest_sha256}, "
                               f"but paper log entry seq {pin[1]} recorded manifest {pin[0]} for the same version: a "
                               "frozen version's content never changes (freeze new prices under a new version name)")
        if inp.expected_manifest_sha256 is not None and inp.expected_manifest_sha256 != P.manifest_sha256:
            reasons.append(f"price snapshot manifest sha256 {P.manifest_sha256} does not match the expected "
                           f"{inp.expected_manifest_sha256} (--expect-manifest-sha256)")

    prior, prior_err = prior_state(chain, cfg.portfolio_id, rd)
    if prior_err:
        reasons.append(prior_err)

    if reasons:
        return _refuse(summary, reasons)
    assert h is not None and P is not None

    fx = px[USDCAD]["close"]
    shares = {t: int(h.positions.get(t, 0)) for t in tickers}
    pre = value_state(shares, px, fx, h.cash_cad - h.margin_loan_cad, h.cash_usd, tickers)
    if pre["nav"] <= 0:
        return _refuse(summary, [f"NAV is not positive (CAD {pre['nav']:,.2f}); nothing can be rebalanced"])
    nav = pre["nav"]
    summary["valuation"] = _state_block(pre, target)

    ledger, ledger_err = unit_ledger(nav, h.net_external_flow_cad, prior)
    if ledger_err:
        return _refuse(summary, [ledger_err])
    assert ledger is not None
    if ledger["initialised"] and h.net_external_flow_cad != 0:
        summary["notes"].append("First report for this portfolio in this paper log: units initialised at "
                                f"{INITIAL_UNIT_VALUE:.2f} per unit; the declared net external flow is recorded "
                                "but not applied.")

    margin = cfg.account_type == "nonreg_margin"
    target_lev = max(1.0, sum(target.values())) if margin else None
    decision = band_decision(_weights(pre), target, params, quarter_end=is_quarter_end(rd, params),
                             leverage=pre["assets"] / nav if margin else None, target_leverage=target_lev)
    summary["decision"] = {
        "quarter_end": decision["quarter_end"], "triggered": decision["triggered"],
        "triggers": decision["triggers"], "leverage_check": decision["leverage_check"],
        "rows": [{"ticker": r["ticker"], "current": _w(r["current"]), "target": _w(r["target"]),
                  "drift": _w(r["drift"]), "rel_drift": None if r["rel_drift"] is None else _r(r["rel_drift"], 6),
                  "abs_trigger": r["abs_trigger"], "rel_trigger": r["rel_trigger"],
                  "calendar_trigger": r["calendar_trigger"]} for r in decision["rows"]]}

    pools = {"CAD": h.cash_cad - h.margin_loan_cad, "USD": h.cash_usd}
    if h.cash_cad > 0 and h.margin_loan_cad > 0:
        summary["notes"].append("CAD cash and the margin loan are netted into one CAD balance (negative = loan).")
    capacity = borrow_capacity_fraction(cfg) * nav
    if decision["triggered"]:
        built = build_trades(shares, px, fx, nav, target, pools, -capacity if capacity > 0 else 0.0, params)
    else:
        built = {"trades": [], "skipped": [], "conversions": [], "shares": dict(shares), "pools": dict(pools)}
    post = value_state(built["shares"], px, fx, built["pools"]["CAD"], built["pools"]["USD"], tickers)
    checks = risk_checks(post, cfg, params, built["shares"])
    summary["checks"] = checks
    post_block = _state_block(post, target) if post["nav"] > 0 else {"nav_cad": _money(post["nav"])}
    summary["post_trade"] = dict(post_block, basis="after the proposed trades (estimated)" if built["trades"]
                                 else "current holdings (no trades proposed)")
    summary["decision"]["borrow_capacity_cad"] = _money(capacity)
    summary["decision"]["action"] = ("full rebalance of all positions to target" if built["trades"] else
                                     "no trade (triggered, but every trade was below the minimum size or unfundable)"
                                     if decision["triggered"] else "no trade")
    if margin and post["cash_usd"] > CASH_EPS and post["loan_cad"] > CASH_EPS:
        summary["notes"].append(
            f"USD cash of USD {post['cash_usd']:,.2f} is held while a CAD margin loan of CAD {post['loan_cad']:,.2f} "
            "is outstanding (the engine converts currency only to fund buys). Converting it would reduce the loan "
            f"and assets/equity, at the {float(params['fx_cost']) * 100:.2f}% conversion cost; the owner decides.")
    summary["drawdown"] = drawdown_alert(ledger["unit_value"], ledger["peak"], cfg.owner_tolerance_pct,
                                         params["alert_levels"])
    summary["unit_ledger"] = {k: (v if not isinstance(v, float) or k in ("units", "units_before", "unit_value",
                                                                          "peak") else _money(v))
                              for k, v in ledger.items()}

    failed = [c for c in checks if not c["ok"]]
    if failed:
        why = [f"post-trade check failed: {c['name']} (value {c['value']}, limit {c['limit']}; {c['detail']})"
               for c in failed]
        if not built["trades"] and not decision["triggered"]:
            why.append("no trades were triggered, so the checks apply to the current holdings")
        elif not built["trades"]:
            why.append("a rebalance was triggered but no trade could be proposed (whole-share rounding, the minimum "
                       "trade size or insufficient cash), so the checks apply to the current holdings")
        why.extend(recipe_cap_conflicts(cfg, params))
        # The state the checks failed on is kept only under ``checked_state`` and labelled; ``post_trade`` is
        # cleared so nothing in a refused summary or report reads as a proposed rebalance.
        if built["trades"]:
            summary["checked_state"] = dict(
                post_block, kind="rejected_hypothetical_rebalance", rejected_trade_count=len(built["trades"]),
                basis=("REJECTED HYPOTHETICAL: the state after the full rebalance the engine considered; it failed "
                       "the post-trade checks, so none of those trades is proposed"))
            summary["decision"]["action"] = ("none: REFUSED (a rebalance was triggered, but the hypothetical full "
                                             "rebalance failed the post-trade checks; no trades are proposed)")
        else:
            summary["checked_state"] = dict(post_block, kind="current_holdings", rejected_trade_count=0,
                                            basis="current holdings (no trades proposed)")
            summary["decision"]["action"] = "none: REFUSED (the current holdings fail the post-trade checks)"
        return _refuse(summary, why)

    trades = [{k: (_money(v) if isinstance(v, float) and k.startswith("est_") and k != "est_price" else v)
               for k, v in t.items()} for t in built["trades"]]
    summary["trades"] = trades
    summary["skipped_trades"] = [{**s, "est_value_cad": _money(s["est_value_cad"])} for s in built["skipped"]]
    summary["trades_emitted"] = bool(trades)
    summary["fx"] = _fx_block(built["conversions"], fx)
    summary["costs"] = {"commission_cad": _money(sum(t["est_commission_cad"] for t in built["trades"])),
                        "spread_cad": _money(sum(t["est_spread_cad"] for t in built["trades"])),
                        "fx_cad": _money(sum(c["cost_cad"] for c in built["conversions"])),
                        "total_cad": _money(sum(t["est_cost_cad"] for t in built["trades"])
                                            + sum(c["cost_cad"] for c in built["conversions"])),
                        "turnover_cad": _money(sum(t["est_value_cad"] for t in built["trades"])),
                        "turnover_over_nav": _r(sum(t["est_value_cad"] for t in built["trades"]) / nav, 6)}
    summary["status"] = "accepted"
    summary["unit_ledger"]["carried"] = True
    return summary


def _refuse(summary: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    summary["status"] = "refused"
    summary["refusal_reasons"] = list(reasons)
    summary["trades"] = []
    summary["skipped_trades"] = []
    summary["trades_emitted"] = False
    summary["fx"] = None
    summary["costs"] = None
    summary["post_trade"] = None
    if summary.get("decision") is not None:
        summary["decision"].setdefault("action", "none: REFUSED")
        if not summary["decision"]["action"].startswith("none: REFUSED"):
            summary["decision"]["action"] = "none: REFUSED"
    if summary.get("unit_ledger") is not None:
        summary["unit_ledger"]["carried"] = False
    return summary
