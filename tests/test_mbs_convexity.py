"""Tests for the registered MBS convexity study and the shared monthly hedge."""
import numpy as np
import pandas as pd
import pytest

from research.mbs_convexity import evaluate as ev
from research.struct_common import monthly_hedge


def _synthetic(n=600, seed=0):
    rng = np.random.default_rng(seed)
    sess = pd.bdate_range("2015-01-01", periods=n)
    a, b = rng.normal(0, 0.004, n), rng.normal(0, 0.001, n)
    y = 0.6 * a + 0.3 * b + rng.normal(0, 0.0005, n)
    px = lambda r: pd.Series(100 * np.cumprod(1 + r), index=sess)
    return px(y), pd.DataFrame({"IEF": px(a), "SHY": px(b)}), sess


def test_hedge_recovers_betas_and_is_point_in_time():
    y, X, sess = _synthetic()
    H = monthly_hedge(y, X, sess)
    last = H.dropna().iloc[-1]
    assert last["IEF"] == pytest.approx(0.6, abs=0.05) and last["SHY"] == pytest.approx(0.3, abs=0.15)
    t = H.dropna().index[len(H.dropna()) // 2]
    y2 = y.copy(); y2.loc[t:] *= 1.5                       # change prices from t on
    H2 = monthly_hedge(y2, X, sess)
    pd.testing.assert_series_equal(H.loc[t], H2.loc[t])  # hedge set at t uses returns to t-1 only


def test_hedge_clipped():
    y, X, sess = _synthetic()
    H = monthly_hedge(-y, X, sess)
    assert (H.dropna() >= 0).all().all() and (H.dropna() <= 2).all().all()


def test_validation_locked():
    if ev.registered(ev.UNLOCK):
        pytest.skip()
    with pytest.raises(SystemExit):
        ev.run("validation")
