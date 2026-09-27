"""Tests for the null-world lab (research/null_lab)."""
import numpy as np
import pandas as pd
import pytest

from research.null_lab import generators as G
from research.null_lab import engines as E
from research.null_lab.api import builders, composite, run_null
from research.null_lab.gates import BootstrapP, Gate


# -- generators --------------------------------------------------------------------------------------
def test_circular_shift_enforces_separation():
    x = np.arange(100.0)[:, None]
    with pytest.raises(ValueError):
        G.circular_shift(x, 5, 12)
    with pytest.raises(ValueError):
        G.circular_shift(x, 95, 12)
    y = G.circular_shift(x, 30, 12)
    assert np.array_equal(np.sort(y[:, 0]), x[:, 0])
    assert y[30, 0] == 0.0


def test_draw_offsets_range():
    rng = np.random.default_rng(0)
    o = G.draw_offsets(137, 12, 5000, rng)
    assert o.min() >= 12 and o.max() <= 125
    with pytest.raises(ValueError):
        G.draw_offsets(20, 12, 1, rng)


def test_series_shift_builder_keeps_distance_both_ways():
    real = np.r_[np.full(10, np.nan), np.arange(200.0)]      # value == source position - 10
    f = builders.shift(real, 30)
    s = f(np.random.default_rng(1), 200)
    t = np.arange(len(real))
    src = s + 10                                              # source position of every value
    d = np.abs(src - t[None, :])
    L = 200
    circ = np.minimum(d, L - d)
    assert np.isfinite(s).all()
    assert circ.min() >= 30


def test_ar1_persistence_and_matching():
    rng = np.random.default_rng(2)
    x = G.ar1_panel(4000, 3, 0.6, rng)[0]
    for j in range(3):
        assert abs(G.series_autocorr(x[:, j], 1) - 0.6) < 0.05
    phi, s = G.match_persistence(0.62, 0.05, 12)
    assert abs(s + (1 - s) * phi - 0.62) < 1e-9
    assert abs(s + (1 - s) * phi ** 12 - 0.05) < 1e-6
    assert G.match_persistence(0.62, None) == (0.62, 0.0)


def test_ma_panel_autocorrelation():
    x = G.ma_panel(20000, 1, 2, np.random.default_rng(3))[0, :, 0]
    assert abs(G.series_autocorr(x, 1) - 2 / 3) < 0.03
    assert abs(G.series_autocorr(x, 3)) < 0.03


def test_permutation_keeps_rows_and_mask():
    rng = np.random.default_rng(4)
    x = rng.standard_normal((50, 10))
    x[rng.random(x.shape) < 0.2] = np.nan
    y = G.permute_cross_section(x, rng)
    assert np.array_equal(np.isnan(x), np.isnan(y))
    for a, b in zip(x, y):
        assert np.array_equal(np.sort(a[np.isfinite(a)]), np.sort(b[np.isfinite(b)]))


def test_stationary_bootstrap_indices():
    rng = np.random.default_rng(5)
    idx = G.stationary_bootstrap(1000, 5000, 21, rng, worlds=3)
    assert idx.shape == (3, 5000) and idx.min() >= 0 and idx.max() < 1000
    breaks = (np.diff(idx, axis=1) % 1000 != 1).mean()
    assert abs(1 / breaks - 21) < 3


def test_segmented_bootstrap_stays_in_window():
    f = builders.bootstrap_paths(1000, 21, split=600)
    p = f(np.random.default_rng(6), 4) + 1                   # engines use source = index + 1
    assert p[:, :601].max() <= 600 and p[:, :601].min() >= 1
    assert p[:, 601:].min() >= 601 and p[:, 601:].max() <= 999


def test_composite_rank_rule():
    a = np.array([[[1.0, 2.0, 3.0, np.nan]]])
    b = np.array([[[3.0, 2.0, 1.0, np.nan]]])
    c = np.array([[[np.nan, 1.0, 2.0, 3.0]]])
    m = composite([a, b, c])
    assert np.isnan(m[0, 0, 3])                               # only one input available
    assert m[0, 0, 1] == pytest.approx(np.mean([2 / 3, 2 / 3, 1 / 3]))


# -- engines reproduce the project's code exactly ------------------------------------------------------
@pytest.fixture(scope="module")
def country():
    return E.CountryEngine()


def test_country_engine_matches_macro_surprise_code(country):
    rng = np.random.default_rng(7)
    real = country.real_signal()
    sigs = np.stack([G.circular_shift(real, 40, 12), G.apply_mask(G.ar1_panel(*real.shape, 0.6, rng)[0:1], real)[0]])
    out = country.run(sigs)
    for i in range(2):
        for w in ("dev", "val"):
            for c in ("base", "stress"):
                ref = country.reference(sigs[i], w, c)
                assert np.max(np.abs(ref - out[(w, c)][i])) < 1e-10


def test_country_engine_refuses_real_signal_in_validation(country):
    real = country.real_signal()
    with pytest.raises(RuntimeError):
        country.run(real[None])


def test_country_bootstrap_path_is_new_but_consistent(country):
    rng = np.random.default_rng(8)
    pb = builders.bootstrap_paths(len(country.cal), 21, split=country.windows["dev"].end_day)
    O, C = country.prices(pb(rng, 2), 2)
    assert np.isfinite(O).all() and np.isfinite(C).all() and (C > 0).all()
    assert not np.allclose(C[0], country.C)
    assert np.allclose(C[:, 0], country.C[0])


def test_stock_engine_matches_options_signals_code():
    se = E.StockEngine()
    real = se.price_signal("mom_12_1")
    sig = G.circular_shift(real, 200, 64)[None]
    out = se.run(sig)
    for w in ("dev", "val"):
        for c in ("base", "stress"):
            assert np.max(np.abs(se.reference(sig[0], w, c) - out[(w, c)][0])) < 1e-10


def test_quintile_edges_match_pandas_qcut():
    rng = np.random.default_rng(9)
    for n in range(25, 101, 7):
        s = rng.standard_normal(n)
        w = E.StockEngine.quintile_weights(np.r_[s, np.full(100 - n, np.nan)][None, None, :])[0, 0, :n]
        q = pd.qcut(pd.Series(s).rank(method="first"), 5, labels=False).to_numpy()
        assert np.array_equal(w > 0, q == 4) and np.array_equal(w < 0, q == 0)


@pytest.mark.parametrize("book,kind,m", [("spy_ief", "r2", 252), ("spy_cash", "tsmom", 315)])
def test_timing_engines_match_project_code(book, kind, m):
    te = E.TimingEngine(book)
    f = builders.shift(te.real_signal(kind), m)
    sig = f(np.random.default_rng(10), 2)
    out = te.run(sig)
    for i in range(2):
        for w in ("dev", "val"):
            for c in ("base", "stress"):
                assert np.max(np.abs(te.reference(sig[i], w, c) - out[(w, c)][i])) < 1e-10


# -- gates --------------------------------------------------------------------------------------------
def test_bootstrap_p_equals_project_function():
    from research.macro_surprise.evaluate import block_bootstrap_p as macro_p
    from research.options_signals.evaluate import block_bootstrap_p as opt_p
    rng = np.random.default_rng(11)
    x = rng.standard_normal((3, 1434)) * 0.01 + 0.0006
    assert np.allclose(BootstrapP(1434, 21, 5000, 20260923).pvalues(x), [macro_p(r) for r in x])
    y = rng.standard_normal((3, 349)) * 0.01 + 0.001
    assert np.allclose(BootstrapP(349, 8, 5000, 20260918).pvalues(y), [opt_p(r) for r in y])


def test_gate_logic():
    rng = np.random.default_rng(12)
    n = 252 * 5
    good = rng.standard_normal(n) * 0.01 + 0.01 * 2.0 / np.sqrt(252)     # Sharpe ~ 2
    bad = rng.standard_normal(n) * 0.01 - 0.01 / np.sqrt(252)            # Sharpe ~ -1
    out = {(w, c): np.stack([good, bad, good]) for w in ("dev", "val") for c in ("base", "stress")}
    out[("dev", "stress")] = np.stack([good, bad, good - 0.01])            # third fails stress in dev
    r = Gate(k=4).evaluate(out, 252)
    assert r["pass_dev"].tolist() == [True, False, False]
    assert r["pass_both"][0] and not r["pass_both"][1] and not r["pass_both"][2]
    assert r["p_val"][0] < 0.0125 and np.isnan(r["p_val"][1])


def test_run_null_reproducible_and_complete():
    te = E.TimingEngine("spy_ief")
    f = builders.shift(te.real_signal("r2"), 252)
    a = run_null(f, te, Gate(k=4, seed=20260918), n_worlds=20, seed=3, chunk=10, horizons=(1, 5))
    b = run_null(f, te, Gate(k=4, seed=20260918), n_worlds=20, seed=3, chunk=10, horizons=(1, 5))
    assert np.array_equal(a["arrays"]["sr_dev"], b["arrays"]["sr_dev"])
    assert a["arrays"]["sr_dev"].shape == (20, 4)
    for key in ("candidate", "family", "pooled_independent", "horizons"):
        assert key in a
    assert 0 <= a["candidate"]["p_pass_dev"]["p"] <= 1


# -- record ---------------------------------------------------------------------------------------------
def test_record_matches_files():
    from research.null_lab import record as rc
    assert rc.verify() == []
    t = rc.table()
    assert t.dev_pass.sum() == 9
    core = t[t.dev_pass & t.val_sr.notna()].set_index("id")
    expected = {"I4": (0.55, -0.09), "R2": (0.74, 0.63), "R3": (0.82, 0.45), "E1": (0.66, 0.38),
                "E2": (0.57, 0.44), "N3": (0.77, 0.49), "N4": (0.51, 0.51), "MA": (0.57, -0.02),
                "CR3": (1.24, 0.40)}
    for k, (d, v) in expected.items():
        assert abs(core.loc[k, "dev_sr"] - d) <= 0.0051 and abs(core.loc[k, "val_sr"] - v) <= 0.0051


def test_record_tests_run():
    from research.null_lab import record as rc
    d = rc.dev_stage(1.0)["summary"]
    assert 0 <= d["p_value_obs_sr_ge_gate"] <= 1 and d["n_candidates"] == len(rc.table())
    v = rc.val_stage(1.0)
    assert v["n"] == 9 and 0 < v["stouffer_p"] < 1
    s = rc.shrinkage(1.0, extended=False, n_boot=200, gross=True)
    assert np.isfinite(s["slope"])
