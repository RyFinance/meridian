"""Tests for the registered sector month-end study (research/sector_month_end/PLAN.md)."""
import numpy as np
import pandas as pd
import pytest

from research.sector_month_end import core as c
from research.sector_month_end import evaluate as ev


def test_control_is_exposure_matched_constant(monkeypatch):
    sess = pd.bdate_range("2010-01-01", "2010-03-31")
    hx = pd.Series(np.linspace(-0.001, 0.001, len(sess)), index=sess)
    monkeypatch.setattr(c, "hedged", lambda s: (hx, pd.Series(1.0, index=sess)))
    r, ctrl = c.sector_book("LQD", ("2010-01-01", "2010-03-31"), "gross")
    w = c.weights(sess, "last")
    assert ctrl.iloc[5] == pytest.approx(w.mean() * hx.iloc[5])
    held = w.shift(1).fillna(0)
    assert r.sum() == pytest.approx((held * hx).sum())


def test_costs_on_entry_and_exit(monkeypatch):
    sess = pd.bdate_range("2010-01-01", "2010-01-31")
    monkeypatch.setattr(c, "hedged", lambda s: (pd.Series(0.0, index=sess), pd.Series(1.0, index=sess)))
    r, _ = c.sector_book("LQD", ("2010-01-01", "2010-01-31"), "base")
    assert r.sum() == pytest.approx(-2 * (3e-4 + 2e-4))        # one entry + one exit per month


def test_validation_locked():
    if ev.registered(ev.UNLOCK):
        pytest.skip()
    with pytest.raises(SystemExit):
        ev.run("validation")
