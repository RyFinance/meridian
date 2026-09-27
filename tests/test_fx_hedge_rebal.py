"""Tests for the registered FX hedge-rebalancing study (research/fx_hedge_rebal/PLAN.md)."""
import numpy as np
import pandas as pd
import pytest

from research.fx_hedge_rebal import core as c
from research.fx_hedge_rebal import evaluate as ev


def test_london_dst_conversion():
    assert c.london_to_utc(pd.Timestamp("2019-07-31"), "08:00") == np.datetime64("2019-07-31T07:00")
    assert c.london_to_utc(pd.Timestamp("2019-01-31"), "16:00") == np.datetime64("2019-01-31T16:00")


def test_month_end_is_last_weekday():
    d = c.month_end_days("2020-01-01", "2020-12-31")
    assert pd.Timestamp("2020-05-29") in d and pd.Timestamp("2020-02-28") in d   # May 31 Sun, Feb 29 Sat
    assert (d.dayofweek < 5).all()


def test_mtd_uses_closes_strictly_before_D():
    idx = pd.to_datetime(["2020-01-31", "2020-02-27", "2020-02-28"])
    px = pd.Series([100.0, 110.0, 999.0], index=idx)
    assert c.mtd(px, pd.Timestamp("2020-02-28")) == pytest.approx(0.10)


def test_daily_book_sign_and_cost():
    days = pd.bdate_range("2020-01-27", "2020-01-31")
    e = pd.DataFrame({"D": [days[-1]] * 2, "ccy": ["EUR", "JPY"], "sign": [1.0, -1.0], "ret": [0.001, 0.002]})
    b = c.daily_book(e, "sign", 1e-4, days)
    assert b.iloc[-1] == pytest.approx(((0.001 - 2e-4) + (-0.002 - 2e-4)) / 2) and b.iloc[0] == 0.0


def test_validation_locked():
    if ev.registered(ev.UNLOCK):
        pytest.skip()
    with pytest.raises(SystemExit):
        ev.run("validation")
