"""Tests for research/forward: every registry here is a temporary file.

The only real files touched are READ: the frozen momentum_gold spec and, in one
test, bot/state (whose bytes and mtimes are asserted unchanged afterwards).
No network: prices come from injected fakes.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import pandas as pd
import pytest

from research.forward import adapters, evaluate, nyse, prices, record, registry, verify

UTC = dt.timezone.utc


def T(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text).replace(tzinfo=UTC)


@pytest.fixture
def reg(tmp_path) -> Path:
    path = tmp_path / "registry.jsonl"
    registry.init(path, note="test", now=T("2026-09-01T00:00:00"))
    return path


def _note(path, i, when):
    return registry.append(path, "note", payload={"i": i}, now=when)


def _lines(path):
    return path.read_text().split("\n")[:-1]


# -- chain --------------------------------------------------------------------------

def test_init_append_verify_and_head(reg):
    for i in range(3):
        _note(reg, i, T(f"2026-09-0{i + 2}T00:00:00"))
    report = registry.verify_chain(reg)
    assert report.ok and report.n_records == 4 and report.head_seq == 3
    recs = [json.loads(line) for line in _lines(reg)]
    assert recs[0]["prev_hash"] == registry.GENESIS_PREV
    assert all(recs[i]["prev_hash"] == recs[i - 1]["hash"] for i in range(1, 4))
    assert all(registry.record_hash(r) == r["hash"] for r in recs)
    assert verify.main(["--registry", str(reg)]) == 0


def test_init_refuses_to_overwrite(reg):
    with pytest.raises(FileExistsError):
        registry.init(reg)


def test_detects_edit(reg):
    _note(reg, 0, T("2026-09-02T00:00:00"))
    lines = _lines(reg)
    rec = json.loads(lines[1])
    rec["payload"]["i"] = 99
    lines[1] = registry.canonical_json(rec)
    reg.write_text("\n".join(lines) + "\n")
    codes = {e.code for e in registry.verify_chain(reg).errors}
    assert "hash" in codes
    assert verify.main(["--registry", str(reg)]) == 1


def test_detects_reorder(reg):
    for i in range(3):
        _note(reg, i, T(f"2026-09-0{i + 2}T00:00:00"))
    lines = _lines(reg)
    lines[1], lines[2] = lines[2], lines[1]
    reg.write_text("\n".join(lines) + "\n")
    codes = {e.code for e in registry.verify_chain(reg).errors}
    assert {"seq", "link"} <= codes


def test_detects_middle_deletion(reg):
    for i in range(3):
        _note(reg, i, T(f"2026-09-0{i + 2}T00:00:00"))
    lines = _lines(reg)
    del lines[2]
    reg.write_text("\n".join(lines) + "\n")
    codes = {e.code for e in registry.verify_chain(reg).errors}
    assert {"seq", "link"} <= codes


def test_tail_truncation_and_full_rewrite_need_an_anchor(reg):
    for i in range(3):
        _note(reg, i, T(f"2026-09-0{i + 2}T00:00:00"))
    head = registry.verify_chain(reg)
    anchor = [(head.head_seq, head.head_hash)]
    # truncating the tail leaves a valid chain; only the anchor exposes it
    lines = _lines(reg)
    reg.write_text("\n".join(lines[:-1]) + "\n")
    assert registry.verify_chain(reg).ok
    assert {e.code for e in registry.verify_chain(reg, anchors=anchor).errors} == {"anchor_missing"}
    # a full rewrite with recomputed hashes also verifies on its own
    reg.unlink()
    registry.init(reg, note="test", now=T("2026-09-01T00:00:00"))
    _note(reg, 0, T("2026-09-02T00:00:00"))
    _note(reg, 1, T("2026-09-03T00:00:00"))
    _note(reg, 42, T("2026-09-04T00:00:00"))  # altered history
    assert registry.verify_chain(reg).ok
    assert "anchor_mismatch" in {e.code for e in registry.verify_chain(reg, anchors=anchor).errors}


def test_refuses_to_append_to_broken_chain(reg):
    _note(reg, 0, T("2026-09-02T00:00:00"))
    reg.write_text(reg.read_text().replace('"i":0', '"i":1'))
    with pytest.raises(registry.RegistryError):
        _note(reg, 2, T("2026-09-03T00:00:00"))


def test_time_order_and_clock_regression(reg):
    _note(reg, 0, T("2026-09-05T00:00:00"))
    with pytest.raises(registry.RegistryError):
        _note(reg, 1, T("2026-09-04T00:00:00"))  # writer clock behind the chain
    last = json.loads(_lines(reg)[-1])
    forged = registry._build(2, last["hash"], "note", T("2026-09-03T00:00:00"), None, None, None, None, None, {})
    reg.write_text(reg.read_text() + registry.canonical_json(forged) + "\n")
    assert "time_order" in {e.code for e in registry.verify_chain(reg).errors}


def test_unterminated_line_is_an_error(reg):
    reg.write_text(reg.read_text() + '{"partial": ')
    assert not registry.verify_chain(reg).ok


# -- calendar ------------------------------------------------------------------------

def test_nyse_calendar_2026():
    h = nyse.holidays(2026)
    for d in ["2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19",
              "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25"]:
        assert dt.date.fromisoformat(d) in h
    assert nyse.early_closes(2026) == {dt.date(2026, 11, 27), dt.date(2026, 12, 24)}
    assert nyse.first_session_of_month(2026, 10) == dt.date(2026, 10, 1)
    assert nyse.first_session_of_month(2027, 1) == dt.date(2027, 1, 4)  # Jan 1 Fri holiday
    assert nyse.next_session(dt.date(2026, 10, 1)) == dt.date(2026, 10, 2)
    assert nyse.next_session(dt.date(2026, 7, 2)) == dt.date(2026, 7, 6)
    assert nyse.open_utc(dt.date(2026, 10, 2)) == T("2026-10-02T13:30:00")
    assert nyse.close_utc(dt.date(2026, 11, 27)) == T("2026-11-27T18:00:00")  # 13:00 EST
    assert nyse.close_utc(dt.date(2026, 12, 1)) == T("2026-12-01T21:00:00")  # 16:00 EST
    assert nyse._easter(2027) == dt.date(2027, 3, 28)


# -- prices ----------------------------------------------------------------------------

def _bars_csv(symbol: str, days: dict[str, tuple[float, float]], utc_offset: int, skip_last=()) -> str:
    """30m bars 08:00-23:30 UTC; regular-session bars get the given open/close."""
    rows = ["time,open,high,low,close,volume"]
    for day, (o, c) in days.items():
        open_utc = dt.datetime.fromisoformat(day).replace(hour=9, minute=30) + dt.timedelta(hours=utc_offset)
        close_utc = open_utc + dt.timedelta(hours=6, minutes=30)
        t = dt.datetime.fromisoformat(day).replace(hour=8)
        while t.hour < 24 and t.date() == dt.date.fromisoformat(day):
            regular = open_utc <= t < close_utc
            if regular and day in skip_last and t == close_utc - dt.timedelta(minutes=30):
                t += dt.timedelta(minutes=30)
                continue
            if t == open_utc:
                bo, bc = o, o + 0.1
            elif t == close_utc - dt.timedelta(minutes=30):
                bo, bc = c - 0.1, c
            elif regular:
                bo, bc = o + 0.2, o + 0.2
            else:
                bo, bc = o - 5, o - 5  # extended hours: very different prices
            rows.append(f"{t:%Y-%m-%dT%H:%M:%SZ},{bo},{bo},{bc},{bc},10")
            t += dt.timedelta(minutes=30)
    return f"{symbol} 30m via lse: n bars\n" + "\n".join(rows)


def test_lse_reconstruction_filters_to_regular_session():
    edt = _bars_csv("X", {"2026-09-21": (100.0, 101.0)}, 4)
    est = _bars_csv("X", {"2026-12-01": (50.0, 51.0)}, 5)
    partial = _bars_csv("X", {"2026-09-22": (10.0, 11.0)}, 4, skip_last={"2026-09-22"})
    sess = prices.reconstruct_sessions(pd.concat([prices.parse_lse_csv(t) for t in (edt, est, partial)]))
    assert sess.loc[dt.date(2026, 9, 21), "open"] == 100.0 and sess.loc[dt.date(2026, 9, 21), "close"] == 101.0
    assert sess.loc[dt.date(2026, 9, 21), "n_bars"] == 13 and sess.loc[dt.date(2026, 9, 21), "complete"]
    assert sess.loc[dt.date(2026, 12, 1), "open"] == 50.0 and sess.loc[dt.date(2026, 12, 1), "close"] == 51.0
    assert not sess.loc[dt.date(2026, 9, 22), "complete"]


class FakeMarket:
    """Injectable LSE fetcher + yfinance history over a dict of official prices."""

    def __init__(self, official: dict[str, dict[str, tuple]], lse_symbols=(), lse_close_shift=0.0):
        self.official = official  # symbol -> date -> (open, close[, dividend])
        self.lse_symbols = set(lse_symbols)
        self.shift = lse_close_shift
        self.calls = []

    def fetch(self, symbol, timeframe, start, end, limit):
        self.calls.append((symbol, timeframe, start, end))
        if symbol not in self.lse_symbols:
            raise LookupError(f"'{symbol}' has no candle data")
        days = {d: (v[0], v[1] + self.shift) for d, v in self.official[symbol].items() if start <= d < end}
        return _bars_csv(symbol, days, 4)

    def history(self, symbol, start, end):
        rows = {pd.Timestamp(d, tz="America/New_York"): {"Open": v[0], "Close": v[1], "Dividends": (v[2] if len(v) > 2 else 0.0),
                                                           "Stock Splits": 0.0}
                for d, v in self.official.get(symbol, {}).items() if start <= dt.date.fromisoformat(d) <= end}
        return pd.DataFrame.from_dict(rows, orient="index")

    def book(self, prefer="lse"):
        return prices.PriceBook(prefer, prices.LSESource(self.fetch), prices.YFSource(self.history))


def test_official_sessions_lse_primary_yf_fallback_and_crosscheck():
    m = FakeMarket({"GLD": {"2026-09-21": (400.0, 398.0)}, "SPMO": {"2026-09-21": (151.0, 152.0)}},
                   lse_symbols={"GLD"}, lse_close_shift=0.04)
    book = m.book()
    g = book.get("GLD", dt.date(2026, 9, 21), dt.date(2026, 9, 21)).loc[dt.date(2026, 9, 21)]
    assert g["close_source"] == prices.SOURCE_LSE and g["close"] == pytest.approx(398.04)
    assert g["close_diff_bps"] == pytest.approx((398.04 / 398 - 1) * 1e4)
    s = book.get("SPMO", dt.date(2026, 9, 21), dt.date(2026, 9, 21)).loc[dt.date(2026, 9, 21)]
    assert s["close_source"] == prices.SOURCE_YF and s["close"] == 152.0
    assert "SPMO" in book.errors()["lse"]
    y = m.book("yfinance").get("GLD", dt.date(2026, 9, 21), dt.date(2026, 9, 21)).loc[dt.date(2026, 9, 21)]
    assert y["close_source"] == prices.SOURCE_YF and y["close"] == 398.0


# -- momentum_gold_v1 ----------------------------------------------------------------------

def test_mg_frozen_rules_reproduce_the_registered_hash():
    frozen, prov = adapters.mg_frozen_spec()
    assert prov["rules_match_registration_event"]
    assert prov["spec_sha256_in_registration_event"] == "56ee118ce04e7ea4383630628b5c46790fc4c3ea0aab90b5d4736aab6293e221"
    assert frozen["weights"] == {"SPMO": 0.5, "GLD": 0.5}
    ev = adapters.mg_evaluation(frozen)
    assert ev["execution"] == "next_open" and ev["cost_per_side_bps"] == 5 and ev["fee_per_order_usd"] == 1


def test_mg_decision_timing_and_targets(reg):
    adapters.register_momentum_gold(reg, now=T("2026-09-23T08:00:00"))
    m = FakeMarket({"GLD": {"2026-10-01": (400.0, 401.0)}, "SPMO": {"2026-10-01": (150.0, 151.0)},
                    "SPY": {"2026-10-01": (600.0, 601.0)}}, lse_symbols={"GLD", "SPY"})
    day = dt.date(2026, 10, 1)
    with pytest.raises(adapters.AdapterError, match="too early"):
        adapters.record_momentum_gold(reg, day, now=T("2026-10-01T20:05:00"), pricebook=m.book())  # 16:05 ET
    with pytest.raises(adapters.AdapterError, match="first NYSE session"):
        adapters.record_momentum_gold(reg, dt.date(2026, 10, 2), now=T("2026-10-02T21:00:00"), pricebook=m.book())
    with pytest.raises(adapters.AdapterError, match="too late"):
        adapters.record_momentum_gold(reg, day, now=T("2026-10-02T13:30:00"), pricebook=m.book())  # 09:30 ET next day
    rec = adapters.record_momentum_gold(reg, day, now=T("2026-10-01T21:00:00"), pricebook=m.book())
    assert rec["payload"]["targets"] == {"SPMO": 0.5, "GLD": 0.5}
    assert rec["intended_execution_utc"] == "2026-10-02T13:30:00.000000Z" and rec["market_asof"] == "2026-10-01"
    assert rec["payload"]["asof_closes"]["SPMO"]["source"] == prices.SOURCE_YF
    assert rec["payload"]["asof_closes"]["GLD"]["source"] == prices.SOURCE_LSE
    assert evaluate.classify(rec) == []
    with pytest.raises(registry.RegistryError, match="already recorded"):
        adapters.record_momentum_gold(reg, day, now=T("2026-10-01T22:00:00"), pricebook=m.book())
    with pytest.raises(registry.RegistryError, match="already recorded"):  # --allow-late cannot re-decide it
        adapters.record_momentum_gold(reg, day, now=T("2026-10-02T14:00:00"), pricebook=m.book(), allow_late=True)
    assert registry.verify_chain(reg).ok


# -- generic + evaluator -------------------------------------------------------------------

def _generic_spec(tmp_path, execution="next_open", benchmark=None):
    spec = {"name": "test candidate", "evaluation": {"type": "targets", "instruments": ["AAA"], "execution": execution,
                                                     "capital_usd": 100000, "cost_per_side_bps": 5,
                                                     "stress_cost_per_side_bps": 15, "fee_per_order_usd": 1,
                                                     "benchmark_targets": benchmark}}
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(spec))
    return p


def test_evaluator_counts_only_clean_decisions_and_charges_costs(reg, tmp_path):
    adapters.register_generic(reg, "cand_v1", _generic_spec(tmp_path), now=T("2026-09-10T00:00:00"))
    m = FakeMarket({"AAA": {"2026-09-14": (99.0, 99.5), "2026-09-15": (100.0, 101.0),
                            "2026-09-16": (101.0, 102.0, 0.5), "2026-09-17": (102.0, 103.0)}})
    clean = adapters.record_targets_decision(reg, "cand_v1", dt.date(2026, 9, 14), {"AAA": 1.0},
                                             now=T("2026-09-14T21:00:00"), pricebook=m.book())
    late = adapters.record_targets_decision(reg, "cand_v1", dt.date(2026, 9, 15), {"AAA": 0.5},
                                            now=T("2026-09-16T15:00:00"), pricebook=m.book(), allow_late=True)
    assert "recorded_after_execution" in late["payload"]["flags"]
    out = evaluate.evaluate(reg, dt.date(2026, 9, 16), pricebook=m.book())
    s = out["strategies"]["cand_v1"]
    assert s["n_decisions"] == 2 and s["n_counted"] == 1
    assert s["excluded"][0]["key"] == "2026-09-15" and "recorded_after_execution" in s["excluded"][0]["reasons"]
    base = next(iter(s["results"].values()))["base"]
    invested = 99999 / 1.0005  # V + 5 bps * V + $1 = 100,000
    units = invested / 100.0
    assert base["total_cost_usd"] == pytest.approx(invested * 5e-4 + 1, rel=1e-9)
    nav1 = units * 101 + (100000 - invested - base["total_cost_usd"])
    nav2 = units * 102 + units * 0.5 + (100000 - invested - base["total_cost_usd"])
    assert [r["nav"] for r in base["daily"]] == pytest.approx([nav1, nav2], rel=1e-9)
    assert base["stats"]["sessions"] == 2 and "descriptive only" in base["stats"]["status"]
    assert clean["seq"] < late["seq"]


def test_generic_close_execution_must_be_recorded_before_the_close(reg, tmp_path):
    adapters.register_generic(reg, "cand_close", _generic_spec(tmp_path, execution="close"), now=T("2026-09-10T00:00:00"))
    with pytest.raises(adapters.AdapterError, match="too late"):
        adapters.record_targets_decision(reg, "cand_close", dt.date(2026, 9, 14), {"AAA": 1.0},
                                         now=T("2026-09-14T20:00:00"), pricebook=None)  # 16:00 ET
    rec = adapters.record_targets_decision(reg, "cand_close", dt.date(2026, 9, 14), {"AAA": 1.0},
                                           now=T("2026-09-14T19:00:00"), pricebook=None)
    assert rec["market_asof"] == "2026-09-11" and evaluate.classify(rec) == []
    with pytest.raises(adapters.AdapterError):
        adapters.record_targets_decision(reg, "cand_close", dt.date(2026, 9, 15), {"BBB": 1.0},
                                         now=T("2026-09-15T14:00:00"), pricebook=None)


# -- PEAD (read-only adapter) --------------------------------------------------------------------

def _epoch(text):
    return T(text).timestamp()


def _fake_bot_state(tmp_path) -> tuple[Path, Path]:
    state = tmp_path / "bot_state"
    state.mkdir()
    cycles = [
        {"ts": _epoch("2026-09-17T20:40:53"), "as_of_date": "2026-09-17", "entries": [
            {"ticker": "LEN", "sue": -0.42, "calibrated_proba": 0.43, "direction": "short", "allowed": False,
             "reason": "no_conviction", "detail": "", "size_fraction": 0.0, "earnings_date": "2026-09-16T16:00:00"}]},
        {"ts": _epoch("2026-08-01T22:42:00"), "as_of_date": "2026-08-01", "backfill": True, "entries": [
            {"ticker": "OLD", "allowed": True, "direction": "long", "earnings_date": "2026-07-31T08:00:00"}]},
        {"ts": _epoch("2026-09-22T23:35:43"), "as_of_date": "2026-09-22", "entries": [
            {"ticker": "AZO", "sue": 1.18, "calibrated_proba": 0.748, "direction": "long", "allowed": True,
             "reason": "executed", "detail": "", "size_fraction": 0.05, "earnings_date": "2026-09-22T06:00:00"}]},
    ]
    ledger = [
        {"event": "open", "entry_date": "2026-08-20", "ticker": "DE", "direction": "long", "fill_price": 620.0,
         "size_fraction": 0.02, "notional": 2000.0, "ts": _epoch("2026-08-20T22:42:00"), "backfill": True},
        {"event": "close", "ticker": "DE", "exit_price": 685.0, "realized_pnl": 160.0, "exit_date": "2026-09-17",
         "ts": _epoch("2026-09-17T22:43:09")},
        {"event": "open", "entry_date": "2026-09-22", "ticker": "AZO", "direction": "long", "fill_price": 2894.73,
         "size_fraction": 0.05, "notional": 5320.0, "ts": _epoch("2026-09-22T23:35:43")},
    ]
    (state / "cycle_log.jsonl").write_text("".join(json.dumps(c) + "\n" for c in cycles))
    (state / "paper_ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ledger))
    root = tmp_path / "root"
    (root / "bot").mkdir(parents=True)
    code = root / "bot" / "run_cycle.py"
    code.write_text("# frozen\n")
    os.utime(code, (T("2026-09-19T04:24:00").timestamp(),) * 2)
    return state, root


def test_pead_ingest_excludes_backfill_and_flags_late_decisions(reg, tmp_path):
    state, root = _fake_bot_state(tmp_path)
    before = {p.name: p.read_bytes() for p in state.iterdir()}
    dry = adapters.ingest_pead(reg, state_dir=state, dry_run=True, root=root)
    assert dry["n_new"] == 2 and len(_lines(reg)) == 1  # dry run wrote nothing
    summary = adapters.ingest_pead(reg, state_dir=state, now=T("2026-09-23T08:00:00"), root=root)
    assert summary["excluded"]["backfill_ledger_opens"] == 1
    assert summary["excluded"]["backfill_cycle_records_in_live_log"] == 1
    assert [x["ticker"] for x in summary["excluded"]["live_exits_of_backfilled_positions"]] == ["DE"]
    recs = registry.load_records(reg)
    decisions = {r["decision_key"]: r for r in recs if r["kind"] == "decision"}
    assert set(decisions) == {"LEN|2026-09-16", "AZO|2026-09-22"}
    azo = decisions["AZO|2026-09-22"]
    assert azo["intended_execution_utc"] == "2026-09-22T20:00:00.000000Z"  # 16:00 ET close
    assert azo["payload"]["source_decided_at_utc"] == "2026-09-22T23:35:43.000000Z"
    assert "decided_after_execution" in azo["payload"]["flags"]
    assert "decided_under_earlier_code" in decisions["LEN|2026-09-16"]["payload"]["flags"]
    assert azo["payload"]["fill"]["price"] == 2894.73
    assert set(evaluate.classify(azo)) >= {"recorded_after_execution", "source_decided_after_execution"}
    again = adapters.ingest_pead(reg, state_dir=state, now=T("2026-09-23T09:00:00"), root=root)
    assert again["n_new"] == 0 and len(registry.load_records(reg)) == len(recs)
    assert {p.name: p.read_bytes() for p in state.iterdir()} == before

    m = FakeMarket({"AZO": {"2026-09-22": (2894.25, 2894.73), "2026-09-23": (2900.0, 2950.0),
                            "2026-09-24": (2950.0, 2960.0)}})
    out = evaluate.evaluate(reg, dt.date(2026, 9, 24), pricebook=m.book())
    res = out["strategies"]["pead_bot_v1"]
    assert res["n_counted"] == 0
    assert res["results"]["counted_summary"]["n_trades"] == 0
    late = res["results"]["late_repriced_trades"][0]
    assert late["entry_date"] == "2026-09-23" and late["entry_at"] == "open" and late["entry_price"] == 2900.0
    assert late["net_return"] == pytest.approx(2960 / 2900 - 1 - 5e-4 * (1 + 2960 / 2900))
    assert late["status"] == "open (marked)"


def test_pead_ingest_of_real_bot_state_is_read_only(tmp_path):
    state = adapters.BOT_STATE
    if not (state / "cycle_log.jsonl").exists():
        pytest.skip("no bot state on this machine")
    watched = [p for p in state.rglob("*") if p.is_file()]
    before = {p: (p.stat().st_mtime_ns, registry.sha256_file(p)) for p in watched}
    path = tmp_path / "registry.jsonl"
    registry.init(path)
    summary = adapters.ingest_pead(path, state_dir=state)
    after = {p: (p.stat().st_mtime_ns, registry.sha256_file(p)) for p in watched}
    assert before == after  # nothing under bot/state changed
    recs = registry.load_records(path)
    keys = {r["decision_key"] for r in recs if r["kind"] == "decision"}
    assert "AZO|2026-09-22" in keys
    assert summary["excluded"]["backfill_ledger_opens"] >= 51
    assert all("backfill" not in json.dumps(r["payload"].get("flags")) for r in recs if r["kind"] == "decision")
    assert all(evaluate.classify(r) for r in recs if r["kind"] == "decision")  # none is forward-clean today


# -- CLI --------------------------------------------------------------------------------------

def test_cli_init_register_and_refuse_early_decision(tmp_path, capsys):
    path = tmp_path / "cli_registry.jsonl"
    assert record.main(["--registry", str(path), "--init"]) == 0
    assert record.main(["--registry", str(path), "--strategy", "momentum_gold_v1", "--register-spec"]) == 0
    assert record.main(["--registry", str(path), "--strategy", "momentum_gold_v1", "--register-spec"]) == 2
    code = record.main(["--registry", str(path), "--strategy", "momentum_gold_v1", "--date", "2026-09-22",
                        "--no-prices", "--dry-run"])
    assert code == 2 and "first NYSE session" in capsys.readouterr().err
    assert verify.main(["--registry", str(path)]) == 0
    kinds = [json.loads(line)["kind"] for line in _lines(path)]
    assert kinds == ["genesis", "spec_registration"]


def test_evaluator_reports_missed_scheduled_decisions(reg):
    adapters.register_momentum_gold(reg, now=T("2026-09-23T08:00:00"))
    spec_reg = registry.registered_specs(registry.load_records(reg))["momentum_gold_v1"][-1]
    assert evaluate.missed_decisions(spec_reg, [], dt.date(2026, 9, 30)) == []
    assert evaluate.missed_decisions(spec_reg, [], dt.date(2026, 11, 5)) == ["2026-10-01", "2026-11-02"]
    assert evaluate.missed_decisions(spec_reg, [{"decision_key": "2026-10-01"}], dt.date(2026, 10, 30)) == []
