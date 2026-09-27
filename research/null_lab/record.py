"""The project's gated record, read from the files, and formal tests against an all-null world.

Every number below is copied from the cited report/results file; `verify()` re-reads the JSON sources
and fails if any copied value drifts by more than 0.005 (run in tests/test_null_lab.py).

Null centres (what a signal with NO information would score, in Sharpe units):
  ls      market-neutral long-short or spread timing: 0 for the net-edge test; -(gross - net) is the
          no-information mean of the NET Sharpe (cost drag), used for the expected dev-pass count.
  long    long-biased book: the registered control / benchmark in the same window (ETF hybrids: B;
          insider: median same-date random control; streaks: C2; PEAD: all-events control), or the
          beta-implied premium beta * mu_bench / sigma_strategy where only a beta was reported
          (crypto, multi-asset sleeves), or sqrt(active share) * SR_SPY for I4 / A1-A3 (long or short
          on a subset of days).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[2]
R = "reports/"

# SPY excess Sharpe / mean in the windows below, computed from data/multiasset/etf/SPY.parquet with
# research.return_search.run.cash_rates (see REPORT.md): used only for beta-implied centres.
SPY = {"2016-06..2020-12": (0.797, 0.1525), "2021..2026-09": (0.717, 0.1195),
       "2004..2017": (0.478, 0.0877), "2011..2017": (0.965, 0.1361), "2018..2026-09": (0.671, 0.1276)}
IEF_SR_2015_2019 = 0.360      # reports/auction_cycle/dev_results.json ief_excess_sharpe_window

# id, family, kind, dev SR (net base), dev years, dev gross SR, dev gate passed (as recorded),
# val SR, val years, val gross, val one-sided p for EDGE (see notes), c_dev, c_val, source
ROWS = [
    # ---- options H1-H4 (weekly L/S, 287 weeks) --------------------------------------------------
    ("H1", "options", "ls", -0.369, 5.52, 0.073, False, None, None, None, None, 0, 0, R + "options_signals/dev/results.json"),
    ("H2", "options", "ls", -0.914, 5.52, -0.092, False, None, None, None, None, 0, 0, R + "options_signals/dev/results.json"),
    ("H3", "options", "ls", -0.940, 5.52, -0.211, False, None, None, None, None, 0, 0, R + "options_signals/dev/results.json"),
    ("H4", "options", "ls", -1.076, 5.52, -0.307, False, None, None, None, None, 0, 0, R + "options_signals/dev/results.json"),
    # ---- IV changes V1-V3 (monthly L/S, 66 months) ----------------------------------------------
    ("V1", "iv_changes", "ls", -0.285, 5.50, -0.014, False, None, None, None, None, 0, 0, R + "iv_changes/dev/results.json"),
    ("V2", "iv_changes", "ls", -1.007, 5.50, -0.737, False, None, None, None, None, 0, 0, R + "iv_changes/dev/results.json"),
    ("V3", "iv_changes", "ls", -1.688, 5.50, -1.357, False, None, None, None, None, 0, 0, R + "iv_changes/dev/results.json"),
    # ---- put writing P1-P3 ------------------------------------------------------------------------
    ("P1", "putwrite", "ls", 0.213, 5.60, 0.445, False, None, None, None, None, 0, 0, R + "putwrite/dev/results.json"),
    ("P2", "putwrite", "ls", 0.155, 5.60, 0.335, False, None, None, None, None, 0, 0, R + "putwrite/dev/results.json"),
    ("P3", "putwrite", "ls", 0.040, 5.60, 0.389, False, None, None, None, None, 0, 0, R + "putwrite/dev/results.json"),
    # ---- COT C1-C3 (weekly L/S commodity ETFs, 2015-2019) ----------------------------------------
    ("C1", "cot", "ls", 0.250, 5.0, 0.945, False, None, None, None, None, 0, 0, R + "cot/dev/results.json"),
    ("C2", "cot", "ls", 0.327, 5.0, 0.397, False, None, None, None, None, 0, 0, R + "cot/dev/results.json"),
    ("C3", "cot", "ls", 0.047, 5.0, 0.562, False, None, None, None, None, 0, 0, R + "cot/dev/results.json"),
    # ---- intraday I1-I4 ---------------------------------------------------------------------------
    ("I1", "intraday", "ls", -0.121, 4.53, 0.309, False, None, None, None, None, 0, 0, R + "intraday/dev/results.json"),
    ("I2", "intraday", "ls", 0.376, 4.53, 0.803, False, None, None, None, None, 0, 0, R + "intraday/dev/results.json"),
    ("I3", "intraday", "ls", -0.957, 2.95, -0.496, False, None, None, None, None, 0, 0, R + "intraday/dev/results.json"),
    ("I4", "intraday", "long", 0.554, 4.53, 0.593, True, -0.092, 5.64, -0.062, 0.591,
     round(np.sqrt(92 / 1141) * SPY["2016-06..2020-12"][0], 3), round(np.sqrt(108 / 1421) * SPY["2021..2026-09"][0], 3),
     R + "intraday/{dev,validation}/results.json"),
    # ---- LETF L1-L2 -------------------------------------------------------------------------------
    ("L1", "letf", "ls", 0.395, 4.53, 0.521, False, None, None, None, None, 0, 0, R + "letf_rebalancing/dev/results.json"),
    ("L2", "letf", "ls", 0.478, 4.53, 0.693, False, None, None, None, None, 0, 0, R + "letf_rebalancing/dev/results.json"),
    # ---- rebalancing R1-R3 (SPY-IEF spread timing) --------------------------------------------------
    ("R1", "rebalancing", "ls", 0.470, 11.90, 0.644, False, None, None, None, None, 0, 0, R + "rebalancing/dev_results.json"),
    ("R2", "rebalancing", "ls", 0.743, 11.90, 0.902, True, 0.627, 11.69, 0.758, 0.108, 0, 0, R + "rebalancing/{dev,validation}_results.json"),
    ("R3", "rebalancing", "ls", 0.823, 11.90, 1.030, True, 0.454, 11.69, 0.668, 0.126, 0, 0, R + "rebalancing/{dev,validation}_results.json"),
    # ---- auction A1-A3 (IEF timing: A1 short 66% of days, A2 long 26%, A3 both) -------------------
    ("A1", "auction", "long", -0.234, 4.99, -0.007, False, None, None, None, None,
     round(-np.sqrt(832 / 1258) * IEF_SR_2015_2019, 3), 0, R + "auction_cycle/dev_results.json"),
    ("A2", "auction", "long", 0.026, 4.99, 0.365, False, None, None, None, None,
     round(np.sqrt(325 / 1258) * IEF_SR_2015_2019, 3), 0, R + "auction_cycle/dev_results.json"),
    ("A3", "auction", "long", -0.180, 4.99, 0.197, False, None, None, None, None,
     round(-(507 / 1258) / np.sqrt(1157 / 1258) * IEF_SR_2015_2019, 3), 0, R + "auction_cycle/dev_results.json"),
    # ---- FX carry/IV F2-F3 (F1 is the registered baseline, not a candidate) ----------------------
    ("FX2", "fx_carry_vol", "ls", -0.221, 5.02, -0.173, False, None, None, None, None, 0, 0, R + "fx_carry_vol/dev/results.json"),
    ("FX3", "fx_carry_vol", "ls", -0.333, 5.02, -0.273, False, None, None, None, None, 0, 0, R + "fx_carry_vol/dev/results.json"),
    # ---- insider N1-N4 (long books, beta 1.1-1.3; control = median same-date random draws) ---------
    ("N1", "insider", "long", 0.419, 9.99, 0.502, False, None, None, None, None, 0.360, 0, R + "insider/dev/results.json"),
    ("N2", "insider", "long", 0.416, 9.99, 0.506, False, None, None, None, None, 0.341, 0, R + "insider/dev/results.json"),
    ("N3", "insider", "long", 0.7652, 6.99, 0.867, True, 0.491, 10.46, 0.584, 0.161, 0.711, 0.418, R + "insider/{dev,validation}/results.json"),
    ("N4", "insider", "long", 0.511, 9.99, 0.603, True, 0.511, 10.46, 0.604, 0.078, 0.441, 0.446, R + "insider/{dev,validation}/results.json"),
    # ---- fundamentals F1-F3 (monthly L/S) ------------------------------------------------------------
    ("F1", "fundamentals", "ls", -0.847, 11.9, -0.752, False, None, None, None, None, 0, 0, R + "fundamentals/dev/results.json"),
    ("F2", "fundamentals", "ls", -0.372, 11.9, -0.296, False, None, None, None, None, 0, 0, R + "fundamentals/dev/results.json"),
    ("F3", "fundamentals", "ls", -0.634, 11.9, -0.538, False, None, None, None, None, 0, 0, R + "fundamentals/dev/results.json"),
    # ---- ETF hybrids E1-E5 (long-only; benchmark B dev 0.535, val 0.546; gate also needs > B) ------
    ("E1", "etf_hybrids", "long", 0.663, 11.99, 0.679, True, 0.377, 11.69, 0.394, 0.961, 0.535, 0.546, R + "etf_hybrids/{dev,validation}/results.json"),
    ("E2", "etf_hybrids", "long", 0.570, 11.99, 0.584, True, 0.442, 11.69, 0.459, 0.821, 0.535, 0.546, R + "etf_hybrids/{dev,validation}/results.json"),
    ("E3", "etf_hybrids", "long", 0.470, 11.99, 0.496, False, None, None, None, None, 0.535, 0, R + "etf_hybrids/dev/results.json"),
    ("E4", "etf_hybrids", "long", 0.505, 11.99, 0.520, False, None, None, None, None, 0.535, 0, R + "etf_hybrids/dev/results.json"),
    ("E5", "etf_hybrids", "long", 0.412, 11.99, 0.448, False, None, None, None, None, 0.535, 0, R + "etf_hybrids/dev/results.json"),
    # ---- PEAD streaks S1 (L/S), S2 (long; gate needs > control C2 0.833) ---------------------------
    ("S1", "pead_streak", "ls", 0.128, 5.99, 0.461, False, None, None, None, None, 0, 0, R + "pead_streak/dev/results.json"),
    ("S2", "pead_streak", "long", 0.791, 5.99, 0.929, False, None, None, None, None, 0.833, 0, R + "pead_streak/dev/results.json"),
    # ---- macro surprise M1 (M2 never eligible) -------------------------------------------------------
    ("M1", "macro_surprise", "ls", -0.503, 5.67, -0.196, False, None, None, None, None, 0, 0, R + "macro_surprise/dev/results.json"),
    # ---- multi-asset book (5 sleeves; beta 0.07) ----------------------------------------------------
    ("MA", "multiasset", "ls", 0.574, 13.39, None, True, -0.024, 8.69, None,
     float(1 - norm.cdf(-0.024 * np.sqrt(8.69))),
     round(0.071 * SPY["2004..2017"][1] / 0.1012, 3), 0, R + "multiasset/dev_results.json, holdout/results.json"),
    # ---- crypto trend (gate 0.30 over >= 3y; best to hold-out; beta-implied centres vs BTC) --------
    ("CR1", "crypto", "long", 0.490, 7.13, None, False, 0.131, 4.72, None, None,
     round(0.092 * 0.9305 / 0.3895, 3), round(-0.105 * 0.2005 / 0.3482, 3), R + "multiasset/crypto/*_results.json"),
    ("CR2", "crypto", "long", 1.114, 6.25, None, False, 0.170, 4.72, None, None,
     round(0.253 * 0.9305 / 0.3328, 3), round(-0.059 * 0.2005 / 0.2487, 3), R + "multiasset/crypto/*_results.json"),
    ("CR3", "crypto", "long", 1.241, 6.17, None, True, 0.397, 4.72, None, None,
     round(0.291 * 0.9305 / 0.317, 3), round(0.158 * 0.2005 / 0.1736, 3), R + "multiasset/crypto/*_results.json"),
]
COLS = ["id", "family", "kind", "dev_sr", "dev_years", "dev_gross", "dev_pass", "val_sr", "val_years", "val_gross",
        "val_p_edge", "c_dev", "c_val", "source"]

# dev -> later-window pairs that were NOT gated at 0.5 but whose later window was run for every
# candidate (selection on dev does not bias a regression of later on dev). Market-neutral: c = 0.
EXTRA_PAIRS = [
    # id, family, dev SR, dev yrs, later SR, later yrs, c_dev, c_val, source
    ("LP_ridge", "liquidity_pressure", 1.006, 4.0, -0.601, 4.49, 0, 0, R + "liquidity_pressure_20260918/results.json"),
    ("LP_gboost", "liquidity_pressure", 0.996, 4.0, -0.413, 4.49, 0, 0, R + "liquidity_pressure_20260918/results.json"),
    ("LP_shock", "liquidity_pressure", 0.489, 4.0, -0.611, 4.49, 0, 0, R + "liquidity_pressure_20260918/results.json"),
    ("LP_pullback", "liquidity_pressure", 0.203, 4.0, -0.690, 4.49, 0, 0, R + "liquidity_pressure_20260918/results.json"),
    ("SC_alphabet", "share_class", -0.941, 6.0, -1.268, 4.49, 0, 0, R + "share_class_20260918/results.json"),
    ("SC_news", "share_class", 0.457, 6.0, -0.852, 4.49, 0, 0, R + "share_class_20260918/results.json"),
    ("SC_fox", "share_class", 0.003, 1.8, -0.693, 4.49, 0, 0, R + "share_class_20260918/results.json"),
    ("EC_SPY_QQQ", "etf_convergence", -0.217, 6.0, -0.271, 4.0, 0, 0, R + "etf_convergence_20260918/results.json"),
    ("EC_GLD_SLV", "etf_convergence", -0.297, 6.0, 0.139, 4.0, 0, 0, R + "etf_convergence_20260918/results.json"),
    ("EC_EFA_EEM", "etf_convergence", -0.523, 6.0, 0.226, 4.0, 0, 0, R + "etf_convergence_20260918/results.json"),
    ("EC_LQD_IEF", "etf_convergence", -0.049, 6.0, -2.312, 4.0, 0, 0, R + "etf_convergence_20260918/results.json"),
    ("FXS_london", "fx_session", -0.35, 4.0, -0.92, 4.0, 0, 0, R + "edge_search_20260918/REPORT.md"),
    ("FXS_newyork", "fx_session", -1.98, 4.0, -0.84, 4.0, 0, 0, R + "edge_search_20260918/REPORT.md"),
    ("MA_fx_carry", "multiasset_sleeve", 0.449, 8.9, 0.247, 8.69, 0, 0, R + "multiasset/{dev_results,holdout/results}.json"),
    ("MA_bond_carry", "multiasset_sleeve", 0.308, 14.4, 0.132, 8.69, 0, 0, R + "multiasset/{dev_results,holdout/results}.json"),
    ("MA_tsmom_broad", "multiasset_sleeve", 0.471, 13.9, 0.212, 8.69, 0, 0, R + "multiasset/{dev_results,holdout/results}.json"),
    ("MA_vix_basis", "multiasset_sleeve", 0.983, 6.98, 0.287, 8.69,
     round(2.751 * SPY["2011..2017"][1] / 0.5619, 3), round(2.751 * SPY["2018..2026-09"][1] / 0.5619, 3),
     R + "multiasset/{dev_results,holdout/results}.json"),
    ("MA_on_intraday_rev", "multiasset_sleeve", 0.300, 13.98, -0.587, 8.69, 0, 0, R + "multiasset/{dev_results,holdout/results}.json"),
    ("PEAD", "pead", 0.700, 3.9, 0.520, 11.0, 0.600, 0.360, R + "pead_2004_2014 + ledger row 1"),
]


def table() -> pd.DataFrame:
    return pd.DataFrame(ROWS, columns=COLS)


def pairs(extended: bool = True) -> pd.DataFrame:
    t = table()
    core = t[t.val_sr.notna()][["id", "family", "dev_sr", "dev_years", "val_sr", "val_years", "c_dev", "c_val", "source"]]
    core = core.assign(set="core")
    if not extended:
        return core.reset_index(drop=True)
    ex = pd.DataFrame(EXTRA_PAIRS, columns=["id", "family", "dev_sr", "dev_years", "val_sr", "val_years", "c_dev", "c_val", "source"])
    return pd.concat([core, ex.assign(set="extra")], ignore_index=True)


# -- verification against the JSON files -------------------------------------------------------------
def _j(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def verify(tol: float = 0.005) -> list[str]:
    """Re-read every JSON-backed number; return a list of mismatches (empty = all good)."""
    bad = []

    def chk(name, got, want):
        if want is None or got is None or abs(float(got) - float(want)) > tol:
            bad.append(f"{name}: file {got} vs table {want}")
    t = table().set_index("id")
    o = _j(R + "options_signals/dev/results.json")["candidates"]
    for i, k in zip(["H1", "H2", "H3", "H4"], ["H1_os", "H2_ivspread", "H3_skew", "H4_composite"]):
        chk(i, o[k]["base"]["sharpe_net"], t.loc[i, "dev_sr"]); chk(i + "g", o[k]["base"]["sharpe_gross"], t.loc[i, "dev_gross"])
    v = _j(R + "iv_changes/dev/results.json")["candidates"]
    for i, k in zip(["V1", "V2", "V3"], ["V1_dcall", "V2_dput", "V3_dspread"]):
        chk(i, v[k]["base"]["sharpe_net"], t.loc[i, "dev_sr"])
    p = _j(R + "putwrite/dev/results.json")["candidates"]
    for i, k in zip(["P1", "P2", "P3"], ["P1_spy", "P2_spy_vrp", "P3_etf3"]):
        chk(i, p[k]["base"]["sharpe_net"], t.loc[i, "dev_sr"])
    c = _j(R + "cot/dev/results.json")["candidates"]
    for i, k in zip(["C1", "C2", "C3"], ["C1_liquidity", "C2_hedging_pressure", "C3_two_premiums"]):
        chk(i, c[k]["base"]["sharpe_net"], t.loc[i, "dev_sr"])
    d = _j(R + "intraday/dev/results.json")["candidates"]
    for i, k in zip(["I1", "I2", "I3", "I4"], ["I1_intraday_momentum", "I2_rest_of_day", "I3_ml_lgbm", "I4_announcement_day"]):
        chk(i, d[k]["base"]["sharpe_net"], t.loc[i, "dev_sr"])
    chk("I4v", _j(R + "intraday/validation/results.json")["candidates"]["I4_announcement_day"]["base"]["sharpe_net"], t.loc["I4", "val_sr"])
    le = _j(R + "letf_rebalancing/dev/results.json")["candidates"]
    chk("L1", le["L1_flow_top_quintile"]["base"]["sharpe_net"], t.loc["L1", "dev_sr"])
    chk("L2", le["L2_flow_scaled"]["base"]["sharpe_net"], t.loc["L2", "dev_sr"])
    rd, rv = _j(R + "rebalancing/dev_results.json")["candidates"], _j(R + "rebalancing/validation_results.json")["candidates"]
    for i, k in zip(["R1", "R2", "R3"], ["R1_calendar", "R2_threshold", "R3_combined"]):
        chk(i, rd[k]["sharpe"], t.loc[i, "dev_sr"])
    chk("R2v", rv["R2_threshold"]["sharpe"], t.loc["R2", "val_sr"]); chk("R3v", rv["R3_combined"]["sharpe"], t.loc["R3", "val_sr"])
    chk("R2p", rv["R2_threshold"]["p_one_sided"], t.loc["R2", "val_p_edge"]); chk("R3p", rv["R3_combined"]["p_one_sided"], t.loc["R3", "val_p_edge"])
    a = _j(R + "auction_cycle/dev_results.json")["candidates"]
    for i, k in zip(["A1", "A2", "A3"], ["A1_pre_short", "A2_post_long", "A3_combined"]):
        chk(i, a[k]["sharpe"], t.loc[i, "dev_sr"])
    f = _j(R + "fx_carry_vol/dev/results.json")["strategies"]
    chk("FX2", f["F2_carry_to_vol"]["base"]["sharpe_net"], t.loc["FX2", "dev_sr"])
    chk("FX3", f["F3_carry_to_vol_targeted"]["base"]["sharpe_net"], t.loc["FX3", "dev_sr"])
    nd, nv = _j(R + "insider/dev/results.json")["candidates"], _j(R + "insider/validation/results.json")["candidates"]
    for i, k in zip(["N1", "N2", "N3", "N4"], ["N1_cluster", "N2_csuite", "N3_opportunistic", "N4_composite"]):
        chk(i, nd[k]["base"]["sharpe"], t.loc[i, "dev_sr"])
        chk(i + "c", nd[k]["control"]["control_sharpe_median"], t.loc[i, "c_dev"])
    for i, k in zip(["N3", "N4"], ["N3_opportunistic", "N4_composite"]):
        chk(i + "v", nv[k]["base"]["sharpe"], t.loc[i, "val_sr"])
        chk(i + "vc", nv[k]["control"]["control_sharpe_median"], t.loc[i, "c_val"])
        chk(i + "vp", nv[k]["control"]["paired_p_one_sided"], t.loc[i, "val_p_edge"])
    fu = _j(R + "fundamentals/dev/results.json")
    for i, k in zip(["F1", "F2", "F3"], ["F1_issuance", "F2_consistency", "F3_combined"]):
        chk(i, fu[k]["sharpe_net"], t.loc[i, "dev_sr"])
    ed, evv = _j(R + "etf_hybrids/dev/results.json")["candidates"], _j(R + "etf_hybrids/validation/results.json")["candidates"]
    for i in ["E1", "E2", "E3", "E4", "E5"]:
        chk(i, ed[i]["sharpe_net"], t.loc[i, "dev_sr"]); chk(i + "b", ed[i]["bench_sharpe_net"], t.loc[i, "c_dev"])
    for i in ["E1", "E2"]:
        chk(i + "v", evv[i]["sharpe_net"], t.loc[i, "val_sr"]); chk(i + "vb", evv[i]["bench_sharpe_net"], t.loc[i, "c_val"])
        chk(i + "vp", evv[i]["paired_sharpe_p_vs_B"], t.loc[i, "val_p_edge"])
    s = _j(R + "pead_streak/dev/results.json")["books"]
    chk("S1", s["S1_streak_ls"]["base"]["sharpe"], t.loc["S1", "dev_sr"]); chk("S2", s["S2_streak_long"]["base"]["sharpe"], t.loc["S2", "dev_sr"])
    chk("S2c", s["C2_all_long"]["base"]["sharpe"], t.loc["S2", "c_dev"])
    chk("M1", _j(R + "macro_surprise/dev/results.json")["books"]["M1"]["base"]["excess_sharpe"], t.loc["M1", "dev_sr"])
    chk("MA", _j(R + "multiasset/dev_results.json")["book"]["sharpe"], t.loc["MA", "dev_sr"])
    chk("MAv", _j(R + "multiasset/holdout/results.json")["primary"]["sharpe"], t.loc["MA", "val_sr"])
    cd, ch = _j(R + "multiasset/crypto/dev_results.json")["candidates"], _j(R + "multiasset/crypto/holdout_results.json")["all_candidates"]
    for i, k in zip(["CR1", "CR2", "CR3"], ["crypto_tsmom_1w", "crypto_tsmom_multi", "crypto_trend_long_only"]):
        chk(i, cd[k]["sharpe"], t.loc[i, "dev_sr"]); chk(i + "v", ch[k]["sharpe"], t.loc[i, "val_sr"])
    lp = _j(R + "liquidity_pressure_20260918/results.json")
    sc = _j(R + "share_class_20260918/results.json")
    ec = _j(R + "etf_convergence_20260918/results.json")
    ex = {e[0]: e for e in EXTRA_PAIRS}
    for i, k in [("LP_ridge", "ridge"), ("LP_gboost", "gradient_boost"), ("LP_shock", "liquidity_shock"), ("LP_pullback", "trend_pullback")]:
        chk(i, lp[k]["base"]["selection"]["excess_sharpe"], ex[i][2]); chk(i + "v", lp[k]["base"]["evaluation"]["excess_sharpe"], ex[i][4])
    for i, k in [("SC_alphabet", "alphabet"), ("SC_news", "news"), ("SC_fox", "fox")]:
        chk(i, sc[k]["base"]["development"]["excess_sharpe"], ex[i][2]); chk(i + "v", sc[k]["base"]["evaluation"]["excess_sharpe"], ex[i][4])
    for i, k in [("EC_SPY_QQQ", "SPY_QQQ"), ("EC_GLD_SLV", "GLD_SLV"), ("EC_EFA_EEM", "EFA_EEM"), ("EC_LQD_IEF", "LQD_IEF")]:
        chk(i, ec[k]["base"]["development"]["excess_sharpe"], ex[i][2]); chk(i + "v", ec[k]["base"]["validation"]["excess_sharpe"], ex[i][4])
    md, mh = _j(R + "multiasset/dev_results.json")["sleeves"], _j(R + "multiasset/holdout/results.json")["sleeves"]
    for i, k in [("MA_fx_carry", "fx_carry"), ("MA_bond_carry", "bond_carry"), ("MA_tsmom_broad", "tsmom_broad"),
                 ("MA_vix_basis", "vix_basis"), ("MA_on_intraday_rev", "overnight_intraday_reversal")]:
        chk(i, md[k]["raw"]["sharpe"], ex[i][2]); chk(i + "v", mh[k]["sharpe"], ex[i][4])
    return bad


# -- formal tests -------------------------------------------------------------------------------------
def _poisson_binomial_sf(p: np.ndarray, k: int) -> float:
    """P(sum of independent Bernoulli(p_i) >= k)."""
    dist = np.zeros(len(p) + 1)
    dist[0] = 1.0
    for q in p:
        dist[1:] = dist[1:] * (1 - q) + dist[:-1] * q
        dist[0] *= (1 - q)
    return float(dist[k:].sum())


def dev_stage(kappa: float = 1.0, gate: float = 0.5) -> dict:
    """Is the observed number of development passes / high dev Sharpes consistent with all-null?"""
    t = table()
    T = t.dev_years.to_numpy()
    se = kappa / np.sqrt(T)
    cost = (t.dev_gross - t.dev_sr).fillna(0.0).clip(lower=0).to_numpy()
    c = t.c_dev.to_numpy(float)
    # null distribution of the NET dev Sharpe: N(c - cost drag, se^2)
    p_null = 1 - norm.cdf((gate - (c - cost)) / se)
    obs_sr = int((t.dev_sr >= gate).sum())
    obs_pass = int(t.dev_pass.sum())
    z_net = (t.dev_sr.to_numpy() - c) / se                               # net edge vs beta-aware centre
    z_gross = (t.dev_gross.fillna(t.dev_sr).to_numpy() - c) / se         # informativeness before costs
    n = len(t)
    out = {"n_candidates": n, "kappa": kappa,
           "observed_dev_sr_ge_gate": obs_sr, "observed_recorded_dev_passes": obs_pass,
           "expected_under_null": float(p_null.sum()),
           "p_value_obs_sr_ge_gate": _poisson_binomial_sf(p_null, obs_sr),
           "p_value_obs_recorded_passes": _poisson_binomial_sf(p_null, obs_pass),
           "net_z_mean": float(z_net.mean()), "gross_z_mean": float(z_gross.mean()),
           "stouffer_net_p": float(1 - norm.cdf(z_net.sum() / np.sqrt(n))),
           "stouffer_gross_p": float(1 - norm.cdf(z_gross.sum() / np.sqrt(n))),
           "n_net_z_gt_1645": int((z_net > 1.645).sum()), "expected_n_z_gt_1645": 0.05 * n,
           "binom_p_net_z_gt_1645": float(_poisson_binomial_sf(np.full(n, 0.05), int((z_net > 1.645).sum()))),
           "max_net_z": float(z_net.max()), "argmax_net_z": t.id[int(np.argmax(z_net))],
           "sidak_p_max_net_z": float(1 - norm.cdf(z_net.max()) ** n),
           "max_gross_z": float(z_gross.max()), "argmax_gross_z": t.id[int(np.argmax(z_gross))],
           "sidak_p_max_gross_z": float(1 - norm.cdf(z_gross.max()) ** n)}
    by_kind = {}
    for kind in ("ls", "long"):
        m = (t.kind == kind).to_numpy()
        ob = int(t.dev_pass[m].sum())
        by_kind[kind] = {"n": int(m.sum()), "observed_recorded_passes": ob,
                         "observed_dev_sr_ge_gate": int((t.dev_sr[m] >= gate).sum()),
                         "expected_under_null": float(p_null[m].sum()),
                         "p_value_recorded": _poisson_binomial_sf(p_null[m], ob),
                         "p_value_sr_ge_gate": _poisson_binomial_sf(p_null[m], int((t.dev_sr[m] >= gate).sum()))}
    out["by_kind"] = by_kind
    per = t[["id", "kind", "dev_sr", "dev_years", "c_dev"]].assign(
        cost_drag=cost, p_pass_null=p_null, z_net=z_net, z_gross=z_gross)
    return {"summary": out, "per_candidate": per}


def val_stage(kappa: float = 1.0) -> dict:
    """The 9 dev-selected candidates in their later window."""
    t = table()
    v = t[t.val_sr.notna() & t.dev_pass].copy()
    se_v = kappa / np.sqrt(v.val_years.to_numpy())
    z_sr = (v.val_sr.to_numpy() - v.c_val.to_numpy()) / se_v
    # one-sided edge p: reported (bootstrap / paired-vs-control) where it exists, else from z_sr
    p = np.where(v.val_p_edge.notna(), v.val_p_edge.to_numpy(float), 1 - norm.cdf(z_sr))
    z_p = norm.ppf(1 - np.clip(p, 1e-12, 1 - 1e-12))
    n = len(v)
    # expected validation passes if the dev Sharpe were the truth (no shrinkage) vs under null
    p_pass_if_true = 1 - norm.cdf((0.75 - v.dev_sr.to_numpy()) / se_v)
    fisher = -2 * np.log(p).sum()
    from scipy.stats import chi2
    return {
        "n": n, "ids": v.id.tolist(), "kappa": kappa,
        "val_sr": v.val_sr.round(3).tolist(), "c_val": v.c_val.tolist(), "p_edge": np.round(p, 3).tolist(),
        "z_from_p": np.round(z_p, 2).tolist(), "z_sr_vs_centre": np.round(z_sr, 2).tolist(),
        "stouffer_z": float(z_p.sum() / np.sqrt(n)), "stouffer_p": float(1 - norm.cdf(z_p.sum() / np.sqrt(n))),
        "fisher_p": float(chi2.sf(fisher, 2 * n)),
        "min_p": float(p.min()), "argmin_p": v.id.iloc[int(np.argmin(p))],
        "sidak_min_p": float(1 - (1 - p.min()) ** n),
        "observed_val_sr_ge_075": int((v.val_sr >= 0.75).sum()),
        "expected_val_sr_ge_075_if_dev_sr_true": float(p_pass_if_true.sum()),
        "p_zero_of_n_if_dev_sr_true": float(np.prod(1 - p_pass_if_true)),
        "mean_dev_minus_centre": float((v.dev_sr - v.c_dev).mean()),
        "mean_val_minus_centre": float((v.val_sr - v.c_val).mean()),
    }


def shrinkage(kappa: float = 1.0, extended: bool = True, n_boot: int = 20000, seed: int = 7,
              gross: bool = False) -> dict:
    """WLS slope b in (val - c_val) = b * (dev - c_dev) + e, weights = years_val / kappa^2.
    All-null => b = 0; dev Sharpe fully real and stable => b = 1. Selection on dev does not bias b.
    gross=True (core set only): use GROSS Sharpes where both windows report one (cost drag is
    persistent and would otherwise create a positive slope with no edge); books judged against a
    same-cost control (insider, ETF hybrids) stay net-vs-control."""
    pr = pairs(extended)
    x = (pr.dev_sr - pr.c_dev).to_numpy(float)
    y = (pr.val_sr - pr.c_val).to_numpy(float)
    if gross:
        if extended:
            raise ValueError("gross Sharpes exist only for the core set")
        t = table().set_index("id").loc[pr.id]
        use = t.dev_gross.notna().to_numpy() & t.val_gross.notna().to_numpy() & \
            ~t.family.isin(["insider", "etf_hybrids"]).to_numpy()
        x = np.where(use, t.dev_gross.to_numpy(float) - pr.c_dev.to_numpy(float), x)
        y = np.where(use, t.val_gross.to_numpy(float) - pr.c_val.to_numpy(float), y)
    w = pr.val_years.to_numpy(float) / kappa ** 2

    def fit(xx, yy, ww):
        X = np.column_stack([np.ones_like(xx), xx])
        W = np.diag(ww)
        beta = np.linalg.solve(X.T @ W @ X, X.T @ W @ yy)
        return beta

    beta = fit(x, y, w)
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(n_boot):
        i = rng.integers(0, len(x), len(x))
        if np.ptp(x[i]) == 0:
            continue
        bs.append(fit(x[i], y[i], w[i])[1])
    bs = np.array(bs)
    # model-based SE (known noise var kappa^2 / T_val)
    X = np.column_stack([np.ones_like(x), x])
    cov = np.linalg.inv(X.T @ np.diag(w) @ X)
    se_b = float(np.sqrt(cov[1, 1]))
    through0 = float((w * x * y).sum() / (w * x * x).sum())
    se0 = float(1 / np.sqrt((w * x * x).sum()))
    return {"n_pairs": int(len(x)), "extended": extended, "kappa": kappa,
            "intercept": float(beta[0]), "slope": float(beta[1]), "slope_se_model": se_b,
            "slope_ci95_model": [float(beta[1] - 1.96 * se_b), float(beta[1] + 1.96 * se_b)],
            "slope_ci95_boot": [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))],
            "p_slope_gt_0_model": float(1 - norm.cdf(beta[1] / se_b)),
            "p_slope_lt_1_model": float(norm.cdf((beta[1] - 1) / se_b)),
            "slope_through_origin": through0, "slope_through_origin_se": se0,
            "mean_dev_edge": float(x.mean()), "mean_val_edge": float(y.mean())}


def edge_variance(kappa: float = 1.0) -> dict:
    """Method-of-moments variance of true net edges across all dev candidates (tau^2) and the
    implied reliability of a dev Sharpe: tau^2 / (tau^2 + se^2)."""
    t = table()
    se2 = kappa ** 2 / t.dev_years.to_numpy()
    cost = (t.dev_gross - t.dev_sr).fillna(0.0).clip(lower=0).to_numpy()
    e = t.dev_sr.to_numpy() - (t.c_dev.to_numpy() - cost)     # dev Sharpe minus its no-information mean
    tau2 = float(np.var(e, ddof=1) - se2.mean())
    return {"n": len(t), "var_dev_minus_null_mean": float(np.var(e, ddof=1)), "mean_se2": float(se2.mean()),
            "tau2_mom": tau2, "tau_mom": float(np.sqrt(max(tau2, 0.0))),
            "mean_dev_minus_null_mean": float(e.mean()),
            "reliability_at_5_7y": float(max(tau2, 0) / (max(tau2, 0) + kappa ** 2 / 5.7))}
