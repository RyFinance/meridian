"""SPEC section 7: monthly historical replay of the REAL autopilot engine on synthetic ETF prices (descriptive).

For each (config, account type, start capital) the replay starts with all-CAD cash on the first month-end of the
frozen synthetic panel (``research.autopilot.synth_prices``, snapshot ``autopilot_replay_synth_v2``) and, every
month-end, does exactly what an owner would do:

1. writes a holdings JSON (as-of = report date, no external flows) and parses it with the engine's own parser;
2. runs ``research.autopilot.engine.evaluate`` on the verified snapshot, presented point-in-time (only price rows
   dated on or before the report date; otherwise every historical report would be refused as future-dated, §5);
3. renders the markdown report and appends a hash-chained paper-log entry (``paperlog.make_entry``) to an
   in-memory chain, which is written to a throwaway log and re-validated with ``paperlog.read_chain`` at the end
   (the chain drives the engine's unit ledger and drawdown alerts);
4. if accepted, fills every proposed trade at that month-end's synthetic close with the declared cost model
   (half-spread, commission, FX conversion cost), replaying the engine's own ``fund`` routine in trade order, and
   checks the result against the engine's post-trade estimate;
5. carries the positions to the next month-end, crediting positive CAD cash at the cycle-8 CASH rate, charging a
   CAD margin loan at the cycle-8 MRATE and crediting USD cash at RF_USD; balances are kept in cents.

Refused months propose no trades, so holdings simply carry forward.  Nothing here is a recommendation to trade,
and nothing is written outside ``--out`` (plus the throwaway logs, in a temporary directory unless ``--log-dir``).
"""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import io
import json
import math
import tempfile
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from research.autopilot import synth_prices
from research.autopilot.config import CONFIGS, USDCAD, borrow_capacity_fraction, parse_config, strict_json_loads
from research.autopilot.engine import CASH_EPS, EngineInputs, evaluate, fund, value_state
from research.autopilot.holdings import parse_holdings
from research.autopilot.paperlog import canonical, guard_path, make_entry, read_chain, sha256_hex
from research.autopilot.prices import PriceData, load_prices
from research.autopilot.report import render_markdown

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "reports" / "cycle9" / "autopilot"
ITEM_RETURNS = REPO / "reports" / "cycle8_max_return" / "out" / "item_returns_monthly.parquet"
ANSWER = REPO / "reports" / "cycle8_max_return" / "out" / "answer.csv"

TFSA_CONFIGS = tuple(CONFIGS)                               # all 8 supported configs
MARGIN_CONFIGS = ("P3@1.25", "P3@1.5", "P4@1.25", "P4@1.5", "P6a@1.25")
STARTS_CAD = (100_000.0, 25_000.0)
DEFAULT_TOLERANCE_PCT = 50                                  # configs not eligible at any cycle-8 tolerance
CENT = 0.01

BY_YEAR_COLUMNS = ["config", "account", "start_cad", "year", "band_events", "calendar_events", "trades",
                   "turnover_pct_nav", "est_cost_cad", "est_cost_bps", "fx_converted_cad", "alerts_info",
                   "alerts_warning", "alerts_breach", "refusals"]
SUMMARY_COLUMNS = [
    "config", "account", "start_cad", "owner_tolerance_pct", "first_report", "last_report", "reports",
    "return_months", "years", "reports_accepted", "band_events", "calendar_events", "trades", "turnover_pct_nav",
    "est_cost_cad", "est_cost_bps", "fx_converted_cad", "alerts_info", "alerts_warning", "alerts_breach", "refusals",
    "initial_turnover_pct_nav", "initial_est_cost_cad",
    "avg_band_events_per_year_ex_initial", "avg_calendar_events_per_year", "avg_trades_per_year_ex_initial",
    "avg_turnover_pct_nav_per_year_ex_initial", "avg_est_cost_cad_per_year_ex_initial",
    "avg_est_cost_bps_per_year_ex_initial", "avg_fx_converted_cad_per_year_ex_initial", "avg_refusals_per_year",
    "avg_cash_pct_nav", "end_nav_cad", "replay_cagr", "replay_max_dd", "cycle8_ideal_cagr", "cycle8_ideal_max_dd",
    "replay_minus_ideal_cagr", "main_refusal_reason"]
MONTHLY_COLUMNS = ["config", "account", "start_cad", "report_date", "status", "triggers", "trades", "skipped",
                   "turnover_cad", "est_cost_cad", "fx_converted_cad", "nav_pre_cad", "nav_post_cad", "cash_cad",
                   "cash_usd", "margin_loan_cad", "cash_pct_nav", "alert", "drawdown", "refusal"]


class ReplayError(RuntimeError):
    """The replay's own bookkeeping disagrees with the engine (a bug, never a data condition)."""


# ------------------------------------------------------------------------------------------------ inputs -----------
def replay_matrix(start_values: tuple[float, ...] = STARTS_CAD) -> list[tuple[str, str, float]]:
    pairs = [(c, "tfsa") for c in TFSA_CONFIGS] + [(c, "nonreg_margin") for c in MARGIN_CONFIGS]
    return [(c, a, s) for s in start_values for c, a in pairs]


def owner_tolerances(answer_path: Path = ANSWER) -> dict[str, int]:
    """Owner tolerance per config: the tightest cycle-8 tolerance (answer.csv) under which the config was eligible;
    DEFAULT_TOLERANCE_PCT (50) for configs that were eligible at none.  Used only for the descriptive alerts."""
    out = {c: DEFAULT_TOLERANCE_PCT for c in CONFIGS}
    with open(answer_path, newline="") as fh:
        rows = sorted(csv.DictReader(fh), key=lambda r: int(r["tolerance"]), reverse=True)
    for row in rows:                        # loosest first, so the tightest eligible level wins
        for c in row["eligible"].split(";"):
            if c in out:
                out[c] = int(row["tolerance"])
    return out


def load_carry(start: str = synth_prices.START, end: str = synth_prices.END) -> dict[date, dict[str, float]]:
    """Cycle-8 monthly CASH (CAD cash), MRATE (margin loan) and RF_USD (USD cash) for each month-end."""
    M = synth_prices.load_sleeves()[0].loc[start:end, ["CASH", "MRATE", "RF_USD"]]
    if M.isna().any().any():
        raise ValueError("missing cycle-8 carry rates in the replay window")
    return {ts.date(): {k: float(v) for k, v in row.items()} for ts, row in M.iterrows()}


class PointInTime:
    """Point-in-time views of a verified PriceData: only rows dated on or before the report date."""

    def __init__(self, prices: PriceData):
        self.prices = prices
        self.dates = {t: [r[0] for r in rows] for t, rows in prices.series.items()}

    def at(self, d: date) -> PriceData:
        series = {}
        for t, rows in self.prices.series.items():
            k = bisect.bisect_right(self.dates[t], d)
            if k:
                series[t] = rows[:k]
        if not series:
            raise ValueError(f"no prices on or before {d}")
        return replace(self.prices, series=series, max_date=max(rows[-1][0] for rows in series.values()))

    def report_dates(self) -> list[date]:
        return sorted(set(self.dates[USDCAD]))

    def closes(self, d: date) -> tuple[dict[str, dict[str, Any]], float]:
        px = {}
        for t, rows in self.prices.series.items():
            k = bisect.bisect_right(self.dates[t], d)
            if k and t != USDCAD:
                row = rows[k - 1]
                px[t] = {"close": float(row[1]), "ccy": row[2], "date": row[0].isoformat()}
        fx_rows = self.prices.series[USDCAD]
        return px, float(fx_rows[bisect.bisect_right(self.dates[USDCAD], d) - 1][1])


# ------------------------------------------------------------------------------------------------ one replay -------
def _cents(x: float) -> float:
    v = round(x, 2)
    return 0.0 if v == 0 else v


def _clean(x: float) -> float:
    return 0.0 if abs(x) <= CASH_EPS else x


@dataclass
class Account:
    shares: dict[str, int]
    cad: float          # net CAD balance; negative = margin loan
    usd: float


def holdings_bytes(acct: Account, as_of: date, margin: bool) -> bytes:
    raw: dict[str, Any] = {"as_of": as_of.isoformat(), "cash_cad": _cents(max(0.0, acct.cad)),
                           "cash_usd": _cents(acct.usd), "net_external_flow_cad": 0,
                           "positions": {t: n for t, n in sorted(acct.shares.items()) if n > 0}}
    if margin:
        raw["margin_loan_cad"] = _cents(max(0.0, -acct.cad))
    return (json.dumps(raw, sort_keys=True, indent=1) + "\n").encode("utf-8")


def accrue(acct: Account, rates: dict[str, float]) -> Account:
    cad = acct.cad * (1.0 + (rates["CASH"] if acct.cad > 0 else rates["MRATE"]))
    usd = acct.usd * (1.0 + rates["RF_USD"])
    return Account(dict(acct.shares), _cents(cad), _cents(usd))


def apply_fills(acct: Account, s: dict[str, Any], px: dict[str, dict[str, Any]], fx: float,
                cad_floor: float) -> tuple[Account, float]:
    """Fill the engine's proposed trades at the report-date closes with the declared cost model, in trade order.
    Returns (new account, CAD value of currency converted)."""
    p = s["params"]
    hs, commission, fx_cost = p["half_spread"], float(p["commission_cad"]), float(p["fx_cost"])
    shares = dict(acct.shares)
    pools = {"CAD": acct.cad, "USD": acct.usd}
    converted = 0.0
    for t in s["trades"]:
        tk, q = t["ticker"], int(t["shares"])
        close, ccy = px[tk]["close"], px[tk]["ccy"]
        comm = commission / fx if ccy == "USD" else commission
        if t["side"] == "SELL":
            if q > shares.get(tk, 0):
                raise ReplayError(f"engine proposed selling {q} {tk} but only {shares.get(tk, 0)} are held")
            pools[ccy] = _clean(pools[ccy] + q * close * (1.0 - hs[tk]) - comm)
            shares[tk] = shares.get(tk, 0) - q
        else:
            funded = fund(pools, ccy, q * close * (1.0 + hs[tk]) + comm, fx, fx_cost, cad_floor)
            if funded is None:
                raise ReplayError(f"engine proposed an unfundable buy of {q} {tk} on {s['report_date']}")
            pools, conv = funded
            if conv is not None:
                converted += conv["amount_from"] * (1.0 if conv["from"] == "CAD" else fx)
            shares[tk] = shares.get(tk, 0) + q
    return Account({t: n for t, n in shares.items() if n != 0}, pools["CAD"], pools["USD"]), converted


def _nav(acct: Account, px: dict[str, dict[str, Any]], fx: float) -> float:
    tickers = sorted(acct.shares)
    return value_state(acct.shares, px, fx, acct.cad, acct.usd, tickers)["nav"]


def _check_post_trade(s: dict[str, Any], acct: Account) -> None:
    pt = s["post_trade"]
    if pt is None or "positions" not in pt:
        return
    est = {r["ticker"]: r["shares"] for r in pt["positions"] if r["shares"]}
    if est != {t: n for t, n in acct.shares.items() if n}:
        raise ReplayError(f"{s['report_date']}: filled shares {acct.shares} differ from engine estimate {est}")
    for name, mine in (("cash_cad", max(0.0, acct.cad)), ("cash_usd", acct.usd),
                       ("margin_loan_cad", max(0.0, -acct.cad))):
        if abs(pt[name] - mine) > 0.011:
            raise ReplayError(f"{s['report_date']}: filled {name} {mine:.4f} differs from engine {pt[name]}")


def run_one(config_id: str, account_type: str, start_cad: float, pit: PointInTime,
            carry: dict[date, dict[str, float]], dates: list[date], *, tolerance_pct: int,
            log_path: Path | None = None) -> dict[str, Any]:
    """Replay one config/account/start over ``dates``; returns monthly rows plus the chain length."""
    margin = account_type == "nonreg_margin"
    portfolio_id = f"replay|{config_id}|{account_type}|{int(start_cad)}"
    cfg_bytes = canonical({"config_id": config_id, "account_type": account_type,
                           "owner_tolerance_pct": tolerance_pct, "portfolio_id": portfolio_id})
    cfg = parse_config(strict_json_loads(cfg_bytes.decode("utf-8")))
    cfg_sha = sha256_hex(cfg_bytes)
    acct = Account({}, float(start_cad), 0.0)
    chain: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for i, rd in enumerate(dates):
        if i:
            acct = accrue(acct, carry[rd])
        hb = holdings_bytes(acct, rd, margin)
        h = parse_holdings(hb, fmt="json")
        acct = Account(dict(h.positions), h.cash_cad - h.margin_loan_cad, h.cash_usd)   # exactly what the file says
        prices = pit.at(rd)
        inp = EngineInputs(config=cfg, config_file="config.json", config_sha256=cfg_sha, holdings=h,
                           holdings_error=None, holdings_file=f"holdings_{rd.isoformat()}.json",
                           holdings_sha256=h.sha256, prices=prices, price_error=None,
                           price_version=prices.dataset_version, report_date=rd)
        s = evaluate(inp, chain)
        report = render_markdown(s).encode("utf-8")
        doc = {**s, "report_file": f"report_{rd.isoformat()}_{config_id}.md", "report_sha256": sha256_hex(report)}
        chain.append(make_entry(doc, chain))

        px, fx = pit.closes(rd)
        nav_pre = _nav(acct, px, fx)
        converted = 0.0
        turnover = 0.0
        cost = 0.0
        if s["status"] == "accepted" and s["trades"]:
            capacity = borrow_capacity_fraction(cfg) * nav_pre
            acct, converted = apply_fills(acct, s, px, fx, -capacity if capacity > 0 else 0.0)
            _check_post_trade(s, acct)
            turnover = sum(q["shares"] * px[q["ticker"]]["close"] * (fx if px[q["ticker"]]["ccy"] == "USD" else 1.0)
                           for q in s["trades"])
            cost = float(s["costs"]["total_cad"])
        acct = Account(acct.shares, _cents(acct.cad), _cents(acct.usd))
        if not margin and acct.cad < 0:
            raise ReplayError(f"{rd}: negative CAD cash {acct.cad} in a {account_type} account")
        nav_post = _nav(acct, px, fx)
        if abs((nav_pre - nav_post) - cost) > 0.02 + 1e-9 * nav_pre:
            raise ReplayError(f"{rd}: realised fill cost {nav_pre - nav_post:.4f} differs from estimate {cost:.2f}")
        kinds = [t["kind"] for t in (s["decision"] or {}).get("triggers", [])] if s["decision"] else []
        dd = s["drawdown"]
        rows.append({"config": config_id, "account": account_type, "start_cad": int(start_cad),
                     "report_date": rd.isoformat(), "status": s["status"], "triggers": "+".join(kinds),
                     "trades": len(s["trades"]), "skipped": len(s["skipped_trades"]), "turnover_cad": turnover,
                     "est_cost_cad": cost, "fx_converted_cad": converted, "nav_pre_cad": nav_pre,
                     "nav_post_cad": nav_post, "cash_cad": max(0.0, acct.cad), "cash_usd": acct.usd,
                     "margin_loan_cad": max(0.0, -acct.cad),
                     "cash_pct_nav": 100.0 * (max(0.0, acct.cad) + max(0.0, acct.usd) * fx) / nav_post,
                     "alert": dd["alert"] if dd else "",
                     "drawdown": dd["drawdown"] if dd else None,
                     "refusal": s["refusal_reasons"][0] if s["refusal_reasons"] else ""})
    if log_path is not None:
        log_path = guard_path(Path(log_path))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_bytes(b"".join(canonical(e) + b"\n" for e in chain))
        if [e["entry_hash"] for e in read_chain(log_path)] != [e["entry_hash"] for e in chain]:
            raise ReplayError(f"throwaway log {log_path} failed validation")
    return {"rows": rows, "chain_length": len(chain), "last_entry_hash": chain[-1]["entry_hash"] if chain else None}


# ------------------------------------------------------------------------------------------------ aggregation ------
def _event_kind(triggers: str, status: str) -> str | None:
    if status != "accepted" or not triggers:
        return None
    kinds = set(triggers.split("+"))
    return "band" if kinds & {"band", "margin_leverage"} else "calendar"


def by_year(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: dict[tuple, dict[str, Any]] = {}
    for r in rows:
        key = (r["config"], r["account"], r["start_cad"], int(r["report_date"][:4]))
        y = out.setdefault(key, {"config": key[0], "account": key[1], "start_cad": key[2], "year": key[3],
                                 "band_events": 0, "calendar_events": 0, "trades": 0, "turnover_pct_nav": 0.0,
                                 "est_cost_cad": 0.0, "est_cost_bps": 0.0, "fx_converted_cad": 0.0,
                                 "alerts_info": 0, "alerts_warning": 0, "alerts_breach": 0, "refusals": 0})
        kind = _event_kind(r["triggers"], r["status"])
        if kind:
            y[f"{kind}_events"] += 1
        y["trades"] += r["trades"]
        y["turnover_pct_nav"] += 100.0 * r["turnover_cad"] / r["nav_pre_cad"]
        y["est_cost_cad"] += r["est_cost_cad"]
        y["est_cost_bps"] += 1e4 * r["est_cost_cad"] / r["nav_pre_cad"]
        y["fx_converted_cad"] += r["fx_converted_cad"]
        if r["alert"] in ("INFO", "WARNING", "BREACH"):
            y[f"alerts_{r['alert'].lower()}"] += 1
        y["refusals"] += r["status"] == "refused"
    return [out[k] for k in sorted(out, key=lambda k: (k[2] != 100_000, _order(k[0], k[1]), k[3]))]


def _order(config_id: str, account: str) -> int:
    pairs = [(c, "tfsa") for c in TFSA_CONFIGS] + [(c, "nonreg_margin") for c in MARGIN_CONFIGS]
    return pairs.index((config_id, account)) if (config_id, account) in pairs else len(pairs)


def _cagr_dd(values: list[float], months: int) -> tuple[float, float]:
    peak, mdd = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        mdd = max(mdd, 1.0 - v / peak)
    return (values[-1] / values[0]) ** (12.0 / months) - 1.0, mdd


def ideal_series(config_id: str, dates: list[date], item_path: Path = ITEM_RETURNS) -> tuple[float, float] | None:
    import pandas as pd  # local: only the summary needs it

    items = pd.read_parquet(item_path)
    if config_id not in items.columns:
        return None
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates[1:]])
    r = items[config_id].reindex(idx)
    if r.isna().any():
        return None
    level = [1.0]
    for x in r:
        level.append(level[-1] * (1.0 + float(x)))
    return _cagr_dd(level, len(dates) - 1)


def summarise(rows: list[dict[str, Any]], tolerance: dict[str, int], ideal: dict[str, tuple[float, float] | None],
              ) -> list[dict[str, Any]]:
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault((r["config"], r["account"], r["start_cad"]), []).append(r)
    out = []
    for (c, a, s0), g in sorted(groups.items(), key=lambda kv: (kv[0][2] != 100_000, _order(kv[0][0], kv[0][1]))):
        g = sorted(g, key=lambda r: r["report_date"])
        months = len(g) - 1
        years = months / 12.0
        yrs = by_year(g)
        tot = {k: sum(y[k] for y in yrs) for k in BY_YEAR_COLUMNS[4:]}
        first = g[0]
        init = {"band": 1 if _event_kind(first["triggers"], first["status"]) == "band" else 0,
                "trades": first["trades"], "turnover": 100.0 * first["turnover_cad"] / first["nav_pre_cad"],
                "cost": first["est_cost_cad"], "bps": 1e4 * first["est_cost_cad"] / first["nav_pre_cad"],
                "fx": first["fx_converted_cad"]}
        # the start value is the cash before the first report; costs of the first month's trades are included
        values = [float(s0)] + [r["nav_post_cad"] for r in g]
        cagr, mdd = _cagr_dd(values, months) if months else (0.0, 0.0)
        idl = ideal.get(c)
        reasons = Counter(r["refusal"] for r in g if r["status"] == "refused")
        out.append({
            "config": c, "account": a, "start_cad": s0, "owner_tolerance_pct": tolerance[c],
            "first_report": g[0]["report_date"], "last_report": g[-1]["report_date"], "reports": len(g),
            "return_months": months, "years": years,
            "reports_accepted": sum(r["status"] == "accepted" for r in g), **tot,
            "initial_turnover_pct_nav": init["turnover"], "initial_est_cost_cad": init["cost"],
            "avg_band_events_per_year_ex_initial": (tot["band_events"] - init["band"]) / years,
            "avg_calendar_events_per_year": tot["calendar_events"] / years,
            "avg_trades_per_year_ex_initial": (tot["trades"] - init["trades"]) / years,
            "avg_turnover_pct_nav_per_year_ex_initial": (tot["turnover_pct_nav"] - init["turnover"]) / years,
            "avg_est_cost_cad_per_year_ex_initial": (tot["est_cost_cad"] - init["cost"]) / years,
            "avg_est_cost_bps_per_year_ex_initial": (tot["est_cost_bps"] - init["bps"]) / years,
            "avg_fx_converted_cad_per_year_ex_initial": (tot["fx_converted_cad"] - init["fx"]) / years,
            "avg_refusals_per_year": tot["refusals"] / years,
            "avg_cash_pct_nav": sum(r["cash_pct_nav"] for r in g) / len(g),
            "end_nav_cad": g[-1]["nav_post_cad"], "replay_cagr": cagr, "replay_max_dd": mdd,
            "cycle8_ideal_cagr": idl[0] if idl else None, "cycle8_ideal_max_dd": idl[1] if idl else None,
            "replay_minus_ideal_cagr": (cagr - idl[0]) if idl else None,
            "main_refusal_reason": reasons.most_common(1)[0][0] if reasons else ""})
    return out


# ------------------------------------------------------------------------------------------------ output -----------
MONEY_COLUMNS = {"turnover_cad", "est_cost_cad", "fx_converted_cad", "nav_pre_cad", "nav_post_cad", "cash_cad",
                 "cash_usd", "margin_loan_cad", "end_nav_cad", "initial_est_cost_cad",
                 "avg_est_cost_cad_per_year_ex_initial", "avg_fx_converted_cad_per_year_ex_initial"}


def _fmt(v: Any, column: str) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        if not math.isfinite(v):
            raise ValueError(f"non-finite value in replay output column {column}")
        out = f"{v:.2f}" if column in MONEY_COLUMNS else f"{v:.6f}"
        return "0.00" if out == "-0.00" else ("0.000000" if out == "-0.000000" else out)
    return str(v)


def csv_bytes(rows: list[dict[str, Any]], columns: list[str]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(columns)
    for r in rows:
        w.writerow([_fmt(r[c], c) for c in columns])
    return buf.getvalue().encode("utf-8")


def _write(path: Path, data: bytes) -> None:
    path = guard_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def run(*, store: Path = synth_prices.STORE, version: str = synth_prices.VERSION, out: Path = OUT_DIR,
        start: str | None = None, end: str | None = None, matrix: list[tuple[str, str, float]] | None = None,
        log_dir: Path | None = None, item_path: Path = ITEM_RETURNS, answer_path: Path = ANSWER,
        monthly: bool = True) -> dict[str, Any]:
    """Run the replay matrix and write replay_by_year.csv, replay_summary.csv (+ replay_monthly.csv, meta)."""
    guard_path(Path(out) / "replay_summary.csv")          # refuse a forbidden output directory before any work
    prices, err = load_prices(Path(store), version)
    if prices is None:
        raise ReplayError(f"replay price snapshot refused: {err}")
    pit = PointInTime(prices)
    dates = [d for d in pit.report_dates() if (start is None or d.isoformat()[:7] >= start)
             and (end is None or d.isoformat()[:7] <= end)]
    if len(dates) < 2:
        raise ReplayError("replay window needs at least two month-ends")
    carry = load_carry(dates[0].isoformat()[:7], dates[-1].isoformat()[:7])
    tolerance = owner_tolerances(answer_path)
    matrix = matrix if matrix is not None else replay_matrix()
    rows: list[dict[str, Any]] = []
    runs = []
    with tempfile.TemporaryDirectory(prefix="autopilot_replay_logs_") as tmp:
        logs = Path(log_dir) if log_dir is not None else Path(tmp)
        for config_id, account, s0 in matrix:
            log = logs / f"paper_log_{config_id}_{account}_{int(s0)}.jsonl"
            res = run_one(config_id, account, s0, pit, carry, dates, tolerance_pct=tolerance[config_id],
                          log_path=log)
            rows.extend(res["rows"])
            runs.append({"config": config_id, "account": account, "start_cad": int(s0),
                         "log_entries": res["chain_length"], "last_entry_hash": res["last_entry_hash"]})
    ideal = {c: ideal_series(c, dates, item_path) for c in sorted({m[0] for m in matrix})}
    yearly = by_year(rows)
    summary = summarise(rows, tolerance, ideal)
    out = Path(out)
    files = {"replay_by_year.csv": csv_bytes(yearly, BY_YEAR_COLUMNS),
             "replay_summary.csv": csv_bytes(summary, SUMMARY_COLUMNS)}
    if monthly:
        files["replay_monthly.csv"] = csv_bytes(rows, MONTHLY_COLUMNS)
    meta = {"kind": "autopilot_replay", "price_snapshot": {"version": version,
                                                           "manifest_sha256": prices.manifest_sha256,
                                                           "files": prices.file_sha256},
            "window": {"first_report": dates[0].isoformat(), "last_report": dates[-1].isoformat(),
                       "reports": len(dates)},
            "owner_tolerance_pct": tolerance, "runs": runs,
            "cycle8_item_returns_sha256": hashlib.sha256(Path(item_path).read_bytes()).hexdigest(),
            "code_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted(Path(__file__).parent.glob("*.py"))},
            "outputs_sha256": {k: hashlib.sha256(v).hexdigest() for k, v in sorted(files.items())},
            "conventions": CONVENTIONS}
    files["replay_meta.json"] = (json.dumps(meta, sort_keys=True, indent=1) + "\n").encode("utf-8")
    for name, data in files.items():
        _write(out / name, data)
    return {"rows": rows, "by_year": yearly, "summary": summary, "meta": meta, "files": sorted(files)}


CONVENTIONS = [
    "Start: all cash (CAD) on the first report date; that first report's purchase counts as a band event and is "
    "reported separately (initial_*) and excluded from the *_ex_initial per-year averages.",
    "band_events: accepted reports triggered by the drift band or (margin) the assets/equity band; "
    "calendar_events: accepted reports triggered only by the quarter-end calendar check.",
    "turnover_pct_nav and est_cost_bps: sums over reports of traded value / pre-trade NAV and estimated cost / "
    "pre-trade NAV; est_cost_cad: half-spread + commission + FX conversion cost as estimated by the engine (fills "
    "use the same cost model, and the realised NAV change is checked against the estimate).",
    "fx_converted_cad: CAD value of currency converted to fund buys (CAD->USD at the amount of CAD spent, USD->CAD "
    "at the USD spent times USDCAD).",
    "alerts_*: number of monthly reports whose drawdown alert was at that level (unit value vs running peak of "
    "accepted reports in the throwaway paper log).",
    "Carry between reports: positive CAD cash earns cycle-8 CASH, a CAD margin loan costs cycle-8 MRATE, USD cash "
    "earns cycle-8 RF_USD; balances are rounded to cents each month (holdings files carry cents).",
    "replay_cagr / replay_max_dd: on month-end NAV after the month's fills, from the start cash; cycle8_ideal_*: "
    "the cycle-8 item (item_returns_monthly.parquet, same config id) compounded over the same return months.",
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m research.autopilot.replay",
                                 description="SPEC section 7 historical replay (descriptive research only).")
    ap.add_argument("--store", type=Path, default=synth_prices.STORE)
    ap.add_argument("--version", default=synth_prices.VERSION)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--start", default=None, help="first report month YYYY-MM (default: panel start)")
    ap.add_argument("--end", default=None, help="last report month YYYY-MM (default: panel end)")
    ap.add_argument("--log-dir", type=Path, default=None, help="keep throwaway paper logs here (default: temp dir)")
    args = ap.parse_args(argv)
    res = run(store=args.store, version=args.version, out=args.out, start=args.start, end=args.end,
              log_dir=args.log_dir)
    print(f"replay: {len(res['summary'])} runs, {len(res['rows'])} monthly reports; wrote {res['files']} to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
