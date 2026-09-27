"""research.power.tables -- build every output under reports/power/ (synthetic / analytic only).

    PYTHONPATH=. .venv/bin/python -m research.power.tables [--fast]

Writes:
  reports/power/<spec>.json / .txt      one plan_check report per example spec (retro_*, pro_*, c4*)
  reports/power/retrospective.csv       registered families, their real windows, current gates vs proposed gate
  reports/power/prospective.csv         archetypes + cycle-4 candidates, base rows and scenario grids
  reports/power/validation_gate_oc.csv  current 0.75 gate vs proposed power-aware gate (+ variants)
  reports/power/winners_curse.csv       dev estimate vs selection-corrected estimates, validation power at each
  reports/power/mc_agreement.csv        analytic vs Monte Carlo, every design
  reports/power/breadth_curves.csv      N_eff vs N for rho grid
  reports/power/{breadth_curves,power_vs_years,validation_gate_oc}.png
  reports/power/manifest.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import pathlib
import time

import numpy as np

from research.power import gates as G
from research.power import plan_check as PC
from research.power import specs as SP
from research.power import verify as V
from research.power.core import SEED, Autocorr, SeriesModel, breadth_eff, single_test_power

OUT = pathlib.Path("reports/power")
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]  # validated default categorical order

NULL_LAB2 = {"retro_tsy_month_end": "tsy_month_end(M)", "retro_insider": "insider(N1-N4)",
             "retro_etf_hybrids": "etf_hybrids(E1-E5)", "retro_ief_shy_duration": "structural_frontier(A: Treasury term premium)",
             "retro_commodity_roll": "commodity_roll", "retro_fx_hedge_rebal": "fx_hedge_rebal",
             "retro_pead_2004_2014": "pead_2004_2014",
             "retro_multiasset_17_sleeves": "multiasset(17-sleeve inclusion + 5-sleeve holdout)"}
OUTCOME = {"retro_tsy_month_end": "dev PASS 0.664; val FAIL 0.69 < 0.75 (p 0.005)",
           "retro_commodity_roll": "dev PASS 0.596 (p 0.006); val FAIL 0.21",
           "retro_fx_hedge_rebal": "dev FAIL 0.09", "retro_pead_2004_2014": "FAIL (HAC t 1.12)",
           "retro_multiasset_17_sleeves": "5/17 included; hold-out FAIL (book -0.02)",
           "retro_ief_shy_duration": "dev FAIL on p (0.569 > 0.52 but p 0.023 > 0.0167)",
           "retro_insider": "dev PASS N3/N4; val FAIL 0.49/0.51", "retro_etf_hybrids": "dev PASS E1/E2; val FAIL 0.38/0.44"}


def _w(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 5) if isinstance(v, float) and math.isfinite(v) else v) for k, v in r.items()})


def _nl2():
    out = {}
    p = pathlib.Path("reports/null_lab2/calibration.csv")
    if p.exists():
        for r in csv.DictReader(open(p)):
            if r["cell"] == "power_true_sr_0.7":
                out[r["family"]] = r["P_pass_dev_and_val"] or r["P_pass_dev"]
    return out


def _pw(rep, world, key):
    for r in rep["power"]:
        if r["world"] == world:
            return r.get(key)


def run_reports() -> dict:
    SP.write_examples()
    reps = {}
    for s in SP.all_specs():
        rep = PC.run_spec(s)
        (OUT / f"{s['name']}.json").write_text(json.dumps(rep, indent=1))
        (OUT / f"{s['name']}.txt").write_text(PC.text(rep) + "\n")
        reps[s["name"]] = rep
    return reps


def retro_rows(reps) -> list[dict]:
    nl2 = _nl2()
    rows = []
    for s in SP.retrospective():
        r = reps[s["name"]]
        if r["design"] == "sleeve_screen":
            p = {round(x["ideal_book_sharpe"], 2): x for x in r["power"]}
            rows.append({"family": s["name"].replace("retro_", ""), "design": "sleeve_screen", "dev_years": 10.0,
                         "val_years": 8.71, "batch_k": 17, "dev_gate": "S_hat>=0.30 per sleeve, no null",
                         "val_gate": "book HAC t>=2", "p_dev_at_0.7": p[0.7]["p_include_real"],
                         "joint_at_0.5": p[0.5]["p_joint"], "joint_at_0.7": p[0.7]["p_joint"],
                         "joint_at_1.0": p[1.0]["p_joint"], "false_pass": r["false_pass_zero_net"],
                         "verdict": r["verdict"], "null_lab2_joint_at_0.7": nl2.get(NULL_LAB2[s["name"]]),
                         "realised": OUTCOME[s["name"]],
                         "note": f"P(include | null)={p[0.0]['p_include_null']:.3f}; E[# null sleeves included]={p[0.0]['expected_null_included']:.1f}"})
            continue
        g = r["gates"]
        yrs = {y["true_net_sharpe"]: y for y in r["years_for_power"]}
        rows.append({
            "family": s["name"].replace("retro_", ""), "design": r["design"],
            "dev_years": r["windows"]["dev_years"], "val_years": r["windows"]["val_years"],
            "batch_k": g.get("batch_k"), "n_raw_total": r["observations"]["raw_total"],
            "n_eff_total": r["observations"]["n_eff_total"], "D_time": r["observations"]["deff_time_D1"],
            "deff_cross": r["observations"]["deff_cross"],
            "se_sharpe_dev": r["standard_errors"]["se_sharpe_null_dev"],
            "dev_threshold": g["dev"]["threshold"], "dev_binding": g["dev"]["binding_leg"],
            "val_threshold": g["val_current"]["threshold"] if g.get("val_current") else None,
            "p_dev_at_0.7": _pw(r, "S=0.7", "p_dev"), "p_val_at_0.7": _pw(r, "S=0.7", "p_val_current"),
            "joint_at_0.5": _pw(r, "S=0.5", "p_joint_current"), "joint_at_0.7": r["joint_power_at_0.7"],
            "joint_at_1.0": _pw(r, "S=1.0", "p_joint_current"), "false_pass": r["false_pass_zero_net"],
            "mde_joint_current": r["mde"]["joint_current_gates"]["sharpe"],
            "years80_joint_current_at_0.7": yrs[0.7]["joint_current"],
            "verdict": r["verdict"],
            "joint_at_0.7_proposed_val_gate": _pw(r, "S=0.7", "p_joint_proposed"),
            "false_pass_proposed": _pw(r, "zero_net_null", "p_joint_proposed"),
            "years80_joint_proposed_at_0.7": yrs[0.7]["joint_proposed"],
            "verdict_proposed": r.get("verdict_with_proposed_val_gate"),
            "null_lab2_joint_at_0.7": nl2.get(NULL_LAB2[s["name"]]), "realised": OUTCOME[s["name"]]})
    return rows


def pro_rows(reps) -> list[dict]:
    rows = []
    for s in SP.prospective() + SP.cycle4():
        r = reps[s["name"]]
        yrs = {y["true_net_sharpe"]: y for y in r["years_for_power"]}
        base = {"archetype": s["name"], "row": "BASE (fixed Sharpe grid)", "dev_years": r["windows"]["dev_years"],
                "val_years": r["windows"]["val_years"], "n_raw_total": r["observations"]["raw_total"],
                "deff_cross": r["observations"]["deff_cross"], "D_time": r["observations"]["deff_time_D1"],
                "n_eff_total": r["observations"]["n_eff_total"], "n_eff_units": r["observations"]["n_eff_units"],
                "kappa0": r["standard_errors"]["kappa0"], "kappa_at_0.7": r["standard_errors"]["kappa_at_0.7"],
                "mde_single_test": r["mde"]["single_test_all_years"]["sharpe"],
                "mde_joint_current": r["mde"]["joint_current_gates"]["sharpe"],
                "mde_joint_proposed": r["mde"]["joint_with_proposed_val_gate"]["sharpe"],
                "mde_natural_joint_proposed": r["mde"]["joint_with_proposed_val_gate"]["natural"],
                "natural_unit": r["standard_errors"]["natural_unit"]}
        for S in (0.3, 0.5, 0.7, 1.0):
            base[f"joint_cur_{S}"] = _pw(r, f"S={S}", "p_joint_current")
            base[f"joint_pav_{S}"] = _pw(r, f"S={S}", "p_joint_proposed")
            base[f"yrs80_single_{S}"] = yrs[S]["single_test"]
            base[f"yrs80_joint_pav_{S}"] = yrs[S]["joint_proposed"]
        base["false_pass_current"] = r["false_pass_zero_net"]
        base["verdict_current"] = r["verdict"]
        base["verdict_proposed"] = r["verdict_with_proposed_val_gate"]
        rows.append(base)
        for sc in r.get("scenarios", []):
            rows.append({"archetype": s["name"], "row": sc["label"], "n_eff_units": sc["n_eff_units"],
                         "deff_cross": sc["deff_cross"], "implied_sharpe_gross": sc.get("implied_sharpe_gross"),
                         "implied_sharpe_net": sc["implied_sharpe_net"], "turnover": sc.get("turnover"),
                         "cost_drag_sharpe": sc.get("cost_drag_sharpe"),
                         "single_test_power_at_implied": sc.get("single_test_power_at_implied"),
                         "joint_current_at_implied": sc.get("joint_current_at_implied"),
                         "joint_proposed_at_implied": sc.get("joint_proposed_at_implied"),
                         "yrs80_single_at_implied": sc.get("years_80_single_test_at_implied"),
                         "yrs80_joint_proposed_at_implied": sc.get("years_80_joint_proposed_at_implied"),
                         "mde_natural_single_test": sc["mde_natural_single_test"],
                         "mde_natural_joint_proposed": sc["mde_natural_joint_proposed"]})
    return rows


def val_gate_oc() -> tuple[list[dict], list[dict]]:
    """Operating characteristics of candidate validation gates on tsy_month_end-like windows (12y + 11.6y, D 1.4,
    stress drag 0.2) and on a generic 5y + 5y daily design."""
    rows = []
    cases = {"tsy_like_12+11.6y": (SeriesModel(252, Autocorr("lrv", D=1.40)), 11.99, 11.63, 0.20),
             "generic_daily_5+5y": (SeriesModel(252, Autocorr("ar1", phi=0.05)), 5.0, 5.0, 0.10),
             "generic_daily_10+10y": (SeriesModel(252, Autocorr("ar1", phi=0.05)), 10.0, 10.0, 0.10)}
    for case, (ser, Yd, Yv, drag) in cases.items():
        dg = G.amendment2_dev_gate(1, drag)
        vgs = {"current: S>=0.75 & p<.05 & stress": G.current_val_gate(1, drag),
               "PROPOSED PAV: HAC-t p<.05/k_val & stress": G.power_aware_val_gate(1, drag),
               "PAV + floor S>=0.3": G.power_aware_val_gate(1, drag, floor=0.3),
               "PAV at k_val=3": G.power_aware_val_gate(3, drag),
               "effect-size: S_val >= 0.5 x S_dev & p<.05": G.Gate(fraction_of_dev=0.5, alpha=0.05, stress_drag_sr=drag)}
        for name, vg in vgs.items():
            for S in (-0.3, 0.0, 0.05, 0.3, 0.5, 0.7, 1.0):
                j = G.joint_pass(S, ser, Yd, dg, ser, Yv, vg)
                rows.append({"case": case, "val_gate": name, "true_net_sharpe": S, "p_dev": j["p_dev"],
                             "p_val_given_dev_pass": j["p_val"], "p_joint": j["p_joint"],
                             "val_threshold_sharpe": vg.threshold(ser, Yv) if vg.fraction_of_dev is None else None,
                             "years80_joint_total_50_50": G.years_joint(S, ser, dg, ser, vg, 0.5) if S > 0 else None})
    wc = []
    for name, ser, Yd, Yv, drag, est, k in (
            ("tsy_month_end", SeriesModel(252, Autocorr("lrv", D=1.40)), 11.99, 11.63, 0.20, 0.664, 1),
            ("commodity_roll", SeriesModel(252, Autocorr("lrv", D=0.60), -0.3, 8.0), 10.44, 9.71, 0.31, 0.596, 2),
            ("ief_shy (did not pass)", SeriesModel(252, Autocorr("lrv", D=0.97)), 12.0, 11.7, 0.002, 0.569, 3)):
        dg = G.amendment2_dev_gate(k, drag, -0.098 if name == "tsy_month_end" else 0.0)
        cmu = G.truncation_corrected_estimate(est, ser, Yd, dg)
        post = G.normal_prior_posterior(est, ser, Yd)
        for lab, S in (("dev estimate", est), ("conditional median-unbiased", cmu), ("N(0,0.5^2) posterior mean", post)):
            if S is None:
                continue
            wc.append({"family": name, "dev_threshold": dg.threshold(ser, Yd), "estimate": lab, "S": S,
                       "p_val_current": float(G.current_val_gate(k, drag).pass_prob(S, ser, Yv)),
                       "p_val_proposed": float(G.power_aware_val_gate(1, drag).pass_prob(S, ser, Yv))})
    return rows, wc


def breadth_rows() -> list[dict]:
    rows = []
    for rho in (0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7):
        for N in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 8000):
            rows.append({"rho_bar": rho, "N": N, "N_eff": float(breadth_eff(N, rho)),
                         "sharpe_multiplier_sqrt_Neff": math.sqrt(float(breadth_eff(N, rho)))})
    return rows


def plots(oc_rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def style(ax):
        ax.grid(True, color="#e6e5e1", linewidth=0.6)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color("#9a9994")
        ax.tick_params(colors="#52514e", labelsize=9)

    # 1. breadth
    fig, ax = plt.subplots(figsize=(7.5, 4.6), dpi=150)
    N = np.unique(np.round(np.logspace(0, np.log10(8000), 200)))
    for i, rho in enumerate((0.01, 0.05, 0.1, 0.3, 0.6)):
        y = breadth_eff(N, rho)
        ax.plot(N, y, color=PALETTE[i], lw=2, label=f"ρ̄ = {rho}")
        ax.text(N[-1] * 1.05, y[-1], f"{rho}", color="#52514e", fontsize=8, va="center")
    ax.plot(N, N, color="#9a9994", lw=1, ls="--", label="independent (ρ̄ = 0)")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("N (assets / events / markets)", color="#52514e"); ax.set_ylabel("effective N", color="#52514e")
    ax.set_title("Effective breadth N/(1+(N−1)ρ̄) saturates at 1/ρ̄", loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=8, loc="upper left"); style(ax)
    fig.tight_layout(); fig.savefig(OUT / "breadth_curves.png"); plt.close(fig)

    # 2. power vs years (single test, alpha .05, daily phi .05) and joint with PAV
    fig, ax = plt.subplots(figsize=(7.5, 4.6), dpi=150)
    ser = SeriesModel(252, Autocorr("ar1", phi=0.05))
    Y = np.linspace(1, 40, 120)
    dg = G.amendment2_dev_gate(1, 0.1)
    pg = G.power_aware_val_gate(1, 0.1)
    vg = G.current_val_gate(1, 0.1)
    for i, S in enumerate((0.3, 0.5, 0.7, 1.0)):
        ax.plot(Y, [G.joint_pass(S, ser, y / 2, dg, ser, y / 2, pg)["p_joint"] for y in Y], color=PALETTE[i], lw=2,
                label=f"S = {S}, proposed val gate")
        ax.plot(Y, [G.joint_pass(S, ser, y / 2, dg, ser, y / 2, vg)["p_joint"] for y in Y], color=PALETTE[i], lw=1.2,
                ls=":", label=f"S = {S}, current 0.75 gate")
    ax.axhline(0.8, color="#9a9994", lw=0.8); ax.axhline(0.5, color="#9a9994", lw=0.8, ls="--")
    ax.set_xlabel("total years (dev = val = half)", color="#52514e"); ax.set_ylabel("P(pass dev AND validation)", color="#52514e")
    ax.set_title("Joint power vs history length (daily, k = 1)", loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=7, ncol=2, loc="upper left"); style(ax); ax.set_ylim(0, 1)
    fig.tight_layout(); fig.savefig(OUT / "power_vs_years.png"); plt.close(fig)

    # 3. validation-gate OC on tsy-like windows
    fig, ax = plt.subplots(figsize=(7.5, 4.6), dpi=150)
    names = ["current: S>=0.75 & p<.05 & stress", "PROPOSED PAV: HAC-t p<.05 & stress (k_val=1)",
             "PAV with k_val=3 (p<.0167)"]
    ser = SeriesModel(252, Autocorr("lrv", D=1.40))
    Ss = np.linspace(0, 1.4, 57)
    gs = [G.current_val_gate(1, 0.2), G.power_aware_val_gate(1, 0.2), G.power_aware_val_gate(3, 0.2)]
    for i, (nm, g) in enumerate(zip(names, gs)):
        ax.plot(Ss, [float(g.pass_prob(s, ser, 11.63)) for s in Ss], color=PALETTE[i], lw=2, label=nm)
    ax.axhline(0.05, color="#9a9994", lw=0.8, ls="--")
    ax.set_xlabel("true net Sharpe in validation", color="#52514e"); ax.set_ylabel("P(validation pass)", color="#52514e")
    ax.set_title("Validation gate operating characteristic (11.6y, tsy_month_end-like)", loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=8, loc="upper left"); style(ax); ax.set_ylim(0, 1)
    fig.tight_layout(); fig.savefig(OUT / "validation_gate_oc.png"); plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    reps = run_reports()
    _w(OUT / "retrospective.csv", retro_rows(reps))
    _w(OUT / "prospective.csv", pro_rows(reps))
    oc, wc = val_gate_oc()
    _w(OUT / "validation_gate_oc.csv", oc)
    _w(OUT / "winners_curse.csv", wc)
    _w(OUT / "breadth_curves.csv", breadth_rows())
    mc = V.suite(fast=a.fast)
    _w(OUT / "mc_agreement.csv", mc)
    plots(oc)
    files = sorted(p for p in OUT.iterdir() if p.is_file() and p.name != "manifest.json")
    code = sorted(pathlib.Path("research/power").glob("*.py"))
    (OUT / "manifest.json").write_text(json.dumps({
        "seed": SEED, "runtime_seconds": round(time.time() - t0, 1), "fast": a.fast,
        "mc_checks": len(mc), "mc_within_tolerance": sum(r["within_tolerance"] is True for r in mc),
        "mc_formula_checks": sum(r["within_tolerance"] is not None for r in mc),
        "synthetic_only": True, "no_family_evaluate_run": True,
        "code_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in code},
        "outputs": [p.name for p in files]}, indent=1))
    print(f"done in {time.time() - t0:.0f}s; MC within tolerance {sum(r['within_tolerance'] is True for r in mc)}/"
          f"{sum(r['within_tolerance'] is not None for r in mc)} formula checks")


if __name__ == "__main__":
    main()
