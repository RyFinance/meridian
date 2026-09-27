import numpy as np
import pandas as pd

from research.pd_inventory import core as c


def test_signal_past_only_and_segments():
    idx = pd.date_range("2000-01-05", periods=80, freq="7D")
    inv = pd.DataFrame({"x": np.arange(80.0), "seg": [0] * 40 + [1] * 40}, index=idx)
    s = c.signal(inv)
    inv2 = inv.copy()
    inv2.iloc[-1, 0] = 1e9
    s2 = c.signal(inv2)
    assert np.allclose(s.w.iloc[:-1], s2.w.iloc[:-1])
    assert s.loc[idx[40]:idx[40 + c.MIN_PRIOR - 1]].empty       # restart after a segment break
    assert (s.avail - s.index == pd.Timedelta(days=9)).all()


def test_weights_lag_and_book_sign(monkeypatch):
    days = pd.bdate_range("2005-01-03", periods=30)
    y = pd.Series(np.r_[np.full(10, 4.0), np.linspace(4.0, 3.8, 20)], index=days)
    monkeypatch.setattr(c, "dgs10", lambda: y)
    w = pd.Series(1.0, index=days)
    b, a, W = c.book(("2005-01-01", "2005-12-31"), "gross", w_override=w)
    assert b.sum() > 0                                           # long duration, yields fall -> profit
    assert np.isclose(b.iloc[0], 0.0)                           # nothing earned on the entry close
