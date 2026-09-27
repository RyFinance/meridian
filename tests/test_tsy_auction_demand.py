import numpy as np
import pandas as pd

from research.tsy_auction_demand import core as c


def test_bucket():
    assert [c.bucket(m) for m in (2.0, 3.0, 4.0, 5.0, 7.0, 9.9, 20, 29.9)] == [2, 3, 5, 5, 7, 10, 20, 30]


def test_signal_uses_only_past():
    d = pd.DataFrame({"auction_date": pd.date_range("2010-01-01", periods=30, freq="MS"), "cusip": "x",
                      "security_term": "10-Year", "bucket": 10, "btc": np.linspace(2, 3, 30)})
    a = c.signals(d)
    d2 = d.copy()
    d2.loc[29, "btc"] = 99.0                     # changing the last auction must not change earlier signals
    b = c.signals(d2)
    assert np.allclose(a.w.iloc[:-1], b.w.iloc[:-1])
    assert b.w.iloc[-1] == -2.0                  # huge demand -> clipped, short duration


def test_book_sign_and_costs():
    idx = pd.bdate_range("2011-01-03", periods=20)
    Y = pd.DataFrame({b: np.r_[np.full(5, 3.0), np.linspace(3.0, 2.9, 15)] for b in c.BUCKET_SERIES}, index=idx)
    ev = pd.DataFrame({"auction_date": [idx[6]], "bucket": [10], "w": [1.0]})
    g, r = c.book(ev, Y, "gross", ("2011-01-01", "2011-12-31"))
    assert g.sum() > 0 and np.isclose(r.event_ret.iloc[0], -(Y[10].iloc[11] - Y[10].iloc[6]) / 100 * c.DUR)
    b, _ = c.book(ev, Y, "base", ("2011-01-01", "2011-12-31"))
    assert np.isclose(g.sum() - b.sum(), 2 * c.COSTS["base"] / c.SCALE)
    assert (g.loc[:idx[6]] == 0).all()           # nothing earned on or before the auction date
