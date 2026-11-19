import numpy as np
from research.cycle8.engine import core


def run(R, L, X=None, o=None, carry=(0.0, 0.0), rebal=None, cf=0.0):
    R = np.asarray(R, float)[None, :, None] if np.ndim(R) == 1 else np.asarray(R, float)[None]
    P, S, n = R.shape
    X = np.zeros((1, S, 1)) if X is None else np.asarray(X, float)[None, :, None]
    o = np.zeros(1) if o is None else np.asarray(o, float)
    C = np.broadcast_to(np.array(carry, float), (1, S, 2))
    rebal = np.ones(S, bool) if rebal is None else rebal
    return core.simulate(R, X, C, np.ones(n) / n, o, L, np.full(n, cf), np.zeros(1), rebal)


def test_unlevered_compounding():
    r = run([0.01] * 12, 1.0)
    assert np.isclose(r["wealth"][0, -1], 1.01 ** 12)
    assert r["calls"][0] == 0


def test_financing_cost():
    r = run([0.0], 2.0, carry=(0.01, 0.0))
    assert np.isclose(r["wealth"][0, -1], 1 - 0.01)


def test_leverage_rebalanced_monthly():
    r = run([0.10, -0.10], 2.0)
    assert np.isclose(r["wealth"][0, -1], 1.2 * 0.8)


def test_margin_call_restores_buffer():
    r = run([-0.40], 2.0)
    # A 1.2, D 1, E 0.2 < 0.36 -> liquidation to 35% of assets after 1% cost
    w = r["wealth"][0, -1]
    k = (0.2 - 0.012) / (core.RESTORE * 0.36 - 0.012)
    A = 1.2 * k
    D = 1 - (1 - k) * 1.2 * 0.99
    assert r["calls"][0] == 1
    assert np.isclose(w, A - D)
    assert np.isclose((A - D) / A, 0.35)


def test_ruin():
    r = run([-0.60, 0.5], 2.0)
    assert r["ruined"][0]
    assert r["wealth"][0, -1] == 0


def test_no_rebalance_drift_between_months():
    rebal = np.array([True, False, True])
    r = run([0.10, 0.10, 0.0], 2.0, rebal=rebal)
    # step 0: A 2.2, D 1 -> E 1.2; step 1 (no rebal): A 2.42, E 1.42; step 2 rebal, 0 return
    assert np.isclose(r["wealth"][0, 2], 1.42)
    assert np.isclose(r["wealth"][0, 3], 1.42)


def test_overlay_pnl_and_margin():
    r = run([0.0, 0.0], 1.0, X=[0.02, -0.02], o=[0.5])
    assert np.isclose(r["wealth"][0, 1], 1.01)
    assert np.isclose(r["wealth"][0, 2], 1.01 * (1 - 0.01))


def test_costs():
    r = run([[0.1, -0.1], [0.0, 0.0]], 1.0, cf=0.001)
    # after step 0: holdings 0.55, 0.45 -> E 1.0; rebalance trades 0.05 + 0.05 -> cost 0.0001
    assert np.isclose(r["wealth"][0, -1], 1.0 - 0.0001)


def test_max_drawdown():
    w = np.array([[1, 1.2, 0.6, 0.9, 1.5]])
    assert np.isclose(core.max_drawdown(w)[0], 0.5)
