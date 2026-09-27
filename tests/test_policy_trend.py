"""Tests for the registered policy-trend study (research/policy_trend/PLAN.md)."""
import numpy as np
import pandas as pd
import pytest

from research.policy_trend import core as c
from research.policy_trend import evaluate as ev


def test_signal_is_point_in_time():
    y = c.load_yields()
    dates = c.month_ends("2014-01-31", "2016-12-30")
    full, _ = c.signal_panel(y, dates)
    cut = pd.Timestamp("2015-06-30")
    trunc = {k: s.loc[: cut - pd.Timedelta(days=1)] for k, s in y.items()}
    part, _ = c.signal_panel(trunc, dates[dates <= cut])
    pd.testing.assert_frame_equal(full.loc[:cut], part)


def test_signal_ignores_same_day_yield():
    y = c.load_yields()
    t = pd.Timestamp("2016-03-31")
    base, _ = c.signal_panel(y, pd.DatetimeIndex([t]))
    y2 = {k: s.copy() for k, s in y.items()}
    y2["UK"].loc[t] = 99.0                        # a print dated t must not enter the signal at t
    pert, _ = c.signal_panel(y2, pd.DatetimeIndex([t]))
    pd.testing.assert_frame_equal(base, pert)


def test_book_legs_and_k():
    idx = pd.DatetimeIndex(["2020-01-31"])
    cols = list(c.ECON)
    score = pd.DataFrame([np.arange(10.0)], index=idx, columns=cols)
    vol = pd.DataFrame([np.ones(10)], index=idx, columns=cols)
    w = c.book(score, vol, low_long=True)
    assert w.loc[idx[0], cols[:3]].sum() == pytest.approx(1) and (w.loc[idx[0], cols[:3]] > 0).all()
    assert w.loc[idx[0], cols[-3:]].sum() == pytest.approx(-1)
    score.iloc[0, 5:] = np.nan                    # 5 eligible < MIN_N -> no book
    assert (c.book(score, vol).abs().sum().sum()) == 0


def test_period_returns_subtract_local_rate():
    dates = pd.DatetimeIndex(["2020-01-31", "2020-02-28"])
    px = pd.DataFrame({k: [100.0, 110.0] for k in c.ECON}, index=dates)
    y = {k: pd.Series([5.0], index=[pd.Timestamp("2020-01-29")]) for k in c.ECON}
    r = c.period_returns(px, y, dates)
    assert r.iloc[0, 0] == pytest.approx(0.10 - 0.05 * 28 / 365)


def test_pnl_charges_turnover():
    idx = pd.DatetimeIndex(["2020-01-31", "2020-02-28"])
    w = pd.DataFrame({"US": [1.0, -1.0], "UK": [-1.0, 1.0]}, index=idx)
    ret = pd.DataFrame({"US": [0.0, 0.0], "UK": [0.0, 0.0]}, index=idx)
    x = c.pnl(w, ret, 1e-4)
    assert x.iloc[0] == pytest.approx(-2e-4) and x.iloc[1] == pytest.approx(-4e-4)


def test_validation_locked():
    if ev._registered(ev.UNLOCK):
        pytest.skip("unlocked")
    with pytest.raises(SystemExit):
        ev.run("validation")
