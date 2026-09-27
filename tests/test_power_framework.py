"""Contract tests for the research-only power disclosure sidecar."""

from dataclasses import replace

import pytest

from research.power_framework import preregistration
from research.power_framework.core import DesignSpec, analyze_design
from research.power_framework.preregistration import (
    PreregistrationPowerSpec,
    _atomic_write,
    analyze_preregistration,
    freeze_disclosure,
    verify_disclosure,
)


def test_assets_do_not_multiply_portfolio_sharpe_information():
    base = DesignSpec(category="long_short_portfolio", n_periods=252)
    wide = replace(base, units_per_period=500, cross_sectional_correlation=0.2)
    a, b = analyze_design(base), analyze_design(wide)
    assert b["raw_observations"] == 500 * a["raw_observations"]
    assert b["effective_observations"] == pytest.approx(a["effective_observations"])
    assert b["power_for_true_sharpe"] == a["power_for_true_sharpe"]


def test_pooled_panel_discounts_correlated_assets():
    independent = DesignSpec(
        category="multi_asset_panel", n_periods=252, units_per_period=500
    )
    correlated = replace(independent, cross_sectional_correlation=0.2)
    a, b = analyze_design(independent), analyze_design(correlated)
    assert a["effective_observations"] == pytest.approx(126_000)
    assert b["effective_observations"] == pytest.approx(126_000 / 100.8)
    assert b["power_for_true_sharpe"]["0.7"] < a["power_for_true_sharpe"]["0.7"]


def test_fixed_validation_gate_exposes_unattainable_power():
    val = DesignSpec(category="monthly_strategy", n_periods=120, minimum_sharpe=0.75)
    result = analyze_design(val)
    assert result["approx_calendar_years_required"]["0.7"] is None


def test_disclosure_requires_same_null_and_valid_hashes():
    stage = DesignSpec(category="daily_return_strategy", n_periods=1260)
    plan = PreregistrationPowerSpec(
        experiment_id="contract_test",
        development=stage,
        validation=stage,
        registered_candidate_count=2,
        calculated_before_returns=True,
        null_process="Mean-centred paired block null",
        same_null_for_p_value_and_false_pass=False,
        expected_false_pass_rate=0.02,
        expected_false_pass_mc_se=0.002,
        input_hashes={"plan": "invalid"},
        simulation_draws=1000,
    )
    disclosure = analyze_preregistration(plan)
    assert verify_disclosure(disclosure)
    assert not disclosure["protocol_amendment_2"]["registration_ready"]
    assert len(disclosure["protocol_amendment_2"]["registration_blockers"]) == 2


def test_frozen_artifacts_are_never_overwritten(tmp_path):
    target = tmp_path / "frozen.json"
    target.write_text("original")
    with pytest.raises(FileExistsError):
        _atomic_write(target, "replacement")
    assert target.read_text() == "original"

    stage = DesignSpec(category="daily_return_strategy", n_periods=1260)
    plan = PreregistrationPowerSpec(
        experiment_id="contract_test",
        development=stage,
        validation=stage,
        registered_candidate_count=1,
        calculated_before_returns=True,
        null_process="Mean-centred paired block null",
        same_null_for_p_value_and_false_pass=True,
        expected_false_pass_rate=0.02,
        expected_false_pass_mc_se=0.002,
        input_hashes={"plan": "a" * 64},
        simulation_draws=1000,
    )
    markdown = tmp_path / "frozen.md"
    with pytest.raises(FileExistsError):
        freeze_disclosure(plan, target, markdown)
    assert target.read_text() == "original"
    assert not markdown.exists()


def test_writer_refuses_a_concurrent_artifact(tmp_path, monkeypatch):
    target = tmp_path / "frozen.json"
    real_link = preregistration.os.link

    def racing_link(source, destination):
        target.write_text("other writer")
        return real_link(source, destination)

    monkeypatch.setattr(preregistration.os, "link", racing_link)
    with pytest.raises(FileExistsError):
        _atomic_write(target, "our disclosure")
    assert target.read_text() == "other writer"
