"""A1 audit: effective sample sizes, breadth semantics, winner's curse, turnover, Sharpe-SE and two-stage checks.
Synthetic data and the committed example specs only (evaluated in memory; nothing is written to reports/power).
"""
from __future__ import annotations

import copy
import json
import math
import pathlib
import time

import numpy as np
from scipy import stats

from research.power import designs as DS
from research.power import gates as G
from research.power import plan_check as PC
from research.power import simulate as M
from research.power.core import Autocorr, SeriesModel, p_exceed
from research.power_audit_a1.common import OUT, binom_se, dump, rng, write_csv

_N = stats.norm
EX = pathlib.Path(__file__).resolve().parents[1] / "power" / "examples"


def load(name):
    return json.loads((EX / f"{name}.json").read_text())


def summ(rep):
    rows = {r["world"]: r for r in rep["power"]}
    return {"joint_current_0.7": rows["S=0.7"]["p_joint_current"], "joint_proposed_0.7": rows["S=0.7"]["p_joint_proposed"],
            "false_pass_current": rows["zero_net_null"]["p_joint_current"],
            "false_pass_proposed": rows["zero_net_null"]["p_joint_proposed"],
            "verdict_current": rep["verdict"], "verdict_proposed": rep["verdict_with_proposed_val_gate"],
            "n_eff_total": rep["observations"]["n_eff_total"], "raw_total": rep["observations"]["raw_total"],
            "val_proposed_threshold": (rep["gates"]["val_proposed"] or {}).get("threshold")}


# ------------------------------------------------------------------------------------------------ 1. breadth semantics
def breadth_semantics(N=2000, T=4000, style_share=0.10, sector_share=0.12, n_sectors=10, signal_r2=0.25):
    """Residuals = sector factors (categorical) + one style factor (Gaussian loadings) + idio. The signal is tilted to
    the style factor with R^2 signal_r2. True bet correlation = style_share * signal_r2. What does a practitioner
    get if he plugs (a) the factor variance share, (b) the measured average pairwise residual correlation?"""
    g = rng("breadth", N, T)
    sec = np.repeat(np.arange(n_sectors), N // n_sectors)
    beta = g.standard_normal(N)
    beta = (beta - beta.mean()) / beta.std()
    ics, pair = [], []
    idx = g.permutation(N)[:400]        # random subset of assets for the pairwise-correlation measurement
    idio_share = 1 - style_share - sector_share
    for i0 in range(0, T, 500):
        P = min(500, T - i0)
        fs = g.standard_normal((P, n_sectors))[:, sec]
        fz = g.standard_normal((P, 1)) * beta[None, :]
        u = math.sqrt(sector_share) * fs + math.sqrt(style_share) * fz + math.sqrt(idio_share) * g.standard_normal((P, N))
        S = g.standard_normal((P, 1))
        s = math.sqrt(signal_r2) * beta[None, :] * S + math.sqrt(1 - signal_r2) * g.standard_normal((P, N))
        uc = u - u.mean(1, keepdims=True)
        sc = s - s.mean(1, keepdims=True)
        ics.append((sc * uc).mean(1))
        # average pairwise correlation of market-neutral residuals over a random subset of pairs
        pair.append(uc[:, idx])
    ic = np.concatenate(ics)
    U = np.concatenate(pair)[:, :400]
    C = np.corrcoef(U.T)
    rho_pair = float((C.sum() - 400) / (400 * 399))
    sd_ic = float(ic.std())
    rho_bet_true_mc = (sd_ic ** 2 * N - 1) / (N - 1)
    neff = lambda rb: N / (1 + (N - 1) * rb)
    rows = [
        {"parametrisation": "truth (MC sd of covariance IC)", "rho_bet": rho_bet_true_mc, "n_eff": neff(rho_bet_true_mc)},
        {"parametrisation": "formula, rho_resid = style factor share, rho_signal = 0.25 (correct semantics)",
         "rho_bet": style_share * signal_r2, "n_eff": neff(style_share * signal_r2)},
        {"parametrisation": "formula, rho_resid = total factor share (sector+style), rho_signal = 0.25 (conservative)",
         "rho_bet": (style_share + sector_share) * signal_r2, "n_eff": neff((style_share + sector_share) * signal_r2)},
        {"parametrisation": "formula, rho_resid = MEASURED avg pairwise corr of market-neutral residuals, rho_signal=0.25",
         "rho_bet": max(rho_pair, 1e-6) * signal_r2, "n_eff": neff(max(rho_pair, 1e-6) * signal_r2)},
        {"parametrisation": "brief's literal N/(1+(N-1) rho_pair) (rho_signal = 1)", "rho_bet": max(rho_pair, 1e-6),
         "n_eff": neff(max(rho_pair, 1e-6))},
    ]
    for r in rows:
        r["sharpe_overstatement_vs_truth"] = math.sqrt(r["n_eff"] / rows[0]["n_eff"])
    return {"N": N, "measured_avg_pairwise_resid_corr": rho_pair, "sd_ic_mc": sd_ic, "rows": rows}


# ------------------------------------------------------------------------------------------------ 2. spec sensitivities
def spec_sensitivities():
    out = []
    # commodity_roll: D = 0.60 backed out of ONE realised bootstrap p (effective obs > raw obs)
    base = load("retro_commodity_roll")
    for D in (0.6, 0.8, 1.0, 1.2):
        sp = copy.deepcopy(base)
        sp["params"]["autocorr"] = {"model": "lrv", "D": D}
        out.append({"spec": "retro_commodity_roll", "change": f"D={D}", **summ(PC.run_spec(sp))})
    # cycle-4 batch k = 3 but PAV k_val = 1 in the spec; Amendment 3 P2 says 0.05/k_val with k_val = # taken together
    for nm in ("c4c_tsy_auction_surprise", "c4_tsy_auction_demand", "c4a_binance_funding_ls_daily", "c4b_finra_svr_weekly"):
        sp0 = load(nm)
        for kv, fl in ((1, None), (int(sp0["gates"]["batch_k"]), None), (int(sp0["gates"]["batch_k"]), 0.3)):
            sp = copy.deepcopy(sp0)
            sp["gates"]["pav"] = {"k_val": kv, **({"floor": fl} if fl else {})}
            sp.pop("scenarios", None)
            out.append({"spec": nm, "change": f"pav k_val={kv}" + (f" floor={fl}" if fl else ""), **summ(PC.run_spec(sp))})
    # event-study effective counts
    for nm in ("retro_pead_2004_2014", "pro_events_8000", "retro_fx_hedge_rebal", "c4c_tsy_auction_surprise"):
        sp = load(nm)
        d = DS.build(sp["design"], sp["params"], nm)
        out.append({"spec": nm, "change": "event deff", "m_w": d.implied["m_w"], "deff": d.implied["deff"],
                    "events_per_year": d.implied["events_per_year"], "n_eff_per_year": d.implied["n_eff_per_year"]})
    return out


def floor_binding():
    """Is the A3 P2 floor (S_hat >= 0.30) ever binding? plan_check's PAV omits it unless the spec sets it."""
    rows = []
    for f in sorted(EX.glob("*.json")):
        sp = json.loads(f.read_text())
        if sp["design"] == "sleeve_screen" or not sp["windows"].get("val_years"):
            continue
        d = DS.build(sp["design"], sp["params"], sp["name"])
        _, _, pg, _ = __import__("research.power.report", fromlist=["x"]).gates_from_spec(sp.get("gates", {}), d)
        legs = pg.legs(d.series, sp["windows"]["val_years"])
        rows.append({"spec": sp["name"], "val_years": sp["windows"]["val_years"], "pav_threshold": max(legs.values()),
                     "binding_leg": max(legs, key=legs.get), "floor_0.30_binds": max(legs.values()) < 0.30})
    return rows


# ------------------------------------------------------------------------------------------------ 3. winner's curse
def winners_curse(n_pass=1500):
    ser = SeriesModel(252, Autocorr("lrv", D=1.40))
    Yd = 11.99
    dg = G.amendment2_dev_gate(1, 0.20, -0.098)
    h = dg.threshold(ser, Yd)
    g = rng("wc")
    rows = []
    for S in (0.0, 0.3, 0.5, 0.7, 1.0):
        se = float(ser.se(S, Yd))
        x = S + se * g.standard_normal(400_000)
        x = x[x > h][:n_pass]
        est = np.array([G.truncation_corrected_estimate(float(v), ser, Yd, dg) for v in x])
        post = np.array([G.normal_prior_posterior(float(v), ser, Yd) for v in x])
        rows.append({"true_S": S, "n_passers": len(x), "P(cond_MU_est <= S | pass)": float(np.mean(est <= S)),
                     "median_cond_MU_est": float(np.median(est)), "mean_raw_S_hat_given_pass": float(x.mean()),
                     "mean_posterior_mean_given_pass": float(post.mean()), "sd_cond_MU_est": float(est.std())})
    # spike-and-slab prior sensitivity at the tsy dev estimate
    se0 = float(ser.se(0.664, Yd))
    spikes = []
    for pi0 in (0.0, 0.5, 0.8, 0.9):
        grid = np.linspace(-1.5, 2.5, 4001)
        slab = _N.pdf(grid / 0.5)
        lik = _N.pdf((0.664 - grid) / se0)
        num_slab = np.trapezoid(grid * slab * lik, grid) / np.trapezoid(slab, grid)
        den_slab = np.trapezoid(slab * lik, grid) / np.trapezoid(slab, grid)
        l0 = _N.pdf(0.664 / se0)
        pm = (1 - pi0) * num_slab / ((1 - pi0) * den_slab + pi0 * l0)
        spikes.append({"prior_mass_at_zero": pi0, "posterior_mean": float(pm)})
    return {"dev_threshold": h, "conditional_MU_calibration": rows, "spike_slab_tsy_0.664": spikes}


# ------------------------------------------------------------------------------------------------ 4. turnover
def turnover_check():
    rows = []
    for lab, N, ph, rs, c, q, disp, ic, qq in (("c4b finra-like", 1000, 0.6, 0.25, 15, 52, 0.05, 0.015, 0.1),
                                               ("cs500-like", 500, 0.95, 0.25, 5, 252, 0.02, 0.02, 0.1),
                                               ("no tilt control", 500, 0.8, 0.0, 10, 52, 0.04, 0.02, 0.1),
                                               ("strong tilt", 500, 0.8, 0.5, 10, 52, 0.04, 0.02, 0.1)):
        core = DS.long_short_core(N, ic, disp, qq, 0.15, rs, ph, c, q)
        mc = M.mc_long_short(n_assets=N, n_periods=150, ic=ic, cs_dispersion=disp, quantile=qq, rho_resid=0.15,
                             rho_signal=rs, signal_autocorr=ph, cost_bps_one_way=c, periods_per_year=q,
                             sharpe_threshold=0.0, n_paths=24, seed_salt=("a1turn", lab))
        tau_a, tau_m = core["turnover_one_way_per_leg"], mc["turnover_one_way_per_leg"]
        d_cost_sr = 4 * (tau_m - tau_a) * c / 1e4 / core["spread_sd"] * math.sqrt(q)
        rows.append({"case": lab, "tau_analytic": tau_a, "tau_mc": tau_m, "rel_err": tau_m / tau_a - 1,
                     "net_sharpe_analytic": core["sharpe_net"], "net_sharpe_overstatement_from_turnover": d_cost_sr})
    return rows


# ------------------------------------------------------------------------------------------------ 5. Sharpe SE
def kappa_checks(n_paths=40_000):
    """Lo/Mertens/Opdyke kappa with autocorrelation AND skew (the D13 = sqrt(D1 D2) approximation), short samples."""
    rows = []
    for lab, q, Y, phi, S, jump in (("monthly AR .3, 10y, S=1, crash innovations", 12, 10, 0.3, 1.0, True),
                                    ("monthly AR .3, 10y, S=1, gaussian", 12, 10, 0.3, 1.0, False),
                                    ("monthly AR .5, 5y, S=1, gaussian", 12, 5, 0.5, 1.0, False),
                                    ("weekly AR .1, 3.4y, S=1, crash innovations", 52, 3.4, 0.1, 1.0, True)):
        g = rng("kappa", lab)
        n = int(round(q * Y))
        burn = 200
        e = g.standard_normal((n_paths, n + burn))
        if jump:
            I = g.random((n_paths, n + burn)) < 0.03
            e = e + I * (-5.0)
            e = (e - (-5.0 * 0.03)) / math.sqrt(1 + 25 * 0.03 * 0.97)
        x = np.empty_like(e)
        x[:, 0] = e[:, 0]
        for t in range(1, n + burn):
            x[:, t] = phi * x[:, t - 1] + e[:, t]
        x = x[:, burn:] / math.sqrt(1 / (1 - phi * phi))
        big = x.ravel()
        sk, ek = float(stats.skew(big)), float(stats.kurtosis(big))
        r = x + S / math.sqrt(q)
        Sh = r.mean(1) / r.std(1, ddof=1) * math.sqrt(q)
        ser = SeriesModel(q, Autocorr("ar1", phi=phi), sk, ek)
        ser_lo = SeriesModel(q, Autocorr("ar1", phi=phi))
        rows.append({"case": lab, "marginal_skew": sk, "marginal_exkurt": ek,
                     "kappa_mc": float(Sh.std() * math.sqrt(Y)), "kappa_formula": float(math.sqrt(ser.kappa2(S))),
                     "kappa_formula_gaussian": float(math.sqrt(ser_lo.kappa2(S))),
                     "mean_S_hat": float(Sh.mean()), "bias_S_hat": float(Sh.mean() - S)})
    return rows


# ------------------------------------------------------------------------------------------------ 6. two-stage dependence
def two_stage_heterogeneity(n=400_000):
    """Joint power at a MEAN Sharpe of 0.7 when the true Sharpe differs across dev/val windows (regime / decay)."""
    ser = SeriesModel(252, Autocorr("lrv", D=1.40))
    dg = G.amendment2_dev_gate(1, 0.2)
    vg = G.power_aware_val_gate(1, 0.2)
    g = rng("het")
    rows = []
    fixed = G.joint_pass(0.7, ser, 12, dg, ser, 11.63, vg)["p_joint"]
    for tau in (0.0, 0.2, 0.4):
        for c in (0.0, 0.5, 1.0):
            z1 = g.standard_normal(n)
            z2 = c * z1 + math.sqrt(1 - c * c) * g.standard_normal(n)
            Sd, Sv = 0.7 + tau * z1, 0.7 + tau * z2
            pd = dg.pass_prob(Sd, ser, 12)
            pv = vg.pass_prob(Sv, ser, 11.63)
            rows.append({"tau_sd_of_true_S": tau, "corr_dev_val_true_S": c, "joint_mean": float(np.mean(pd * pv)),
                         "product_of_marginals": float(np.mean(pd) * np.mean(pv)), "fixed_S_formula": fixed})
    return rows


def run():
    t = time.time()
    out = {}
    out["breadth_semantics"] = breadth_semantics(); print("breadth", out["breadth_semantics"], round(time.time() - t, 1))
    out["spec_sensitivities"] = spec_sensitivities(); print("specs", round(time.time() - t, 1))
    out["floor_binding"] = floor_binding(); print("floor", round(time.time() - t, 1))
    out["winners_curse"] = winners_curse(); print("wc", out["winners_curse"], round(time.time() - t, 1))
    out["turnover"] = turnover_check(); print("turnover", out["turnover"], round(time.time() - t, 1))
    out["kappa"] = kappa_checks(); print("kappa", out["kappa"], round(time.time() - t, 1))
    out["two_stage_heterogeneity"] = two_stage_heterogeneity(); print("het", round(time.time() - t, 1))
    write_csv("spec_sensitivities.csv", out["spec_sensitivities"])
    write_csv("breadth_semantics.csv", out["breadth_semantics"]["rows"])
    write_csv("floor_binding.csv", out["floor_binding"])
    write_csv("winners_curse_check.csv", out["winners_curse"]["conditional_MU_calibration"])
    write_csv("turnover_check.csv", out["turnover"])
    write_csv("kappa_check.csv", out["kappa"])
    write_csv("two_stage_heterogeneity.csv", out["two_stage_heterogeneity"])
    dump("effective_n.json", out)
    return out


if __name__ == "__main__":
    run()
