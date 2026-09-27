"""Tests for the registered credit gate (research/credit_gate/PLAN.md)."""
import numpy as np
import pandas as pd
import pytest

from research.credit_gate import core as c
from research.credit_gate import evaluate as ev


def test_signal_ignores_same_day_value():
    s = c.credit_series()
    t = pd.Timestamp("2015-06-30")
    base = c.signal_at(s, t)
    s2 = s.copy(); s2.loc[t] = 999.0
    assert c.signal_at(s2, t) == base


def test_weights_take_effect_next_session_and_returns_lag():
    idx = pd.bdate_range("2020-01-01", periods=6)
    w = c.weights_from_signal(pd.Series({idx[1]: 1.0}), idx)
    assert list(w) == [0, 0, 1, 1, 1, 1]
    px = pd.Series([100, 100, 100, 110, 110, 110.0], index=idx)
    rf = pd.Series(0.0, index=idx)
    r = c.daily_returns(w, px, rf, 0.0)
    assert r.iloc[3] == pytest.approx(0.10)          # held from close of idx[2]
    assert r.iloc[2] == 0.0


def test_costs_charged_on_switch():
    idx = pd.bdate_range("2020-01-01", periods=5)
    w = pd.Series([0, 1, 1, 0.0, 0.0], index=idx)          # switch costs book on the following day
    px = pd.Series(100.0, index=idx); rf = pd.Series(0.0, index=idx)
    r = c.daily_returns(w, px, rf, 1e-4)
    assert r.sum() == pytest.approx(-2e-4)


def test_validation_locked():
    if ev._registered(ev.UNLOCK):
        pytest.skip()
    with pytest.raises(SystemExit):
        ev.run("validation")
