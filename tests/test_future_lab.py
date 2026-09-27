"""Tests for research/future_lab (simulated-futures lab). Synthetic checks of every engine and
metric, plus fast checks of the real input panels and of the frozen monitoring spec if present."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.future_lab import engines as E
from research.future_lab import forward as F
from research.future_lab import ordering as O
from research.future_lab import paths as PA

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "reports" / "future_lab" / "monitoring_rule_spec.json"


def student_t(rng, df, size):
    """Unit-variance Student-t draws (no Gaussian innovations anywhere in the lab)."""
    return rng.standard_t(df, size) / np.sqrt(df / (df - 2))


def ar1(n, phi, seed):
    rng = np.random.default_rng(seed)
    e = student_t(rng, 6, n)
    x = np.empty(n)
    x[0] = e[0]
    for t in range(1, n):
        x[t] = phi * x[t - 1] + e[t]
    return x


# ---------------------------------------------------------------- block length
def test_politis_white_longer_for_dependent_series():
    iid = E.politis_white(ar1(3000, 0.0, 1))
    dep = E.politis_white(ar1(3000, 0.7, 1))
    assert iid["sb"] < 5
    assert dep["sb"] > 3 * iid["sb"]
    assert dep["cb"] > dep["sb"]  # CB length exceeds SB length by (3/2)^(1/3)
    assert dep["cb"] / dep["sb"] == pytest.approx(1.5 ** (1 / 3), rel=1e-6)


def test_panel_block_length_uses_absolute_returns():
    rng = np.random.default_rng(3)
    vol = np.exp(ar1(3000, 0.97, 4) * 0.3)  # volatility clustering, no mean dependence
    r = 0.01 * vol * student_t(rng, 6, 3000)
    b = E.panel_block_length(r[:, None])
    assert b["per_column"][0]["abs_sb"] > b["per_column"][0]["r_sb"]
    assert b["sb"] == pytest.approx(b["per_column"][0]["abs_sb"])


# ---------------------------------------------------------------- samplers
def test_stationary_indices_block_length_and_range():
    idx = E.stationary_indices(500, 2000, 400, 20.0, seed=7)
    assert idx.shape == (2000, 400) and idx.min() >= 0 and idx.max() < 500
    breaks = (idx[:, 1:] != (idx[:, :-1] + 1) % 500).mean()
    assert breaks == pytest.approx(1 / 20, rel=0.08)
    assert np.array_equal(idx, E.stationary_indices(500, 2000, 400, 20.0, seed=7))  # seeded


def test_circular_indices_contiguous_blocks_with_wrap():
    idx = E.circular_indices(100, 50, 95, 10, seed=1)
    blocks = idx.reshape(50, -1, 5)  # every 10-day block is contiguous mod n; check halves of it
    d = np.diff(idx.reshape(50, 19, 5), axis=2) % 100
    assert np.all(d == 1)
    assert blocks.shape[1] == 19


def test_fit_markov_recovers_transition_matrix():
    P = np.array([[0.97, 0.03, 0.0], [0.02, 0.95, 0.03], [0.0, 0.04, 0.96]])
    rng = np.random.default_rng(11)
    s = E.simulate_markov(P, np.array([1.0, 0.0, 0.0]), 1, 200_000, rng)[0]
    Phat = E.fit_markov(s)
    assert np.allclose(Phat, P, atol=0.01)
    assert np.allclose(E.mean_durations(Phat), 1 / (1 - np.diag(P)), rtol=0.15)


def test_regime_indices_draw_only_matching_regime_and_uniformly():
    rng = np.random.default_rng(5)
    labels = np.repeat(rng.integers(0, 3, 60), 25)  # 1500 days in runs of 25
    x = np.where(labels == 2, -0.01, 0.002) + 0.001 * student_t(rng, 6, len(labels))
    idx, s = E.regime_indices(labels, 3000, 600, 15.0, seed=9)
    assert np.all(labels[idx] == s)  # every row comes from the simulated regime
    # within-regime draws are uniform, so each regime's mean return is preserved
    for k in range(3):
        m = s == k
        assert x[idx][m].mean() == pytest.approx(x[labels == k].mean(), rel=0.03, abs=2e-5)


def test_joint_resampling_preserves_cross_correlation():
    rng = np.random.default_rng(2)
    n = 2000
    a = 0.01 * student_t(rng, 5, n)
    b = 0.8 * a + 0.006 * student_t(rng, 5, n)
    ret = np.column_stack([a, b])
    rf = np.full(n, 0.0001)
    labels = {"vol_tercile": np.repeat(np.arange(4) % 3, n // 4), "dd_state": np.repeat(np.arange(8) % 2, n // 8)}
    blocks = E.panel_block_length(ret)
    target = np.corrcoef(a, b)[0, 1]
    for m in ("stationary", "circular", "regime_vol", "regime_dd", "fhs_gjr_t"):
        sim = E.simulate_panel(m, ret, rf, np.zeros((n, 1)), labels, blocks, 400, 500, seed=4)
        R = sim["R"]
        c = np.corrcoef(R[0].ravel(), R[1].ravel())[0, 1]
        assert c == pytest.approx(target, abs=0.05), m
        assert sim["RF"].shape == (400, 500)


def test_gjr_fit_and_fhs_reproduce_variance():
    rng = np.random.default_rng(8)
    n, omega, a, g, b = 4000, 0.02, 0.04, 0.10, 0.88
    z = student_t(rng, 7, n)
    e = np.empty(n)
    h = omega / (1 - a - g / 2 - b)
    for t in range(n):
        e[t] = np.sqrt(h) * z[t]
        h = omega + (a + g * (e[t] < 0)) * e[t] ** 2 + b * h
    x = 0.01 * e + 0.0003
    fit, zs = E.fit_gjr_t(x)
    assert fit.persistence == pytest.approx(a + g / 2 + b, abs=0.04)
    assert 4 < fit.nu < 20
    assert fit.mu == pytest.approx(x.mean())
    sim, d, diag = E.fhs_simulate([fit], zs[:, None], 2000, 1000, seed=1)
    assert diag[0]["credible"]
    assert np.sqrt((((sim[0] - fit.mu)) ** 2).mean()) == pytest.approx(x.std(), rel=0.15)
    assert sim[0].mean() == pytest.approx(x.mean(), abs=3 * x.std() / np.sqrt(2000 * 1000 / 50))


# ---------------------------------------------------------------- path metrics
def test_path_metrics_on_known_path():
    R = np.array([[0.10, -0.20, 0.05, 0.0, 0.30]])
    W = PA.wealth(R)
    assert W[0, -1] == pytest.approx(1.1 * 0.8 * 1.05 * 1.0 * 1.3)
    assert PA.max_drawdown(W)[0] == pytest.approx(-0.2)
    assert PA.longest_underwater(W)[0] == 3  # days 2-4 below the 1.10 peak
    assert PA.max_drawdown(PA.wealth(np.array([[-0.1, 0.05]])))[0] == pytest.approx(-0.1)  # start counts as a peak
    assert PA.cagr(np.array([1.21]), 504)[0] == pytest.approx(0.10)
    RF = np.full_like(R, 0.0001)
    RL = PA.levered(R, RF, 2.0)
    assert np.allclose(RL, 2 * R - (RF + 0.015 / 252))
    assert np.allclose(PA.levered(R, RF, 1.0), R)
    rdd = PA.running_max_dd(W)
    assert np.all(np.diff(rdd, axis=1) <= 1e-15)


# ---------------------------------------------------------------- ordering
def test_regime_permutation_keeps_terminal_wealth_and_covers_all_days():
    dates = pd.bdate_range("2020-01-01", periods=600)
    rng = np.random.default_rng(1)
    labels = np.repeat(rng.integers(0, 3, 30), 20)
    eps = O.monthly_episodes(dates, labels)
    assert eps[0][0] == 0 and eps[-1][1] == 600
    assert all(a1 == b0 for (_, a1), (b0, _) in zip(eps[:-1], eps[1:]))
    orders = O.permuted_orders(eps, 50, seed=3)
    assert np.all(np.sort(orders, axis=1) == np.arange(600))
    r = 0.01 * student_t(rng, 5, 600)
    W = np.cumprod(1 + r[orders], axis=1)[:, -1]
    assert np.allclose(W, np.prod(1 + r), rtol=1e-12)


def test_best_window_and_removal_drop():
    x = np.zeros(300)
    x[100:120] = 0.01
    i, s = O.best_window(x, 20)
    assert i == 100 and s == pytest.approx(0.2)
    rng = np.random.default_rng(0)
    R = 0.0005 + 0.01 * student_t(rng, 5, (20, 800))
    drop, full = O.removal_drop(R, np.zeros_like(R), np.zeros_like(R), 100, "excess")
    assert np.all(drop > 0)  # removing the best window always lowers the Sharpe


# ---------------------------------------------------------------- forward design
def test_years_needed_matches_forward_power_report():
    # reports/forward_power/REPORT.md: years for 80% power, one-sided 5%, iid
    for sr, years in [(0.5, 24.7), (0.75, 11.0), (1.0, 6.2), (1.5, 2.7), (2.0, 1.5)]:
        assert F.years_needed(sr) == pytest.approx(years, abs=0.06)
    assert F.years_needed(0.0) == float("inf")
    assert F.power_at(F.years_needed(1.0), 1.0) == pytest.approx(0.80, abs=1e-6)
    assert F.assurance(3, 0.8, 1e-9) == pytest.approx(F.power_at(3, 0.8), abs=1e-6)
    assert F.years_needed(1.0, k=1.2) == pytest.approx(1.44 * F.years_needed(1.0))


def test_paired_ir_formula_matches_direct_computation():
    rng = np.random.default_rng(6)
    c = 0.0004 + 0.01 * student_t(rng, 6, 5000)
    s = 0.9 * c + 0.0002 + 0.004 * student_t(rng, 6, 5000)
    direct = (s - c).mean() / (s - c).std(ddof=1) * np.sqrt(252)
    rho = np.corrcoef(s, c)[0, 1]
    via = F.paired_ir(s.mean() * 252, c.mean() * 252, s.std(ddof=1) * np.sqrt(252), c.std(ddof=1) * np.sqrt(252), rho)
    assert via == pytest.approx(direct, rel=1e-6)


def test_posterior_normal_normal():
    m, sd = F.posterior(np.array(1.0), np.array(4.0), 0.0, 0.5, 1.0)
    assert float(sd) == pytest.approx(1 / np.sqrt(4 + 4))
    assert float(m) == pytest.approx(4.0 / 8.0)
    assert F.sceptical_sd(0.8) == pytest.approx(0.8 / F.Z_ALPHA)


def _params(bound=-0.15):
    return {"prior_sharpe_mean": 0.35, "prior_sharpe_sd": 0.45, "k_sharpe": 1.0, "prior_ir_mean": 0.15,
            "prior_ir_sd": 0.5, "k_ir": 1.0, "skeptical_sharpe_sd": 0.43, "skeptical_ir_sd": 0.2,
            "dd_boundary": [bound] * 60}


def _daily(ret, ctl, start="2027-01-01"):
    idx = pd.bdate_range(start, periods=len(ret))
    return pd.DataFrame({"ret": ret, "rf": 0.0001, "control_ret": ctl}, index=idx)


def test_evaluator_kills_on_drawdown_and_promotes_on_strong_record():
    rule = json.loads(json.dumps(F.DEFAULT_RULE))
    spec = {"candidate": "x", "control": "c", "forward_start": "2027-01-01", "parameters": _params(), "rule": rule}
    rng = np.random.default_rng(0)
    n = 1300
    ret = 0.0003 + 0.008 * student_t(rng, 6, n)
    ret[200:230] = -0.01  # a 26% slide in month 10-11
    out = F.evaluate_forward(spec, _daily(ret, ret * 0.5))
    assert out["decision"] == "KILL_DRAWDOWN"
    assert 9 <= out["looks"][-1]["months_elapsed"] <= 12
    strong = 0.002 + 0.005 * student_t(rng, 6, n)  # Sharpe ~6
    out = F.evaluate_forward(spec, _daily(strong, 0.0002 + 0.005 * student_t(rng, 6, n)))
    assert out["decision"] == "PROMOTE"
    assert out["looks"][-1]["months_elapsed"] >= 24


def test_vectorised_rule_agrees_with_mechanical_evaluator():
    rule = json.loads(json.dumps(F.DEFAULT_RULE))
    prm = _params(-0.12)
    spec = {"candidate": "x", "control": "c", "forward_start": "2027-01-01", "parameters": prm, "rule": rule}
    rng = np.random.default_rng(12)
    names = {0: "END_NO_DECISION", 1: "KILL_SHARPE", 2: "KILL_DRAWDOWN", 3: "REVERT_TO_CONTROL", 4: "PROMOTE"}
    agree = 0
    for drift in (-0.0015, 0.0, 0.0004, 0.002):
        ret = drift + 0.007 * student_t(rng, 6, 1260)
        ctl = 0.0003 + 0.007 * student_t(rng, 6, 1260)
        rf = np.full(1260, 0.0001)
        rdd = PA.running_max_dd(PA.wealth(ret[None]))[:, 20::21]
        dec = F.rule_decisions((ret - rf)[None], (ret - ctl)[None], rdd, rule, prm)
        mech = F.evaluate_forward(spec, _daily(ret, ctl))
        agree += names[int(dec["code"][0])] == mech["decision"] or (dec["code"][0] == 0 and mech["decision"] == "CONTINUE")
    assert agree >= 3  # calendar month-ends vs 21-day looks can shift a borderline look by one month


def test_dd_boundary_and_false_alarm():
    rng = np.random.default_rng(1)
    R = 0.0003 + 0.01 * student_t(rng, 6, (4000, 1260))
    rdd = PA.running_max_dd(PA.wealth(R))[:, 20::21]
    b = F.dd_boundary(rdd, 0.99)
    assert b.shape == (60,) and np.all(np.diff(b) <= 1e-12)
    fa = F.boundary_false_alarm(rdd, b)
    assert 0.01 <= fa <= 0.15  # pointwise 1% at 60 looks -> a few % family-wise


# ---------------------------------------------------------------- real inputs (read-only, fast)
def test_real_panels_align_and_long_proxy_tracks_audited_control():
    from research.future_lab.data import load_gold, load_long, load_pead, spy_state

    g, lg = load_gold(), load_long()
    ov = g.dates.intersection(lg.dates)
    a, b = g.returns["spy_gld"].loc[ov], lg.returns["spy_gld"].loc[ov]
    assert a.corr(b) > 0.999
    cagr = lambda s: (1 + s).prod() ** (252 / len(s)) - 1
    assert abs(cagr(a) - cagr(b)) < 0.005
    p = load_pead()
    assert p.returns.notna().all().all() and len(p.dates) == 973
    assert (p.turnover["pead_2x"] >= 0).all() and 8 < p.turnover["pead_2x"].mean() * 252 < 15
    # causal regime variable: vol on date t uses returns through t-1 only
    st = spy_state()
    from research.future_lab.data import etf_close
    r = etf_close("SPY").pct_change(fill_method=None)
    t = st.index[500]
    assert st.loc[t, "vol63"] == pytest.approx(r.loc[:t].iloc[-64:-1].std() * np.sqrt(252))


def test_frozen_spec_integrity_if_present():
    if not SPEC.exists():
        pytest.skip("spec not generated yet")
    spec = json.loads(SPEC.read_text())
    assert F.verify_spec(spec)
    for c in ("pead_2x", "pead_2p5", "spmo_gld"):
        cand = spec["candidates"][c]
        assert cand["role"] == "candidate"
        b = cand["parameters"]["dd_boundary"]
        assert len(b) == 60 and all(x < 0 for x in b) and np.all(np.diff(b) <= 1e-12)
        for k in ("prior_sharpe_mean", "prior_sharpe_sd", "k_sharpe", "skeptical_sharpe_sd"):
            assert np.isfinite(cand["parameters"][k]) and cand["parameters"][k] == cand["parameters"][k]
    tampered = json.loads(SPEC.read_text())
    tampered["rule"]["kill_sharpe"]["threshold"] = 0.0
    assert not F.verify_spec(tampered)
