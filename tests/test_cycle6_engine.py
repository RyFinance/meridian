"""Cycle-6 engine unit tests. SYNTHETIC DATA ONLY; ledgers are temp files (test-only env overrides)."""
from __future__ import annotations

import copy
import hashlib
import json
import math

import numpy as np
import pandas as pd
import pytest

from research.cycle6.engine import book, controls, fidelity, guards, panel, portfolio, runner, styles
from research.cycle6.engine import vol as evol


# ------------------------------------------------------------------------------------------------ fixtures
def synth_daily(n_mkts=5, years=12, seed=0, drift=None, start="2000-01-03"):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=int(years * 261))
    vols = np.linspace(0.08, 0.30, n_mkts) / math.sqrt(261)
    mu = np.zeros(n_mkts) if drift is None else np.asarray(drift) / 261
    x = mu + rng.standard_normal((len(idx), n_mkts)) * vols
    df = pd.DataFrame(x, index=idx, columns=[f"M{i}" for i in range(n_mkts)])
    df.iloc[:300, -1] = np.nan          # late starter
    df.iloc[1000:1010, 0] = np.nan      # a gap
    return df


def to_long(df):
    s = df.stack()
    out = s.rename("value").reset_index()
    out.columns = ["date", "market_id", "value"]
    return out


@pytest.fixture
def ledgers(tmp_path, monkeypatch):
    pre = tmp_path / "prereg.md"
    pre.write_text("| UTC | Kind | ID | File | SHA-256 | Note |\n|---|---|---|---|---|---|\n")
    trial = tmp_path / "trial.csv"
    monkeypatch.setenv("CYCLE6_TEST_PREREG_LEDGER", str(pre))
    monkeypatch.setenv("CYCLE6_TEST_TRIAL_LEDGER", str(trial))
    monkeypatch.delenv("QUANT_DATA_MANIFEST_SHA256", raising=False)
    return pre, trial


def make_snapshot(tmp_path, daily, cls="EQ", extra=None):
    from research.data_snapshot import canonical
    vdir = tmp_path / "store" / "versions" / "v1"
    view = vdir / "view"
    (view / "panels").mkdir(parents=True)
    to_long(daily).to_parquet(view / "panels" / "daily.parquet", index=False)
    pd.DataFrame({"class": cls, "market_id": daily.columns, "qa_status": "PASS"}).to_csv(
        view / "candidates.csv", index=False)
    for name, df in (extra or {}).items():
        to_long(df).to_parquet(view / "panels" / f"{name}.parquet", index=False)
    payload = {"schema_version": 1, "dataset_version": "v1", "records": []}
    sha = hashlib.sha256(canonical(payload)).hexdigest()
    (vdir / "manifest.json").write_text(json.dumps({"manifest_sha256": sha, "payload": payload}))
    return view, view / "candidates.csv", sha


BASE_PARAMS = {
    "schema": "cycle6-component-v1", "id": "TSMOM-EQ", "style": "tsmom", "class": "EQ",
    "inputs": {"daily_excess": "panels/daily.parquet", "signal_inputs": {},
               "series": {"ref": {"path": "panels/ref.parquet", "market_id": "REF"}}},
    "universe": {"min_assets": 3},
    "vol": {"com_days": 60, "annualisation": 261, "min_obs": 756, "lag_obs": 0},
    "signal": {"lookback_months": 12, "target_vol": 0.40},
    "weights": {"rank_vol_scale": False},
    "costs": {"bp_per_side": {"EQ": 2, "FI": 2, "FX": 3, "CM": 6}, "stress_multiplier": 3, "drift": True},
    "control": {"type": "always_long", "n_books": 100, "seed": 20260926},
    "inference": {"B": 199, "seed": 20260926, "crash": None, "bandwidth_fraction": 0.20, "overlap": 1,
                  "ci_B": 99, "ci_level": 0.90, "ci_level_crash_short": 0.95, "k": 21},
    "post_pub_cutoff": "2006-01",
    "fidelity": {"tier": "aqr_class", "reference": "ref", "scale_convention": "none",
                 "thresholds": {"n_min": 60, "rho_min": 0.65, "beta_lo": 0.70, "beta_hi": 1.30, "te_ratio_max": 0.90}},
    "betas": ["ref"],
}


def write_spec(tmp_path, params, name="SPEC.md", ledger=None, ledger_id=None):
    txt = "# synthetic spec\n\n```json\n" + json.dumps(params, indent=1) + "\n```\n"
    p = tmp_path / name
    p.write_text(txt)
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    if ledger is not None:
        with ledger.open("a") as f:
            f.write(f"| 2026-09-26T00:00:00Z | spec | {ledger_id or params['id']} | {name} | {sha} | test |\n")
    return p, sha


# ------------------------------------------------------------------------------------------------ vol
def test_vol_matches_bruteforce_and_warmup():
    rng = np.random.default_rng(1)
    x = rng.standard_normal(900) * 0.01 + 0.0003
    fast = evol.ew_vol_1d(x, 60, 261, 756)
    slow = evol.ew_vol_bruteforce(x, 60, 261, 756)
    assert np.all(np.isnan(fast[:755])) and np.all(np.isnan(slow[:755]))
    np.testing.assert_allclose(fast[755:], slow[755:], rtol=1e-8)
    # panel version skips NaN days (they are not observations) and truncates at the first valid obs
    idx = pd.bdate_range("2000-01-03", periods=900)
    s = pd.Series(x, idx)
    s.iloc[100:105] = np.nan
    v = evol.ew_vol(s.to_frame("a"), com_days=60, annualisation=261, min_obs=50)["a"]
    ref = evol.ew_vol_bruteforce(s.dropna().to_numpy(), 60, 261, 50)
    np.testing.assert_allclose(v.dropna().to_numpy(), ref[~np.isnan(ref)], rtol=1e-8)
    assert v.iloc[100:105].isna().all()
    lagged = evol.ew_vol(s.to_frame("a"), com_days=60, annualisation=261, min_obs=50, lag_obs=1)["a"].dropna()
    refv = ref[~np.isnan(ref)]
    assert len(lagged) == len(refv) - 1 and lagged.index[0] > v.dropna().index[0]
    np.testing.assert_allclose(lagged.to_numpy(), refv[:-1], rtol=1e-8)


# ------------------------------------------------------------------------------------------------ tsmom
def _tsmom(daily):
    mret = panel.monthly_returns(daily)
    v = panel.month_end_sample(evol.ew_vol(daily, com_days=60, annualisation=261, min_obs=756), mret.index)
    return mret, v, styles.tsmom_weights(mret, v, lookback_months=12, target_vol=0.4, min_assets=3)


def test_tsmom_sign_scale_and_no_lookahead():
    daily = synth_daily(seed=2)
    mret, v, (W, elig, n) = _tsmom(daily)
    t = mret.index[60]
    cum = np.log1p(mret.loc[mret.index[49]:t]).sum()
    for m in W.columns:
        if elig.at[t, m]:
            assert W.at[t, m] == pytest.approx(np.sign(cum[m]) * 0.4 / v.at[t, m] / n[t])
    # shuffle all daily data after month t's end: weights through t unchanged
    cut = t.to_timestamp(how="end")
    d2 = daily.copy()
    fut = d2.index > cut
    rng = np.random.default_rng(5)
    d2.loc[fut] = d2.loc[fut].to_numpy()[rng.permutation(fut.sum())] * 3.0
    _, _, (W2, _, _) = _tsmom(d2)
    pd.testing.assert_frame_equal(W.loc[:t], W2.loc[:t])
    assert not W.loc[t + 1:].equals(W2.loc[t + 1:])


# ------------------------------------------------------------------------------------------------ ranks
def test_rank_weights_sum_to_plus_minus_one():
    rng = np.random.default_rng(3)
    idx = pd.period_range("2000-01", periods=40, freq="M")
    sig = pd.DataFrame(rng.standard_normal((40, 7)), index=idx, columns=list("abcdefg"))
    sig.iloc[5, :4] = np.nan           # only 3 eligible -> undefined at min_assets 4
    sig.iloc[7, 2] = sig.iloc[7, 3]     # tie
    W, elig, n = styles.xs_rank_weights(sig, min_assets=4)
    ok = n >= 4
    np.testing.assert_allclose(W[ok].clip(lower=0).sum(axis=1), 1.0)
    np.testing.assert_allclose(W[ok].clip(upper=0).sum(axis=1), -1.0)
    assert (W.iloc[5] == 0).all()
    assert W.iloc[7, 2] == pytest.approx(W.iloc[7, 3])
    vol = pd.DataFrame(rng.uniform(0.05, 0.3, (40, 7)), index=idx, columns=sig.columns)
    Wv, _, _ = styles.xs_rank_weights(sig, min_assets=4, vol=vol)
    np.testing.assert_allclose(Wv[ok].clip(lower=0).sum(axis=1), 1.0)
    # higher signal -> higher weight (monotone, no vol scaling)
    r = sig.iloc[10].rank()
    assert np.all(np.diff(W.iloc[10][r.sort_values().index].to_numpy()) > 0)


def test_bab_legs_are_beta_neutral():
    rng = np.random.default_rng(4)
    idx = pd.period_range("2000-01", periods=20, freq="M")
    beta = pd.DataFrame(rng.uniform(0.4, 1.6, (20, 8)), index=idx, columns=list("abcdefgh"))
    W, _, n = styles.bab_weights(beta, min_assets=4)
    np.testing.assert_allclose((W * beta).sum(axis=1), 0.0, atol=1e-12)
    assert (W.where(W > 0).notna() & (beta > beta.median(axis=1).to_numpy()[:, None])).sum().sum() == 0


def test_fp_betas_recover_true_beta():
    rng = np.random.default_rng(6)
    idx = pd.bdate_range("2000-01-03", periods=2000)
    m = pd.Series(rng.standard_normal(2000) * 0.01, idx)
    d = pd.DataFrame({"lo": 0.5 * m + rng.standard_normal(2000) * 0.004,
                      "hi": 1.5 * m + rng.standard_normal(2000) * 0.004}, index=idx)
    b = styles.fp_betas(d, m, vol_window_days=252, vol_min_days=120, corr_window_days=1260, corr_min_days=750,
                        overlap_days=3, shrink_w=1.0)
    assert b["lo"].iloc[-1] == pytest.approx(0.5, abs=0.08)
    assert b["hi"].iloc[-1] == pytest.approx(1.5, abs=0.15)
    assert b.iloc[:700].isna().all().all()


def test_seasonality_signal_and_shuffle():
    idx = pd.period_range("1990-01", periods=24 * 12, freq="M")
    base = np.where(idx.month == 1, 0.05, 0.0)
    mret = pd.DataFrame({"a": base, "b": -base, "c": 0.0 * base, "d": 0.5 * base}, index=idx)
    s = styles.seasonality_signal(mret, years=20, min_years=5)
    dec = [p for p in idx if p.month == 12 and p.year >= 1996]
    assert np.allclose(s.loc[dec, "a"], 0.05) and np.allclose(s.loc[dec, "b"], -0.05)
    assert np.allclose(s.loc[[p for p in idx if p.month == 6 and p.year >= 1996], "a"], 0.0)
    assert s.iloc[:59].isna().all().all()
    p = styles.permute_month_labels(mret, np.random.default_rng(1))
    # each year keeps its multiset of returns
    for y in (1990, 2000):
        assert sorted(p[idx.year == y]["a"]) == sorted(mret[idx.year == y]["a"])


# ------------------------------------------------------------------------------------------------ portfolio
def test_execution_lag_differs_from_shadow_and_costs():
    idx = pd.bdate_range("2001-01-01", "2001-06-30")
    d = pd.DataFrame(0.0, index=idx, columns=["a", "b"])
    d.loc[pd.Timestamp("2001-03-01"), "a"] = 0.10     # jump on March's first session only
    mret = panel.monthly_returns(d)
    rnet = panel.net_period_returns(d)
    zero = pd.Series({"a": 0.0, "b": 0.0})
    defined = pd.Series(True, index=mret.index)
    W1 = pd.DataFrame({"a": [1.0, 0, 0, 0, 0, 0], "b": 0.0}, index=mret.index)   # signal end-Jan: hold Feb
    g = portfolio.gross_shadow(W1, mret, defined)
    n = portfolio.net_implementable(W1, rnet, zero, defined, drift=False)
    # shadow: Feb close-to-close, misses the jump; net: Feb day-1 close .. Mar day-1 close, catches it
    assert g.loc[pd.Period("2001-02", "M"), "ret"] == pytest.approx(0.0)
    assert n.loc[pd.Period("2001-02", "M"), "ret"] == pytest.approx(0.10)
    W2 = pd.DataFrame({"a": [0, 1.0, 0, 0, 0, 0], "b": 0.0}, index=mret.index)   # signal end-Feb: hold Mar
    assert portfolio.gross_shadow(W2, mret, defined).loc[pd.Period("2001-03", "M"), "ret"] == pytest.approx(0.10)
    assert portfolio.net_implementable(W2, rnet, zero, defined, drift=False).loc[
        pd.Period("2001-03", "M"), "ret"] == pytest.approx(0.0)
    # costs = turnover x rate (undrifted); stress = 3x
    W = pd.DataFrame({"a": [1.0, 0.0, 1.0, 1.0, -0.5, 0.0], "b": [0, 0.5, 0.5, 0, 0, 0]}, index=mret.index)
    rate = pd.Series({"a": 0.0003, "b": 0.0006})
    c = portfolio.net_implementable(W, rnet, rate, defined, drift=False)
    Wl = W.shift(1).fillna(0)
    tr = (Wl - Wl.shift(1).fillna(0)).abs()
    np.testing.assert_allclose(c["turnover"], tr.sum(axis=1).reindex(c.index))
    np.testing.assert_allclose(c["cost"], (tr * rate).sum(axis=1).reindex(c.index))
    np.testing.assert_allclose(c["ret"], c["ret_before_cost"] - c["cost"])
    s = portfolio.net_implementable(W, rnet, rate, defined, cost_multiplier=3, drift=False)
    np.testing.assert_allclose(s["cost"], 3 * c["cost"])


def test_net_period_returns_compound():
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2003-01-01", "2003-04-30")
    d = pd.DataFrame({"a": rng.standard_normal(len(idx)) * 0.01}, index=idx)
    r = panel.net_period_returns(d)["a"]
    feb = d.loc["2003-02-04":"2003-03-03", "a"]    # Feb day 2 .. Mar day 1
    assert d.loc["2003-02"].index[0] == pd.Timestamp("2003-02-03")
    assert r[pd.Period("2003-02", "M")] == pytest.approx(np.prod(1 + feb) - 1)
    assert panel.monthly_returns(d)["a"][pd.Period("2003-02", "M")] == pytest.approx(
        np.prod(1 + d.loc["2003-02", "a"]) - 1)


def test_random_rank_placebo_mean_near_zero():
    rng = np.random.default_rng(8)
    idx = pd.period_range("2000-01", periods=240, freq="M")
    mu = np.linspace(-0.01, 0.01, 10)
    R = pd.DataFrame(mu + rng.standard_normal((240, 10)) * 0.03, index=idx, columns=[f"m{i}" for i in range(10)])
    elig = R.notna()
    builder = lambda s: styles.xs_rank_weights(s, min_assets=4)[0]  # noqa: E731
    defined = pd.Series(True, index=idx)
    ev = lambda W: {"gross": portfolio.gross_shadow(W, R, defined)["ret"]}  # noqa: E731
    c = controls.random_rank_books(elig, builder, ev, n_books=100, seed=20260926)
    oracle = ev(builder(pd.DataFrame(np.tile(mu, (240, 1)), index=idx, columns=R.columns)))["gross"]
    assert abs(c["gross"].mean()) < 0.1 * oracle.mean()
    c2 = controls.random_rank_books(elig, builder, ev, n_books=100, seed=20260926)
    pd.testing.assert_series_equal(c["gross"], c2["gross"])


def test_matched_active_series():
    idx = pd.period_range("2000-01", periods=5, freq="M")
    b = pd.Series([0.01, 0.02, -0.01, 0.0, 0.03], idx)
    c = pd.Series([0.02, 0.01, 0.00, 0.01, 0.02], idx)
    ratio = pd.Series([0.5, 0.5, 0.0, 1.0, 0.5], idx)
    a, mbar = controls.matched_active(b, c, ratio)
    assert mbar == pytest.approx(0.5)
    np.testing.assert_allclose(a, b - 0.5 * c)


# ------------------------------------------------------------------------------------------------ fidelity
def test_fidelity_tiers_on_known_series():
    rng = np.random.default_rng(9)
    idx = pd.period_range("2000-01", periods=120, freq="M")
    ref = pd.Series(rng.standard_normal(120) * 0.03, idx)
    r = fidelity.aqr_tier(ref.copy(), ref)
    assert r["pass"] and r["rho"] == pytest.approx(1) and r["beta"] == pytest.approx(1) and r["te_ann"] == pytest.approx(0, abs=1e-12)
    r2 = fidelity.aqr_tier(2 * ref, ref)
    assert not r2["pass"] and r2["beta"] == pytest.approx(2) and any("beta" in x for x in r2["reasons"])
    r3 = fidelity.aqr_tier(2 * ref, ref, scale_convention="ex_post_vol",
                           target_vol_ann=float(ref.std() * math.sqrt(12)))
    assert r3["pass"] and r3["beta"] == pytest.approx(1)
    assert not fidelity.aqr_tier(ref.iloc[:50], ref)["pass"]
    noise = pd.Series(rng.standard_normal(120) * 0.03, idx)
    r4 = fidelity.aqr_tier(ref + noise, ref)
    te = float((noise).std() * math.sqrt(12))
    assert r4["te_ann"] == pytest.approx(te)
    x = pd.Series(0.01 + rng.standard_normal(120) * 0.02, idx)
    m, v = float(x.mean() * 12), float(x.std() * math.sqrt(12))
    paper = {"start": "2000-01", "end": "2009-12", "mean_ann": m, "vol_ann": v, "sharpe_ann": m / v}
    assert fidelity.paper_stat_tier(x, paper)["pass"]
    assert not fidelity.paper_stat_tier(x.iloc[10:], paper)["pass"]           # coverage 110/120 < 95%
    assert not fidelity.paper_stat_tier(x, {**paper, "mean_ann": m + 0.05})["pass"]


# ------------------------------------------------------------------------------------------------ book
def test_erc_equal_risk_contributions_and_fallback():
    rng = np.random.default_rng(10)
    A = rng.standard_normal((4, 4))
    S = A @ A.T + 4 * np.eye(4)
    w = book.erc_weights(S)
    np.testing.assert_allclose(book.risk_contributions(w, S), 0.25, atol=1e-8)
    assert w.sum() == pytest.approx(1) and np.all(w > 0)
    assert book.erc_weights(np.array([[1.0, 2.0], [2.0, 1.0]])) is None    # not PD -> fallback


def test_build_book_vol_target_and_cap():
    rng = np.random.default_rng(11)
    idx = pd.period_range("2000-01", periods=150, freq="M")
    X = pd.DataFrame(rng.standard_normal((150, 3)) * [0.01, 0.03, 0.05], index=idx, columns=["a", "b", "c"])
    tb = pd.Series(0.03, idx)
    bk, wts = book.build_book(X, tb, {"cov_months": 60, "shrink": 0.25, "vol_target": 0.10, "gross_cap": 2.0,
                                      "cash_spread": 0.005, "financing_spread": 0.02, "fallback_min_obs": 12})
    assert (bk["gross"] <= 2.0 + 1e-12).all()
    erc = bk[bk["method"] == "erc"]
    assert len(erc) == 90 and erc.index[0] == idx[60]           # needs 60 earlier months
    assert (bk.loc[idx[1:12], "method"] == "cash").all() and (bk.loc[idx[12:60], "method"] == "inv_vol").all()
    unc = erc[erc["gross"] < 2.0 - 1e-9]
    np.testing.assert_allclose(unc["exante_vol"], 0.10)
    m = book.mdd_simulation(bk["excess"].to_numpy(), n_paths=500, seed=20260925)
    assert m == book.mdd_simulation(bk["excess"].to_numpy(), n_paths=500, seed=20260925)
    assert m["mdd_p05"] <= m["mdd_median"] <= m["mdd_p95"] <= 0
    lev = book.leverage_for_target(pd.Series(np.full(120, 0.004)), 0.03, n_draws=200)
    assert lev["leverage"] == pytest.approx((0.12 - 0.03 - 0.02) / (0.048 - 0.02)) and lev["status"] == "not attainable (leverage > cap)"


# ------------------------------------------------------------------------------------------------ runner guards
def _setup_run(tmp_path, ledgers, params_over=None, ledger_it=True):
    pre, trial = ledgers
    daily = synth_daily(n_mkts=5, years=12, seed=12, drift=[0.02, 0.0, 0.03, -0.01, 0.01])
    mret = panel.monthly_returns(daily)
    ref = pd.DataFrame({"REF": mret.mean(axis=1).to_numpy()}, index=mret.index.to_timestamp(how="end").normalize())
    view, memb, msha = make_snapshot(tmp_path, daily, extra={"ref": ref})
    p = copy.deepcopy(BASE_PARAMS)
    p["engine_sha256"] = guards.engine_sha256()
    p["snapshot_manifest_sha256"] = msha
    for k, v in (params_over or {}).items():
        p[k] = v
    spec, sha = write_spec(tmp_path, p, ledger=pre if ledger_it else None)
    args = ["--spec", str(spec), "--snapshot-root", str(view), "--membership", str(memb),
            "--out", str(tmp_path / "out" / p["id"])]
    return args, sha, trial


def test_runner_refuses_unledgered_spec(tmp_path, ledgers):
    args, sha, trial = _setup_run(tmp_path, ledgers, ledger_it=False)
    with pytest.raises(guards.GuardError, match="not in the prereg ledger"):
        runner.main_component(args)
    assert not trial.exists()


def test_runner_refuses_engine_hash_mismatch(tmp_path, ledgers):
    args, sha, trial = _setup_run(tmp_path, ledgers, params_over={"engine_sha256": "0" * 64})
    with pytest.raises(guards.GuardError, match="engine hash mismatch"):
        runner.main_component(args)
    assert not trial.exists()


def test_runner_refuses_snapshot_mismatch(tmp_path, ledgers):
    args, sha, trial = _setup_run(tmp_path, ledgers, params_over={"snapshot_manifest_sha256": "f" * 64})
    with pytest.raises(guards.GuardError, match="snapshot manifest mismatch"):
        runner.main_component(args)


def test_runner_end_to_end_then_refuses_duplicate(tmp_path, ledgers):
    args, sha, trial = _setup_run(tmp_path, ledgers)
    assert runner.main_component(args) == 0
    out = tmp_path / "out" / "TSMOM-EQ"
    for f in ("gross.csv", "net.csv", "net_stress.csv", "control.csv", "active.csv", "weights.parquet",
              "metrics.json"):
        assert (out / f).exists(), f
    m = json.loads((out / "metrics.json").read_text())
    assert m["active_post"]["p"]["B"] == 199 and 0 < m["active_post"]["p"]["p"] <= 1
    assert "pass" in m["fidelity"] and m["net_post"]["ci"]["level"] == 0.90
    assert m["exposure_match"]["mbar_post"] is not None
    rows = guards.read_trials()
    assert [r["status"] for r in rows] == ["started", "ok"] and rows[0]["spec_sha256"] == sha
    args2 = list(args)
    args2[-1] = str(tmp_path / "out" / "again")
    with pytest.raises(guards.GuardError, match="already exists"):
        runner.main_component(args2)
    with pytest.raises(guards.GuardError, match="not in the prereg ledger"):
        runner.main_component(args2 + ["--bugfix-entry", "BUG-1"])


def test_rank_component_end_to_end(tmp_path, ledgers):
    over = {"id": "XSMOM-EQ", "style": "xsmom", "signal": {"lookback_months": 12, "skip_months": 1},
            "universe": {"min_assets": 4}, "control": {"type": "random_rank", "n_books": 5, "seed": 20260926},
            "inference": {**BASE_PARAMS["inference"], "crash": {"intensity_per_year": 0.2, "jump_sd": -6},
                          "bandwidth_fraction": 0.20}}
    args, sha, trial = _setup_run(tmp_path, ledgers, params_over=over)
    assert runner.main_component(args) == 0
    net = pd.read_csv(tmp_path / "out" / "XSMOM-EQ" / "net.csv", index_col=0)
    act = pd.read_csv(tmp_path / "out" / "XSMOM-EQ" / "active.csv", index_col=0)
    assert net["net_exposure"].abs().max() < 1e-9
    assert act["active_full_window"].notna().sum() > 60


def test_test_overrides_refused_outside_pytest(monkeypatch, tmp_path):
    monkeypatch.setenv("CYCLE6_TEST_TRIAL_LEDGER", str(tmp_path / "x.csv"))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(guards.GuardError, match="test-only"):
        guards.trial_ledger_path()


def test_book_end_to_end_and_guards(tmp_path, ledgers):
    pre, trial = ledgers
    rng = np.random.default_rng(13)
    idx = pd.bdate_range("1995-01-02", periods=261 * 20)
    core = pd.DataFrame(rng.standard_normal((len(idx), 2)) * [0.011, 0.004] + [0.0003, 0.0001], index=idx,
                        columns=["SPY", "IEF"])
    tb = pd.DataFrame({"TB3M": 0.03}, index=idx)
    view, memb, msha = make_snapshot(tmp_path, core, extra={"tbill": tb})
    comps = tmp_path / "components"
    months = pd.period_range("1995-02", periods=239, freq="M")
    for cid, passed in (("TSMOM-EQ", True), ("XSMOM-EQ", False)):
        d = comps / cid
        d.mkdir(parents=True)
        spec_sha = hashlib.sha256(cid.encode()).hexdigest()
        net = pd.DataFrame({"ret": rng.standard_normal(239) * 0.03 + 0.004, "gross_exposure": 1.5},
                           index=[str(m) for m in months])
        net.index.name = "month"
        net.to_csv(d / "net.csv")
        (d / "metrics.json").write_text(json.dumps({"fidelity": {"pass": passed}, "post_pub_cutoff": "2011-01",
                                                    "run": {"spec_sha256": spec_sha}}))
        guards.append_trial({"kind": "component", "id": cid, "spec_sha256": spec_sha, "status": "ok"})
    p = {"schema": "cycle6-book-v1", "id": "BOOK", "engine_sha256": guards.engine_sha256(),
         "snapshot_manifest_sha256": msha, "components_root": str(comps), "candidates": ["TSMOM-EQ", "XSMOM-EQ"],
         "core": {"daily_excess": "panels/daily.parquet", "markets": ["SPY", "IEF"], "weights": [0.6, 0.4],
                  "cost_bp_per_side": 2, "post_pub_cutoff": "2011-01"},
         "tbill": {"path": "panels/tbill.parquet", "market_id": "TB3M"},
         "book": {"cov_months": 60, "shrink": 0.25, "vol_target": 0.10, "gross_cap": 2.0, "cash_spread": 0.005,
                  "financing_spread": 0.02, "fallback_min_obs": 12},
         "inference": {"ci_B": 99, "ci_level": 0.90, "seed": 1},
         "leverage_calc": {"target_total_ann": 0.12, "lcb_level": 0.75, "n_draws": 500, "mean_block": 12,
                           "seed": 20260925, "cap": 2.0},
         "mdd_sim": {"n_paths": 500, "horizon_months": 120, "mean_block": 12, "seed": 20260925}}
    spec, sha = write_spec(tmp_path, p, name="BOOK.md", ledger=pre)
    args = ["--spec", str(spec), "--snapshot-root", str(view), "--membership", str(memb),
            "--out", str(tmp_path / "book")]
    assert runner.main_book(args) == 0
    m = json.loads((tmp_path / "book" / "metrics.json").read_text())
    assert m["sleeves"]["TSMOM-EQ"]["included"] and not m["sleeves"]["XSMOM-EQ"]["included"]
    assert m["max_gross"] <= 2.0 + 1e-9 and "mdd_p05" in m["mdd_simulation"]
    assert m["positive"] in (True, False)
    with pytest.raises(guards.GuardError, match="already exists"):
        runner.main_book(args[:-1] + [str(tmp_path / "book2")])


# ------------------------------------------------------------------------------------------------ addendum-1 changes
def test_paper_stat_published_metrics_only():
    rng = np.random.default_rng(20)
    idx = pd.period_range("1981-01", "2011-12", freq="M")
    x = pd.Series(0.004 + rng.standard_normal(len(idx)) * 0.03, idx)
    sh = float(x.mean() / x.std() * math.sqrt(12))
    paper = {"start": "1981-01", "end": "2011-12", "mean_ann": None, "vol_ann": None, "sharpe_ann": sh + 0.1}
    r = fidelity.paper_stat_tier(x, paper)
    assert r["pass"] and r["compared_metrics"] == ["sharpe_ann"]
    assert {d["metric"] for d in r["skipped_metrics"]} == {"mean_ann", "vol_ann"}
    assert not fidelity.paper_stat_tier(x, {**paper, "sharpe_ann": sh + 0.4})["pass"]
    assert not fidelity.paper_stat_tier(x.iloc[24:], paper)["pass"]                       # coverage binds
    none = fidelity.paper_stat_tier(x, {**paper, "sharpe_ann": None})
    assert not none["pass"] and any("no published metric" in s for s in none["reasons"])
    th = fidelity.paper_stat_tier(x, {**paper, "mean_ann": 0.0}, thresholds={"mean_abs": None})
    assert th["pass"] and {"metric": "mean_ann", "reason": "threshold null"} in th["skipped_metrics"]


BSV_SP = {"construction": "bsv", "years": 20, "min_years": 1, "sizing_vol_window_months": 36,
          "sizing_vol_min_months": 36, "sizing_vol_floor_quantile": 0.10, "sizing_vol_floor_abs": 0.025,
          "class_vol_target": 0.10, "class_vol_window_months": 120, "class_vol_min_months": 60,
          "class_vol_method": "ex_ante_cov"}


def _bsv_mret(seed=21, T=420, N=6):
    rng = np.random.default_rng(seed)
    idx = pd.period_range("1980-01", periods=T, freq="M")
    vols = np.linspace(0.02, 0.08, N)
    return pd.DataFrame(rng.standard_normal((T, N)) * vols, index=idx, columns=[f"c{i}" for i in range(N)])


def test_bsv_seasonality_sizing_target_and_no_lookahead():
    from research.cycle6.engine import component
    mret = _bsv_mret()
    sig = styles.seasonality_signal(mret, years=20, min_years=1)
    W, elig, n = component.bsv_builder(BSV_SP, mret, 2)(sig)
    svol = styles.rolling_vol_monthly(mret, window_months=36, min_months=36)
    cube = styles.rolling_cov_cube(mret, window_months=120, min_months=60)
    ok = np.where(n.to_numpy() >= 2)[0]
    assert len(ok) > 200 and ok[0] >= 59
    for j in ok[::37]:
        w = W.iloc[j].to_numpy()
        assert math.sqrt(12 * w @ cube[j] @ w) == pytest.approx(0.10, rel=1e-9)
        Wr, _, _ = styles.xs_rank_weights(sig.iloc[[j]], min_assets=2, eligible=svol.iloc[[j]].notna())
        v = svol.iloc[j]
        fl = max(v[Wr.iloc[0] != 0].quantile(0.10), 0.025)
        raw = Wr.iloc[0] / v.clip(lower=fl)
        np.testing.assert_allclose(w / np.abs(w).sum(), (raw / raw.abs().sum()).to_numpy(), atol=1e-12)
    t = mret.index[300]
    m2 = mret.copy()
    m2.loc[t + 1:] = m2.loc[t + 1:].to_numpy()[::-1] * 5
    W2, _, _ = component.bsv_builder(BSV_SP, m2, 2)(styles.seasonality_signal(m2, years=20, min_years=1))
    pd.testing.assert_frame_equal(W.loc[:t], W2.loc[:t])
    Wr2, scale = styles.class_vol_target(W, mret, target_vol=0.1, window_months=120, min_months=60,
                                         method="strategy_realised")
    assert scale.notna().sum() > 100


def test_fp_monthly_betas_and_treasury_bab_component():
    from research.cycle6.engine import component
    rng = np.random.default_rng(22)
    idx = pd.period_range("1960-01", periods=600, freq="M")
    mkt = pd.Series(rng.standard_normal(600) * 0.02, idx)
    true = np.array([0.2, 0.5, 1.0, 1.6, 2.2])
    mret = pd.DataFrame(np.outer(mkt, true) + rng.standard_normal((600, 5)) * 0.002, index=idx,
                        columns=[f"b{i}" for i in range(5)])
    b = styles.fp_betas_monthly(mret, mret.mean(axis=1), vol_window_months=12, vol_min_months=12,
                                corr_window_months=60, corr_min_months=36, overlap_months=1, shrink_w=1.0)
    assert b.iloc[:35].isna().all().all() and b.iloc[35].notna().all()
    np.testing.assert_allclose(b.iloc[-1].to_numpy() / b.iloc[-1].mean(), true / true.mean(), rtol=0.25)
    assert (b.iloc[100:].rank(axis=1).diff(axis=1).iloc[:, 1:] > 0).mean().mean() > 0.95
    # full pipeline on synthetic daily data with monthly betas
    days = pd.bdate_range("1990-01-01", periods=261 * 20)
    mk = rng.standard_normal(len(days)) * 0.003
    daily = pd.DataFrame(np.outer(mk, true) + rng.standard_normal((len(days), 5)) * 0.0005, index=days,
                         columns=[f"b{i}" for i in range(5)])
    p = copy.deepcopy(BASE_PARAMS)
    p.update({"id": "BAB-FI", "style": "bab", "class": "FI", "universe": {"min_assets": 4},
              "signal": {"beta_frequency": "monthly", "benchmark": "ew_universe", "vol_window_months": 12,
                         "vol_min_months": 12, "corr_window_months": 60, "corr_min_months": 36,
                         "overlap_months": 1, "shrink_w": 0.6, "log_returns": True},
              "control": {"type": "random_rank", "n_books": 5, "seed": 1}})
    p["fidelity"] = {"tier": "paper_stat", "paper": {"start": "1995-01", "end": "2009-12", "mean_ann": None,
                                                     "vol_ann": None, "sharpe_ann": 0.81}}
    res = component.compute_component(p, {"daily": daily, "classes": {}, "signal_inputs": {}, "series": {}})
    W = res["W"]
    betas = styles.fp_betas_monthly(panel.monthly_returns(daily), panel.monthly_returns(daily).mean(axis=1),
                                    vol_window_months=12, vol_min_months=12, corr_window_months=60,
                                    corr_min_months=36, overlap_months=1, shrink_w=0.6)
    live = W.abs().sum(axis=1) > 0
    assert live.sum() > 150
    np.testing.assert_allclose((W[live] * betas[live]).sum(axis=1), 0.0, atol=1e-10)
    assert (W[live]["b0"] > 0).all() and (W[live]["b4"] < 0).all()
    assert res["metrics"]["fidelity"]["compared_metrics"] == ["sharpe_ann"]


def test_book_core_not_backfilled(tmp_path, ledgers):
    pre, trial = ledgers
    rng = np.random.default_rng(23)
    idx = pd.bdate_range("1995-01-02", periods=261 * 20)
    core = pd.DataFrame(rng.standard_normal((len(idx), 2)) * [0.011, 0.004], index=idx, columns=["SPY", "IEF"])
    core.loc[:"2002-07-31", "IEF"] = np.nan          # IEF incepts Aug 2002
    view, memb, msha = make_snapshot(tmp_path, core, extra={"tbill": pd.DataFrame({"TB3M": 0.03}, index=idx)})
    comps = tmp_path / "components"
    months = pd.period_range("1995-02", periods=239, freq="M")
    d = comps / "TSMOM-EQ"
    d.mkdir(parents=True)
    net = pd.DataFrame({"ret": rng.standard_normal(239) * 0.03, "gross_exposure": 1.0}, index=[str(m) for m in months])
    net.index.name = "month"
    net.to_csv(d / "net.csv")
    (d / "metrics.json").write_text(json.dumps({"fidelity": {"pass": True}, "post_pub_cutoff": "2011-01",
                                                "run": {"spec_sha256": "a" * 64}}))
    guards.append_trial({"id": "TSMOM-EQ", "spec_sha256": "a" * 64, "status": "ok"})
    params = {"components_root": str(comps), "candidates": ["TSMOM-EQ"],
              "core": {"daily_excess": "panels/daily.parquet", "markets": ["SPY", "IEF"], "weights": [0.6, 0.4],
                       "cost_bp_per_side": 2, "post_pub_cutoff": "2011-01"},
              "tbill": {"path": "panels/tbill.parquet", "market_id": "TB3M"},
              "book": {"cov_months": 60, "shrink": 0.25, "vol_target": 0.10, "gross_cap": 2.0, "cash_spread": 0.005,
                       "financing_spread": 0.02, "fallback_min_obs": 12},
              "inference": {"ci_B": 49, "ci_level": 0.90, "seed": 1}, "id": "BOOK",
              "leverage_calc": {"target_total_ann": 0.12, "lcb_level": 0.75, "n_draws": 100, "mean_block": 12,
                                "seed": 1, "cap": 2.0},
              "mdd_sim": {"n_paths": 100, "horizon_months": 120, "mean_block": 12, "seed": 1}}
    c, _ = runner.core_sleeve(params, view)
    assert c.index[0] == pd.Period("2002-09", "M")      # needs a full prior month (Aug) of trading
    res = runner.compute_book(params, view)
    assert res["metrics"]["sleeves"]["CORE"]["first_defined_month"] == "2002-09"
    w = res["weights"]
    pre_core = w[w["month"] < "2002-10"]
    assert len(pre_core) > 0 and set(pre_core["sleeve"]) == {"TSMOM-EQ"}
    assert "CORE" in set(w[w["month"] >= "2003-10"]["sleeve"])
