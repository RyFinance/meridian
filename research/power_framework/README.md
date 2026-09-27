# Power-first research design

This package answers a narrow question before returns are calculated: **can the registered
experiment answer its own question?** It is research-only. It never edits
`research/preregistrations.jsonl`, reads a validation return, unlocks a holdout, or changes trading
code.

## Supported designs

`DesignSpec` supports the seven required categories:

- `daily_return_strategy`
- `monthly_strategy`
- `event_study`
- `long_short_portfolio`
- `cross_sectional_ranking`
- `carry_strategy`
- `multi_asset_panel`

Every analysis reports raw and effective observations, temporal design effect, average
cross-sectional correlation and effective breadth, expected standard errors, minimum detectable
effect, power for true annualized Sharpe 0.3/0.5/0.7/1.0, approximate years required, and scenarios
that add assets/events or time clusters.

The important switch is `inference_mode`:

- `portfolio_time_series`: there is one implemented portfolio return per period. Asset count is
  reported but does not multiply statistical power. This is the conservative default for daily,
  monthly, long-short, and carry strategies.
- `pooled_panel`: asset/event observations are the inferential units. Cross-sectional breadth is
  discounted by `1 + (m - 1) rho`. This defaults for event studies, cross-sectional rankings, and
  multi-asset panels, but is valid only if the estimand and null genuinely preserve that panel.

Temporal effective observations use the finite-sample mean-variance design effect

`1 + 2 * sum((1 - lag/n) * autocorrelation_at_lag)`.

Supply either an AR(1) `autocorrelation` or an explicit truncated `autocorrelations` list. These
average-correlation approximations are deliberately transparent. Cluster/bootstrap simulation is
still required for a real gate.

## Preregistration integration

Create a JSON object accepted by `PreregistrationPowerSpec`. A minimal shape is:

```json
{
  "experiment_id": "new_family_v1",
  "registered_candidate_count": 3,
  "family_alpha": 0.05,
  "calculated_before_returns": true,
  "null_process": "Paired, mean-centred 21-session circular-block null; full frozen gate evaluated in every draw.",
  "same_null_for_p_value_and_false_pass": true,
  "expected_false_pass_rate": 0.031,
  "expected_false_pass_mc_se": 0.002,
  "input_hashes": {
    "plan": "replace-with-64-lowercase-hex-characters",
    "data_manifest": "replace-with-64-lowercase-hex-characters"
  },
  "simulation_draws": 100000,
  "simulation_seed": 20260924,
  "development": {
    "label": "development",
    "category": "cross_sectional_ranking",
    "n_periods": 1260,
    "units_per_period": 400,
    "autocorrelation": 0.10,
    "cross_sectional_correlation": 0.15,
    "minimum_sharpe": 0.80
  },
  "validation": {
    "label": "locked validation",
    "category": "cross_sectional_ranking",
    "n_periods": 756,
    "units_per_period": 400,
    "autocorrelation": 0.10,
    "cross_sectional_correlation": 0.15,
    "minimum_sharpe": 0.75
  }
}
```

The placeholder hashes above intentionally fail readiness checks. Replace them with hashes of the
actual frozen plan/code/data manifest. Then run:

```bash
PYTHONPATH=. .venv/bin/python -m research.power_framework power_spec.json \
  --json-out research/new_family/POWER.json \
  --markdown-out research/new_family/POWER.md
```

The command refuses to overwrite either output. The JSON and Markdown are sidecars for the normal
preregistration workflow; their hash must still be registered before any strategy return is
calculated.

## What “joint power” means

The disclosure simulates disjoint normal development and validation estimates using the adjusted
standard errors and the registered multiplicity/Sharpe thresholds. This satisfies the standard
pre-return power disclosure at true Sharpe 0.5 and 0.7 and also reports 0.3 and 1.0. It is optimistic
when stress-cost or auxiliary guards have less than unit power; model those conditions explicitly
for the experiment when material.

The supplied `expected_false_pass_rate` is intentionally **not** derived from the analytic power
calculator. Protocol Amendment 2 requires it to come from the same experiment-specific null process
as the gating p-value, with the full gate evaluated in every null world. A missing, inconsistent, or
greater-than-5% false-pass estimate blocks registration readiness.
