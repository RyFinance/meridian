"""Rebalancing autopilot engine (research/autopilot/SPEC.md).  Synthetic inputs only: no market data, no network,
no existing research artifacts, and never the forward registry."""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import random
import shutil
import socket
import subprocess
import sys
from dataclasses import replace
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path

import pytest

from research.autopilot import cli, paperlog
from research.autopilot.config import (CONFIGS, DECLARED, MARGIN, STACKED, UNIVERSE, parse_config, position_cap,
                                       recipe_exposures, recipe_for, target_weights)
from research.autopilot.engine import (EngineInputs, band_decision, build_trades, evaluate, fund, is_quarter_end,
                                       recipe_cap_conflicts, risk_checks, value_state)
from research.autopilot.holdings import HoldingsError, parse_holdings
from research.autopilot.paperlog import PaperLogError, guard_path, make_entry, read_chain
from research.autopilot.prices import PriceData, freeze_price_csv, parse_price_csv
from research.autopilot.report import render_markdown

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "research" / "autopilot"
RD = date(2026, 8, 26)          # not a quarter-end month
QE = date(2026, 9, 28)          # quarter-end month (September)
FX = 1.35
PRICES = {"XEQT.TO": (30.0, "CAD"), "ZAG.TO": (14.0, "CAD"), "ZGLD.TO": (20.0, "CAD"), "DBMF": (28.0, "USD"),
          "RSSB": (25.0, "USD"), "RSST": (30.0, "USD"), "GDE": (35.0, "USD"), "SSO": (90.0, "USD"),
          "CASH.TO": (50.0, "CAD")}


# ------------------------------------------------------------------------------------------------ helpers ----------
def price_rows(d: date, *, prices=PRICES, fx=FX, drop=(), extra=()):
    rows = [(d, t, c, ccy) for t, (c, ccy) in sorted(prices.items()) if t not in drop]
    if "USDCAD" not in drop:
        rows.append((d, "USDCAD", fx, "CAD"))
    return rows + list(extra)


def csv_bytes(rows) -> bytes:
    lines = ["date,ticker,close,currency"] + [f"{d.isoformat()},{t},{c!r},{ccy}" for d, t, c, ccy in rows]
    return ("\n".join(lines) + "\n").encode()


def price_data(rows) -> PriceData:
    data = csv_bytes(rows)
    series, max_date = parse_price_csv(data)
    sha = hashlib.sha256(data).hexdigest()
    return PriceData(dataset_version="unit", manifest_sha256="f" * 64, keys=("prices/p.csv",),
                     file_sha256={"prices/p.csv": sha}, mode="verified", series=series, max_date=max_date)


def cfg_of(config_id="P3@1.0", account_type="tfsa", tol=35, overrides=None, **extra):
    raw = {"config_id": config_id, "account_type": account_type, "owner_tolerance_pct": tol, **extra}
    if overrides is not None:
        raw["overrides"] = overrides
    return raw


def price_cad(t, prices=PRICES, fx=FX):
    c, ccy = prices[t]
    return c * (fx if ccy == "USD" else 1.0)


def holdings_for(weights, *, nav=100_000.0, as_of=RD, prices=PRICES, fx=FX, loan=0.0, cash_usd=0.0, flow=0.0,
                 margin=False, extra=None):
    positions, etf = {}, 0.0
    for t, w in sorted(weights.items()):
        n = round(w * nav / price_cad(t, prices, fx))
        positions[t] = n
        etf += n * price_cad(t, prices, fx)
    cash_cad = nav + loan - etf - cash_usd * fx
    assert cash_cad >= -1e-6, cash_cad
    h = {"as_of": as_of.isoformat(), "cash_cad": round(max(cash_cad, 0.0), 2), "cash_usd": cash_usd,
         "net_external_flow_cad": flow, "positions": positions}
    if margin:
        h["margin_loan_cad"] = loan
    h.update(extra or {})
    return h


def targets(config_id, account_type="tfsa", overrides=None):
    return target_weights(parse_config(cfg_of(config_id, account_type, overrides=overrides)))


def inputs(cfg_raw, hold_raw, rows, rd=RD) -> EngineInputs:
    cfg = parse_config(cfg_raw)
    try:
        h, err = parse_holdings(json.dumps(hold_raw).encode(), fmt="json"), None
    except HoldingsError as exc:
        h, err = None, str(exc)
    return EngineInputs(config=cfg, config_file="config.json", config_sha256="c" * 64, holdings=h,
                        holdings_error=err, holdings_file="holdings.json", holdings_sha256="h" * 64,
                        prices=price_data(rows), price_error=None, price_version="unit", report_date=rd)


def run_eval(cfg_raw, hold_raw, rows=None, rd=RD, chain=()):
    return evaluate(inputs(cfg_raw, hold_raw, price_rows(rd) if rows is None else rows, rd), list(chain))


def assert_refused(s, *needles):
    assert s["status"] == "refused"
    assert s["trades"] == [] and s["trades_emitted"] is False
    text = " ".join(s["refusal_reasons"])
    for n in needles:
        assert n in text, (n, s["refusal_reasons"])


def snapshot(tmp_path, rows, version="p1"):
    src = tmp_path / f"src_{version}"
    src.mkdir()
    (src / "prices.csv").write_bytes(csv_bytes(rows))
    store = tmp_path / "store"
    freeze_price_csv(src / "prices.csv", store, version, source="synthetic_test", source_identifier="test://prices",
                     retrieved_at="2026-09-01T12:00:00+00:00")
    return store, version, src / "prices.csv"


def write_inputs(d: Path, cfg_raw, hold_raw, *, holdings_name="holdings.json"):
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text(json.dumps(cfg_raw))
    (d / holdings_name).write_text(json.dumps(hold_raw) if holdings_name.endswith(".json") else hold_raw)
    return d / "config.json", d / holdings_name


def cli_args(cfg_path, hold_path, store, version, rd, out, log, *more):
    return ["--config", str(cfg_path), "--holdings", str(hold_path), "--price-store", str(store),
            "--price-version", version, "--report-date", rd.isoformat(), "--out", str(out), "--log", str(log), *more]


def load_summary(out: Path) -> dict:
    (path,) = sorted(out.glob("summary_*.json"))
    return json.loads(path.read_text())


# ------------------------------------------------------------------------------------------------ recipes ----------
@pytest.mark.parametrize("config_id", sorted(CONFIGS))
def test_recipes_reproduce_exposures_exactly(config_id):
    exp = CONFIGS[config_id]["exposures"]
    L = CONFIGS[config_id]["L"]
    stacked = STACKED[config_id]
    assert sum(stacked.values(), Fraction(0)) == 1
    assert recipe_exposures(stacked) == exp
    margin = dict(MARGIN[config_id])
    loan = margin.pop("loan")
    assert sum(margin.values(), Fraction(0)) == L
    assert loan == L - 1
    assert recipe_exposures(margin) == exp
    assert "SSO" not in margin and "GDE" not in stacked and "GDE" not in margin
    for kind_acct in ("tfsa", "rrsp", "nonreg_cash"):
        assert recipe_for(config_id, kind_acct)[2] == "stacked"
    assert recipe_for(config_id, "nonreg_margin")[1] == L - 1


def test_config_table_matches_spec_section_1():
    assert sorted(CONFIGS) == sorted(["P3@1.0", "P3@1.25", "P3@1.5", "P4@1.0", "P4@1.25", "P4@1.5",
                                      "P6a@1.0", "P6a@1.25"])
    assert {t for c in STACKED.values() for t in c if t == "SSO"} == {"SSO"}
    assert [c for c, r in STACKED.items() if "SSO" in r] == ["P6a@1.25"]
    # P6a@1.25 holds RSST at 0.99 x 0.625 = 61.875% of NAV (under the 65% cap)
    assert targets("P6a@1.25")["RSST"] == pytest.approx(0.61875)


@pytest.mark.parametrize("raw, needle", [
    (cfg_of("P5@1.0"), "unsupported config id"),
    (cfg_of("P3@2.0"), "unsupported config id"),
    (cfg_of("P3@1.0", "lira"), "unsupported account type"),
    (cfg_of("P3@1.0", tol=40), "owner_tolerance_pct"),
    (cfg_of("P3@1.0", overrides={"max_position": 0.8}), "max_position"),          # risk limits only tighten
    (cfg_of("P3@1.0", overrides={"leverage_cap_addon": 0.2}), "leverage_cap_addon"),
    (cfg_of("P3@1.0", overrides={"fx_cost": 0.0}), "fx_cost"),                    # costs only raised
    (cfg_of("P3@1.0", overrides={"freshness_days": 10}), "freshness_days"),
    (cfg_of("P3@1.0", overrides={"alert_levels": {}}), "non-overridable"),
    ({**cfg_of("P3@1.0"), "surprise": 1}, "unknown config keys"),
])
def test_unsupported_or_loosened_config_is_refused(raw, needle):
    s = run_eval(raw, holdings_for(targets("P3@1.0")))
    assert_refused(s, "unsupported configuration", needle)
    assert "REFUSED" in render_markdown(s)


# ------------------------------------------------------------------------------------------------ determinism ------
def test_determinism_byte_identical_report_json_and_log_entry(tmp_path):
    rows = price_rows(QE)
    store, version, _ = snapshot(tmp_path, rows)
    hold = holdings_for({"XEQT.TO": 0.7, "ZAG.TO": 0.25, "DBMF": 0.03}, as_of=QE, cash_usd=500.0)
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of("P4@1.0", "rrsp"), hold)
    outs = []
    for tag in ("a", "b"):
        out, log = tmp_path / tag / "out", tmp_path / tag / "paper_log.jsonl"
        assert cli.main(cli_args(cfg_path, hold_path, store, version, QE, out, log)) == 0
        outs.append((out, log))
    (oa, la), (ob, lb) = outs
    names = sorted(p.name for p in oa.iterdir())
    assert names == ["report_2026-09-28_P4@1.0.md", "summary_2026-09-28_P4@1.0.json"]
    for name in names:
        assert (oa / name).read_bytes() == (ob / name).read_bytes()
    assert la.read_bytes() == lb.read_bytes()
    assert load_summary(oa)["trades"], "scenario should propose trades"
    # ... and with a non-empty paper log: the next report appends identical lines to identical logs
    rd2 = QE + timedelta(days=1)
    store2, v2, _ = snapshot(tmp_path, price_rows(rd2), version="p2")
    hold2 = holdings_for(targets("P4@1.0"), as_of=rd2, flow=1000.0)
    cfg2, hold2_path = write_inputs(tmp_path / "in2", cfg_of("P4@1.0", "rrsp"), hold2)
    for tag in ("a", "b"):
        out, log = tmp_path / tag / "out2", tmp_path / tag / "paper_log.jsonl"
        assert cli.main(cli_args(cfg2, hold2_path, store2, v2, rd2, out, log)) == 0
    assert la.read_bytes() == lb.read_bytes()
    assert len(la.read_bytes().splitlines()) == 2
    for name in sorted(p.name for p in (tmp_path / "a" / "out2").iterdir()):
        assert (tmp_path / "a" / "out2" / name).read_bytes() == (tmp_path / "b" / "out2" / name).read_bytes()
    # no wall-clock time or absolute path leaks into the outputs
    text = (oa / names[0]).read_text() + (oa / names[1]).read_text() + la.read_text()
    assert str(tmp_path) not in text


def test_evaluate_is_pure():
    raw, hold = cfg_of("P6a@1.25", "tfsa"), holdings_for({"XEQT.TO": 0.99})
    a = json.dumps(run_eval(raw, hold), sort_keys=True)
    b = json.dumps(run_eval(raw, hold), sort_keys=True)
    assert a == b


# ------------------------------------------------------------------------------------------------ refusals: data ---
def test_stale_price_refused_and_boundary_accepted():
    hold = holdings_for(targets("P3@1.0"))
    s = run_eval(cfg_of(), hold, price_rows(RD - timedelta(days=6)))
    assert_refused(s, "stale price for XEQT.TO", "stale USD/CAD rate")
    ok = run_eval(cfg_of(), hold, price_rows(RD - timedelta(days=5)))
    assert ok["status"] == "accepted"


def test_future_dated_price_refused():
    rows = price_rows(RD, extra=[(RD + timedelta(days=1), "XEQT.TO", 31.0, "CAD")])
    s = run_eval(cfg_of(), holdings_for(targets("P3@1.0")), rows)
    assert_refused(s, "future-dated")


@pytest.mark.parametrize("delta, needle", [(6, "stale holdings"), (-1, "future-dated")])
def test_stale_or_future_holdings_refused(delta, needle):
    s = run_eval(cfg_of(), holdings_for(targets("P3@1.0"), as_of=RD - timedelta(days=delta)))
    assert_refused(s, needle)


def test_missing_price_for_held_or_target_ticker_refused():
    held = holdings_for({**targets("P3@1.0"), "GDE": 0.0}, extra={})
    held["positions"]["GDE"] = 10
    assert_refused(run_eval(cfg_of(), held, price_rows(RD, drop=("GDE",))), "no price for GDE")
    # DBMF is a P4@1.0 target even though it is not held
    s = run_eval(cfg_of("P4@1.0"), holdings_for({"XEQT.TO": 0.5}), price_rows(RD, drop=("DBMF",)))
    assert_refused(s, "no price for DBMF")


def test_missing_usdcad_refused():
    s = run_eval(cfg_of(), holdings_for(targets("P3@1.0")), price_rows(RD, drop=("USDCAD",)))
    assert_refused(s, "missing USD/CAD rate")


def test_wrong_currency_price_refused():
    rows = [r if r[1] != "DBMF" else (r[0], r[1], r[2], "CAD") for r in price_rows(RD)]
    s = run_eval(cfg_of("P4@1.0"), holdings_for(targets("P4@1.0")), rows)
    assert_refused(s, "quoted in CAD; expected USD")


def test_tampered_snapshot_object_refused(tmp_path):
    store, version, _ = snapshot(tmp_path, price_rows(RD))
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of("P3@1.0"), holdings_for({"XEQT.TO": 0.99}))
    manifest = json.loads((store / "versions" / version / "manifest.json").read_text())
    sha = manifest["payload"]["records"][0]["sha256"]
    obj = store / "objects" / "sha256" / sha[:2] / sha
    os.chmod(obj, 0o644)
    obj.write_bytes(obj.read_bytes().replace(b"30.0", b"99.0"))
    out, log = tmp_path / "out", tmp_path / "log.jsonl"
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, out, log)) == 1
    s = load_summary(out)
    assert_refused(s, "research.data_snapshot.verify", "missing/corrupt frozen object")
    assert s["valuation"] is None
    report = next(out.glob("report_*.md")).read_text()
    assert "REFUSED" in report and "Proposed trades" not in report
    (entry,) = read_chain(log)
    assert entry["body"]["status"] == "refused" and entry["body"]["trades"] == []


def test_tampered_manifest_and_missing_store_refused(tmp_path):
    store, version, _ = snapshot(tmp_path, price_rows(RD))
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of("P3@1.0"), holdings_for({"XEQT.TO": 0.99}))
    mpath = store / "versions" / version / "manifest.json"
    mpath.write_text(mpath.read_text().replace('"source":"synthetic_test"', '"source":"edited"'))
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, tmp_path / "o1", tmp_path / "l1")) == 1
    assert_refused(load_summary(tmp_path / "o1"), "manifest hash mismatch")
    assert cli.main(cli_args(cfg_path, hold_path, tmp_path / "nope", version, RD, tmp_path / "o2",
                             tmp_path / "l2")) == 1
    assert_refused(load_summary(tmp_path / "o2"), "failed research.data_snapshot.verify")


def test_live_source_drift_refused_unless_labelled_replay(tmp_path):
    store, version, src = snapshot(tmp_path, price_rows(RD))
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of("P3@1.0"), holdings_for(targets("P3@1.0")))
    src.write_bytes(src.read_bytes() + f"{RD.isoformat()},VFV.TO,100.0,CAD\n".encode())
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, tmp_path / "o1", tmp_path / "l1")) == 1
    assert_refused(load_summary(tmp_path / "o1"), "input changed")
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, tmp_path / "o2", tmp_path / "l2",
                             "--replay")) == 0
    s = load_summary(tmp_path / "o2")
    assert s["status"] == "accepted" and s["inputs"]["prices"]["mode"] == "replay"
    assert "REPLAY" in next((tmp_path / "o2").glob("report_*.md")).read_text()


@pytest.mark.parametrize("mutate, needle", [
    (lambda h: h["positions"].update({"VFV.TO": 10}), "unknown tickers"),
    (lambda h: h["positions"].update({"XEQT.TO": -5}), "negative shares"),
    (lambda h: h["positions"].update({"XEQT.TO": 2.5}), "fractional shares"),
    (lambda h: h.update({"cash_cad": -100}), "cash_cad is negative"),
    (lambda h: h.pop("net_external_flow_cad"), "missing required fields"),
    (lambda h: h.update({"as_of": "28/09/2026"}), "ISO date"),
])
def test_bad_holdings_refused(mutate, needle):
    hold = holdings_for(targets("P3@1.0"))
    mutate(hold)
    assert_refused(run_eval(cfg_of(), hold), "holdings file unparsable", needle)


def test_holdings_unparsable_bytes_and_duplicate_keys_refused(tmp_path):
    store, version, _ = snapshot(tmp_path, price_rows(RD))
    cfg_path, _ = write_inputs(tmp_path / "in", cfg_of(), {})
    bad = tmp_path / "in" / "bad.json"
    bad.write_text('{"as_of": "2026-08-26", "as_of": "2026-08-25", "cash_cad": 1, "cash_usd": 0, '
                   '"net_external_flow_cad": 0, "positions": {}}')
    assert cli.main(cli_args(cfg_path, bad, store, version, RD, tmp_path / "o", tmp_path / "l")) == 1
    assert_refused(load_summary(tmp_path / "o"), "duplicate JSON key")


def test_holdings_csv_format_accepted(tmp_path):
    store, version, _ = snapshot(tmp_path, price_rows(RD))
    csv_text = ("record,key,value\nfield,as_of,2026-08-25\nfield,cash_cad,1000\nfield,cash_usd,0\n"
                "field,net_external_flow_cad,0\nposition,XEQT.TO,1980\nposition,ZAG.TO,2757\n")
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of(), csv_text, holdings_name="holdings.csv")
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, tmp_path / "o", tmp_path / "l")) == 0
    s = load_summary(tmp_path / "o")
    assert s["inputs"]["holdings"]["file"] == "holdings.csv"
    assert s["valuation"]["nav_cad"] == pytest.approx(1980 * 30 + 2757 * 14 + 1000)


# ------------------------------------------------------------------------------------------------ account rules ----
@pytest.mark.parametrize("account", ["tfsa", "rrsp", "nonreg_cash"])
def test_no_borrow_accounts_refuse_any_loan(account):
    hold = holdings_for(targets("P3@1.25", account), loan=5000.0)
    hold["margin_loan_cad"] = 5000.0
    assert_refused(run_eval(cfg_of("P3@1.25", account), hold), "can never borrow")


@pytest.mark.parametrize("account", ["tfsa", "rrsp", "nonreg_cash", "nonreg_margin"])
def test_negative_shares_refused_in_every_account(account):
    hold = holdings_for({"XEQT.TO": 0.5}, margin=account == "nonreg_margin")
    hold["positions"]["ZAG.TO"] = -100
    assert_refused(run_eval(cfg_of("P3@1.0", account), hold), "negative shares", "shorts are never allowed")


def test_margin_account_borrows_within_caps():
    hold = holdings_for({}, nav=100_000.0, margin=True)        # all cash, no loan yet
    s = run_eval(cfg_of("P4@1.25", "nonreg_margin"), hold)
    assert s["status"] == "accepted", s["refusal_reasons"]
    assert [(t["side"], t["ticker"], t["shares"]) for t in s["trades"]] == [          # USD-listed buys first
        ("BUY", "DBMF", 327), ("BUY", "XEQT.TO", 1980), ("BUY", "ZAG.TO", 2828), ("BUY", "ZGLD.TO", 618)]
    pt = s["post_trade"]
    assert 20_000 < pt["margin_loan_cad"] <= 25_000                # capacity = recipe loan (L - 1) x NAV
    assert pt["cash_cad"] == 0.0 and pt["cash_usd"] == 0.0
    assert pt["equity_over_assets"] >= 0.40
    assert pt["gross_exposure_over_nav"] <= 1.25 + 0.15
    assert all(c["ok"] for c in s["checks"])
    assert {c["name"] for c in s["checks"]} >= {"equity_assets_floor", "leverage_cap", "position_cap"}


@pytest.mark.parametrize("config_id", sorted(CONFIGS))
@pytest.mark.parametrize("account", ["tfsa", "nonreg_margin"])
def test_every_recipe_from_cash_passes_checks(config_id, account):
    """SPEC section 4 change (2026-09-29): XEQT.TO/ZAG.TO are capped at target + 5 pp, so the P3@1.25, P3@1.5 and
    P4@1.5 margin recipes (XEQT.TO at 74.25% / 89.10% / 71.28% of NAV) now rebalance from cash like every other pair."""
    s = run_eval(cfg_of(config_id, account), holdings_for({}, margin=account == "nonreg_margin"))
    assert s["status"] == "accepted", s["refusal_reasons"]
    assert all(c["ok"] for c in s["checks"]) and s["trades"]
    assert recipe_cap_conflicts(parse_config(cfg_of(config_id, account)), DECLARED) == []


@pytest.mark.parametrize("config_id, xeqt", [("P3@1.25", 0.7425), ("P3@1.5", 0.891), ("P4@1.5", 0.7128)])
def test_formerly_conflicting_margin_recipes_now_run(config_id, xeqt):
    s = run_eval(cfg_of(config_id, "nonreg_margin"), holdings_for({}, margin=True))
    assert s["status"] == "accepted", s["refusal_reasons"]
    assert s["targets"]["XEQT.TO"] == pytest.approx(xeqt)
    cap = next(c for c in s["checks"] if c["name"] == "position_cap")
    assert cap["ok"] and cap["limit"]["per_ticker"]["XEQT.TO"] == pytest.approx(xeqt + 0.05)
    assert cap["value"]["ticker"] in ("XEQT.TO", "ZAG.TO", "ZGLD.TO", "DBMF")
    xe = next(r for r in s["post_trade"]["positions"] if r["ticker"] == "XEQT.TO")
    assert 0.65 < xe["weight"] <= xeqt + 0.05


def test_position_cap_per_ticker_rules():
    p = dict(DECLARED)
    t = targets("P3@1.5", "nonreg_margin")
    assert position_cap("XEQT.TO", t, p) == (pytest.approx(0.891 + 0.05), "target + one_ticket_cap_addon")
    assert position_cap("ZAG.TO", t, p)[0] == pytest.approx(0.594 + 0.05)
    assert position_cap("RSST", t, p) == (0.65, "max_position")
    assert position_cap("SSO", t, p) == (0.30, "max_position_sso")
    # the one-ticket cap follows the target, so it can be tighter than 65% (P3@1.0 XEQT.TO: 59.4% + 5 pp)
    assert position_cap("XEQT.TO", targets("P3@1.0"), p)[0] == pytest.approx(0.644)
    # a held one-ticket fund that the recipe does not use (target 0) is capped at the add-on alone
    assert position_cap("ZAG.TO", targets("P6a@1.0"), p)[0] == pytest.approx(0.05)
    # max_position overrides do not touch XEQT.TO/ZAG.TO; one_ticket_cap_addon may only be tightened
    assert position_cap("XEQT.TO", t, {**p, "max_position": 0.5})[0] == pytest.approx(0.941)
    assert position_cap("XEQT.TO", t, {**p, "one_ticket_cap_addon": 0.02})[0] == pytest.approx(0.911)
    s = run_eval(cfg_of("P3@1.0", overrides={"one_ticket_cap_addon": 0.06}), holdings_for(targets("P3@1.0")))
    assert_refused(s, "unsupported configuration", "one_ticket_cap_addon")


def test_margin_xeqt_drift_beyond_target_plus_5pp_still_refused():
    """XEQT.TO at 96% of NAV in a P3@1.5 margin account: 6.9 pp over its 89.10% target, above its 94.10% cap.
    With the band widened by override (10 pp, relative 100%, leverage 0.5) nothing triggers, so the post-trade check
    runs on the current holdings and refuses; with the declared band the drift triggers a rebalance that passes."""
    hold = holdings_for({"XEQT.TO": 0.96, "ZAG.TO": 0.54}, loan=50_000.0, margin=True)
    wide = {"band_abs": 0.10, "band_rel": 1.0, "margin_leverage_band": 0.5}
    s = run_eval(cfg_of("P3@1.5", "nonreg_margin", overrides=wide), hold)
    assert not s["decision"]["triggered"]
    assert_refused(s, "position_cap", "XEQT.TO 96.00% > 94.10% (target + one_ticket_cap_addon)",
                   "no trades were triggered")
    ok = run_eval(cfg_of("P3@1.5", "nonreg_margin"), hold)
    assert ok["status"] == "accepted" and ok["decision"]["triggered"] and ok["trades"]
    assert all(c["ok"] for c in ok["checks"])


def test_tightened_cap_below_a_recipe_target_is_named_as_a_conflict():
    s = run_eval(cfg_of("P6a@1.25", overrides={"max_position": 0.60}), holdings_for({}))
    assert_refused(s, "position_cap", "RSST 61.", "recipe itself targets RSST at 61.88%", "cannot pass the cap")


def test_margin_account_must_state_loan():
    hold = holdings_for(targets("P4@1.25", "nonreg_margin"), loan=23_750.0)
    assert_refused(run_eval(cfg_of("P4@1.25", "nonreg_margin"), hold), "must state margin_loan_cad")


def test_margin_usd_buys_funded_by_borrowed_cad_conversion():
    hold = holdings_for({}, margin=True)
    s = run_eval(cfg_of("P4@1.25", "nonreg_margin"), hold)
    assert s["status"] == "accepted"
    assert s["fx"]["cad_to_usd"]["usd_needed"] > 0 and s["fx"]["cad_to_usd"]["for"] == ["DBMF"]
    assert s["post_trade"]["cash_usd"] >= 0 and s["post_trade"]["margin_loan_cad"] > 0


def test_never_negative_cash_property_no_borrow_accounts():
    rng = random.Random(20260928)
    tickers = sorted(UNIVERSE)
    accepted_with_trades = 0
    for _ in range(250):
        cid = rng.choice(sorted(CONFIGS))
        account = rng.choice(["tfsa", "rrsp", "nonreg_cash"])
        positions = {t: rng.choice([0, rng.randint(1, 4000)]) for t in rng.sample(tickers, rng.randint(0, 6))}
        prices = {t: (round(c * rng.uniform(0.5, 1.5), 2), ccy) for t, (c, ccy) in PRICES.items()}
        fx = round(rng.uniform(1.2, 1.5), 4)
        overrides = rng.choice([{}, {"commission_cad": 9.99}, {"min_trade_cad": 0.0}, {"fx_cost": 0.02},
                                {"commission_cad": 50.0, "min_trade_cad": 0.0}, {"cash_buffer": 0.03}])
        hold = {"as_of": RD.isoformat(), "cash_cad": rng.choice([0.0, round(rng.uniform(0, 30_000), 2)]),
                "cash_usd": rng.choice([0.0, round(rng.uniform(0, 8_000), 2)]), "net_external_flow_cad": 0,
                "positions": positions}
        s = run_eval(cfg_of(cid, account, overrides=overrides), hold, price_rows(RD, prices=prices, fx=fx))
        for c in s["checks"]:
            if c["name"] == "no_borrowing_no_negative_cash":
                assert c["ok"], (cid, account, hold, overrides)
        if s["status"] == "accepted":
            assert s["post_trade"]["cash_cad"] >= 0 and s["post_trade"]["cash_usd"] >= 0
            assert s["post_trade"]["margin_loan_cad"] == 0
            assert all(isinstance(t["shares"], int) and t["shares"] > 0 for t in s["trades"])
            sides = [t["side"] for t in s["trades"]]
            assert sides == sorted(sides, key=lambda x: x != "SELL")      # sells before buys
            accepted_with_trades += bool(s["trades"])
        else:
            assert s["trades"] == []
    assert accepted_with_trades > 100


def test_fund_never_borrows_without_capacity():
    pools = {"CAD": 100.0, "USD": 10.0}
    assert fund(pools, "CAD", 100.0, FX, 0.001, 0.0) == ({"CAD": 0.0, "USD": 10.0}, None)
    assert fund(pools, "CAD", 200.0, FX, 0.001, 0.0) is None
    new, conv = fund(pools, "USD", 50.0, FX, 0.001, 0.0)
    assert new["USD"] == 0.0 and conv["from"] == "CAD" and new["CAD"] == pytest.approx(100 - 40 * FX / 0.999)
    assert fund(pools, "USD", 100.0, FX, 0.001, 0.0) is None
    new, _ = fund(pools, "CAD", 500.0, FX, 0.001, -1000.0)      # margin capacity
    assert new["CAD"] == pytest.approx(-(400 - 10 * FX * 0.999))


def test_risk_check_flags_negative_cash_directly():
    cfg = parse_config(cfg_of("P3@1.0", "tfsa"))
    px = {t: {"close": c, "ccy": ccy, "date": RD.isoformat()} for t, (c, ccy) in PRICES.items()}
    state = value_state({"XEQT.TO": 100}, px, FX, -50.0, 0.0, ["XEQT.TO"])
    checks = {c["name"]: c for c in risk_checks(state, cfg, DECLARED, {"XEQT.TO": 100})}
    assert checks["no_borrowing_no_negative_cash"]["ok"] is False


# ------------------------------------------------------------------------------------------------ rounding ---------
@pytest.mark.parametrize("nav, xeqt, zag", [(100_000.0, 1980, 2828), (25_000.0, 495, 707)])
def test_whole_share_rounding_buys_rounded_down(nav, xeqt, zag):
    s = run_eval(cfg_of("P3@1.0"), holdings_for({}, nav=nav))
    assert s["status"] == "accepted"
    assert [(t["side"], t["ticker"], t["shares"]) for t in s["trades"]] == [("BUY", "XEQT.TO", xeqt),
                                                                          ("BUY", "ZAG.TO", zag)]
    # 0.99 x 0.60 x NAV / 30 and 0.99 x 0.40 x NAV / 14, floored
    assert xeqt == math.floor(0.594 * nav / 30 + 1e-9) and zag == math.floor(0.396 * nav / 14 + 1e-9)
    spent = xeqt * 30 * 1.0005 + zag * 14 * 1.0005
    assert s["post_trade"]["cash_cad"] == pytest.approx(nav - spent, abs=0.01)


def test_buys_rounded_down_to_fit_cash_when_short():
    # four commissions of CAD 100 exceed the 1% buffer of a CAD 25,000 account: the last buy is cut
    s = run_eval(cfg_of("P4@1.0", overrides={"commission_cad": 100.0}), holdings_for({}, nav=25_000.0))
    assert s["status"] == "accepted"
    assert any((t["note"] or "").startswith("rounded down from") for t in s["trades"])
    assert s["post_trade"]["cash_cad"] >= 0 and s["post_trade"]["cash_usd"] >= 0


def test_minimum_trade_size_skips_small_trades():
    # (The TFSA holdings must stay cash-funded: a negative cash_cad is itself an unparsable-holdings refusal.)
    w = targets("P4@1.0")
    hold = holdings_for(w, extra={})
    hold["positions"]["XEQT.TO"] += 300                 # +9 pp -> triggers a full rebalance ...
    hold["positions"]["ZAG.TO"] -= 643                  # ... funded by -9 pp of ZAG (CAD 9,002)
    hold["cash_cad"] = round(hold["cash_cad"] + 643 * 14 - 300 * 30, 2)
    hold["positions"]["ZGLD.TO"] -= 3                   # CAD 60 short of target -> buy skipped (< CAD 100)
    hold["cash_cad"] = round(hold["cash_cad"] + 60, 2)
    hold["positions"]["GDE"] = 2                        # CAD 94.50 of a non-target ticker -> sell skipped
    hold["cash_cad"] = round(hold["cash_cad"] - 94.5, 2)
    assert hold["cash_cad"] > 0
    s = run_eval(cfg_of("P4@1.0"), hold)
    assert s["status"] == "accepted", s["refusal_reasons"]
    assert s["decision"]["triggered"]
    traded = {t["ticker"] for t in s["trades"]}
    skipped = {(k["side"], k["ticker"]) for k in s["skipped_trades"]}
    assert "GDE" not in traded and ("SELL", "GDE") in skipped
    assert "ZGLD.TO" not in traded and ("BUY", "ZGLD.TO") in skipped
    assert all(t["est_value_cad"] >= 100 for t in s["trades"])
    minimum = [k for k in s["skipped_trades"] if "minimum" in k["reason"]]
    assert {k["ticker"] for k in minimum} == {"GDE", "ZGLD.TO"}
    assert all(0 < k["est_value_cad"] < 100 for k in minimum)
    assert ("SELL", "XEQT.TO") in {(t["side"], t["ticker"]) for t in s["trades"]}
    assert ("BUY", "ZAG.TO") in {(t["side"], t["ticker"]) for t in s["trades"]}
    after = {r["ticker"]: r["shares"] for r in s["post_trade"]["positions"]}
    assert after["GDE"] == 2 and after["ZGLD.TO"] == hold["positions"]["ZGLD.TO"]
    assert "minimum trade size" in render_markdown(s)
    # with the minimum lowered to 0 the same small trades go through
    s0 = run_eval(cfg_of("P4@1.0", overrides={"min_trade_cad": 0.0}), hold)
    assert s0["status"] == "accepted"
    assert {("SELL", "GDE"), ("BUY", "ZGLD.TO")} <= {(t["side"], t["ticker"]) for t in s0["trades"]}


# ------------------------------------------------------------------------------------------------ band logic -------
T = {"XEQT.TO": 0.594, "ZAG.TO": 0.396}


@pytest.mark.parametrize("current, target, quarter_end, triggered, kinds", [
    ({"XEQT.TO": 0.614, "ZAG.TO": 0.376}, T, False, False, []),                    # inside band (2 pp)
    ({"XEQT.TO": 0.645, "ZAG.TO": 0.345}, T, False, True, ["band"]),               # abs 5.1 pp > 5 pp
    ({"ZGLD.TO": 0.125}, {"ZGLD.TO": 0.099}, False, True, ["band"]),              # rel 26% and abs 2.6 pp
    ({"ZGLD.TO": 0.120}, {"ZGLD.TO": 0.099}, False, False, []),                   # rel 21%: inside
    ({"X": 0.029}, {"X": 0.02}, False, False, []),                                 # rel 45% but abs 0.9 pp
    ({"GDE": 0.009}, {}, False, False, []),                                        # target 0, abs 0.9 pp
    ({"GDE": 0.011}, {}, False, True, ["band"]),                                   # target 0, abs 1.1 pp
    ({"XEQT.TO": 0.614, "ZAG.TO": 0.376}, T, True, True, ["calendar"]),            # quarter-end, 2 pp
    ({"XEQT.TO": 0.603, "ZAG.TO": 0.387}, T, True, False, []),                     # quarter-end, 0.9 pp
])
def test_band_decision(current, target, quarter_end, triggered, kinds):
    d = band_decision(current, target, DECLARED, quarter_end=quarter_end)
    assert d["triggered"] is triggered
    assert [t["kind"] for t in d["triggers"]] == kinds


def test_margin_leverage_band():
    d = band_decision(T, T, DECLARED, quarter_end=False, leverage=1.36, target_leverage=1.2375)
    assert d["triggered"] and [t["kind"] for t in d["triggers"]] == ["margin_leverage"]
    d = band_decision(T, T, DECLARED, quarter_end=False, leverage=1.30, target_leverage=1.2375)
    assert not d["triggered"]


def drifted(config_id, shifts, account="tfsa"):
    w = dict(targets(config_id, account))
    for t, dw in shifts.items():
        w[t] = w.get(t, 0.0) + dw
    return w


def test_end_to_end_band_and_calendar():
    inside = drifted("P3@1.0", {"XEQT.TO": 0.02, "ZAG.TO": -0.02})
    s = run_eval(cfg_of(), holdings_for(inside, as_of=RD))
    assert s["status"] == "accepted" and not s["decision"]["triggered"] and s["trades"] == []
    assert "inside the drift band" in render_markdown(s)
    s = run_eval(cfg_of(), holdings_for(inside, as_of=QE), rd=QE)          # same drift at quarter-end
    assert s["decision"]["quarter_end"] and [t["kind"] for t in s["decision"]["triggers"]] == ["calendar"]
    assert s["trades"]
    small = drifted("P3@1.0", {"XEQT.TO": 0.008, "ZAG.TO": -0.008})
    s = run_eval(cfg_of(), holdings_for(small, as_of=QE), rd=QE)
    assert not s["decision"]["triggered"] and s["trades"] == []
    big = drifted("P3@1.0", {"XEQT.TO": 0.06, "ZAG.TO": -0.06})
    s = run_eval(cfg_of(), holdings_for(big))
    assert [t["kind"] for t in s["decision"]["triggers"]] == ["band"] and s["trades"]
    rel = drifted("P4@1.0", {"ZGLD.TO": 0.03, "XEQT.TO": -0.03})          # ZGLD rel 30%, abs 3 pp
    s = run_eval(cfg_of("P4@1.0"), holdings_for(rel))
    assert s["decision"]["triggered"] and any("ZGLD.TO: relative drift" in d
                                              for t in s["decision"]["triggers"] for d in t["detail"])
    stray = drifted("P3@1.0", {"XEQT.TO": -0.008})
    stray["GDE"] = 0.008                                                    # non-target ticker, 0.8 pp
    s = run_eval(cfg_of(), holdings_for(stray))
    assert not s["decision"]["triggered"]


def test_sells_before_buys_and_full_rebalance():
    hold = holdings_for({"XEQT.TO": 0.30, "RSST": 0.60})
    s = run_eval(cfg_of("P4@1.25"), hold)
    sides = [t["side"] for t in s["trades"]]
    assert sides[0] == "SELL" and sides == sorted(sides, key=lambda x: x != "SELL")
    after = {r["ticker"]: r for r in s["post_trade"]["positions"]}
    for t, g in targets("P4@1.25").items():
        assert abs(after[t]["weight"] - g) < 0.005                         # within rounding of target


# ------------------------------------------------------------------------------------------------ risk caps --------
def test_leverage_cap_breach_refused():
    w = drifted("P3@1.25", {"RSSB": 0.03, "ZAG.TO": -0.03})               # inside band, gross 1.2675
    raw = cfg_of("P3@1.25", overrides={"leverage_cap_addon": 0.0})
    s = run_eval(raw, holdings_for(w))
    assert_refused(s, "post-trade check failed: leverage_cap", "no trades were triggered")
    assert run_eval(cfg_of("P3@1.25"), holdings_for(w))["status"] == "accepted"


def test_equity_assets_floor_breach_refused():
    hold = holdings_for({}, margin=True)
    s = run_eval(cfg_of("P4@1.25", "nonreg_margin", overrides={"equity_assets_floor": 0.9}), hold)
    assert_refused(s, "equity_assets_floor")
    assert s["post_trade"] is None and s["checked_state"]["equity_over_assets"] < 0.9
    assert run_eval(cfg_of("P4@1.25", "nonreg_margin"), hold)["status"] == "accepted"


def test_position_cap_breach_refused():
    w = drifted("P6a@1.25", {"RSST": 0.036, "SSO": -0.02, "XEQT.TO": -0.01})   # RSST 65.5%, inside band
    s = run_eval(cfg_of("P6a@1.25"), holdings_for(w))
    assert_refused(s, "position_cap", "RSST")
    s = run_eval(cfg_of("P6a@1.25", overrides={"max_position": 0.60}), holdings_for({}))
    assert_refused(s, "position_cap", "RSST 61.")
    s = run_eval(cfg_of("P6a@1.25", overrides={"max_position_sso": 0.20}), holdings_for({}))
    assert_refused(s, "position_cap", "SSO 24.")
    ok = run_eval(cfg_of("P6a@1.25"), holdings_for({}))
    assert ok["status"] == "accepted" and all(c["ok"] for c in ok["checks"])


def test_triggered_but_untradeable_breach_says_why():
    # RSST at USD 2,000 (CAD 2,700 a share) in a CAD 24,000 account: 6 shares = 67.5% of NAV, 5.6 pp above target,
    # but selling one share would undershoot the target, so sells round to 0; the SSO buy has no cash; the XEQT buy
    # is below CAD 100.  The band fires, no trade can be proposed, the position cap is breached -> refused.
    prices = {**PRICES, "RSST": (2000.0, "USD")}
    hold = {"as_of": RD.isoformat(), "cash_cad": 0, "cash_usd": 0, "net_external_flow_cad": 0,
            "positions": {"RSST": 6, "SSO": 40, "XEQT.TO": 98}}
    s = run_eval(cfg_of("P6a@1.25"), hold, price_rows(RD, prices=prices))
    assert s["decision"]["triggered"]
    assert_refused(s, "position_cap", "RSST 67.50%", "a rebalance was triggered but no trade could be proposed")
    assert "no trades were triggered" not in " ".join(s["refusal_reasons"])


def test_config_label_is_printed_under_the_title_and_validated():
    label = "HYPOTHETICAL HOLDINGS — research sample, not a recommendation"
    s = run_eval(cfg_of("P3@1.0", label=label), holdings_for(targets("P3@1.0")))
    assert s["status"] == "accepted" and s["config"]["label"] == label
    lines = render_markdown(s).splitlines()
    assert lines[0].startswith("# Rebalancing report") and lines[2] == f"**{label}**"
    plain = run_eval(cfg_of("P3@1.0"), holdings_for(targets("P3@1.0")))
    assert plain["config"]["label"] is None and render_markdown(plain).splitlines()[2].startswith("> Research tool")
    for bad in ("two\nlines", "", "x" * 201, 7):
        assert_refused(run_eval(cfg_of("P3@1.0", label=bad), holdings_for(targets("P3@1.0"))), "label must be")


# ------------------------------------------------------------------------------------------------ unit ledger ------
def _chain_of(*summaries):
    chain = []
    for s in summaries:
        chain.append(make_entry(s, chain))
    return chain


def test_unit_accounting_flows_and_drawdown_alerts():
    raw = cfg_of("P3@1.0", tol=35)
    d1, d2, d3 = date(2026, 8, 3), date(2026, 8, 10), date(2026, 8, 17)
    s1 = run_eval(raw, holdings_for(targets("P3@1.0"), as_of=d1, flow=5000.0), rd=d1)
    assert s1["unit_ledger"]["unit_value"] == pytest.approx(100.0) and s1["unit_ledger"]["initialised"]
    assert s1["drawdown"]["alert"] == "NONE"
    units1 = s1["unit_ledger"]["units"]
    # a CAD 10,000 deposit at unchanged prices: more units, same unit value
    nav1 = s1["valuation"]["nav_cad"]
    s2 = run_eval(raw, holdings_for(targets("P3@1.0"), nav=nav1 + 10_000, as_of=d2, flow=10_000.0), rd=d2,
                  chain=_chain_of(s1))
    assert s2["unit_ledger"]["units"] > units1
    assert s2["unit_ledger"]["unit_value"] == pytest.approx(100.0 * (s2["valuation"]["nav_cad"] - 10_000)
                                                            / nav1, rel=1e-9)
    chain = _chain_of(s1, s2)
    base = holdings_for(targets("P3@1.0"), nav=nav1 + 10_000, as_of=d3)
    for factor, tol, level in [(0.90, 25, "NONE"), (0.75, 35, "INFO"), (0.75, 25, "WARNING"),
                               (0.70, 35, "WARNING"), (0.62, 35, "BREACH")]:
        prices = {t: (c * factor, ccy) for t, (c, ccy) in PRICES.items()}
        s3 = run_eval(cfg_of("P3@1.0", tol=tol), base, price_rows(d3, prices=prices), rd=d3, chain=chain)
        led = s3["unit_ledger"]
        assert led["units"] == pytest.approx(s2["unit_ledger"]["units"])       # no flow: units unchanged
        dd = 1 - led["unit_value"] / s2["unit_ledger"]["unit_value"]
        assert s3["drawdown"]["drawdown"] == pytest.approx(dd, abs=1e-7)
        assert s3["drawdown"]["alert"] == level, (factor, tol, dd)
        assert s3["status"] == "accepted"      # alerts never force de-risking or refusal
    # a withdrawal does not change the unit value either
    s4 = run_eval(raw, holdings_for(targets("P3@1.0"), nav=nav1 + 5_000, as_of=d3, flow=-5_000.0), rd=d3,
                  chain=chain)
    assert s4["unit_ledger"]["unit_value"] == pytest.approx(s2["unit_ledger"]["unit_value"], rel=1e-9)


def test_unit_ledger_ignores_refused_and_other_portfolios_and_rejects_rewind():
    d1, d2 = date(2026, 8, 3), date(2026, 8, 10)
    s1 = run_eval(cfg_of(), holdings_for(targets("P3@1.0"), as_of=d1), rd=d1)
    other = run_eval(cfg_of("P3@1.0", "rrsp"), holdings_for(targets("P3@1.0"), nav=50_000, as_of=d1), rd=d1)
    refused = run_eval(cfg_of(), holdings_for(targets("P3@1.0"), as_of=d1 - timedelta(days=9)), rd=d1)
    assert refused["status"] == "refused"
    chain = _chain_of(s1, other, refused)
    s2 = run_eval(cfg_of(), holdings_for(targets("P3@1.0"), as_of=d2), rd=d2, chain=chain)
    assert s2["unit_ledger"]["prior_report_date"] == d1.isoformat()
    assert s2["unit_ledger"]["units"] == pytest.approx(s1["unit_ledger"]["units"])
    # a report dated before an accepted entry cannot rewind the ledger
    later = _chain_of(s1, s2)
    assert_refused(run_eval(cfg_of(), holdings_for(targets("P3@1.0"), as_of=d1), rd=d1 + timedelta(days=1),
                            chain=later), "already holds an accepted report")
    # same-day re-run is computed from the earlier dates only (supersedes, no double-counted flow)
    again = run_eval(cfg_of(), holdings_for(targets("P3@1.0"), as_of=d2), rd=d2, chain=later)
    assert again["unit_ledger"] == s2["unit_ledger"]


# ------------------------------------------------------------------------------------------------ report content ---
def test_report_mentions_required_items():
    s = run_eval(cfg_of("P6a@1.25", overrides={"commission_cad": 4.95}), holdings_for({}), rd=RD)
    md = render_markdown(s)
    for needle in ["Nothing in this report is a recommendation to trade", "2x daily-reset",
                   "RSST: equity leg is US-only", "Norbert's gambit", "DLR.TO", "DLR-U.TO", "commission_cad",
                   "Drawdown vs tolerance", "Alerts never trigger automatic de-risking", "## Checks", "Proposed trades"]:
        assert needle in md, needle
    s = run_eval(cfg_of("P3@1.25"), holdings_for({}))
    assert "bond leg is US Treasuries" in render_markdown(s)


# ------------------------------------------------------------------------------------------------ paper log --------
def test_paper_log_hash_chain_validates_and_detects_tampering(tmp_path):
    log = tmp_path / "paper_log.jsonl"
    for i in range(3):
        paperlog.append(log, {"i": i, "status": "accepted"})
    chain = read_chain(log)
    assert [e["seq"] for e in chain] == [0, 1, 2] and chain[0]["prev_hash"] == "0" * 64
    assert chain[1]["prev_hash"] == chain[0]["entry_hash"] and paperlog.validate(log)
    lines = log.read_bytes().splitlines(keepends=True)

    def bad(data: bytes):
        p = tmp_path / "bad.jsonl"
        p.write_bytes(data)
        with pytest.raises(PaperLogError):
            read_chain(p)
        assert not paperlog.validate(p)

    bad(lines[0] + lines[1].replace(b'"i":1', b'"i":7') + lines[2])        # edited body
    bad(lines[0] + lines[2])                                                # deleted line
    bad(lines[1] + lines[0] + lines[2])                                     # reordered
    bad(b"".join(lines)[:-1])                                               # truncated
    bad(lines[0] + lines[1].replace(b'{"body"', b'{ "body"') + lines[2])    # re-serialised
    forged = json.loads(lines[1])
    forged["body"]["i"] = 9
    forged["entry_hash"] = paperlog.entry_hash(forged)                      # rehashed, but chain now breaks
    bad(lines[0] + paperlog.canonical(forged) + b"\n" + lines[2])
    # appending to a tampered log is fatal and writes nothing
    tampered = tmp_path / "t.jsonl"
    tampered.write_bytes(lines[0] + lines[2])
    with pytest.raises(PaperLogError):
        paperlog.append(tampered, {"i": 3})
    assert tampered.read_bytes() == lines[0] + lines[2]


def test_cli_refuses_tampered_log_and_writes_nothing(tmp_path):
    store, version, _ = snapshot(tmp_path, price_rows(RD))
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of(), holdings_for(targets("P3@1.0")))
    log = tmp_path / "log.jsonl"
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, tmp_path / "o1", log)) == 0
    log.write_bytes(log.read_bytes().replace(b'"status":"accepted"', b'"status":"refused"'))
    before = log.read_bytes()
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, tmp_path / "o2", log)) == 2
    assert log.read_bytes() == before and not (tmp_path / "o2").exists()


def test_cli_refuses_conflicting_existing_output(tmp_path):
    store, version, _ = snapshot(tmp_path, price_rows(RD))
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of(), holdings_for(targets("P3@1.0")))
    out, log = tmp_path / "out", tmp_path / "log.jsonl"
    out.mkdir()
    (out / f"report_{RD.isoformat()}_P3@1.0.md").write_text("owner notes\n")
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, out, log)) == 2
    assert not log.exists()


def test_forward_registry_hard_guard(tmp_path, monkeypatch):
    real = REPO / "reports" / "forward" / "registry.jsonl"
    existed, before = real.exists(), (real.read_bytes() if real.exists() else None)
    for p in (real, REPO / "reports" / "forward" / "x.jsonl", tmp_path / "registry.jsonl",
              Path(os.path.relpath(real, Path.cwd()))):
        with pytest.raises(PaperLogError):
            guard_path(p)
    # the CLI refuses the registry as --log before touching anything
    store, version, _ = snapshot(tmp_path, price_rows(RD))
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of(), holdings_for(targets("P3@1.0")))
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, tmp_path / "out", real)) == 2
    assert not (tmp_path / "out").exists()
    assert real.exists() == existed and (real.read_bytes() if existed else None) == before
    # symlinks / same-file aliases of a (sandboxed) forward registry are refused too
    fake_dir = tmp_path / "reports" / "forward"
    fake_dir.mkdir(parents=True)
    fake = fake_dir / "registry.jsonl"
    fake.write_bytes(b"")
    monkeypatch.setattr(paperlog, "FORWARD_DIR", fake_dir)
    monkeypatch.setattr(paperlog, "FORWARD_REGISTRY_PATH", fake)
    alias = tmp_path / "innocent.jsonl"
    alias.symlink_to(fake)
    hard = tmp_path / "hardlink.jsonl"
    os.link(fake, hard)
    for p in (alias, hard, fake_dir / "log.jsonl"):
        with pytest.raises(PaperLogError):
            paperlog.append(p, {"x": 1})
    assert fake.read_bytes() == b"" and not (fake_dir / "log.jsonl").exists()


def test_default_log_path_is_separate_from_registry():
    assert paperlog.DEFAULT_LOG_PATH == REPO / "reports" / "autopilot" / "paper_log.jsonl"
    assert cli.build_parser().get_default("log") == paperlog.DEFAULT_LOG_PATH


# ------------------------------------------------------------------------------------------------ no network -------
FORBIDDEN_MODULES = {"requests", "urllib", "urllib3", "http", "httpx", "aiohttp", "socket", "socketserver", "ssl",
                     "ftplib", "smtplib", "poplib", "imaplib", "telnetlib", "nntplib", "xmlrpc", "websocket",
                     "websockets", "asyncio", "subprocess", "multiprocessing", "paramiko", "grpc", "webbrowser"}


def test_engine_never_imports_network_modules():
    files = sorted(PKG.glob("*.py"))
    assert {f.name for f in files} >= {"__init__.py", "config.py", "holdings.py", "prices.py", "engine.py",
                                       "report.py", "paperlog.py", "cli.py"}
    for path in files:
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            bad = {n.split(".")[0] for n in names} & FORBIDDEN_MODULES
            assert not bad, f"{path.name} imports {bad}"
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else ""
                assert name not in {"__import__", "import_module", "system", "popen"}, f"{path.name}: {name}()"


def test_import_does_not_load_network_modules():
    code = ("import sys, research.autopilot.cli, research.autopilot.engine, research.autopilot.report\n"
            "bad = sorted(m for m in sys.modules if m.split('.')[0] in "
            "{'socket','ssl','requests','urllib3','httpx','aiohttp','ftplib','smtplib'} "
            "or m in ('http.client','urllib.request'))\nprint(bad)\n")
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]", out.stdout


def test_engine_runs_with_sockets_blocked(tmp_path, monkeypatch):
    store, version, _ = snapshot(tmp_path, price_rows(QE))
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of("P4@1.25", "nonreg_margin"),
                                       holdings_for({"XEQT.TO": 0.5}, as_of=QE, cash_usd=300.0, margin=True))

    def blocked(*_a, **_k):
        raise AssertionError("network access attempted")

    for name in ("socket", "create_connection", "getaddrinfo", "gethostbyname", "socketpair", "fromfd"):
        monkeypatch.setattr(socket, name, blocked)
    out, log = tmp_path / "out", tmp_path / "log.jsonl"
    assert cli.main(cli_args(cfg_path, hold_path, store, version, QE, out, log)) == 0
    s = load_summary(out)
    assert s["status"] == "accepted" and s["trades"]
    assert len(read_chain(log)) == 1


# ------------------------------------------------------------------------------------------------ SPEC coverage ----
@pytest.mark.parametrize("month, expected", [(m, m in (3, 6, 9, 12)) for m in range(1, 13)])
def test_quarter_end_months(month, expected):
    assert is_quarter_end(date(2026, month, 15), DECLARED) is expected


def test_holdings_freshness_boundary_accepted():
    for delta in (0, 5):
        s = run_eval(cfg_of(), holdings_for(targets("P3@1.0"), as_of=RD - timedelta(days=delta)))
        assert s["status"] == "accepted", (delta, s["refusal_reasons"])


def test_margin_leverage_trigger_end_to_end():
    """Every position inside its band, but assets/equity is > 0.10 above target: the margin trigger alone fires and
    the full rebalance sells back toward the target leverage (repaying part of the loan)."""
    raw = cfg_of("P4@1.25", "nonreg_margin")
    base = targets("P4@1.25", "nonreg_margin")
    target_lev = sum(base.values())                                      # 0.99 x 1.25 = 1.2375
    for shift, fires in ((0.026, True), (0.020, False)):
        w = {t: g + shift for t, g in base.items()}
        hold = holdings_for(w, loan=(sum(w.values()) - 1) * 100_000 + 50.0, margin=True)
        s = run_eval(raw, hold)
        assert s["status"] == "accepted", s["refusal_reasons"]
        assert not any(r["abs_trigger"] or r["rel_trigger"] for r in s["decision"]["rows"])
        assert s["decision"]["triggered"] is fires
        if fires:
            assert [t["kind"] for t in s["decision"]["triggers"]] == ["margin_leverage"]
            assert {t["side"] for t in s["trades"]} == {"SELL"}
            pt = s["post_trade"]
            pre_lev = s["valuation"]["leverage_assets_over_equity"]
            assert pre_lev - target_lev > 0.10
            # positions are back at target; the DBMF sale proceeds stay as USD cash (only buys trigger FX), so gross
            # assets/equity lands inside the band but not exactly on target, and the report says so
            assert abs(pt["leverage_assets_over_equity"] - target_lev) <= 0.10
            assert pt["leverage_assets_over_equity"] < pre_lev
            for r in pt["positions"]:
                assert abs(r["weight"] - r["target"]) < 0.001
            assert pt["margin_loan_cad"] < hold["margin_loan_cad"] and pt["cash_usd"] > 0
            assert any("converts currency only to fund buys" in n for n in s["notes"])
        else:
            assert s["trades"] == [] and "<= 0.10" in s["decision"]["leverage_check"]


def test_cost_estimates_follow_declared_model():
    s = run_eval(cfg_of("P4@1.0", overrides={"commission_cad": 4.95}), holdings_for({}))
    assert s["status"] == "accepted" and len(s["trades"]) == 4
    for t in s["trades"]:
        rate = FX if t["ccy"] == "USD" else 1.0
        value_cad = t["shares"] * PRICES[t["ticker"]][0] * rate
        assert t["est_value_cad"] == pytest.approx(value_cad, abs=0.01)
        assert t["est_spread_cad"] == pytest.approx(value_cad * DECLARED["half_spread"][t["ticker"]], abs=0.01)
        assert t["est_commission_cad"] == 4.95
        assert t["est_cost_cad"] == pytest.approx(t["est_spread_cad"] + 4.95, abs=0.01)
    (dbmf,) = [t for t in s["trades"] if t["ticker"] == "DBMF"]
    usd_needed = dbmf["shares"] * 28.0 * 1.001 + 4.95 / FX              # value + half-spread + commission, in USD
    fx = s["fx"]["cad_to_usd"]
    assert fx["for"] == ["DBMF"] and fx["usd_needed"] == pytest.approx(usd_needed, abs=0.01)
    assert fx["cad_spent"] == pytest.approx(usd_needed * FX / 0.999, abs=0.01)
    assert fx["est_cost_cad"] == pytest.approx(fx["cad_spent"] * 0.001, abs=0.01)
    c = s["costs"]
    assert c["commission_cad"] == pytest.approx(4 * 4.95)
    assert c["total_cad"] == pytest.approx(c["commission_cad"] + c["spread_cad"] + c["fx_cad"], abs=0.02)
    md = render_markdown(s)
    assert "0.10%" in md and "Norbert's gambit" in md and "DLR-U.TO" in md
    # CAD-only trades need no conversion and print no FX instructions
    s2 = run_eval(cfg_of("P3@1.0"), holdings_for({}))
    assert s2["fx"]["any_conversion"] is False and s2["costs"]["fx_cad"] == 0.0
    assert "No currency conversion is needed" in render_markdown(s2)


def test_report_prints_overrides():
    s = run_eval(cfg_of("P3@1.0", overrides={"commission_cad": 4.95, "min_trade_cad": 250}), holdings_for({}))
    md = render_markdown(s)
    assert "| commission_cad | 4.95 |" in md and "| min_trade_cad | 250 |" in md
    assert s["params"]["commission_cad"] == 4.95 and s["params"]["min_trade_cad"] == 250.0
    assert "None — all declared parameters apply." in render_markdown(run_eval(cfg_of(), holdings_for({})))


def test_report_contains_spec_section_6_items():
    hold = holdings_for({"XEQT.TO": 0.70, "ZAG.TO": 0.25}, cash_usd=100.0)
    md = render_markdown(run_eval(cfg_of("P4@1.0", "rrsp"), hold))
    for needle in ["## Recipe and targets", "Target weight of NAV", "## Current holdings, weights and drift",
                   "| Drift |", "## Band decision", "Decision: **full rebalance", "## Proposed trades",
                   "| Shares |", "Est. cost (CAD)", "## FX needed", "## Drawdown vs tolerance", "## Checks", "PASS"]:
        assert needle in md, needle


def test_snapshot_manifest_hash_recorded(tmp_path):
    store, version, _ = snapshot(tmp_path, price_rows(RD))
    manifest_sha = json.loads((store / "versions" / version / "manifest.json").read_text())["manifest_sha256"]
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of(), holdings_for(targets("P3@1.0")))
    out, log = tmp_path / "out", tmp_path / "log.jsonl"
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, out, log)) == 0
    s = load_summary(out)
    assert s["inputs"]["prices"]["manifest_sha256"] == manifest_sha
    assert s["inputs"]["prices"]["dataset_version"] == version and s["inputs"]["prices"]["mode"] == "verified"
    assert manifest_sha[:16] in next(out.glob("report_*.md")).read_text()
    (entry,) = read_chain(log)
    assert entry["body"]["inputs"]["prices"]["manifest_sha256"] == manifest_sha


def test_missing_snapshot_object_refused(tmp_path):
    store, version, _ = snapshot(tmp_path, price_rows(RD))
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of(), holdings_for(targets("P3@1.0")))
    sha = json.loads((store / "versions" / version / "manifest.json").read_text())["payload"]["records"][0]["sha256"]
    obj = store / "objects" / "sha256" / sha[:2] / sha
    os.chmod(obj.parent, 0o755)
    obj.unlink()
    out = tmp_path / "out"
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, out, tmp_path / "log.jsonl")) == 1
    assert_refused(load_summary(out), "research.data_snapshot.verify", "missing/corrupt frozen object")


def test_missing_holdings_file_refused(tmp_path):
    store, version, _ = snapshot(tmp_path, price_rows(RD))
    cfg_path, _ = write_inputs(tmp_path / "in", cfg_of(), holdings_for(targets("P3@1.0")))
    out, log = tmp_path / "out", tmp_path / "log.jsonl"
    assert cli.main(cli_args(cfg_path, tmp_path / "in" / "absent.json", store, version, RD, out, log)) == 1
    s = load_summary(out)
    assert_refused(s, "holdings file unparsable", "unreadable")
    assert s["inputs"]["holdings"]["sha256"] is None
    assert read_chain(log)[0]["body"]["status"] == "refused"


def test_cli_fatal_on_unreadable_config_writes_nothing(tmp_path):
    store, version, _ = snapshot(tmp_path, price_rows(RD))
    _, hold_path = write_inputs(tmp_path / "in", cfg_of(), holdings_for(targets("P3@1.0")))
    bad_cfg = tmp_path / "in" / "bad.json"
    bad_cfg.write_text("{not json")
    out, log = tmp_path / "out", tmp_path / "log.jsonl"
    assert cli.main(cli_args(bad_cfg, hold_path, store, version, RD, out, log)) == 2
    assert not out.exists() and not log.exists()


def test_paper_log_entry_hash_is_sha256_of_canonical_json(tmp_path):
    log = tmp_path / "paper_log.jsonl"
    e0 = paperlog.append(log, {"status": "accepted", "x": 1.5})
    e1 = paperlog.append(log, {"status": "refused", "x": "ü"})
    for e, prev in ((e0, "0" * 64), (e1, e0["entry_hash"])):
        body = {k: v for k, v in e.items() if k != "entry_hash"}
        canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        assert e["entry_hash"] == hashlib.sha256(canon).hexdigest()
        assert e["prev_hash"] == prev
    assert log.read_bytes().splitlines()[1] == paperlog.canonical(e1)


# ------------------------------------------------------------------------------------------------ review fixes -----
def _fake_forward(tmp_path, monkeypatch, *, registry=True):
    fake_dir = tmp_path / "reports" / "forward"
    fake_dir.mkdir(parents=True)
    fake = fake_dir / "registry.jsonl"
    if registry:
        fake.write_bytes(b"")
    monkeypatch.setattr(paperlog, "FORWARD_DIR", fake_dir)
    monkeypatch.setattr(paperlog, "FORWARD_REGISTRY_PATH", fake)
    return fake_dir, fake


@pytest.mark.parametrize("registry", [True, False])
def test_guard_path_is_case_insensitive_ap_safe_1(tmp_path, monkeypatch, registry):
    """AP-SAFE-1: on case-insensitive APFS, REPORTS/FORWARD/... and Reports/Forward/x.jsonl name the forward
    directory.  They are refused whether or not the registry file exists yet (and on case-sensitive file systems
    too: the comparison itself is case-insensitive)."""
    fake_dir, fake = _fake_forward(tmp_path, monkeypatch, registry=registry)
    for p in (tmp_path / "REPORTS" / "FORWARD" / "registry.jsonl", tmp_path / "Reports" / "Forward" / "x.jsonl",
              tmp_path / "reports" / "forward" / "REGISTRY.JSONL", tmp_path / "reports" / "FORWARD" / "new" / "a.md",
              tmp_path / "elsewhere" / "Registry.JSONL", tmp_path / "reports" / "x" / ".." / "Forward" / "y.jsonl"):
        with pytest.raises(PaperLogError):
            guard_path(p)
    assert guard_path(tmp_path / "reports" / "forwardish" / "x.jsonl").name == "x.jsonl"
    # the real repository layout, relative to the repo root, as in the review
    monkeypatch.undo()
    monkeypatch.chdir(REPO)
    for rel in ("REPORTS/FORWARD/registry.jsonl", "Reports/Forward/x.jsonl", "reports/FORWARD/REGISTRY.JSONL"):
        with pytest.raises(PaperLogError):
            guard_path(Path(rel))


def test_guard_path_file_identity_catches_what_names_miss_ap_safe_1(tmp_path, monkeypatch):
    """Even with the name comparison disabled, an existing ancestor that is the same directory as reports/forward
    (here: the case-variant spelling on a case-insensitive file system) is refused by samefile."""
    fake_dir, _fake = _fake_forward(tmp_path, monkeypatch)
    variant = tmp_path / "REPORTS" / "FORWARD"
    if not variant.exists():
        pytest.skip("case-sensitive file system: no case-variant alias exists")
    monkeypatch.setattr(paperlog, "_lexically_within", lambda _p, _r: False)
    with pytest.raises(PaperLogError, match="same directory"):
        guard_path(variant / "sub" / "x.jsonl")


def test_cli_refuses_case_variant_forward_log_and_writes_nothing(tmp_path, monkeypatch):
    fake_dir, fake = _fake_forward(tmp_path, monkeypatch, registry=False)
    store, version, _ = snapshot(tmp_path, price_rows(RD))
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of(), holdings_for(targets("P3@1.0")))
    log = tmp_path / "Reports" / "Forward" / "paper_log.jsonl"
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, tmp_path / "out", log)) == 2
    assert sorted(p.name for p in fake_dir.iterdir()) == [] and not (tmp_path / "out").exists()


def test_refused_after_checks_has_no_post_trade_and_labels_the_rejected_state_ap_safe_2():
    hold = holdings_for({}, margin=True)
    s = run_eval(cfg_of("P4@1.25", "nonreg_margin", overrides={"equity_assets_floor": 0.9}), hold)
    assert_refused(s, "equity_assets_floor")
    assert s["decision"]["triggered"] is True
    assert s["post_trade"] is None and s["trades"] == [] and s["costs"] is None and s["fx"] is None
    cs = s["checked_state"]
    assert cs["kind"] == "rejected_hypothetical_rebalance" and cs["rejected_trade_count"] == 4
    assert cs["basis"].startswith("REJECTED HYPOTHETICAL")
    assert s["decision"]["action"].startswith("none: REFUSED")
    md = render_markdown(s)
    assert "full rebalance of all positions to target" not in md
    assert "Position after trades" not in md and "Proposed trades" not in md
    assert "## REJECTED hypothetical state after a full rebalance (NOT proposed)" in md
    assert "none of these trades is proposed" in md and "Decision: **none: REFUSED" in md
    # refused with no trigger: the checked state is the current holdings, labelled as such
    w = drifted("P6a@1.25", {"RSST": 0.036, "SSO": -0.02, "XEQT.TO": -0.01})
    s = run_eval(cfg_of("P6a@1.25"), holdings_for(w))
    assert s["post_trade"] is None and s["checked_state"]["kind"] == "current_holdings"
    assert "State checked — current holdings (no trades proposed)" in render_markdown(s)
    # accepted runs keep post_trade and state the action
    ok = run_eval(cfg_of("P4@1.25", "nonreg_margin"), hold)
    assert ok["post_trade"] is not None and ok["checked_state"] is None
    assert ok["decision"]["action"] == "full rebalance of all positions to target"


def test_manifest_is_pinned_by_the_paper_log_ap_safe_3(tmp_path):
    """Same dataset_version, different content (a re-frozen or swapped store): refused, because the paper log
    already recorded another manifest for that version.  The refused entry does not move the pin."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    sa, v, _ = snapshot(tmp_path / "a", price_rows(RD), version="prices_v1")
    sb, _v, _ = snapshot(tmp_path / "b", price_rows(RD, prices={**PRICES, "XEQT.TO": (33.0, "CAD")}),
                         version="prices_v1")
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of(), holdings_for(targets("P3@1.0")))
    log = tmp_path / "log.jsonl"
    assert cli.main(cli_args(cfg_path, hold_path, sa, v, RD, tmp_path / "o1", log)) == 0
    pinned = load_summary(tmp_path / "o1")["inputs"]["prices"]["manifest_sha256"]
    assert cli.main(cli_args(cfg_path, hold_path, sb, v, RD, tmp_path / "o2", log)) == 1
    s = load_summary(tmp_path / "o2")
    assert_refused(s, "paper log entry seq 0 recorded manifest", pinned, "never changes")
    assert s["inputs"]["prices"]["pinned_manifest_sha256"] == pinned and s["inputs"]["prices"]["pinned_by_seq"] == 0
    assert "(MISMATCH)" in (tmp_path / "o2" / f"report_{RD.isoformat()}_P3@1.0.md").read_text()
    # the original store still runs (pin = first entry), and so does a new version name
    assert cli.main(cli_args(cfg_path, hold_path, sa, v, RD, tmp_path / "o3", log)) == 0
    sc, v2, _ = snapshot(tmp_path / "b", price_rows(RD, prices={**PRICES, "XEQT.TO": (33.0, "CAD")}),
                         version="prices_v2")
    assert cli.main(cli_args(cfg_path, hold_path, sc, v2, RD, tmp_path / "o4", log)) == 0


def test_expect_manifest_sha256_option_ap_safe_3(tmp_path):
    store, version, _ = snapshot(tmp_path, price_rows(RD))
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of(), holdings_for(targets("P3@1.0")))
    log = tmp_path / "log.jsonl"
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, tmp_path / "o1", log,
                             "--expect-manifest-sha256", "0" * 64)) == 1
    s = load_summary(tmp_path / "o1")
    assert_refused(s, "does not match the expected", "0" * 64)
    right = s["inputs"]["prices"]["manifest_sha256"]
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, tmp_path / "o2", log,
                             "--expect-manifest-sha256", right)) == 0
    before = log.read_bytes()
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, tmp_path / "o3", log,
                             "--expect-manifest-sha256", "XYZ")) == 2
    assert log.read_bytes() == before and not (tmp_path / "o3").exists()


def test_log_head_recorded_and_truncation_detectable_ap_safe_4(tmp_path):
    store, version, _ = snapshot(tmp_path, price_rows(RD))
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of(), holdings_for(targets("P3@1.0")))
    log = tmp_path / "log.jsonl"
    outs = []
    for i, rd in enumerate((RD, RD + timedelta(days=1), RD + timedelta(days=2))):
        out = tmp_path / f"o{i}"
        assert cli.main(cli_args(cfg_path, hold_path, store, version, rd, out, log)) == 0
        outs.append(load_summary(out))
    chain = read_chain(log)
    for i, doc in enumerate(outs):
        assert doc["paper_log"] == {"seq": i, "prev_entry_hash": chain[i]["prev_hash"], "entries_before": i}
        assert paperlog.check_summary_against_log(chain, doc) == []
        report = next((tmp_path / f"o{i}").glob("report_*.md")).read_text()
        assert f"entry seq {i}, chained after entry_hash `{chain[i]['prev_hash']}`" in report
    assert outs[0]["paper_log"]["prev_entry_hash"] == paperlog.GENESIS
    # drop the last line: the shorter chain still validates, but the last summary now points past its end
    lines = log.read_bytes().splitlines(keepends=True)
    log.write_bytes(b"".join(lines[:-1]))
    short = read_chain(log)
    assert len(short) == 2
    problems = paperlog.check_summary_against_log(short, outs[2])
    assert problems and "trailing lines were removed" in problems[0]
    # and a run appended after the truncation reuses seq 2 with a different body
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD + timedelta(days=3), tmp_path / "o9", log)) == 0
    assert "different body" in " ".join(paperlog.check_summary_against_log(read_chain(log), outs[2]))


def test_unexpected_exception_is_fatal_and_writes_nothing_ap_safe_5(tmp_path, capsys):
    """A valuation overflow (finite close x 1e9 shares = inf) raises inside the engine: exit 2, not 1."""
    prices = {**PRICES, "XEQT.TO": (1e300, "CAD")}
    store, version, _ = snapshot(tmp_path, price_rows(RD, prices=prices))
    hold = {"as_of": RD.isoformat(), "cash_cad": 0, "cash_usd": 0, "net_external_flow_cad": 0,
            "positions": {"XEQT.TO": 10**9}}
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of(), hold)
    log = tmp_path / "log.jsonl"
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, tmp_path / "out", log)) == 2
    assert "FATAL (unexpected error" in capsys.readouterr().err
    assert not log.exists() and not (tmp_path / "out").exists()


def test_failure_after_writing_started_removes_outputs_ap_safe_5(tmp_path, monkeypatch):
    store, version, _ = snapshot(tmp_path, price_rows(RD))
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of(), holdings_for(targets("P3@1.0")))
    log = tmp_path / "log.jsonl"
    out = tmp_path / "new" / "deeper" / "out"

    def boom(*_a, **_k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(cli, "append", boom)
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, out, log)) == 2
    assert not log.exists() and not (tmp_path / "new").exists()
    # a pre-existing --out directory with identical earlier outputs is left exactly as it was
    monkeypatch.undo()
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, out, log)) == 0
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    log_before = log.read_bytes()
    monkeypatch.setattr(cli, "append", boom)
    assert cli.main(cli_args(cfg_path, hold_path, store, version, RD, out, log)) == 2
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before and log.read_bytes() == log_before


def test_refusal_text_is_location_independent_ap_safe_6(tmp_path, monkeypatch):
    store, version, src = snapshot(tmp_path, price_rows(RD))
    cfg_path, hold_path = write_inputs(tmp_path / "in", cfg_of(), holdings_for(targets("P3@1.0")))
    m = store / "versions" / version / "manifest.json"
    os.chmod(m, 0o644)
    m.write_text(m.read_text().replace("synthetic_test", "synthetic_tesT"))
    texts = []
    for i, (st, ver) in enumerate(((store, version), (store, "missing_version"), (tmp_path / "no_store", "v"))):
        out = tmp_path / f"out{i}"
        assert cli.main(cli_args(cfg_path, hold_path, st, ver, RD, out, tmp_path / "log.jsonl")) == 1
        texts.append(" ".join(load_summary(out)["refusal_reasons"]))
        texts.append(next(out.glob("report_*.md")).read_text())
    blob = " ".join(texts)
    assert "manifest hash mismatch" in blob and "<price-store>/versions/missing_version/manifest.json" in blob
    for leak in (str(tmp_path), str(tmp_path.resolve()), str(REPO), str(Path.home())):
        assert leak not in blob
    # relative store paths give the same text
    monkeypatch.chdir(tmp_path)
    assert cli.main(cli_args(cfg_path, hold_path, Path("store"), "missing_version", RD, tmp_path / "rel",
                             tmp_path / "log2.jsonl")) == 1
    rel = " ".join(load_summary(tmp_path / "rel")["refusal_reasons"])
    assert rel == next(t for t in texts if "missing_version" in t and not t.startswith("#"))


def test_buys_never_convert_currency_in_both_directions():
    """Review (math): buys used to run largest-first regardless of currency, so a CAD buy could convert USD cash that
    a later USD buy then bought back (two conversion costs, and the report told the owner to convert both ways).
    USD-listed buys are now funded first, so each run converts in one direction at most."""
    # margin account: USD cash from distributions, CAD loan, ZAG.TO far under target, DBMF slightly under
    t = targets("P4@1.5", "nonreg_margin")
    w = {**t, "ZAG.TO": t["ZAG.TO"] - 0.10, "DBMF": t["DBMF"] - 0.004}
    hold = holdings_for(w, loan=48_000.0, cash_usd=400.0, margin=True)
    s = run_eval(cfg_of("P4@1.5", "nonreg_margin"), hold)
    assert s["status"] == "accepted" and {"ZAG.TO", "DBMF"} <= {x["ticker"] for x in s["trades"]}
    fx = s["fx"]
    assert not (fx["cad_to_usd"]["usd_needed"] > 0 and fx["usd_to_cad"]["cad_needed"] > 0), fx
    buys = [x for x in s["trades"] if x["side"] == "BUY"]
    assert [x["ccy"] for x in buys] == sorted((x["ccy"] for x in buys), key=lambda c: c != "USD")
    # the property over random accounts, every account type
    rng = random.Random(20260929)
    for _ in range(200):
        cid = rng.choice(sorted(CONFIGS))
        account = rng.choice(["tfsa", "rrsp", "nonreg_cash", "nonreg_margin"])
        tg = targets(cid, account)
        ww = {k: max(0.0, v + rng.uniform(-0.08, 0.08)) for k, v in tg.items()}
        margin = account == "nonreg_margin"
        usd = rng.choice([0.0, 300.0, 3_000.0])
        if not margin and sum(ww.values()) > 0.95:
            ww = {k: v * 0.95 / sum(ww.values()) for k, v in ww.items()}
        loan = (max(0.0, sum(ww.values()) - 1.0) * 100_000.0 + usd * FX + 2_000.0) if margin else 0.0
        hh = holdings_for(ww, loan=loan, cash_usd=usd if margin else 0.0, margin=margin)
        if not margin:
            hh["cash_usd"] = min(usd, 250.0)
        ss = run_eval(cfg_of(cid, account), hh)
        if ss["status"] == "accepted" and ss["fx"]:
            assert not (ss["fx"]["cad_to_usd"]["usd_needed"] > 0 and ss["fx"]["usd_to_cad"]["cad_needed"] > 0), \
                (cid, account, ss["fx"])
