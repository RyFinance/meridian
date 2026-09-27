"""Explicit file/column map for every daily or event-cycle return series used
in the M_eff (effective-number-of-independent-tests) correlation analysis.

Column names differ across families (net/active/base/G/B/M/excess/a bare '0'
for an unnamed column, or entry/signal_date-indexed option-cycle files), so
this is a hand-verified list rather than a heuristic column-sniffer -- each
entry was checked against the file's actual header (see the historian
session notes / build.py docstring) before being added. Every series is
loaded read-only and reduced to a monthly SUM of its return column
(data_sources.load_series_monthly) purely to get a common grid for a
correlation matrix; no performance statistic is computed or reported from
these loads.

`window` is "dev" or "validation" so the M_eff report can (and does) keep
development-stage and validation-stage series from the same family in
separate figures where useful, though the main event correlates everything
available within a family together.
"""
from __future__ import annotations

SERIES = [
    # --- auction_cycle ---
    dict(id="auction_cycle/A1_dev", family_id="auction_cycle(A1-A3)", window="dev",
         path="reports/auction_cycle/dev_A1_pre_short_daily.csv", date_col="date", value_col="net"),
    dict(id="auction_cycle/A2_dev", family_id="auction_cycle(A1-A3)", window="dev",
         path="reports/auction_cycle/dev_A2_post_long_daily.csv", date_col="date", value_col="net"),
    dict(id="auction_cycle/A3_dev", family_id="auction_cycle(A1-A3)", window="dev",
         path="reports/auction_cycle/dev_A3_combined_daily.csv", date_col="date", value_col="net"),

    # --- commodity_roll ---
    dict(id="commodity_roll/dev", family_id="commodity_roll", window="dev",
         path="reports/commodity_roll/dev_daily.csv", date_col="date", value_col="base"),
    dict(id="commodity_roll/validation", family_id="commodity_roll", window="validation",
         path="reports/commodity_roll/validation_daily.csv", date_col="date", value_col="base"),

    # --- credit_gate ---
    dict(id="credit_gate/dev", family_id="credit_gate(G)", window="dev",
         path="reports/credit_gate/dev_daily_base.csv", date_col="date", value_col="G"),

    # --- etf_basis ---
    dict(id="etf_basis/dev", family_id="etf_basis(B)", window="dev",
         path="reports/etf_basis/dev_daily.csv", date_col="date", value_col="B"),

    # --- insider ---
    dict(id="insider/N1_dev", family_id="insider(N1-N4)", window="dev",
         path="reports/insider/dev/N1_cluster_daily.csv", date_col="date", value_col="net"),
    dict(id="insider/N2_dev", family_id="insider(N1-N4)", window="dev",
         path="reports/insider/dev/N2_csuite_daily.csv", date_col="date", value_col="net"),
    dict(id="insider/N3_dev", family_id="insider(N1-N4)", window="dev",
         path="reports/insider/dev/N3_opportunistic_daily.csv", date_col="date", value_col="net"),
    dict(id="insider/N4_dev", family_id="insider(N1-N4)", window="dev",
         path="reports/insider/dev/N4_composite_daily.csv", date_col="date", value_col="net"),
    dict(id="insider/N3_val", family_id="insider(N1-N4)", window="validation",
         path="reports/insider/validation/N3_opportunistic_daily.csv", date_col="date", value_col="net"),
    dict(id="insider/N4_val", family_id="insider(N1-N4)", window="validation",
         path="reports/insider/validation/N4_composite_daily.csv", date_col="date", value_col="net"),

    # --- intraday ---
    dict(id="intraday/I1_dev", family_id="intraday(I1-I4)", window="dev",
         path="reports/intraday/dev/I1_intraday_momentum_base_daily.csv", date_col="date", value_col="0"),
    dict(id="intraday/I2_dev", family_id="intraday(I1-I4)", window="dev",
         path="reports/intraday/dev/I2_rest_of_day_base_daily.csv", date_col="date", value_col="0"),
    dict(id="intraday/I3_dev", family_id="intraday(I1-I4)", window="dev",
         path="reports/intraday/dev/I3_ml_lgbm_base_daily.csv", date_col="date", value_col="0"),
    dict(id="intraday/I4_dev", family_id="intraday(I1-I4)", window="dev",
         path="reports/intraday/dev/I4_announcement_day_base_daily.csv", date_col="date", value_col="0"),
    dict(id="intraday/I4_val", family_id="intraday(I1-I4)", window="validation",
         path="reports/intraday/validation/I4_announcement_day_base_daily.csv", date_col="date", value_col="0"),

    # --- letf_rebalancing ---
    dict(id="letf_rebalancing/L1_dev", family_id="letf_rebalancing(L1-L2)", window="dev",
         path="reports/letf_rebalancing/dev/L1_flow_top_quintile_base_daily.csv", date_col="date", value_col="0"),
    dict(id="letf_rebalancing/L2_dev", family_id="letf_rebalancing(L1-L2)", window="dev",
         path="reports/letf_rebalancing/dev/L2_flow_scaled_base_daily.csv", date_col="date", value_col="0"),

    # --- macro_surprise (candidates + its own controls) ---
    dict(id="macro_surprise/M1_dev", family_id="macro_surprise(M1,M2)", window="dev",
         path="reports/macro_surprise/dev/M1_base_daily.csv", date_col="date", value_col="excess"),
    dict(id="macro_surprise/M2_dev", family_id="macro_surprise(M1,M2)", window="dev",
         path="reports/macro_surprise/dev/M2_base_daily.csv", date_col="date", value_col="excess"),
    dict(id="macro_surprise/C_EW_dev", family_id="macro_surprise(M1,M2)", window="dev",
         path="reports/macro_surprise/dev/C_EW_base_daily.csv", date_col="date", value_col="excess"),
    dict(id="macro_surprise/C_MOM_dev", family_id="macro_surprise(M1,M2)", window="dev",
         path="reports/macro_surprise/dev/C_MOM_base_daily.csv", date_col="date", value_col="excess"),

    # --- mbs_convexity ---
    dict(id="mbs_convexity/dev", family_id="mbs_convexity", window="dev",
         path="reports/mbs_convexity/dev_daily.csv", date_col="date", value_col="base"),

    # --- pead_attack / pead_portfolio ---
    dict(id="pead_attack/real_book", family_id="pead_attack", window="dev",
         path="reports/pead_attack/real_book_daily.csv", date_col="Unnamed: 0", value_col="excess"),
    dict(id="pead_portfolio/PEAD", family_id="pead_portfolio(B1-B5)", window="dev",
         path="reports/pead_portfolio/daily_excess_main.csv", date_col="Unnamed: 0", value_col="PEAD"),
    dict(id="pead_portfolio/B1", family_id="pead_portfolio(B1-B5)", window="dev",
         path="reports/pead_portfolio/daily_excess_main.csv", date_col="Unnamed: 0", value_col="B1_beta_hedged"),
    dict(id="pead_portfolio/B2", family_id="pead_portfolio(B1-B5)", window="dev",
         path="reports/pead_portfolio/daily_excess_main.csv", date_col="Unnamed: 0", value_col="B2_vol_managed"),
    dict(id="pead_portfolio/B3", family_id="pead_portfolio(B1-B5)", window="dev",
         path="reports/pead_portfolio/daily_excess_main.csv", date_col="Unnamed: 0", value_col="B3_pead_tsmom"),

    # --- putwrite ---
    dict(id="putwrite/P1_dev", family_id="putwrite(P1-P3)", window="dev",
         path="reports/putwrite/dev/P1_spy_base_daily.csv", date_col="date", value_col="0"),
    dict(id="putwrite/P2_dev", family_id="putwrite(P1-P3)", window="dev",
         path="reports/putwrite/dev/P2_spy_vrp_base_daily.csv", date_col="date", value_col="0"),
    dict(id="putwrite/P3_dev", family_id="putwrite(P1-P3)", window="dev",
         path="reports/putwrite/dev/P3_etf3_base_daily.csv", date_col="date", value_col="0"),

    # --- rebalancing ---
    dict(id="rebalancing/R1_dev", family_id="rebalancing(R1-R3)", window="dev",
         path="reports/rebalancing/dev_R1_calendar_daily.csv", date_col="date", value_col="net"),
    dict(id="rebalancing/R2_dev", family_id="rebalancing(R1-R3)", window="dev",
         path="reports/rebalancing/dev_R2_threshold_daily.csv", date_col="date", value_col="net"),
    dict(id="rebalancing/R3_dev", family_id="rebalancing(R1-R3)", window="dev",
         path="reports/rebalancing/dev_R3_combined_daily.csv", date_col="date", value_col="net"),
    dict(id="rebalancing/R2_val", family_id="rebalancing(R1-R3)", window="validation",
         path="reports/rebalancing/validation_R2_threshold_daily.csv", date_col="date", value_col="net"),
    dict(id="rebalancing/R3_val", family_id="rebalancing(R1-R3)", window="validation",
         path="reports/rebalancing/validation_R3_combined_daily.csv", date_col="date", value_col="net"),

    # --- sector_month_end / tsy_month_end / fx_hedge_rebal (month-end flow siblings) ---
    dict(id="sector_month_end/dev", family_id="sector_month_end", window="dev",
         path="reports/sector_month_end/dev_daily_active.csv", date_col="date", value_col="base"),
    dict(id="tsy_month_end/dev", family_id="tsy_month_end(M)", window="dev",
         path="reports/tsy_month_end/dev_daily.csv", date_col="date", value_col="active"),
    dict(id="tsy_month_end/validation", family_id="tsy_month_end(M)", window="validation",
         path="reports/tsy_month_end/validation_daily.csv", date_col="date", value_col="active"),

    # --- fx_session (unregistered; used only for the project-wide FX cluster) ---
    dict(id="fx_session/london_fix_reversal", family_id="fx_session_screen", window="dev",
         path="reports/fx_session_20260918/london_fix_reversal_base_daily.csv", date_col="date", value_col="return"),
    dict(id="fx_session/london_reversal", family_id="fx_session_screen", window="dev",
         path="reports/fx_session_20260918/london_reversal_base_daily.csv", date_col="date", value_col="return"),
    dict(id="fx_session/new_york_continuation", family_id="fx_session_screen", window="dev",
         path="reports/fx_session_20260918/new_york_continuation_base_daily.csv", date_col="date", value_col="return"),

    # --- "nav-style" (date,return,nav,...) series: momentum program + unregistered lookalikes ---
    dict(id="momentum_construction/C1", family_id="momentum_construction", window="dev",
         path="reports/momentum_construction_20260919/C1_slots30_nav.csv", date_col="date", value_col="return"),
    dict(id="momentum_construction/C4", family_id="momentum_construction", window="dev",
         path="reports/momentum_construction_20260919/C4_inv_vol_nav.csv", date_col="date", value_col="return"),
    dict(id="momentum_construction/C7", family_id="momentum_construction", window="dev",
         path="reports/momentum_construction_20260919/C7_mom6_1_nav.csv", date_col="date", value_col="return"),
    dict(id="momentum_construction/C9", family_id="momentum_construction", window="dev",
         path="reports/momentum_construction_20260919/C9_high52_nav.csv", date_col="date", value_col="return"),
    dict(id="residual_momentum/R1", family_id="residual_momentum", window="dev",
         path="reports/residual_momentum_20260919/R1_capm_residual_nav.csv", date_col="date", value_col="return"),
    dict(id="residual_momentum/R2", family_id="residual_momentum", window="dev",
         path="reports/residual_momentum_20260919/R2_ff3_residual_nav.csv", date_col="date", value_col="return"),
    dict(id="residual_momentum/R4", family_id="residual_momentum", window="dev",
         path="reports/residual_momentum_20260919/R4_risk_adj_raw_nav.csv", date_col="date", value_col="return"),
    dict(id="vol_managed_momentum/V1", family_id="vol_managed_momentum", window="dev",
         path="reports/vol_managed_momentum_20260919/V1_nav.csv", date_col="date", value_col="return"),
    dict(id="vol_managed_momentum/V2", family_id="vol_managed_momentum", window="dev",
         path="reports/vol_managed_momentum_20260919/V2_nav.csv", date_col="date", value_col="return"),
    dict(id="vol_managed_momentum/V5", family_id="vol_managed_momentum", window="dev",
         path="reports/vol_managed_momentum_20260919/V5_nav.csv", date_col="date", value_col="return"),
    dict(id="vol_managed_momentum/baseline", family_id="vol_managed_momentum", window="dev",
         path="reports/vol_managed_momentum_20260919/B_baseline_nav.csv", date_col="date", value_col="return"),
    dict(id="momentum_lab/baseline_12_1", family_id="momentum_verification_lab", window="dev",
         path="reports/momentum_lab/baseline_12_1_nav.csv", date_col="date", value_col="return"),

    # --- return_search (unregistered), a representative subset across asset classes ---
    dict(id="return_search/stocks_momentum", family_id="return_search", window="dev",
         path="reports/return_search_20260919/dev/stocks__momentum_base.csv", date_col="date", value_col="return"),
    dict(id="return_search/stocks_trend", family_id="return_search", window="dev",
         path="reports/return_search_20260919/dev/stocks__trend_base.csv", date_col="date", value_col="return"),
    dict(id="return_search/stocks_breakout", family_id="return_search", window="dev",
         path="reports/return_search_20260919/dev/stocks__breakout_base.csv", date_col="date", value_col="return"),
    dict(id="return_search/etf_momentum", family_id="return_search", window="dev",
         path="reports/return_search_20260919/dev/etf__momentum_base.csv", date_col="date", value_col="return"),
    dict(id="return_search/etf_trend", family_id="return_search", window="dev",
         path="reports/return_search_20260919/dev/etf__trend_base.csv", date_col="date", value_col="return"),
    dict(id="return_search/crypto_trend", family_id="return_search", window="dev",
         path="reports/return_search_20260919/dev/crypto__trend_base.csv", date_col="date", value_col="return"),
    dict(id="return_search/vol_contango", family_id="return_search", window="dev",
         path="reports/return_search_20260919/dev/vol__contango_base.csv", date_col="date", value_col="return"),

    # --- crowding_unwind / downside_rotation (unregistered) ---
    dict(id="crowding_unwind/base", family_id="crowding_downside_rotation", window="dev",
         path="reports/crowding_unwind_20260919/crowding_unwind_base.csv", date_col="date", value_col="return"),
    dict(id="crowding_unwind/positioning_only", family_id="crowding_downside_rotation", window="dev",
         path="reports/crowding_unwind_20260919/positioning_only_base.csv", date_col="date", value_col="return"),
    dict(id="downside_rotation/primary", family_id="crowding_downside_rotation", window="dev",
         path="reports/downside_rotation_20260919/primary_base.csv", date_col="date", value_col="return"),
    dict(id="downside_rotation/equal_weight", family_id="crowding_downside_rotation", window="dev",
         path="reports/downside_rotation_20260919/equal_weight_base.csv", date_col="date", value_col="return"),

    # --- etf_convergence / share_class / liquidity_pressure (unregistered) ---
    dict(id="etf_convergence/SPY_QQQ", family_id="etf_convergence_share_class_liquidity", window="dev",
         path="reports/etf_convergence_20260918/SPY_QQQ_base.csv", date_col="date", value_col="return"),
    dict(id="etf_convergence/GLD_SLV", family_id="etf_convergence_share_class_liquidity", window="dev",
         path="reports/etf_convergence_20260918/GLD_SLV_base.csv", date_col="date", value_col="return"),
    dict(id="etf_convergence/LQD_IEF", family_id="etf_convergence_share_class_liquidity", window="dev",
         path="reports/etf_convergence_20260918/LQD_IEF_base.csv", date_col="date", value_col="return"),

    # --- edge_first_backtest (unregistered PEAD probe) ---
    dict(id="edge_first_backtest/pead_long_only", family_id="edge_probe_scripts", window="dev",
         path="reports/edge_first_backtest/daily_returns.csv", date_col="timestamp", value_col="pead_long_only"),

    # --- event-cycle families (entry-dated, irregular; 'net' is the per-cycle net return) ---
    dict(id="cot/C1", family_id="cot(C1-C3)", window="dev",
         path="reports/cot/dev/C1_liquidity_base.csv", date_col="entry", value_col="net"),
    dict(id="cot/C2", family_id="cot(C1-C3)", window="dev",
         path="reports/cot/dev/C2_hedging_pressure_base.csv", date_col="entry", value_col="net"),
    dict(id="cot/C3", family_id="cot(C1-C3)", window="dev",
         path="reports/cot/dev/C3_two_premiums_base.csv", date_col="entry", value_col="net"),
    dict(id="options_signals/H1", family_id="options_signals(H1-H4)", window="dev",
         path="reports/options_signals/dev/H1_os_base.csv", date_col="entry", value_col="net"),
    dict(id="options_signals/H2", family_id="options_signals(H1-H4)", window="dev",
         path="reports/options_signals/dev/H2_ivspread_base.csv", date_col="entry", value_col="net"),
    dict(id="options_signals/H3", family_id="options_signals(H1-H4)", window="dev",
         path="reports/options_signals/dev/H3_skew_base.csv", date_col="entry", value_col="net"),
    dict(id="options_signals/H4", family_id="options_signals(H1-H4)", window="dev",
         path="reports/options_signals/dev/H4_composite_base.csv", date_col="entry", value_col="net"),
    dict(id="iv_changes/V1", family_id="iv_changes(V1-V3)", window="dev",
         path="reports/iv_changes/dev/V1_dcall_base.csv", date_col="entry", value_col="net"),
    dict(id="iv_changes/V2", family_id="iv_changes(V1-V3)", window="dev",
         path="reports/iv_changes/dev/V2_dput_base.csv", date_col="entry", value_col="net"),
    dict(id="iv_changes/V3", family_id="iv_changes(V1-V3)", window="dev",
         path="reports/iv_changes/dev/V3_dspread_base.csv", date_col="entry", value_col="net"),
    dict(id="fundamentals/F1", family_id="fundamentals(F1-F3)", window="dev",
         path="reports/fundamentals/dev/F1_issuance_curve.csv", date_col="entry", value_col="net"),
    dict(id="fundamentals/F2", family_id="fundamentals(F1-F3)", window="dev",
         path="reports/fundamentals/dev/F2_consistency_curve.csv", date_col="entry", value_col="net"),
    dict(id="fundamentals/F3", family_id="fundamentals(F1-F3)", window="dev",
         path="reports/fundamentals/dev/F3_combined_curve.csv", date_col="entry", value_col="net"),
    dict(id="fx_carry_vol/F1", family_id="fx_carry_vol(F2,F3 vs F1)", window="dev",
         path="reports/fx_carry_vol/dev/F1_plain_carry_base.csv", date_col="entry", value_col="net"),
    dict(id="fx_carry_vol/F2", family_id="fx_carry_vol(F2,F3 vs F1)", window="dev",
         path="reports/fx_carry_vol/dev/F2_carry_to_vol_base.csv", date_col="entry", value_col="net"),
    dict(id="fx_carry_vol/F3", family_id="fx_carry_vol(F2,F3 vs F1)", window="dev",
         path="reports/fx_carry_vol/dev/F3_carry_to_vol_targeted_base.csv", date_col="entry", value_col="net"),
    dict(id="structural_frontier/C_tlt_puts", family_id="structural_frontier(C: TLT put insurance)", window="dev",
         path="reports/structural_frontier/option_dev_cycles.csv", date_col="entry", value_col="candidate_base"),
    dict(id="vrp_putwrite/PW", family_id="vrp_putwrite(PW)", window="dev",
         path="reports/vrp_putwrite/dev_cycles.csv", date_col="entry", value_col="r_base"),

    # --- monthly-native families ---
    dict(id="policy_trend/P1", family_id="policy_trend(P1)", window="dev",
         path="reports/policy_trend/dev_monthly_base.csv", date_col="Unnamed: 0", value_col="P1"),
    dict(id="policy_trend/C_MOM", family_id="policy_trend(P1)", window="dev",
         path="reports/policy_trend/dev_monthly_base.csv", date_col="Unnamed: 0", value_col="C_MOM"),

    # --- multiasset sleeves (a sample of the 17; date col is unnamed) ---
    dict(id="multiasset/tsmom", family_id="multiasset(17-sleeve inclusion + 5-sleeve holdout)", window="dev",
         path="reports/multiasset/dev_sleeve_returns.csv", date_col="Unnamed: 0", value_col="tsmom"),
    dict(id="multiasset/fx_carry", family_id="multiasset(17-sleeve inclusion + 5-sleeve holdout)", window="dev",
         path="reports/multiasset/dev_sleeve_returns.csv", date_col="Unnamed: 0", value_col="fx_carry"),
    dict(id="multiasset/xs_momentum", family_id="multiasset(17-sleeve inclusion + 5-sleeve holdout)", window="dev",
         path="reports/multiasset/dev_sleeve_returns.csv", date_col="Unnamed: 0", value_col="xs_momentum"),
    dict(id="multiasset/bond_carry", family_id="multiasset(17-sleeve inclusion + 5-sleeve holdout)", window="dev",
         path="reports/multiasset/dev_sleeve_returns.csv", date_col="Unnamed: 0", value_col="bond_carry"),

    # --- overlay_control (registered CONTROL study; a 2-cell sample of its 30) ---
    dict(id="overlay_control/SPY_O0_buyhold", family_id="overlay_control", window="dev",
         path="reports/overlay_control_20260919/diagnostics/SPY__O0_base.csv", date_col="date", value_col="return"),
    dict(id="overlay_control/SPY_O1_owntrend", family_id="overlay_control", window="dev",
         path="reports/overlay_control_20260919/diagnostics/SPY__O1_base.csv", date_col="date", value_col="return"),
    dict(id="overlay_control/SPMO_O0_buyhold", family_id="overlay_control", window="dev",
         path="reports/overlay_control_20260919/diagnostics/SPMO__O0_base.csv", date_col="date", value_col="return"),

    # --- survivor_hybrid (OOS, monthly-native) ---
    dict(id="survivor_hybrid/H1", family_id="survivor_hybrid(H1-H4)", window="dev",
         path="reports/survivor_hybrid/returns_oos.csv", date_col="date", value_col="H1_net"),
    dict(id="survivor_hybrid/H2", family_id="survivor_hybrid(H1-H4)", window="dev",
         path="reports/survivor_hybrid/returns_oos.csv", date_col="date", value_col="H2_net"),
    dict(id="survivor_hybrid/H3", family_id="survivor_hybrid(H1-H4)", window="dev",
         path="reports/survivor_hybrid/returns_oos.csv", date_col="date", value_col="H3_net"),
    dict(id="survivor_hybrid/H4", family_id="survivor_hybrid(H1-H4)", window="dev",
         path="reports/survivor_hybrid/returns_oos.csv", date_col="date", value_col="H4_net"),
]

# etf_hybrids uses a 2-row multi-index header and needs the special loader
# in data_sources.load_etf_hybrids_multiindex; handled separately in build.py.
ETF_HYBRIDS_DEV = dict(path="reports/etf_hybrids/dev/daily.csv", sleeves=["E1", "E2", "E3", "E4", "E5", "B"], family_id="etf_hybrids(E1-E5)", window="dev")
ETF_HYBRIDS_VAL = dict(path="reports/etf_hybrids/validation/daily.csv", sleeves=["E1", "E2", "B"], family_id="etf_hybrids(E1-E5)", window="validation")
