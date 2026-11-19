"""SPEC section 7 replay: synthetic panel construction and a short-window end-to-end replay (deterministic).

Uses only the frozen cycle-8 inputs (snapshot cycle8_v1 view and reports/cycle8_max_return/out) and writes only to
pytest's tmp_path.
"""
from __future__ import annotations

import csv
import io
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research import data_snapshot
from research.autopilot import make_samples, replay, synth_prices
from research.autopilot.paperlog import PaperLogError, read_chain
from research.autopilot.prices import load_prices, parse_price_csvs

REPO = Path(__file__).resolve().parents[1]
START, END = "2008-06", "2009-06"          # 13 month-ends: includes quarter-ends and a deep drawdown
MATRIX = [("P6a@1.25", "tfsa", 25_000.0), ("P4@1.0", "tfsa", 100_000.0),
          ("P4@1.25", "nonreg_margin", 100_000.0), ("P3@1.5", "nonreg_margin", 100_000.0)]


@pytest.fixture(scope="module")
def built():
    return synth_prices.build(START, END)


@pytest.fixture(scope="module")
def store(built, tmp_path_factory):
    root = tmp_path_factory.mktemp("synth")
    synth_prices.write_sources(root / "src", built)
    manifest = data_snapshot.freeze(synth_prices.snapshot_spec(root / "src", built, "test_synth_v1"),
                                    root / "store")
    return root / "store", "test_synth_v1", manifest["manifest_sha256"]


@pytest.fixture(scope="module")
def result(store, tmp_path_factory):
    out = tmp_path_factory.mktemp("replay")
    res = replay.run(store=store[0], version=store[1], out=out / "out", matrix=MATRIX, log_dir=out / "logs")
    return res, out


def _csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(path.read_text())))


# ------------------------------------------------------------------------------------------------ panel ------------
def test_panel_starts_at_20_and_follows_the_declared_formulas(built):
    px, r, fx = built["panel"], built["returns"], built["usdcad"]
    assert list(px.columns) == sorted(synth_prices.CURRENCY)
    assert (px.iloc[0] == 20.0).all()
    assert px.index[0] == pd.Timestamp("2008-06-30") and px.index[-1] == pd.Timestamp("2009-06-30")
    M, _fxm, _h = synth_prices.load_sleeves()
    W = M.loc[START:END].iloc[1:]
    ret = px.pct_change().iloc[1:]
    cad_ret = (px[["RSSB", "RSST", "GDE"]].mul(fx, axis=0)).pct_change().iloc[1:]
    np.testing.assert_allclose(ret["XEQT.TO"], W["EQ_G_tfsa"], atol=1e-12)
    np.testing.assert_allclose(ret["ZAG.TO"], W["BOND"], atol=1e-12)
    np.testing.assert_allclose(ret["ZGLD.TO"], W["GOLD"], atol=1e-12)
    np.testing.assert_allclose(ret["CASH.TO"], W["CASH"], atol=1e-12)
    np.testing.assert_allclose(ret["DBMF"], W["RF_USD"] + W["X_TREND"], atol=1e-12)
    np.testing.assert_allclose(cad_ret["RSSB"], W["EQ_G_tfsa"] + W["BOND"] - W["CASH"], atol=1e-12)
    np.testing.assert_allclose(cad_ret["RSST"], W["EQ_G_tfsa"] + W["X_TREND"], atol=1e-12)
    np.testing.assert_allclose(cad_ret["GDE"], 0.9 * W["EQ_G_tfsa"] + 0.9 * (W["GOLD"] - W["CASH"]) + 0.1 * W["CASH"],
                               atol=1e-12)
    daily = pd.read_parquet(synth_prices.LETF_SIM)[synth_prices.LETF_COLUMN].loc["2009-03-01":"2009-03-31"]
    np.testing.assert_allclose(ret.loc["2009-03-31", "SSO"], (1 + daily).prod() - 1, atol=1e-12)
    assert r.index.equals(px.index)


def test_panel_csvs_parse_with_the_engine_parser(built):
    series, max_date = parse_price_csvs([("p", built["prices_csv"]), ("f", built["fx_csv"])])
    assert max_date == date(2009, 6, 30)
    assert set(series) == set(synth_prices.CURRENCY) | {"USDCAD"}
    assert all(row[2] == synth_prices.CURRENCY[t] for t, rows in series.items() if t != "USDCAD" for row in rows)
    assert all(row[2] == "CAD" for row in series["USDCAD"])
    assert len(series["XEQT.TO"]) == 13


def test_frozen_snapshot_verifies_and_is_deterministic(built, store, tmp_path):
    prices, err = load_prices(store[0], store[1])
    assert err is None and prices.manifest_sha256 == store[2]
    assert set(prices.keys) == {f"prices/{synth_prices.PRICE_FILE}", f"prices/{synth_prices.FX_FILE}"}
    again = synth_prices.build(START, END)
    assert again["prices_csv"] == built["prices_csv"] and again["fx_csv"] == built["fx_csv"]
    assert again["provenance"] == built["provenance"]


def test_point_in_time_view_never_shows_later_rows(store):
    prices, _ = load_prices(store[0], store[1])
    pit = replay.PointInTime(prices)
    d = date(2008, 12, 31)
    view = pit.at(d)
    assert view.max_date == d
    assert all(r[0] <= d for rows in view.series.values() for r in rows)
    assert view.manifest_sha256 == prices.manifest_sha256


# ------------------------------------------------------------------------------------------------ replay -----------
def test_replay_is_deterministic_byte_for_byte(store, result, tmp_path):
    res, out = result
    again = replay.run(store=store[0], version=store[1], out=tmp_path / "out", matrix=MATRIX,
                       log_dir=tmp_path / "logs")
    for name in res["files"]:
        assert (out / "out" / name).read_bytes() == (tmp_path / "out" / name).read_bytes(), name
    for log in sorted((out / "logs").glob("*.jsonl")):
        assert log.read_bytes() == (tmp_path / "logs" / log.name).read_bytes()
    assert again["meta"]["outputs_sha256"] == res["meta"]["outputs_sha256"]


def test_throwaway_logs_validate_one_line_per_report(result):
    res, out = result
    logs = sorted((out / "logs").glob("*.jsonl"))
    assert len(logs) == len(MATRIX)
    for log in logs:
        chain = read_chain(log)
        assert len(chain) == 13
        assert [e["body"]["report_date"] for e in chain] == sorted(e["body"]["report_date"] for e in chain)
        assert all(e["body"]["kind"] == "autopilot_rebalance_report" for e in chain)
    assert {r["log_entries"] for r in res["meta"]["runs"]} == {13}


def test_by_year_rows_sum_to_summary_totals(result):
    res, out = result
    yearly = _csv(out / "out" / "replay_by_year.csv")
    summary = _csv(out / "out" / "replay_summary.csv")
    assert list(yearly[0]) == replay.BY_YEAR_COLUMNS
    assert len(summary) == len(MATRIX)
    for s in summary:
        ys = [y for y in yearly if (y["config"], y["account"], y["start_cad"]) ==
              (s["config"], s["account"], s["start_cad"])]
        assert [int(y["year"]) for y in ys] == [2008, 2009]
        for col in ("band_events", "calendar_events", "trades", "alerts_info", "alerts_warning", "alerts_breach",
                    "refusals"):
            assert sum(int(y[col]) for y in ys) == int(s[col]), col
        for col in ("turnover_pct_nav", "est_cost_cad", "est_cost_bps", "fx_converted_cad"):
            assert sum(float(y[col]) for y in ys) == pytest.approx(float(s[col]), abs=0.02), col
        assert int(s["reports"]) == 13 and int(s["return_months"]) == 12


def test_accounting_identities_and_account_constraints(result):
    res, _ = result
    rows = res["rows"]
    for r in rows:
        assert r["nav_pre_cad"] - r["nav_post_cad"] == pytest.approx(r["est_cost_cad"], abs=0.021)
        if r["account"] == "tfsa":
            assert r["cash_cad"] >= 0 and r["margin_loan_cad"] == 0 and r["cash_usd"] >= 0
        if r["status"] == "refused":
            assert r["trades"] == 0 and r["turnover_cad"] == 0 and r["est_cost_cad"] == 0
    first = [r for r in rows if r["report_date"] == "2008-06-30" and r["status"] == "accepted"]
    assert first and all(r["triggers"].startswith("band") and r["trades"] > 0 for r in first)
    # every accepted run starts invested: initial turnover about 99% (tfsa) or 99% x L (margin) of NAV
    s = {(x["config"], x["account"]): x for x in res["summary"]}
    assert s[("P4@1.0", "tfsa")]["initial_turnover_pct_nav"] == pytest.approx(99.0, abs=0.5)
    assert s[("P4@1.25", "nonreg_margin")]["initial_turnover_pct_nav"] == pytest.approx(123.75, abs=0.5)


def test_formerly_conflicting_margin_config_now_runs_every_month(result):
    """SPEC section 4 change (2026-09-29): XEQT.TO is capped at its target + 5 pp, so the P3@1.5 margin replay is
    invested (XEQT.TO 89.1%, ZAG.TO 59.4%, loan about 48.5% of NAV) instead of refused and left in cash."""
    res, _ = result
    rows = [r for r in res["rows"] if (r["config"], r["account"]) == ("P3@1.5", "nonreg_margin")]
    assert len(rows) == 13 and all(r["status"] == "accepted" for r in rows)
    assert not any("position_cap" in r["refusal"] for r in rows)
    assert all(r["margin_loan_cad"] > 0.3 * r["nav_post_cad"] for r in rows)
    s = next(x for x in res["summary"] if (x["config"], x["account"]) == ("P3@1.5", "nonreg_margin"))
    assert s["initial_turnover_pct_nav"] == pytest.approx(148.5, abs=0.5) and s["refusals"] == 0


def test_margin_loan_accrues_mrate_between_reports(result):
    res, _ = result
    M, _fx, _h = synth_prices.load_sleeves()
    rows = [r for r in res["rows"] if (r["config"], r["account"]) == ("P4@1.25", "nonreg_margin")]
    checked = 0
    for prev, cur in zip(rows, rows[1:]):
        if cur["trades"] == 0 and prev["margin_loan_cad"] > 0 and prev["cash_usd"] == 0:
            mrate = float(M.loc[cur["report_date"], "MRATE"])
            assert cur["margin_loan_cad"] == pytest.approx(round(prev["margin_loan_cad"] * (1 + mrate), 2), abs=0.01)
            checked += 1
    assert checked >= 1


def test_ideal_comparison_uses_the_same_months(result):
    res, _ = result
    items = pd.read_parquet(replay.ITEM_RETURNS)["P4@1.0"].loc["2008-07-31":"2009-06-30"]
    assert len(items) == 12
    expected = float((1 + items).prod() - 1)
    s = next(x for x in res["summary"] if (x["config"], x["account"]) == ("P4@1.0", "tfsa"))
    assert s["cycle8_ideal_cagr"] == pytest.approx(expected, abs=1e-12)   # 12 return months = 1 year


def test_owner_tolerances_follow_cycle8_answer_table():
    tol = replay.owner_tolerances()
    assert tol["P4@1.0"] == tol["P4@1.25"] == tol["P4@1.5"] == 25
    assert tol["P3@1.0"] == tol["P6a@1.0"] == 35
    assert tol["P6a@1.25"] == 50 and tol["P3@1.25"] == tol["P3@1.5"] == replay.DEFAULT_TOLERANCE_PCT


def test_replay_matrix_matches_the_task():
    m = replay.replay_matrix()
    assert len(m) == 2 * (8 + 5)
    assert {(c, a) for c, a, _ in m if a == "nonreg_margin"} == {(c, "nonreg_margin") for c in replay.MARGIN_CONFIGS}
    assert {s for _c, _a, s in m} == {100_000.0, 25_000.0}


def test_replay_refuses_to_write_under_the_forward_registry(store):
    with pytest.raises(PaperLogError):
        replay.run(store=store[0], version=store[1], out=REPO / "reports" / "forward", matrix=MATRIX[:1])


# ------------------------------------------------------------------------------------------------ samples ----------
def test_sample_price_rows_are_on_or_before_the_sample_dates():
    rows = make_samples.price_rows()
    assert len(rows) == 2 * 10
    for d, t, c, ccy in rows:
        assert d <= make_samples.REPORT_DATE and c > 0
    by_date = {}
    for d, t, _c, _ccy in rows:
        by_date.setdefault(t, []).append(d)
    assert all(len(v) == 2 and min(v) <= make_samples.BUY_DATE for v in by_date.values())


@pytest.mark.parametrize("config_id, account", make_samples.SAMPLES)
def test_hypothetical_holdings_are_at_target_and_never_borrow_in_tfsa(config_id, account):
    rows = make_samples.price_rows()
    h = make_samples.at_target_holdings(config_id, account, rows)
    assert h["as_of"] == make_samples.REPORT_DATE.isoformat()
    assert h["cash_cad"] >= 0 and h["cash_usd"] >= 0
    bare = make_samples.at_target_holdings(config_id, account, rows, carry_income=False)
    assert bare["positions"] == h["positions"] and bare["cash_usd"] == 0
    if account == "tfsa":
        # 1% buffer + one year of distributions (at most a few % of NAV); never a loan
        assert "margin_loan_cad" not in h and bare["cash_cad"] < 0.02 * make_samples.START_CAD
        assert bare["cash_cad"] <= h["cash_cad"] < 0.05 * make_samples.START_CAD
    else:
        assert h["margin_loan_cad"] > 0 and h["cash_cad"] == 0


def test_sample_carry_accrues_margin_interest_then_pays_distributions():
    divs = {"XEQT.TO": [(date(2025, 9, 15), 0.5)], "DBMF": [(date(2025, 10, 10), 1.0)],
            "ZAG.TO": [(date(2025, 8, 29), 9.0)]}                        # on the buy date: not paid to the holder
    mrate = {date(2025, 9, 30): 0.01, date(2025, 10, 31): 0.01}
    cad, usd = make_samples.carry({"XEQT.TO": 100, "DBMF": 10, "ZAG.TO": 5}, -1000.0, (divs, mrate))
    assert cad == pytest.approx((-1000.0 * 1.01 + 50.0) * 1.01)
    assert usd == pytest.approx(10 * 1.0 * (1 - make_samples.US_WITHHOLDING))
    cad, _ = make_samples.carry({"XEQT.TO": 100}, 500.0, (divs, mrate))      # positive cash earns nothing
    assert cad == pytest.approx(550.0)
    real_divs, real_mrate = make_samples.carry_inputs()
    assert min(real_mrate) == date(2025, 9, 30) and max(real_mrate) == make_samples.REPORT_DATE
    assert len(real_mrate) == 12 and all(0 < r < 0.01 for r in real_mrate.values())
    assert all(make_samples.BUY_DATE < d <= make_samples.REPORT_DATE for v in real_divs.values() for d, _ in v)


def test_synthetic_v2_changes_only_gde(built):
    """v2 fixes GDE's collateral income; every other series is identical to the v1 formulas."""
    px, r = built["panel"], built["returns"]
    M, _fxm, _h = synth_prices.load_sleeves()
    W = M.loc[START:END].iloc[1:]
    np.testing.assert_allclose(r["GDE_cad"].iloc[1:] - (0.9 * W["EQ_G_tfsa"] + 0.9 * (W["GOLD"] - W["CASH"])),
                               0.1 * W["CASH"], atol=1e-15)
    assert synth_prices.VERSION == "autopilot_replay_synth_v2" and synth_prices.V1_VERSION == "autopilot_replay_synth_v1"
    assert synth_prices.SOURCE_DIR != synth_prices.V1_SOURCE_DIR
    assert built["provenance"]["supersedes"]["version"] == "autopilot_replay_synth_v1"


def test_frozen_repo_snapshots_verify_when_present():
    for store, version in ((synth_prices.STORE, synth_prices.VERSION), (synth_prices.STORE, synth_prices.V1_VERSION),
                           (make_samples.STORE, make_samples.VERSION)):
        if not (Path(store) / "versions" / version / "manifest.json").exists():
            pytest.skip(f"{version} not frozen in this checkout")
        data_snapshot.verify(Path(store), version, source=True)
