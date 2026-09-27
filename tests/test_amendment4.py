"""Tests for research.amendment4 (Amendment-4 simulation helpers). Synthetic data only; fast (small path counts)."""
import math
import warnings

import numpy as np
import pytest

from research.amendment4 import active, calib, ci, dgp, gating, validators
from research.amendment4.power_bench import analytic_joint
from research.power.core import Autocorr, SeriesModel


# ------------------------------------------------------------------------------------------------ 1. active series
def test_active_series_values():
    book = np.array([0.02, -0.01, 0.03, 0.0])
    e = np.array([1.0, 0.0, 1.0, 0.0])
    r = np.array([0.02, -0.01, 0.03, 0.01])
    out = active.active_series(book, e, r)
    np.testing.assert_allclose(out, book - 0.5 * r)


def test_active_series_multi_benchmark_and_paths():
    rng = np.random.default_rng(0)
    e = rng.random((3, 50, 2))
    r = rng.standard_normal((3, 50, 2))
    book = (e * r).sum(axis=-1)
    out = active.active_series(book, e, r)
    expect = book - (e.mean(axis=1, keepdims=True) * r).sum(axis=-1)
    np.testing.assert_allclose(out, expect)
    with pytest.raises(ValueError):
        active.active_series(book, e[..., 0], r)


def test_active_series_removes_premium_under_zero_skill():
    rng = np.random.default_rng(1)
    book, e, r, cost = active.long_only_timing(400, 2520, rng, S_active=0.0, cost_sr=0.0)
    raw_mean = book.mean()
    act_mean = active.active_series(book, e, r).mean()
    assert raw_mean > 0.012          # 0.6 * 0.4 / sqrt(252) = 0.015
    assert abs(act_mean) < 0.003


# ------------------------------------------------------------------------------------------------ 2. calibrated test
def test_fit_ar_bic_recovers_ar1():
    rng = np.random.default_rng(2)
    x = dgp.ar1(1, 20000, rng, 0.5)[0]
    p, phi = calib.fit_ar_bic(x - x.mean(), 3)
    assert p >= 1 and abs(phi[0] - 0.5) < 0.03


def test_is_stationary():
    assert calib.is_stationary(np.array([0.5, 0.0, 0.0]), 1)
    assert not calib.is_stationary(np.array([1.2, 0.0, 0.0]), 1)
    assert not calib.is_stationary(np.array([0.6, 0.5, 0.0]), 2)


def test_calibrated_size_and_power_small():
    rng = np.random.default_rng(3)
    X = dgp.ar1(3000, 120, rng, 0.3)
    p = calib.calibrated_pvalues(X, seed=5)["p"]
    assert 0.035 < np.mean(p <= 0.05) < 0.07
    p1 = calib.calibrated_pvalues(X + 1.5 / math.sqrt(12), seed=5)["p"]
    assert np.mean(p1 <= 0.05) > 0.6


def test_calibrated_pvalue_deterministic_and_bounded():
    x = np.random.default_rng(4).standard_normal(120) + 0.1
    a = calib.calibrated_pvalue(x, seed=9)
    b = calib.calibrated_pvalue(x, seed=9)
    assert a == b and 0 < a <= 1
    # sequential stopping never changes a decision at alpha_max
    X = np.random.default_rng(5).standard_normal((300, 120))
    full = calib.calibrated_pvalues(X, seed=3, full=True)["p"]
    fast = calib.calibrated_pvalues(X, seed=3)["p"]
    assert np.array_equal(full <= 0.05, fast <= 0.05)


def test_declared_crash_layer_is_more_conservative():
    X = dgp.crash(500, 120, np.random.default_rng(6), 0.2 / 12, -6.0)
    p0 = calib.calibrated_pvalues(X, seed=1)["p"]
    p1 = calib.calibrated_pvalues(X, seed=1, crash=(0.2 / 12, -6.0))["p"]
    assert np.all(p1 >= p0)


def test_stat_lags_rule():
    assert calib.stat_lags(120) == 12
    assert calib.stat_lags(260, overlap=4) == 26
    assert calib.stat_lags(2520) == 252


# ------------------------------------------------------------------------------------------------ 3. stress rule
def test_stress_rule_R4_equals_base_at_zero_drag_and_is_monotone():
    rng = np.random.default_rng(7)
    X = np.ascontiguousarray(rng.standard_normal((1500, 144)) + 0.9 / math.sqrt(12))
    base = gating.val_gate(X, X + 1, 12, stress_rule="R0_mean_pos", seed=3)
    prev = None
    for d in (0.0, 0.2, 0.5):
        ok = gating.val_gate(X, X - d / math.sqrt(12), 12, stress_rule="R4_gate", seed=3)
        if d == 0.0:
            assert np.array_equal(ok, base)
        if prev is not None:
            assert np.all(ok <= prev)
        prev = ok


# ------------------------------------------------------------------------------------------------ 4. validators
def test_enforce_D_floor_and_effective_obs():
    assert validators.enforce_D(0.6) == 1.0
    assert validators.enforce_D(1.4) == 1.4
    assert validators.effective_obs(15233, 0.6) == 15233
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert validators.enforce_D(0.6, {"source": "full_dev_null", "se": 0.1}) == 0.6
    with pytest.raises(validators.EffectiveNError):
        validators.enforce_D(-1)


def test_validate_spec_floors_lrv_D():
    v = validators.validate_spec("timeseries", {"periods_per_year": 252, "autocorr": {"model": "lrv", "D": 0.6}})
    assert v["params"]["autocorr"]["D"] == 1.0 and v["D_floored"]
    d, _ = validators.build_validated("timeseries", {"periods_per_year": 252, "autocorr": {"model": "lrv", "D": 0.6}})
    assert d.series.D1 >= 1.0
    assert d.n_eff(10) <= d.n_raw(10)


def test_rho_bet_from_ic_dispersion():
    N, rb = 500, 0.05
    sd = math.sqrt((1 + (N - 1) * rb) / N)
    assert validators.rho_bet_from_ic_dispersion(N, sd) == pytest.approx(rb)
    assert validators.rho_bet_from_ic_dispersion(N, 0.01) == 0.0


def test_breadth_refuses_market_neutral_pairwise():
    params = {"n_assets": 500, "periods_per_year": 12, "ic": 0.02, "ic_autocorr": 0.0, "rho_resid": 0.0001,
              "rho_signal": 1.0}
    with pytest.raises(validators.EffectiveNError):
        validators.validate_spec("cross_sectional_ic", params, {"rho_source": "market_neutral_pairwise_residual"})
    with pytest.raises(validators.EffectiveNError):
        validators.validate_spec("cross_sectional_ic", params, None)
    sd = math.sqrt((1 + 499 * 0.06) / 500)
    d, v = validators.build_validated("cross_sectional_ic", params, {"rho_source": "ic_dispersion", "sd_ic": sd})
    assert d.implied["rho_bet"] == pytest.approx(0.06)
    assert d.implied["sharpe_gross_linear_book"] < 0.3


def test_rho_bet_from_held_bets():
    rng = np.random.default_rng(8)
    F = rng.standard_normal((5000, 1))
    B = math.sqrt(0.2) * F + math.sqrt(0.8) * rng.standard_normal((5000, 30))
    assert validators.rho_bet_from_held_bets(B) == pytest.approx(0.2, abs=0.03)


# ------------------------------------------------------------------------------------------------ 5-6. power, CIs
def test_analytic_joint_monotone_in_S():
    ser = SeriesModel(12, Autocorr("ar1", phi=0.0))
    pj = [analytic_joint(ser, 12, 10, 10, S, 0.1)[2] for S in (0.25, 0.4, 0.7, 1.0)]
    assert all(a < b for a, b in zip(pj, pj[1:]))


def test_calibrated_ci_contains_truth_on_long_series():
    x = np.random.default_rng(9).standard_normal(1200) + 0.5 / math.sqrt(12)
    out = ci.calibrated_ci(x, level=0.95, B=199)
    lo, hi, est = out["sharpe_ann"]
    assert lo < 0.5 < hi and lo < est < hi
    lo, hi, est = out["mean_ann"]
    assert lo < est < hi
