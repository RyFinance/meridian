"""Tests for research.power (synthetic only). Run: .venv/bin/python -m pytest tests/test_power.py -q"""
from __future__ import annotations

import json
import math
import pathlib
import warnings

import numpy as np
import pytest

from research.power import designs as DS
from research.power import gates as G
from research.power import plan_check as PC
from research.power import report as R
from research.power import simulate as M
from research.power import specs as SP
from research.power import verify as V
from research.power.core import (Autocorr, CorrelationAssumptionError, IndependenceWarning, SeriesModel,
                                 batch_alpha, breadth_eff, kish_deff, single_test_power, years_single_test)


# ------------------------------------------------------------------------------------------ core formulas
def test_ar1_lrv_closed_form_matches_sum():
    a = Autocorr("ar1", phi=0.3)
    assert a.D1() == pytest.approx(1.3 / 0.7)
    assert Autocorr("acf", rho=tuple(0.3 ** k for k in range(1, 200))).D1() == pytest.approx(1.3 / 0.7, rel=1e-9)
    n = 50
    exact = 1 + 2 * sum((1 - k / n) * 0.3 ** k for k in range(1, n))
    assert a.D1(n) == pytest.approx(exact)


def test_overlap_D_equals_horizon_and_persistent_overlap():
    assert Autocorr("overlap", horizon=5).D1() == pytest.approx(5.0)
    assert Autocorr("overlap_persistent", phi=1.0, horizon=5).D1() == pytest.approx(5.0)
    assert Autocorr("overlap_persistent", phi=0.0, horizon=5).D1() == pytest.approx(1.0)


def test_bartlett_bootstrap_D_underestimates_short_blocks():
    a = Autocorr("ar1", phi=0.5)
    assert a.bartlett(1) == 1.0
    assert a.bartlett(2) < a.bartlett(20) < a.D1()
    assert a.bartlett(400) == pytest.approx(a.D1(), rel=0.02)


def test_sharpe_se_reduces_to_lo_and_mertens():
    s = SeriesModel(12, Autocorr("ar1", phi=0.0))
    S = 1.2
    sp = S / math.sqrt(12)
    assert float(s.kappa2(S)) == pytest.approx(1 + sp ** 2 / 2)                  # Lo (2002) iid
    sk = SeriesModel(12, Autocorr("ar1", phi=0.0), skew=-1.0, exkurt=5.0)
    assert float(sk.kappa2(S)) == pytest.approx(1 + sp + (7 / 4) * sp ** 2)     # Mertens / Opdyke


def test_kish_and_breadth():
    assert kish_deff(10, 0.1) == pytest.approx(1.9)
    assert kish_deff(10, 0.1, cluster_size_cv=1.0) == pytest.approx(1 + 19 * 0.1)
    assert float(breadth_eff(500, 0.1)) == pytest.approx(500 / 50.9)
    assert float(breadth_eff(10 ** 6, 0.2)) == pytest.approx(5.0, rel=1e-4)      # ceiling 1/rho


def test_batch_alpha():
    assert batch_alpha(1) == 0.05 and batch_alpha(3) == pytest.approx(0.05 / 3)


def test_power_mde_years_are_mutually_consistent():
    s = SeriesModel(252, Autocorr("ar1", phi=0.1))
    Y = years_single_test(0.7, s, 0.05)
    assert float(single_test_power(0.7, s, Y, 0.05)) == pytest.approx(0.8, abs=1e-6)
    from research.power.core import mde_single_test
    m = mde_single_test(s, Y, 0.05)
    assert m == pytest.approx(0.7, abs=1e-4)
    assert float(single_test_power(0.0, s, 10, 0.05)) == pytest.approx(0.05)


# ------------------------------------------------------------------------------------------ refusals
def test_refuses_zero_correlation_for_panels_events_cross_sections():
    with pytest.raises(CorrelationAssumptionError):
        DS.panel(n_markets=30, periods_per_year=12, rho=0.0, autocorr=0.0)
    with pytest.raises(CorrelationAssumptionError):
        DS.event_study(events_per_year=500, car_sd=0.05, hold_days=5, icc=0.0,
                       concurrency={"model": "uniform_poisson"}, portfolio_autocorr=0.0)
    with pytest.raises(CorrelationAssumptionError):
        DS.cross_sectional_ic(n_assets=100, periods_per_year=12, ic=0.02, ic_autocorr=0.0, rho_resid=0.0)
    with pytest.raises(CorrelationAssumptionError):
        DS.carry(n_assets=4, periods_per_year=12, rho=0.0, autocorr=0.0, skew=-1, exkurt=3)
    with pytest.raises(TypeError):
        DS.panel(n_markets=30, periods_per_year=12, rho=None, autocorr=0.0)
    with pytest.raises(TypeError):
        DS.timeseries(periods_per_year=12, autocorr=None)


def test_override_warns_loudly():
    with pytest.warns(IndependenceWarning):
        d = DS.panel(n_markets=30, periods_per_year=12, rho=0.0, autocorr=0.0, assume_independent="orthogonalised")
    assert d.n_eff_units == pytest.approx(30)


def test_single_asset_event_needs_no_icc():
    d = DS.event_study(events_per_year=12, car_sd=0.01, hold_days=3, icc=0.0,
                       concurrency={"model": "clusters", "mean_size": 1}, portfolio_autocorr=0.0)
    assert d.deff_cross == 1.0


# ------------------------------------------------------------------------------------------ designs
def test_event_deff_and_calendar_equivalence():
    d = DS.event_study(events_per_year=100, car_sd=0.05, hold_days=1, icc=0.2,
                       concurrency={"model": "clusters", "mean_size": 5}, portfolio_autocorr=0.0, mean_car=0.01)
    assert d.deff_cross == pytest.approx(1 + 4 * 0.2)
    assert d.implied["sharpe_net"] == pytest.approx(0.2 * math.sqrt(100 / 1.8))
    assert d.sharpe_from_natural(d.natural_from_sharpe(0.7)) == pytest.approx(0.7)


def test_long_short_no_tilt_matches_textbook():
    d = DS.long_short(n_assets=1000, periods_per_year=12, ic=0.05, cs_dispersion=0.05, quantile=0.1, rho_resid=0.0,
                      rho_signal=0.0, signal_autocorr=0.5, cost_bps_one_way=0, spread_autocorr=0.0,
                      assume_independent="unit test")
    from scipy.stats import norm
    k = 2 * norm.pdf(norm.isf(0.1)) / 0.1
    assert d.implied["spread_mean_gross"] == pytest.approx(0.05 * 0.05 * k, rel=1e-3)
    assert d.implied["spread_sd"] == pytest.approx(0.05 * math.sqrt((1 - 0.05 ** 2) * 2 / 100), rel=2e-2)


def test_one_factor_moments_diversify_idio_not_common_crash():
    cm = DS.crash_moments(0.05, -4, 1)
    single = DS.one_factor_portfolio_moments(1, 0.4, cm["skew"], cm["exkurt"], cm["skew"], cm["exkurt"])
    assert single["skew"] == pytest.approx(0.4 ** 1.5 * cm["skew"] + 0.6 ** 1.5 * cm["skew"])
    many = DS.one_factor_portfolio_moments(1000, 0.4, cm["skew"], cm["exkurt"])
    assert many["skew"] == pytest.approx(cm["skew"], rel=0.01)


# ------------------------------------------------------------------------------------------ gates
def test_amendment2_gate_legs():
    s = SeriesModel(252, Autocorr("ar1", phi=0.0))
    g = G.amendment2_dev_gate(4, 0.1)
    assert g.sharpe_c == 2.4 and g.alpha == pytest.approx(0.0125)
    L = g.legs(s, 9.0)
    assert L["sharpe_c_over_sqrtT"] == pytest.approx(0.8)
    assert g.threshold(s, 9.0) == pytest.approx(max(0.8, 2.2414 / 3, 0.1), rel=1e-3)


def test_fixed_075_gate_cannot_reach_80pct_below_075():
    s = SeriesModel(252, Autocorr("ar1", phi=0.05))
    assert math.isinf(G.years_joint(0.7, s, G.amendment2_dev_gate(1, 0.1), s, G.current_val_gate(1, 0.1)))
    assert math.isfinite(G.years_joint(0.7, s, G.amendment2_dev_gate(1, 0.1), s, G.power_aware_val_gate(1, 0.1)))


def test_pav_size_and_uniform_dominance():
    s = SeriesModel(252, Autocorr("ar1", phi=0.05))
    pav = G.power_aware_val_gate(1, 0.1)
    cur = G.current_val_gate(1, 0.1)
    for Y in (3, 6, 12):
        assert float(pav.pass_prob(0.0, s, Y)) <= 0.05 + 1e-12
        # wherever the 0.75 gate is stricter than the level-5% threshold, PAV has more power at every S > 0
        if cur.threshold(s, Y) > pav.threshold(s, Y):
            for S in (0.1, 0.3, 0.7, 1.5):
                assert float(pav.pass_prob(S, s, Y)) > float(cur.pass_prob(S, s, Y))


def test_fraction_of_dev_gate_integrates():
    s = SeriesModel(12, Autocorr("ar1", phi=0.0))
    dg = G.amendment2_dev_gate(1, None)
    vg = G.Gate(fraction_of_dev=0.0, alpha=0.05)
    a = G.joint_pass(0.7, s, 10, dg, s, 10, vg)
    b = G.joint_pass(0.7, s, 10, dg, s, 10, G.Gate(alpha=0.05))
    assert a["p_joint"] == pytest.approx(b["p_joint"], abs=2e-3)


def test_winners_curse_shrinks_estimate():
    s = SeriesModel(252, Autocorr("lrv", D=1.4))
    dg = G.amendment2_dev_gate(1, 0.2)
    c = G.truncation_corrected_estimate(0.664, s, 12, dg)
    assert c is not None and c < 0.664
    assert G.truncation_corrected_estimate(0.3, s, 12, dg) is None


def test_reproduces_null_lab2_tsy_calibration():
    """Analytic joint power at S=0.7 for tsy_month_end matches null_lab2's independent simulation (0.291)."""
    s = SeriesModel(252, Autocorr("ar1", phi=0.15))
    j = G.joint_pass(0.7, s, 12, G.amendment2_dev_gate(1, 0.008 / 0.028), s, 11.63, G.current_val_gate(1, 0.008 / 0.028))
    assert j["p_joint"] == pytest.approx(0.291, abs=0.02)


# ------------------------------------------------------------------------------------------ Monte Carlo
def test_literal_block_bootstrap_matches_bartlett_threshold():
    s = SeriesModel(252, Autocorr("ar1", phi=0.15), null_block=21)
    g = G.Gate(alpha=0.05)
    an = float(g.pass_prob(0.0, s, 5))
    mc = M.mc_gate(s, 0.0, 5, g, n_paths=1500, B=299, seed_salt="t_cbb")
    assert abs(mc["p_pass"] - an) < 0.03


@pytest.fixture(scope="module")
def mc_rows():
    return V.suite(fast=True)


def test_mc_agreement_every_design(mc_rows):
    checked = [r for r in mc_rows if r["within_tolerance"] is not None]
    bad = [r for r in checked if not r["within_tolerance"]]
    assert not bad, bad
    designs = {r["design"].split(" ")[0] for r in checked}
    for d in ("timeseries", "monthly;", "event", "cross-sectional", "decile", "carry", "panel", "17-sleeve"):
        assert d in designs


def test_naive_independence_is_oversized(mc_rows):
    naive = [r for r in mc_rows if "naive" in r["check"]]
    assert naive and all(r["mc"] > 0.10 for r in naive)


# ------------------------------------------------------------------------------------------ CLI / schema
def test_all_examples_validate_and_run(tmp_path):
    for s in SP.all_specs():
        PC.validate(s)
    s = next(x for x in SP.retrospective() if x["name"] == "retro_tsy_month_end")
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(s))
    PC.main([str(p), "--out", str(tmp_path)])
    rep = json.loads((tmp_path / "retro_tsy_month_end.json").read_text())
    assert rep["verdict"] in ("DECISIVE", "MARGINAL", "INCAPABLE")
    assert (tmp_path / "retro_tsy_month_end.txt").exists()
    assert 0.2 < rep["joint_power_at_0.7"] < 0.4


def test_schema_rejects_missing_correlation():
    import jsonschema
    s = next(x for x in SP.prospective() if x["name"] == "pro_panel30_monthly")
    s = json.loads(json.dumps(s))
    del s["params"]["rho"]
    with pytest.raises(jsonschema.ValidationError):
        PC.validate(s)


def test_verdict_rule():
    assert R.verdict(0.6, 0.01) == "DECISIVE"
    assert R.verdict(0.3, 0.01) == "MARGINAL"
    assert R.verdict(0.2, 0.01) == "INCAPABLE"
    assert R.verdict(0.9, 0.2) == "INCAPABLE"
