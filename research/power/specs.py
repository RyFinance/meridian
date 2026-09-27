"""research.power.specs -- the example / retrospective / prospective design specs (written to examples/*.json).

Parameter provenance (READ-ONLY use of existing report JSON; no family's evaluate.py is run, no returns computed):
  tsy_month_end   reports/tsy_month_end/dev_results.json: base active Sharpe 0.664, stress 0.461 (drag 0.20),
                  shift-null mean/sd -0.098/0.342 over 11.99y -> kappa0 1.185, D = 1.40; per-window sd 133 bp
                  (reports/future_lab2/REPORT.md).
  commodity_roll  reports/commodity_roll/dev_results.json: base 0.596, stress 0.288 (drag 0.31), bootstrap p 0.0064
                  -> implied D_boot = (0.596 sqrt(10.44) / z_{0.9936})^2 = 0.60 (mean-reverting spread noise).
  fx_hedge_rebal  reports/fx_hedge_rebal/dev_results.json: 360 events, base 0.09, stress -0.52 (drag 0.61),
                  permutation null mean -0.27; per-pair event sd 32 bp is backed out of the book Sharpe at icc 0.4.
  pead_2004_2014  reports/pead_2004_2014/REPORT.md: 5,604 traded events / 10.96y, 20-day hold.
  IEF-SHY         reports/structural_frontier/term_dev_results.json: active 0.569, null q95 0.468 -> kappa0 0.986.
  insider, etf_hybrids, multiasset: gate structure from reports/null_lab2/gate_table.csv, vol/phi from
                  research/null_lab2/sim_params.py (so they are directly comparable with null_lab2's calibration).
Everything else marked ASSUMPTION in each spec's `assumptions` list.
"""
from __future__ import annotations

import itertools
import json
import pathlib

from research.power.designs import crash_moments, one_factor_portfolio_moments

EX = pathlib.Path(__file__).with_name("examples")

A2 = {"kind": "amendment2"}
VAL75 = {"kind": "sharpe", "value": 0.75, "alpha": "auto"}


def _spec(name, design, params, dev, val, gates, desc, assumptions=(), power=None, scenarios=None):
    s = {"name": name, "description": desc, "assumptions": list(assumptions), "design": design, "params": params,
         "windows": {"dev_years": dev, "val_years": val}, "gates": gates}
    if power:
        s["power"] = power
    if scenarios:
        s["scenarios"] = scenarios
    return s


# ============================================================================================ retrospective
def retrospective() -> list[dict]:
    R = []
    R.append(_spec("retro_tsy_month_end", "event_study",
                   {"events_per_year": 12, "car_sd": 0.0133, "hold_days": 3, "icc": 0.0,
                    "concurrency": {"model": "clusters", "mean_size": 1}, "portfolio_autocorr": {"model": "lrv", "D": 1.40},
                    "mean_car": 0.0030, "cost_per_event": 0.0004},
                   11.99, 11.63,
                   {"batch_k": 1, "stress_drag_sr": 0.20, "dev": {"kind": "amendment2", "null_center_sr": -0.098}, "val": VAL75},
                   "TLT last-3-sessions month-end window, active vs C_EXP; shift-null gate (registered).",
                   ["one window per month on one asset => m_w = 1, icc irrelevant",
                    "D = 1.40 from the family's own shift-null sd (0.342 x sqrt(11.99))^2"],
                   {"dev_estimate": 0.664}))
    R.append(_spec("retro_commodity_roll", "carry",
                   {"n_assets": 3, "periods_per_year": 252, "rho": None,
                    "blocks": {"sizes": [2, 1], "rho_within": 0.5, "rho_between": 0.1},
                    "autocorr": {"model": "lrv", "D": 0.60}, "skew": -0.3, "exkurt": 8.0},
                   10.44, 9.71, {"batch_k": 2, "stress_drag_sr": 0.31, "dev": A2, "val": VAL75},
                   "Same-commodity deferred-minus-front ETF spreads (USL-USO, UNL-UNG, DBC-GSG), daily book.",
                   ["ASSUMPTION pair correlation: crude & broad 0.5, natgas 0.1",
                    "ASSUMPTION daily skew -0.3 / excess kurtosis 8 (contango blow-ups)",
                    "D = 0.60 implied by the registered bootstrap p=0.0064 at Sharpe 0.596"],
                   {"dev_estimate": 0.596}))
    R.append(_spec("retro_fx_hedge_rebal", "event_study",
                   {"events_per_year": 60, "car_sd": 0.0032, "hold_days": 1, "icc": 0.4,
                    "concurrency": {"model": "clusters", "mean_size": 5}, "portfolio_autocorr": 0.0,
                    "mean_car": 0.0002583, "cost_per_event": 0.0002},
                   6.0, 5.67,
                   {"batch_k": 1, "stress_drag_sr": 0.61, "dev": {"kind": "amendment2", "null_center_sr": -0.27}, "val": VAL75},
                   "5 USD pairs x 72 month-end London 08:00-16:00 windows, equity-flow-signed.",
                   ["ASSUMPTION signed cross-pair correlation 0.4 (USD common factor, mostly same-signed flows)",
                    "per-event sd 32 bp backed out from the reported book Sharpe"],
                   {"dev_estimate": 0.09}, scenarios=[{"label": f"icc={r}", "params": {"icc": r}} for r in (0.2, 0.4, 0.6)]))
    R.append(_spec("retro_pead_2004_2014", "event_study",
                   {"events_per_year": 510, "car_sd": 0.07, "hold_days": 20, "icc": 0.02,
                    "concurrency": {"model": "seasonal_poisson", "season_fraction": 0.45, "n_seasons": 4},
                    "portfolio_autocorr": 0.05},
                   10.96, None,
                   {"batch_k": 1, "stress_drag_sr": None,
                    "dev": {"kind": "custom", "hac_t": 2.0, "both_halves_positive": True, "stress": False,
                            "name": "HAC t>=2 & both halves"}, "val": {"kind": "none"}},
                   "Production PEAD model replayed 2004-2014 (single stage: HAC t >= 2 and positive both halves).",
                   ["ASSUMPTION 20-day CAR sd 7%", "ASSUMPTION signed residual correlation of concurrent events 0.02",
                    "ASSUMPTION earnings seasons = 45% of trading days", "beats-all-events-control leg not modelled"],
                   scenarios=[{"label": f"icc={r}", "params": {"icc": r}} for r in (0.005, 0.02, 0.05, 0.1)]))
    R.append(_spec("retro_multiasset_17_sleeves", "sleeve_screen",
                   {"k": 17, "m_real": 5, "rho": 0.15, "incl_sharpe": 0.30, "periods_per_year": 252, "autocorr": 0.10,
                    "hold_t": 2.0},
                   10.0, 8.71, {},
                   "17 candidate sleeves, inclusion if dev Sharpe >= 0.30 (no null, no multiplicity), hold-out book HAC t >= 2.",
                   ["ASSUMPTION 5 of 17 sleeves real, pairwise sleeve correlation 0.15",
                    "alpha-vs-SPY HAC t leg treated as identical to the mean HAC t leg (low-beta book)"]))
    R.append(_spec("retro_ief_shy_duration", "timeseries",
                   {"periods_per_year": 252, "autocorr": {"model": "lrv", "D": 0.97}},
                   12.0, 11.7, {"batch_k": 3, "stress_drag_sr": 0.002, "dev": A2, "val": VAL75},
                   "structural_frontier A: IEF minus SHY, fully funded, daily active spread (k=3 batch).",
                   ["D = 0.97 from the family's own block-bootstrap null q95 0.468"], {"dev_estimate": 0.569}))
    R.append(_spec("retro_insider", "timeseries", {"periods_per_year": 252, "autocorr": 0.05},
                   10.0, 10.5,
                   {"batch_k": 4, "stress_drag_sr": 0.073,
                    "dev": {"kind": "custom", "sharpe_abs": 0.5, "stress": False, "name": "flat 0.5, no null"},
                    "val": VAL75},
                   "insider N1-N4, pre-amendment flat-0.5 dev gate (control leg not modelled).",
                   ["vol 11% / phi 0.05 / stress drag 0.8%/yr from null_lab2 sim_params"]))
    R.append(_spec("retro_etf_hybrids", "timeseries", {"periods_per_year": 252, "autocorr": 0.05},
                   12.0, 11.7,
                   {"batch_k": 5, "stress_drag_sr": 0.062,
                    "dev": {"kind": "custom", "sharpe_abs": 0.5, "stress": False, "name": "flat 0.5, no null"},
                    "val": VAL75},
                   "etf_hybrids E1-E5, pre-amendment flat-0.5 dev gate.",
                   ["vol 13% / phi 0.05 / stress drag 0.8%/yr from null_lab2 sim_params"]))
    return R


# ============================================================================================ prospective
def _ls_grid(ics, rhos, extra=None):
    sc = []
    for ic, r in itertools.product(ics, rhos):
        sc.append({"label": f"IC={ic} rho={r} tilt0.25", "params": {"ic": ic, "rho_resid": r, "rho_signal": 0.25,
                                                                   "correlation_mode": "factor_tilt", **(extra or {})}})
        sc.append({"label": f"IC={ic} rho={r} LITERAL", "params": {"ic": ic, "rho_resid": r, "rho_signal": 1.0,
                                                                  "correlation_mode": "equicorrelated_bets", **(extra or {})}})
    return sc


def prospective() -> list[dict]:
    P = []
    base_g = {"batch_k": 1, "stress_drag_sr": 0.1, "dev": A2, "val": VAL75}
    P.append(_spec("pro_cs500_daily_ls", "long_short",
                   {"n_assets": 500, "periods_per_year": 252, "ic": 0.02, "cs_dispersion": 0.02, "quantile": 0.1,
                    "rho_resid": 0.2, "rho_signal": 0.25, "signal_autocorr": 0.95, "cost_bps_one_way": 5,
                    "spread_autocorr": 0.0, "exkurt": 3.0},
                   5.0, 5.0, base_g, "500 stocks x 10y, daily decile long-short.",
                   ["ASSUMPTION daily residual cross-sectional sd 2%", "ASSUMPTION signal daily autocorr 0.95",
                    "ASSUMPTION 5 bp one-way", "tilt0.25 = signal's R^2 on the correlated factor 0.25; LITERAL = "
                    "brief's N/(1+(N-1) rho) on the held bets"],
                   scenarios=_ls_grid((0.01, 0.02, 0.03), (0.1, 0.2, 0.3))))
    P.append(_spec("pro_cs2000_weekly_ls", "long_short",
                   {"n_assets": 2000, "periods_per_year": 52, "ic": 0.02, "cs_dispersion": 0.045, "quantile": 0.1,
                    "rho_resid": 0.2, "rho_signal": 0.25, "signal_autocorr": 0.8, "cost_bps_one_way": 10,
                    "spread_autocorr": 0.0, "exkurt": 2.0},
                   7.5, 7.5, base_g, "2,000 stocks x 15y, weekly decile long-short.",
                   ["ASSUMPTION weekly residual cs sd 4.5%", "ASSUMPTION weekly signal autocorr 0.8", "ASSUMPTION 10 bp one-way"],
                   scenarios=_ls_grid((0.01, 0.02, 0.03), (0.1, 0.2, 0.3))))
    P.append(_spec("pro_events_8000", "event_study",
                   {"events_per_year": 8000, "car_sd": 0.06, "hold_days": 5, "icc": 0.02,
                    "concurrency": {"model": "seasonal_poisson", "season_fraction": 0.45, "n_seasons": 4},
                    "portfolio_autocorr": 0.0, "mean_car": 0.002, "cost_per_event": 0.001},
                   5.0, 5.0, base_g, "8,000 events/yr, 5-day hold, earnings-season clustering, 10y.",
                   ["ASSUMPTION 5-day CAR sd 6%", "ASSUMPTION 10 bp round-trip cost per event"],
                   scenarios=[{"label": f"icc={r} gross={m*1e4:.0f}bp", "params": {"icc": r, "mean_car": m}}
                              for r, m in itertools.product((0.005, 0.02, 0.05), (0.0015, 0.002, 0.003))]))
    P.append(_spec("pro_panel30_monthly", "panel",
                   {"n_markets": 30, "periods_per_year": 12, "rho": 0.45, "autocorr": 0.05, "skew": -0.3,
                    "exkurt": 2.0, "sharpe_per_market": 0.3},
                   10.0, 10.0, base_g, "30 futures markets x 20y monthly.",
                   ["ASSUMPTION per-market net Sharpe grid 0.2-0.4"],
                   scenarios=[{"label": f"rho={r} s_mkt={s}", "params": {"rho": r, "sharpe_per_market": s}}
                              for r, s in itertools.product((0.3, 0.45, 0.6), (0.2, 0.3, 0.4))]))
    P.append(_spec("pro_crypto200_daily", "panel",
                   {"n_markets": 200, "periods_per_year": 252, "rho": 0.6, "autocorr": 0.05, "skew": -0.5,
                    "exkurt": 8.0, "sharpe_per_market": 0.3},
                   2.5, 2.5, base_g, "200 crypto perps x 5y daily, directional per-asset strategy pooled.",
                   ["ASSUMPTION per-market Sharpe grid 0.2-0.4", "a market-neutral cross-sectional book escapes rho only "
                    "to the extent its signal is orthogonal to the common factor (see the long_short design)"],
                   scenarios=[{"label": f"rho={r} s_mkt={s}", "params": {"rho": r, "sharpe_per_market": s}}
                              for r, s in itertools.product((0.5, 0.6, 0.7), (0.2, 0.3, 0.4))]))
    cm = crash_moments(0.03, -4.0, 1.0)
    pm = one_factor_portfolio_moments(4, 0.4, cm["skew"], cm["exkurt"])
    P.append(_spec("pro_commodity4_monthly", "carry",
                   {"n_assets": 4, "periods_per_year": 12, "rho": 0.4, "autocorr": 0.05, "skew": round(pm["skew"], 4),
                    "exkurt": round(pm["exkurt"], 4), "sharpe_per_asset": 0.4},
                   17.5, 17.5, base_g, "4 commodities x 35y monthly carry, common crash factor.",
                   ["ASSUMPTION common crash: 3%/month chance of a -4 sd jump -> book skew/kurt via one-factor cumulants"],
                   scenarios=[{"label": f"s_asset={s}", "params": {"sharpe_per_asset": s}} for s in (0.3, 0.4, 0.5)]))
    return P


# ============================================================================================ cycle-4 candidates
def cycle4() -> list[dict]:
    C = []
    g = {"batch_k": 3, "stress_drag_sr": 0.15, "dev": A2, "val": VAL75, "pav": {"k_val": 1}}
    binance_sc = []
    for n, ic, r in itertools.product((50, 100, 150), (0.01, 0.02, 0.03), (0.2, 0.3, 0.4)):
        binance_sc.append({"label": f"N={n} IC={ic} rho={r}", "params": {"n_assets": n, "ic": ic, "rho_resid": r}})
    for ic, r in itertools.product((0.01, 0.02, 0.03), (0.2, 0.4)):
        binance_sc.append({"label": f"N=100 IC={ic} rho={r} LITERAL", "params": {"ic": ic, "rho_resid": r, "rho_signal": 1.0,
                                                                                 "correlation_mode": "equicorrelated_bets"}})
    C.append(_spec("c4a_binance_funding_ls_daily", "long_short",
                   {"n_assets": 100, "periods_per_year": 365, "ic": 0.02, "cs_dispersion": 0.04, "quantile": 0.2,
                    "rho_resid": 0.3, "rho_signal": 0.25, "signal_autocorr": 0.9, "cost_bps_one_way": 8,
                    "spread_autocorr": 0.05, "skew": -0.3, "exkurt": 10.0},
                   3.0, 3.67, g,
                   "Binance USD-M perps, funding-rate cross-sectional quintile long-short, daily (365 d/yr); "
                   "dev 2020-01..2022-12, validation 2023-01..2026-08.",
                   ["universe grows ~50 -> ~150: scenarios at N = 50/100/150 (dev-average ~70, val-average ~130)",
                    "ASSUMPTION daily residual cs sd 4%", "ASSUMPTION funding signal daily autocorr 0.9",
                    "ASSUMPTION 8 bp one-way (taker + slippage, alts)", "funding carry P&L itself not modelled",
                    "ASSUMPTION batch k = 3 (the three cycle-4 designs registered together)",
                    "rho_resid 0.2-0.4 after market-neutral; signal tilt R^2 0.25 on that residual factor"],
                   scenarios=binance_sc))
    C.append(_spec("c4a_binance_funding_ls_weekly", "long_short",
                   {"n_assets": 100, "periods_per_year": 52, "ic": 0.03, "cs_dispersion": 0.10, "quantile": 0.2,
                    "rho_resid": 0.3, "rho_signal": 0.25, "signal_autocorr": 0.6, "cost_bps_one_way": 8,
                    "spread_autocorr": 0.0, "skew": -0.3, "exkurt": 5.0},
                   3.0, 3.67, g, "Binance funding long-short, weekly rebalance.",
                   ["ASSUMPTION weekly residual cs sd 10%", "ASSUMPTION weekly signal autocorr 0.6"],
                   scenarios=[{"label": f"N={n} IC={ic} rho={r}", "params": {"n_assets": n, "ic": ic, "rho_resid": r}}
                              for n, ic, r in itertools.product((50, 150), (0.02, 0.03, 0.05), (0.2, 0.4))]))
    C.append(_spec("c4b_finra_svr_weekly", "long_short",
                   {"n_assets": 2000, "periods_per_year": 52, "ic": 0.015, "cs_dispersion": 0.05, "quantile": 0.1,
                    "rho_resid": 0.15, "rho_signal": 0.25, "signal_autocorr": 0.6, "cost_bps_one_way": 15,
                    "spread_autocorr": 0.0, "exkurt": 3.0},
                   3.4, 4.7, g,
                   "FINRA daily short-volume ratio, 1,500-3,000 US stocks, weekly decile long-short; "
                   "dev 2018-08..2021-12, validation 2022-01..2026-09.",
                   ["ASSUMPTION weekly residual cs sd 5%", "ASSUMPTION weekly signal autocorr 0.6",
                    "ASSUMPTION 15 bp one-way (small/mid caps)", "ASSUMPTION batch k = 3"],
                   scenarios=[{"label": f"N={n} IC={ic} rho={r}", "params": {"n_assets": n, "ic": ic, "rho_resid": r}}
                              for n, ic, r in itertools.product((1500, 3000), (0.01, 0.015, 0.02), (0.1, 0.2))]
                   + [{"label": f"N=2000 IC={ic} rho=0.15 sig_ac={a} cost={c}bp",
                       "params": {"ic": ic, "signal_autocorr": a, "cost_bps_one_way": c}}
                      for ic, a, c in itertools.product((0.01, 0.015, 0.02), (0.85, 0.95), (5, 10))]
                   + [{"label": f"N=2000 IC={ic} rho={r} LITERAL", "params": {"ic": ic, "rho_resid": r, "rho_signal": 1.0,
                                                                              "correlation_mode": "equicorrelated_bets"}}
                      for ic, r in itertools.product((0.01, 0.02), (0.1, 0.2))]))
    C.append(_spec("c4c_tsy_auction_surprise", "event_study",
                   {"events_per_year": 41, "car_sd": 0.010, "hold_days": 5, "icc": 0.3,
                    "concurrency": {"model": "clusters", "mean_size": 3, "cv": 0.4}, "portfolio_autocorr": 0.0,
                    "mean_car": 0.0015, "cost_per_event": 0.0002},
                   12.0, 12.5, g,
                   "Treasury note/bond auction result surprises, ~1,000 auctions 2002-2026, signed next-5-day TLT/IEF return.",
                   ["~41 auctions/yr; refunding / 2-5-7 weeks cluster ~3 auctions whose windows overlap on ONE asset",
                    "icc = correlation of SIGNED positions' returns within a cluster = sign agreement x 1 (same "
                    "instrument); ASSUMPTION 0.3, scenarios 0.1-0.6",
                    "ASSUMPTION dev/val split 2002-2013 / 2014-2026", "ASSUMPTION 2 bp round trip per event"],
                   scenarios=[{"label": f"sd={sd*100:.1f}% icc={r} gross={m*1e4:.0f}bp",
                               "params": {"car_sd": sd, "icc": r, "mean_car": m}}
                              for sd, r, m in itertools.product((0.007, 0.010, 0.012), (0.1, 0.3, 0.6), (0.001, 0.002, 0.004))]))
    return C


def all_specs() -> list[dict]:
    return retrospective() + prospective() + cycle4()


def write_examples() -> list[pathlib.Path]:
    EX.mkdir(exist_ok=True)
    out = []
    for s in all_specs():
        p = EX / f"{s['name']}.json"
        p.write_text(json.dumps(s, indent=1))
        out.append(p)
    return out
