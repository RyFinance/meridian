"""Tests for research/trial_accounting: the M_eff estimators and the
preregistrations.jsonl parser. Read-only: these tests do not touch any
strategy evaluate.py and do not compute new strategy performance.
"""
import numpy as np
import pandas as pd

from research.trial_accounting import data_sources as ds
from research.trial_accounting import meff


def test_meff_independent_series_equals_m():
    """M independent (uncorrelated) series should give M_eff ~= M under all
    three estimators."""
    rng = np.random.default_rng(20260924)
    n_months, m = 200, 5
    idx = [f"2010-{i:02d}" if i <= 12 else f"2011-{i-12:02d}" for i in range(1, n_months + 1)]
    data = {f"s{i}": rng.normal(0, 1, n_months) for i in range(m)}
    df = pd.DataFrame(data, index=idx[:n_months])
    result = meff.all_meff(df, min_overlap=6)
    assert result["m"] == m
    for method in ("cheverud", "nyholt", "li_ji"):
        assert result[method] >= m - 1.0, f"{method} collapsed independent series too much: {result[method]}"
        assert result[method] <= m


def test_meff_perfectly_correlated_series_collapses_to_one():
    """M perfect copies of the same series is exactly one effective test."""
    rng = np.random.default_rng(1)
    n_months = 100
    base = rng.normal(0, 1, n_months)
    idx = [str(i) for i in range(n_months)]
    df = pd.DataFrame({f"s{i}": base for i in range(4)}, index=idx)
    result = meff.all_meff(df, min_overlap=6)
    assert result["m"] == 4
    for method in ("cheverud", "nyholt", "li_ji"):
        assert abs(result[method] - 1.0) < 1e-6, f"{method} did not collapse perfectly correlated series: {result[method]}"


def test_meff_bounds_are_respected_on_mixed_correlation():
    """A mix of correlated and independent series should land strictly
    between 1 and M for every estimator (sanity/no-crash check on a
    realistic, partially-correlated panel)."""
    rng = np.random.default_rng(7)
    n = 150
    common = rng.normal(0, 1, n)
    idx = [str(i) for i in range(n)]
    cols = {}
    for i in range(3):
        cols[f"corr{i}"] = 0.8 * common + 0.2 * rng.normal(0, 1, n)
    for i in range(3):
        cols[f"indep{i}"] = rng.normal(0, 1, n)
    df = pd.DataFrame(cols, index=idx)
    result = meff.all_meff(df, min_overlap=6)
    for method in ("cheverud", "nyholt", "li_ji"):
        assert 1.0 <= result[method] <= result["m"]


def test_meff_handles_nonoverlapping_series_without_crashing():
    """Two series with disjoint date ranges (e.g. a dev window and a much
    later validation window) must not produce NaNs or crash the eigenvalue
    decomposition; they should be treated as uncorrelated (2 low-overlap
    pairs flagged, not silently dropped)."""
    early = pd.Series(np.random.default_rng(2).normal(0, 1, 12), index=[f"2003-{m:02d}" for m in range(1, 13)])
    late = pd.Series(np.random.default_rng(3).normal(0, 1, 12), index=[f"2020-{m:02d}" for m in range(1, 13)])
    df = pd.concat([early.rename("dev"), late.rename("val")], axis=1)
    eigs, corr, diag = meff.eigenvalues_of_correlation(df, min_overlap=6)
    assert diag["n_low_overlap_pairs"] == 1
    assert np.isclose(corr.loc["dev", "val"], 0.0)
    assert len(eigs) == 2
    assert np.isclose(eigs.sum(), 2.0, atol=1e-6)


def test_load_preregistrations_sorted_and_parses_both_timestamp_formats():
    """research/preregistrations.jsonl mixes two timestamp formats
    ('...-0700' and '...-07:00' with microseconds); both must parse and the
    result must come back in chronological order for shots-before-result
    comparisons to be meaningful."""
    preregs = ds.load_preregistrations()
    assert len(preregs) >= 60
    times = [r["registered_at_utc"] for r in preregs]
    assert times == sorted(times)
    # first registration in the project per its own text
    assert preregs[0]["file"] == "research/PREREGISTRATION_pead_2004_2014.md"
    for r in preregs:
        assert r["registered_at_utc"].tzinfo is not None


def test_dir_guess_matches_registered_trials_family_directory():
    """Sanity-check the family-directory heuristic used to line up
    preregistrations.jsonl entries with families.csv rows, against a couple
    of known cases (a nested PLAN.md and a top-level protocol file)."""
    assert ds._dir_of("research/options_signals/PLAN.md") == "options_signals"
    assert ds._dir_of("research/multiasset/PLAN_CRYPTO.md") == "multiasset"
    assert ds._dir_of("reports/future_lab/monitoring_rule_spec.json") == "future_lab"
