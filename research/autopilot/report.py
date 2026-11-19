"""Human-readable markdown report and JSON summary (SPEC.md section 6).

Both are pure functions of the engine summary: no clock, no paths other than the basenames already in the summary,
so identical inputs give byte-identical outputs.  The report is prose and tables for a human; it is deliberately
not in any broker, FIX or CSV-import order format.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from research.autopilot.engine import DISCLAIMER

SLEEVE_NAMES = {"EQ": "equity", "BOND": "bonds", "GOLD": "gold", "TREND": "trend (managed futures)"}


def summary_json_bytes(doc: dict[str, Any]) -> bytes:
    """Deterministic JSON serialisation of the summary (sorted keys, fixed indentation, trailing newline)."""
    return (json.dumps(doc, sort_keys=True, indent=1, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cad(x: float | None) -> str:
    return "n/a" if x is None else f"CAD {x:,.2f}"


def _num(x: float | None, nd: int = 2) -> str:
    return "n/a" if x is None else f"{x:,.{nd}f}"


def _pct(x: float | None, nd: int = 2) -> str:
    return "n/a" if x is None else f"{x * 100:.{nd}f}%"


def _pp(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:+.2f} pp"


def _short(h: str | None) -> str:
    return "n/a" if not h else f"`{h[:16]}…`"


def _cell(x: Any) -> str:
    return str(x).replace("|", "\\|").replace("\n", " ")


def _table(header: list[str], rows: list[list[Any]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return out


def _headline(s: dict[str, Any]) -> str:
    if s["status"] == "refused":
        return "**REFUSED** — no trades are proposed. The reasons are listed below."
    if s["trades"]:
        return (f"**ACCEPTED — rebalance to target proposed** ({len(s['trades'])} trade"
                f"{'s' if len(s['trades']) != 1 else ''}; sells first, then buys).")
    if s["decision"] and s["decision"]["triggered"]:
        return "**ACCEPTED — rebalance triggered, but every trade was below the minimum size or unfundable; no trades.**"
    return "**ACCEPTED — inside the drift band; no trades needed.**"


def render_markdown(s: dict[str, Any]) -> str:
    cfg = s["config"]
    L: list[str] = []
    L.append(f"# Rebalancing report — {cfg['config_id']} · {cfg['account_type']} · {s['report_date']}")
    L.append("")
    if cfg.get("label"):
        L.append(f"**{_cell(cfg['label'])}**")
        L.append("")
    L.append(f"> {DISCLAIMER}")
    L.append("")
    L.append(f"Status: {_headline(s)}")
    L.append("")
    if s["refusal_reasons"]:
        L.append("## Why this report was refused")
        L.append("")
        L += [f"- {r}" for r in s["refusal_reasons"]]
        L.append("")

    # ---- inputs
    L.append("## Inputs")
    L.append("")
    hin, pin = s["inputs"]["holdings"], s["inputs"]["prices"]
    usd = s["inputs"]["usdcad"]
    rows = [["Config", f"{cfg['config_id']} (file `{cfg['file']}`, sha256 {_short(cfg['sha256'])})"],
            ["Account type", cfg["account_type"]],
            ["Portfolio id (paper-log key)", s["portfolio_id"]],
            ["Owner drawdown tolerance", f"{cfg['owner_tolerance_pct']}%"],
            ["Holdings file", f"`{hin['file']}` as of {hin['as_of'] or 'n/a'} (sha256 {_short(hin['sha256'])})"],
            ["Declared net external flow since last accepted report",
             _cad(hin["net_external_flow_cad"]) if hin["net_external_flow_cad"] is not None else "n/a"],
            ["Price snapshot", f"version `{pin['dataset_version']}`, manifest sha256 {_short(pin['manifest_sha256'])}"
                               f"{' (REPLAY: live source not re-checked)' if pin['mode'] == 'replay' else ''}"],
            ["Price files", ", ".join(f"`{k}` {_short(v)}" for k, v in sorted(pin["files"].items())) or "n/a"],
            ["Latest price date in snapshot", pin["max_date"] or "n/a"],
            ["USD/CAD", f"{usd['rate']:.4f} ({usd['date']})" if usd else "n/a"]]
    if pin.get("pinned_manifest_sha256"):
        rows.append(["Manifest pinned by paper log", f"seq {pin['pinned_by_seq']}: {_short(pin['pinned_manifest_sha256'])}"
                     + (" (matches)" if pin["pinned_manifest_sha256"] == pin["manifest_sha256"] else " (MISMATCH)")])
    if pin.get("expected_manifest_sha256"):
        rows.append(["Expected manifest (--expect-manifest-sha256)", _short(pin["expected_manifest_sha256"])
                     + (" (matches)" if pin["expected_manifest_sha256"] == pin["manifest_sha256"] else " (MISMATCH)")])
    head = s.get("paper_log")
    if head:
        rows.append(["Paper-log position", f"entry seq {head['seq']}, chained after entry_hash "
                                           f"`{head['prev_entry_hash']}` ({head['entries_before']} earlier entries)"])
    L += _table(["Item", "Value"], rows)
    L.append("")
    L.append("### Parameter overrides (from the config file)")
    L.append("")
    if cfg["overrides"]:
        L += _table(["Parameter", "Override"], [[k, json.dumps(v, sort_keys=True)]
                                                for k, v in sorted(cfg["overrides"].items())])
    else:
        L.append("None — all declared parameters apply.")
    L.append("")

    # ---- recipe & targets
    if cfg.get("supported"):
        p = s["params"]
        L.append("## Recipe and targets")
        L.append("")
        L.append(f"Recipe: **{cfg['recipe_kind']}** (target gross exposure {cfg['target_gross']:.3f}× NAV; "
                 f"exposures " + ", ".join(f"{k} {float(v):.3f}" for k, v in cfg["exposures"].items()
                                           if float(v) != 0) + "). "
                 f"Targets = (1 − {p['cash_buffer'] * 100:.2f}% cash buffer) × recipe weights"
                 + (", buffer held in CASH.TO." if p.get("cash_buffer_vehicle") == "CASH.TO"
                    else ", buffer held as broker cash."))
        L.append("")
        trows = [[t, float(w), s["targets"].get(t)] for t, w in cfg["recipe_weights"].items()]
        if "CASH.TO" in s["targets"] and "CASH.TO" not in cfg["recipe_weights"]:
            trows.append(["CASH.TO", 0.0, s["targets"]["CASH.TO"]])
        L += _table(["Ticker", "Recipe weight", "Target weight of NAV"],
                    [[t, f"{w:.4f}", _pct(g)] for t, w, g in trows])
        if float(cfg["recipe_loan_fraction"]) > 0:
            L.append("")
            L.append(f"Recipe margin loan: {float(cfg['recipe_loan_fraction']):.3f} × NAV (the cash buffer nets "
                     f"against it, so the target loan is about {max(0.0, sum(s['targets'].values()) - 1) * 100:.2f}% "
                     f"of NAV).")
        L.append("")

    # ---- current holdings
    v = s["valuation"]
    if v is not None:
        L.append("## Current holdings, weights and drift")
        L.append("")
        dec_rows = {r["ticker"]: r for r in (s["decision"] or {}).get("rows", [])}
        rows = []
        for r in v["positions"]:
            d = dec_rows.get(r["ticker"], {})
            flags = [n for n, k in (("abs", "abs_trigger"), ("rel", "rel_trigger"), ("calendar", "calendar_trigger"))
                     if d.get(k)]
            rows.append([r["ticker"], f"{r['shares']:,}", f"{r['close']:,.4f} {r['ccy']}", r["price_date"],
                         _num(r["value_cad"]), _pct(r["weight"]), _pct(r["target"]), _pp(d.get("drift")),
                         "n/a (target 0)" if d and d.get("rel_drift") is None else _pct(d.get("rel_drift"), 1),
                         ", ".join(flags) if flags else "inside"])
        L += _table(["Ticker", "Shares", "Close", "Price date", "Value (CAD)", "Current", "Target", "Drift",
                     "Rel. drift", "Band"], rows)
        L.append("")
        L += _table(["Item", "Value"], [
            ["ETF value", _cad(v["etf_value_cad"])], ["Cash (CAD)", _cad(v["cash_cad"])],
            ["Cash (USD)", f"USD {v['cash_usd']:,.2f}"], ["Margin loan", _cad(v["margin_loan_cad"])],
            ["NAV", _cad(v["nav_cad"])],
            ["Effective gross exposure / NAV", f"{v['gross_exposure_over_nav']:.3f}"],
            ["Assets / equity", f"{v['leverage_assets_over_equity']:.3f}"],
            ["Sleeve exposure / NAV", ", ".join(f"{SLEEVE_NAMES[k]} {x:.3f}"
                                                for k, x in v["sleeve_exposure_over_nav"].items())]])
        L.append("")

    # ---- decision
    dec = s["decision"]
    if dec is not None:
        p = s["params"]
        L.append("## Band decision")
        L.append("")
        L.append(f"Rule: trade if any position's abs drift > {p['band_abs'] * 100:.2f} pp, or relative drift > "
                 f"{p['band_rel'] * 100:.0f}% of target and abs drift > {p['band_rel_min_abs'] * 100:.2f} pp"
                 + (f"; margin account: also if assets/equity differs from target by > {p['margin_leverage_band']:.2f}"
                    if cfg["account_type"] == "nonreg_margin" else "")
                 + f". Quarter-end report (months {', '.join(str(m) for m in p['calendar_months'])}): rebalance if "
                   f"any abs drift > {p['calendar_abs'] * 100:.2f} pp.")
        L.append("")
        L.append(f"- Quarter-end report: {'yes' if dec['quarter_end'] else 'no'}")
        if dec["leverage_check"]:
            L.append(f"- Margin leverage: {dec['leverage_check']}")
        if dec["triggers"]:
            for trig in dec["triggers"]:
                L.append(f"- Triggered by **{trig['kind']}**: " + "; ".join(trig["detail"]))
        else:
            L.append("- No trigger: every position is inside the band.")
        L.append(f"- Decision: **{dec.get('action') or ('full rebalance of all positions to target' if dec['triggered'] else 'no trade')}**")
        L.append("")

    # ---- trades
    if s["status"] == "accepted":
        L.append("## Proposed trades (for the owner to review; not orders)")
        L.append("")
        if s["trades"]:
            L += _table(["#", "Side", "Ticker", "Shares", "Est. price", "Est. value", "Est. value (CAD)",
                         "Est. cost (CAD)", "Note"],
                        [[i, t["side"], t["ticker"], f"{t['shares']:,}", f"{t['est_price']:,.4f} {t['ccy']}",
                          f"{t['est_value_ccy']:,.2f} {t['ccy']}", _num(t["est_value_cad"]),
                          _num(t["est_cost_cad"]), t["note"] or ""]
                         for i, t in enumerate(s["trades"], start=1)])
            L.append("")
            c = s["costs"]
            L.append(f"Estimated costs: commissions {_cad(c['commission_cad'])}, half-spread {_cad(c['spread_cad'])}, "
                     f"FX conversion {_cad(c['fx_cad'])}; total {_cad(c['total_cad'])}. Turnover "
                     f"{_cad(c['turnover_cad'])} ({_pct(c['turnover_over_nav'])} of NAV). Whole shares only; buys "
                     f"are rounded down so cash never goes negative.")
        else:
            L.append("None.")
        if s["skipped_trades"]:
            L.append("")
            L.append("Skipped:")
            L.append("")
            L += _table(["Side", "Ticker", "Shares", "Est. value (CAD)", "Reason"],
                        [[k["side"], k["ticker"], f"{k['shares']:,}", _num(k["est_value_cad"]), k["reason"]]
                         for k in s["skipped_trades"]])
        L.append("")

        fx = s["fx"]
        L.append("## FX needed")
        L.append("")
        if fx and fx["any_conversion"]:
            cu, uc = fx["cad_to_usd"], fx["usd_to_cad"]
            if cu["usd_needed"]:
                L.append(f"- Convert about {_cad(cu['cad_spent'])} to USD {cu['usd_needed']:,.2f} for "
                         f"{', '.join(cu['for'])} (broker conversion at {s['params']['fx_cost'] * 100:.2f}%: "
                         f"est. {_cad(cu['est_cost_cad'])}).")
            if uc["cad_needed"]:
                L.append(f"- Convert about USD {uc['usd_spent']:,.2f} to {_cad(uc['cad_needed'])} for "
                         f"{', '.join(uc['for'])} (est. cost {_cad(uc['est_cost_cad'])}).")
            L.append("- For large conversions, Norbert's gambit (buy DLR.TO, journal to DLR-U.TO, sell) usually costs "
                     "less than the broker rate: two commissions plus the spread, and it takes about 1–3 days.")
        else:
            L.append("No currency conversion is needed for the proposed trades.")
        L.append("")

    # ---- post-trade and checks
    pt = s["post_trade"]
    if pt is not None and "positions" in pt:
        L.append(f"## Position after trades — {pt['basis']}")
        L.append("")
        L += _table(["Ticker", "Shares", "Value (CAD)", "Weight", "Target"],
                    [[r["ticker"], f"{r['shares']:,}", _num(r["value_cad"]), _pct(r["weight"]), _pct(r["target"])]
                     for r in pt["positions"]])
        L.append("")
        L += _table(["Item", "Value"], [
            ["Cash (CAD)", _cad(pt["cash_cad"])], ["Cash (USD)", f"USD {pt['cash_usd']:,.2f}"],
            ["Margin loan", _cad(pt["margin_loan_cad"])], ["NAV", _cad(pt["nav_cad"])],
            ["Effective gross exposure / NAV", f"{pt['gross_exposure_over_nav']:.3f}"],
            ["Equity / assets", _pct(pt["equity_over_assets"])]])
        L.append("")
    cs = s.get("checked_state")
    if cs is not None and "positions" in cs:
        if cs["kind"] == "rejected_hypothetical_rebalance":
            L.append("## REJECTED hypothetical state after a full rebalance (NOT proposed)")
            L.append("")
            L.append(f"The engine computed this state ({cs['rejected_trade_count']} hypothetical trades) only to run the "
                     "post-trade checks. It failed them, so **none of these trades is proposed**; it is shown only to "
                     "explain the refusal.")
        else:
            L.append("## State checked — current holdings (no trades proposed)")
        L.append("")
        L += _table(["Ticker", "Shares", "Value (CAD)", "Weight", "Target"],
                    [[r["ticker"], f"{r['shares']:,}", _num(r["value_cad"]), _pct(r["weight"]), _pct(r["target"])]
                     for r in cs["positions"]])
        L.append("")
        L += _table(["Item", "Value"], [
            ["Cash (CAD)", _cad(cs["cash_cad"])], ["Cash (USD)", f"USD {cs['cash_usd']:,.2f}"],
            ["Margin loan", _cad(cs["margin_loan_cad"])], ["NAV", _cad(cs["nav_cad"])],
            ["Effective gross exposure / NAV", f"{cs['gross_exposure_over_nav']:.3f}"],
            ["Equity / assets", _pct(cs["equity_over_assets"])]])
        L.append("")
    if s["checks"]:
        L.append("## Checks" + (" (FAILED — see the refusal reasons)" if s["status"] == "refused" else ""))
        L.append("")
        L += _table(["Check", "Result", "Value", "Limit", "Detail"],
                    [[c["name"], "PASS" if c["ok"] else "FAIL", json.dumps(c["value"], sort_keys=True),
                      json.dumps(c["limit"], sort_keys=True), c["detail"]] for c in s["checks"]])
        L.append("")

    # ---- drawdown
    dd, led = s["drawdown"], s["unit_ledger"]
    L.append("## Drawdown vs tolerance")
    L.append("")
    if dd and led:
        L += _table(["Item", "Value"], [
            ["Unit value (NAV / units)", f"{led['unit_value']:,.4f}"], ["Units", f"{led['units']:,.6f}"],
            ["Running peak (paper log)", f"{led['peak']:,.4f}"],
            ["Previous accepted report", led["prior_report_date"] or "none (units initialised here)"],
            ["Flow applied to units", _cad(led["flow_applied_cad"])],
            ["Drawdown from peak", _pct(dd["drawdown"])],
            ["Owner tolerance", _pct(dd["tolerance"], 0)],
            ["Drawdown / tolerance", _pct(dd["fraction_of_tolerance"], 1)],
            ["Alert", dd["alert"]]])
        L.append("")
        L.append("Alert levels: INFO at ≥ 50% of tolerance, WARNING at ≥ 75%, BREACH at ≥ 100%. "
                 f"{dd['policy']}"
                 + ("" if led.get("carried") else " (This run was refused, so it does not update the unit ledger.)"))
    else:
        L.append("Not computed (the inputs could not be valued).")
    L.append("")

    if s["notes"]:
        L.append("## Notes")
        L.append("")
        L += [f"- {n}" for n in s["notes"]]
        L.append("")
    L.append("---")
    L.append(f"Engine schema `{s['schema']}`. Deterministic: the report date is an input and no wall-clock time "
             "appears here. Nothing in this report is a recommendation to trade.")
    return "\n".join(L) + "\n"
