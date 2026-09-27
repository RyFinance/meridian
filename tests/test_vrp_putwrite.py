"""Tests for the registered SPY put-writing study (research/vrp_putwrite/PLAN.md)."""
import numpy as np
import pandas as pd
import pytest

from research.vrp_putwrite import core as c
from research.vrp_putwrite import evaluate as ev


def test_monthly_expiry_mapping():
    e = pd.Series(pd.to_datetime(["2014-07-19", "2015-02-20", "2019-04-18", "2019-04-12", "2023-03-16", "2023-03-17"]))
    m = c.monthly_expiries(e)
    assert pd.Timestamp("2014-07-18") in m            # Saturday expiry -> Friday
    assert pd.Timestamp("2019-04-18") in m            # Good Friday week -> Thursday
    assert pd.Timestamp("2023-03-16") not in m        # ordinary Thursday weekly when Friday exists
    assert pd.Timestamp("2019-04-12") not in m        # weekly, not third week


def test_excess_return_formula_and_skip():
    cy = pd.DataFrame({"entry": pd.to_datetime(["2016-01-19", "2016-02-22", "2016-03-21"]),
                       "strike": [100.0, 100.0, np.nan], "premium": [2.0, 2.0, np.nan],
                       "spot_x": [105.0, 90.0, 100.0], "status": ["ok", "ok", "no_print"]})
    r = c.excess_returns(cy, 0.01)
    assert r.iloc[0] == pytest.approx((2 - 0 - 0.02) / 100)
    assert r.iloc[1] == pytest.approx((2 - 10 - 0.02) / 100)
    assert r.iloc[2] == 0.0


def test_cycles_use_entry_day_prints_only():
    spy = c.load_spy_raw()
    cy = c.cycles(c.load_puts(), spy, "2016-01-01", "2016-06-30")
    assert (cy["status"] == "ok").all()
    assert ((cy["strike"] <= cy["spot"]) & (cy["strike"] >= cy["spot"] * 0.98)).all()
    assert (cy["expiry"] > cy["entry"]).all()


def test_validation_locked():
    if ev._registered(ev.UNLOCK):
        pytest.skip()
    with pytest.raises(SystemExit):
        ev.run("validation")
