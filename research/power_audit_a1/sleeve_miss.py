"""A1 audit: the one Monte Carlo miss (17-sleeve screen, analytic 0.4745 vs MC 0.507).

Decomposition
-------------
Let pi(R, Z) be the probability that R real and Z null sleeves are included at the dev screen and g(R, Z) the
probability that the hold-out book of that composition passes (HAC t >= 2). Then

    P_joint = sum_{R,Z} pi(R, Z) g(R, Z)

The cycle-4 analytic uses pi_bin(R, Z) = Binom(R; m, p1) x Binom(Z; k - m, p0) (independent inclusion) and
g_an(R, Z) = P(N(S_book, se^2) >= h). With an audit MC that records (R, Z, pass) per path:

    MC - analytic = sum (pi_MC - pi_bin) g_an          [composition error]
                  + sum pi_MC (g_MC - g_an)            [hold-stage error]

and the composition error splits into
    sum (pi_1F - pi_bin) g_an                          [correlated inclusion: exact one-factor integral, no MC]
    sum (pi_MC - pi_1F) g_an                           [residual: marginal inclusion rates / non-normal S_hat]

Everything is synthetic.
"""
from __future__ import annotations

import math
import time

import numpy as np
from numpy.polynomial.hermite_e import hermegauss
from scipy import stats

from research.power import gates as G
from research.power import simulate as M
from research.power.core import Autocorr, SeriesModel, p_exceed
from research.power_audit_a1.common import ar1_paths, binom_se, dump, rng, write_csv

_N = stats.norm
GH_X, GH_W = hermegauss(96)
GH_W = GH_W / GH_W.sum()

BASE = dict(k=17, rho=0.15, incl_sharpe=0.3, dev_years=10.0, hold_years=8.71, phi=0.1, q=52, hold_t=2.0)


# ------------------------------------------------------------------------------------------------ analytic pieces
def g_an(r, z, s, ser, hold_years, rho, hold_t):
    """Hold-stage pass probability of the book with r real + z null sleeves (cycle-4 formula, re-derived)."""
    n = r + z
    if n == 0:
        return 0.0
    h = hold_t * float(ser.se_null(hold_years))
    Sb = r * s / math.sqrt(n * (1 + (n - 1) * rho))
    return float(p_exceed(h, Sb, ser.se(Sb, hold_years)))


def pi_binomial(s, m, k, p_incl_real, p_incl_null):
    pr = stats.binom.pmf(np.arange(m + 1), m, p_incl_real)
    pz = stats.binom.pmf(np.arange(k - m + 1), k - m, p_incl_null)
    return np.outer(pr, pz)


def pi_one_factor(s, m, k, rho, c, se1, se0, rho_est=None):
    """Exact (normal-theory) joint inclusion law when the k Sharpe estimates share a common factor:
    S_hat_i = s_i + se_i (sqrt(r) G + sqrt(1 - r) E_i), r = corr of the estimates (= rho for the means).
    Integrates Binom x Binom over G by Gauss-Hermite."""
    r_ = rho if rho_est is None else rho_est
    out = np.zeros((m + 1, k - m + 1))
    for gx, gw in zip(GH_X, GH_W):
        p1 = _N.sf((c - s - se1 * math.sqrt(r_) * gx) / (se1 * math.sqrt(1 - r_)))
        p0 = _N.sf((c - se0 * math.sqrt(r_) * gx) / (se0 * math.sqrt(1 - r_)))
        out += gw * np.outer(stats.binom.pmf(np.arange(m + 1), m, p1),
                             stats.binom.pmf(np.arange(k - m + 1), k - m, p0))
    return out


def analytic_tables(s, m, P):
    ser = SeriesModel(P["q"], Autocorr("ar1", phi=P["phi"]))
    se1 = float(ser.se(s, P["dev_years"]))
    se0 = float(ser.se(0.0, P["dev_years"]))
    p1 = float(_N.sf((P["incl_sharpe"] - s) / se1))
    p0 = float(_N.sf(P["incl_sharpe"] / se0))
    k = P["k"]
    g = np.array([[g_an(r, z, s, ser, P["hold_years"], P["rho"], P["hold_t"]) for z in range(k - m + 1)]
                  for r in range(m + 1)])
    pib = pi_binomial(s, m, k, p1, p0)
    pif = pi_one_factor(s, m, k, P["rho"], P["incl_sharpe"], se1, se0)
    return dict(ser=ser, se1=se1, se0=se0, p1=p1, p0=p0, g=g, pi_bin=pib, pi_1f=pif,
                joint_bin=float(np.sum(pib * g)), joint_1f=float(np.sum(pif * g)))


# ------------------------------------------------------------------------------------------------ audit MC
def audit_mc(s, m, P, n_paths, salt, hold_stat="true_D_t", chunk=800):
    """Independent re-implementation (explicit AR recursion, own seeds). Records R, Z and pass per path.
    hold_stat: 'true_D_t' = mean / (sd * sqrt(D/n)) as in the cycle-4 MC; 'nw_t' = literal Newey-West t
    (plug-in lags) -- a practitioner statistic, NOT the analytic's assumption."""
    g = rng("sleeve", s, m, P["rho"], P["phi"], salt, hold_stat)
    k, q = P["k"], P["q"]
    nd, nh = int(round(q * P["dev_years"])), int(round(q * P["hold_years"]))
    n = nd + nh
    phi, rho = P["phi"], P["rho"]
    D = (1 + phi) / (1 - phi)
    mu = np.zeros(k)
    mu[:m] = s / math.sqrt(q)
    Rs, Zs, ok_all, Sh_all = [], [], [], []
    L = int(math.floor(4 * (nh / 100) ** (2 / 9)))
    for i0 in range(0, n_paths, chunk):
        Pn = min(chunk, n_paths - i0)
        common = ar1_paths(g, (Pn, n, 1), phi)
        idio = ar1_paths(g, (Pn, n, k), phi)
        x = math.sqrt(rho) * common + math.sqrt(1 - rho) * idio + mu
        dev, hold = x[:, :nd], x[:, nd:]
        Sh = dev.mean(axis=1) / dev.std(axis=1, ddof=1) * math.sqrt(q)
        inc = Sh >= P["incl_sharpe"]
        cnt = inc.sum(axis=1)
        book = (hold * inc[:, None, :]).sum(axis=2) / np.maximum(cnt, 1)[:, None]
        mb = book.mean(axis=1)
        if hold_stat == "true_D_t":
            t = mb / (book.std(axis=1, ddof=1) * math.sqrt(D / nh))
        else:
            t = mb / np.sqrt(M.nw_lrv(book, L) / nh)
        ok = (cnt > 0) & (np.nan_to_num(t, nan=-9) >= P["hold_t"])
        Rs.append(inc[:, :m].sum(axis=1)); Zs.append(inc[:, m:].sum(axis=1)); ok_all.append(ok)
        Sh_all.append(Sh)
    R, Z, ok = np.concatenate(Rs), np.concatenate(Zs), np.concatenate(ok_all)
    Sh = np.concatenate(Sh_all)
    return R, Z, ok, Sh


def normal_theory_mc(s, m, P, n_paths, salt):
    """Draw the dev Sharpe vector from the exact one-factor normal model and the hold book Sharpe from N(Sb, se^2):
    checks the Gauss-Hermite integral (no estimator, no autocorrelation code involved)."""
    g = rng("sleeve_nt", s, m, salt)
    A = analytic_tables(s, m, P)
    ser, k, rho = A["ser"], P["k"], P["rho"]
    se = np.r_[np.full(m, A["se1"]), np.full(k - m, A["se0"])]
    mu = np.r_[np.full(m, s), np.zeros(k - m)]
    G_ = g.standard_normal((n_paths, 1))
    E = g.standard_normal((n_paths, k))
    Sh = mu + se * (math.sqrt(rho) * G_ + math.sqrt(1 - rho) * E)
    inc = Sh >= P["incl_sharpe"]
    R, Z = inc[:, :m].sum(1), inc[:, m:].sum(1)
    gtab = A["g"]
    u = g.random(n_paths)
    ok = u < gtab[R, Z]
    return float(ok.mean())


def decompose(s, m, P, n_paths, salt="main"):
    A = analytic_tables(s, m, P)
    t0 = time.time()
    R, Z, ok, Sh = audit_mc(s, m, P, n_paths, salt)
    k = P["k"]
    piMC = np.zeros((m + 1, k - m + 1))
    gMC = np.full((m + 1, k - m + 1), np.nan)
    np.add.at(piMC, (R, Z), 1.0)
    for r in range(m + 1):
        for z in range(k - m + 1):
            sel = (R == r) & (Z == z)
            if sel.any():
                gMC[r, z] = ok[sel].mean()
    piMC /= len(R)
    g = A["g"]
    p_mc = float(ok.mean())
    comp_total = float(np.sum((piMC - A["pi_bin"]) * g))
    corr_incl = float(np.sum((A["pi_1f"] - A["pi_bin"]) * g))
    comp_resid = float(np.sum((piMC - A["pi_1f"]) * g))
    hold_err = float(np.nansum(piMC * (np.nan_to_num(gMC) - g)))
    # standard error of the MC hold-stage error term (binomial in each cell)
    var_h = np.nansum(piMC ** 2 * np.nan_to_num(gMC * (1 - gMC)) / np.maximum(piMC * len(R), 1))
    # marginal inclusion rates
    p1_mc = float(R.mean() / m) if m else float("nan")
    p0_mc = float(Z.mean() / (k - m))
    # correlation of inclusion indicators among nulls / variance inflation of Z
    varZ_mc = float(Z.var())
    varZ_bin = (k - m) * A["p0"] * (1 - A["p0"])
    # kappa of the dev Sharpe estimates vs analytic
    se_null_mc = float(Sh[:, m:].std()) if m < k else float("nan")
    se_real_mc = float(Sh[:, :m].std()) if m else float("nan")
    corr_sh = float(np.corrcoef(Sh[:, -1], Sh[:, -2])[0, 1])
    return {
        "s_sleeve": s, "m_real": m, "n_paths": n_paths, "seconds": round(time.time() - t0, 1),
        "analytic_binomial_cycle4": A["joint_bin"], "analytic_one_factor": A["joint_1f"],
        "mc_audit": p_mc, "mc_se": binom_se(p_mc, n_paths),
        "total_gap_mc_minus_cycle4": p_mc - A["joint_bin"],
        "part_correlated_inclusion_exact": corr_incl,
        "part_composition_residual_mc": comp_resid,
        "part_hold_stage_mc": hold_err, "part_hold_stage_se": float(math.sqrt(var_h)),
        "check_sum": corr_incl + comp_resid + hold_err,
        "p_incl_real_analytic": A["p1"], "p_incl_real_mc": p1_mc,
        "p_incl_null_analytic": A["p0"], "p_incl_null_mc": p0_mc,
        "var_Z_binomial": varZ_bin, "var_Z_mc": varZ_mc, "var_Z_one_factor": float(
            np.sum(A["pi_1f"].sum(0) * np.arange(k - m + 1) ** 2) - np.sum(A["pi_1f"].sum(0) * np.arange(k - m + 1)) ** 2),
        "sd_Shat_null_analytic": A["se0"], "sd_Shat_null_mc": se_null_mc,
        "sd_Shat_real_analytic": A["se1"], "sd_Shat_real_mc": se_real_mc,
        "corr_Shat_two_nulls_mc": corr_sh,
    }


def run(n_main=100_000, n_var=50_000):
    rows, out = [], {}
    P = dict(BASE)
    t = time.time()
    # (1) the cycle-4 simulator itself, re-seeded, high precision (rules out MC noise / seed luck)
    rep = []
    for s, m in ((0.6, 5), (0.4, 5), (0.0, 0)):
        vals = []
        for salt in ("a1_rep1", "a1_rep2"):
            r = M.mc_sleeve_screen(s_sleeve=s, k=17, m_real=m, rho=0.15, incl_sharpe=0.3, dev_years=10,
                                   hold_years=8.71, phi=0.1, periods_per_year=52, n_paths=n_main // 2, seed_salt=salt)
            vals.append(r["p_joint"])
        p = float(np.mean(vals))
        an = G.sleeve_screen_power(s, k=17, m_real=m, rho=0.15, incl_sharpe=0.3, dev_years=10, hold_years=8.71,
                                   sleeve_series=SeriesModel(52, Autocorr("ar1", phi=0.1)))["p_joint"]
        rep.append({"s_sleeve": s, "m_real": m, "cycle4_mc_code_reseeded": p, "se": binom_se(p, n_main),
                    "cycle4_analytic": float(an), "z_gap": (p - float(an)) / binom_se(p, n_main)})
    out["cycle4_simulator_reseeded"] = rep
    print("reseeded cycle-4 MC", rep, round(time.time() - t, 1))

    # (2) decomposition with the independent audit MC, base case + variants
    variants = [("base rho=.15 phi=.1", dict()), ("rho=0 (independent sleeves)", dict(rho=0.0)),
                ("phi=0 (no autocorr)", dict(phi=0.0)), ("rho=.30", dict(rho=0.30))]
    for lab, upd in variants:
        Pv = dict(BASE, **upd)
        for s, m in ((0.6, 5), (0.4, 5), (0.0, 0)):
            n = n_main if lab.startswith("base") else n_var
            d = decompose(s, m, Pv, n, salt=lab)
            d["normal_theory_mc_of_one_factor_integral"] = normal_theory_mc(s, m, Pv, 400_000, lab)
            d["variant"] = lab
            rows.append(d)
            print(lab, s, m, {k_: (round(v, 4) if isinstance(v, float) else v) for k_, v in d.items()
                              if k_ in ("analytic_binomial_cycle4", "analytic_one_factor", "mc_audit", "mc_se",
                                        "part_correlated_inclusion_exact", "part_composition_residual_mc",
                                        "part_hold_stage_mc", "seconds")})
    out["decomposition"] = rows

    # (3) practitioner hold statistic (literal NW t) -- what the real hold-out gate computes
    prac = []
    for s, m in ((0.6, 5), (0.0, 0)):
        R, Z, ok, _ = audit_mc(s, m, BASE, n_var, "prac", hold_stat="nw_t")
        A = analytic_tables(s, m, BASE)
        prac.append({"s_sleeve": s, "m_real": m, "mc_nw_t_hold": float(ok.mean()), "se": binom_se(float(ok.mean()), n_var),
                     "analytic_one_factor": A["joint_1f"], "analytic_binomial": A["joint_bin"]})
    out["practitioner_nw_hold"] = prac
    print("practitioner", prac)

    # (4) what the correction does to the registered retrospective spec (daily, 252, phi .1) and its verdict
    retro = []
    Pr = dict(BASE, q=252, phi=0.1)
    fac = math.sqrt(5 * (1 + 4 * 0.15)) / 5
    for S in (0.0, 0.3, 0.5, 0.7, 1.0):
        s = S * fac
        mm = 5 if S > 0 else 0
        A = analytic_tables(s, mm, Pr)
        retro.append({"ideal_book_S": S, "per_sleeve_s": s, "cycle4_binomial": A["joint_bin"],
                      "one_factor_corrected": A["joint_1f"]})
    out["retro_multiasset_daily"] = retro
    write_csv("sleeve_miss_decomposition.csv", rows)
    dump("sleeve_miss.json", out)
    return out


if __name__ == "__main__":
    run()
