import numpy as np
import pandas as pd

from research.cycle8.engine import core, metrics as MX
from research.cycle9 import run8b


def test_daily_boot_equals_monthly_when_one_day_per_month():
    rng = np.random.default_rng(3)
    nm, n_f = 300, 2
    Rm = rng.normal(0.006, 0.04, (nm, n_f))
    Xm = rng.normal(0.002, 0.03, (nm, 1))
    carry = np.stack([np.full(nm, 0.005), np.full(nm, 0.003)], -1)
    D = np.zeros((nm, run8b.SLOTS, n_f + 1))
    D[:, 0, :n_f] = Rm
    D[:, 0, n_f:] = Xm
    C = np.zeros((nm, run8b.SLOTS, 2))
    C[:, 0] = carry
    w = np.array([0.6, 0.4])
    o = np.array([0.5])
    cf = np.array([0.0005, 0.0005])
    co = np.array([0.0002])
    L = 1.5
    got = run8b.daily_boot(D, C, n_f, w, o, L, cf, co, P=400, mean_block=24, seed=11, T_eval=240, horizons=(240,))
    # reference: monthly simulation with the same bootstrap indices
    r = np.random.default_rng(11)
    idx = MX.stationary_indices(nm, 36 + 240, 400, 24, r)[:, 36:]
    res = core.simulate(Rm[idx], Xm[idx], carry[idx], w, o, L, cf, co, np.ones(240, bool))
    dd = core.max_drawdown(res["wealth"])
    for tol in run8b.TOL:
        assert np.isclose(got[f"pd_dd{int(tol * 100)}_20y"], (dd > tol).mean())


def test_intramonth_path_raises_drawdown_probability():
    rng = np.random.default_rng(5)
    nm = 200
    D = np.zeros((nm, run8b.SLOTS, 1))
    C = np.zeros((nm, run8b.SLOTS, 2))
    for i in range(nm):
        daily = rng.normal(0.0004, 0.012, 21)
        D[i, :21, 0] = daily
    Dm = np.zeros_like(D)
    Dm[:, 0, 0] = np.prod(1 + D[:, :, 0], 1) - 1
    a = run8b.daily_boot(D, C, 1, np.array([1.0]), np.zeros(1), 1.0, np.zeros(1), np.zeros(1), 300, 24, 1,
                         T_eval=240, horizons=(240,))
    b = run8b.daily_boot(Dm, C, 1, np.array([1.0]), np.zeros(1), 1.0, np.zeros(1), np.zeros(1), 300, 24, 1,
                         T_eval=240, horizons=(240,))
    assert a["pd_dd25_20y"] >= b["pd_dd25_20y"]


def test_trend_input_rules():
    rng = np.random.default_rng(7)
    idx = pd.period_range("1985-01", "2026-08", freq="M").to_timestamp("M")
    ts = pd.Series(rng.normal(0.01, 0.035, len(idx)), index=idx)
    panel = pd.DataFrame(index=idx)
    for i in range(5):
        c = np.full(len(idx), np.nan)
        c[200 + 10 * i:] = rng.normal(0.003, 0.03 + 0.01 * i, len(idx) - 200 - 10 * i)
        panel[f"f{i}"] = c
    X, info = run8b.trend_input(panel, ts)
    live_start = pd.Timestamp(info["live_start"]) + pd.offsets.MonthEnd(0)
    assert live_start == idx[220]
    e1 = panel.mean(1).where(panel.notna().sum(1) >= 3).loc[live_start:"2026-05"]
    k = info["k"]
    assert np.isclose(k, (panel.std() * np.sqrt(12)).median() / (e1.std() * np.sqrt(12)))
    assert np.allclose(X.loc[live_start:], k * e1)
    pre = X.loc[:live_start - pd.offsets.MonthEnd(1)]
    m_pre = ts.loc[:live_start - pd.offsets.MonthEnd(1)].mean()
    assert np.isclose(pre.mean(), info["rho"] * m_pre)
    assert np.isclose(pre.std(), info["k_pre"] * ts.loc[:live_start - pd.offsets.MonthEnd(1)].std())
    X2, info2 = run8b.trend_input(panel, ts, "s2_full_haircut")
    assert np.isclose(X2.loc[:live_start - pd.offsets.MonthEnd(1)].mean(), (k * e1).mean())
    assert X.index[0] == pd.Timestamp("1985-01-31") and X.index[-1] == pd.Timestamp("2026-05-31")
