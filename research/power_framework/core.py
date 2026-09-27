"""Analytic, conservative first-pass power calculations for research designs.

The central choice is the estimand.  A portfolio time-series has one portfolio return per
period, even if five hundred securities were used to construct it.  A pooled panel/event
estimand can obtain additional information from cross-sectional units, discounted by their
average correlation.  Making that choice explicit prevents raw rows from being mistaken for
independent observations.

The calculations are planning approximations, not evidence and not a replacement for the
registered same-null simulation of the experiment's full gate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from math import isfinite, sqrt
from typing import Any, Literal

from scipy.stats import norm

POWER_GRID = (0.3, 0.5, 0.7, 1.0)

SUPPORTED_CATEGORIES = (
    "daily_return_strategy",
    "monthly_strategy",
    "event_study",
    "long_short_portfolio",
    "cross_sectional_ranking",
    "carry_strategy",
    "multi_asset_panel",
)

InferenceMode = Literal["portfolio_time_series", "pooled_panel"]

_DEFAULTS: dict[str, tuple[float, InferenceMode]] = {
    "daily_return_strategy": (252.0, "portfolio_time_series"),
    "monthly_strategy": (12.0, "portfolio_time_series"),
    # Event dates default to trading-day clusters.  Override observations_per_year when the
    # analysis unit is an event sequence rather than a calendar-day cluster.
    "event_study": (252.0, "pooled_panel"),
    "long_short_portfolio": (252.0, "portfolio_time_series"),
    "cross_sectional_ranking": (252.0, "pooled_panel"),
    "carry_strategy": (12.0, "portfolio_time_series"),
    "multi_asset_panel": (252.0, "pooled_panel"),
}


@dataclass(frozen=True)
class DesignSpec:
    """Frozen inputs for one development or validation stage.

    ``n_periods`` is the number of time/event clusters. ``units_per_period`` is the average
    number of assets/events observed in one cluster.  For a simple daily strategy these are
    trading days and one; for a daily stock panel they might be trading days and stocks.

    ``portfolio_time_series`` estimates the Sharpe of one implemented portfolio return per
    period and therefore does not multiply inference by the asset count. ``pooled_panel``
    estimates a pooled asset/event effect and uses correlation-adjusted cross-sectional
    breadth.  The latter is appropriate only when the sampling unit and null preserve the
    panel structure.
    """

    category: str
    n_periods: int
    observations_per_year: float | None = None
    units_per_period: float = 1.0
    autocorrelation: float = 0.0
    autocorrelations: tuple[float, ...] | None = None
    cross_sectional_correlation: float = 0.0
    inference_mode: InferenceMode | None = None
    candidate_count: int = 1
    family_alpha: float = 0.05
    target_power: float = 0.80
    sides: int = 1
    minimum_sharpe: float = 0.0
    label: str = ""

    def __post_init__(self) -> None:
        if self.category not in SUPPORTED_CATEGORIES:
            raise ValueError(
                f"unsupported category {self.category!r}; expected one of {SUPPORTED_CATEGORIES}"
            )
        if not isinstance(self.n_periods, int) or isinstance(self.n_periods, bool) or self.n_periods < 2:
            raise ValueError("n_periods must be an integer >= 2")
        default_frequency, default_mode = _DEFAULTS[self.category]
        if self.observations_per_year is None:
            object.__setattr__(self, "observations_per_year", default_frequency)
        if self.inference_mode is None:
            object.__setattr__(self, "inference_mode", default_mode)
        if self.inference_mode not in ("portfolio_time_series", "pooled_panel"):
            raise ValueError("inference_mode must be portfolio_time_series or pooled_panel")
        if self.observations_per_year is None or not isfinite(self.observations_per_year):
            raise ValueError("observations_per_year must be finite")
        if self.observations_per_year <= 0:
            raise ValueError("observations_per_year must be > 0")
        if not isfinite(self.units_per_period) or self.units_per_period < 1:
            raise ValueError("units_per_period must be finite and >= 1")
        if not isfinite(self.autocorrelation) or not -1 < self.autocorrelation < 1:
            raise ValueError("autocorrelation must lie strictly between -1 and 1")
        if self.autocorrelations is not None:
            acf = tuple(float(x) for x in self.autocorrelations)
            if not acf:
                raise ValueError("autocorrelations cannot be empty")
            if any(not isfinite(x) or not -1 < x < 1 for x in acf):
                raise ValueError("each supplied autocorrelation must lie strictly between -1 and 1")
            if self.autocorrelation != 0:
                raise ValueError("supply autocorrelation or autocorrelations, not both")
            object.__setattr__(self, "autocorrelations", acf)
        rho_x = self.cross_sectional_correlation
        if not isfinite(rho_x) or rho_x > 1:
            raise ValueError("cross_sectional_correlation must be finite and <= 1")
        if self.units_per_period > 1:
            lower = -1.0 / (self.units_per_period - 1.0)
            if rho_x <= lower:
                raise ValueError(
                    "cross_sectional_correlation violates the equicorrelation positive-definite bound"
                )
        elif rho_x != 0:
            raise ValueError("cross_sectional_correlation must be zero when units_per_period is one")
        if not isinstance(self.candidate_count, int) or isinstance(self.candidate_count, bool):
            raise ValueError("candidate_count must be an integer")
        if self.candidate_count < 1:
            raise ValueError("candidate_count must be >= 1")
        if not 0 < self.family_alpha < 1:
            raise ValueError("family_alpha must lie in (0, 1)")
        if not 0.5 < self.target_power < 1:
            raise ValueError("target_power must lie in (0.5, 1)")
        if self.sides not in (1, 2):
            raise ValueError("sides must be 1 or 2")
        if not isfinite(self.minimum_sharpe) or self.minimum_sharpe < 0:
            raise ValueError("minimum_sharpe must be finite and >= 0")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DesignSpec":
        body = dict(value)
        if body.get("autocorrelations") is not None:
            body["autocorrelations"] = tuple(body["autocorrelations"])
        return cls(**body)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _finite_ar1_design_effect(n: int, rho: float) -> float:
    """Finite-sample variance inflation for the sample mean under an AR(1) ACF."""

    if n <= 1 or rho == 0:
        return 1.0
    # 1 + 2 sum_{k=1}^{n-1} (1-k/n) rho^k.  Closed-form geometric sums avoid
    # allocating an array for very long daily histories.
    sum_r = rho * (1.0 - rho ** (n - 1)) / (1.0 - rho)
    sum_kr = rho * (1.0 - n * rho ** (n - 1) + (n - 1) * rho**n) / (1.0 - rho) ** 2
    out = 1.0 + 2.0 * (sum_r - sum_kr / n)
    if out <= 0 or not isfinite(out):
        raise ValueError("autocorrelation inputs imply a non-positive serial design effect")
    return out


def _truncated_acf_design_effect(n: int, autocorrelations: tuple[float, ...]) -> float:
    out = 1.0
    for lag, rho in enumerate(autocorrelations[: n - 1], start=1):
        out += 2.0 * (1.0 - lag / n) * rho
    if out <= 0 or not isfinite(out):
        raise ValueError("autocorrelations imply a non-positive serial design effect")
    return out


def serial_design_effect(spec: DesignSpec, *, asymptotic: bool = False) -> float:
    """Return variance inflation of the mean caused by temporal dependence."""

    if spec.autocorrelations is not None:
        if asymptotic:
            out = 1.0 + 2.0 * sum(spec.autocorrelations)
            if out <= 0:
                raise ValueError("autocorrelations imply a non-positive asymptotic design effect")
            return out
        return _truncated_acf_design_effect(spec.n_periods, spec.autocorrelations)
    if asymptotic:
        return (1.0 + spec.autocorrelation) / (1.0 - spec.autocorrelation)
    return _finite_ar1_design_effect(spec.n_periods, spec.autocorrelation)


def cross_sectional_design_effect(units: float, rho: float) -> float:
    """Equicorrelation design effect: 1 + (m - 1) rho."""

    out = 1.0 + (units - 1.0) * rho
    if out <= 0 or not isfinite(out):
        raise ValueError("cross-sectional inputs imply a non-positive design effect")
    return out


def _critical_value(spec: DesignSpec) -> float:
    per_test_alpha = spec.family_alpha / spec.candidate_count
    tail_alpha = per_test_alpha if spec.sides == 1 else per_test_alpha / 2.0
    return float(norm.ppf(1.0 - tail_alpha))


def _power(effect: float, se: float, threshold: float) -> float:
    # A quant_v7 pass is directional: even for a two-sided p-value the estimated Sharpe must
    # clear the positive registered gate.  The lower rejection tail cannot promote a candidate.
    return float(norm.sf((threshold - effect) / se))


def _information_required(spec: DesignSpec, effect: float) -> float | None:
    """Approximate independent information-years needed for target power.

    The estimate distribution is N(theta, 1/I).  A pass requires both the multiplicity-adjusted
    significance threshold z/sqrt(I) and ``minimum_sharpe``.  A true effect at or below a fixed
    positive Sharpe gate may never achieve 80% power; returning ``None`` makes that visible.
    """

    if effect <= 0:
        return None
    critical = _critical_value(spec)
    z_power = float(norm.ppf(spec.target_power))
    gate = spec.minimum_sharpe
    significance_solution = ((critical + z_power) / effect) ** 2
    if gate == 0:
        return significance_solution
    crossover = (critical / gate) ** 2
    if significance_solution <= crossover:
        return significance_solution
    if effect <= gate:
        return None
    fixed_gate_solution = (z_power / (effect - gate)) ** 2
    return max(crossover, fixed_gate_solution)


def _as_number(value: float) -> int | float:
    rounded = round(value)
    return int(rounded) if abs(value - rounded) < 1e-12 else float(value)


def _base_analysis(spec: DesignSpec) -> dict[str, Any]:
    serial_deff = serial_design_effect(spec)
    cross_deff = cross_sectional_design_effect(
        spec.units_per_period, spec.cross_sectional_correlation
    )
    effective_periods = spec.n_periods / serial_deff
    effective_units = spec.units_per_period / cross_deff
    pooled_effective = effective_periods * effective_units
    if spec.inference_mode == "portfolio_time_series":
        effective_observations = effective_periods
        breadth_used = 1.0
    else:
        effective_observations = pooled_effective
        breadth_used = effective_units

    information_years = effective_observations / float(spec.observations_per_year)
    se_standardized = 1.0 / sqrt(effective_observations)
    se_sharpe = 1.0 / sqrt(information_years)
    critical = _critical_value(spec)
    significance_cutoff = critical * se_sharpe
    decision_threshold = max(spec.minimum_sharpe, significance_cutoff)
    mde = decision_threshold + float(norm.ppf(spec.target_power)) * se_sharpe
    power = {
        f"{effect:.1f}": _power(effect, se_sharpe, decision_threshold)
        for effect in POWER_GRID
    }

    asymptotic_serial_deff = serial_design_effect(spec, asymptotic=True)
    information_years_per_calendar_year = breadth_used / asymptotic_serial_deff
    years_required: dict[str, float | None] = {}
    for effect in POWER_GRID:
        needed = _information_required(spec, effect)
        years_required[f"{effect:.1f}"] = (
            None if needed is None else float(needed / information_years_per_calendar_year)
        )

    analytic_null_pass = _power(0.0, se_sharpe, decision_threshold)
    raw_observations = spec.n_periods * spec.units_per_period
    return {
        "label": spec.label,
        "category": spec.category,
        "inference_mode": spec.inference_mode,
        "analysis_unit": {
            "time_or_event_clusters": spec.n_periods,
            "average_assets_or_events_per_cluster": spec.units_per_period,
            "observations_per_year": spec.observations_per_year,
            "calendar_years": spec.n_periods / float(spec.observations_per_year),
        },
        "raw_observations": _as_number(raw_observations),
        "effective_observations": float(effective_observations),
        "effective_time_observations": float(effective_periods),
        "pooled_effective_observations": float(pooled_effective),
        "information_years": float(information_years),
        "autocorrelation_adjustment": {
            "method": "truncated_supplied_acf" if spec.autocorrelations is not None else "finite_ar1",
            "lag1_or_ar1": (
                spec.autocorrelations[0] if spec.autocorrelations is not None else spec.autocorrelation
            ),
            "supplied_acf": list(spec.autocorrelations) if spec.autocorrelations is not None else None,
            "design_effect": float(serial_deff),
            "asymptotic_design_effect_for_year_projection": float(asymptotic_serial_deff),
            "standard_error_inflation": sqrt(serial_deff),
            "effective_time_observations": float(effective_periods),
        },
        "cross_sectional_adjustment": {
            "average_pairwise_correlation": spec.cross_sectional_correlation,
            "design_effect": float(cross_deff),
            "effective_units_per_period": float(effective_units),
            "used_in_primary_power": spec.inference_mode == "pooled_panel",
        },
        "testing": {
            "family_alpha": spec.family_alpha,
            "registered_candidate_count": spec.candidate_count,
            "bonferroni_alpha_per_candidate": spec.family_alpha / spec.candidate_count,
            "sides": spec.sides,
            "critical_value": critical,
            "minimum_registered_sharpe": spec.minimum_sharpe,
            "significance_cutoff_sharpe": float(significance_cutoff),
            "decision_threshold_sharpe": float(decision_threshold),
            "analytic_null_pass_probability": float(analytic_null_pass),
            "target_power": spec.target_power,
        },
        "expected_standard_error": {
            "standardized_observation_effect": float(se_standardized),
            "annualized_sharpe": float(se_sharpe),
        },
        "minimum_detectable_effect": {
            "annualized_sharpe_at_target_power": float(mde),
            "standardized_observation_effect_at_target_power": float(
                mde / sqrt(float(spec.observations_per_year))
            ),
        },
        "power_for_true_sharpe": power,
        "approx_calendar_years_required": years_required,
        "projection_information_years_per_calendar_year": float(
            information_years_per_calendar_year
        ),
    }


def _scenario_summary(spec: DesignSpec) -> dict[str, Any]:
    out = _base_analysis(spec)
    return {
        "n_periods": spec.n_periods,
        "units_per_period": spec.units_per_period,
        "raw_observations": out["raw_observations"],
        "effective_observations": out["effective_observations"],
        "information_years": out["information_years"],
        "sharpe_standard_error": out["expected_standard_error"]["annualized_sharpe"],
        "minimum_detectable_sharpe": out["minimum_detectable_effect"][
            "annualized_sharpe_at_target_power"
        ],
        "power_true_sharpe_0.5": out["power_for_true_sharpe"]["0.5"],
        "power_true_sharpe_0.7": out["power_for_true_sharpe"]["0.7"],
    }


def analyze_design(spec: DesignSpec, *, include_sensitivity: bool = True) -> dict[str, Any]:
    """Return every required planning output for one design stage.

    Sensitivity rows show the separate effects of adding concurrent assets/events and adding
    time/event clusters.  In ``portfolio_time_series`` mode, concurrent units do not increase
    primary power; this is a safeguard, not a missing feature.
    """

    result = _base_analysis(spec)
    result["spec"] = spec.to_dict()
    if not include_sensitivity:
        return result

    unit_rows = []
    for multiplier in (1, 2, 5):
        units = spec.units_per_period * multiplier
        rho = spec.cross_sectional_correlation
        # A negative equicorrelation that is legal at m may be illegal at 2m or 5m.  The
        # conservative sensitivity floors it at zero rather than inventing a non-PSD matrix.
        if units > 1 and rho <= -1.0 / (units - 1.0):
            rho = 0.0
        scenario = replace(spec, units_per_period=units, cross_sectional_correlation=rho)
        row = {"multiplier": multiplier, **_scenario_summary(scenario)}
        if rho != spec.cross_sectional_correlation:
            row["correlation_note"] = "negative correlation reset to zero to keep equicorrelation PSD"
        unit_rows.append(row)

    period_rows = []
    for multiplier in (1, 2, 5):
        scenario = replace(spec, n_periods=spec.n_periods * multiplier)
        period_rows.append({"multiplier": multiplier, **_scenario_summary(scenario)})

    result["effect_of_adding_assets_or_events"] = {
        "concurrent_unit_interpretation": (
            "Primary Sharpe power is unchanged when assets/events are merely ingredients of one "
            "portfolio return per period. Breadth may improve the true Sharpe, but that is a separate "
            "economic assumption."
            if spec.inference_mode == "portfolio_time_series"
            else "Concurrent assets/events add information only after the equicorrelation design-effect discount."
        ),
        "concurrent_units_per_period": unit_rows,
        "additional_time_or_event_clusters": period_rows,
    }
    result["limitations"] = [
        "Normal-theory planning approximation; use the experiment's frozen block/cluster null for its gate.",
        "Average AR(1)/ACF and equicorrelation summarize dependence and can miss common shocks, overlap, and fat tails.",
        "Cross-sectional breadth is inferential only for a pooled panel/event estimand; portfolio Sharpe has one return per period.",
        "The analytic null-pass probability is diagnostic only and cannot replace P(full pass|null) from the same registered null used for the p-value.",
    ]
    return result
