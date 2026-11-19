"""Scenario tests for live.zb_itb.trader against FakeBroker (no network, no orders)."""
import json, tempfile
from pathlib import Path
import live.zb_itb.trader as T
from live.zb_itb.broker import FakeBroker

def setup(sig_d=1, **fb):
    tmp = Path(tempfile.mkdtemp()); T.JOURNAL, T.STATE, T.KILL = tmp / "j.jsonl", tmp / "s.json", tmp / "KILL"
    T.CFG["virtual_capital_usd"] = None          # broker-equity tests; virtual-account tests set it explicitly
    T.ACCOUNTS = {"ITB": {"symbol": "ITB", "env": ".env.alpaca", "start_equity_usd": 2000, "virtual": False}}
    b = FakeBroker(**fb); T.get_broker = lambda dry, account=None: b
    T.signal = lambda day, dry: {"d": sig_d, "zb_p0_prev1600": 1.0, "zb_p1_0900": 1.0}
    return b
def events(): return [json.loads(l)["event"] for l in T.JOURNAL.read_text().splitlines()] if T.JOURNAL.exists() else []
def recs(): return [json.loads(l) for l in T.JOURNAL.read_text().splitlines()] if T.JOURNAL.exists() else []

def test_full_cycle_long():
    b = setup(1); T.cmd_enter(True)
    assert b.position("ITB") and float(b.position("ITB")["qty"]) > 0
    assert any(o["type"] == "stop" and o["side"] == "sell" for o in b.orders())
    T.cmd_exit(True); assert b.position("ITB") is None and not b.orders()
    T.cmd_failsafe(True); assert events()[-1] == "failsafe_ok"
def test_short_cycle():
    b = setup(-1); T.cmd_enter(True)
    assert float(b.position("ITB")["qty"]) < 0 and any(o["type"] == "stop" and o["side"] == "buy" for o in b.orders())
def test_long_only_skips_short():
    T.CFG["side_mode"] = "long_only"; b = setup(-1); T.cmd_enter(True); T.CFG["side_mode"] = "long_short"
    assert b.position("ITB") is None and events()[-1] == "skip"
def test_cannot_short():
    b = setup(-1, shortable=False); T.cmd_enter(True); assert b.position("ITB") is None
def test_small_account_no_short():
    b = setup(-1, equity=1500); T.cmd_enter(True); assert b.position("ITB") is None
def test_pdt_guard():
    b = setup(1, equity=10_000, daytrades=3); T.cmd_enter(True); assert b.position("ITB") is None
def test_kill_file():
    b = setup(1); T.KILL.write_text("manual"); T.cmd_enter(True); assert b.position("ITB") is None
def test_drawdown_kill():
    b = setup(1, equity=10_000); T.STATE.write_text(json.dumps({"accounts": {"ITB": {"hw_dry-run": 12_000}}})); T.cmd_enter(True)
    assert T.KILL.exists() and b.position("ITB") is None
def test_no_double_entry():
    b = setup(1); T.cmd_enter(True); n = len(b.log); T.cmd_enter(True); assert len(b.log) == n
def test_size_whole_shares_and_cap():
    b = setup(1, equity=1_000_000, px=95.0); T.cmd_enter(True)
    q = float(b.position("ITB")["qty"]); assert q == int(q) and q * 95 <= T.CFG["max_notional_usd"]
def test_tiny_account_skips():
    b = setup(1, equity=50, px=95.0); T.cmd_enter(True); assert b.position("ITB") is None
def test_auto_long_only_below_2k():
    T.CFG["side_mode"] = "auto"; b = setup(-1, equity=1500); T.cmd_enter(True)
    assert b.position("ITB") is None and events()[-1] == "skip"
def test_auto_shorts_at_2k_plus():
    T.CFG["side_mode"] = "auto"; b = setup(-1, equity=30_000); T.cmd_enter(True)
    assert float(b.position("ITB")["qty"]) < 0
def test_auto_longs_always():
    T.CFG["side_mode"] = "auto"; b = setup(1, equity=500, px=95.0); T.cmd_enter(True)
    assert float(b.position("ITB")["qty"]) > 0
def test_regime_off_skips():
    b = setup(1); T.regime_corr = lambda day, dry: -0.2; T.cmd_enter(True)
    assert b.position("ITB") is None and any("regime off" in json.loads(l).get("reason", "") for l in T.JOURNAL.read_text().splitlines())
def test_regime_on_trades():
    b = setup(1); T.regime_corr = lambda day, dry: 0.5; T.cmd_enter(True); assert b.position("ITB")
def test_regime_missing_fails_open():
    b = setup(1); T.regime_corr = lambda day, dry: None; T.cmd_enter(True); assert b.position("ITB")
def test_position_exists_despite_unfilled_status_gets_stop(monkeypatch):
    """2026-10-19 regression: late market entry filled after the poll window; the trader must still protect the position."""
    b = setup(1); monkeypatch.setattr(T, "regime_corr", lambda day, dry: 0.5)
    orig = b.submit
    def submit(**kw):
        o = orig(**kw)
        if kw.get("type") == "market": o["status"] = "accepted"      # broker keeps saying 'not filled'...
        return o                                                        # ...but FakeBroker has opened the position
    b.submit = submit
    monkeypatch.setattr(T, "sleep_until", lambda t, dry: None)
    monkeypatch.setattr(T.time, "sleep", lambda s: None)
    monkeypatch.setitem(T.CFG, "opg_deadline_et", "23:59:00"); monkeypatch.setitem(T.CFG, "late_entry_cutoff_et", "23:59:30")
    monkeypatch.setitem(T.CFG, "signal_ready_et", "00:00:00")
    T.cmd_enter(False)
    ev = events()
    assert "warn" in ev and "stop_placed" in ev and any(o["type"] == "stop" for o in b.orders())

def test_virtual_1k_sizes_small_and_long_only(monkeypatch):
    b = setup(1, equity=100_000, px=86.0); monkeypatch.setitem(T.CFG, "virtual_capital_usd", 1000); monkeypatch.setattr(T, "regime_corr", lambda d, dry: 0.5)
    T.ACCOUNTS["ITB"]["virtual"] = True
    T.cmd_enter(True); q = float(b.position("ITB")["qty"]); assert q == 11            # floor(1000 / (86 * 1.01))
def test_virtual_1k_skips_shorts(monkeypatch):
    monkeypatch.setitem(T.CFG, "side_mode", "auto")
    b = setup(-1, equity=100_000); monkeypatch.setitem(T.CFG, "virtual_capital_usd", 1000); monkeypatch.setattr(T, "regime_corr", lambda d, dry: 0.5)
    T.ACCOUNTS["ITB"]["virtual"] = True
    T.cmd_enter(True); assert b.position("ITB") is None
def test_virtual_equity_updates_on_exit(monkeypatch):
    b = setup(1, equity=100_000, px=86.0); monkeypatch.setitem(T.CFG, "virtual_capital_usd", 1000); monkeypatch.setattr(T, "regime_corr", lambda d, dry: 0.5)
    T.ACCOUNTS["ITB"]["virtual"] = True
    T.cmd_enter(True); b._pos["unrealized_pl"] = "4.40"; T.cmd_exit(True)
    assert abs(T.virtual_equity("dry-run") - (1004.40 - T.virtual_fees(11, 86.0))) < 0.006 and T.virtual_commission(11) > 0.7

def test_dual_accounts_one_signal(monkeypatch):
    """The live shape: one ZB signal, two brokers, two symbols, two stops, two account-tagged journals."""
    tmp = Path(tempfile.mkdtemp()); T.JOURNAL, T.STATE, T.KILL = tmp / "j.jsonl", tmp / "s.json", tmp / "KILL"
    T.CFG["virtual_capital_usd"] = None
    T.ACCOUNTS = {
        "ITB": {"symbol": "ITB", "env": ".env.alpaca.itb", "start_equity_usd": 2000, "virtual": False},
        "NAIL": {"symbol": "NAIL", "env": ".env.alpaca.nail", "start_equity_usd": 2000, "virtual": False},
    }
    brokers = {"ITB": FakeBroker(equity=2000, px=85.0), "NAIL": FakeBroker(equity=2000, px=25.0)}
    T.get_broker = lambda dry, account=None: brokers[account]
    T.signal = lambda day, dry: {"d": 1, "zb_p0_prev1600": 1.0, "zb_p1_0900": 1.0}
    T.regime_corr = lambda day, dry: 0.5
    T.cmd_enter(True)
    assert float(brokers["ITB"].position("ITB")["qty"]) > 0
    assert float(brokers["NAIL"].position("NAIL")["qty"]) > 0
    assert any(o["type"] == "stop" and o["symbol"] == "ITB" for o in brokers["ITB"].orders())
    assert any(o["type"] == "stop" and o["symbol"] == "NAIL" for o in brokers["NAIL"].orders())
    assert {r.get("account") for r in recs() if r.get("event") == "entry_submitted"} == {"ITB", "NAIL"}
    T.cmd_exit(True)
    assert brokers["ITB"].position("ITB") is None and brokers["NAIL"].position("NAIL") is None
def test_account_highwater_ignores_legacy_single_account(monkeypatch):
    # 2026-10-21 regression: a fresh $2k account inherited the old $100k paper high-water and tripped the kill switch
    b = setup(1, equity=2000, px=86.0); monkeypatch.setattr(T, "regime_corr", lambda d, dry: 0.5)
    T.STATE.write_text(json.dumps({"hw_dry-run": 100_129.8}))
    assert T.drawdown_guard(b.account(), "dry-run", "ITB") and not T.KILL.exists()
    st = json.loads(T.STATE.read_text()); assert st["accounts"]["ITB"]["hw_dry-run"] == 2000
def test_account_highwater_still_kills_real_drawdown():
    b = setup(1, equity=1600)
    T.STATE.write_text(json.dumps({"accounts": {"ITB": {"hw_dry-run": 2000}}}))
    assert not T.drawdown_guard(b.account(), "dry-run", "ITB") and T.KILL.exists()

def _live_clock(monkeypatch):
    monkeypatch.setattr(T, "regime_corr", lambda day, dry: 0.5)
    monkeypatch.setattr(T, "sleep_until", lambda t, dry: None)
    monkeypatch.setattr(T.time, "sleep", lambda s: None)
    monkeypatch.setitem(T.CFG, "opg_deadline_et", "23:59:00"); monkeypatch.setitem(T.CFG, "late_entry_cutoff_et", "23:59:30")
    monkeypatch.setitem(T.CFG, "signal_ready_et", "00:00:00")
def test_partial_auction_fill_tops_up_remaining(monkeypatch):
    """2026-10-22 regression: the auction filled 3 of 71 NAIL; the late order must buy only the rest and stop the whole position."""
    b = setup(1, equity=2000, px=27.0); _live_clock(monkeypatch)
    orig = b.submit
    def submit(**kw):
        if kw.get("time_in_force") == "opg":
            o = orig(**{**kw, "type": "market", "qty": "3"})                 # 3 shares fill in the auction...
            o.update(status="expired", filled_qty="3", qty=kw["qty"], type="market", time_in_force="opg"); return o
        return orig(**kw)
    b.submit = submit
    T.cmd_enter(False)
    late = [r for r in recs() if r["event"] == "late_entry_submitted"]
    target = int(late[0]["qty"]) + 3
    assert float(b.position("ITB")["qty"]) == target
    assert any(o["type"] == "stop" and int(o["qty"]) == target for o in b.orders())
def test_close_retries_while_shares_held(monkeypatch):
    """2026-10-22 regression: a close sent right after canceling the stop got 403 'insufficient qty available'."""
    b = setup(1); monkeypatch.setattr(T.time, "sleep", lambda s: None)
    b._pos = {"symbol": "ITB", "qty": "3", "avg_entry_price": "95", "unrealized_pl": "1"}
    calls = {"n": 0}; orig = b.close_position
    def close(sym):
        calls["n"] += 1
        if calls["n"] < 3: raise T.BrokerError("DELETE /v2/positions/ITB -> 403: insufficient qty available for order")
        return orig(sym)
    b.close_position = close
    T.flatten(b, "test", "ITB", "ITB")
    assert b.position("ITB") is None and calls["n"] == 3
def test_stopped_out_before_exit_books_realized_pl():
    """2026-10-28 regression: NAIL's stop filled before 10:30, the exit found it flat and journaled trade_pl 0 (real: −$64)."""
    b = setup(1, equity=2000, px=30.80); T.cmd_enter(True)
    q = float(b.position("ITB")["qty"])
    for o in b.orders():                                   # the stop fills at 29.80
        o.update(status="filled", filled_qty=str(int(q)), filled_avg_price="29.80", filled_at=T.now_et().isoformat())
    b._pos = None
    T.cmd_exit(True)
    end = [r for r in recs() if r["event"] == "day_end_equity"][-1]
    assert abs(end["trade_pl"] - round(-1.0 * q, 2)) < 0.01 and end["trade_pl"] < 0
def test_flat_no_trade_day_books_zero():
    b = setup(0); T.cmd_exit(True)
    assert [r for r in recs() if r["event"] == "day_end_equity"][-1]["trade_pl"] == 0.0
def test_late_entry_resizes_to_buying_power(monkeypatch):
    """2026-10-30 regression: NAIL gapped above its 09:15 sizing price; the late order (58 sh, cost 1981) was rejected
    against 1942 buying power and the day was skipped. The late order must shrink to what the account can afford."""
    b = setup(1, equity=1941.73, px=32.27); _live_clock(monkeypatch)
    orig = b.submit
    def submit(**kw):
        if kw.get("time_in_force") == "opg":                                   # the auction fills 1 share
            o = orig(**{**kw, "type": "market", "qty": "1"})
            o.update(status="expired", filled_qty="1", qty=kw["qty"], type="market", time_in_force="opg"); return o
        q = int(kw["qty"])
        if kw.get("type") == "market" and (q + 1) * 34.16 > 1941.73:
            raise T.BrokerError('POST /v2/orders -> 403: {"buying_power":"1941.73","code":40310000,"cost_basis":"%.2f",'
                                '"message":"insufficient buying power"}' % ((q + 1) * 34.16))
        return orig(**kw)
    b.submit = submit
    T.cmd_enter(False)
    ev = recs()
    assert any(r["event"] == "warn" and r.get("reason") == "late entry resized to buying power" for r in ev)
    q = float(b.position("ITB")["qty"]); assert 0 < q and q * 34.16 <= 1941.73
    assert any(o["type"] == "stop" and int(o["qty"]) == int(q) for o in b.orders())
def test_qty_within_buying_power_waits_on_reservation():
    err = 'POST /v2/orders -> 403: {"buying_power":"75.89","code":40310000,"cost_basis":"1910.62","message":"insufficient buying power"}'
    assert T._qty_within_buying_power(err, 68) is None                  # an open auction order holds the cash: wait
    assert T._qty_within_buying_power(err, 68, force=True) == 2
def test_failsafe_waits_for_network_after_wake(monkeypatch):
    """2026-10-26 regression: the failsafe ran on wake before DNS was up and gave up; it must retry until the network is back."""
    b = setup(1); monkeypatch.setattr(T.time, "sleep", lambda s: None)
    b._pos = {"symbol": "ITB", "qty": "3", "avg_entry_price": "95", "unrealized_pl": "1"}
    calls = {"n": 0}; orig = b.position
    def position(sym):
        calls["n"] += 1
        if calls["n"] < 4: raise T.BrokerError("GET https://paper-api.alpaca.markets/v2/positions/ITB failed after retries: ConnectionError(NameResolutionError)")
        return orig(sym)
    b.position = position
    T.cmd_failsafe(False)
    assert "failsafe_triggered" in events() and "error" not in events() and orig("ITB") is None
BARS = [{"t": "2026-11-02T14:30:00Z", "o": 92.0, "h": 93.0, "l": 91.5, "c": 92.5},
        {"t": "2026-11-02T15:29:00Z", "o": 94.0, "h": 94.6, "l": 93.8, "c": 94.5}]
def test_shortfall_is_force_fill_simulated(monkeypatch):
    """2026-11-02: ITB's paper fills got 2 of 21 shares; the other 19 are booked as a simulated trade at the open."""
    b = setup(1, equity=2000, px=92.0); monkeypatch.setattr(T, "_minute_bars", lambda b, s, d: BARS)
    import datetime as dt
    day = dt.date(2026, 11, 2)
    T.log("entry_submitted", ts_et="2026-11-02T09:15:02-05:00", account="ITB", side="buy", qty=21, target_qty=21)
    T.log("entry_filled", ts_et="2026-11-02T09:35:00-05:00", account="ITB", qty=2.0)
    T._simulate_shortfalls(day, True)
    s = [r for r in recs() if r["event"] == "sim_trade"][0]
    assert s["qty"] == 19 and s["entry_price"] == 92.0 and s["exit_price"] == 94.5 and s["ts_et"].startswith("2026-11-02T10:30")
    assert abs(s["gross_pl"] - 19 * 2.5) < 1e-9 and T.sim_offset("ITB") == s["net_pl"]
    T._simulate_shortfalls(day, True); assert len([r for r in recs() if r["event"] == "sim_trade"]) == 1   # once per day
def test_paper_short_below_broker_2k_is_simulated(monkeypatch):
    """2026-11-03: NAIL broker $1,986 but desk $2,212 with sims; the short is taken on paper as a simulation."""
    b = setup(-1, equity=1986.15, px=36.0)
    b.mode = "paper"; monkeypatch.setattr(T, "regime_corr", lambda d, dry: 0.5)
    T.log("sim_trade", account="ITB", net_pl=226.08)
    T.cmd_enter(True)
    assert b.position("ITB") is None
    si = [r for r in recs() if r["event"] == "sim_intent"][0]
    assert si["side"] == "sell" and si["equity"] == 2212.23 and si["qty"] >= 1
