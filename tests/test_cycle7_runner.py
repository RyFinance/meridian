"""Cycle-7 runner tests. SYNTHETIC DATA ONLY; every ledger / repo root is a temp path (pytest-only overrides)."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import shutil

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from research.cycle6.engine import component, controls, panel, portfolio, styles
from research.cycle7.runner import common, evaluate, pool, run_sample
from research.cycle7.runner import sample as smp
from research.cycle7.runner.common import GuardError


# ------------------------------------------------------------------------------------------------ fixtures
def synth_daily(cols, years=12, seed=0, drift=None, start="2000-01-03"):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=int(years * 261))
    n = len(cols)
    vols = np.linspace(0.06, 0.20, n) / math.sqrt(261)
    mu = np.zeros(n) if drift is None else np.asarray(drift) / 261
    x = mu + rng.standard_normal((len(idx), n)) * vols
    df = pd.DataFrame(x, index=idx, columns=cols)
    df.iloc[:300, -1] = np.nan
    return df


def to_long(df):
    out = df.stack().rename("value").reset_index()
    out.columns = ["date", "market_id", "value"]
    return out


def make_snapshot(root, daily, cls, extra=None, members=None, version="v1"):
    from research.data_snapshot import canonical
    vdir = root / "store" / "versions" / version
    view = vdir / "view"
    (view / "panels").mkdir(parents=True)
    to_long(daily).to_csv(view / "panels" / "daily.csv", index=False)
    ids = list(daily.columns) if members is None else members
    pd.DataFrame({"class": cls, "market_id": ids, "qa_status": "PASS"}).to_csv(view / "candidates.csv", index=False)
    for name, df in (extra or {}).items():
        to_long(df).to_csv(view / "panels" / f"{name}.csv", index=False)
    payload = {"schema_version": 1, "dataset_version": version, "records": []}
    sha = hashlib.sha256(canonical(payload)).hexdigest()
    (vdir / "manifest.json").write_text(json.dumps({"manifest_sha256": sha, "payload": payload}))
    return f"store/versions/{version}/view", sha


INF = {"B": 99, "seed": 20260927, "crash": None, "bandwidth_fraction": 0.20, "overlap": 1, "ci_B": 49,
       "ci_level": 0.90, "ci_level_crash_short": 0.95, "k": 20}
TSMOM = {
    "schema": "cycle6-component-v1", "id": "TSMOM-FI", "style": "tsmom", "class": "FI",
    "engine_sha256": common.ENGINE_SHA256, "snapshot_manifest_sha256": "0" * 64,
    "inputs": {"daily_excess": "orig/daily_FI.parquet", "signal_inputs": {},
               "series": {"eq_beta_ref": {"path": "orig/ref.parquet", "market_id": "REF"},
                          "aqr_ref": {"path": "orig/aqr.parquet", "market_id": "AQR"}}},
    "universe": {"min_assets": 3},
    "signal": {"input_lag_months": {}, "lookback_months": 12, "target_vol": 0.4},
    "weights": {"rank_vol_scale": False},
    "costs": {"bp_per_side": {"EQ": 2, "FI": 2, "FX": 3, "CM": 6}, "stress_multiplier": 3, "drift": True},
    "control": {"type": "always_long"}, "inference": INF, "post_pub_cutoff": "2011-01", "betas": ["eq_beta_ref"],
    "vol": {"com_days": 60, "annualisation": 261, "min_obs": 756, "lag_obs": 0},
    "fidelity": {"tier": "aqr_class", "reference": "aqr_ref", "scale_convention": "none",
                 "thresholds": {"n_min": 60, "rho_min": 0.65, "beta_lo": 0.7, "beta_hi": 1.3, "te_ratio_max": 0.9}},
}
XSMOM = {**copy.deepcopy(TSMOM), "id": "XSMOM-FX", "style": "xsmom", "class": "FX",
         "universe": {"min_assets": 4}, "signal": {"input_lag_months": {}, "lookback_months": 12, "skip_months": 1},
         "control": {"type": "random_rank", "n_books": 4, "seed": 20260926},
         "inference": {**INF, "crash": {"intensity_per_year": 0.2, "jump_sd": -6}, "bandwidth_fraction": 0.1},
         "fidelity": {"tier": "paper_stat", "paper": {"start": "2001-01", "end": "2010-12", "mean_ann": None,
                                                      "vol_ann": None, "sharpe_ann": 0.5}}}
XSMOM.pop("vol")
XSMOM["inputs"] = {"daily_excess": "orig/daily_FX.parquet", "signal_inputs": {},
                   "series": {"eq_beta_ref": {"path": "orig/ref.parquet", "market_id": "REF"}}}

LEDGER_HEAD = "| UTC | Kind | ID | File | SHA-256 | Note |\n|---|---|---|---|---|---|\n"


def ledger_add(path, kind, id_, file, sha, note="test"):
    with path.open("a") as f:
        f.write(f"| 2026-09-27T00:00:00Z | {kind} | {id_} | {file} | {sha} | {note} |\n")


@pytest.fixture
def env(tmp_path, monkeypatch):
    c6, c7, trial = tmp_path / "c6.md", tmp_path / "c7.md", tmp_path / "trial.csv"
    c6.write_text(LEDGER_HEAD)
    c7.write_text(LEDGER_HEAD)
    monkeypatch.setenv("CYCLE7_TEST_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("CYCLE7_TEST_CYCLE6_LEDGER", str(c6))
    monkeypatch.setenv("CYCLE7_TEST_PREREG_LEDGER", str(c7))
    monkeypatch.setenv("CYCLE7_TEST_TRIAL_LEDGER", str(trial))
    monkeypatch.delenv("QUANT_DATA_MANIFEST_SHA256", raising=False)
    ledger_add(c7, "code", "RUNNER", "research/cycle7/runner/*.py", common.runner_sha256())
    return {"root": tmp_path, "c6": c6, "c7": c7, "trial": trial}


def setup(env, params=TSMOM, cols=("FA", "FB", "FC", "FD", "FE"), drift=(0.03, 0.0, 0.02, -0.01, 0.01),
          sample_over=None, ledger_sample=True, ledger_spec=True, version="v1", sample_id="NEW", members=None):
    root = env["root"]
    drift = (list(drift) + [0.0] * len(cols))[:len(cols)]
    daily = synth_daily(list(cols), seed=7, drift=drift)
    mret = panel.monthly_returns(daily)
    ref = pd.DataFrame({"REF": mret.mean(axis=1).to_numpy()}, index=mret.index.to_timestamp(how="end").normalize())
    snap_rel, msha = make_snapshot(root, daily, params["class"], extra={"ref": ref}, members=members, version=version)
    ledger_add(env["c7"], "snapshot", f"SNAP-{version}", snap_rel, msha)
    spec = root / "specs" / f"{params['id']}.md"
    if not spec.exists():
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text("# synthetic frozen spec\n\n```json\n" + json.dumps(params, indent=1) + "\n```\n")
        ssha = hashlib.sha256(spec.read_bytes()).hexdigest()
        if ledger_spec:
            ledger_add(env["c6"], "spec", params["id"], f"specs/{params['id']}.md", ssha)
            ledger_add(env["c7"], "reference", params["id"], f"specs/{params['id']}.md", ssha)
    ssha = hashlib.sha256(spec.read_bytes()).hexdigest()
    imap = {"daily_excess": "panels/daily.csv", "series.eq_beta_ref": "panels/ref.csv"}
    if "aqr_ref" in params["inputs"]["series"]:
        imap["series.aqr_ref"] = None
    s = {"schema": "cycle7-sample-v1", "spec_id": params["id"], "spec_path": f"specs/{params['id']}.md",
         "spec_sha256": ssha, "sample_id": sample_id, "snapshot_root_rel": snap_rel,
         "snapshot_manifest_sha256": msha, "membership": "candidates.csv", "input_map": imap,
         "instrument_filter": {"class": params["class"]}, "month_window": {"start": None, "end_exclusive": None},
         "seeds_offsets": [0, 1, 2, 3, 4], "cost_mult_sensitivity": 2}
    s.update(sample_over or {})
    sp = root / "research" / "cycle7" / "samples" / f"{params['id']}__{sample_id}.md"
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text("# synthetic sample\n\n```json\n" + json.dumps(s, indent=1) + "\n```\n")
    if ledger_sample:
        ledger_add(env["c7"], "sample", f"{params['id']}__{sample_id}", str(sp.relative_to(root)),
                   hashlib.sha256(sp.read_bytes()).hexdigest())
    return sp, root / "out" / f"{params['id']}__{sample_id}", s


# ------------------------------------------------------------------------------------------------ guards
def test_refuses_unledgered_sample(env):
    sp, out, _ = setup(env, ledger_sample=False)
    with pytest.raises(GuardError, match="sample hash .* not in the cycle-7 prereg ledger"):
        run_sample.run(sp, out)
    assert not env["trial"].exists() and not (out / "metrics.json").exists()


def test_refuses_spec_hash_mismatch_and_unledgered_spec(env):
    sp, out, _ = setup(env, sample_over={"spec_sha256": "a" * 64})
    with pytest.raises(GuardError, match="spec hash mismatch"):
        run_sample.run(sp, out)
    sp2, out2, _ = setup(env, params=XSMOM, cols=("A", "B", "C", "D", "E"), ledger_spec=False, version="v2")
    with pytest.raises(GuardError, match="not in the cycle-6 prereg ledger"):
        run_sample.run(sp2, out2)
    assert not env["trial"].exists()


def test_refuses_engine_mismatch(env, tmp_path, monkeypatch):
    sp, out, _ = setup(env)
    eng = tmp_path / "engine_copy"
    shutil.copytree(common.eguards.ENGINE_DIR, eng, ignore=shutil.ignore_patterns("__pycache__"))
    assert common.dir_py_sha256(eng) == common.ENGINE_SHA256
    (eng / "vol.py").write_text((eng / "vol.py").read_text() + "\n# drift\n")
    monkeypatch.setenv("CYCLE7_TEST_ENGINE_DIR", str(eng))
    with pytest.raises(GuardError, match="engine hash mismatch"):
        run_sample.run(sp, out)
    assert not env["trial"].exists()


def test_refuses_snapshot_mismatch(env):
    sp, out, _ = setup(env, sample_over={"snapshot_manifest_sha256": "b" * 64})
    with pytest.raises(GuardError, match="snapshot manifest mismatch"):
        run_sample.run(sp, out)


def test_param_mapping_and_drift():
    s = {"snapshot_manifest_sha256": "c" * 64,
         "input_map": {"orig/daily_FI.parquet": "p/d.csv", "series.eq_beta_ref": {"path": "p/r.csv", "market_id": "X"},
                       "series.aqr_ref": None}}
    new, dropped = smp.map_params(TSMOM, s)
    assert new["inputs"]["daily_excess"] == "p/d.csv" and dropped == ["aqr_ref"]
    assert new["inputs"]["series"]["eq_beta_ref"] == {"path": "p/r.csv", "market_id": "X"}
    assert new["snapshot_manifest_sha256"] == "c" * 64 and new["signal"] == TSMOM["signal"]
    drift = copy.deepcopy(new)
    drift["signal"]["lookback_months"] = 11
    with pytest.raises(GuardError, match="parameter drift"):
        smp.assert_no_drift(TSMOM, drift, dropped)
    drift = copy.deepcopy(new)
    drift["inputs"]["series"]["eq_beta_ref"]["frequency"] = "daily"
    with pytest.raises(GuardError, match="parameter drift"):
        smp.assert_no_drift(TSMOM, drift, dropped)
    with pytest.raises(GuardError, match="does not cover"):
        smp.map_params(TSMOM, {**s, "input_map": {"daily_excess": "p/d.csv"}})
    with pytest.raises(GuardError, match="only set 'path' and 'market_id'"):
        smp.map_params(TSMOM, {**s, "input_map": {**s["input_map"], "series.eq_beta_ref": {"path": "a", "frequency": "daily"}}})
    with pytest.raises(GuardError, match="neither"):
        smp.map_params(TSMOM, {**s, "input_map": {**s["input_map"], "signal.lookback_months": "x"}})
    with pytest.raises(GuardError, match="relative path"):
        smp.map_params(TSMOM, {**s, "input_map": {**s["input_map"], "daily_excess": "../escape.csv"}})
    carry = copy.deepcopy(XSMOM)
    carry["signal"] = {"kind": "fx", "foreign_rate": "fr", "us_rate": "us_rate"}
    carry["inputs"]["series"]["us_rate"] = {"path": "orig/us.parquet", "market_id": "US"}
    with pytest.raises(GuardError, match="used by the signal"):
        smp.map_params(carry, {**s, "input_map": {"daily_excess": "a", "series.eq_beta_ref": "b", "series.us_rate": None}})


def test_end_to_end_then_refuses_duplicate(env):
    sp, out, _ = setup(env)
    m = run_sample.run(sp, out)
    for f in ("net.csv", "gross.csv", "control.csv", "active.csv", "metrics.json"):
        assert (out / f).exists(), f
    assert m["n_months"] >= 24 and m["active"]["p"]["B"] == 99 and 0 < m["active"]["p"]["p"] <= 1
    assert [x["seed"] for x in m["seeds"]] == [INF["seed"] + o for o in range(5)]
    assert m["active"]["ci_level_primary"] == 0.90 and m["active"]["ci_95"]["level"] == 0.95
    assert m["active"]["se_if"]["se_sharpe_m"] > 0 and m["run"]["dropped_diagnostic_series"] == ["aqr_ref"]
    rows = common.read_trials()
    assert [r["status"] for r in rows] == ["started", "ok"] and rows[0]["engine_sha256"] == common.ENGINE_SHA256
    with pytest.raises(GuardError, match="already exists"):
        run_sample.run(sp, env["root"] / "out" / "again")


def test_failed_run_is_logged(env):
    sp, out, s = setup(env, sample_over={"input_map": {"daily_excess": "panels/missing.csv",
                                                       "series.eq_beta_ref": "panels/ref.csv", "series.aqr_ref": None}})
    with pytest.raises(Exception):
        run_sample.run(sp, out)
    assert [r["status"] for r in common.read_trials()] == ["started", "failed"]


def test_overrides_refused_outside_pytest(monkeypatch, tmp_path):
    monkeypatch.setenv("CYCLE7_TEST_TRIAL_LEDGER", str(tmp_path / "x.csv"))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(GuardError, match="test-only"):
        common.trial_ledger_path()


# ------------------------------------------------------------------------------------------------ window / filter
def _engine(env, params=TSMOM, cols=("FA", "FB", "FC", "FD", "FE"), members=None, ids=None, version="v1"):
    sp, out, s = setup(env, params=params, cols=cols, members=members, version=version)
    ctx = smp.preflight(sp)
    data = component.load_inputs(ctx["params"], ctx["snapshot_root"], ctx["membership"])
    if ids is not None:
        data = evaluate.apply_filter(data, ids)
    return ctx["params"], component.compute_component(ctx["params"], data), s


def test_window_evaluation_always_long(env):
    params, res, s = _engine(env)
    a_full = evaluate.active_series(res, params, None, None, 2.0)
    eng = res["active"]["active_full_window"].dropna()
    pd.testing.assert_series_equal(a_full["active"], eng, check_names=False)
    a = evaluate.active_series(res, params, "2006-01", "2009-01", 2.0)
    assert str(a["active"].index.min()) == "2006-01" and str(a["active"].index.max()) == "2008-12"
    assert len(a["active"]) == 36
    net, ctl = res["net"], res["control"]
    ratio = controls.exposure_ratio(net["net_exposure"], ctl["net_exposure"])
    win = net.index[(net.index >= pd.Period("2006-01", "M")) & (net.index < pd.Period("2009-01", "M"))]
    mbar = float(np.nanmean(ratio.reindex(win)))
    assert a["mbar"] == pytest.approx(mbar)
    exp = net["ret"].reindex(win) - mbar * ctl["net"].reindex(win)
    np.testing.assert_allclose(a["active"].to_numpy(), exp.to_numpy(), atol=1e-14)
    m, frames = evaluate.window_metrics(res, params, {**s, "month_window": {"start": "2006-01", "end_exclusive": "2009-01"}},
                                        ["FA", "FB", "FC", "FD", "FE"])
    assert m["n_months"] == 36 and len(frames["net"]) == 36 and frames["net"].index.min() >= pd.Period("2006-01", "M")


def test_two_x_cost_path_matches_direct_always_long(env):
    params, res, s = _engine(env)
    a = evaluate.active_series(res, params, None, None, 2.0)
    assert a["stress_identity_max_err"] < 1e-12
    # direct: rebuild the always-long control at cost multiplier 2 with the frozen engine pieces
    sp = params["signal"]
    daily = synth_daily(["FA", "FB", "FC", "FD", "FE"], seed=7, drift=[0.03, 0.0, 0.02, -0.01, 0.01])
    mret, rnet = panel.monthly_returns(daily), panel.net_period_returns(daily)
    from research.cycle6.engine import vol as evol
    v = evol.ew_vol(daily, com_days=60, annualisation=261, min_obs=756)
    vme = panel.month_end_sample(v, mret.index)
    Wc, _, nc = styles.tsmom_weights(mret, vme, lookback_months=sp["lookback_months"], target_vol=sp["target_vol"],
                                     min_assets=3, force_long=True)
    rate = pd.Series(0.0002, index=daily.columns)
    c2 = portfolio.net_implementable(Wc, rnet, rate, nc >= 3, cost_multiplier=2.0)["ret"]
    ctl_c = res["control"]["net"] - (res["control"]["net"] - res["control"]["stress"]) / 2.0
    np.testing.assert_allclose(ctl_c.to_numpy(), c2.reindex(ctl_c.index).to_numpy(), atol=1e-12)
    b2 = res["net"]["ret_before_cost"] - 2 * res["net"]["cost"]
    ratio = controls.exposure_ratio(res["net"]["net_exposure"], res["control"]["net_exposure"])
    exp, _ = controls.matched_active(b2, c2, ratio)
    np.testing.assert_allclose(a["active_c"].to_numpy(), exp.dropna().to_numpy(), atol=1e-12)
    assert (a["active_c"] <= a["active"] + 1e-12).mean() > 0.5   # extra cost mostly lowers active


def test_two_x_cost_identity_on_known_control():
    b = pd.Series([0.01, -0.02, 0.03])
    cost = pd.Series([0.001, 0.002, 0.0005])
    ctl = pd.DataFrame({"net": b - cost, "stress": b - 3 * cost})
    np.testing.assert_allclose(ctl["net"] - evaluate.control_cost(ctl, 3.0), b - 2 * cost, atol=1e-15)


def test_rank_window_and_filter_is_mechanical(env):
    cols = ("A", "B", "C", "D", "E", "F")
    keep = ["A", "B", "C", "D", "F"]
    params, res_f, s = _engine(env, params=XSMOM, cols=cols, ids=keep)
    # same data, membership listing only `keep` -> identical engine output
    root2 = env["root"] / "second"
    root2.mkdir()
    daily = synth_daily(list(cols), seed=7, drift=[0.03, 0.0, 0.02, -0.01, 0.01, 0.0])
    mret = panel.monthly_returns(daily)
    ref = pd.DataFrame({"REF": mret.mean(axis=1).to_numpy()}, index=mret.index.to_timestamp(how="end").normalize())
    rel, _ = make_snapshot(root2, daily, "FX", extra={"ref": ref}, members=keep)
    data2 = component.load_inputs(params, root2 / rel, root2 / rel / "candidates.csv")
    res2 = component.compute_component(params, data2)
    pd.testing.assert_frame_equal(res_f["net"], res2["net"])
    pd.testing.assert_frame_equal(res_f["active"], res2["active"])
    a = evaluate.active_series(res_f, params, "2005-01", None, 2.0)
    eng = res_f["active"]["active_full_window"]
    pd.testing.assert_series_equal(a["active"], eng[eng.index >= pd.Period("2005-01", "M")].dropna(),
                                   check_names=False)
    m, _ = evaluate.window_metrics(res_f, params, {**s, "month_window": {"start": "2005-01", "end_exclusive": None}}, keep)
    assert m["crash_declared"] and m["n_months"] < 120 and m["active"]["ci_level_primary"] == 0.95
    assert "E" not in m["instruments_held_in_window"]


def test_filter_rules(env):
    sp, out, s = setup(env, params=XSMOM, cols=("A", "B", "C", "D", "E"))
    ctx = smp.preflight(sp)
    f = lambda flt: evaluate.filtered_universe(ctx["snapshot_root"], ctx["membership"], ctx["params"], flt)  # noqa
    assert f({"class": "FX", "exclude_market_ids": ["B"]}) == ["A", "C", "D", "E"]
    assert f({"class": "FX", "include_market_ids": ["E", "A"]}) == ["A", "E"]
    with pytest.raises(GuardError, match="not PASS"):
        f({"class": "FX", "include_market_ids": ["Z"]})
    with pytest.raises(GuardError, match="class"):
        f({"class": "FI"})


def test_instrument_list_hash_guard(env):
    sp, out, _ = setup(env, sample_over={"instrument_filter": {"class": "FI", "instrument_list_sha256": "d" * 64}})
    with pytest.raises(GuardError, match="instrument list hash mismatch"):
        run_sample.run(sp, out)
    assert not env["trial"].exists()


# ------------------------------------------------------------------------------------------------ pooling
def test_pooled_estimate_known():
    r = pool.pooled_estimate([0.2, 0.1], [0.1, 0.2])
    assert r["sharpe_m"] == pytest.approx((0.2 * 100 + 0.1 * 25) / 125)
    assert r["se_pool_indep_m"] == pytest.approx(1 / math.sqrt(125))


def test_stouffer_known_cases():
    assert pool.stouffer([0.03], [0.1], np.eye(1))["p_pool"] == 0.03
    p, se = [0.05, 0.10], [0.1, 0.2]
    z = stats.norm.isf(p)
    c = 1 / np.asarray(se)
    exp = stats.norm.sf((c * z).sum() / math.sqrt((c ** 2).sum()))
    assert pool.stouffer(p, se, np.eye(2))["p_pool"] == pytest.approx(exp)
    R = np.array([[1, 0.5], [0.5, 1]])
    exp_r = stats.norm.sf((c * z).sum() / math.sqrt(c @ R @ c))
    assert pool.stouffer(p, se, R)["p_pool"] == pytest.approx(exp_r)
    # perfectly correlated identical samples: no gain over one
    assert pool.stouffer([0.05, 0.05], [0.1, 0.1], np.ones((2, 2)))["p_pool"] == pytest.approx(0.05)
    # p = 1 clipped to B/(B+1)
    assert pool.stouffer([1.0, 0.01], [0.1, 0.1], np.eye(2), [99, 99])["p_pool"] is not None


def test_corr_matrix_and_pooled_series():
    idx = pd.period_range("2000-01", periods=40, freq="M")
    rng = np.random.default_rng(3)
    a = pd.Series(rng.standard_normal(40), idx)
    b = pd.Series(a.to_numpy() * 0.5 + rng.standard_normal(40), idx)
    c = pd.Series(rng.standard_normal(20), idx[:20])
    R = pool.corr_matrix([a, b, c])
    assert R[0, 1] == pytest.approx(a.corr(b)) and R[0, 2] == 0 and R[1, 2] == 0
    s1 = pd.Series([1.0, 2.0, 3.0], idx[:3])
    s2 = pd.Series([3.0, 6.0], idx[1:3])
    ps = pool.pooled_series([s1, s2], [1.0, 3.0])
    np.testing.assert_allclose(ps.to_numpy(), [1.0, (2 + 9) / 4, (3 + 18) / 4])


def test_best_year_share():
    idx = pd.period_range("2000-01", periods=36, freq="M")
    x = pd.Series(0.0, idx)
    x.iloc[0], x.iloc[12], x.iloc[24] = 0.06, 0.03, -0.05
    r = evaluate.best_year_share(x)
    assert r["share"] == pytest.approx(0.06 / 0.09) and r["best_year"] == 2000
    assert evaluate.best_year_share(-x.abs())["share"] is None


def test_k_from_ledger(tmp_path):
    p = tmp_path / "l.md"
    p.write_text(LEDGER_HEAD)
    with pytest.raises(GuardError, match="exactly one"):
        common.ledger_k(p)
    ledger_add(p, "k", "k", "-", "-", "k=4 fixed before first return")
    assert common.ledger_k(p) == 4


def test_pool_end_to_end(env):
    sp1, out1, _ = setup(env, sample_id="EARLY", sample_over={"month_window": {"start": None, "end_exclusive": "2006-01"}})
    run_sample.run(sp1, out1)
    sp2, out2, _ = setup(env, sample_id="LATE", version="v2",
                         sample_over={"month_window": {"start": "2006-01", "end_exclusive": None}})
    run_sample.run(sp2, out2)
    ledger_add(env["c7"], "k", "k", "-", "-", "k=3")
    res = pool.pool_all(env["root"] / "out")
    spec = res["specs"]["TSMOM-FI"]
    assert res["k"] == 3 and spec["samples"] == ["TSMOM-FI__EARLY", "TSMOM-FI__LATE"]
    assert spec["R"][0][1] == 0.0  # no common months
    m1 = json.loads((out1 / "metrics.json").read_text())
    m2 = json.loads((out2 / "metrics.json").read_text())
    se = [m1["active"]["se_if"]["se_sharpe_m"], m2["active"]["se_if"]["se_sharpe_m"]]
    z = stats.norm.isf([m1["active"]["p"]["p"], m2["active"]["p"]["p"]])
    c = 1 / np.asarray(se)
    assert spec["per_seed"][0]["p_pool"] == pytest.approx(stats.norm.sf((c * z).sum() / np.linalg.norm(c)))
    assert len(spec["per_seed"]) == 5 and isinstance(spec["positive"], bool)
    assert spec["positive"] == all(spec["gates"].values())
