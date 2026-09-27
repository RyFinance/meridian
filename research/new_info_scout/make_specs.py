"""Write research/power design specs for every new-information family and run plan_check on them.

Synthetic / analytic only. No real returns are read. Every correlation input is stated and labelled ASSUMPTION.
Gates follow Protocol Amendment 3 for a batch of k = 2 (alpha = 0.025): amendment-2 development gate, P2 validation
gate (one-sided p < 0.05/k_val with k_val = 2 per the draft Amendment 4 Q2, stress mean > 0, Sharpe floor 0.30).

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.new_info_scout.make_specs
Writes research/new_info_scout/specs/*.json and reports/new_info_scout/power/<name>.{json,txt}.
"""
from __future__ import annotations

import json
import pathlib

from research.power import plan_check as PC

HERE = pathlib.Path(__file__).resolve().parent
SPECS = HERE / "specs"
OUT = HERE.parents[1] / "reports" / "new_info_scout" / "power"


def gates(stress: float) -> dict:
    return {"batch_k": 2, "stress_drag_sr": stress, "dev": {"kind": "amendment2"},
            "val": {"kind": "tstat", "alpha": "auto", "floor": 0.30}, "pav": {"k_val": 2, "floor": 0.30}}


def ts_scen(vol: float, sharpes=(0.2, 0.3, 0.45, 0.6, 0.8)) -> list[dict]:
    return [{"label": f"implied net S={s}", "params": {"mean_ann": s * vol, "vol_ann": vol}} for s in sharpes]


SPEC_LIST: list[dict] = [
    # F1 --------------------------------------------------------------------------------------------------------
    {"name": "nis_f1_pd_treasury_inventory",
     "description": "NY Fed FR 2004 primary-dealer net outright positions in long Treasury coupons (inventory stock), "
                    "weekly signal, daily P&L of a constant-duration 10y Treasury position. Signal 1998-01-28+ "
                    "(first trade 1998-05-01 after a 13-week minimum history; flat 13 weeks after the 2001-07 and "
                    "2013-04 bucket-definition breaks).",
     "assumptions": [
         "dev 1998-05-01..2012-06-29 (14.2y less 0.25y break flat = 13.9y), val 2012-07-02..2026-08-31 (14.2y less 0.25y = 13.9y)",
         "daily 10y-duration Treasury returns have ~zero autocorrelation; weekly-held position => D ASSUMPTION 1.1",
         "exkurt 3 for daily Treasury returns (ASSUMPTION, typical)",
         "vol 6.5%/yr for a 7-duration Treasury position (ASSUMPTION)",
         "base cost 1 bp/side, stress 3 bp/side, turnover 0.3/week => stress drag 0.62%/yr / 6.5% = 0.10 Sharpe",
         "implied net Sharpe from literature (Fleming-Rosenberg 2008 inventory compensation; intermediary asset "
         "pricing) discounted for decay: 0.2-0.45; base 0.30 (ASSUMPTION)",
         "batch k=2, k_val=2"],
     "design": "timeseries",
     "params": {"periods_per_year": 252, "autocorr": {"model": "lrv", "D": 1.1}, "skew": 0.0, "exkurt": 3.0,
                "mean_ann": 0.0195, "vol_ann": 0.065},
     "windows": {"dev_years": 13.9, "val_years": 13.9}, "gates": gates(0.10),
     "scenarios": ts_scen(0.065) + [
         {"label": "D=1.3 (weekly overlap residue), S=0.3", "params": {"autocorr": {"model": "lrv", "D": 1.3}}},
         {"label": "IEF-only window 2002-08.. (24.0y), S=0.3", "windows": {"dev_years": 11.9, "val_years": 12.1}},
         {"label": "D=1.0 (Amendment-4 Q3 floor), S=0.7 check", "params": {"autocorr": {"model": "lrv", "D": 1.0},
                                                                            "mean_ann": 0.0455}},
         {"label": "D=1.0, batch k=1 (registered alone), S=0.7", "params": {"autocorr": {"model": "lrv", "D": 1.0},
                                                                             "mean_ann": 0.0455},
          "gates": {"batch_k": 1, "pav": {"k_val": 1, "floor": 0.30}}},
         {"label": "D=1.1, batch k=1, S=0.7", "params": {"mean_ann": 0.0455},
          "gates": {"batch_k": 1, "pav": {"k_val": 1, "floor": 0.30}}}]},
    # F2 --------------------------------------------------------------------------------------------------------
    {"name": "nis_f2_fed_custody_official_flows",
     "description": "H.4.1 marketable Treasuries held in custody for foreign official accounts (FRED WMTSECL1, "
                    "weekly Wed level, 2002-12-18+), 4-week change z-score -> 10y duration position, daily P&L.",
     "assumptions": ["dev 2003-07..2014-12 (11.5y), val 2015-01..2026-08 (11.7y)",
                     "D ASSUMPTION 1.1; exkurt 3; vol 6.5%",
                     "direction of the effect is NOT pinned down by the literature (continuation vs reversal): "
                     "prior implied net Sharpe 0.1-0.3 (ASSUMPTION)",
                     "stress drag 0.10"],
     "design": "timeseries",
     "params": {"periods_per_year": 252, "autocorr": {"model": "lrv", "D": 1.1}, "exkurt": 3.0,
                "mean_ann": 0.013, "vol_ann": 0.065},
     "windows": {"dev_years": 11.5, "val_years": 11.7}, "gates": gates(0.10), "scenarios": ts_scen(0.065)},
    # F3 --------------------------------------------------------------------------------------------------------
    {"name": "nis_f3_margin_debt_deleveraging",
     "description": "FINRA monthly customer margin debit balances (1997-01+), 12-month growth z-score -> SPY "
                    "timing, monthly.",
     "assumptions": ["published ~3rd week of the following month; revisions small but unaudited",
                     "dev 1997-03..2011-10 (14.7y), val 2011-11..2026-07 (14.7y)",
                     "monthly equity returns: skew -0.6, exkurt 2, D ASSUMPTION 1.2 (persistent signal)",
                     "implied net Sharpe 0.15-0.3 (ASSUMPTION; the 'margin debt peaks' literature is mostly "
                     "contemporaneous)", "stress drag 0.03"],
     "design": "timeseries",
     "params": {"periods_per_year": 12, "autocorr": {"model": "lrv", "D": 1.2}, "skew": -0.6, "exkurt": 2.0,
                "mean_ann": 0.0375, "vol_ann": 0.15},
     "windows": {"dev_years": 14.7, "val_years": 14.7}, "gates": gates(0.03), "scenarios": ts_scen(0.15)},
    # F4 --------------------------------------------------------------------------------------------------------
    {"name": "nis_f4_treasury_supply_maturity",
     "description": "Maturity-weighted marketable Treasury debt (fiscaldata MSPD, monthly 2001-01+) / GDP "
                    "(Greenwood-Vayanos 2014) -> duration timing, monthly.",
     "assumptions": ["dev 2001-03..2013-10 (12.7y), val 2013-11..2026-08 (12.8y)",
                     "signal AR(1) ~0.99 monthly: returns ~iid but the test has ~2-3 independent regimes; D "
                     "ASSUMPTION 1.5 as a partial allowance", "implied net Sharpe 0.2-0.4 (G-V 1952-2008 in-sample, "
                     "halved for decay)", "stress drag 0.02"],
     "design": "timeseries",
     "params": {"periods_per_year": 12, "autocorr": {"model": "lrv", "D": 1.5}, "exkurt": 1.0,
                "mean_ann": 0.0195, "vol_ann": 0.065},
     "windows": {"dev_years": 12.7, "val_years": 12.8}, "gates": gates(0.02), "scenarios": ts_scen(0.065)},
    # F5 --------------------------------------------------------------------------------------------------------
    {"name": "nis_f5_crypto_dated_basis_term",
     "description": "BTC dated-futures annualised basis (BitMEX 2014-11+, Deribit 2016-12+, Binance 2020-09+) "
                    "as a timing signal for BTC, daily (365).",
     "assumptions": ["only BTC/ETH have dated futures on the free archives: no cross-section (Binance USD-M "
                     "delivery folders are BTC/ETH only)", "dev 2015-01..2020-10 (5.8y), val 2020-11..2026-08 (5.8y)",
                     "D ASSUMPTION 1.1, skew -0.5, exkurt 10, vol 65%", "implied net Sharpe 0.3-0.8 (ASSUMPTION)",
                     "stress drag 0.02"],
     "design": "timeseries",
     "params": {"periods_per_year": 365, "autocorr": {"model": "lrv", "D": 1.1}, "skew": -0.5, "exkurt": 10.0,
                "mean_ann": 0.325, "vol_ann": 0.65},
     "windows": {"dev_years": 5.8, "val_years": 5.8}, "gates": gates(0.02),
     "scenarios": ts_scen(0.65, (0.3, 0.5, 0.8, 1.2, 1.6))},
    # F6 --------------------------------------------------------------------------------------------------------
    {"name": "nis_f6_cross_venue_basis_dispersion",
     "description": "Dispersion of perp/dated/spot basis for the same coin across Binance, Bybit, BitMEX, Deribit, "
                    "OKX; convergence trade, daily 2020-01+ (the first date >= 3 venues are survivor-free).",
     "assumptions": ["dev 2020-01..2023-04 (3.3y), val 2023-05..2026-08 (3.3y)",
                     "D ASSUMPTION 1.3 (convergence P&L autocorrelated), skew -1, exkurt 15",
                     "implied net Sharpe after cross-venue fees/borrow 0.5-1.5 (ASSUMPTION)",
                     "stress drag 0.3 (fees dominate)"],
     "design": "timeseries",
     "params": {"periods_per_year": 365, "autocorr": {"model": "lrv", "D": 1.3}, "skew": -1.0, "exkurt": 15.0,
                "mean_ann": 0.08, "vol_ann": 0.10},
     "windows": {"dev_years": 3.3, "val_years": 3.3}, "gates": gates(0.3),
     "scenarios": ts_scen(0.10, (0.5, 0.8, 1.2, 1.6, 2.0))},
    # F7 --------------------------------------------------------------------------------------------------------
    {"name": "nis_f7_binance_oi_positioning_xs",
     "description": "Binance USD-M metrics (open interest, top-trader and taker long/short ratios, 2020-09+), "
                    "cross-sectional quintile long-short on OI-growth/positioning, daily.",
     "assumptions": ["dev 2020-09..2023-08 (3.0y), val 2023-09..2026-08 (3.0y)", "N ~100 liquid perps",
                     "rho_resid 0.3 is the variance share of the factor the signal tilts to (ASSUMPTION; Q4 "
                     "calibration from pre-dev IC dispersion impossible: no pre-dev data)", "rho_signal 0.25",
                     "signal_autocorr 0.8, cost 8 bp one-way, IC 0.015 base"],
     "design": "long_short",
     "params": {"n_assets": 100, "periods_per_year": 365, "ic": 0.015, "cs_dispersion": 0.04, "quantile": 0.2,
                "rho_resid": 0.3, "rho_signal": 0.25, "signal_autocorr": 0.8, "cost_bps_one_way": 8,
                "spread_autocorr": 0.05, "skew": -0.3, "exkurt": 10.0},
     "windows": {"dev_years": 3.0, "val_years": 3.0}, "gates": gates(0.15),
     "scenarios": [{"label": f"IC={ic} rho={r}", "params": {"ic": ic, "rho_resid": r}}
                   for ic in (0.01, 0.02, 0.03) for r in (0.2, 0.4)]
                  + [{"label": "IC=0.02 rho=0.3 LITERAL", "params": {"ic": 0.02, "rho_signal": 1.0,
                                                                   "correlation_mode": "equicorrelated_bets"}}]},
    # F8 --------------------------------------------------------------------------------------------------------
    {"name": "nis_f8_liquidation_cascades",
     "description": "Forced-liquidation cascades (Binance COIN-M liquidationSnapshot 2023-06..2024-10 only; OI-drop "
                    "proxy from metrics 2020-09+) -> post-cascade reversal, event study.",
     "assumptions": ["events: cascade days, ~40/yr across majors", "cascades hit all coins together: clusters mean 3, "
                     "icc 0.5 (ASSUMPTION)", "car_sd 4%, 3-day hold, gross 50 bp, cost 8 bp",
                     "windows: proxy 2020-09..2026-08 split 3.0/3.0; literal snapshot data would be 0.65/0.65y"],
     "design": "event_study",
     "params": {"events_per_year": 40, "car_sd": 0.04, "hold_days": 3, "icc": 0.5,
                "concurrency": {"model": "clusters", "mean_size": 3, "cv": 0.5}, "portfolio_autocorr": 0.0,
                "mean_car": 0.005, "cost_per_event": 0.0008, "days_per_year": 365, "skew": 0.5, "exkurt": 8.0},
     "windows": {"dev_years": 3.0, "val_years": 3.0}, "gates": gates(0.1),
     "scenarios": [{"label": "snapshot archive only (0.65+0.65y)", "windows": {"dev_years": 0.65, "val_years": 0.65}},
                   {"label": "gross 150 bp", "params": {"mean_car": 0.015}}]},
    # F9 --------------------------------------------------------------------------------------------------------
    {"name": "nis_f9_stablecoin_supply",
     "description": "Aggregate stablecoin net issuance (DefiLlama, 2017-11+, usable 2019+) -> BTC timing, daily.",
     "assumptions": ["dev 2019-01..2022-10 (3.8y), val 2022-11..2026-08 (3.8y)", "not point-in-time (re-derived "
                     "history)", "D 1.1, skew -0.5, exkurt 10, vol 60%", "implied 0.2-0.6"],
     "design": "timeseries",
     "params": {"periods_per_year": 365, "autocorr": {"model": "lrv", "D": 1.1}, "skew": -0.5, "exkurt": 10.0,
                "mean_ann": 0.24, "vol_ann": 0.60},
     "windows": {"dev_years": 3.8, "val_years": 3.8}, "gates": gates(0.02), "scenarios": ts_scen(0.60)},
    # F10 -------------------------------------------------------------------------------------------------------
    {"name": "nis_f10_index_inclusion_flows",
     "description": "S&P 500 additions/deletions, announcement next open -> effective-date close (~5 days), "
                    "1995-2026, fixed-dollar calendar-time book.",
     "assumptions": ["~45 changes/yr; adds and deletes announced together: clusters mean 2, cv 0.5, icc 0.05",
                     "car_sd 5%; post-2010 effect < 1% announcement-to-effective (Greenwood-Sammon 2025): base "
                     "gross 30 bp; cost 10 bp", "dev 1995-2010 (15.5y), val 2011-2026 (15.7y)",
                     "DATA NOT ASSEMBLABLE: removed/acquired names lack free prices (survivorship)"],
     "design": "event_study",
     "params": {"events_per_year": 45, "car_sd": 0.05, "hold_days": 5, "icc": 0.05,
                "concurrency": {"model": "clusters", "mean_size": 2, "cv": 0.5}, "portfolio_autocorr": 0.0,
                "mean_car": 0.003, "cost_per_event": 0.001},
     "windows": {"dev_years": 15.5, "val_years": 15.7}, "gates": gates(0.1),
     "scenarios": [{"label": f"gross {g} bp", "params": {"mean_car": g / 1e4}} for g in (30, 100, 200)]},
    # F11 -------------------------------------------------------------------------------------------------------
    {"name": "nis_f11_cftc_tff_dealer",
     "description": "CFTC Traders-in-Financial-Futures dealer/intermediary net positions in Treasury and equity-"
                    "index futures (2006-06+, weekly, released Friday for Tuesday) -> futures timing, daily P&L.",
     "assumptions": ["dev 2006-07..2016-07 (10.0y), val 2016-08..2026-08 (10.1y)", "D 1.1, exkurt 3, vol 6.5%",
                     "implied 0.2-0.3", "COT information family already viewed/spent in research/cot"],
     "design": "timeseries",
     "params": {"periods_per_year": 252, "autocorr": {"model": "lrv", "D": 1.1}, "exkurt": 3.0,
                "mean_ann": 0.0163, "vol_ann": 0.065},
     "windows": {"dev_years": 10.0, "val_years": 10.1}, "gates": gates(0.05), "scenarios": ts_scen(0.065)},
    # F12 -------------------------------------------------------------------------------------------------------
    {"name": "nis_f12_repo_quarter_end_gsib",
     "description": "Quarter-end G-SIB window dressing: repo/SOFR spikes and the bill/2y reaction around the 4 "
                    "quarter-ends a year, event study on one instrument.",
     "assumptions": ["4 events/yr, one instrument, clusters of 1 (icc irrelevant)",
                     "SOFR/TGCR 2018-04+ (8.4y); GCF repo 2005+ (21y) as the long scenario",
                     "car_sd 0.4% (2y note, 5 days), gross 5 bp, cost 1 bp"],
     "design": "event_study",
     "params": {"events_per_year": 4, "car_sd": 0.004, "hold_days": 5, "icc": 0.0,
                "concurrency": {"model": "clusters", "mean_size": 1}, "portfolio_autocorr": 0.0,
                "mean_car": 0.0005, "cost_per_event": 0.0001},
     "windows": {"dev_years": 4.2, "val_years": 4.2}, "gates": gates(0.05),
     "scenarios": [{"label": "GCF 2005+ (10.5+10.5y)", "windows": {"dev_years": 10.5, "val_years": 10.5}},
                   {"label": "gross 20 bp", "params": {"mean_car": 0.002}}]},
    # F13 -------------------------------------------------------------------------------------------------------
    {"name": "nis_f13_13f_holdings_changes",
     "description": "13F institutional-ownership breadth / change, quarterly long-short on ~1000 US stocks, "
                    "structured 13F data 2013q2+.",
     "assumptions": ["dev 2013-08..2019-12 (6.4y), val 2020-01..2026-08 (6.6y)", "IC 0.02 quarterly, rho_resid 0.3, "
                     "rho_signal 0.25, cost 10 bp", "OSAP DelBreadth/IO predictors already viewed; prices survivor-only"],
     "design": "long_short",
     "params": {"n_assets": 1000, "periods_per_year": 4, "ic": 0.02, "cs_dispersion": 0.12, "quantile": 0.2,
                "rho_resid": 0.3, "rho_signal": 0.25, "signal_autocorr": 0.6, "cost_bps_one_way": 10,
                "spread_autocorr": 0.0, "skew": 0.0, "exkurt": 2.0},
     "windows": {"dev_years": 6.4, "val_years": 6.6}, "gates": gates(0.05)},
    # F15 -------------------------------------------------------------------------------------------------------
    {"name": "nis_f15_tga_reserves_liquidity",
     "description": "Treasury General Account / bank reserves / ON RRP (H.4.1 via FRED WTREGEN, WRESBAL; RRPONTSYD), "
                    "weekly 2002-12+, 4-week change -> SPY timing, daily P&L.",
     "assumptions": ["dev 2003-07..2014-12 (11.5y), val 2015-01..2026-08 (11.7y)", "D 1.1, skew -0.4, exkurt 8, "
                     "vol 16%", "implied 0.1-0.3; the 2022-23 'liquidity' narrative is known to the director",
                     "stress drag 0.02"],
     "design": "timeseries",
     "params": {"periods_per_year": 252, "autocorr": {"model": "lrv", "D": 1.1}, "skew": -0.4, "exkurt": 8.0,
                "mean_ann": 0.032, "vol_ann": 0.16},
     "windows": {"dev_years": 11.5, "val_years": 11.7}, "gates": gates(0.02), "scenarios": ts_scen(0.16)},
    # F16 -------------------------------------------------------------------------------------------------------
    {"name": "nis_f16_buyback_issuance_events",
     "description": "Buyback authorisations / follow-on issuance announcements from 8-K text (EDGAR 2004-08+), "
                    "next-open entry, 20-day hold, fixed-dollar calendar-time book.",
     "assumptions": ["~1,000 informative events/yr; icc 0.02 same-day; seasonal clustering around earnings "
                     "(season_fraction 0.4)", "car_sd 6% over 20d; post-announcement drift after decay 30 bp gross; "
                     "cost 10 bp", "dev 2004-09..2015-06 (10.8y), val 2015-07..2026-08 (11.2y)",
                     "DATA NOT ASSEMBLABLE: survivor-only prices; www.sec.gov intermittently 403 without email; "
                     "OSAP ShareRepurchase/ShareIss viewed; fundamentals F1 failed"],
     "design": "event_study",
     "params": {"events_per_year": 1000, "car_sd": 0.06, "hold_days": 20, "icc": 0.02,
                "concurrency": {"model": "seasonal_poisson", "season_fraction": 0.4, "n_seasons": 4},
                "portfolio_autocorr": 0.0, "mean_car": 0.003, "cost_per_event": 0.001},
     "windows": {"dev_years": 10.8, "val_years": 11.2}, "gates": gates(0.1),
     "scenarios": [{"label": f"gross {g} bp", "params": {"mean_car": g / 1e4}} for g in (20, 30, 60)]},
    # F14 -------------------------------------------------------------------------------------------------------
    {"name": "nis_f14_borrow_constraint_proxy",
     "description": "Borrow-constraint proxy (no free lending-fee data): FINRA bi-monthly short interest / "
                    "days-to-cover change, 2018-01+ bulk file, long-short on ~500 US stocks, 2 periods/month.",
     "assumptions": ["dev 2018-02..2022-04 (4.2y), val 2022-05..2026-08 (4.3y)", "IC 0.015, rho 0.3/0.25, "
                     "cost 10 bp, signal_autocorr 0.8", "OSAP ShortInterest viewed; survivor-only prices"],
     "design": "long_short",
     "params": {"n_assets": 500, "periods_per_year": 24, "ic": 0.015, "cs_dispersion": 0.06, "quantile": 0.2,
                "rho_resid": 0.3, "rho_signal": 0.25, "signal_autocorr": 0.8, "cost_bps_one_way": 10,
                "spread_autocorr": 0.0, "skew": 0.0, "exkurt": 2.0},
     "windows": {"dev_years": 4.2, "val_years": 4.3}, "gates": gates(0.05)},
]


def main() -> None:
    SPECS.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for spec in SPEC_LIST:
        (SPECS / f"{spec['name']}.json").write_text(json.dumps(spec, indent=1))
        rep = PC.run_spec(spec)
        (OUT / f"{spec['name']}.json").write_text(json.dumps(rep, indent=1))
        (OUT / f"{spec['name']}.txt").write_text(PC.text(rep))
        imp = next((r for r in rep["power"] if r.get("world") == "implied_by_primitives"), None) \
            if isinstance(rep.get("power"), list) else None
        summary.append({"name": spec["name"], "years": spec["windows"]["dev_years"] + spec["windows"]["val_years"],
                        "joint_0.7": rep["joint_power_at_0.7"], "false_pass": rep["false_pass_zero_net"],
                        "verdict": rep["verdict"], "verdict_proposed": rep["verdict_with_proposed_val_gate"],
                        "mde": rep["mde"], "implied": rep.get("implied"),
                        "scenarios": [{k: s.get(k) for k in ("label", "implied_sharpe_net", "joint_proposed_at_implied",
                                                             "years_80_joint_proposed_at_implied")}
                                      for s in rep.get("scenarios", [])]})
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    for s in summary:
        print(f"{s['name']:40s} yrs {s['years']:5.1f}  joint@0.7 {s['joint_0.7']:.3f}  fp {s['false_pass']:.4f}  "
              f"{s['verdict']}/{s['verdict_proposed']}")


if __name__ == "__main__":
    main()
