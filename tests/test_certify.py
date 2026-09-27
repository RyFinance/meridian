"""Tests for research/certify/guards.py on synthetic data. No project report files are read here;
everything is generated so the guards can be checked against known ground truth."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.certify import guards as g


def _dates(n, start="2003-01-02"):
    return pd.bdate_range(start, periods=n)


# ================================================================================================
# G1 beta
# ================================================================================================

def test_g1_pure_beta_fails():
    """A series that is exactly beta * benchmark + tiny noise, with zero true alpha, must fail G1."""
    rng = np.random.default_rng(0)
    n = 2000
    idx = _dates(n)
    bench = pd.Series(rng.normal(0, 0.01, n), index=idx)
    y = 0.8 * bench + pd.Series(rng.normal(0, 1e-5, n), index=idx)   # ~zero alpha, tiny idiosyncratic noise
    out = g.g1_beta(y, {"BENCH": bench})
    assert out["pass"] is False
    assert out["value"]["alpha_t"] < g.G1_ALPHA_T_MIN
    assert out["value"]["betas"]["BENCH"] == pytest.approx(0.8, abs=0.05)


def test_g1_genuine_alpha_passes():
    """beta exposure plus a real, persistent iid alpha on top should pass G1."""
    rng = np.random.default_rng(1)
    n = 3000
    idx = _dates(n)
    bench = pd.Series(rng.normal(0.0002, 0.01, n), index=idx)
    alpha_daily = 0.0006  # a large, persistent daily alpha so the mean/std ratio clears both conditions
    noise = rng.normal(0, 0.003, n)
    y = 0.3 * bench + alpha_daily + pd.Series(noise, index=idx)
    out = g.g1_beta(y, {"BENCH": bench})
    assert out["pass"] is True
    assert out["value"]["alpha_t"] >= g.G1_ALPHA_T_MIN
    assert out["value"]["alpha_share_of_mean"] >= g.G1_ALPHA_SHARE_MIN


def test_g1_not_run_without_inputs():
    idx = _dates(20)
    y = pd.Series(np.zeros(20), index=idx)
    out = g.g1_beta(y, {})
    assert out["pass"] is None


# ================================================================================================
# G2 reduced exposure
# ================================================================================================

def test_g2_reduced_exposure_of_falling_asset_fails():
    """Holding less of a falling benchmark (no real skill) should not look like a genuine active
    return once matched on exposure and on volatility."""
    rng = np.random.default_rng(2)
    n = 1500
    idx = _dates(n)
    bench = pd.Series(rng.normal(-0.0003, 0.01, n), index=idx)  # a falling benchmark
    exposure = pd.Series(0.3, index=idx)                          # constant, reduced exposure
    y = exposure * bench + pd.Series(rng.normal(0, 1e-5, n), index=idx)  # just holds less of it
    out = g.g2_reduced_exposure(y, {"BENCH": bench}, exposure)
    assert out["pass"] is False


def test_g2_not_run_without_exposure():
    idx = _dates(20)
    y = pd.Series(np.zeros(20), index=idx)
    bench = pd.Series(np.zeros(20), index=idx)
    out = g.g2_reduced_exposure(y, {"BENCH": bench}, None)
    assert out["pass"] is None


# ================================================================================================
# G3 concentration
# ================================================================================================

def test_g3_concentrated_in_one_year_fails():
    """Almost all of the P&L sitting in a single year should fail the concentration guard."""
    idx = _dates(252 * 6)  # ~6 years
    x = np.random.default_rng(3).normal(0, 0.001, len(idx))
    # dump almost all the positive return into year 3 (index roughly 750:1000)
    x[750:1000] += 0.02
    s = pd.Series(x, index=idx)
    out = g.g3_concentration(s)
    assert out["pass"] is False
    assert out["value"]["max_year_share"] >= g.G3_MAX_YEAR_SHARE_MAX


def test_g3_well_spread_iid_alpha_passes():
    """A steady, iid daily alpha spread evenly over many years should pass the concentration checks."""
    rng = np.random.default_rng(4)
    idx = _dates(252 * 10)
    x = rng.normal(0.0004, 0.004, len(idx))  # persistent small positive mean, moderate noise
    s = pd.Series(x, index=idx)
    out = g.g3_concentration(s)
    assert out["pass"] is True
    assert out["value"]["max_year_share"] < g.G3_MAX_YEAR_SHARE_MAX
    assert out["value"]["sign_test_p"] < g.G3_SIGN_TEST_P_MAX


def test_g3_not_run_on_short_series():
    s = pd.Series(np.zeros(3), index=_dates(3))
    out = g.g3_concentration(s)
    assert out["pass"] is None


# ================================================================================================
# G4 one asset
# ================================================================================================

def test_g4_single_asset_is_flagged_not_passed():
    idx = _dates(300)
    pnl = pd.DataFrame({"ONLY": np.random.default_rng(5).normal(0.001, 0.01, len(idx))}, index=idx)
    out = g.g4_one_asset(pnl)
    assert out["pass"] == "flag"


def test_g4_one_dominant_asset_fails():
    rng = np.random.default_rng(6)
    idx = _dates(1000)
    a = rng.normal(0.02, 0.01, len(idx))     # dominant, large positive contributor
    b = rng.normal(0.0001, 0.001, len(idx))  # small contributor
    pnl = pd.DataFrame({"A": a, "B": b}, index=idx)
    out = g.g4_one_asset(pnl)
    assert out["pass"] is False
    assert out["value"]["max_asset_share"] >= g.G4_MAX_ASSET_SHARE_MAX


def test_g4_diversified_assets_pass():
    rng = np.random.default_rng(7)
    idx = _dates(1500)
    pnl = pd.DataFrame({
        "A": rng.normal(0.0006, 0.004, len(idx)),
        "B": rng.normal(0.0006, 0.004, len(idx)),
        "C": rng.normal(0.0006, 0.004, len(idx)),
    }, index=idx)
    out = g.g4_one_asset(pnl)
    assert out["pass"] is True


# ================================================================================================
# G5 null calibration
# ================================================================================================

def test_g5_pass_and_fail_threshold():
    assert g.g5_null_calibration(0.02)["pass"] is True
    assert g.g5_null_calibration(0.20)["pass"] is False
    assert g.g5_null_calibration(None)["pass"] is None


def test_g5_flags_shifted_null():
    out = g.g5_null_calibration(0.01, null_distribution=np.full(500, -0.96))
    assert out["pass"] is True
    assert out["value"]["flag"] is not None


def test_g5_no_flag_for_centred_null():
    out = g.g5_null_calibration(0.01, null_distribution=np.random.default_rng(8).normal(0, 0.3, 500))
    assert out["value"]["flag"] is None


# ================================================================================================
# G6 post-publication
# ================================================================================================

def test_g6_insufficient_data_is_flagged():
    idx = _dates(80)
    y = pd.Series(np.random.default_rng(9).normal(0.001, 0.01, len(idx)), index=idx)
    out = g.g6_post_publication(y, str(idx[-10].date()))  # only ~10 obs after publication
    assert out["pass"] == "flag"


def test_g6_pass_and_fail():
    rng = np.random.default_rng(10)
    idx = _dates(1500)
    pub = str(idx[500].date())
    y_pass = pd.Series(rng.normal(0.0015, 0.004, len(idx)), index=idx)
    out_pass = g.g6_post_publication(y_pass, pub)
    assert out_pass["pass"] is True

    y_fail = pd.Series(rng.normal(0.0, 0.01, len(idx)), index=idx)
    out_fail = g.g6_post_publication(y_fail, pub)
    assert out_fail["pass"] is False


# ================================================================================================
# G7 execution lag
# ================================================================================================

def test_g7_lag_destroys_signal_fails():
    rng = np.random.default_rng(11)
    idx = _dates(1000)
    y = pd.Series(rng.normal(0.001, 0.004, len(idx)), index=idx)
    lagged = pd.Series(rng.normal(0.0, 0.004, len(idx)), index=idx)  # unrelated, no signal left
    out = g.g7_execution_lag(y, lagged)
    assert out["pass"] is False


def test_g7_robust_to_lag_passes():
    rng = np.random.default_rng(12)
    idx = _dates(1000)
    y = pd.Series(rng.normal(0.001, 0.004, len(idx)), index=idx)
    lagged = y * 0.9 + pd.Series(rng.normal(0, 1e-6, len(idx)), index=idx)
    out = g.g7_execution_lag(y, lagged)
    assert out["pass"] is True


def test_g7_not_run_without_lagged_returns():
    idx = _dates(20)
    y = pd.Series(np.zeros(20), index=idx)
    out = g.g7_execution_lag(y, None)
    assert out["pass"] is None


# ================================================================================================
# certify(): end-to-end wiring
# ================================================================================================

def test_certify_runs_all_guards_and_marks_missing_inputs_not_run():
    rng = np.random.default_rng(13)
    idx = _dates(1500)
    bench = pd.Series(rng.normal(0.0002, 0.01, len(idx)), index=idx)
    y = 0.3 * bench + 0.0005 + pd.Series(rng.normal(0, 0.003, len(idx)), index=idx)
    out = g.certify(y, benchmarks={"BENCH": bench})
    assert set(out.keys()) == {
        "G1_beta", "G2_reduced_exposure", "G3_concentration", "G4_one_asset",
        "G5_null_calibration", "G6_post_publication", "G7_execution_lag",
    }
    # inputs not supplied -> NOT-RUN
    assert out["G2_reduced_exposure"]["pass"] is None  # no exposure supplied
    assert out["G4_one_asset"]["pass"] is None          # no asset_pnl supplied
    assert out["G5_null_calibration"]["pass"] is None   # no null_pass_rate supplied
    assert out["G6_post_publication"]["pass"] is None   # no publication_date supplied
    assert out["G7_execution_lag"]["pass"] is None       # no lagged_returns supplied
    # inputs supplied -> guard actually ran
    assert out["G1_beta"]["pass"] in (True, False)
    assert out["G3_concentration"]["pass"] in (True, False)
