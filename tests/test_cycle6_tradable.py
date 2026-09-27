"""Cycle-6 tradable-variant unit tests. SYNTHETIC DATA ONLY; ledgers are temp files (test-only env overrides)."""
from __future__ import annotations

import hashlib
import json
import math

import numpy as np
import pandas as pd
import pytest

from research.cycle6.engine import guards as eg
from research.cycle6.tradable import data as vdata
from research.cycle6.tradable import mapping, runner, sim, vguards

P = lambda s: pd.Period(s, "M")


# ------------------------------------------------------------------------------------------------ mapping
def test_instrument_weights_lag_core_and_sum():
    bw = pd.DataFrame({"month": ["2010-02", "2010-02", "2010-03", "2010-03"],
                       "sleeve": ["A", "CORE", "A", "B"], "scaled_weight": [0.5, 1.0, 2.0, 1.0]})
    comp = {"A": pd.DataFrame({"signal_month": ["2010-01", "2010-02"], "market_id": ["M1", "M1"], "weight": [1.0, -0.5]}),
            "B": pd.DataFrame({"signal_month": ["2010-02", "2010-02"], "market_id": ["M1", "M2"], "weight": [0.2, 0.4]})}
    core = {"sleeve": "CORE", "markets": ["SPY", "IEF"], "weights": [0.6, 0.4]}
    X = mapping.instrument_weights(bw, comp, core)
    assert X.at[P("2010-02"), "M1"] == pytest.approx(0.5)          # A formed 2010-01 held 2010-02
    assert X.at[P("2010-02"), "CORE:SPY"] == pytest.approx(0.6)
    assert X.at[P("2010-03"), "M1"] == pytest.approx(2.0 * -0.5 + 0.2)   # summed across sleeves
    assert X.at[P("2010-03"), "M2"] == pytest.approx(0.4)
    assert X.at[P("2010-03"), "CORE:IEF"] == 0.0


def _X():
    idx = pd.period_range("2010-01", periods=3, freq="M")
    return pd.DataFrame({"FX_EUR": [0.8, -0.4, 0.3], "FX_NOK": [0.3, 0.3, 0.3], "CORE:IEF": [0.4, 0.4, 0.4],
                         "FI_US_10Y": [-0.2, 0.5, 0.1]}, index=idx)


MAP = {"FX_EUR": [{"vehicle": "M6E", "from": "2010-03"}, {"vehicle": "FXE", "from": None}],
       "FX_NOK": [{"vehicle": None}], "CORE:IEF": [{"vehicle": "IEF"}], "FI_US_10Y": [{"vehicle": "IEF"}]}


def test_long_flat_clip_drop_and_cap():
    Y, info, drops, chosen = mapping.vehicle_targets(_X(), MAP, lambda v, h: v != "M6E", long_only=True, gross_cap=1.0)
    h1, h2 = P("2010-01"), P("2010-02")
    # clip at instrument level: FI_US -0.2 -> 0 (not netted against core IEF)
    assert info.at[h1, "mapped_gross"] == pytest.approx(0.8 + 0.4)
    assert Y.at[h1, "FXE"] == pytest.approx(0.8 / 1.2)
    assert Y.at[h1, "IEF"] == pytest.approx(0.4 / 1.2)
    assert Y.loc[h1].sum() == pytest.approx(1.0)
    assert Y.at[h2, "FXE"] == 0.0 and Y.at[h2, "IEF"] == pytest.approx(0.9)
    assert info.at[h2, "scale"] == 1.0                                      # never scaled up
    assert set(drops["instrument"]) == {"FX_NOK"}
    assert (Y >= 0).all().all()


def test_margin_future_priority_and_shorts():
    Y, info, drops, chosen = mapping.vehicle_targets(_X(), MAP, lambda v, h: True, long_only=False, gross_cap=2.0)
    assert Y.at[P("2010-02"), "FXE"] == pytest.approx(-0.4)                 # ETF before the future's from-month
    assert Y.at[P("2010-03"), "M6E"] == pytest.approx(0.3)                  # future from its from-month
    assert Y.at[P("2010-03"), "FXE"] == 0.0
    assert Y.at[P("2010-01"), "IEF"] == pytest.approx(0.2)                  # 0.4 core - 0.2 FI netted per vehicle
    assert info["gross"].max() <= 2.0 + 1e-12


def test_unavailable_vehicle_falls_back_then_drops():
    Y, _, drops, _ = mapping.vehicle_targets(_X(), MAP, lambda v, h: v not in ("M6E", "FXE"), long_only=False,
                                             gross_cap=2.0)
    assert "FXE" not in Y.columns and "M6E" not in Y.columns
    assert set(drops["instrument"]) == {"FX_NOK", "FX_EUR"}


def test_unmapped_instrument_raises():
    with pytest.raises(ValueError):
        mapping.vehicle_targets(_X(), {"FX_EUR": []}, lambda v, h: True, long_only=True, gross_cap=1.0)


# ------------------------------------------------------------------------------------------------ sim
def _meta(**kw):
    m = {"kind": "etf", "ccy": "USD", "half_spread_bp": 1.0, "tax_class": "us_ric", "borrow_fee_ann": 0.003,
         "commission": {"type": "per_share", "per_share": 0.005, "min": 1.0, "max_pct": 0.01}}
    m.update(kw)
    return m


def _mkt(idx, R, U, dy=None, g=0.0, L=1.3, r=0.03, rcad=0.02):
    cols = list(R)
    return {"R": pd.DataFrame(R, index=idx), "U": pd.DataFrame(U, index=idx),
            "dy": pd.DataFrame(dy if dy is not None else {c: 0.0 for c in cols}, index=idx),
            "g": pd.Series(g, index=idx), "L": pd.Series(L, index=idx),
            "r": {"USD": pd.Series(r, index=idx), "CAD": pd.Series(rcad, index=idx)}}


def _acct(**kw):
    a = {"F": "USD", "capital": 100_000.0, "rounded": False, "withholding": {}, "creditable": {}, "conv_rate": 0.0003,
         "cash_spread": 0.005, "financing_spread": 0.02, "spread_mult": 1.0, "borrow_mult": 1.0}
    a.update(kw)
    return a


def test_sim_single_etf_usd_unrounded():
    idx = pd.period_range("2015-01", periods=2, freq="M")
    Y = pd.DataFrame({"IEF": [0.5, 0.5]}, index=idx)
    mkt = _mkt(idx, {"IEF": [0.01, -0.02]}, {"IEF": [100.0, 100.0]})
    fr, q = sim.simulate(Y, mkt, {"IEF": _meta()}, _acct())
    shares = 0.5 * 100_000 / 100
    cost0 = 1e-4 * 0.5 + 0.005 * shares / 100_000
    exp0 = 0.5 * 0.01 + 0.5 * (0.03 - 0.005) / 12 - cost0
    assert fr["total"].iloc[0] == pytest.approx(exp0)
    assert fr["excess"].iloc[0] == pytest.approx(exp0 - 0.03 / 12)
    assert fr["turnover"].iloc[1] == 0.0                   # constant capital, same price -> no trade
    assert q["IEF"].iloc[0] == pytest.approx(shares)


def test_sim_rounding_min_ticket_and_unheld():
    idx = pd.period_range("2015-01", periods=1, freq="M")
    Y = pd.DataFrame({"A": [0.002], "B": [0.3]}, index=idx)
    mkt = _mkt(idx, {"A": [0.0], "B": [0.0]}, {"A": [150.0], "B": [99.0]})
    fr, q = sim.simulate(Y, mkt, {"A": _meta(), "B": _meta()}, _acct(capital=25_000.0, rounded=True))
    assert q["A"].iloc[0] == 0.0 and fr["n_zero_held"].iloc[0] == 1      # 50 USD target < half a share of 150
    nB = sim.round_half_away(np.array([0.3 * 25_000 / 99.0]))[0]
    assert q["B"].iloc[0] == nB
    assert fr["cost_commission"].iloc[0] == pytest.approx(1.0 / 25_000)   # min ticket binds (76 shares * 0.005)
    assert fr["round_abs_err"].iloc[0] == pytest.approx(0.002 + abs(nB * 99 / 25_000 - 0.3))
    assert sim.round_half_away(np.array([-2.5, 2.5, 0.49]))[0] == -3.0


def test_sim_cad_funding_translation_and_conversion():
    idx = pd.period_range("2015-01", periods=1, freq="M")
    Y = pd.DataFrame({"GLD": [0.5]}, index=idx)
    mkt = _mkt(idx, {"GLD": [0.02]}, {"GLD": [100.0]}, g=0.03, L=1.25)
    fr, _ = sim.simulate(Y, mkt, {"GLD": _meta(tax_class="none", half_spread_bp=0.0)},
                         _acct(F="CAD", conv_rate=0.0015))
    asset = 0.5 * (1.02 * 1.03 - 1)
    assert fr["asset_ret"].iloc[0] == pytest.approx(asset)
    assert fr["cost_fx"].iloc[0] == pytest.approx(0.0015 * 0.5)
    assert fr["rf"].iloc[0] == pytest.approx(0.02 / 12)                   # CAD rate for a CAD-funded account
    # CAD-listed vehicle in a USD-funded account
    Y2 = pd.DataFrame({"ZFM": [1.0]}, index=idx)
    mkt2 = _mkt(idx, {"ZFM": [0.01]}, {"ZFM": [14.0]}, g=0.05, L=1.25)
    fr2, _ = sim.simulate(Y2, mkt2, {"ZFM": _meta(ccy="CAD", tax_class="ca_domestic", half_spread_bp=0.0,
                                                   commission={"type": "per_share", "per_share": 0.0, "min": 0, "max_pct": 1})},
                          _acct(F="USD", conv_rate=0.0))
    assert fr2["asset_ret"].iloc[0] == pytest.approx(1.01 / 1.05 - 1)


def test_sim_withholding_by_account_and_creditable():
    idx = pd.period_range("2015-01", periods=1, freq="M")
    Y = pd.DataFrame({"SPY": [0.6]}, index=idx)
    mkt = _mkt(idx, {"SPY": [0.0]}, {"SPY": [400.0]}, dy={"SPY": [0.004]})
    tfsa, _ = sim.simulate(Y, mkt, {"SPY": _meta()}, _acct(withholding={"us_ric": 0.15}))
    rrsp, _ = sim.simulate(Y, mkt, {"SPY": _meta()}, _acct(withholding={"us_ric": 0.0}))
    marg, _ = sim.simulate(Y, mkt, {"SPY": _meta()}, _acct(withholding={}, creditable={"us_ric": 0.15}))
    assert tfsa["withholding"].iloc[0] == pytest.approx(0.15 * 0.6 * 0.004)
    assert rrsp["withholding"].iloc[0] == 0.0
    assert marg["withholding"].iloc[0] == 0.0 and marg["withholding_creditable"].iloc[0] > 0
    assert tfsa["total"].iloc[0] == pytest.approx(rrsp["total"].iloc[0] - 0.15 * 0.6 * 0.004)


def test_sim_short_borrow_and_financing():
    idx = pd.period_range("2015-01", periods=1, freq="M")
    Y = pd.DataFrame({"A": [1.5], "B": [-0.3]}, index=idx)
    mkt = _mkt(idx, {"A": [0.0], "B": [0.0]}, {"A": [50.0], "B": [50.0]})
    meta = {"A": _meta(half_spread_bp=0.0), "B": _meta(half_spread_bp=0.0, borrow_fee_ann=0.01)}
    fr, _ = sim.simulate(Y, mkt, meta, _acct())
    C = 1 - 1.2
    assert fr["cash_interest"].iloc[0] == pytest.approx(C * (0.03 + 0.02) / 12)
    assert fr["borrow"].iloc[0] == pytest.approx(0.01 / 12 * 0.3)


def test_sim_future_no_cash_and_roll():
    idx = pd.period_range("2015-02", periods=2, freq="M")
    Y = pd.DataFrame({"M6E": [0.5, 0.5]}, index=idx)
    fmeta = {"kind": "future", "ccy": "USD", "tick_value": 1.25, "roll_months": [3, 6, 9, 12],
             "commission": {"type": "per_contract", "per_contract": 0.77}, "tax_class": "none", "borrow_fee_ann": 0}
    mkt = _mkt(idx, {"M6E": [0.01, 0.0]}, {"M6E": [13_500.0, 13_500.0]})
    fr, q = sim.simulate(Y, mkt, {"M6E": fmeta}, _acct(rounded=True))
    n = sim.round_half_away(np.array([0.5 * 100_000 / 13_500]))[0]
    assert fr["cash_frac"].iloc[0] == 1.0
    assert fr["asset_ret"].iloc[0] == pytest.approx(n * 13_500 / 100_000 * 0.01)
    assert fr["cost_roll"].iloc[0] == 0.0
    assert fr["cost_roll"].iloc[1] == pytest.approx((2 * n * 0.77 + 0.5 * 1.25 * 2 * n) / 100_000)


def test_sim_held_without_return_raises():
    idx = pd.period_range("2015-01", periods=1, freq="M")
    Y = pd.DataFrame({"A": [0.5]}, index=idx)
    mkt = _mkt(idx, {"A": [np.nan]}, {"A": [10.0]})
    with pytest.raises(ValueError):
        sim.simulate(Y, mkt, {"A": _meta()}, _acct())


# ------------------------------------------------------------------------------------------------ data helpers
def test_raw_close_and_period_sum():
    idx = pd.bdate_range("2020-01-01", "2020-03-31")
    close = pd.DataFrame({"USO": 10.0}, index=idx)
    splits = pd.DataFrame({"USO": [0.125]}, index=[pd.Timestamp("2020-02-03")])
    raw = vdata.raw_close(close, splits)
    assert raw.loc["2020-01-15", "USO"] == pytest.approx(1.25) and raw.loc["2020-02-10", "USO"] == 10.0
    d = pd.DataFrame({"X": 0.0}, index=idx)
    d.loc["2020-01-01", "X"] = 1.0     # first session of Jan -> belongs to Dec's period
    d.loc["2020-01-20", "X"] = 2.0
    d.loc["2020-02-03", "X"] = 4.0     # first session of Feb -> Jan's period
    s = vdata.period_sum(d)["X"]
    assert s[P("2020-01")] == pytest.approx(6.0)


# ------------------------------------------------------------------------------------------------ guards + e2e
@pytest.fixture
def ledgers(tmp_path, monkeypatch):
    pre = tmp_path / "prereg.md"
    pre.write_text("| UTC | Kind | ID | File | SHA-256 | Note |\n|---|---|---|---|---|---|\n")
    trial = tmp_path / "trial.csv"
    monkeypatch.setenv("CYCLE6_TEST_PREREG_LEDGER", str(pre))
    monkeypatch.setenv("CYCLE6_TEST_TRIAL_LEDGER", str(trial))
    monkeypatch.delenv("QUANT_DATA_MANIFEST_SHA256", raising=False)
    return pre, trial


def _long(df):
    s = df.stack()
    o = s.rename("value").reset_index()
    o.columns = ["date", "market_id", "value"]
    return o


def make_view(tmp_path, book_spec_sha="b" * 64):
    from research.data_snapshot import canonical
    rng = np.random.default_rng(7)
    vdir = tmp_path / "store" / "versions" / "v1"
    view = vdir / "view"
    t = view / "trade"
    (t / "inputs" / "book").mkdir(parents=True)
    (t / "inputs" / "components" / "A").mkdir(parents=True)
    idx = pd.bdate_range("2008-01-01", "2012-12-31")
    px = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.01, (len(idx), 3)), axis=0)), index=idx,
                      columns=["SPY", "IEF", "FXE"])
    px.loc[: "2009-06-30", "FXE"] = np.nan
    _long(px).to_parquet(t / "adj.parquet", index=False)
    _long(px).to_parquet(t / "close.parquet", index=False)
    _long(pd.DataFrame({"SPY": [0.5]}, index=[pd.Timestamp("2010-03-19")])).to_parquet(t / "div.parquet", index=False)
    _long(pd.DataFrame({"IEF": [2.0]}, index=[pd.Timestamp("2011-01-03")])).to_parquet(t / "split.parquet", index=False)
    _long(pd.DataFrame({"GC=F": 1200.0}, index=idx)).to_parquet(t / "lev.parquet", index=False)
    _long(pd.DataFrame({"USDCAD": 1.1 + 0.05 * np.sin(np.arange(len(idx)) / 50)}, index=idx)).to_parquet(
        t / "usdcad.parquet", index=False)
    _long(pd.DataFrame({"TB3M": 0.01}, index=idx)).to_parquet(t / "tb.parquet", index=False)
    me = pd.date_range("2007-12-31", "2012-12-31", freq="ME")
    _long(pd.DataFrame({"FX_CAD": 0.015}, index=me)).to_parquet(t / "cad.parquet", index=False)
    _long(pd.DataFrame({"FX_EUR": 1.3}, index=me)).to_parquet(t / "spot.parquet", index=False)
    fx = pd.DataFrame(rng.normal(0, 0.005, (len(idx), 2)), index=idx, columns=["FX_EUR", "FX_NOK"])
    _long(fx).to_parquet(t / "fxpanel.parquet", index=False)
    core = px[["SPY", "IEF"]].pct_change().fillna(0.0) - 0.01 / 252
    _long(core).to_parquet(t / "core.parquet", index=False)
    months = pd.period_range("2008-02", "2012-11", freq="M")
    bw = pd.concat([pd.DataFrame({"month": months.astype(str), "sleeve": "A", "erc_weight": 0.5, "scaled_weight": 0.8}),
                    pd.DataFrame({"month": months.astype(str), "sleeve": "CORE", "erc_weight": 0.5, "scaled_weight": 0.6})])
    bw.to_csv(t / "inputs" / "book" / "weights.csv", index=False)
    bk = pd.DataFrame({"month": months.astype(str), "sleeve_ret": rng.normal(0, 0.01, len(months))})
    bk["excess"] = bk["sleeve_ret"]
    bk.to_csv(t / "inputs" / "book" / "book.csv", index=False)
    (t / "inputs" / "book" / "metrics.json").write_text(json.dumps(
        {"run": {"spec_sha256": book_spec_sha}, "sleeves": {"A": {"included": True}, "CORE": {"included": True},
                                                           "Z": {"included": False}}}))
    sm = pd.period_range("2008-01", "2012-10", freq="M").astype(str)
    cw = pd.concat([pd.DataFrame({"signal_month": sm, "market_id": "FX_EUR",
                                  "weight": np.where(np.arange(len(sm)) % 3 == 0, -1.0, 1.0)}),
                    pd.DataFrame({"signal_month": sm, "market_id": "FX_NOK", "weight": 0.5})])
    cw.to_parquet(t / "inputs" / "components" / "A" / "weights.parquet", index=False)
    pd.DataFrame({"vehicle": ["SPY", "IEF", "FXE", "FXS", "M6E"], "data_status": ["OK", "OK", "OK", "UNAVAILABLE", "OK"]}
                 ).to_csv(t / "vehicle_universe.csv", index=False)
    payload = {"schema_version": 1, "dataset_version": "v1", "records": []}
    sha = hashlib.sha256(canonical(payload)).hexdigest()
    (vdir / "manifest.json").write_text(json.dumps({"manifest_sha256": sha, "payload": payload}))
    return view, sha


def make_params(snap_sha, variant="MARGIN", book_spec_sha="b" * 64):
    etf = lambda ccy="USD", tc="us_ric": {"kind": "etf", "ccy": ccy, "half_spread_bp": 1.0, "tax_class": tc,
                                          "borrow_fee_ann": 0.003,
                                          "commission": {"type": "per_share", "per_share": 0.005, "min": 1.0, "max_pct": 0.01}}
    vehicles = {"SPY": etf(), "IEF": etf(), "FXE": etf(tc="none"), "FXS": etf(tc="none"),
                "M6E": {"kind": "future", "ccy": "USD", "tick_value": 1.25, "multiplier": 12500, "from": "2011-01",
                        "roll_months": [3, 6, 9, 12], "commission": {"type": "per_contract", "per_contract": 0.77},
                        "tax_class": "none", "borrow_fee_ann": 0.0,
                        "proxy": {"path": "trade/fxpanel.parquet", "market_id": "FX_EUR"},
                        "sizing": {"source": "fx_spot", "series": "FX_EUR"}}}
    mp = {"FX_EUR": [{"vehicle": "M6E", "from": "2011-01"}, {"vehicle": "FXE", "from": None}],
          "FX_NOK": [{"vehicle": None, "reason": "no vehicle"}],
          "CORE:SPY": [{"vehicle": "SPY"}], "CORE:IEF": [{"vehicle": "IEF"}]}
    if variant != "MARGIN":
        vehicles.pop("M6E")
        mp["FX_EUR"] = [{"vehicle": "FXE", "from": None}]
    return {"schema": "cycle6-variant-v1", "id": "TRADE-TEST", "variant": variant,
            "engine_sha256": eg.engine_sha256(), "code_sha256": vguards.code_sha256(),
            "snapshot_manifest_sha256": snap_sha, "book_spec_sha256": book_spec_sha,
            "inputs": {"book_weights": "trade/inputs/book/weights.csv", "book_csv": "trade/inputs/book/book.csv",
                       "book_metrics": "trade/inputs/book/metrics.json",
                       "components": {"A": "trade/inputs/components/A/weights.parquet"},
                       "core": {"sleeve": "CORE", "markets": ["SPY", "IEF"], "weights": [0.6, 0.4]}},
            "data": {"etf_adjclose": "trade/adj.parquet", "etf_close": "trade/close.parquet",
                     "etf_splits": "trade/split.parquet", "etf_dividends": "trade/div.parquet",
                     "fx_spot_monthly": "trade/spot.parquet", "sizing_levels": "trade/lev.parquet",
                     "usdcad": "trade/usdcad.parquet", "tbill": {"path": "trade/tb.parquet", "market_id": "TB3M"},
                     "cad_rate": {"path": "trade/cad.parquet", "market_id": "FX_CAD"},
                     "paper_panels": [{"path": "trade/fxpanel.parquet"},
                                      {"path": "trade/core.parquet", "prefix": "CORE:"}]},
            "long_only": variant != "MARGIN", "gross_cap": 1.0 if variant != "MARGIN" else 2.0,
            "mapping": mp, "vehicles": vehicles,
            "accounts": ({"MARGIN": {"withholding": {}, "creditable": {"us_ric": 0.15}}} if variant == "MARGIN" else
                         {"TFSA": {"withholding": {"us_ric": 0.15}}, "RRSP": {"withholding": {"us_ric": 0.0}}}),
            "costs": {"conv_rate": 0.0003, "cash_spread": 0.005, "financing_spread": 0.02},
            "funding": ["CAD", "USD"], "sizes_cad": [25000, 100000],
            "headline": {"account": "MARGIN" if variant == "MARGIN" else "TFSA", "F": "CAD", "size_cad": 100000},
            "sensitivities": [{"name": "norbert", "conv_rate": 0.0015}, {"name": "spread3x", "spread_mult": 3.0}],
            "post_pub_cutoff": "2010-06", "inference": {"ci_level": 0.9, "ci_B": 49, "seed": 1}}


def write_spec(tmp_path, params, name="TRADE-TEST.md"):
    p = tmp_path / name
    p.write_text("# test spec\n\n```json\n" + json.dumps(params, indent=1) + "\n```\n")
    return p, hashlib.sha256(p.read_bytes()).hexdigest()


def ledger_add(pre, spec_sha, sid="TRADE-TEST"):
    with pre.open("a") as f:
        f.write(f"| 2026-09-26T00:00:00Z | spec | {sid} | x | {spec_sha} | test |\n")


def test_guard_refuses_unledgered_and_bad_code_hash(tmp_path, ledgers):
    pre, trial = ledgers
    view, snap = make_view(tmp_path)
    spec, sha = write_spec(tmp_path, make_params(snap))
    with pytest.raises(vguards.GuardError, match="not in the prereg ledger"):
        vguards.preflight(spec, view, None)
    bad = make_params(snap)
    bad["code_sha256"] = "0" * 64
    spec2, sha2 = write_spec(tmp_path, bad, "bad.md")
    ledger_add(pre, sha2)
    with pytest.raises(vguards.GuardError, match="variant code hash mismatch"):
        vguards.preflight(spec2, view, None)
    wrong_schema = make_params(snap)
    wrong_schema["schema"] = "cycle6-book-v1"
    spec3, sha3 = write_spec(tmp_path, wrong_schema, "ws.md")
    ledger_add(pre, sha3)
    with pytest.raises(vguards.GuardError, match="schema"):
        vguards.preflight(spec3, view, None)
    assert not trial.exists()


@pytest.mark.parametrize("variant", ["MARGIN", "ETF-LF"])
def test_end_to_end_synthetic_and_single_run(tmp_path, ledgers, variant):
    pre, trial = ledgers
    view, snap = make_view(tmp_path)
    spec, sha = write_spec(tmp_path, make_params(snap, variant))
    ledger_add(pre, sha)
    out = tmp_path / "out"
    rc = runner.main(["--spec", str(spec), "--snapshot-root", str(view),
                      "--membership", str(view / "trade" / "vehicle_universe.csv"), "--out", str(out)])
    assert rc == 0
    rows = pd.read_csv(trial)
    assert list(rows["status"]) == ["started", "ok"] and set(rows["kind"]) == {"variant"}
    assert rows["summary"].iloc[1].startswith("code_sha256=")
    m = json.loads((out / "metrics.json").read_text())
    assert m["first_active_month"] == "2008-02"                  # core (SPY/IEF priced in 2008-01) from 2008-02
    assert m["vehicle_first_available_month"]["FXE"] == "2009-08"   # first price 2009-07 -> available 2009-08
    assert m["vehicle_first_available_month"]["FXS"] is None
    hl = m["scenarios"][m["headline"]]
    assert hl["post"]["excess"]["n"] > 12 and "sharpe_ann" in hl["post"]["ci"]
    assert "tracking_vs_paper_book" in m["scenarios"][f"{hl['scenario']['account']}_USD_100000"]
    Y = pd.read_csv(out / "vehicle_targets.csv", index_col=0)
    if variant == "ETF-LF":
        assert (Y >= 0).all().all() and (Y.sum(axis=1) <= 1 + 1e-12).all()
        assert m["scenarios"]["TFSA_CAD_100000"]["full"]["cost_drag_ann"]["withholding"] > 0
        assert m["scenarios"]["RRSP_CAD_100000"]["full"]["cost_drag_ann"]["withholding"] == 0
    else:
        assert (Y.get("FXE", pd.Series(0.0)) < 0).any()           # shorts allowed before the future's from-month
        assert Y.loc["2011-01":, "FXE"].abs().sum() == 0 and Y.loc["2011-01":, "M6E"].abs().sum() > 0
    d = pd.read_csv(out / "dropped.csv")
    assert set(d["instrument"]) == {"FX_NOK", "FX_EUR"}
    assert d.loc[d["instrument"] == "FX_EUR", "month"].max() < "2009-08"   # dropped only before FXE is available
    # a second run of the same spec hash is refused before computing
    with pytest.raises(vguards.GuardError, match="already exists"):
        runner.main(["--spec", str(spec), "--snapshot-root", str(view),
                     "--membership", str(view / "trade" / "vehicle_universe.csv"), "--out", str(tmp_path / "o2")])


def test_book_spec_hash_mismatch_refused(tmp_path, ledgers):
    pre, trial = ledgers
    view, snap = make_view(tmp_path, book_spec_sha="c" * 64)
    spec, sha = write_spec(tmp_path, make_params(snap))
    ledger_add(pre, sha)
    rc = runner.main(["--spec", str(spec), "--snapshot-root", str(view),
                      "--membership", str(view / "trade" / "vehicle_universe.csv"), "--out", str(tmp_path / "o")])
    assert rc == 1
    assert list(pd.read_csv(trial)["status"]) == ["started", "failed"]
