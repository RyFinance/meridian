"""Gate calibration by simulation (Workstream C1, task 2).

For every family in `families.ROWS`, simulate its development (and, where registered, validation)
gate on synthetic AR(1) return paths under three null worlds:
  (a) zero gross mean, realistic cost drag  (true annualised Sharpe = sim_params.null_offset_a, default -0.30)
  (b) zero net mean                          (true annualised Sharpe = sim_params.null_offset_b, default 0.0)
  (c) a structural drift the gate's own controls do not remove:
        - for an "absolute" gate (no control subtracted): a long-biased beta leak,
          true Sharpe = beta_leak (already expressed in Sharpe units in sim_params, i.e. beta *
          assumed-market-Sharpe of 0.75, matching reports/null_lab/REPORT.md's own convention for
          long-only timing books);
        - for an "active" gate whose null is a shift/permutation test: the null TEST's own
          reference distribution is decentred by `shift_perm_offset` (matched, where the family's
          own dev_results.json reports it, to that number -- e.g. sector_month_end's shift-null
          mean_sd=[-0.965, 0.31], fx_hedge_rebal's perm_mean_sd~[-0.27, 0.39], fx_news F1's
          perm_sharpe_mean_sd~[-4.08, 0.42] -- and otherwise to the project-wide -0.30 cost-drag
          default), while the TRUE world stays at zero. This is exactly the "null answers the wrong
          question" pathology the workstream brief calls out for sector_month_end.
and at four power points, true net Sharpe = 0.3, 0.5, 0.7, 1.0 (a real, persistent edge, no cost
drag beyond what's already in the representative vol/mean scaling).

For bootstrap/shift/permutation null legs, computing a literal nested bootstrap p-value for every
one of the ~2.4M inner+outer draws this would need is out of the 15-minute CPU budget. Instead
(documented substitution, allowed by the task brief's "approximate faithfully" clause): a reference
null distribution of Sharpe_hat is built by simulating the SAME length/vol/autocorrelation series
at the null test's assumed mean (0 for a mean-centred bootstrap; `shift_perm_offset` for a
shift/permutation null), and "p < alpha" is replaced by "Sharpe_hat exceeds that reference
distribution's (1-alpha) quantile". This is the same asymptotic idea a block-bootstrap or
permutation p-value targets, verified once with a literal nested bootstrap in
`tests/test_null_lab2.py::test_bootstrap_quantile_matches_nested_bootstrap`.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass

import numpy as np

from research.null_lab2 import sim_params as SP
from research.null_lab2.families import ROWS, GateRow
from research.null_lab2.synth import ar1_paths, sharpe_of, ann_mean_of, naive_t_of, kappa_of

SEED = 20260924
N_DRAWS = 2000
POWER_GRID = (0.3, 0.5, 0.7, 1.0)
MARKET_SR = 0.75  # representative long-run SPY-style Sharpe used for the world-(c) beta leak


def _rng(*salt) -> np.random.Generator:
    ss = np.random.SeedSequence([SEED, *[abs(hash(s)) % (2 ** 31) for s in salt]])
    return np.random.default_rng(ss)


def _null_reference_quantile(n_periods: int, periods_per_year: float, annual_vol: float, phi: float,
                              ref_mean_sr: float, alpha: float, n_draws: int, rng: np.random.Generator) -> float:
    """Reference (1-alpha) quantile of Sharpe_hat for a null test centred at ref_mean_sr."""
    paths = ar1_paths(n_periods, n_draws, periods_per_year, annual_vol, annual_vol * ref_mean_sr, phi, rng)
    sr = sharpe_of(paths, periods_per_year)
    return float(np.nanquantile(sr, 1 - alpha))


@dataclass
class StageResult:
    n_periods: int
    kappa: float
    pass_frac: float
    sharpe_leg_frac: float
    null_leg_frac: float
    stress_leg_frac: float
    mean_sharpe_hat: float
    se_pass_frac: float  # Monte-Carlo SE of the pass-fraction estimate


def _effective_threshold(row: GateRow) -> tuple[float | None, float]:
    """Returns (effective_dev_threshold, effective_dev_alpha).

    PAIRED_VS_BENCHMARK-style archetypes (pead_portfolio) gate on the *paired difference*
    exceeding zero (beats-benchmark), not on the raw Sharpe magnitude carried in
    dev_thresh_val (which we keep in families.py purely as the reported benchmark figure).
    """
    if row.archetype == "PAIRED_VS_BENCHMARK":
        return 0.0, row.dev_alpha or 0.05
    return row.dev_thresh_val, row.dev_alpha or 0.05


def _stage(row: GateRow, n_periods: int, threshold: float | None, null_type: str, alpha: float | None,
           true_sr: float, params: SP.SimParams, gate_stress: bool, n_draws: int, seed_salt: str) -> StageResult:
    rng = _rng(row.family, seed_salt, "main")
    annual_mean = true_sr * params.annual_vol
    paths = ar1_paths(n_periods, n_draws, params.periods_per_year, params.annual_vol, annual_mean, params.phi, rng)
    sr_hat = sharpe_of(paths, params.periods_per_year)
    mean_hat = ann_mean_of(paths, params.periods_per_year)

    sharpe_leg = np.ones(n_draws, dtype=bool) if threshold is None else sr_hat >= threshold

    if gate_stress:
        stress_leg = (mean_hat - params.stress_drag) > 0
    else:
        stress_leg = np.ones(n_draws, dtype=bool)

    if null_type in ("none", "reported_only") or alpha is None:
        null_leg = np.ones(n_draws, dtype=bool)
    else:
        rng_ref = _rng(row.family, seed_salt, "ref")
        if null_type == "bootstrap":
            ref_mean_sr = 0.0
        elif null_type in ("shift", "permutation"):
            ref_mean_sr = params.shift_perm_offset
        else:
            ref_mean_sr = 0.0
        q = _null_reference_quantile(n_periods, params.periods_per_year, params.annual_vol, params.phi,
                                      ref_mean_sr, alpha, n_draws, rng_ref)
        null_leg = sr_hat >= q

    passed = sharpe_leg & stress_leg & null_leg
    p = float(passed.mean())
    se = float(np.sqrt(p * (1 - p) / n_draws))
    kappa = kappa_of(sharpe_of(ar1_paths(n_periods, n_draws, params.periods_per_year, params.annual_vol, 0.0, params.phi,
                                          _rng(row.family, seed_salt, "kappa")), params.periods_per_year),
                      n_periods / params.periods_per_year)
    return StageResult(n_periods=n_periods, kappa=kappa, pass_frac=p,
                        sharpe_leg_frac=float(sharpe_leg.mean()), null_leg_frac=float(null_leg.mean()),
                        stress_leg_frac=float(stress_leg.mean()), mean_sharpe_hat=float(np.nanmean(sr_hat)),
                        se_pass_frac=se)


def _tstat_replication_stage(row: GateRow, n_periods: int, true_sr: float, params: SP.SimParams,
                              n_draws: int, seed_salt: str) -> StageResult:
    """pead_2004_2014: HAC t >= 2.0 (proxy) AND positive in both halves."""
    rng = _rng(row.family, seed_salt, "main")
    annual_mean = true_sr * params.annual_vol
    paths = ar1_paths(n_periods, n_draws, params.periods_per_year, params.annual_vol, annual_mean, params.phi, rng)
    t = naive_t_of(paths)
    half = n_periods // 2
    half1_pos = paths[:, :half].mean(axis=1) > 0
    half2_pos = paths[:, half:].mean(axis=1) > 0
    passed = (t >= 2.0) & half1_pos & half2_pos
    p = float(passed.mean())
    se = float(np.sqrt(p * (1 - p) / n_draws))
    sr_hat = sharpe_of(paths, params.periods_per_year)
    kappa = kappa_of(sharpe_of(ar1_paths(n_periods, n_draws, params.periods_per_year, params.annual_vol, 0.0, params.phi,
                                          _rng(row.family, seed_salt, "kappa")), params.periods_per_year),
                      n_periods / params.periods_per_year)
    return StageResult(n_periods=n_periods, kappa=kappa, pass_frac=p, sharpe_leg_frac=float((t >= 2.0).mean()),
                        null_leg_frac=float((half1_pos & half2_pos).mean()), stress_leg_frac=1.0,
                        mean_sharpe_hat=float(np.nanmean(sr_hat)), se_pass_frac=se)


def _dsr_stage(row: GateRow, n_periods: int, true_sr: float, params: SP.SimParams, n_draws: int,
               seed_salt: str) -> StageResult:
    """survivor_hybrid: net Sharpe>=0.75 AND 95% bootstrap-CI lower bound>0 (proxied by naive
    t>=1.96, two-sided) AND deflated-Sharpe probability >= 0.95 at N=84 trials, trial Sharpe sd=0.5
    (annual), matching the project's own convention in research/survivor_hybrid/PLAN.md."""
    from scipy.stats import skew, kurtosis, norm
    rng = _rng(row.family, seed_salt, "main")
    annual_mean = true_sr * params.annual_vol
    paths = ar1_paths(n_periods, n_draws, params.periods_per_year, params.annual_vol, annual_mean, params.phi, rng)
    sr_hat = sharpe_of(paths, params.periods_per_year)
    t = naive_t_of(paths)
    sharpe_leg = sr_hat >= 0.75
    ci_leg = t >= 1.96
    g3 = skew(paths, axis=1)
    g4 = kurtosis(paths, axis=1, fisher=False)
    T = n_periods
    n_trials = 84
    trial_sharpe_var = 0.25 / params.periods_per_year
    euler = 0.5772156649015329
    sr0 = math.sqrt(trial_sharpe_var) * ((1 - euler) * norm.ppf(1 - 1 / n_trials)
                                          + euler * norm.ppf(1 - 1 / (n_trials * math.e)))
    sr_period = paths.mean(axis=1) / paths.std(axis=1, ddof=1)
    denom = np.sqrt(np.clip(1 - g3 * sr_period + (g4 - 1) / 4 * sr_period ** 2, 1e-6, None))
    dsr = norm.cdf((sr_period - sr0) * np.sqrt(T - 1) / denom)
    dsr_leg = dsr >= 0.95
    passed = sharpe_leg & ci_leg & dsr_leg
    p = float(passed.mean())
    se = float(np.sqrt(p * (1 - p) / n_draws))
    kappa = kappa_of(sharpe_of(ar1_paths(n_periods, n_draws, params.periods_per_year, params.annual_vol, 0.0, params.phi,
                                          _rng(row.family, seed_salt, "kappa")), params.periods_per_year),
                      n_periods / params.periods_per_year)
    return StageResult(n_periods=n_periods, kappa=kappa, pass_frac=p, sharpe_leg_frac=float(sharpe_leg.mean()),
                        null_leg_frac=float(dsr_leg.mean()), stress_leg_frac=float(ci_leg.mean()),
                        mean_sharpe_hat=float(np.nanmean(sr_hat)), se_pass_frac=se)


def simulate_dev(row: GateRow, true_sr: float, n_draws: int = N_DRAWS, seed_salt: str = "dev") -> StageResult | None:
    if row.dev_years is None:
        return None
    ppy_hint = None
    params = SP.get(row.family, row.dev_kind, row.dev_null)
    n_periods = max(2, round(row.dev_years * params.periods_per_year))
    threshold, alpha = _effective_threshold(row)
    gate_stress = "stress" in (row.stress_cond or "").lower() and "none" not in (row.stress_cond or "").lower()
    if row.archetype == "TSTAT_REPLICATION":
        return _tstat_replication_stage(row, n_periods, true_sr, params, n_draws, seed_salt)
    if row.archetype == "DSR_SINGLE_STAGE":
        return _dsr_stage(row, n_periods, true_sr, params, n_draws, seed_salt)
    return _stage(row, n_periods, threshold, row.dev_null, row.dev_alpha if row.dev_null not in
                  ("none", "reported_only") else None, true_sr, params, gate_stress, n_draws, seed_salt)


def simulate_val(row: GateRow, true_sr: float, n_draws: int = N_DRAWS, seed_salt: str = "val") -> StageResult | None:
    if row.val_years is None or row.val_thresh is None:
        return None
    if row.archetype in ("TSTAT_REPLICATION", "DSR_SINGLE_STAGE", "PAIRED_VS_BENCHMARK"):
        return None  # single-stage archetypes: no separate validation window
    params = SP.get(row.family, row.dev_kind, row.val_null)
    n_periods = max(2, round(row.val_years * params.periods_per_year))
    gate_stress = True
    return _stage(row, n_periods, row.val_thresh, row.val_null, row.val_alpha, true_sr, params,
                  gate_stress, n_draws, seed_salt)


def run_all(n_draws: int = N_DRAWS) -> list[dict]:
    out = []
    worlds = {
        "a_zero_gross_cost_drag": None,   # true_sr resolved per-row below (world a)
        "b_zero_net": 0.0,
        "c_structural_drift": None,       # resolved per-row (beta leak or shift-offset test)
    }
    for row in ROWS:
        params = SP.get(row.family, row.dev_kind, row.dev_null)
        for world_name in worlds:
            if world_name == "a_zero_gross_cost_drag":
                true_sr = params.null_offset_a
                world_desc = f"gross~0, net Sharpe {true_sr:+.2f} from cost drag"
            elif world_name == "b_zero_net":
                true_sr = 0.0
                world_desc = "net Sharpe 0.00 (idealised, no cost drag)"
            else:
                if row.dev_kind.startswith("active") or row.dev_kind.startswith("absolute (hedged") or \
                        row.dev_kind.startswith("absolute (market-neutral"):
                    if row.dev_null in ("shift", "permutation"):
                        true_sr = 0.0
                        world_desc = (f"net Sharpe 0.00, but the {row.dev_null}-null reference is "
                                      f"decentred to {params.shift_perm_offset:+.2f} SR (own-data mismatch)")
                    else:
                        true_sr = params.beta_leak
                        world_desc = f"residual/uncancelled exposure leaks true Sharpe {true_sr:+.2f}"
                else:
                    true_sr = params.beta_leak
                    world_desc = (f"long-biased beta 0.3 x market SR {MARKET_SR} leaks true Sharpe "
                                  f"{true_sr:+.2f} (absolute-Sharpe gate cannot see it)")

            dev = simulate_dev(row, true_sr, n_draws=n_draws, seed_salt=world_name)
            val = simulate_val(row, true_sr, n_draws=n_draws, seed_salt=world_name)
            both = None
            if dev is not None and val is not None:
                both = dev.pass_frac * val.pass_frac  # independent dev/val draws
            out.append({
                "family": row.family, "archetype": row.archetype, "protocol": row.protocol,
                "cell": world_name, "true_sr": true_sr, "world_desc": world_desc,
                "dev_years": row.dev_years, "val_years": row.val_years,
                "P_pass_dev": None if dev is None else round(dev.pass_frac, 4),
                "P_pass_dev_se": None if dev is None else round(dev.se_pass_frac, 4),
                "kappa_dev": None if dev is None else round(dev.kappa, 3),
                "P_pass_val_given_run": None if val is None else round(val.pass_frac, 4),
                "P_pass_dev_and_val": None if both is None else round(both, 4),
            })
        for sr in POWER_GRID:
            dev = simulate_dev(row, sr, n_draws=n_draws, seed_salt=f"power_{sr}")
            val = simulate_val(row, sr, n_draws=n_draws, seed_salt=f"power_{sr}")
            both = None
            if dev is not None and val is not None:
                both = dev.pass_frac * val.pass_frac
            out.append({
                "family": row.family, "archetype": row.archetype, "protocol": row.protocol,
                "cell": f"power_true_sr_{sr}", "true_sr": sr,
                "world_desc": f"real persistent edge, true net Sharpe {sr}",
                "dev_years": row.dev_years, "val_years": row.val_years,
                "P_pass_dev": None if dev is None else round(dev.pass_frac, 4),
                "P_pass_dev_se": None if dev is None else round(dev.se_pass_frac, 4),
                "kappa_dev": None if dev is None else round(dev.kappa, 3),
                "P_pass_val_given_run": None if val is None else round(val.pass_frac, 4),
                "P_pass_dev_and_val": None if both is None else round(both, 4),
            })
    return out


if __name__ == "__main__":
    import csv
    import pathlib

    rows = run_all()
    out_path = pathlib.Path("reports/null_lab2/calibration.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {out_path}")
