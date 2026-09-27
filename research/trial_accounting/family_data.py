"""Hand-curated, cited family- and trial-level metadata.

Why hand-curated rather than parsed out of the markdown ledgers: the prose
tables in RESEARCH_LEDGER_2026-09-23.md, FAMILY_TRIAL_LEDGER.md and
GATE_CONSISTENCY.md are free text with merged cells, footnotes and duplicate
row numbers (36-38 appear twice, disclosed in the ledger itself). Regex-
parsing that reliably is more fragile, and more likely to silently
mis-attribute a number, than reading each source once and recording a
reviewable citation next to each field. Every row below cites the file(s) it
was read from; the numeric counts that ARE machine-parseable (n_candidates,
dev/validation pass counts for the 35 gate-evaluable families) are instead
pulled live from reports/null_lab2/multiple_testing.json and
reports/null_lab2/gate_table.csv in build.py, not retyped here, specifically
so this module cannot silently drift from the other agent's numbers.

information_family vocabulary used below (examples from the task spec, plus
extensions needed to cover this registry): calendar/flow, price momentum,
earnings events, positioning, macro releases, options prints, credit spreads,
FX intraday, rates/duration, commodity roll, crypto trend, insider
transactions, academic-anomaly replication, ETF structure/basis, fund/regime
selection.

strategy_family vocabulary: time-series timing, cross-sectional selection,
spread/relative value, event study, carry/premium, portfolio construction/
overlay, meta-analysis/screening, benchmark construction.

tier: 1 = registered, gate-evaluable (in null_lab2 gate_table.csv);
      2 = registered, non-standard gate (momentum program, control study);
      3 = never preregistered (estimate only).
"""
from __future__ import annotations

# Each row: family_id must equal the corresponding `family` value in
# reports/null_lab2/gate_table.csv for tier==1 rows (build.py joins on it).
FAMILIES = [
    # ---------------- Tier 1: registered, gate-evaluable (35, from gate_table.csv) ----------------
    dict(family_id="pead_attack", tier=1, information_family="earnings events",
         strategy_family="event study",
         directories=["research/pead_attack", "reports/pead_attack"],
         candidate_labels=["P1_within_date_permutation", "P1L", "P1G", "P2", "P3", "P1W_amendment", "P1V_amendment"],
         forward_observations=0,
         contamination_status="Portfolio-level placebo of the PRODUCTION PEAD book (sweep_wide_5p0), reproduced trade for trade -- shares 100% of its information/window with pead_production_history and the live paper bot. An unregistered precursor, reports/pead_audit/ (mtime 2026-09-18, curves for wide_2p5/3p5/5p0/10p0 and old_pead_75), sits between pead_production_history and this family in both time and design and is not separately counted here. PLAN_AMENDMENT_1 was registered AFTER the PLAN.md primary result was seen (P1 p=0.113), explicitly disclosed as exploratory in its own registration text.",
         current_classification="SPENT as an edge (real vs random-selection placebo p=0.113; edge concentrated in one 2021-10..2023-10 subperiod, IR 0.30 -> -1.29 when removed)", evidence_confidence="high",
         source_files=["research/pead_attack/PLAN.md", "research/pead_attack/PLAN_AMENDMENT_1.md", "reports/pead_attack/real_book_daily.csv", "research/RESEARCH_LEDGER_2026-09-23.md row 1"]),
    dict(family_id="pead_2004_2014", tier=1, information_family="earnings events",
         strategy_family="event study",
         directories=["research/PREREGISTRATION_pead_2004_2014.md"],
         candidate_labels=["pead_2004_2014_replication"],
         forward_observations=0,
         contamination_status="2004-2014 window is the PEAD production model's own historical training/validation period; a pure out-of-sample replication only in the narrow sense that the specific HAC-t gate was fixed before this run, not that the window was unseen (RESEARCH_LEDGER row 1, reports/pead_2004_2014/REPORT.md).",
         current_classification="SPENT",
         evidence_confidence="high",
         source_files=["research/PREREGISTRATION_pead_2004_2014.md", "reports/pead_2004_2014/REPORT.md", "reports/null_lab2/gate_table.csv"]),
    dict(family_id="options_signals(H1-H4)", tier=1, information_family="options prints",
         strategy_family="cross-sectional selection",
         directories=["research/options_signals", "reports/options_signals"],
         candidate_labels=["H1_os", "H2_ivspread", "H3_skew", "H4_composite"],
         forward_observations=0,
         contamination_status="OPRA prints (100 names, 2014-2026) shared with iv_changes(V1-V3); H3 skew factor (SmileSlope) is the top OSAP survivor, so the underlying anomaly is already published (RESEARCH_LEDGER row 6).",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/options_signals/PLAN.md", "reports/options_signals/dev/*.csv", "reports/null_lab2/gate_table.csv"]),
    dict(family_id="putwrite(P1-P3)", tier=1, information_family="options prints",
         strategy_family="carry/premium",
         directories=["research/putwrite", "reports/putwrite"],
         candidate_labels=["P1_spy", "P2_spy_vrp", "P3_etf3"],
         forward_observations=0,
         contamination_status="SPY/QQQ/IWM 1-day puts; distinct OPRA subset from options_signals/iv_changes but same underlyings as vrp_putwrite and structural_frontier(C), which post-date it (RESEARCH_LEDGER row 8).",
         current_classification="PARTIALLY USED (index options beyond 1-day puts untested)", evidence_confidence="high",
         source_files=["research/putwrite/PLAN.md", "reports/putwrite/dev/*.csv"]),
    dict(family_id="cot(C1-C3)", tier=1, information_family="positioning",
         strategy_family="carry/premium",
         directories=["research/cot", "reports/cot"],
         candidate_labels=["C1_liquidity", "C2_hedging_pressure", "C3_two_premiums"],
         forward_observations=0,
         contamination_status="CFTC COT on 11 commodity ETFs; same positioning data family as crowding_unwind (unregistered) and informs commodity_roll's mechanism story (RESEARCH_LEDGER rows 9-10).",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/cot/PLAN.md", "reports/cot/dev/*.csv"]),
    dict(family_id="intraday(I1-I4)", tier=1, information_family="calendar/flow",
         strategy_family="time-series timing",
         directories=["research/intraday", "reports/intraday"],
         candidate_labels=["I1_intraday_momentum", "I2_rest_of_day", "I3_ml_lgbm", "I4_announcement_day"],
         forward_observations=0,
         contamination_status="ES/NQ 30m bars, own family; I4 dev-passed then failed validation (RESEARCH_LEDGER row 11).",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/intraday/PLAN.md", "reports/intraday/dev/*.csv", "reports/intraday/validation/*.csv"]),
    dict(family_id="fx_carry_vol(F2,F3 vs F1)", tier=1, information_family="FX intraday",
         strategy_family="carry/premium",
         directories=["research/fx_carry_vol", "reports/fx_carry_vol"],
         candidate_labels=["F1_plain_carry", "F2_carry_to_vol", "F3_carry_to_vol_targeted"],
         forward_observations=0,
         contamination_status="G10 forward points/1M IV; sibling of fx_news and fx_hedge_rebal (different FX information, same instrument universe) and fx_session_20260918 (unregistered, same majors).",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/fx_carry_vol/PLAN.md", "reports/fx_carry_vol/dev/*.csv"]),
    dict(family_id="pead_portfolio(B1-B5)", tier=1, information_family="earnings events",
         strategy_family="portfolio construction/overlay",
         directories=["research/pead_portfolio", "reports/pead_portfolio"],
         candidate_labels=["B1_beta_hedged", "B2_vol_managed", "B3_pead_tsmom", "B4_pead_3sleeves", "B5_hedged_3sleeves"],
         forward_observations=0,
         contamination_status="Built directly on the PEAD production book (bot/, pead_attack); single-window, no independent validation split (gate_table.csv notes).",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/pead_portfolio/PLAN.md", "reports/pead_portfolio/daily_excess_main.csv"]),
    dict(family_id="insider(N1-N4)", tier=1, information_family="insider transactions",
         strategy_family="cross-sectional selection",
         directories=["research/insider", "reports/insider"],
         candidate_labels=["N1_cluster", "N2_csuite", "N3_opportunistic", "N4_composite"],
         forward_observations=0,
         contamination_status="SEC Form 4, 2006-2026, survivor-biased price universe; N3/N4 dev-passed then failed validation (RESEARCH_LEDGER row 18).",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/insider/PLAN.md", "reports/insider/dev/*.csv", "reports/insider/validation/*.csv"]),
    dict(family_id="rebalancing(R1-R3)", tier=1, information_family="calendar/flow",
         strategy_family="time-series timing",
         directories=["research/rebalancing", "reports/rebalancing"],
         candidate_labels=["R1_calendar", "R2_threshold", "R3_combined"],
         forward_observations=0,
         contamination_status="60/40 SPY-IEF drift; dev windows previously viewed per its own PLAN.md disclosure; mechanism cousin of tsy_month_end/sector_month_end (calendar-forced flow) though on a different rebalancing mechanism (RESEARCH_LEDGER row 13; registered_trials.csv note).",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/rebalancing/PLAN.md", "reports/rebalancing/dev_*.csv", "reports/rebalancing/validation_*.csv"]),
    dict(family_id="letf_rebalancing(L1-L2)", tier=1, information_family="calendar/flow",
         strategy_family="time-series timing",
         directories=["research/letf_rebalancing", "reports/letf_rebalancing"],
         candidate_labels=["L1_flow_top_quintile", "L2_flow_scaled"],
         forward_observations=0,
         contamination_status="PROCESS FLAG (null_lab2 flags.csv, high severity): L2 dev Sharpe 0.48 is below its own registered 0.50 gate, yet the ledger classifies it FORWARD ONLY and recommends a forward test anyway -- the one gate in the registry bypassed after failing.",
         current_classification="FORWARD ONLY (disputed -- see contamination_status)", evidence_confidence="high",
         source_files=["research/letf_rebalancing/PLAN.md", "reports/letf_rebalancing/dev/*.csv", "reports/null_lab2/flags.csv"]),
    dict(family_id="iv_changes(V1-V3)", tier=1, information_family="options prints",
         strategy_family="cross-sectional selection",
         directories=["research/iv_changes", "reports/iv_changes"],
         candidate_labels=["V1_dcall", "V2_dput", "V3_dspread"],
         forward_observations=0,
         contamination_status="Same OPRA 100-name universe as options_signals; separate trial per its own PLAN.md disclosure.",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/iv_changes/PLAN.md", "reports/iv_changes/dev/*.csv"]),
    dict(family_id="pead_streak(S1-S2)", tier=1, information_family="earnings events",
         strategy_family="event study",
         directories=["research/pead_streak", "reports/pead_streak"],
         candidate_labels=["S1_streak_long_short", "S2_streak_long_only"],
         forward_observations=0,
         contamination_status="Windows previously used by PEAD work (own PLAN.md disclosure).",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/pead_streak/PLAN.md", "reports/pead_streak"]),
    dict(family_id="auction_cycle(A1-A3)", tier=1, information_family="rates/duration",
         strategy_family="event study",
         directories=["research/auction_cycle", "reports/auction_cycle"],
         candidate_labels=["A1_pre_short", "A2_post_long", "A3_combined"],
         forward_observations=0,
         contamination_status="Bond prices 2015+ previously viewed by other rates families (own PLAN.md disclosure); shares IEF/TLT universe with tsy_month_end, structural_frontier(A), sector_month_end.",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/auction_cycle/PLAN.md", "reports/auction_cycle/dev_*.csv"]),
    dict(family_id="fundamentals(F1-F3)", tier=1, information_family="earnings events",
         strategy_family="cross-sectional selection",
         directories=["research/fundamentals", "reports/fundamentals"],
         candidate_labels=["F1_issuance", "F2_consistency", "F3_combined"],
         forward_observations=0,
         contamination_status="Current-member universe; its 2015+ performance already known via OSAP/survivor_hybrid (own PLAN.md disclosure).",
         current_classification="PARTIALLY USED", evidence_confidence="high",
         source_files=["research/fundamentals/PLAN.md", "reports/fundamentals/dev/*.csv"]),
    dict(family_id="survivor_hybrid(H1-H4)", tier=1, information_family="academic-anomaly replication",
         strategy_family="portfolio construction/overlay",
         directories=["research/survivor_hybrid", "reports/survivor_hybrid"],
         candidate_labels=["H1_ew", "H2_inverse_vol", "H3_large_cap", "H4_mechanism_equal_risk"],
         forward_observations=0,
         contamination_status="Window partly contaminated by edge_graveyard's OSAP meta-study, disclosed in its own PLAN.md; half the OOS window is GameStop Jan-2021 (RESEARCH_LEDGER row 20).",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/survivor_hybrid/PLAN.md", "reports/survivor_hybrid/returns_oos.csv"]),
    dict(family_id="etf_hybrids(E1-E5)", tier=1, information_family="price momentum",
         strategy_family="cross-sectional selection",
         directories=["research/etf_hybrids", "reports/etf_hybrids"],
         candidate_labels=["E1_vol_managed_mom", "E2_dual_momentum", "E3_52wk_high", "E4_mom_lowvol_blend", "E5_seasonality"],
         forward_observations=0,
         contamination_status="11 of its sector/country ETFs overlap the multiasset book's universe, disclosed in its own PLAN.md; E1/E2 dev-passed then failed validation.",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/etf_hybrids/PLAN.md", "reports/etf_hybrids/dev/daily.csv", "reports/etf_hybrids/validation/daily.csv"]),
    dict(family_id="macro_surprise(M1,M2)", tier=1, information_family="macro releases",
         strategy_family="cross-sectional selection",
         directories=["research/macro_surprise", "reports/macro_surprise"],
         candidate_labels=["M1_long_short", "M2_long_only"],
         forward_observations=0,
         contamination_status="Registered ~10h before the 2026-09-23 protocol amendment, so used the old 0.5 flat-Sharpe gate rather than 1.8/sqrt(T) (gate_table.csv note); shares the economic-calendar source with fx_news and policy_trend.",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/macro_surprise/PLAN.md", "reports/macro_surprise/dev/*.csv"]),
    dict(family_id="multiasset(17-sleeve inclusion + 5-sleeve holdout)", tier=1, information_family="price momentum",
         strategy_family="time-series timing",
         directories=["research/multiasset", "reports/multiasset"],
         candidate_labels=None,  # filled programmatically from reports/multiasset/dev_sleeve_returns.csv columns
         forward_observations=0,
         contamination_status="INCONSISTENCY (null_lab2 flags.csv, medium): 17 candidates screened at a flat 0.30 Sharpe with no null and no multiple-testing correction -- calibrated 19.4% false-pass rate at zero-net-mean vs 5/17 actual passes, roughly what noise alone would produce for ~3 of the 5. Shares ETF universe with etf_hybrids.",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/multiasset/PLAN.md", "research/multiasset/PLAN_ADDENDUM_1.md", "research/multiasset/PLAN_ADDENDUM_2.md", "reports/multiasset/dev_sleeve_returns.csv", "reports/multiasset/holdout/holdout_returns.csv"]),
    dict(family_id="multiasset/crypto(2 candidates)", tier=1, information_family="crypto trend",
         strategy_family="time-series timing",
         directories=["research/multiasset"],
         candidate_labels=["crypto_trend_long_only", "crypto_tsmom_multi"],
         forward_observations=0,
         contamination_status="Best-of-N selection with no numeric dev threshold in the source PLAN text (null_lab2 REPORT.md Limitations); its simulated 100% false-pass figure is flagged there as a modeling artifact, not a finding.",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/multiasset/PLAN_CRYPTO.md", "research/multiasset/PREREGISTRATION_crypto_holdout.md"]),
    dict(family_id="japan_us_flow(J1)", tier=1, information_family="FX intraday",
         strategy_family="time-series timing",
         directories=["research/japan_us_flow", "reports/japan_us_flow"],
         candidate_labels=["J1"],
         forward_observations=0,
         contamination_status="Independent LSE data trial; pre-return source audit found holiday quote-bar issues, fixed before any return (PLAN_AMENDMENT_1).",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/japan_us_flow/PLAN.md", "reports/japan_us_flow"]),
    dict(family_id="credit_lead", tier=1, information_family="credit spreads",
         strategy_family="time-series timing",
         directories=["research/credit_lead", "reports/credit_lead"],
         candidate_labels=["credit_lead_HY_IG_ratio"],
         forward_observations=0,
         contamination_status="P(pass|null) computed but not gated (null_lab2 flags.csv medium severity #6) -- false-pass rate triples (4.6% to 13.3%) under a small residual exposure leak because nothing in the registered pass criteria can catch it.",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/credit_lead/PLAN.md", "reports/credit_lead/REPORT.md"]),
    dict(family_id="index_option_breadth", tier=1, information_family="options prints",
         strategy_family="time-series timing",
         directories=["research/index_option_breadth", "reports/index_option_breadth"],
         candidate_labels=["index_option_breadth_weekly"],
         forward_observations=0,
         contamination_status="Same P(pass|null)-not-gated issue as credit_lead (null_lab2 flags.csv #6).",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/index_option_breadth/PLAN.md", "reports/index_option_breadth/REPORT.md"]),
    dict(family_id="policy_trend(P1)", tier=1, information_family="macro releases",
         strategy_family="cross-sectional selection",
         directories=["research/policy_trend", "reports/policy_trend"],
         candidate_labels=["P1_policy_trend"],
         forward_observations=0,
         contamination_status="Shares the economic-calendar source with macro_surprise and fx_news.",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/policy_trend/PLAN.md", "reports/policy_trend/dev_monthly_base.csv"]),
    dict(family_id="fx_news(F1,F2)", tier=1, information_family="macro releases",
         strategy_family="event study",
         directories=["research/fx_news", "reports/fx_news"],
         candidate_labels=["F1_15m_2h", "F2_15m_24h"],
         forward_observations=0,
         contamination_status="Discovered and corrected a calendar timestamp-timezone bug (Berlin wall time pre-2016) before computing any return; disclosed that macro_surprise's date-level signal is unaffected by the same bug (RESEARCH_LEDGER cycle-3 update).",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/fx_news/PLAN.md", "reports/fx_news/REPORT.md"]),
    dict(family_id="credit_gate(G)", tier=1, information_family="credit spreads",
         strategy_family="time-series timing",
         directories=["research/credit_gate", "reports/credit_gate"],
         candidate_labels=["G_credit_gate"],
         forward_observations=0,
         contamination_status="iBoxx USD HY/corp ratio, LSE vault 2010+; shares credit-spread information with credit_lead and etf_basis (HYG/LQD).",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/credit_gate/PLAN.md", "reports/credit_gate/dev_daily_base.csv"]),
    dict(family_id="structural_frontier(A: Treasury term premium)", tier=1, information_family="rates/duration",
         strategy_family="spread/relative value",
         directories=["research/structural_frontier", "reports/structural_frontier"],
         candidate_labels=["A_ief_shy_duration"],
         forward_observations=0,
         contamination_status="INFORMATIONAL (null_lab2 flags.csv #9, low severity, positive finding): the one clean case where the Bonferroni p-gate (p=0.023 vs 0.0167) correctly overrode a nominal Sharpe pass (0.57 vs 0.52). Shares IEF/TLT duration exposure with auction_cycle, tsy_month_end, sector_month_end.",
         current_classification="Suggestive, failed batch gate; no validation", evidence_confidence="high",
         source_files=["research/structural_frontier/PLAN.md", "reports/structural_frontier/REPORT.md"]),
    dict(family_id="structural_frontier(B: HY credit carry)", tier=1, information_family="credit spreads",
         strategy_family="carry/premium",
         directories=["research/structural_frontier", "reports/structural_frontier"],
         candidate_labels=["B_hyg_credit_carry"],
         forward_observations=0,
         contamination_status="2009 crisis-year contribution; equity-beta correlation 0.60 (EVIDENCE_MATRIX.md).",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/structural_frontier/PLAN.md", "reports/structural_frontier/REPORT.md"]),
    dict(family_id="structural_frontier(C: TLT put insurance)", tier=1, information_family="options prints",
         strategy_family="carry/premium",
         directories=["research/structural_frontier", "reports/structural_frontier"],
         candidate_labels=["C_tlt_put_insurance"],
         forward_observations=0,
         contamination_status="Same TLT option-print limitation (no historical bid/ask) as vrp_putwrite/putwrite.",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/structural_frontier/PLAN.md", "reports/structural_frontier/REPORT.md"]),
    dict(family_id="vrp_putwrite(PW)", tier=1, information_family="options prints",
         strategy_family="carry/premium",
         directories=["research/vrp_putwrite", "reports/vrp_putwrite"],
         candidate_labels=["PW_atm_spy_putwrite"],
         forward_observations=0,
         contamination_status="Same SPY option-print universe as putwrite(P1-P3) and structural_frontier(C); active premium found to equal equity beta here.",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/vrp_putwrite/PLAN.md", "reports/vrp_putwrite/dev_cycles.csv"]),
    dict(family_id="etf_basis(B)", tier=1, information_family="credit spreads",
         strategy_family="spread/relative value",
         directories=["research/etf_basis", "reports/etf_basis"],
         candidate_labels=["B_hyg_lqd_basis"],
         forward_observations=0,
         contamination_status="HYG/LQD vs own iBoxx basis; shares HY credit information with credit_gate, credit_lead, structural_frontier(B).",
         current_classification="SPENT (HY-only forward idea at most)", evidence_confidence="high",
         source_files=["research/etf_basis/PLAN.md", "reports/etf_basis/dev_daily.csv"]),
    dict(family_id="tsy_month_end(M)", tier=1, information_family="calendar/flow",
         strategy_family="time-series timing",
         directories=["research/tsy_month_end", "reports/tsy_month_end", "research/forward_audit"],
         candidate_labels=["M_tlt_month_end"],
         forward_observations=1,
         contamination_status="STRONGEST DEV EVIDENCE IN THE REGISTRY, downgraded by independent audit (reports/audit_tsy/REPORT.md): the rule was published in 2019; post-publication active Sharpe 0.56 (p=0.059), last 36 months 0.25. The unregistered combined p=0.00034 was withdrawn. Mechanism sibling of sector_month_end (failed) and rebalancing/auction_cycle (calendar-forced Treasury flow). One forward decision recorded 2026-09-25 (reports/forward/CYCLE4_FORWARD_ACTIONS_2026-09-24.md, registry seq 3); no outcome observed yet.",
         current_classification="FORWARD OBSERVATION (validation FAILED, 0.69 vs 0.75)", evidence_confidence="high",
         source_files=["research/tsy_month_end/PLAN.md", "research/tsy_month_end/VALIDATION_UNLOCK.md", "reports/tsy_month_end/dev_daily.csv", "reports/tsy_month_end/validation_daily.csv", "reports/audit_tsy/REPORT.md", "reports/forward/CYCLE4_FORWARD_ACTIONS_2026-09-24.md"]),
    dict(family_id="commodity_roll", tier=1, information_family="commodity roll",
         strategy_family="spread/relative value",
         directories=["research/commodity_roll", "reports/commodity_roll", "reports/audit_commodity_roll"],
         candidate_labels=["A1_dollar_neutral_pairs", "A1_independent_audit_reestimate"],
         forward_observations=0,
         contamination_status="Dev PASS (0.596 vs 0.557, p=0.0064), independent audit WEAKENED it (spot-hedged alpha t=3.09 but tradable pure-roll t=1.6), then validation FAILED (0.21 vs 0.75). Shares COT/commodity-positioning information family with cot(C1-C3) and crowding_unwind (unregistered).",
         current_classification="SPENT (natgas-only strength is post hoc, not a candidate)", evidence_confidence="high",
         source_files=["research/commodity_roll/PLAN.md", "research/commodity_roll/VALIDATION_UNLOCK.md", "reports/commodity_roll/dev_daily.csv", "reports/commodity_roll/validation_daily.csv", "reports/audit_commodity_roll"]),
    dict(family_id="mbs_convexity", tier=1, information_family="rates/duration",
         strategy_family="spread/relative value",
         directories=["research/mbs_convexity", "reports/mbs_convexity"],
         candidate_labels=["A2_mbb_minus_hedge"],
         forward_observations=0,
         contamination_status="2009 QE year dominates the dev result; shares rates/duration information with auction_cycle, tsy_month_end, structural_frontier(A).",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/mbs_convexity/PLAN.md", "reports/mbs_convexity/dev_daily.csv"]),
    dict(family_id="sector_month_end", tier=1, information_family="calendar/flow",
         strategy_family="time-series timing",
         directories=["research/sector_month_end", "reports/sector_month_end"],
         candidate_labels=["B1_lqd_mbb_tip"],
         forward_observations=0,
         contamination_status="NULL-ANSWERS-WRONG-QUESTION case study (GATE_CONSISTENCY.md, null_lab2 flags.csv #3 high): active Sharpe -0.43 yet shift-null p=0.038, because the shift-null's own mean was -0.96 (not mean-zero). Explicitly does NOT corroborate tsy_month_end despite being informed by its mechanism.",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/sector_month_end/PLAN.md", "reports/sector_month_end/dev_daily_active.csv", "reports/evidence_audit_20260923/GATE_CONSISTENCY.md"]),
    dict(family_id="fx_hedge_rebal", tier=1, information_family="FX intraday",
         strategy_family="time-series timing",
         directories=["research/fx_hedge_rebal", "reports/fx_hedge_rebal"],
         candidate_labels=["B2_fx_hedge_rebal"],
         forward_observations=0,
         contamination_status="Binds on absolute book Sharpe, not active-vs-C_USDSHORT control (null_lab2 flags.csv #8, medium, 'control not gated'); quarter-ends weaker (wrong sign for the claimed mechanism).",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/fx_hedge_rebal/PLAN.md", "reports/fx_hedge_rebal"]),

    # ---------------- Tier 2: registered, non-standard gate (momentum program + control) ----------------
    dict(family_id="momentum_construction", tier=2, information_family="price momentum",
         strategy_family="cross-sectional selection",
         directories=["research/momentum_construction", "reports/momentum_construction_20260919"],
         candidate_labels=["C1_slots30", "C2_slots50", "C3_slots10", "C4_inv_vol", "C5_sector_cap4", "C6_weekly", "C7_mom6_1", "C8_rank_blend", "C9_high52", "C10_skip5"],
         forward_observations=0,
         contamination_status="10 pre-specified variants on already-observed 2011-2026 stock history; median pairwise correlation 0.94 (RESEARCH_LEDGER row 25) -- the registry's own text already flags this as a near-single-test family despite 10 nominal candidates.",
         current_classification="SPENT (0/10 pass)", evidence_confidence="high",
         source_files=["research/momentum_construction/PLAN.md", "reports/momentum_construction_20260919/*_nav.csv"]),
    dict(family_id="vol_managed_momentum", tier=2, information_family="price momentum",
         strategy_family="portfolio construction/overlay",
         directories=["research/vol_managed_momentum", "reports/vol_managed_momentum_20260919"],
         candidate_labels=["V1_20pct_constvol", "V2_15pct_constvol", "V3_spy200d_gate", "V4_V1xV3", "V5_moreira_muir"],
         forward_observations=0,
         contamination_status="Overlays on the SAME frozen 12-1 signal used across the momentum program; only the exposure series varies, so these 5 are highly non-independent of each other and of momentum_construction/residual_momentum's underlying signal.",
         current_classification="SPENT (0/30 exposure-overlay cells beat baseline)", evidence_confidence="high",
         source_files=["research/vol_managed_momentum/PLAN.md", "reports/vol_managed_momentum_20260919/*_nav.csv"]),
    dict(family_id="residual_momentum", tier=2, information_family="price momentum",
         strategy_family="cross-sectional selection",
         directories=["research/residual_momentum", "reports/residual_momentum_20260919"],
         candidate_labels=["R1_capm_residual", "R2_ff3_residual", "R3_ff3_residual_std", "R4_risk_adj_raw"],
         forward_observations=0,
         contamination_status="Same stock universe/window as momentum_construction; no variant beat SPMO in both halves.",
         current_classification="SPENT", evidence_confidence="high",
         source_files=["research/residual_momentum/PLAN.md", "reports/residual_momentum_20260919/*_nav.csv"]),
    dict(family_id="overlay_control", tier=2, information_family="price momentum",
         strategy_family="portfolio construction/overlay",
         directories=["research/overlay_control", "reports/overlay_control_20260919"],
         candidate_labels=None,  # filled programmatically: 5 overlays x 6 buyable ETFs = 30
         forward_observations=0,
         contamination_status="Registered as a CONTROL study (how much any overlay improves a fund you can just buy), not a search for a pass; its 30 cells should not be read as 30 independent edge attempts.",
         current_classification="SPENT (overlays do not help; used as the momentum-program comparator)", evidence_confidence="high",
         source_files=["research/overlay_control/PLAN.md", "reports/overlay_control_20260919/diagnostics/*_base.csv"]),
    dict(family_id="momentum_verification_lab", tier=2, information_family="price momentum",
         strategy_family="meta-analysis/screening",
         directories=["research/momentum_verification", "research/momentum_lab"],
         candidate_labels=["momentum_verification_diagnostic", "momentum_lab_decision_rule"],
         forward_observations=0,
         contamination_status="Infrastructure/decision-rule registrations (survivorship diagnostic, selection rule fixed before ~25 variant results were seen), not Sharpe-gated candidates themselves; DECISION_RULE.md is the ONE file in the entire registry whose current sha256 does not match its registered hash (FAMILY_TRIAL_LEDGER.md line 3; registered_trials.csv row 41 hash_matches=False) -- flagged, not silently repaired, by the prior audit.",
         current_classification="infrastructure", evidence_confidence="high",
         source_files=["research/momentum_verification/PLAN.md", "research/momentum_lab/DECISION_RULE.md", "reports/evidence_audit_20260923/registered_trials.csv"]),

    # ---------------- Tier 3: never preregistered (estimates; some counts below are file-glob-derived and more precise than null_lab2's ranges, others remain ranges) ----------------
    dict(family_id="return_search", tier=3, information_family="price momentum",
         strategy_family="cross-sectional selection",
         directories=["research/return_search", "reports/return_search_20260919"],
         candidate_labels=None,  # filled programmatically from reports/return_search_20260919/dev/*_base.csv
         forward_observations=0,
         contamination_status="No PLAN.md hash in preregistrations.jsonl. Includes stock momentum candidate later diagnosed for survivorship bias by momentum_verification (own de-biasing study, +16pt CAGR correction).",
         current_classification="SPENT", evidence_confidence="medium",
         source_files=["reports/return_search_20260919/dev/*.csv", "research/RESEARCH_LEDGER_2026-09-23.md row 22"]),
    dict(family_id="sleeve_blend_higher_sharpe", tier=3, information_family="price momentum",
         strategy_family="portfolio construction/overlay",
         directories=["research/higher_sharpe.py", "research/blend_sleeves.py", "reports/higher_sharpe", "reports/sleeve_blend", "reports/strategy_research", "reports/config_sweep"],
         candidate_labels=None,  # filled programmatically by counting output CSVs/metrics in these 4 dirs, excluding controls/summaries
         forward_observations=0,
         contamination_status="No PLAN.md/spec hash in preregistrations.jsonl for any of these 4 output directories. Several strategy_research and higher_sharpe variants are PEAD-derived (pead_sue_*, pead_causal_ml_*, pead_reaction_confirmed, wide_pead_mtm), so this cluster is not fully independent of the PEAD information family either.",
         current_classification="SPENT (null_lab2 REPORT.md: 2024-25 eval, none qualifies; blend 0.27)", evidence_confidence="low",
         source_files=["reports/higher_sharpe/*.csv", "reports/sleeve_blend/*.csv", "reports/strategy_research/*.csv", "reports/config_sweep/*_metrics.json", "research/RESEARCH_LEDGER_2026-09-23.md row 31"]),
    dict(family_id="edge_probe_scripts", tier=3, information_family="earnings events",
         strategy_family="event study",
         directories=["research/edge_executable_probe.py", "research/edge_first_backtest.py", "research/edge_timing_probe.py", "research/edge_sue_placebo.py"],
         candidate_labels=["edge_executable_probe", "edge_first_backtest", "edge_timing_probe", "edge_sue_placebo_s2", "edge_sue_placebo_s3", "edge_sue_placebo_long_short", "edge_sue_placebo_large_sue"],
         forward_observations=0,
         contamination_status="Unregistered PEAD probes that precede and partly overlap the later registered pead_attack placebo design; edge_sue_placebo.py's several sub-variants are cited in pead_attack/PLAN.md sec.2 but were not themselves hashed into preregistrations.jsonl.",
         current_classification="SPENT (precursor/superseded by pead_attack)", evidence_confidence="low",
         source_files=["research/edge_sue_placebo.py", "reports/edge_first_backtest/daily_returns.csv", "reports/null_lab2/multiple_testing.json tier3"]),
    dict(family_id="crowding_downside_rotation", tier=3, information_family="positioning",
         strategy_family="time-series timing",
         directories=["research/crowding_unwind.py", "research/downside_rotation.py", "reports/crowding_unwind_20260919", "reports/downside_rotation_20260919"],
         candidate_labels=["crowding_unwind_base", "crowding_unwind_positioning_only", "crowding_unwind_price_only", "downside_rotation_primary", "downside_rotation_momentum_only", "downside_rotation_equal_weight"],
         forward_observations=0,
         contamination_status="crowding_unwind screens 14 commodity-ETF markets inside a single unregistered run (RESEARCH_LEDGER row 10) -- treated here as ~6 named output variants, but the internal 14-market screen is itself an unaudited multiple-comparison problem not reflected in that count. Shares COT/positioning information with cot(C1-C3).",
         current_classification="SPENT", evidence_confidence="low",
         source_files=["reports/crowding_unwind_20260919/*_base.csv", "reports/downside_rotation_20260919/*_base.csv"]),
    dict(family_id="momentum_gold_fund_designs", tier=3, information_family="price momentum",
         strategy_family="benchmark construction",
         directories=["reports/momentum_gold_20260919", "reports/momentum_fund_designs_20260919", "reports/momentum_gold_audit_20260921"],
         candidate_labels=None,  # count of fund-design report subfolders, filled programmatically where possible
         forward_observations=0,
         contamination_status="The 50/50 SPMO/GLD benchmark (`reports/momentum_gold_20260919/`) that the user independently recalled ('~20%/~1 Sharpe') was chosen post-hoc after this fund-design search, on already-viewed 2017-2026 history, disclosed explicitly in RESEARCH_LEDGER section 1 ('post-hoc follow-up... chosen after three other fund designs'). This is the single most important shots-before case for interpreting that number.",
         current_classification="FORWARD ONLY (benchmark; forward paper spec frozen 2026-09-20, first decision window 2026-10-01, zero fills at last check)", evidence_confidence="medium",
         source_files=["research/RESEARCH_LEDGER_2026-09-23.md section 1 and row 28-29", "reports/momentum_gold_20260919", "reports/momentum_fund_designs_20260919"]),
    dict(family_id="etf_convergence_share_class_liquidity", tier=3, information_family="ETF structure/basis",
         strategy_family="spread/relative value",
         directories=["research/etf_convergence_screen.py", "research/share_class.py", "research/liquidity_pressure.py",
                      "reports/etf_convergence_20260918", "reports/share_class_20260918", "reports/liquidity_pressure_20260918", "reports/edge_search_20260918"],
         candidate_labels=None,  # filled programmatically: etf_convergence 5 pairs + share_class 4 + liquidity_pressure 5 = 14
         forward_observations=0,
         contamination_status="RECONCILIATION FINDING (this workstream): research/etf_convergence_spec_20260918.json, share_class_spec_20260918.json and liquidity_pressure_spec_20260918.json exist on disk with 'written before any result' language, dated 2026-09-18, but NONE of the three appears in research/preregistrations.jsonl (grep-confirmed) -- a shadow-registration pattern (self-declared intent to preregister that was never actually logged). This cluster is also absent from null_lab2's tier-3 detail list, so it should be treated as additive to that estimate, not already included in it.",
         current_classification="SPENT (RESEARCH_LEDGER row 17: bounded nulls; share class -1.41)", evidence_confidence="medium",
         source_files=["research/etf_convergence_spec_20260918.json", "research/share_class_spec_20260918.json", "research/liquidity_pressure_spec_20260918.json", "reports/etf_convergence_20260918/*_base.csv", "reports/share_class_20260918/*_base.csv", "reports/liquidity_pressure_20260918/*_base.csv"]),
    dict(family_id="fx_session_screen", tier=3, information_family="FX intraday",
         strategy_family="spread/relative value",
         directories=["research/fx_session_screen.py", "reports/fx_session_20260918"],
         candidate_labels=["london_fix_reversal", "london_reversal", "new_york_continuation"],
         forward_observations=0,
         contamination_status="Same shadow-registration pattern as the row above: research/fx_session_spec_20260918.json and fx_session_amendment_1.md exist on disk but fx_session does not appear in preregistrations.jsonl. Also absent from null_lab2's tier-3 detail list -- additive, not already counted, in the 40-73 range. Shares FX-majors universe with fx_carry_vol, fx_news, fx_hedge_rebal.",
         current_classification="SPENT (RESEARCH_LEDGER row 16: bounded null)", evidence_confidence="medium",
         source_files=["research/fx_session_spec_20260918.json", "reports/fx_session_20260918/*_base_daily.csv"]),
    dict(family_id="pead_production_history", tier=3, information_family="earnings events",
         strategy_family="event study",
         directories=["reports/PEAD_INVESTIGATION_REPORT.md", "reports/PEAD_REVALIDATION_REPORT.md", "reports/PHASE_7_FINAL_REPORT.md",
                      "reports/pead_backtest_report.json", "reports/pead_baseline_comparison_original_75.json", "reports/pead_expanded_validation_report.json",
                      "reports/pead_liquidity_tier_report.json", "reports/pead_ml_filter_report.json", "reports/pead_significance_report.json",
                      "reports/pead_walk_forward_expanded_report.json", "reports/phase3_ml_filter_report.json", "reports/phase6_walk_forward_report.json",
                      "reports/pead_live_backtest_monte_carlo.json"],
         candidate_labels=["phase3_ml_filter", "phase6_walk_forward", "phase7_final", "pead_baseline_comparison_original_75",
                            "pead_expanded_validation", "pead_liquidity_tier", "pead_ml_filter", "pead_significance",
                            "pead_walk_forward_expanded", "pead_live_backtest_monte_carlo", "pead_investigation", "pead_revalidation", "pead_backtest_report"],
         forward_observations=0,
         contamination_status="Predates the registration system entirely: these reports are dated 2026-08-18 (mtime), roughly a month before the first preregistration on 2026-09-17 (research/PREREGISTRATION_pead_2004_2014.md). This is the largest single block of informal, never-registered development history in the project and is the direct ancestor of the current PEAD production book (bot/) and of pead_attack's placebo design. Not counted at all in null_lab2's tier-3 estimate (which starts its narrative from research/return_search onward).",
         current_classification="SPENT (superseded by the registered pead_2004_2014 replication and pead_attack placebo)", evidence_confidence="medium",
         source_files=["reports/PHASE_7_FINAL_REPORT.md", "reports/pead_significance_report.json", "reports/pead_ml_filter_report.json"]),
    dict(family_id="pead_production_bot_live", tier=3, information_family="earnings events",
         strategy_family="event study",
         directories=["bot/", "reports/forward/PEAD_FORWARD_DIAGNOSIS.md"],
         candidate_labels=["pead_bot_v1_paper"],
         forward_observations=3,
         contamination_status="Paper bot live since 2026-08-18. 89 of 92 ledger events are backfill; live decisions are logged ~3.5h after the close they fill at, so RESEARCH_LEDGER row 1 counts none of them as clean forward evidence. PEAD decisions are excluded from the hash-chained forward registry until a pead_bot_v2 entry-convention fix is itself registered (RESEARCH_LEDGER section 5).",
         current_classification="SPENT as an edge (event-exposure product); not a source of clean forward evidence yet", evidence_confidence="high",
         source_files=["research/RESEARCH_LEDGER_2026-09-23.md row 1 and section 5", "reports/forward/PEAD_FORWARD_DIAGNOSIS.md"]),
    dict(family_id="reversal_research_20260921", tier=3, information_family="price momentum",
         strategy_family="cross-sectional selection",
         directories=["reports/reversal_research_20260921"],
         candidate_labels=["reversal_5d"],
         forward_observations=0,
         contamination_status="Registration exists only in its own folder, not in preregistrations.jsonl; the run crashed (sector ETFs missing from panel) before producing a result (RESEARCH_LEDGER row 30).",
         current_classification="INCOMPLETE (not a completed trial)", evidence_confidence="low",
         source_files=["research/RESEARCH_LEDGER_2026-09-23.md row 30"]),
    dict(family_id="edge_graveyard_osap_meta", tier=3, information_family="academic-anomaly replication",
         strategy_family="meta-analysis/screening",
         directories=["research/edge_graveyard", "reports/edge_graveyard"],
         candidate_labels=["osap_meta_study"],
         forward_observations=0,
         contamination_status="Meta-study over already-published OSAP predictor performance since 2015; the direct upstream contamination source for survivor_hybrid's 53-survivor universe (RESEARCH_LEDGER row 31 'meta' entry; survivor_hybrid PLAN.md disclosure).",
         current_classification="meta (not itself a trial)", evidence_confidence="medium",
         source_files=["reports/edge_graveyard", "research/EDGE_GRAVEYARD_PLAN.md"]),
]


def expand_programmatic_candidate_labels(families: list[dict], repo_root: str) -> None:
    """Fill in candidate_labels=None rows by globbing the actual output
    directories, so multi-candidate counts for return_search/multiasset/
    overlay_control/etc. come from the files on disk rather than being
    retyped by hand. Mutates `families` in place.
    """
    import glob
    import os

    def g(pattern):
        return sorted(glob.glob(os.path.join(repo_root, pattern)))

    for fam in families:
        if fam["candidate_labels"] is not None:
            continue
        fid = fam["family_id"]
        if fid == "multiasset(17-sleeve inclusion + 5-sleeve holdout)":
            import pandas as pd
            df = pd.read_csv(os.path.join(repo_root, "reports/multiasset/dev_sleeve_returns.csv"), nrows=0)
            fam["candidate_labels"] = [c for c in df.columns if c != df.columns[0]]
        elif fid == "overlay_control":
            files = g("reports/overlay_control_20260919/diagnostics/*__O*_base.csv")
            fam["candidate_labels"] = [os.path.basename(f)[:-len("_base.csv")] for f in files]
        elif fid == "return_search":
            files = g("reports/return_search_20260919/dev/*_base.csv")
            fam["candidate_labels"] = sorted({os.path.basename(f)[:-len("_base.csv")] for f in files})
        elif fid == "sleeve_blend_higher_sharpe":
            labels = []
            for f in g("reports/higher_sharpe/*.csv"):
                b = os.path.basename(f)
                if b in ("SPY_control.csv", "SPY_control_stress.csv") or b.endswith("_stress.csv"):
                    continue
                labels.append("higher_sharpe/" + b[:-4])
            for f in g("reports/sleeve_blend/*.csv"):
                b = os.path.basename(f)
                if b == "selection_correlations.csv":
                    continue
                labels.append("sleeve_blend/" + b[:-4])
            for f in g("reports/strategy_research/*.csv"):
                b = os.path.basename(f)
                if b in ("SPY_caps_only.csv", "current_pead_mark_to_market.csv"):
                    continue
                labels.append("strategy_research/" + b[:-4])
            for f in g("reports/config_sweep/*_metrics.json"):
                labels.append("config_sweep/" + os.path.basename(f)[:-len("_metrics.json")])
            fam["candidate_labels"] = labels
        elif fid == "etf_convergence_share_class_liquidity":
            labels = []
            for f in g("reports/etf_convergence_20260918/*_base.csv"):
                labels.append("etf_convergence/" + os.path.basename(f)[:-len("_base.csv")])
            for f in g("reports/share_class_20260918/*_base.csv"):
                labels.append("share_class/" + os.path.basename(f)[:-len("_base.csv")])
            for f in g("reports/liquidity_pressure_20260918/*_base.csv"):
                labels.append("liquidity_pressure/" + os.path.basename(f)[:-len("_base.csv")])
            fam["candidate_labels"] = labels
        elif fid == "momentum_gold_fund_designs":
            labels = []
            for sub in ("reports/momentum_gold_20260919", "reports/momentum_fund_designs_20260919", "reports/momentum_gold_audit_20260921"):
                d = os.path.join(repo_root, sub)
                if os.path.isdir(d):
                    labels.append(os.path.basename(sub))
            fam["candidate_labels"] = labels or ["momentum_gold_selection"]
        else:
            fam["candidate_labels"] = [fid]


# ---------------------------------------------------------------------------
# Key results for the "shots before result" analysis (task section 3)
# ---------------------------------------------------------------------------
KEY_RESULTS = [
    dict(key="tsy_month_end", family_id="tsy_month_end(M)", registered_at="2026-09-23T22:31:39-0700",
         headline_p=0.006, p_description="dev shift-null p (0.006); validation missed (0.69 vs 0.75 gate; shift p=0.005, bootstrap p=0.004)"),
    dict(key="commodity_roll", family_id="commodity_roll", registered_at="2026-09-23T23:16:05-0700",
         headline_p=0.0064, p_description="dev bootstrap p (0.0064); validation FAILED (0.21 vs 0.75, p=0.24)"),
    dict(key="multiasset_sleeves", family_id="multiasset(17-sleeve inclusion + 5-sleeve holdout)", registered_at="2026-09-18T11:52:15-0700",
         headline_p=None, p_description="no null/p-value in the registered gate (flat Sharpe>=0.30 inclusion bar, HAC-t>=2.0 at holdout); 5/17 dev-passed, holdout FAILED"),
    dict(key="insider_N3_N4", family_id="insider(N1-N4)", registered_at="2026-09-19T01:43:31-0700",
         headline_p=None, p_description="no dev null in the pre-amendment OLD_ABS_NO_NULL gate; N3/N4 dev Sharpe 0.77/0.51, both FAILED validation (0.49/0.51 vs 0.75)"),
    dict(key="rebalancing_R2_R3", family_id="rebalancing(R1-R3)", registered_at="2026-09-19T03:17:37-0700",
         headline_p=None, p_description="no dev null (pre-amendment gate); R2/R3 dev Sharpe 0.74/0.82, both FAILED validation (0.63/0.45 vs 0.75)"),
    dict(key="pead", family_id="pead_attack", registered_at="2026-09-23T05:06:57-0700",
         headline_p=0.113, p_description="pead_attack P1 primary: real production book vs 10,000 within-date permutations of calibrated probabilities (Kelly size, SUE-sign direction kept), one-sided p on marked excess Sharpe. The registered pead_2004_2014 HAC-t replication (2026-09-17) is the family's earlier, separate registration and is also reported in the family table."),
]
