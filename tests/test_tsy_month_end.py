"""Tests for the registered Treasury month-end study (research/tsy_month_end/PLAN.md)."""
import pandas as pd
import pytest

from research.tsy_month_end import core as c
from research.tsy_month_end import evaluate as ev


def test_weights_hold_last_three_sessions():
    sess = pd.bdate_range("2021-03-01", "2021-04-30")
    w = c.weights(sess, "last")
    mar = sess[sess.month == 3]
    held_closes = w.loc[mar][w.loc[mar] == 1].index
    assert list(held_closes) == list(mar[-4:-1])               # closes of 4th..2nd-to-last -> earns the last 3 sessions
    r = c.returns(w, pd.Series(range(1, len(sess) + 1), index=sess, dtype=float), pd.Series(0.0, index=sess), 0.0)
    earning = r[r != 0].index
    assert set(mar[-3:]).issubset(set(earning))


def test_placebo_positions():
    sess = pd.bdate_range("2021-03-01", "2021-03-31")
    w = c.weights(sess, 5)
    assert list(w[w == 1].index) == list(sess[1:4])            # held at closes of sessions 2..4 -> earns 3..5


def test_validation_locked():
    if ev._registered(ev.UNLOCK):
        pytest.skip()
    with pytest.raises(SystemExit):
        ev.run("validation")
