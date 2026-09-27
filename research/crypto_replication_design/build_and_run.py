"""Power specs for the crypto funding-XS external-replication design (cycle 5, C2). NO market data is read.

    PYTHONPATH=. .venv/bin/python -m research.crypto_replication_design.build_and_run

Writes design specs to research/crypto_replication_design/specs/ and results to reports/crypto_replication_design/.
Uses research.power.plan_check.run_spec (unchanged). The only empirical inputs are the ALREADY-REPORTED Binance dev
summary numbers (Sharpe 1.65, bootstrap p 0.038, T 2.17 y); nothing new is computed from any venue's data.
"""
from __future__ import annotations

import csv
import json
import math
import pathlib

import numpy as np
from scipy import stats

from research.power.plan_check import run_spec

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPECS = pathlib.Path(__file__).with_name("specs")
OUT = ROOT / "reports" / "crypto_replication_design"
N = stats.norm

# ----------------------------------------------------------------------------- base series model (as c4a spec)
BASE_PARAMS = {"n_assets": 100, "periods_per_year": 365, "ic": 0.02, "cs_dispersion": 0.04, "quantile": 0.2,
               "rho_resid": 0.3, "rho_signal": 0.25, "signal_autocorr": 0.9, "cost_bps_one_way": 8,
               "spread_autocorr": 0.05, "skew": -0.3, "exkurt": 10.0}
ASSUME = [
    "series model copied from research/power/examples/c4a_binance_funding_ls_daily.json (registered for the frozen rule)",
    "ASSUMPTION rho_resid 0.3, rho_signal 0.25 (factor tilt), signal autocorr 0.9, spread AR(1) 0.05, skew -0.3, exkurt 10",
    "SE model 'heavy': spread AR(1) 0.30 -> kappa0 ~1.36/sqrt(yr), matching the SE implied by the ALREADY-REPORTED Binance "
    "dev bootstrap (1.65 / z(0.038) = 0.93 over 2.17 y); no new data used",
    "single-stage design: the replication window is the only tested window (val_years null); the 'dev' gate below IS "
    "the replication gate",
    "stress_drag_sr 0.15 (stress cost minus base cost, Sharpe units), as c4a",
]
GRID = [0.3, 0.5, 0.7, 1.0, 1.2, 1.65]

GATES = {  # replication gate variants (one-sided; k = 1)
    "p05_floor030": {"kind": "custom", "alpha": 0.05, "sharpe_abs": 0.30, "stress": True,
                     "description": "one-sided p<0.05, stress mean>0, Sharpe>=0.30 (amendment-3 P2 form, k=1)"},
    "p025_floor030": {"kind": "custom", "alpha": 0.025, "sharpe_abs": 0.30, "stress": True,
                      "description": "one-sided p<0.025 (95% CI excludes 0), stress>0, Sharpe>=0.30"},
    "p01_floor030": {"kind": "custom", "alpha": 0.01, "sharpe_abs": 0.30, "stress": True,
                     "description": "one-sided p<0.01, stress>0, Sharpe>=0.30"},
    "half_dev_p025": {"kind": "custom", "alpha": 0.025, "sharpe_abs": 0.825, "stress": True,
                      "description": "Sharpe >= 50% of Binance dev 1.65 (0.825) AND 95% CI excludes 0, stress>0"},
}

DESIGNS = {
    # name: (years, params override, description)
    "R1_bybit_2020_2022": (1.5, {"n_assets": 50, "cost_bps_one_way": 10},
                           "Bybit USDT linear perps 2020-01..2022-12; ASSUMPTION ~1.5 effective years with >=25 "
                           "eligible perps (alt perps listed mostly 2020-Q4..2021), mean N ~50, base cost 10 bp"),
    "R2_bybit_2023_2026_FORBIDDEN": (3.67, {"n_assets": 100, "cost_bps_one_way": 8},
                                     "Bybit 2023-01..2026-08 -- overlaps the LOCKED Binance validation window; "
                                     "powered only to show what is being forgone; NOT permitted"),
    "R3_bitmex_perps_2020_2022_HYPOTHETICAL": (2.0, {"n_assets": 15, "cost_bps_one_way": 10},
                                               "BitMEX perps 2020-2022; ASSUMPTION N~15 < MIN_UNIVERSE 25, so the "
                                               "frozen rule drops every day; row shows power IF re-specified (not the "
                                               "exact claim)"),
    "F1_forward_1y": (1.0, {}, "forward-only, frozen rule, Binance USD-M (observation only), N=100, 1 year"),
    "F2_forward_2y": (2.0, {}, "forward-only, 2 years"),
    "F3_forward_3y": (3.0, {}, "forward-only, 3 years"),
    "F5_forward_5y": (5.0, {}, "forward-only, 5 years"),
}
SE_MODELS = {"base": {}, "heavy": {"spread_autocorr": 0.30}}


def spec(dname, gname, sename):
    years, over, desc = DESIGNS[dname]
    p = dict(BASE_PARAMS, **over, **SE_MODELS[sename])
    return {"name": f"crep_{dname}__{gname}__{sename}", "description": desc + f" | gate {gname} | SE model {sename}",
            "assumptions": ASSUME, "design": "long_short", "params": p,
            "windows": {"dev_years": years, "val_years": None},
            "gates": {"batch_k": 1, "stress_drag_sr": 0.15, "dev": GATES[gname], "val": {"kind": "none"}},
            "power": {"alpha": 0.05, "sharpe_grid": GRID}}


# ----------------------------------------------------------------------------- dependence (data-free)
def quintile_weight_cosine(r: float, q: float = 0.2) -> float:
    """cos(w_A, w_B) for quintile long-short weights when the two venues' signals are bivariate normal with corr r."""
    z = N.ppf(q)
    mvn = stats.multivariate_normal([0, 0], [[1, r], [r, 1]])
    p_bb = mvn.cdf([z, z])                          # both in bottom quintile (long on both)
    p_bt = float(q - mvn.cdf([z, -z]))              # A bottom, B top = P(X<z, Y>-z)
    return float((p_bb - p_bt) / q)


def dependence_table():
    rows = []
    for r in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95):
        c = quintile_weight_cosine(r)
        for phi in (0.7, 0.85, 0.95):
            rows.append({"signal_corr_same_coin": r, "universe_overlap_phi": phi, "weight_cosine": c,
                         "approx_strategy_return_corr": phi * c})
    return rows


def arbitrage_bound_table():
    """Lower bound on same-coin cross-venue signal corr r >= s_c^2/(s_c^2 + b^2): s_c = cross-coin sd of the 7-day
    daily-equivalent funding signal, b = max sd of the venue-specific component (bounded by cross-venue funding
    arbitrage cost). Inputs are ASSUMPTION grids, not data."""
    rows = []
    for s_c in (2.0, 3.0, 5.0, 10.0):          # bp/day
        for b in (0.5, 1.0, 2.0, 3.0):         # bp/day
            rows.append({"cross_coin_sd_bp_day": s_c, "venue_specific_sd_bp_day": b,
                         "r_lower_bound": s_c ** 2 / (s_c ** 2 + b ** 2)})
    return rows


def conditional_false_pass(se_rep_by_design):
    """P(replication passes | S_true, Binance dev S_hat = 1.65), treating (S_hat_bin, S_hat_rep) as bivariate normal
    with corr rho (sampling-error correlation from overlapping coins x months)."""
    s_bin, se_bin = 1.65, 1.65 / N.isf(0.038)
    rows = []
    for d, (se_rep, thr) in se_rep_by_design.items():
        for rho in (0.0, 0.3, 0.5, 0.7, 0.8, 0.9):
            for S in (0.0, 0.3, 0.7):
                m = S + rho * se_rep / se_bin * (s_bin - S)
                sd = se_rep * math.sqrt(1 - rho ** 2)
                rows.append({"design": d, "rho_sampling": rho, "true_S": S, "se_rep": se_rep, "threshold": thr,
                             "cond_mean_S_hat_rep": m, "P_pass_given_binance_dev": float(N.sf((thr - m) / sd)),
                             "P_pass_unconditional": float(N.sf((thr - S) / se_rep)),
                             "effective_independent_fraction": 1 - rho ** 2})
    return rows, se_bin


def replication_bf_oc(se_rep, se_bin, s_bin=1.65):
    """Verhagen-Wagenmakers replication BF (normal approximation): H_r: S ~ N(s_bin, se_bin^2) (original posterior
    under a flat prior) vs H_0: S = 0. BF_r0(x) = N(x; s_bin, se_bin^2 + se_rep^2) / N(x; 0, se_rep^2).
    Also the sceptical-prior posterior P(S > 0 | rep only) with prior N(0, 0.5^2) (project convention)."""
    out = []
    xs = np.linspace(-2, 4, 60001)
    bf = N.pdf(xs, s_bin, math.sqrt(se_bin ** 2 + se_rep ** 2)) / N.pdf(xs, 0, se_rep)
    for thr_bf in (3.0, 10.0):
        right = xs >= xs[int(np.argmin(bf))]       # BF is U-shaped (unequal variances); use the right branch
        ok = xs[right & (bf >= thr_bf)]
        xc = float(ok.min()) if ok.size else math.inf
        for S in (0.0, 0.3, 0.5, 0.7, 1.0, 1.65):
            out.append({"criterion": f"BF_r0>={thr_bf:g}", "S_hat_threshold": xc, "true_S": S,
                        "P_meet": float(N.sf((xc - S) / se_rep))})
    # sceptical prior N(0, 0.5^2): posterior mean = x * tau2/(tau2+se2); P(S>0) > 0.975  <=> x > 1.96*se*sqrt((tau2+se2)/tau2)
    tau2 = 0.25
    # posterior sd = sqrt(tau2 se2/(tau2+se2)); mean = x tau2/(tau2+se2); P(S>0)>0.975 <=> mean/sd > 1.96 <=> x > 1.96 se sqrt((tau2+se2)/tau2)
    xc = 1.96 * se_rep * math.sqrt((tau2 + se_rep ** 2) / tau2)
    for S in (0.0, 0.3, 0.5, 0.7, 1.0, 1.65):
        out.append({"criterion": "sceptical_N(0,0.5^2)_P(S>0)>0.975", "S_hat_threshold": xc, "true_S": S,
                    "P_meet": float(N.sf((xc - S) / se_rep))})
    return out


def group_sequential(kappa_by_model, looks=(3.0, 5.0), alpha=0.05, kill_z=-1.0, kill_looks=(1.0, 2.0)):
    """Forward design: O'Brien-Fleming-type efficacy boundaries at `looks` (years), one-sided overall alpha; plus
    kill-only (futility) looks at `kill_looks` (z < kill_z stops; can only lower the false-pass rate).
    Z_t = S_hat_t / (kappa/sqrt(t)); Brownian information structure; efficacy boundary c*sqrt(T/t)."""
    T = looks[-1]
    tt = list(kill_looks) + list(looks)
    cov = np.array([[math.sqrt(min(a, b) / max(a, b)) for b in tt] for a in tt])
    rng = np.random.default_rng(20260925)
    Z0 = rng.multivariate_normal(np.zeros(len(tt)), cov, size=400000)

    def p_pass(c, drift):
        Z = Z0 + drift[None, :]
        alive = np.ones(len(Z), bool)
        passed = np.zeros(len(Z), bool)
        for j, t in enumerate(tt):
            if t in kill_looks:
                alive &= Z[:, j] >= kill_z
            else:
                hit = alive & ~passed & (Z[:, j] >= c * math.sqrt(T / t))
                passed |= hit
        return float(passed.mean())
    # calibrate c at S = 0 WITHOUT futility (conservative: futility only lowers size)
    lo, hi = 1.0, 3.5
    for _ in range(40):
        mid = (lo + hi) / 2
        z_nf = Z0[:, len(kill_looks):]
        pr = float((z_nf >= np.array([mid * math.sqrt(T / t) for t in looks])[None, :]).any(axis=1).mean())
        lo, hi = (mid, hi) if pr > alpha else (lo, mid)
    c = (lo + hi) / 2
    rows = []
    for model, kappa in kappa_by_model.items():
        for S in (0.0, 0.3, 0.5, 0.7, 1.0, 1.65):
            drift = np.array([S * math.sqrt(t) / kappa for t in tt])
            rows.append({"se_model": model, "kappa": kappa, "looks_years": "|".join(map(str, looks)),
                         "kill_looks_years": "|".join(map(str, kill_looks)), "kill_z": kill_z,
                         "efficacy_z_boundaries": "|".join(f"{c * math.sqrt(T / t):.3f}" for t in looks),
                         "true_S": S, "P_confirm": p_pass(c, drift),
                         "P_killed_early": float(((Z0[:, :len(kill_looks)] + drift[None, :len(kill_looks)]) < kill_z).any(axis=1).mean())})
    return rows


def main():
    SPECS.mkdir(exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    se_for_cond = {}
    for d in DESIGNS:
        for g in GATES:
            for sm in SE_MODELS:
                sp = spec(d, g, sm)
                (SPECS / f"{sp['name']}.json").write_text(json.dumps(sp, indent=1))
                rep = run_spec(sp)
                (OUT / f"{sp['name']}.json").write_text(json.dumps(rep, indent=1))
                by = {r["world"]: r for r in rep["power"]}
                se0 = rep["standard_errors"]["se_sharpe_null_dev"]
                row = {"design": d, "gate": g, "se_model": sm, "years": DESIGNS[d][0],
                       "n_assets": sp["params"]["n_assets"], "se_sharpe_null": se0,
                       "threshold_sharpe": rep["gates"]["dev"]["threshold"],
                       "binding_leg": rep["gates"]["dev"]["binding_leg"],
                       "false_pass_S0": by["zero_net_null"]["p_joint_current"],
                       **{f"power_S{s}": by[f"S={s}"]["p_joint_current"] for s in GRID},
                       "mde80_sharpe": rep["mde"]["dev_gate_only"]["sharpe"],
                       "years80_at_0.7": next(y["dev_gate_only"] for y in rep["years_for_power"]
                                              if abs(y["true_net_sharpe"] - 0.7) < 1e-9),
                       "verdict": rep["verdict"]}
                summary.append(row)
                if g == "p05_floor030":
                    se_for_cond[f"{d}|{sm}"] = (se0, rep["gates"]["dev"]["threshold"])
    with open(OUT / "power_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)
    dep = dependence_table()
    arb = arbitrage_bound_table()
    cond, se_bin = conditional_false_pass({k: v for k, v in se_for_cond.items() if k.startswith(("R1", "R2"))})
    bf = []
    for k, (se, _) in se_for_cond.items():
        for r in replication_bf_oc(se, se_bin):
            bf.append({"design_se": k, "se_rep": se, **r})
    kap = {m: se_for_cond[f"F1_forward_1y|{m}"][0] for m in SE_MODELS}
    gs = group_sequential(kap)
    for name, rows in (("forward_group_sequential.csv", gs), ("dependence_weight_cosine.csv", dep), ("arbitrage_bound.csv", arb),
                       ("conditional_false_pass.csv", cond), ("bayes_criteria_oc.csv", bf)):
        with open(OUT / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    (OUT / "manifest.json").write_text(json.dumps({
        "program": "cycle5 C2 crypto replication design", "data_read": "none (power model only)",
        "binance_dev_inputs_already_reported": {"sharpe": 1.65, "bootstrap_p": 0.038, "years": 2.17,
                                                "implied_se": se_bin},
        "files": ["power_summary.csv", "dependence_weight_cosine.csv", "arbitrage_bound.csv",
                  "conditional_false_pass.csv", "bayes_criteria_oc.csv", "forward_group_sequential.csv", "crep_*.json (one plan_check report per spec)"],
        "n_specs": len(summary)}, indent=1))
    for r in summary:
        print(f"{r['design']:<40} {r['gate']:<14} {r['se_model']:<5} se={r['se_sharpe_null']:.2f} thr={r['threshold_sharpe']:.2f} "
              f"FP={r['false_pass_S0']:.3f} P0.5={r['power_S0.5']:.2f} P0.7={r['power_S0.7']:.2f} P1.0={r['power_S1.0']:.2f} "
              f"P1.65={r['power_S1.65']:.2f} y80@.7={r['years80_at_0.7']} {r['verdict']}")


if __name__ == "__main__":
    main()
