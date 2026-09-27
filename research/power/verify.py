"""research.power.verify -- the Monte Carlo agreement suite: analytic vs simulated, one row per check.

Used by tests/test_power.py (fast=True) and by research.power.tables (fast=False -> reports/power/mc_agreement.csv).
Tolerance: |analytic - MC| <= max(0.03, 3 * MC SE) for probabilities; 5% relative for sds/means; 10% for turnover;
7.5% for kappa under rare crashes (the Opdyke
SE is asymptotic; with 120-210 months of jump data the simulated kappa runs 3-5% above it); 15% for sample skewness (small-sample downward bias of the sample skew with rare jumps);
(the bivariate-normal orthant ignores the signal's factor-tilt mixture; it understates turnover by ~5% at rho_s=0.5).
"""
from __future__ import annotations

import math

from research.power import designs as DS
from research.power import gates as G
from research.power import simulate as M
from research.power.core import Autocorr, SeriesModel, p_exceed, single_test_power


def _row(design, check, param, analytic, mc, se=None, kind="prob"):
    diff = mc - analytic
    if kind == "prob":
        tol = max(0.03, 3 * (se or 0.0))
        ok = abs(diff) <= tol
    else:
        tol = max({"turnover": 0.10, "moment": 0.15, "heavy_kappa": 0.075}.get(kind, 0.05) * abs(analytic), 3 * (se or 0.0))
        ok = abs(diff) <= tol
    return {"design": design.replace(",", ";"), "check": check, "param": param.replace(",", ";"), "analytic": round(analytic, 4), "mc": round(mc, 4),
            "mc_se": None if se is None else round(se, 4), "diff": round(diff, 4), "tolerance": round(tol, 4),
            "within_tolerance": bool(ok)}


def suite(fast: bool = False) -> list[dict]:
    f = 0.5 if fast else 1.0
    n = lambda k: max(400, int(k * f))
    R = []

    # 1-2. daily AR(1) + literal CBB, two-stage (tsy-like windows)
    ser = SeriesModel(252, Autocorr("ar1", phi=0.15), null_block=21)
    dg, vg, pg = G.amendment2_dev_gate(1, 0.2), G.current_val_gate(1, 0.2), G.power_aware_val_gate(1, 0.2)
    for S in ((0.0, 0.7) if fast else (0.0, 0.5, 0.7, 1.0)):
        for lab, v in (("current_0.75", vg), ("proposed_PAV", pg)):
            an = G.joint_pass(S, ser, 12, dg, ser, 11.63, v)
            mc = M.mc_two_stage(ser, S, 12, 11.63, dg, v, n_paths=n(2000), B=399,
                                seed_salt=("v2", lab))
            R.append(_row("timeseries daily AR(1) phi=.15, literal 21-day CBB", f"joint dev+val ({lab})", f"S={S}",
                          an["p_joint"], mc["p_joint"], mc["mc_se_joint"]))
    # kappa check (Lo 2002)
    s1 = SeriesModel(252, Autocorr("ar1", phi=0.15))
    mc = M.mc_gate(s1, 0.7, 12, G.Gate(sharpe_abs=0.0), n_paths=n(4000), seed_salt="kappa")
    R.append(_row("timeseries daily AR(1) phi=.15", "kappa = sd(S_hat) sqrt(Y) (Lo 2002)", "S=0.7",
                  math.sqrt(float(s1.kappa2(0.7))), mc["kappa_mc"], kind="sd"))
    # monthly overlap (H=3) with NW test
    s3 = SeriesModel(12, Autocorr("overlap", horizon=3))
    g3 = G.Gate(alpha=0.05)
    for S in (0.0, 0.6):
        an = float(g3.pass_prob(S, s3, 10))
        mc = M.mc_gate(s3, S, 10, g3, n_paths=n(4000), seed_salt="overlap", ideal_null=True)
        R.append(_row("monthly; 3-month overlapping holding (D=3)", "test power (true-D null)", f"S={S}", an,
                      mc["p_pass"], mc["mc_se"]))
        mc = M.mc_gate(s3, S, 10, g3, n_paths=n(4000), seed_salt="overlap_nw")
        r = _row("monthly; 3-month overlapping holding (D=3)", "INFO: literal NW(6 lags) t, n=120 (finite-sample "
                 "HAC bias; not a formula check)", f"S={S}", an, mc["p_pass"], mc["mc_se"])
        r["within_tolerance"] = None
        R.append(r)
    mc = M.mc_gate(s3, 0.0, 10, G.Gate(sharpe_abs=-9), n_paths=n(4000), seed_salt="overlap_k")
    R.append(_row("monthly, 3-month overlapping holding (D=3)", "kappa0 = sqrt(D)", "S=0", math.sqrt(3), mc["kappa_mc"], kind="sd"))

    # 3. events
    conc = {"model": "seasonal_poisson", "season_fraction": 0.45}
    for icc, S in ((0.02, 0.0), (0.02, 0.7), (0.1, 0.5)):
        d = DS.event_study(events_per_year=510, car_sd=0.07, hold_days=20, icc=icc, concurrency=conc, portfolio_autocorr=0.0)
        mc = M.mc_event_study(events_per_year=510, car_sd=0.07, hold_days=20, icc=icc, concurrency=conc,
                              mean_car=d.natural_from_sharpe(S), years=10, n_paths=n(4000), seed_salt="ev")
        R.append(_row("event study 510/yr, 20d hold, seasons 45%", "calendar-time test power", f"icc={icc} S={S}",
                      float(single_test_power(S, d.series, 10, 0.05)), mc["p_calendar"], mc["mc_se"]))
        R.append(_row("event study 510/yr, 20d hold, seasons 45%", "sd(mean CAR) = car_sd sqrt(deff/N)", f"icc={icc}",
                      0.07 * math.sqrt(d.deff_cross / 5100), mc["sd_mean_car"], kind="sd"))
        if S == 0.0:
            R.append(_row("event study 510/yr, 20d hold, seasons 45%", "naive independent-event t false-positive",
                          f"icc={icc}", _N_naive(d.deff_cross), mc["p_naive_event_t"], math.sqrt(0.25 / n(4000))))
    d = DS.event_study(events_per_year=60, car_sd=0.0032, hold_days=1, icc=0.4, concurrency={"model": "clusters", "mean_size": 5},
                       portfolio_autocorr=0.0)
    mc = M.mc_event_study(events_per_year=60, car_sd=0.0032, hold_days=1, icc=0.4, concurrency={"model": "clusters", "mean_size": 5},
                          mean_car=d.natural_from_sharpe(0.7), years=6, n_paths=n(4000), seed_salt="evcl")
    R.append(_row("event study 5-pair month-end clusters", "calendar-time test power", "icc=0.4 S=0.7",
                  float(single_test_power(0.7, d.series, 6, 0.05)), mc["p_calendar"], mc["mc_se"]))

    # 4. cross-sectional IC
    for ic, rr, rs, H, ph in ((0.0, 0.2, 0.5, 1, 0.0), (0.02, 0.2, 0.5, 1, 0.0), (0.03, 0.1, 1.0, 1, 0.0),
                              (0.0, 0.1, 0.25, 3, 0.9)):
        d = DS.cross_sectional_ic(n_assets=200, periods_per_year=12, ic=ic, rho_resid=rr, rho_signal=rs,
                                  ic_autocorr={"model": "overlap_persistent", "phi": ph, "horizon": H})
        mc = M.mc_cross_sectional_ic(n_assets=200, n_periods=120, ic=ic, rho_resid=rr, rho_signal=rs, horizon=H,
                                     signal_autocorr=ph, n_paths=n(2000))
        lab = f"IC={ic} rho_r={rr} rho_s={rs} H={H} phi_s={ph}"
        R.append(_row("cross-sectional IC, N=200, T=120", "sd(IC_t) = sqrt((1+(N-1)rho_bet)/N)", lab,
                      mc["sd_ic_analytic"], mc["sd_ic_mc"], kind="sd"))
        R.append(_row("cross-sectional IC, N=200, T=120", "sd(mean IC) incl. overlap D", lab,
                      mc["sd_mean_ic_analytic"], mc["sd_mean_ic_mc"], kind="sd"))
        R.append(_row("cross-sectional IC, N=200, T=120", "IC t-test power", lab,
                      float(single_test_power(d.implied["sharpe_gross_linear_book"], d.series, 10, 0.05)),
                      mc["p_reject"], mc["mc_se"]))

    # 5. long-short
    for (N, ic, rr, rs, ph, c) in ((200, 0.03, 0.1, 0.25, 0.8, 10), (200, 0.02, 0.2, 0.5, 0.9, 5)):
        d = DS.long_short(n_assets=N, periods_per_year=52, ic=ic, cs_dispersion=0.04, quantile=0.1, rho_resid=rr,
                          rho_signal=rs, signal_autocorr=ph, cost_bps_one_way=c, spread_autocorr=0.0)
        I = d.implied
        mc = M.mc_long_short(n_assets=N, n_periods=260, ic=ic, cs_dispersion=0.04, quantile=0.1, rho_resid=rr,
                             rho_signal=rs, signal_autocorr=ph, cost_bps_one_way=c, periods_per_year=52,
                             sharpe_threshold=0.5, n_paths=n(800))
        lab = f"N={N} IC={ic} rho_r={rr} rho_s={rs} sig_ac={ph} {c}bp"
        R.append(_row("decile long-short, weekly, 5y", "spread sd", lab, I["spread_sd"], mc["spread_sd"], kind="sd"))
        R.append(_row("decile long-short, weekly, 5y", "gross mean spread", lab, I["spread_mean_gross"],
                      mc["spread_mean_gross"], mc["spread_mean_se"], kind="mean"))
        R.append(_row("decile long-short, weekly, 5y", "one-way turnover per leg", lab, I["turnover_one_way_per_leg"],
                      mc["turnover_one_way_per_leg"], kind="turnover"))
        R.append(_row("decile long-short, weekly, 5y", "P(net S_hat >= 0.5)", lab,
                      float(p_exceed(0.5, I["sharpe_net"], d.series.se(I["sharpe_net"], 5))), mc["p_pass"], mc["mc_se"]))

    # 6. carry with common crashes
    g = G.Gate(sharpe_c=1.8, alpha=0.05)
    for (K, rho, p, m, sd, S, Y) in ((4, 0.4, 0.05, -4.0, 1.0, 0.7, 17.5), (4, 0.4, 0.05, -4.0, 1.0, 0.0, 17.5),
                                     (8, 0.3, 0.03, -6.0, 1.0, 0.5, 10)):
        cm = DS.crash_moments(p, m, sd)
        pm = DS.one_factor_portfolio_moments(K, rho, cm["skew"], cm["exkurt"])
        d = DS.carry(n_assets=K, periods_per_year=12, rho=rho, autocorr=0.0, skew=pm["skew"], exkurt=pm["exkurt"])
        mc = M.mc_carry(n_assets=K, rho=rho, p_crash=p, jump_mean=m, jump_sd=sd, S=S, periods_per_year=12, years=Y,
                        gate=g, ser=d.series, n_paths=n(6000))
        lab = f"K={K} rho={rho} crash p={p} jump={m}sd S={S}"
        R.append(_row("carry monthly, common crash factor", "dev-gate power (Opdyke SE)", lab,
                      float(g.pass_prob(S, d.series, Y)), mc["p_pass"], mc["mc_se"]))
        if S > 0:
            R.append(_row("carry monthly, common crash factor", "kappa(S) (Mertens/Opdyke)", lab,
                          math.sqrt(float(d.series.kappa2(S))), mc["kappa_mc"], kind="heavy_kappa"))
            R.append(_row("carry monthly, common crash factor", "book skew (one-factor cumulants)", lab,
                          pm["skew"], mc["skew_mc"], kind="moment"))

    # 7. panel
    for (K, rho, bl, phi, S) in ((30, 0.3, None, 0.05, 0.7),
                                 (30, None, {"sizes": [10, 10, 10], "rho_within": 0.6, "rho_between": 0.3}, 0.05, 0.5),
                                 (30, 0.6, None, 0.1, 0.0)):
        d = DS.panel(n_markets=K, periods_per_year=12, rho=rho, blocks=bl, autocorr=phi)
        mc = M.mc_panel(n_markets=K, rho=rho, blocks=bl, phi=phi, S=S, periods_per_year=12, years=10, n_paths=n(3000))
        lab = f"K={K} {'blocks' if bl else 'rho=' + str(rho)} phi={phi} S={S}"
        R.append(_row("panel 30 markets monthly 10y", "EW-book test power", lab,
                      float(single_test_power(S, d.series, 10, 0.05)), mc["p_reject"], mc["mc_se"]))
        if S == 0.0:
            R.append(_row("panel 30 markets monthly 10y", "naive pooled K*T t false-positive", lab,
                          d.naive["naive_false_positive_at_nominal_0.05"], mc["p_naive_pooled"], mc["mc_se"]))

    # sleeve screen
    s52 = SeriesModel(52, Autocorr("ar1", phi=0.1))
    for (s, m) in ((0.0, 0), (0.4, 5), (0.6, 5)):
        an = G.sleeve_screen_power(s, k=17, m_real=m, rho=0.15, incl_sharpe=0.3, dev_years=10, hold_years=8.71,
                                   sleeve_series=s52)
        mc = M.mc_sleeve_screen(s_sleeve=s, k=17, m_real=m, rho=0.15, incl_sharpe=0.3, dev_years=10, hold_years=8.71,
                                phi=0.1, periods_per_year=52, n_paths=n(3000))
        R.append(_row("17-sleeve screen (weekly), hold-out HAC t>=2", "joint pass", f"s_sleeve={s} m_real={m}",
                      an["p_joint"], mc["p_joint"], mc["mc_se"]))
    return R


def _N_naive(deff):
    from scipy.stats import norm
    return float(norm.sf(norm.isf(0.05) / math.sqrt(deff)))
