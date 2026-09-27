"""Tests for the registered bond-ETF basis study (research/etf_basis/PLAN.md)."""
import numpy as np
import pandas as pd
import pytest

from research.etf_basis import core as c
from research.etf_basis import evaluate as ev


def test_trigger_timing_and_hold():
    sess = pd.bdate_range("2020-01-01", periods=12)
    trig = pd.Series(0.0, index=sess); trig.iloc[2] = -3.0
    pos = c.positions(trig, sess)
    assert list(pos) == [0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 0]
    px = pd.Series(100.0, index=sess); px.iloc[3] = 200.0      # the jump on the day after the trigger (t+1) must NOT be earned
    r = c.sleeve_returns(pos, px, pd.Series(0.0, index=sess), 0.0)
    assert r.iloc[3] == 0.0 and r.iloc[4] == pytest.approx(-0.5)


def test_zscore_uses_only_past():
    x = pd.Series(np.random.default_rng(1).normal(size=600))
    z1 = c.zscore(x)
    y = x.copy(); y.iloc[400:] += 100
    z2 = c.zscore(y)
    pd.testing.assert_series_equal(z1.iloc[:400], z2.iloc[:400])


def test_validation_locked():
    if ev._registered(ev.UNLOCK):
        pytest.skip()
    with pytest.raises(SystemExit):
        ev.run("validation")
