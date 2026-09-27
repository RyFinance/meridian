"""Selection burden, forking-path penalty, winner's curse, spike-and-slab posterior, validation power.
Uses DEV-window numbers only. PYTHONPATH=. .venv/bin/python -m research.audit_funding_stat.burden"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import optimize, stats

from research.audit_funding_stat.lockpanel import OUT

ANN, ALPHA = 365, 0.025
N = stats.norm


def main():
    res = {}
    corr = json.loads((OUT.parent / "crypto_funding_xs" / "corrected" / "dev_results.json").read_text())
    asrun = json.loads((OUT.parent / "crypto_funding_xs" / "dev_results.json").read_text())
    cal = json.loads((OUT / "null_calibration.json").read_text())
    an = json.loads((OUT / "analysis.json").read_text())
    a = pd.read_csv(OUT.parent / "crypto_funding_xs" / "dev_daily.csv", index_col=0, parse_dates=True)["base"]
    c = pd.read_csv(OUT.parent / "crypto_funding_xs" / "corrected" / "dev_daily.csv", index_col=0, parse_dates=True)["base"]
    ov = a.index.intersection(c.index)
    rho = float(((a[ov] - a.mean()) * (c[ov] - c.mean())).sum() /
                np.sqrt(((a - a.mean()) ** 2).sum() * ((c - c.mean()) ** 2).sum()))
    p_obs, p1_obs = corr["bootstrap_p"], asrun["bootstrap_p"]
    res["rho_Z_asrun_vs_corrected"] = rho
    z1o, z2o = N.isf(p1_obs), N.isf(p_obs)
    res["z_asrun"], res["z_corrected"] = z1o, z2o
    res["P_H0_Z2_ge_obs_given_Z1_obs"] = float(N.sf((z2o - rho * z1o) / np.sqrt(1 - rho ** 2)))

    # ---- forking-path model (H0: both z ~ N(0,1), corr rho)
    rng = np.random.default_rng(11)
    M = 4_000_000
    z1 = rng.standard_normal(M); z2 = rho * z1 + np.sqrt(1 - rho ** 2) * rng.standard_normal(M)
    p1, p2 = N.sf(z1), N.sf(z2)
    fork = {}
    for lab, nm_hi, q_fail, q_pass in (("no_fork (corrected run only, committed in advance)", None, 0, 0),
                                       ("near-miss search p1 in [.025,.10], q_fail=1, q_pass=0", 0.10, 1.0, 0.0),
                                       ("near-miss search p1 in [.025,.20], q_fail=1, q_pass=0", 0.20, 1.0, 0.0),
                                       ("any-fail search, q_fail=1, q_pass=0", 1.0, 1.0, 0.0),
                                       ("near-miss [.025,.10], q_fail=1, q_pass=0.5", 0.10, 1.0, 0.5),
                                       ("near-miss [.025,.10], q_fail=0.5, q_pass=0", 0.10, 0.5, 0.0)):
        if nm_hi is None:
            rep = p2
            size = np.mean(p2 < ALPHA); pev = np.mean(p2 <= p_obs)
        else:
            u = rng.random(M)
            nm = (p1 >= ALPHA) & (p1 <= nm_hi) & (u < q_fail)
            recheck_pass = (p1 < ALPHA) & (u < q_pass)
            rep = np.where(nm | recheck_pass, p2, p1)
            size = np.mean(rep < ALPHA); pev = np.mean(rep <= p_obs)
        fork[lab] = {"size_at_nominal_0.025": float(size), "inflation": float(size / ALPHA),
                     "p_equiv_for_observed_0.0026": float(pev)}
    res["forking_paths"] = fork
    p_fork = fork["near-miss search p1 in [.025,.10], q_fail=1, q_pass=0"]["p_equiv_for_observed_0.0026"]
    # calibrated (dependence-robust) p: stationary-bootstrap-63 null; forking factor applied multiplicatively
    p_cal = cal["calibrated_p_for_observed_0.0026"]["stationary_boot_empirical_mean_block_63"]
    p_cal_fork = min(1.0, p_cal * p_fork / p_obs)

    def adj(p):
        return {"raw": p, "batch_k2_bonf": min(1, 2 * p), "crypto_family_3_bonf": min(1, 3 * p),
                "sidak_Meff25": 1 - (1 - p) ** 25, "sidak_Meff19": 1 - (1 - p) ** 19,
                "sidak_Meff34": 1 - (1 - p) ** 34, "bonf_project_240": min(1, 240 * p)}
    res["burden_adjusted"] = {"frozen_p_0.0026": adj(p_obs), "fork_adjusted": adj(p_fork),
                              "calibrated_stationary63": adj(p_cal), "calibrated_and_fork": adj(p_cal_fork)}

    # ---- winner's curse (truncated-normal conditional median-unbiased)
    S_hat = corr["books"]["base"]["sharpe"]
    se_boot = S_hat / z2o
    out = {}
    for lab, se in (("SE_bootstrap_implied", se_boot), ("SE_HAC21", 0.6434 * np.sqrt(an["distribution"]["kappa2_NW21"]))):
        cthr = max(corr["gate"], N.isf(ALPHA) * se)
        def q(mu, target):
            return stats.truncnorm((cthr - mu) / se, np.inf, loc=mu, scale=se).cdf(S_hat) - target
        # conditional CDF at S_hat is decreasing in mu
        mue = optimize.brentq(lambda m: q(m, 0.5), -3, 8)
        lo = optimize.brentq(lambda m: q(m, 0.975), -4, 8)
        hi = optimize.brentq(lambda m: q(m, 0.025), -3, 12)
        out[lab] = {"se": float(se), "selection_threshold_sharpe": float(cthr), "cmu": float(mue),
                    "ci95": [float(lo), float(hi)]}
    # path-conditional: condition on the observed as-run z1 and the selection Z2>1.96 (same drift/√T scaling)
    se = se_boot; s1 = asrun["books"]["base"]["sharpe"] / z1o
    def cdf_path(mu, target):
        m2 = mu / se; m1 = mu / s1
        mc = m2 + rho * (z1o - m1); sc = np.sqrt(1 - rho ** 2)
        return stats.truncnorm((N.isf(ALPHA) - mc) / sc, np.inf, loc=mc, scale=sc).cdf(z2o) - target
    out["path_conditional_on_asrun_z1"] = {"cmu": float(optimize.brentq(lambda m: cdf_path(m, 0.5), -3, 8)),
                                          "ci95": [float(optimize.brentq(lambda m: cdf_path(m, 0.975), -4, 8)),
                                                   float(optimize.brentq(lambda m: cdf_path(m, 0.025), -3, 12))]}
    res["winners_curse"] = out

    # ---- spike and slab, pi0 = 0.8
    grid = np.linspace(0, 6, 6001)
    ss = {}
    slabs = {"halfnormal_sd1": stats.halfnorm(scale=1.0).pdf, "halfnormal_sd0.5": stats.halfnorm(scale=0.5).pdf,
             "normal_0.7_0.35_trunc": lambda s: stats.norm(0.7, 0.35).pdf(s) / stats.norm(0.7, 0.35).sf(0)}
    for sl, f in slabs.items():
        for selab, se_ in (("se_boot", se_boot), ("se_boot_x1.25_calibration", se_boot * 1.25)):
            lik0 = N.pdf(S_hat, 0, se_)
            dens = f(grid); dens /= np.trapezoid(dens, grid)
            lik = N.pdf(S_hat, grid, se_)
            m1 = np.trapezoid(dens * lik, grid)
            post0 = 0.8 * lik0 / (0.8 * lik0 + 0.2 * m1)
            pd_ = dens * lik / m1
            cdf = np.cumsum(pd_) * (grid[1] - grid[0])
            ss[f"{sl}|{selab}"] = {"P_null_posterior": float(post0), "BF10": float(m1 / lik0),
                                   "slab_post_median": float(grid[np.searchsorted(cdf, 0.5)]),
                                   "post_mean_incl_spike": float((1 - post0) * np.trapezoid(grid * pd_, grid)),
                                   "P_S_gt_0.3": float((1 - post0) * (1 - np.interp(0.3, grid, cdf))),
                                   "_post_grid": None}
            ss[f"{sl}|{selab}"]["_draws"] = (post0, grid, pd_)
    # ---- validation power (2023-01-01..2026-08-31 = 1339 days, universe full)
    T = 1339 / ANN
    ser = pd.read_csv(OUT / "series_dev.csv", index_col=0, parse_dates=True)["base"]
    d = pd.read_csv(OUT.parent / "crypto_funding_xs" / "corrected" / "dev_daily.csv", index_col=0, parse_dates=True)
    full = d.loc["2021-07-01":]
    drag_ann = float((d["base"] - d["stress"]).mean() * ANN)
    drag_full = float((full["base"] - full["stress"]).mean() * ANN)
    vol_full = float(full["base"].std() * np.sqrt(ANN))
    drag_sr = drag_full / vol_full
    res["validation_setup"] = {"T_years": T, "stress_drag_ann_dev": drag_ann, "stress_drag_ann_2021H2_2022": drag_full,
                               "base_vol_ann_2021H2_2022": vol_full, "base_vol_ann_dev": float(d["base"].std() * np.sqrt(ANN)),
                               "stress_leg_threshold_in_base_sharpe": drag_sr,
                               "note": "pass iff base Sharpe_hat >= max(1.645*SE [p<.05], 0.30, stress drag in Sharpe units)"}

    def ppass(S, k2):
        se_v = np.sqrt(k2 * (1 + S ** 2 / (2 * ANN)) / T)
        thr = max(N.isf(0.05) * se_v, 0.30, drag_sr)
        return N.sf((thr - S) / se_v), thr, se_v
    pw = {}
    for k2 in (1.0, 1.57, 1.84):
        row = {"threshold_sharpe": ppass(0, k2)[1], "se_null": ppass(0, k2)[2]}
        for S in (0.0, 0.12, 0.27, 0.3, 0.5, 0.7, 1.0, 1.5, 2.44):
            row[f"S={S}"] = float(ppass(S, k2)[0])
        for lab in ("SE_bootstrap_implied", "SE_HAC21"):
            row[f"S=CMU({lab})={out[lab]['cmu']:.2f}"] = float(ppass(max(out[lab]["cmu"], 0), k2)[0])
        row[f"S=path_CMU={out['path_conditional_on_asrun_z1']['cmu']:.2f}"] = float(ppass(max(out['path_conditional_on_asrun_z1']['cmu'], 0), k2)[0])
        # predictive power under spike-slab posteriors
        for key, v in ss.items():
            post0, grid, pd_ = v["_draws"]
            pp = np.array([ppass(s, k2)[0] for s in grid[::20]])
            w = pd_[::20] / pd_[::20].sum()
            row[f"predictive|{key}"] = float(post0 * ppass(0, k2)[0] + (1 - post0) * (w * pp).sum())
            if k2 == 1.57:
                # posterior after a validation PASS / FAIL
                ppos = (1 - post0) * (w * pp).sum(); p0 = post0 * ppass(0, k2)[0]
                v["P_null_after_val_PASS"] = float(p0 / (p0 + ppos))
                v["P_null_after_val_FAIL"] = float(post0 * (1 - ppass(0, k2)[0]) / (post0 * (1 - ppass(0, k2)[0]) + (1 - post0) * (w * (1 - pp)).sum()))
        pw[f"kappa2={k2}"] = row
    for v in ss.values():
        v.pop("_draws"); v.pop("_post_grid")
    res["spike_slab_pi0_0.8"] = ss
    res["validation_power"] = pw
    (OUT / "burden.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
