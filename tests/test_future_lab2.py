"""Tests for research/future_lab2 (alternate-futures lab v2). Checks the world simulators against
the real input data, the SPRT engine's operating characteristics against known Wald bounds using
synthetic Normal data, and the fixed-sample power formula's self-consistency."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from research.future_lab import forward as F
from research.future_lab2 import gold_world as G
from research.future_lab2 import rule as RU
from research.future_lab2 import tsy_world as T

ROOT = Path(__file__).resolve().parents[1]
SEED = 20260924


# ---------------------------------------------------------------- tsy_world data
def test_tsy_window_history_reproduces_audit_numbers():
    """win_ex must reproduce reports/audit_tsy/e_postpub.json's window_ex mean/t exactly (same
    audit CSVs, same pre/post-publication cutoff)."""
    pl = T.pools()
    e = json.loads((ROOT / "reports" / "audit_tsy" / "e_postpub.json").read_text())
    pre, post = pl["pre"], pl["post"]
    assert len(pre) == e["pre_2003-01_2019-09"]["window_ex"]["n"]
    assert len(post) == e["post_2019-10_2026-08"]["window_ex"]["n"]
    assert pre.mean() * 1e4 == pytest.approx(e["pre_2003-01_2019-09"]["window_ex"]["mean_bp"], abs=1e-6)
    assert post.mean() * 1e4 == pytest.approx(e["post_2019-10_2026-08"]["window_ex"]["mean_bp"], abs=1e-6)
    t_pre = pre.mean() / pre.std(ddof=1) * np.sqrt(len(pre))
    t_post = post.mean() / post.std(ddof=1) * np.sqrt(len(post))
    assert t_pre == pytest.approx(e["pre_2003-01_2019-09"]["window_ex"]["t"], rel=1e-6)
    assert t_post == pytest.approx(e["post_2019-10_2026-08"]["window_ex"]["t"], rel=1e-6)


def test_tsy_spec_frozen_code_unedited():
    """The candidate's frozen code hashes (in the spec this lab must not edit) still match disk."""
    spec = json.loads(T.SPEC_PATH.read_text())
    core = ROOT / spec["frozen_code"]["core"]
    ev = ROOT / spec["frozen_code"]["evaluate"]
    assert hashlib.sha256(core.read_bytes()).hexdigest() == spec["frozen_code"]["core_sha256"]
    assert hashlib.sha256(ev.read_bytes()).hexdigest() == spec["frozen_code"]["evaluate_sha256"]


def test_tsy_world_means_match_design():
    pl = T.pools()
    blocks = T.block_lengths(pl)
    n_paths, horizon = 6000, 36
    for w, target in [("W0", -T.BASE_COST_PER_WINDOW), ("W1", pl["pre"].mean() - T.BASE_COST_PER_WINDOW),
                      ("W2", pl["post"].mean() - T.BASE_COST_PER_WINDOW)]:
        X = T.simulate(w, n_paths, horizon, SEED, pl, blocks)
        assert X.shape == (n_paths, horizon)
        assert X.mean() == pytest.approx(target, abs=6e-4)
    # W5 costs strictly more than W2 by the extra shock, for every path-mean
    x2 = T.simulate("W2", n_paths, horizon, SEED, pl, blocks)
    x5 = T.simulate("W5", n_paths, horizon, SEED, pl, blocks)
    assert x2.mean() - x5.mean() == pytest.approx(T.W5_EXTRA_PER_WINDOW, abs=1e-9)
    # W3 decays from ~W2's mean at month 1 to ~W0's mean by month 60+
    x3_first = T.simulate("W3", 8000, 1, SEED, pl, blocks)
    x3_late = T.simulate("W3", 8000, 90, SEED, pl, blocks)[:, 70:]
    assert x3_first.mean() == pytest.approx(pl["post"].mean() - T.BASE_COST_PER_WINDOW, abs=2e-3)
    assert x3_late.mean() == pytest.approx(-T.BASE_COST_PER_WINDOW, abs=2e-3)
    # W4 keeps the full-history net mean but inflates dispersion ~1.5x
    x_all = T.simulate("W4", n_paths, horizon, SEED, pl, blocks)
    x_base = T.simulate("W0", n_paths, horizon, SEED, pl, blocks)  # same shape pool, unscaled deviations
    assert x_all.std() > x_base.std()


def test_tsy_all_worlds_run_and_shape():
    pl = T.pools()
    blocks = T.block_lengths(pl)
    for w in T.WORLDS:
        X = T.simulate(w, 500, 24, SEED, pl, blocks)
        assert X.shape == (500, 24)
        assert np.isfinite(X).all()


# ---------------------------------------------------------------- gold_world data
def test_gold_pools_join_and_split_correctly():
    pl = G.pools()
    assert len(pl["earlier"]) + len(pl["later"]) == len(pl["all"])
    assert (pl["earlier"].index < "2020-01-01").all()
    assert (pl["later"].index >= "2020-01-01").all()
    # matches reports/momentum_gold_20260919/REPORT.md's "later_evaluation": 2020-2026-09-17
    later_active_ann = (pl["later"]["strat"] - pl["later"]["ctrl"]).mean() * 252
    assert later_active_ann == pytest.approx(0.0313, abs=0.01)


def test_gold_all_worlds_run_and_shape():
    pl = G.pools()
    blocks = G.block_lengths(pl)
    for w in G.WORLDS:
        sim = G.simulate(w, 200, 252, SEED, pl, blocks)
        assert set(sim) == {"R", "C", "RF"}
        for arr in sim.values():
            assert arr.shape == (200, 252)
            assert np.isfinite(arr).all()


def test_gold_w0_has_no_active_edge():
    pl = G.pools()
    blocks = G.block_lengths(pl)
    sim = G.simulate("W0", 8000, 63, SEED, pl, blocks)
    active = sim["R"] - sim["C"]
    assert active.mean() == pytest.approx(0.0, abs=3e-4)


def test_gold_frozen_spec_applicable():
    spec = json.loads((ROOT / "reports" / "future_lab" / "monitoring_rule_spec.json").read_text())
    assert F.verify_spec(spec)
    assert "spmo_gld" in spec["candidates"]


# ---------------------------------------------------------------- SPRT engine (synthetic Normal)
def test_sprt_type1_and_power_near_nominal():
    """Classic Wald SPRT operating characteristics: simulate iid Normal(mu, sigma^2) data directly
    (not the project's historical worlds) and check the simulated error rates are close to the
    nominal alpha/beta the boundaries were built for."""
    rng = np.random.default_rng(3)
    mu0, mu1, sigma, alpha, beta = 0.0, 1.0, 3.0, 0.05, 0.2
    n_paths, horizon = 20_000, 4000
    X0 = rng.normal(mu0, sigma, size=(n_paths, horizon))
    X1 = rng.normal(mu1, sigma, size=(n_paths, horizon))
    r0 = RU.sprt_run(X0, mu0, mu1, sigma, alpha, beta)
    r1 = RU.sprt_run(X1, mu0, mu1, sigma, alpha, beta)
    # Wald's boundaries are an approximation: because the log-likelihood-ratio walk overshoots a
    # boundary before it is detected (discrete steps, not continuous time), the ACHIEVED error
    # rates are typically somewhat below the nominal alpha/beta, not equal to them (Wald 1945).
    assert 0.0 < r0["confirm"].mean() <= alpha + 0.02
    assert 0.0 < r1["kill"].mean() <= beta + 0.02
    assert r0["undecided"].mean() < 0.01
    assert r1["undecided"].mean() < 0.01


def test_sprt_bounds_match_wald_formula():
    A, B = RU.sprt_bounds(0.05, 0.2)
    assert A == pytest.approx(np.log(0.8 / 0.05))
    assert B == pytest.approx(np.log(0.2 / 0.95))
    assert A > 0 > B


def test_sprt_summary_shapes_and_monotone_checkpoints():
    rng = np.random.default_rng(1)
    X = rng.normal(0.5, 2.0, size=(500, 120))
    res = RU.sprt_run(X, 0.0, 1.0, 2.0, 0.05, 0.2)
    summ = RU.sprt_summary(res, checkpoints=(12, 24, 36, 60, 120))
    assert set(summ["by_checkpoint"]) == {"12m", "24m", "36m", "60m", "120m"}
    cum_confirm = [summ["by_checkpoint"][f"{c}m"]["p_confirm_by"] for c in (12, 24, 36, 60, 120)]
    assert all(b - a >= -1e-9 for a, b in zip(cum_confirm, cum_confirm[1:]))  # non-decreasing


# ---------------------------------------------------------------- fixed-sample power
def test_fixed_sample_power_matches_months_needed():
    effect, sigma = 0.002, 0.013
    n = RU.fixed_sample_months_needed(effect, sigma, alpha=0.05, power=0.8)
    p = RU.fixed_sample_power(n, effect, sigma, alpha=0.05)
    assert p == pytest.approx(0.8, abs=1e-6)


def test_fixed_sample_power_monotone_in_n():
    effect, sigma = 0.0015, 0.0135
    p_low = RU.fixed_sample_power(24, effect, sigma)
    p_high = RU.fixed_sample_power(120, effect, sigma)
    assert p_high > p_low


def test_fixed_sample_months_needed_infinite_at_zero_effect():
    assert RU.fixed_sample_months_needed(0.0, 0.01) == float("inf")


# ---------------------------------------------------------------- dist_tstat_sharpe
def test_dist_tstat_sharpe_quantiles_ordered():
    rng = np.random.default_rng(7)
    X = rng.normal(0.001, 0.013, size=(4000, 120))
    d = RU.dist_tstat_sharpe(X, ann_factor=12, checkpoints=(12, 60, 120))
    for cp in ("12m", "60m", "120m"):
        t = d[cp]["tstat"]
        assert t["p05"] <= t["p50"] <= t["p95"]
    # more months -> tighter (lower-variance) t-stat distribution for a fixed true mean
    spread_12 = d["12m"]["tstat"]["p95"] - d["12m"]["tstat"]["p05"]
    spread_120 = d["120m"]["tstat"]["p95"] - d["120m"]["tstat"]["p05"]
    assert spread_120 < spread_12


def test_dist_tstat_sharpe_key_fn_days_to_months():
    rng = np.random.default_rng(9)
    X = rng.normal(0.0005, 0.01, size=(300, 2520))
    d = RU.dist_tstat_sharpe(X, 252, [252, 1260, 2520], key_fn=lambda days: f"{days // 21}m")
    assert set(d) == {"12m", "60m", "120m"}


# ---------------------------------------------------------------- frozen-rule wrapper
def test_apply_frozen_rule_runs_on_synthetic_paths():
    spec = json.loads((ROOT / "reports" / "future_lab" / "monitoring_rule_spec.json").read_text())
    params = spec["candidates"]["spmo_gld"]["parameters"]
    rule = spec["rule"]
    rng = np.random.default_rng(4)
    n, h = 300, 60 * 21
    R = rng.normal(0.0007, 0.012, size=(n, h))
    C = rng.normal(0.0005, 0.011, size=(n, h))
    RF = np.full((n, h), 0.0001)
    out = RU.apply_frozen_rule(R, C, RF, rule, params, checkpoints=(12, 24, 36, 60))
    assert set(out["operating_characteristics"]) == {"12m", "24m", "36m", "60m"}
    for cp, row in out["operating_characteristics"].items():
        total = row["kill_sharpe"] + row["kill_drawdown"] + row["revert_to_control"] + row["promote"] + row["undecided"]
        assert total == pytest.approx(1.0, abs=1e-6)
    assert 0.0 <= out["p_undecided_at_cap"] <= 1.0
