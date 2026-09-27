"""Tests for the registered FX news-continuation study (research/fx_news/PLAN.md)."""
import numpy as np
import pandas as pd
import pytest

from research.fx_news import evaluate as fe
from research.fx_news import events as ev


@pytest.mark.parametrize("name,expected", [
    ("Fed Interest Rate Decision", ("policy", 1)), ("ECB Interest Rate Decision", ("policy", 1)),
    ("Loan Prime Rate 1Y", (None, 0)), ("Deposit Facility Rate", (None, 0)),
    ("Inflation Rate YoY", ("inflation", 1)), ("Core PCE Price Index MoM", ("inflation", 1)),
    ("PPI MoM", ("inflation", 1)), ("Harmonised Inflation Rate YoY Prel", ("inflation", 1)),
    ("Michigan Inflation Expectations Final", (None, 0)), ("Import Prices MoM", (None, 0)),
    ("House Price Index YoY", (None, 0)), ("Wholesale Prices MoM", (None, 0)),
    ("Non Farm Payrolls", ("growth", 1)), ("Unemployment Rate", ("growth", -1)),
    ("Balance of Trade", (None, 0)),
])
def test_category(name, expected):
    assert ev.category(name) == expected


def test_timestamp_rule_matches_release_schedules():
    bulk, live = pd.Timestamp("2025-12-10"), pd.Timestamp("2026-01-15")
    # payrolls 08:30 ET: 2015-07-02 EDT -> 12:30 UTC (2015 stamps are Berlin wall time: 14:30 CEST)
    assert ev.true_utc(pd.Timestamp("2015-07-02 14:30"), bulk) == pd.Timestamp("2015-07-02 12:30")
    # 2015 winter: 08:30 EST = 13:30 UTC, Berlin CET stamp 14:30
    assert ev.true_utc(pd.Timestamp("2015-02-06 14:30"), bulk) == pd.Timestamp("2015-02-06 13:30")
    # 2016+ bulk: fixed UTC+1
    assert ev.true_utc(pd.Timestamp("2020-06-05 13:30"), bulk) == pd.Timestamp("2020-06-05 12:30")
    assert ev.true_utc(pd.Timestamp("2024-01-05 14:30"), bulk) == pd.Timestamp("2024-01-05 13:30")
    # live feed: UTC as stamped
    assert ev.true_utc(pd.Timestamp("2026-06-05 12:30"), live) == pd.Timestamp("2026-06-05 12:30")


def test_real_calendar_corrected_times_hit_known_schedules():
    r = ev.releases("2016-01-01", "2020-12-31")
    nfp = r[(r["ccy"] == "USD") & (r["name"] == "Non Farm Payrolls")]
    hm = nfp["t_utc"].dt.strftime("%H:%M")
    assert hm.isin(["12:30", "13:30"]).mean() > 0.97          # 08:30 ET
    jp = r[(r["ccy"] == "JPY") & r["name"].str.startswith("GDP Growth Rate QoQ")]
    assert jp["t_utc"].dt.strftime("%H:%M").eq("23:50").mean() > 0.9   # 08:50 JST


def test_event_groups_net_votes_and_drop_ties():
    t = pd.Timestamp("2020-01-10 13:30")
    rel = pd.DataFrame({"ccy": ["USD"] * 3 + ["EUR"] * 2, "t_utc": [t] * 3 + [t] * 2,
                        "vote": [1, 1, -1, 1, -1], "category": ["growth"] * 5})
    g = ev.event_groups(rel)
    assert list(g["ccy"]) == ["USD"] and g["sign"].iloc[0] == 1 and g["n"].iloc[0] == 3


def _series(start, n, f):
    idx = pd.date_range(start, periods=n, freq="min")
    return pd.Series([f(i) for i in range(n)], index=idx)


def test_price_at_uses_bar_close_ending_at_t_and_respects_lookback():
    s = _series("2020-01-01 00:00", 10, lambda i: 100 + i)       # bar starting 00:0i closes at 100+i
    t = np.array([np.datetime64("2020-01-01T00:05")])
    assert fe.price_at(s, t, 5)[0] == 104                          # bar 00:04-00:05
    far = np.array([np.datetime64("2020-01-01T00:30")])
    assert np.isnan(fe.price_at(s, far, 5)[0])                     # stale beyond lookback
    assert fe.price_at(s, far, 60)[0] == 109


def test_currency_orientation_and_usd_basket():
    t0 = np.array([np.datetime64("2020-01-01T00:02")])
    t1 = np.array([np.datetime64("2020-01-01T00:08")])
    up = _series("2020-01-01 00:00", 10, lambda i: 1.0 + 0.01 * i)      # every pair rises 1%/min
    closes = {p: up for p in fe.PAIRS}
    for ccy, (pair, orient) in ev.PAIRS.items():
        r = fe.currency_returns(pd.DataFrame({"ccy": [ccy]}), closes, t0, t1, 5, 5)[0]
        assert np.sign(r) == orient                                   # EUR up when EURUSD rises; JPY down when USDJPY rises
    r_usd = fe.currency_returns(pd.DataFrame({"ccy": ["USD"]}), closes, t0, t1, 5, 5)[0]
    legs = [o * (up.iloc[7] / up.iloc[1] - 1) for _, o in ev.PAIRS.values()]
    assert r_usd == pytest.approx(-np.mean(legs))


def test_daily_series_fills_zero_days():
    days = pd.bdate_range("2020-01-06", "2020-01-10")
    d = fe.daily_series(np.array([1.0, 2.0]), np.array([days[0], days[0]]), days)
    assert list(d) == [3.0, 0, 0, 0, 0]


def test_validation_locked():
    if fe._registered(fe.UNLOCK):
        pytest.skip("validation unlocked")
    with pytest.raises(SystemExit):
        fe.run("validation")
