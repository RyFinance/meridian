"""Tests for the registered macro-surprise experiment (research/macro_surprise/PLAN.md)."""
import numpy as np
import pandas as pd
import pytest

from research.macro_surprise import evaluate as ev
from research.macro_surprise import signals as sg


def test_parse_value_units():
    assert sg.parse_value("252K") == 252_000
    assert sg.parse_value("-22000K") == -22_000_000
    assert sg.parse_value("$ 4.7B") == pytest.approx(4.7e9)
    assert sg.parse_value("-0.5%") == -0.5
    assert sg.parse_value("13.7%%") == 13.7
    assert sg.parse_value("54.5Points") == 54.5
    assert sg.parse_value("-6Points") == -6
    assert np.isnan(sg.parse_value("0/9"))
    assert np.isnan(sg.parse_value(None))


@pytest.mark.parametrize("name,expected", [
    ("Unemployment Rate", -1), ("Initial Jobless Claims", -1), ("Claimant Count Change", -1),
    ("ISM Manufacturing PMI", 1), ("Non Farm Payrolls", 1), ("Retail Sales MoM", 1),
    ("Michigan Consumer Expectations Final", 1), ("CBI Distributive Trades", 1),
    ("Gross Domestic Product QoQ", 1), ("ISM New York Index", 1),
    ("Inflation Rate YoY", 0), ("ISM Manufacturing Prices", 0), ("Consumer Inflation Expectations", 0),
    ("Business Inventories MoM", 0), ("Balance of Trade", 0), ("Gross Debt to GDP", 0),
    ("Average Hourly Earnings MoM", 0), ("Fed Interest Rate Decision", 0), ("Mortgage Approvals", 0),
    ("House Price Index YoY", 0), ("Participation Rate", 0),
])
def test_direction(name, expected):
    assert sg.direction(name) == expected


def test_normalise_name_strips_period_suffix():
    assert sg.normalise_name("Balance of Trade DEC", "DEC") == "Balance of Trade"
    assert sg.normalise_name("Industrial Production YoY JAN-FEB", None) == "Industrial Production YoY"
    assert sg.normalise_name("IPCA mid-month CPI YoY MAY 2016", None) == "IPCA mid-month CPI YoY"


def _rel(rows):
    return pd.DataFrame(rows, columns=["economy", "day", "vote"]).assign(day=lambda d: pd.to_datetime(d.day))


def test_diffusion_window_excludes_signal_day_and_scales_by_sqrt_n():
    t = pd.Timestamp("2020-03-31")
    rows = [("US", t - pd.Timedelta(days=d), 1) for d in range(1, 17)]       # 16 votes of +1 in window
    rows += [("US", t, -1), ("US", t + pd.Timedelta(days=1), -1)]             # same-day and future
    rows += [("US", t - pd.Timedelta(days=92), -1)]                           # before window
    score, count = sg.diffusion(_rel(rows), pd.DatetimeIndex([t]))
    assert count.loc[t, "US"] == 16
    assert score.loc[t, "US"] == pytest.approx(16 / 4.0)
    assert np.isnan(score.loc[t, "JP"])                                       # < MIN_RELEASES


def test_diffusion_min_releases():
    t = pd.Timestamp("2020-03-31")
    rows = [("JP", t - pd.Timedelta(days=d), 1) for d in range(1, sg.MIN_RELEASES)]
    score, _ = sg.diffusion(_rel(rows), pd.DatetimeIndex([t]))
    assert np.isnan(score.loc[t, "JP"])


def test_real_calendar_truncation_invariance():
    dates = pd.DatetimeIndex(["2016-06-30", "2017-12-29", "2018-09-28"])
    full, _ = sg.diffusion(sg.releases(), dates)
    cut, _ = sg.diffusion(sg.releases(upto=pd.Timestamp("2018-09-28")), dates)
    pd.testing.assert_frame_equal(full, cut)


def _prices(n=200, seed=1):
    rng = np.random.default_rng(seed)
    cal = pd.bdate_range("2019-01-01", periods=n)
    cols = list(sg.ECONOMIES)
    close = pd.DataFrame(np.exp(np.cumsum(rng.normal(0, 0.01, (n, len(cols))), axis=0)) * 100,
                         index=cal, columns=cols)
    opn = close.shift(1).fillna(close.iloc[0]) * np.exp(rng.normal(0, 0.002, close.shape))
    return opn, close


def test_target_books_legs_and_k():
    opn, close = _prices()
    dates = pd.DatetimeIndex([close.index[100], close.index[150]])
    score = pd.DataFrame(np.arange(14.0)[None, :].repeat(2, 0), index=dates, columns=list(sg.ECONOMIES))
    score.iloc[1, :3] = np.nan                                                # 11 eligible -> k = 3
    books = ev.target_books(score, close, dates)
    w0, w1 = books["M1"][dates[0]], books["M1"][dates[1]]
    assert w0[w0 > 0].sum() == pytest.approx(1) and w0[w0 < 0].sum() == pytest.approx(-1)
    assert (w0 > 0).sum() == 4 and (w0 < 0).sum() == 4
    assert set(w0[w0 > 0].index) == set(list(sg.ECONOMIES)[-4:])             # highest scores long
    assert (w1 > 0).sum() == 3 and (w1 < 0).sum() == 3
    assert (books["M2"][dates[0]] >= 0).all() and books["M2"][dates[0]].sum() == pytest.approx(1)
    assert books["C_EW"][dates[1]].sum() == pytest.approx(1) and (books["C_EW"][dates[1]] > 0).sum() == 11


def test_simulate_no_lookahead_and_costs():
    opn, close = _prices()
    rf = pd.Series(0.0001, index=close.index)
    dates = pd.DatetimeIndex([close.index[100], close.index[130], close.index[160]])
    score = pd.DataFrame(np.random.default_rng(3).normal(size=(3, 14)), index=dates, columns=list(sg.ECONOMIES))
    book = ev.target_books(score, close, dates)["M1"]
    end = close.index[-1]
    base, _ = ev.simulate(book, opn, close, rf, ev.COSTS["base"], end)
    close2, opn2 = close.copy(), opn.copy()
    close2.iloc[170:] *= 1.5
    opn2.iloc[170:] *= 1.5
    pert, _ = ev.simulate(book, opn2, close2, rf, ev.COSTS["base"], end)
    cut = close.index[169]
    pd.testing.assert_series_equal(base.loc[:cut, "nav"], pert.loc[:cut, "nav"])
    gross, _ = ev.simulate(book, opn, close, rf, ev.COSTS["gross"], end)
    assert gross["nav"].iloc[-1] > base["nav"].iloc[-1]
    assert base.index[0] == close.index[101]                                  # next session after signal


def test_simulate_flat_prices_long_short_earns_rf_minus_costs():
    cal = pd.bdate_range("2020-01-01", periods=120)
    close = pd.DataFrame(100.0, index=cal, columns=list(sg.ECONOMIES))
    opn = close.copy()
    rf = pd.Series(0.0002, index=cal)
    w = pd.Series(0.0, index=list(sg.ECONOMIES))
    w.iloc[:2], w.iloc[-2:] = 0.5, -0.5
    f, _ = ev.simulate({cal[70]: w}, opn, close, rf, ev.COSTS["base"], cal[-1])
    assert f["excess"].sum() < 0                                              # costs + borrow only
    f0, _ = ev.simulate({cal[70]: w}, opn, close, rf, ev.COSTS["gross"], cal[-1])
    assert f0["excess"].abs().max() < 1e-12
    fs, _ = ev.simulate({cal[70]: w}, opn, close, rf, ev.COSTS["stress"], cal[-1])
    assert fs["excess"].mean() < f["excess"].mean()                           # proceeds earn nothing


def test_validation_locked():
    if ev._registered(ev.UNLOCK):
        pytest.skip("validation unlocked")
    with pytest.raises(SystemExit):
        ev.run("validation")
