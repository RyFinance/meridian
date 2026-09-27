"""Tests for research/pead_attack (placebo engine, marking, permutations, statistics)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.pead_attack.analysis import classify, holm, p_upper, years_for_power
from research.pead_attack.engine import PRODUCTION_LIMITS, START_CAPITAL, Stream, kelly_sizes, simulate
from research.pead_attack.marking import mark_book, to_mtm_positions
from research.pead_attack.placebo import within_date_permutation
from research.pead_audit.mtm_audit import mtm_book

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "reports" / "pead_attack" / "inputs" / "events.parquet"


# -- synthetic fixtures ------------------------------------------------------------------------
def _synthetic(n_days=60, tickers=("AAA", "BBB", "CCC", "DDD"), seed=0):
    dates = pd.bdate_range("2024-01-02", periods=n_days)
    rng = np.random.default_rng(seed)
    closes = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.01, (n_days, len(tickers))), axis=0)),
                          index=dates, columns=list(tickers))
    cal = pd.DataFrame({"tier": "armed", "rf": 0.0001, "mkt_rf": rng.normal(0, 0.01, n_days)}, index=dates)
    return dates, closes, cal


def _events(rows):
    ev = pd.DataFrame(rows, columns=["date", "ticker"])
    ev["date"] = pd.to_datetime(ev["date"])
    ev["earnings_date_raw"] = ev["date"] + pd.Timedelta(hours=7)
    ev["row_order"] = np.arange(len(ev))
    ev["scorable"] = True
    return ev


def test_within_date_permutation_preserves_date_blocks_and_is_seeded():
    rng = np.random.default_rng(1)
    codes = rng.integers(0, 30, 500)
    vals = rng.random(500)
    perm = within_date_permutation(codes, np.random.default_rng([7, 1, 3]))
    assert sorted(perm) == list(range(500))
    assert (codes[perm] == codes).all()  # every value stays inside its date
    for c in np.unique(codes):
        m = codes == c
        assert sorted(vals[perm][m]) == sorted(vals[m])
    again = within_date_permutation(codes, np.random.default_rng([7, 1, 3]))
    assert (perm == again).all()
    other = within_date_permutation(codes, np.random.default_rng([7, 1, 4]))
    assert not (perm == other).all()


def test_engine_highest_conviction_first_and_gross_cap():
    dates, closes, cal = _synthetic()
    ev = _events([(dates[1], "AAA"), (dates[1], "BBB"), (dates[1], "CCC")])
    st = Stream.build(ev, cal, closes)
    score = np.array([0.6, 0.9, 0.7])
    size = np.array([0.05, 0.05, 0.05])
    from risk.limits import RiskLimits
    res = simulate(st, score, size, np.ones(3), limits=RiskLimits(max_position_pct=0.05, max_total_exposure_pct=0.10),
                   collect_decisions=True)
    placed = res["trades"].sort_values("entry_i")["ticker"].tolist()
    assert set(placed) == {"BBB", "CCC"}  # 0.9 and 0.7 fill the 10% cap; 0.6 is risk_blocked
    reasons = {int(e): r for _, e, r in res["decisions"]}
    assert reasons[0] == "risk_blocked" and reasons[1] is None and reasons[2] is None


def test_engine_no_conviction_breaker_and_one_decision_per_event():
    dates, closes, cal = _synthetic()
    cal.loc[dates[3], "tier"] = "halt_new_entries"
    ev = _events([(dates[1], "AAA"), (dates[3], "BBB"), (dates[3], "CCC")])
    st = Stream.build(ev, cal, closes)
    res = simulate(st, np.array([0.5, 0.9, 0.9]), np.array([0.0, 0.05, 0.05]), np.ones(3), collect_decisions=True)
    assert len(res["trades"]) == 0
    dec = res["decisions"]
    assert [r for _, _, r in dec] == ["no_conviction", "circuit_breaker_halt", "circuit_breaker_halt"]
    assert len({e for _, e, _ in dec}) == len(dec)  # each event decided once, never retried on later days


def test_engine_exit_after_20_business_days_and_cost():
    dates, closes, cal = _synthetic()
    ev = _events([(dates[2], "AAA")])
    st = Stream.build(ev, cal, closes)
    res = simulate(st, np.array([0.9]), np.array([0.05]), np.array([-1.0]))
    t = res["trades"].iloc[0]
    assert t.entry_i == 2 and t.exit_i == 22  # bdate calendar: 20 business days later
    entry, exit_ = closes["AAA"].iloc[2], closes["AAA"].iloc[22]
    notional = 0.05 * START_CAPITAL
    gross = notional * -1 * (exit_ - entry) / entry
    cost = (notional + notional * exit_ / entry) * 0.0005
    assert t.realized_pnl == pytest.approx(gross - cost, rel=1e-12)
    assert res["final_cash_nav"] == pytest.approx(START_CAPITAL + gross - cost, rel=1e-12)


def test_engine_skips_held_ticker_until_it_exits():
    dates, closes, cal = _synthetic()
    ev = _events([(dates[1], "AAA"), (dates[21], "AAA")])  # second event arrives the day the first exits
    st = Stream.build(ev, cal, closes)
    res = simulate(st, np.array([0.9, 0.9]), np.array([0.05, 0.05]), np.ones(2))
    tr = res["trades"].sort_values("entry_i")
    assert tr["entry_i"].tolist() == [1, 21] and tr["exit_i"].iloc[0] == 21  # exits are processed before entries


def test_mark_book_equals_mtm_book_on_synthetic_ledger():
    dates, closes, cal = _synthetic(n_days=80)
    ev = _events([(dates[i], t) for i, t in [(1, "AAA"), (2, "BBB"), (5, "CCC"), (30, "AAA"), (31, "DDD")]])
    st = Stream.build(ev, cal, closes)
    sign = np.array([1.0, -1.0, 1.0, 1.0, -1.0])
    res = simulate(st, np.array([0.9, 0.8, 0.7, 0.6, 0.5]), np.array([0.05, 0.03, 0.02, 0.05, 0.04]), sign)
    tr = res["trades"]
    assert (tr["exit_i"] >= 0).all()
    rf = cal["rf"]
    ref = mtm_book(to_mtm_positions(tr, dates), closes, dates, rf, 0.0005, 0.0, cash_earns_rf=True)
    fast = mark_book(tr, closes.to_numpy(), {c: j for j, c in enumerate(closes.columns)}, rf.to_numpy())
    assert np.max(np.abs(fast["ret"] - ref["ret"].to_numpy())) < 1e-14
    assert np.max(np.abs(fast["long_mv"] - ref["long_mv"].to_numpy())) < 1e-9
    fixed = mark_book(tr, closes.to_numpy(), {c: j for j, c in enumerate(closes.columns)}, rf.to_numpy(),
                      exit_day_cash_fix=True)
    assert fixed["nav"][-1] < fast["nav"][-1]  # the fix removes one day of idle-cash interest per trade


def test_kelly_sizes_match_production_function():
    from risk.kelly import fractional_kelly_size
    p = np.array([0.3, 0.5, 0.55, 0.7, np.nan, 0.93])
    s = kelly_sizes(p, 0.96)
    for v, got in zip(p, s):
        if np.isfinite(v):
            assert got == float(fractional_kelly_size(v, 0.96, 0.25, PRODUCTION_LIMITS.max_position_pct))
        else:
            assert np.isnan(got)


def test_p_upper_holm_classify_and_power():
    assert p_upper(1.0, np.array([0.1, 0.2, 1.5])) == pytest.approx(2 / 4)
    assert p_upper(9.0, np.zeros(999)) == pytest.approx(1 / 1000)
    adj = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj == pytest.approx({"a": 0.03, "c": 0.06, "b": 0.06})
    base = {("P1", "sharpe"): 0.5, ("P3", "sharpe"): 0.5, ("P1L", "capm_alpha"): 0.5}
    assert classify(base).startswith("D")
    assert classify({**base, ("P1", "sharpe"): 0.01}).startswith("B")
    assert classify({("P1", "sharpe"): 0.01, ("P3", "sharpe"): 0.01, ("P1L", "capm_alpha"): 0.02}).startswith("A")
    assert classify({**base, ("P3", "sharpe"): 0.01, ("P1L", "capm_alpha"): 0.01}).startswith("C")
    assert years_for_power(0.02, 0.04) == pytest.approx(((1.6448536 + 0.8416212) * 2) ** 2, rel=1e-6)
    assert years_for_power(-0.01, 0.04) == float("inf")


@pytest.mark.skipif(not INPUTS.exists(), reason="frozen inputs not built (research.pead_attack.inputs)")
def test_engine_reproduces_recorded_sweep_ledger():
    from research.pead_attack.reproduce import main
    out = main()
    assert out["gate_passed"], out
    assert out["ledger"]["n_engine"] == 625
    assert out["marking"]["excess_sharpe_reproduced"] == pytest.approx(0.6998806027785588, abs=1e-12)


@pytest.mark.skipif(not INPUTS.exists(), reason="frozen inputs not built (research.pead_attack.inputs)")
def test_placebo_draw_inputs_respect_family_design():
    from research.pead_attack.common import Inputs
    from research.pead_attack.placebo import draw_inputs
    inp = Inputs()
    S = inp.stream.ev_scorable
    s1, z1, g1 = draw_inputs(inp, "P1", 0)
    s1l, z1l, g1l = draw_inputs(inp, "P1L", 0)
    assert np.array_equal(s1, s1l, equal_nan=True) and (g1l == 1).all() and np.array_equal(g1, inp.sign_prod)
    assert np.isnan(s1[~S]).all() and np.isfinite(s1[S]).all()
    dates = inp.events["date"].to_numpy()
    for d in pd.unique(dates[S])[:50]:
        m = S & (dates == d)
        assert sorted(s1[m]) == sorted(inp.p_real[m])
    assert np.array_equal(z1[S], kelly_sizes(s1[S], inp.b))
    s3, z3, g3 = draw_inputs(inp, "P3", 0)
    assert (z3[S] == 0.05).all() and (g3 == 1).all()
    s2, z2, g2 = draw_inputs(inp, "P2", 0)
    assert np.array_equal(g2, inp.sign_prod) and not np.array_equal(s2[S], s3[S])
    sg, _, _ = draw_inputs(inp, "P1G", 0)
    assert sorted(sg[S]) == sorted(inp.p_real[S])
