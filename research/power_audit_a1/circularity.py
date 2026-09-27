"""A1 audit: are the 53 'agreements' independent checks? Non-circular re-checks with practitioner statistics.

(1) A static classification of every row of reports/power/mc_agreement.csv by what the MC shares with the analytic.
(2) Re-checks that replace the analytic's own quantities inside the MC test statistic with what a practitioner
    computes (literal Newey-West t with plug-in lags, literal block bootstrap), and high-precision size checks
    where the cycle-4 tolerance (max 3 pp, 3 SE) cannot see a size error.
Synthetic data only.
"""
from __future__ import annotations

import csv
import math
import time

import numpy as np
from scipy import stats

from research.power import designs as DS
from research.power import gates as G
from research.power import simulate as M
from research.power.core import Autocorr, SeriesModel, nw_default_lags, single_test_power, z_upper
from research.power_audit_a1.common import OUT, ar1_paths, binom_se, dump, rng, write_csv

_N = stats.norm
ROOT = OUT.parents[1]


# ------------------------------------------------------------------------------------------------ (1) classification
def classify_rows() -> list[dict]:
    """Shared-assumption audit of each mc_agreement row (from reading simulate.py / verify.py)."""
    rows = list(csv.DictReader(open(ROOT / "reports" / "power" / "mc_agreement.csv")))
    out = []
    for r in rows:
        d, c = r["design"], r["check"]
        dgp_same = True                 # every MC simulates exactly the analytic's structural model
        stat = "literal"
        note = ""
        vacuous = False
        if d.startswith("timeseries daily") and "joint" in c:
            stat = "literal CBB p + literal Sharpe legs (independent of D formula)"
        elif "kappa" in c and "timeseries" in d:
            stat = "literal sample Sharpe"
        elif "overlapping" in d and "test power" in c:
            stat = "ideal_null=True: threshold = analytic z*sqrt(D/Y) (shares D)"
        elif "overlapping" in d and "kappa0" in c:
            stat = "literal sample Sharpe"
        elif "INFO" in c:
            stat = "literal NW t (the only practitioner HAC row) -- excluded from the count"
        elif d.startswith("event study") and "test power" in c:
            stat = "Sharpe >= z/sqrt(Y) threshold = the analytic's own iid-day null threshold"
            note = "does not test a clustered/HAC estimator; checks the deff variance only"
        elif d.startswith("event study") and "sd(mean CAR)" in c:
            stat = "literal sd across paths"
        elif "naive" in c:
            stat = "literal naive t"
        elif d.startswith("cross-sectional") and "power" in c:
            stat = "rejection uses m / (sd_ANALYTIC * sqrt(D_ANALYTIC/T)) -- the analytic SE itself"
            note = "fully circular for the SE; practitioner HAC rejection is computed but never reported"
        elif d.startswith("cross-sectional"):
            stat = "literal moments; DGP = exactly the one-factor Rademacher model the formula is derived from"
        elif d.startswith("decile"):
            stat = "literal sort/turnover/cost; DGP = the analytic's two-block tilt model"
        elif d.startswith("carry") and "power" in c:
            stat = "ideal_null=True: threshold uses the analytic D_null (=1)"
        elif d.startswith("carry"):
            stat = "literal moments"
        elif d.startswith("panel") and "EW-book" in c:
            stat = "t = mean/(sd*sqrt(D_TRUE/n)); per-market Sharpe set from the analytic N_eff (book S = S by construction)"
            note = "the N_eff part is an algebraic identity, not a check"
        elif d.startswith("panel") and "naive" in c:
            stat = "literal naive pooled t"
        elif d.startswith("17-sleeve"):
            stat = "hold t = mean/(sd*sqrt(D_TRUE/n)) -- analytic D, not an estimated HAC"
        try:
            a, m = float(r["analytic"]), float(r["mc"])
            tol = float(r["tolerance"])
            # a size/false-pass row is vacuous when the tolerance exceeds half the quantity itself
            if 0 <= a <= 0.06 and tol >= 0.5 * max(a, 1e-9):
                vacuous = True
        except ValueError:
            pass
        out.append({"design": d, "check": c, "param": r["param"], "analytic": r["analytic"], "mc": r["mc"],
                    "within_tolerance": r["within_tolerance"], "dgp_equals_analytic_model": dgp_same,
                    "mc_statistic": stat, "tolerance_vacuous_for_size": vacuous, "note": note})
    return out


# ------------------------------------------------------------------------------------------------ (2a) HAC-t size
def nw_size_grid(n_paths=40_000):
    """Size of a literal one-sided Newey-West t (plug-in lags floor(4(n/100)^(2/9)), the report's own default) at
    nominal 0.05 / 0.0167 / 0.01 -- Amendment 3 P2 allows 'a HAC t' as the validation p."""
    cases = [("daily AR(1) .05, 5y", 252, 5, Autocorr("ar1", phi=0.05)),
             ("daily AR(1) .15, 11.6y", 252, 11.63, Autocorr("ar1", phi=0.15)),
             ("daily(365) AR(1) .05, 3.67y (c4a val)", 365, 3.67, Autocorr("ar1", phi=0.05)),
             ("weekly AR(1) .1, 4.7y (c4b val)", 52, 4.7, Autocorr("ar1", phi=0.1)),
             ("monthly iid, 10y", 12, 10, Autocorr("ar1", phi=0.0)),
             ("monthly AR(1) .3, 10y", 12, 10, Autocorr("ar1", phi=0.3)),
             ("monthly 3m overlap, 10y", 12, 10, Autocorr("overlap", horizon=3)),
             ("monthly 3m overlap, 20y", 12, 20, Autocorr("overlap", horizon=3)),
             ("weekly 4w overlap, 5y", 52, 5, Autocorr("overlap", horizon=4))]
    rows = []
    for lab, q, Y, ac in cases:
        n = int(round(q * Y))
        L = nw_default_lags(n)
        g = rng("nwsize", lab)
        ts = []
        for i0 in range(0, n_paths, 4000):
            P = min(4000, n_paths - i0)
            x = M.sim_series(ac, n, P, g)
            ts.append(x.mean(1) / np.sqrt(M.nw_lrv(x, L) / n))
        t = np.concatenate(ts)
        D_nw_pop = ac.newey_west(L)
        for a in (0.05, 0.05 / 3, 0.01):
            p = float(np.mean(t >= z_upper(a)))
            rows.append({"case": lab, "n": n, "nw_lags": L, "D_true": ac.D1(), "D_nw_population": D_nw_pop,
                         "nominal_alpha": a, "size_mc": p, "se": binom_se(p, n_paths), "size_ratio": p / a,
                         "size_population_formula": float(_N.sf(z_upper(a) * math.sqrt(D_nw_pop / ac.D1())))})
    return rows


# ------------------------------------------------------------------------------------------------ (2b) CBB size
def cbb_size(n_paths=12_000, B=399):
    """High-precision size of the literal mean-centred CBB p (b = 21) on the PAV validation window."""
    rows = []
    for lab, ac, Y, b in (("daily AR(1) .15, 11.63y, b=21", Autocorr("ar1", phi=0.15), 11.63, 21),
                          ("daily AR(1) .05, 5y, b=21", Autocorr("ar1", phi=0.05), 5.0, 21)):
        n = int(round(252 * Y))
        g = rng("cbb", lab)
        ps = []
        for i0 in range(0, n_paths, 1000):
            P = min(1000, n_paths - i0)
            x = M.sim_series(ac, n, P, g)
            ps.append(M.cbb_pvalue(x, b, B, g))
        p = np.concatenate(ps)
        for a in (0.05, 0.05 / 3):
            s = float(np.mean(p < a))
            rows.append({"case": lab, "nominal_alpha": a, "size_mc": s, "se": binom_se(s, n_paths),
                         "size_formula_Dboot_vs_D": float(_N.sf(z_upper(a) * math.sqrt(ac.bartlett(b) / ac.D1())))})
    return rows


# ------------------------------------------------------------------------------------------------ (2c) re-checks
def ic_practitioner(n_paths=3000):
    rows = []
    for ic, rr, rs, H, ph in ((0.0, 0.2, 0.5, 1, 0.0), (0.02, 0.2, 0.5, 1, 0.0), (0.0, 0.1, 0.25, 3, 0.9),
                              (0.0, 0.1, 0.25, 6, 0.95)):
        d = DS.cross_sectional_ic(n_assets=200, periods_per_year=12, ic=ic, rho_resid=rr, rho_signal=rs,
                                  ic_autocorr={"model": "overlap_persistent", "phi": ph, "horizon": H})
        mc = M.mc_cross_sectional_ic(n_assets=200, n_periods=120, ic=ic, rho_resid=rr, rho_signal=rs, horizon=H,
                                     signal_autocorr=ph, n_paths=n_paths, seed_salt="a1_prac")
        an = float(single_test_power(d.implied["sharpe_gross_linear_book"], d.series, 10, 0.05))
        rows.append({"case": f"IC={ic} rho_r={rr} rho_s={rs} H={H} phi_s={ph}", "analytic": an,
                     "mc_circular_sd_analytic": mc["p_reject"],
                     "mc_practitioner_hac_lags_2H": mc["p_reject_practitioner_hac"],
                     "se": binom_se(mc["p_reject_practitioner_hac"], n_paths), "D_analytic": mc["D_analytic"]})
    return rows


def panel_practitioner(n_paths=6000):
    """EW-book test with a literal NW t (plug-in lags) instead of the true D, monthly 10y, K = 30."""
    rows = []
    for rho, phi, S in ((0.3, 0.05, 0.0), (0.3, 0.05, 0.7), (0.6, 0.1, 0.0), (0.45, 0.2, 0.0)):
        K, q, Y = 30, 12, 10
        n = q * Y
        g = rng("panel", rho, phi, S)
        n_eff = K / (1 + (K - 1) * rho)
        s_m = S / math.sqrt(n_eff)
        ok = []
        for i0 in range(0, n_paths, 1000):
            P = min(1000, n_paths - i0)
            common = ar1_paths(g, (P, n, 1), phi)
            idio = ar1_paths(g, (P, n, K), phi)
            x = math.sqrt(rho) * common + math.sqrt(1 - rho) * idio + s_m / math.sqrt(q)
            book = x.mean(2)
            L = nw_default_lags(n)
            t = book.mean(1) / np.sqrt(M.nw_lrv(book, L) / n)
            ok.append(t >= z_upper(0.05))
        p = float(np.concatenate(ok).mean())
        ser = SeriesModel(q, Autocorr("ar1", phi=phi))
        rows.append({"case": f"K=30 rho={rho} phi={phi} S={S}", "analytic": float(single_test_power(S, ser, Y, 0.05)),
                     "mc_literal_nw": p, "se": binom_se(p, n_paths)})
    return rows


def carry_practitioner(n_paths=8000):
    """Carry with common crashes, dev gate 1.8/sqrt(T) & p<.05 where p is a literal NW t (not ideal null)."""
    rows = []
    g8 = G.Gate(sharpe_c=1.8, alpha=0.05)
    for (K, rho, p, m, sd, S, Y) in ((8, 0.3, 0.03, -6.0, 1.0, 0.0, 10), (8, 0.3, 0.03, -6.0, 1.0, 0.5, 10),
                                     (4, 0.4, 0.05, -4.0, 1.0, 0.0, 17.5), (4, 0.4, 0.05, -4.0, 1.0, 0.7, 17.5)):
        cm = DS.crash_moments(p, m, sd)
        pm = DS.one_factor_portfolio_moments(K, rho, cm["skew"], cm["exkurt"])
        d = DS.carry(n_assets=K, periods_per_year=12, rho=rho, autocorr=0.0, skew=pm["skew"], exkurt=pm["exkurt"])
        g = rng("carry", K, S)
        n = int(round(12 * Y))
        mJ = p * m
        v = rho + (1 - rho) / K
        oks = []
        for i0 in range(0, n_paths, 2000):
            P = min(2000, n_paths - i0)
            I = g.random((P, n)) < p
            J = m + sd * g.standard_normal((P, n))
            F = (g.standard_normal((P, n)) + I * J - mJ) / math.sqrt(cm["var"])
            e = g.standard_normal((P, n, K)).mean(2)
            x = (math.sqrt(rho) * F + math.sqrt(1 - rho) * e) / math.sqrt(v)
            ok, _ = M.apply_gate(x, S, 12, g8, d.series, rng=g, ideal_null=False)   # literal NW t
            oks.append(ok)
        pp = float(np.concatenate(oks).mean())
        rows.append({"case": f"K={K} rho={rho} crash p={p} jump={m} S={S} Y={Y}",
                     "analytic": float(g8.pass_prob(S, d.series, Y)), "mc_literal_nw": pp, "se": binom_se(pp, n_paths)})
    return rows


def run():
    t = time.time()
    cls = classify_rows()
    write_csv("circularity_classification.csv", cls)
    print("classified", len(cls), round(time.time() - t, 1))
    nw = nw_size_grid(); write_csv("hac_t_size_grid.csv", nw); print("nw", round(time.time() - t, 1))
    cb = cbb_size(); write_csv("cbb_size.csv", cb); print("cbb", cb, round(time.time() - t, 1))
    icp = ic_practitioner(); print("ic", icp, round(time.time() - t, 1))
    pan = panel_practitioner(); print("panel", pan, round(time.time() - t, 1))
    car = carry_practitioner(); print("carry", car, round(time.time() - t, 1))
    write_csv("noncircular_rechecks.csv", [dict(block="ic", **r) for r in icp] + [dict(block="panel", **r) for r in pan]
              + [dict(block="carry", **r) for r in car])
    dump("circularity.json", {"classification": cls, "nw_size": nw, "cbb_size": cb, "ic": icp, "panel": pan,
                              "carry": car})


if __name__ == "__main__":
    run()
