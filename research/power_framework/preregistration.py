"""Hashable power disclosures for the quant_v7 preregistration workflow."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from research.power_framework.core import POWER_GRID, DesignSpec, analyze_design

FRAMEWORK_VERSION = "quant_v7.power.v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _framework_sha256() -> str:
    digest = hashlib.sha256()
    for name in ("core.py", "preregistration.py"):
        path = Path(__file__).with_name(name)
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


@dataclass(frozen=True)
class PreregistrationPowerSpec:
    """Power inputs that must be frozen before strategy returns are calculated.

    ``expected_false_pass_rate`` is not calculated by this normal approximation.  It must come
    from the same registered null process that supplies the gating p-value and must evaluate the
    full development gate.  This separation enforces Protocol Amendment 2 N4.
    """

    experiment_id: str
    development: DesignSpec
    validation: DesignSpec
    registered_candidate_count: int
    family_alpha: float = 0.05
    null_process: str = ""
    same_null_for_p_value_and_false_pass: bool = False
    expected_false_pass_rate: float | None = None
    expected_false_pass_mc_se: float | None = None
    calculated_before_returns: bool = False
    input_hashes: dict[str, str] | None = None
    simulation_draws: int = 100_000
    simulation_seed: int = 20260924

    def __post_init__(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id cannot be blank")
        if not isinstance(self.registered_candidate_count, int) or isinstance(
            self.registered_candidate_count, bool
        ):
            raise ValueError("registered_candidate_count must be an integer")
        if self.registered_candidate_count < 1:
            raise ValueError("registered_candidate_count must be >= 1")
        if not 0 < self.family_alpha < 1:
            raise ValueError("family_alpha must lie in (0, 1)")
        if self.expected_false_pass_rate is not None and not (
            0 <= self.expected_false_pass_rate <= 1
        ):
            raise ValueError("expected_false_pass_rate must lie in [0, 1]")
        if self.expected_false_pass_mc_se is not None and not (
            0 <= self.expected_false_pass_mc_se <= 1
        ):
            raise ValueError("expected_false_pass_mc_se must lie in [0, 1]")
        if not isinstance(self.simulation_draws, int) or self.simulation_draws < 1_000:
            raise ValueError("simulation_draws must be an integer >= 1,000")
        if not isinstance(self.simulation_seed, int):
            raise ValueError("simulation_seed must be an integer")
        if self.input_hashes is None:
            object.__setattr__(self, "input_hashes", {})
        else:
            object.__setattr__(self, "input_hashes", dict(self.input_hashes))

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PreregistrationPowerSpec":
        body = dict(value)
        body["development"] = DesignSpec.from_dict(body["development"])
        body["validation"] = DesignSpec.from_dict(body["validation"])
        return cls(**body)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _stage_specs(plan: PreregistrationPowerSpec) -> tuple[DesignSpec, DesignSpec]:
    common = {
        "candidate_count": plan.registered_candidate_count,
        "family_alpha": plan.family_alpha,
    }
    return replace(plan.development, **common), replace(plan.validation, **common)


def _joint_power(
    development: dict[str, Any],
    validation: dict[str, Any],
    *,
    draws: int,
    seed: int,
) -> dict[str, dict[str, float]]:
    rng = np.random.default_rng(seed)
    dev_se = development["expected_standard_error"]["annualized_sharpe"]
    val_se = validation["expected_standard_error"]["annualized_sharpe"]
    dev_threshold = development["testing"]["decision_threshold_sharpe"]
    val_threshold = validation["testing"]["decision_threshold_sharpe"]
    rows: dict[str, dict[str, float]] = {}
    for effect in POWER_GRID:
        key = f"{effect:.1f}"
        p_dev = development["power_for_true_sharpe"][key]
        p_val = validation["power_for_true_sharpe"][key]
        dev_estimate = effect + dev_se * rng.standard_normal(draws)
        val_estimate = effect + val_se * rng.standard_normal(draws)
        passed = (dev_estimate >= dev_threshold) & (val_estimate >= val_threshold)
        simulated = float(passed.mean())
        rows[key] = {
            "development_power_analytic": float(p_dev),
            "validation_power_analytic": float(p_val),
            "joint_power_analytic_independent_stages": float(p_dev * p_val),
            "joint_power_simulated": simulated,
            "joint_power_simulation_mc_se": float(
                np.sqrt(simulated * (1.0 - simulated) / draws)
            ),
        }
    return rows


def _readiness_blockers(plan: PreregistrationPowerSpec) -> list[str]:
    blockers: list[str] = []
    if not plan.calculated_before_returns:
        blockers.append("calculated_before_returns must be true")
    if not plan.null_process.strip():
        blockers.append("null_process must describe the registered signal-destruction process")
    if not plan.same_null_for_p_value_and_false_pass:
        blockers.append("p-value and P(full pass|null) must use the same registered null process")
    if plan.expected_false_pass_rate is None:
        blockers.append("expected_false_pass_rate from the full same-null gate is required")
    elif plan.expected_false_pass_rate > plan.family_alpha:
        blockers.append("expected_false_pass_rate exceeds the family false-pass ceiling")
    if plan.expected_false_pass_mc_se is None:
        blockers.append("expected_false_pass_mc_se is required")
    if not plan.input_hashes:
        blockers.append("at least one relevant code/input SHA-256 is required")
    else:
        invalid = sorted(k for k, value in plan.input_hashes.items() if not _SHA256_RE.fullmatch(value))
        if invalid:
            blockers.append("invalid lowercase SHA-256 for: " + ", ".join(invalid))
    return blockers


def analyze_preregistration(plan: PreregistrationPowerSpec) -> dict[str, Any]:
    """Build a deterministic, hashable preregistration power disclosure.

    Joint operating characteristics simulate independent normal stage estimates using the
    correlation-adjusted standard errors.  They include the registered Sharpe floors but not
    stress-cost or other full-gate conditions, so they are optimistic when those conditions have
    less than unit power.  The experiment-specific same-null false-pass simulation remains a
    separate mandatory input.
    """

    dev_spec, val_spec = _stage_specs(plan)
    development = analyze_design(dev_spec)
    validation = analyze_design(val_spec)
    joint = _joint_power(
        development,
        validation,
        draws=plan.simulation_draws,
        seed=plan.simulation_seed,
    )
    blockers = _readiness_blockers(plan)
    low_power_at_07 = joint["0.7"]["joint_power_simulated"] < 0.50
    body: dict[str, Any] = {
        "framework_version": FRAMEWORK_VERSION,
        "status": "READY_TO_REGISTER_BEFORE_RETURNS" if not blockers else "INCOMPLETE_DO_NOT_REGISTER",
        "registered_automatically": False,
        "experiment_id": plan.experiment_id,
        "power_was_calculated_before_returns": plan.calculated_before_returns,
        "batch": {
            "registered_candidate_count": plan.registered_candidate_count,
            "family_alpha": plan.family_alpha,
            "bonferroni_alpha_per_candidate": plan.family_alpha
            / plan.registered_candidate_count,
        },
        "development": development,
        "validation": validation,
        "joint_development_and_validation_power": joint,
        "joint_power_simulation": {
            "draws": plan.simulation_draws,
            "seed": plan.simulation_seed,
            "stage_relationship": "independent disjoint development and validation estimates",
            "model": "normal estimates with standard errors from the design-effect calculator",
            "important_omission": "stress-cost and experiment-specific auxiliary gates are not simulated; model their full joint power separately when material",
        },
        "same_null_gate": {
            "null_process": plan.null_process,
            "same_null_for_p_value_and_false_pass": plan.same_null_for_p_value_and_false_pass,
            "expected_full_gate_false_pass_rate": plan.expected_false_pass_rate,
            "monte_carlo_standard_error": plan.expected_false_pass_mc_se,
            "source": "externally supplied by the experiment-specific registered null engine; never inferred from this normal approximation",
        },
        "protocol_amendment_2": {
            "reports_joint_power_at_true_sharpe_0.5": True,
            "reports_joint_power_at_true_sharpe_0.7": True,
            "joint_power_at_true_sharpe_0.5": joint["0.5"]["joint_power_simulated"],
            "joint_power_at_true_sharpe_0.7": joint["0.7"]["joint_power_simulated"],
            "low_power_at_true_sharpe_0.7": low_power_at_07,
            "required_failure_wording_if_validation_fails": (
                "not certified (low power)"
                if low_power_at_07
                else "validation failure; preserve the null and frozen specification"
            ),
            "registration_ready": not blockers,
            "registration_blockers": blockers,
        },
        "provenance": {
            "input_spec_sha256": _sha256_value(plan.to_dict()),
            "framework_source_sha256": _framework_sha256(),
            "relevant_code_and_input_hashes": plan.input_hashes,
        },
        "workflow_instruction": "Register this disclosure hash with the plan before calculating strategy returns. This tool does not edit research/preregistrations.jsonl.",
    }
    body["sha256"] = _sha256_value(body)
    return body


def verify_disclosure(disclosure: dict[str, Any]) -> bool:
    expected = disclosure.get("sha256")
    body = {key: value for key, value in disclosure.items() if key != "sha256"}
    return isinstance(expected, str) and expected == _sha256_value(body)


def render_markdown(disclosure: dict[str, Any]) -> str:
    """Render the compact section intended for a research PLAN."""

    if not verify_disclosure(disclosure):
        raise ValueError("power disclosure hash is missing or invalid")
    batch = disclosure["batch"]
    protocol = disclosure["protocol_amendment_2"]
    same_null = disclosure["same_null_gate"]
    lines = [
        f"## Ex-ante power disclosure — {disclosure['experiment_id']}",
        "",
        f"Status: **{disclosure['status']}**. This artifact is not automatically registered.",
        f"Calculated before strategy returns: **{disclosure['power_was_calculated_before_returns']}**.",
        f"Batch: {batch['registered_candidate_count']} registered candidate(s); family alpha "
        f"{batch['family_alpha']:.4g}; Bonferroni alpha {batch['bonferroni_alpha_per_candidate']:.4g} per candidate.",
        "",
        "| Stage | Raw observations | Effective observations | Autocorrelation design effect | Cross-sectional correlation | Sharpe SE | MDE Sharpe |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key, label in (("development", "Development"), ("validation", "Validation")):
        stage = disclosure[key]
        lines.append(
            f"| {label} | {stage['raw_observations']} | {stage['effective_observations']:.2f} | "
            f"{stage['autocorrelation_adjustment']['design_effect']:.3f} | "
            f"{stage['cross_sectional_adjustment']['average_pairwise_correlation']:.3f} | "
            f"{stage['expected_standard_error']['annualized_sharpe']:.3f} | "
            f"{stage['minimum_detectable_effect']['annualized_sharpe_at_target_power']:.3f} |"
        )
    lines.extend(
        [
            "",
            "| True Sharpe | Development power | Validation power | Joint analytic power | Joint simulated power (MC SE) | Approx. development years required |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for effect in POWER_GRID:
        key = f"{effect:.1f}"
        row = disclosure["joint_development_and_validation_power"][key]
        years = disclosure["development"]["approx_calendar_years_required"][key]
        years_text = "not attainable" if years is None else f"{years:.2f}"
        lines.append(
            f"| {key} | {row['development_power_analytic']:.1%} | "
            f"{row['validation_power_analytic']:.1%} | "
            f"{row['joint_power_analytic_independent_stages']:.1%} | "
            f"{row['joint_power_simulated']:.1%} ({row['joint_power_simulation_mc_se']:.2%}) | "
            f"{years_text} |"
        )
    false_pass = same_null["expected_full_gate_false_pass_rate"]
    false_pass_text = "missing" if false_pass is None else f"{false_pass:.2%}"
    lines.extend(
        [
            "",
            f"Same registered null for p-value and P(full pass|null): **{same_null['same_null_for_p_value_and_false_pass']}**.",
            f"Null process: {same_null['null_process'] or 'MISSING'}.",
            f"Expected P(full pass|null): **{false_pass_text}** (externally supplied by the full-gate null simulation).",
            f"Joint power at true Sharpe 0.7 is below 50%: **{protocol['low_power_at_true_sharpe_0.7']}**.",
            f"Required validation-failure wording: **{protocol['required_failure_wording_if_validation_fails']}**.",
            "",
            "The joint simulation is a planning approximation for the registered Sharpe/significance gates. "
            "It assumes disjoint stages and does not grant power for unmodelled stress-cost or auxiliary guards. "
            "The experiment-specific block/cluster null remains authoritative for both its p-value and false-pass gate.",
            "",
        ]
    )
    if protocol["registration_blockers"]:
        lines.append("Registration blockers:")
        lines.append("")
        lines.extend(f"- {item}" for item in protocol["registration_blockers"])
        lines.append("")
    lines.extend(
        [
            f"Power disclosure SHA-256: `{disclosure['sha256']}`",
            f"Framework source SHA-256: `{disclosure['provenance']['framework_source_sha256']}`",
            "",
        ]
    )
    return "\n".join(lines)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        # link() publishes the fully written file only if the destination is still absent.
        # replace() would overwrite an artifact created after the caller's existence check.
        os.link(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def freeze_disclosure(
    plan: PreregistrationPowerSpec,
    json_path: str | Path,
    markdown_path: str | Path,
    *,
    require_ready: bool = True,
) -> dict[str, Any]:
    """Write new immutable-by-convention JSON/Markdown artifacts, never a registry entry.

    Existing artifacts are never overwritten.  The caller must separately hash/register the
    resulting files under the project's normal preregistration procedure.
    """

    json_target, markdown_target = Path(json_path), Path(markdown_path)
    if json_target == markdown_target:
        raise ValueError("json_path and markdown_path must differ")
    existing = [str(path) for path in (json_target, markdown_target) if path.exists()]
    if existing:
        raise FileExistsError("refusing to overwrite frozen artifact(s): " + ", ".join(existing))
    disclosure = analyze_preregistration(plan)
    if require_ready and not disclosure["protocol_amendment_2"]["registration_ready"]:
        blockers = disclosure["protocol_amendment_2"]["registration_blockers"]
        raise ValueError("power disclosure is not registration-ready: " + "; ".join(blockers))
    json_text = json.dumps(disclosure, indent=2, sort_keys=True, allow_nan=False) + "\n"
    markdown_text = render_markdown(disclosure)
    _atomic_write(json_target, json_text)
    json_inode = json_target.stat().st_ino
    try:
        _atomic_write(markdown_target, markdown_text)
    except Exception:
        # Remove only the JSON inode created by this call.  A concurrent replacement belongs to
        # another writer and must not be deleted during rollback.
        if json_target.exists() and json_target.stat().st_ino == json_inode:
            json_target.unlink()
        raise
    return disclosure
