import numpy as np
import pandas as pd

from research.crypto_funding_xs import core as c


def _panel(n=40, days=120, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2021-01-01", periods=days, freq="D")
    cols = [f"S{i}USDT" for i in range(n)]
    O = pd.DataFrame(100.0, index=idx, columns=cols)
    C = O * (1 + rng.normal(0, 0.02, (days, n)))
    V = pd.DataFrame(rng.uniform(1, 2, (days, n)), index=idx, columns=cols)
    SIG = pd.DataFrame(np.tile(np.arange(n) * 1e-4, (days, 1)), index=idx, columns=cols)
    FUND = SIG * 3
    return dict(O=O, C=C, V=V, SIG=SIG, FUND=FUND), {s: idx[0] - pd.Timedelta(days=100) for s in cols}


def test_weights_direction_and_neutral():
    P, F = _panel()
    W = c.weights(P, F, "2021-03-01", "2021-03-10")
    w = W.iloc[0]
    assert np.isclose(w.sum(), 0) and np.isclose(w.abs().sum(), 1)
    assert w["S0USDT"] > 0 and w["S39USDT"] < 0          # long lowest funding, short highest


def test_funding_sign_and_costs():
    P, F = _panel()
    for k in ("O", "C"):
        P[k] = P["O"].copy()                              # zero price return
    W = c.weights(P, F, "2021-03-01", "2021-03-10")
    g = c.returns(P, W, "gross")
    assert (g > 0).all()                                  # short high-funding receives, long low-funding pays less
    b = c.returns(P, W, "base")
    assert (b <= g + 1e-12).all() and b.iloc[0] < g.iloc[0]


def test_min_universe_drops_day():
    P, F = _panel(n=20)
    W = c.weights(P, F, "2021-03-01", "2021-03-03")
    assert W.isna().all(axis=1).all()


def test_signal_window_excludes_t(tmp_path, monkeypatch):
    f = pd.Series([0.001, 0.002, 0.004], index=pd.to_datetime(["2021-01-07 16:00", "2021-01-08 00:00", "2021-01-08 08:00"]))
    monkeypatch.setattr(c, "funding", lambda s: f)
    k = pd.DataFrame({"open": 1.0, "close": 1.0, "quote_volume": 1.0}, index=pd.date_range("2020-10-01", "2021-01-10"))
    monkeypatch.setattr(c, "klines", lambda s: k)
    monkeypatch.setattr(c, "MIN_SETTLE", 1)
    P, _ = c.panel(["XUSDT"], "2021-01-08", "2021-01-09")
    assert np.isclose(P["SIG"].at[pd.Timestamp("2021-01-08"), "XUSDT"], 0.001 / 7)       # 00:00 settlement excluded
    assert np.isclose(P["FUND"].at[pd.Timestamp("2021-01-07"), "XUSDT"], 0.003)          # paid in (t, t+1d]: 16:00 + next 00:00
    assert np.isclose(P["FUND"].at[pd.Timestamp("2021-01-08"), "XUSDT"], 0.004)
