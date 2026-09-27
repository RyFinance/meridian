"""Tests for research/null_lab2 (Workstream C1: null-world calibration across all families).

Covers: the synthetic AR(1) generator's statistical properties, that the bootstrap/shift reference-
quantile substitution used by calibrate.py approximates a literal nested bootstrap (the documented
approximation the workstream brief allows), the gate table's structural integrity, and that the
calibration/flags/multiple-testing outputs are internally consistent.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from research.null_lab2 import calibrate as C
from research.null_lab2 import flags as F
from research.null_lab2 import multiple_testing as MT
from research.null_lab2 import sim_params as SP
from research.null_lab2.families import ROWS
from research.null_lab2.synth import ar1_paths, sharpe_of, ann_mean_of, naive_t_of, kappa_of


# -- synth.py: generator statistical properties ------------------------------------------------------

def test_ar1_paths_matches_target_vol_and_mean():
    rng = np.random.default_rng(1)
    paths = ar1_paths(2520, 4000, 252.0, annual_vol=0.10, annual_mean=0.05, phi=0.10, rng=rng)
    ann_vol_hat = paths.std(axis=1, ddof=1).mean() * math.sqrt(252.0)
    ann_mean_hat = ann_mean_of(paths, 252.0).mean()
    assert ann_vol_hat == pytest.approx(0.10, rel=0.05)
    assert ann_mean_hat == pytest.approx(0.05, rel=0.10)


def test_ar1_paths_autocorrelation_matches_phi():
    rng = np.random.default_rng(2)
    phi = 0.30
    paths = ar1_paths(5000, 500, 252.0, annual_vol=0.08, annual_mean=0.0, phi=phi, rng=rng)
    x = paths - paths.mean(axis=1, keepdims=True)
    num = (x[:, 1:] * x[:, :-1]).sum(axis=1)
    den = (x[:, :-1] ** 2).sum(axis=1)
    phi_hat = float(np.mean(num / den))
    assert phi_hat == pytest.approx(phi, abs=0.05)


def test_zero_mean_sharpe_is_centred_at_zero():
    rng = np.random.default_rng(3)
    paths = ar1_paths(1260, 5000, 252.0, annual_vol=0.06, annual_mean=0.0, phi=0.05, rng=rng)
    sr = sharpe_of(paths, 252.0)
    assert float(np.nanmean(sr)) == pytest.approx(0.0, abs=0.05)


def test_kappa_of_is_near_one_for_low_autocorrelation():
    rng = np.random.default_rng(4)
    paths = ar1_paths(1260, 5000, 252.0, annual_vol=0.06, annual_mean=0.0, phi=0.02, rng=rng)
    sr = sharpe_of(paths, 252.0)
    kappa = kappa_of(sr, 1260 / 252.0)
    # Low autocorrelation should give kappa close to the iid value of 1.0, well inside the
    # reports/null_lab/REPORT.md range of ~0.85-1.4 this project already established.
    assert 0.85 <= kappa <= 1.25


def test_naive_t_scales_as_sharpe_times_sqrt_years():
    rng = np.random.default_rng(5)
    T_years = 10.0
    n = int(T_years * 252)
    paths = ar1_paths(n, 6000, 252.0, annual_vol=0.08, annual_mean=0.04, phi=0.0, rng=rng)
    t = naive_t_of(paths)
    sr = sharpe_of(paths, 252.0)
    # For phi=0 (iid) the naive t-stat should equal Sharpe_hat * sqrt(T_years) exactly (up to fp).
    np.testing.assert_allclose(t, sr * math.sqrt(T_years), rtol=1e-6)


# -- calibrate.py: the bootstrap-quantile substitution is a fair proxy for a literal bootstrap p ----

def test_bootstrap_quantile_matches_nested_bootstrap():
    """Exactness check for the documented approximation in calibrate.py's module docstring: for a
    mean-centred-bootstrap-style null test, replacing "p < alpha via literal resampling" with
    "Sharpe_hat exceeds the (1-alpha) quantile of a same-length/vol/autocorrelation zero-mean
    reference batch" should give close to the same false-pass rate as an actual nested block
    bootstrap, at a shared alpha."""
    rng_outer = np.random.default_rng(42)
    n_periods, periods_per_year, annual_vol, phi, alpha = 504, 252.0, 0.06, 0.10, 0.05
    n_outer = 600

    # (1) calibrate.py's method: single reference batch, quantile threshold.
    q = C._null_reference_quantile(n_periods, periods_per_year, annual_vol, phi, 0.0, alpha,
                                    3000, np.random.default_rng(7))
    outer_paths = ar1_paths(n_periods, n_outer, periods_per_year, annual_vol, 0.0, phi, rng_outer)
    sr_outer = sharpe_of(outer_paths, periods_per_year)
    p_quantile_method = float((sr_outer >= q).mean())

    # (2) a literal nested block bootstrap p-value per outer draw (block=21, 400 inner draws -- small
    # inner count to keep the test fast; still enough to check the quantile method isn't badly off).
    block = 21
    n_inner = 400
    rng_inner = np.random.default_rng(99)
    passed = np.zeros(n_outer, dtype=bool)
    nb = int(np.ceil(n_periods / block))
    for i in range(n_outer):
        x = outer_paths[i] - outer_paths[i].mean()  # mean-centred, as the project's bootstrap does
        starts = rng_inner.integers(0, n_periods, size=(n_inner, nb))
        idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_inner, -1)[:, :n_periods] % n_periods
        boot = x[idx]
        sr_boot = boot.mean(axis=1) / boot.std(axis=1, ddof=1) * math.sqrt(periods_per_year)
        p = float((sr_boot >= sr_outer[i]).mean())
        passed[i] = p < alpha
    p_nested_method = float(passed.mean())

    # Both should land near alpha (well-calibrated test), and near each other.
    assert p_quantile_method == pytest.approx(alpha, abs=0.03)
    assert p_nested_method == pytest.approx(alpha, abs=0.04)
    assert abs(p_quantile_method - p_nested_method) < 0.06


# -- families.py / gate_table structural integrity ---------------------------------------------------

def test_every_row_has_required_fields():
    assert len(ROWS) >= 30
    seen = set()
    for row in ROWS:
        assert row.family not in seen, f"duplicate family key {row.family}"
        seen.add(row.family)
        assert row.archetype
        assert row.protocol in ("pre-2026-09-23", "post-2026-09-23") or "pre-2026-09-23" in row.protocol \
            or row.protocol.startswith("mixed")
        assert row.k >= 1
        assert row.dev_null in ("none", "bootstrap", "shift", "permutation", "placebo_rank",
                                 "reported_only", "bootstrap+DSR")


def test_post_amendment_thresholds_match_formula():
    for row in ROWS:
        if row.protocol == "post-2026-09-23" and row.dev_years and row.dev_thresh_val:
            mult = 2.4 if row.k >= 4 else 1.8
            expected = mult / math.sqrt(row.dev_years)
            assert row.dev_thresh_val == pytest.approx(expected, rel=1e-6), row.family


def test_sim_params_exists_for_every_family():
    for row in ROWS:
        p = SP.get(row.family, row.dev_kind, row.dev_null)
        assert p.periods_per_year > 0
        assert p.annual_vol > 0


# -- calibration.py: end-to-end smoke test on a small subset -----------------------------------------

def test_simulate_dev_pass_rate_decreases_with_null_offset():
    """A sanity check on the whole pipeline: for a bootstrap-gated family, P(pass dev) should be
    monotone increasing in true_sr."""
    row = next(r for r in ROWS if r.family == "tsy_month_end(M)")
    p_neg = C.simulate_dev(row, -0.3, n_draws=800, seed_salt="t1").pass_frac
    p_zero = C.simulate_dev(row, 0.0, n_draws=800, seed_salt="t2").pass_frac
    p_pos = C.simulate_dev(row, 0.7, n_draws=800, seed_salt="t3").pass_frac
    assert p_neg <= p_zero <= p_pos


def test_simulate_dev_returns_none_when_no_dev_window():
    class Dummy:
        dev_years = None
    # families with no dev window (none currently) should be skippable; simulate via a row copy
    row = ROWS[0]
    orig = row.dev_years
    try:
        row.dev_years = None
        assert C.simulate_dev(row, 0.0, n_draws=100) is None
    finally:
        row.dev_years = orig


def test_no_dev_null_families_have_high_false_pass_rate_at_flat_threshold():
    """Cross-check against reports/null_lab/REPORT.md's headline finding: the old flat-0.5 gate
    false-passes roughly 10-19% of zero-mean nulls. options_signals uses exactly that old gate."""
    row = next(r for r in ROWS if r.family == "options_signals(H1-H4)")
    res = C.simulate_dev(row, 0.0, n_draws=3000, seed_salt="cross_check")
    assert 0.05 <= res.pass_frac <= 0.30


# -- flags.py / multiple_testing.py ------------------------------------------------------------------

def test_flags_build_and_have_required_fields(tmp_path):
    calib_path = tmp_path / "calibration.csv"
    out_path = tmp_path / "flags.csv"
    rows = C.run_all(n_draws=200)
    import csv as _csv
    with open(calib_path, "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    fl = F.build(calib_path=str(calib_path), out_path=str(out_path))
    assert len(fl) > 5
    for row in fl:
        assert row["severity"] in ("high", "medium", "low")
        assert row["family"]
        assert row["description"]
    assert out_path.exists()


def test_multiple_testing_totals_are_consistent(tmp_path):
    calib_path = tmp_path / "calibration.csv"
    out_path = tmp_path / "mt.json"
    rows = C.run_all(n_draws=200)
    import csv as _csv
    with open(calib_path, "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    result = MT.build(calib_path=str(calib_path), out_path=str(out_path))
    t1 = result["tier1_registered_gate_evaluable"]
    assert t1["n_candidates"] == sum(r["n_candidates"] for r in t1["rows"])
    assert t1["actual_dev_passes"] >= t1["actual_full_dev_and_val_passes"]
    gt = result["grand_total"]
    assert gt["low"] <= gt["point_estimate"] <= gt["high"]
