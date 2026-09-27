"""Tests for the registered commodity roll study (research/commodity_roll/PLAN.md)."""
import numpy as np
import pandas as pd
import pytest

from research.commodity_roll import core as c
from research.commodity_roll import evaluate as ev


def _px(vals, start="2020-01-01"):
    return pd.Series(vals, index=pd.bdate_range(start, periods=len(vals)), dtype=float)


def test_sign_long_deferred_short_front():
    n = 30
    long_ = _px(100 * 1.001 ** np.arange(n))           # deferred rises 0.1%/day
    short = _px(np.full(n, 100.0))
    r = c.pair_returns(long_, short, 0.0, 0.0)
    assert r.iloc[1:].sum() > 0 and r.iloc[0] == 0.0     # nothing earned before the first rebalance


def test_rebalance_cost_and_borrow():
    long_ = _px([100, 100, 100, 100.0])
    short = _px([100, 100, 100, 100.0])
    r = c.pair_returns(long_, short, 1e-3, 0.0365)
    # first session is a month start: reset from (0,0) to (1,1) costs 2 x 1e-3; then borrow 1 day per session
    assert r.iloc[0] == pytest.approx(-2e-3)
    assert r.iloc[1] == pytest.approx(-0.0365 / 365)


def test_drift_between_rebalances():
    long_ = _px([100, 110, 110.0], start="2020-01-30")    # Jan 30 (month start inside Jan? no) -> Jan 30 is first obs of Jan here
    short = _px([100, 100, 100.0], start="2020-01-30")
    r = c.pair_returns(long_, short, 0.0, 0.0)
    assert r.iloc[1] == pytest.approx(0.10)                # held 1 unit from Jan 30 close into Jan 31


def test_validation_locked():
    if ev.registered(ev.UNLOCK):
        pytest.skip()
    with pytest.raises(SystemExit):
        ev.run("validation")
