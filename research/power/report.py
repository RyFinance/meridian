"""research.power.report -- evaluate a design under the project's two-stage pipeline and return a JSON-able report.

Verdict (proposed thresholds, recorded in every report):
  DECISIVE   joint dev+validation power at true net Sharpe 0.7 >= 50%  AND  P(pass both | S = 0) <= 5%
  INCAPABLE  joint power at 0.7 < 25% (a real 0.7 edge is >= 3x more likely to be missed than caught)
             OR false-pass > 10%
  MARGINAL   anything in between
"""
from __future__ import annotations

import math

import numpy as np

from research.power import gates as G
from research.power.core import (DEFAULT_POWER, NULL_WORLDS, SHARPE_GRID, batch_alpha, mde_single_test,
                                 nw_default_lags, single_test_power, size_with_estimated_variance,
                                 years_single_test)
from research.power.designs import Design

VERDICT_RULE = {"decisive_min_joint_power_at_0.7": 0.50, "max_false_pass": 0.05,
                "incapable_below_joint_power_at_0.7": 0.25, "incapable_above_false_pass": 0.10}


def verdict(joint_at_07: float, false_pass: float) -> str:
    if joint_at_07 >= VERDICT_RULE["decisive_min_joint_power_at_0.7"] and false_pass <= VERDICT_RULE["max_false_pass"]:
        return "DECISIVE"
    if joint_at_07 < VERDICT_RULE["incapable_below_joint_power_at_0.7"] or \
            false_pass > VERDICT_RULE["incapable_above_false_pass"]:
        return "INCAPABLE"
    return "MARGINAL"


# ---------------------------------------------------------------------------------------------- gate resolution
def _alpha(v, k):
    if v in (None, "none"):
        return None
    if v == "auto":
        return batch_alpha(k)
    return float(v)


def gates_from_spec(g: dict, design: Design) -> tuple[G.Gate, G.Gate | None, G.Gate, dict]:
    """Build (dev_gate, val_gate, proposed_val_gate) from the JSON 'gates' block."""
    k = int(g.get("batch_k", 1))
    drag = g.get("stress_drag_sr")
    dev = g.get("dev", {"kind": "amendment2"})
    center = float(dev.get("null_center_sr", 0.0))
    if dev.get("kind", "amendment2") == "amendment2":
        dg = G.amendment2_dev_gate(k, drag, center)
        if "alpha" in dev:
            dg.alpha = _alpha(dev["alpha"], k)
        if "sharpe_c" in dev:
            dg.sharpe_c = dev["sharpe_c"]
    else:
        dg = G.Gate(name=dev.get("name", "custom_dev"), sharpe_abs=dev.get("sharpe_abs"),
                    sharpe_c=dev.get("sharpe_c"), alpha=_alpha(dev.get("alpha"), k), null_center_sr=center,
                    hac_t=dev.get("hac_t"), stress_drag_sr=drag if dev.get("stress", True) else None,
                    both_halves_positive=bool(dev.get("both_halves_positive", False)),
                    description=dev.get("description", ""))
    val = g.get("val", {"kind": "sharpe", "value": 0.75, "alpha": "auto"})
    vk = val.get("kind", "sharpe")
    vdrag = drag if val.get("stress", True) else None
    vcenter = float(val.get("null_center_sr", 0.0))
    if vk == "none":
        vg = None
    elif vk == "sharpe":
        vg = G.Gate(name=f"val_sharpe_{val.get('value', 0.75)}", sharpe_abs=float(val.get("value", 0.75)),
                    alpha=_alpha(val.get("alpha", "auto"), k), stress_drag_sr=vdrag, null_center_sr=vcenter,
                    hac_t=val.get("hac_t"))
    elif vk == "tstat":
        vg = G.Gate(name="val_tstat", alpha=_alpha(val.get("alpha", "auto"), k), stress_drag_sr=vdrag,
                    sharpe_abs=val.get("floor"), null_center_sr=vcenter)
    elif vk == "hac_t":
        vg = G.Gate(name="val_hac_t", hac_t=float(val["t"]), stress_drag_sr=vdrag, sharpe_abs=val.get("floor"))
    elif vk == "fraction_of_dev":
        vg = G.Gate(name=f"val_frac_{val['fraction']}", fraction_of_dev=float(val["fraction"]),
                    alpha=_alpha(val.get("alpha", "auto"), k), stress_drag_sr=vdrag, sharpe_abs=val.get("floor"))
    elif vk == "natural":
        thr = design.sharpe_from_natural(float(val["value"]))
        vg = G.Gate(name=f"val_natural_{val['value']}", natural_min=float(val["value"]), natural_to_sharpe=thr,
                    alpha=_alpha(val.get("alpha", "auto"), k), stress_drag_sr=vdrag)
    else:
        raise ValueError(f"unknown validation gate kind {vk!r}")
    pav_cfg = g.get("pav", {})
    pg = G.power_aware_val_gate(k_val=int(pav_cfg.get("k_val", 1)), stress_drag_sr=drag,
                                floor=pav_cfg.get("floor"))
    info = {"batch_k": k, "alpha_batch": batch_alpha(k), "stress_drag_sr": drag}
    return dg, vg, pg, info


# ---------------------------------------------------------------------------------------------- evaluate
def evaluate(design: Design, *, dev_years: float, val_years: float | None, dev_gate: G.Gate,
             val_gate: G.Gate | None, pav_gate: G.Gate | None = None, alpha: float = 0.05,
             power: float = DEFAULT_POWER, grid=SHARPE_GRID, dev_fraction: float | None = None,
             val_multiplier: float = 1.0, dev_estimate: float | None = None, name: str | None = None,
             gate_info: dict | None = None) -> dict:
    ser = design.series
    Yd = float(dev_years)
    Yv = float(val_years) if val_years else None
    Yt = Yd + (Yv or 0.0)
    frac = dev_fraction if dev_fraction is not None else (Yd / Yt)
    n_dev = int(round(ser.periods_per_year * Yd))
    lags = nw_default_lags(n_dev)
    D_nw = ser.autocorr.newey_west(lags)

    obs = {
        "raw_dev": design.n_raw(Yd), "raw_val": design.n_raw(Yv) if Yv else None, "raw_total": design.n_raw(Yt),
        "raw_unit": design.raw_unit, "periods_dev": n_dev,
        "deff_time_D1": ser.D1, "deff_time_D1_finite_dev": ser.autocorr.D1(n_dev) if ser.autocorr.model != "lrv" else ser.D1,
        "deff_cross": design.deff_cross, "deff_total": design.deff_cross * ser.D1,
        "n_eff_dev": design.n_eff(Yd), "n_eff_val": design.n_eff(Yv) if Yv else None,
        "n_eff_total": design.n_eff(Yt), "n_units": design.n_units, "n_eff_units": design.n_eff_units,
    }
    se = {
        "se_sharpe_null_dev": float(ser.se(0.0, Yd)), "se_sharpe_null_val": float(ser.se(0.0, Yv)) if Yv else None,
        "se_sharpe_null_total": float(ser.se(0.0, Yt)),
        "se_sharpe_at": {str(s): float(ser.se(s, Yt)) for s in grid},
        "kappa0": math.sqrt(float(ser.kappa2(0.0))), "kappa_at_0.7": math.sqrt(float(ser.kappa2(0.7))),
        "natural_unit": design.natural_unit,
        "se_mean_natural_dev": design.se_natural(Yd), "se_mean_natural_total": design.se_natural(Yt),
    }
    nw = {"nw_lags_default": lags, "D_nw_expected": D_nw, "D_true": ser.D1,
          "actual_size_nominal_alpha_with_default_nw": size_with_estimated_variance(alpha, ser.D1, D_nw),
          "actual_size_nominal_alpha_if_iid_se": size_with_estimated_variance(alpha, ser.D1, 1.0)}

    # MDE
    mde_single = mde_single_test(ser, Yt, alpha, power)
    mde_dev = G.solve_mde(lambda S: dev_gate.pass_prob(S, ser, Yd), power)
    mde_joint_cur = G.mde_joint(ser, Yd, dev_gate, ser, Yv, val_gate, power, val_multiplier)
    mde_joint_pav = G.mde_joint(ser, Yd, dev_gate, ser, Yv, pav_gate, power, val_multiplier) if (pav_gate and Yv) else None
    nat = lambda S: (design.natural_from_sharpe(S) if S is not None and math.isfinite(S) else None)
    mde = {"alpha": alpha, "power": power,
           "single_test_all_years": {"sharpe": mde_single, "natural": nat(mde_single)},
           "dev_gate_only": {"sharpe": mde_dev, "natural": nat(mde_dev)},
           "joint_current_gates": {"sharpe": mde_joint_cur, "natural": nat(mde_joint_cur)},
           "joint_with_proposed_val_gate": {"sharpe": mde_joint_pav, "natural": nat(mde_joint_pav)}}

    # power table
    worlds = [("cost_drag_null", NULL_WORLDS["cost_drag_null"]), ("zero_net_null", 0.0),
              ("structural_leak", NULL_WORLDS["structural_leak"])] + [(f"S={s}", s) for s in grid]
    implied_S = design.implied.get("sharpe_net")
    if implied_S is not None and math.isfinite(implied_S):
        worlds.append(("implied_by_primitives", float(implied_S)))
    rows = []
    for label, S in worlds:
        cur = G.joint_pass(S, ser, Yd, dev_gate, ser, Yv, val_gate, val_multiplier)
        pav = G.joint_pass(S, ser, Yd, dev_gate, ser, Yv, pav_gate, val_multiplier) if (pav_gate and Yv) else None
        rows.append({"world": label, "true_net_sharpe": S,
                     "single_test_all_years": float(single_test_power(S, ser, Yt, alpha)),
                     "p_dev": cur["p_dev"], "p_val_current": cur["p_val"], "p_joint_current": cur["p_joint"],
                     "p_val_proposed": pav["p_val"] if pav else None,
                     "p_joint_proposed": pav["p_joint"] if pav else None,
                     "natural_mean": nat(S)})

    # years for 80% power
    yrs = []
    for s in list(grid) + ([float(implied_S)] if implied_S is not None and implied_S > 0 else []):
        yrs.append({"true_net_sharpe": s,
                    "single_test": years_single_test(s, ser, alpha, power),
                    "dev_gate_only": G.years_single_gate(s, ser, dev_gate, power),
                    "joint_current": G.years_joint(s, ser, dev_gate, ser, val_gate, frac, power, val_multiplier),
                    "joint_proposed": G.years_joint(s, ser, dev_gate, ser, pav_gate, frac, power, val_multiplier)
                    if (pav_gate and Yv) else None})

    by = {r["world"]: r for r in rows}
    j07 = by["S=0.7"]["p_joint_current"] if "S=0.7" in by else G.joint_pass(0.7, ser, Yd, dev_gate, ser, Yv, val_gate)["p_joint"]
    fp = by["zero_net_null"]["p_joint_current"]
    v_cur = verdict(j07, fp)
    j07p = by["S=0.7"]["p_joint_proposed"] if "S=0.7" in by else None
    fpp = by["zero_net_null"]["p_joint_proposed"]
    v_pav = verdict(j07p, fpp) if j07p is not None else None

    # breadth / correlation tables with natural-unit MDEs
    rho_rows = []
    for r in design.rho_sensitivity:
        rr = dict(r)
        if "natural_slope" in rr:
            rr["mde_natural_single_test"] = rr["natural_slope"] * mde_single + design.natural_offset
        if rr.get("sharpe_net") is not None:
            rr["single_test_power_at_implied"] = float(single_test_power(rr["sharpe_net"], ser, Yt, alpha))
            rr["joint_current_at_implied"] = G.joint_pass(rr["sharpe_net"], ser, Yd, dev_gate, ser, Yv,
                                                          val_gate, val_multiplier)["p_joint"]
        rho_rows.append(rr)

    wc = None
    if dev_estimate is not None:
        corr = G.truncation_corrected_estimate(dev_estimate, ser, Yd, dev_gate)
        post = G.normal_prior_posterior(dev_estimate, ser, Yd)
        wc = {"dev_estimate": dev_estimate, "conditional_median_unbiased": corr,
              "normal_prior_posterior_mean_sd0.5": post}
        for lab, S in (("at_dev_estimate", dev_estimate), ("at_conditional_median_unbiased", corr),
                       ("at_posterior_mean", post)):
            if S is None:
                continue
            wc[lab] = {"p_val_current": float(val_gate.pass_prob(S, ser, Yv)) if (val_gate and Yv and val_gate.fraction_of_dev is None) else None,
                       "p_val_proposed": float(pav_gate.pass_prob(S, ser, Yv)) if (pav_gate and Yv) else None}

    return {
        "name": name or design.name, "design": design.kind, "inputs": design.inputs,
        "series_model": ser.to_dict(),
        "windows": {"dev_years": Yd, "val_years": Yv, "total_years": Yt, "dev_fraction_for_years_solver": frac,
                    "val_sharpe_multiplier": val_multiplier},
        "gates": {"dev": dev_gate.to_dict() | {"threshold": dev_gate.threshold(ser, Yd),
                                              "binding_leg": dev_gate.binding_leg(ser, Yd),
                                              "legs": dev_gate.legs(ser, Yd)},
                  "val_current": (val_gate.to_dict() | {"threshold": val_gate.threshold(ser, Yv),
                                                        "binding_leg": val_gate.binding_leg(ser, Yv),
                                                        "legs": val_gate.legs(ser, Yv)}) if (val_gate and Yv) else None,
                  "val_proposed": (pav_gate.to_dict() | {"threshold": pav_gate.threshold(ser, Yv),
                                                         "binding_leg": pav_gate.binding_leg(ser, Yv)})
                  if (pav_gate and Yv) else None,
                  **(gate_info or {})},
        "observations": obs, "standard_errors": se, "newey_west_check": nw, "mde": mde,
        "power": rows, "years_for_power": yrs, "implied": design.implied,
        "breadth_curve": design.breadth_curve, "correlation_sensitivity": rho_rows, "naive_independence": design.naive,
        "winners_curse": wc,
        "verdict": v_cur, "verdict_with_proposed_val_gate": v_pav, "verdict_rule": VERDICT_RULE,
        "joint_power_at_0.7": j07, "false_pass_zero_net": fp,
        "notes": design.notes,
    }


def text_table(rep: dict) -> str:
    """Short fixed-width summary for the terminal / .txt report."""
    L = []
    w = rep["windows"]
    L.append(f"{rep['name']}  [{rep['design']}]  dev {w['dev_years']:.2f}y"
             + (f" + val {w['val_years']:.2f}y" if w["val_years"] else " (single stage)"))
    o, s = rep["observations"], rep["standard_errors"]
    L.append(f"  raw obs (total) {o['raw_total']:.0f} {o['raw_unit']};  D_time {o['deff_time_D1']:.3f}  "
             f"deff_cross {o['deff_cross']:.3f}  ->  effective obs {o['n_eff_total']:.1f}")
    L.append(f"  SE(Sharpe) dev {s['se_sharpe_null_dev']:.3f}"
             + (f", val {s['se_sharpe_null_val']:.3f}" if s['se_sharpe_null_val'] else "")
             + f";  SE(mean, {s['natural_unit']}) total {s['se_mean_natural_total']:.4g}")
    g = rep["gates"]
    L.append(f"  dev gate threshold {g['dev']['threshold']:.3f} (binding: {g['dev']['binding_leg']})"
             + (f";  val threshold {g['val_current']['threshold']:.3f} (binding: {g['val_current']['binding_leg']})"
                if g.get("val_current") else "")
             + (f";  proposed val threshold {g['val_proposed']['threshold']:.3f}" if g.get("val_proposed") else ""))
    m = rep["mde"]

    def f(x):
        return "inf" if x is None or isinstance(x, str) or not math.isfinite(x) else f"{x:.2f}"

    L.append(f"  MDE Sharpe (80%): single test {f(m['single_test_all_years']['sharpe'])}, dev gate "
             f"{f(m['dev_gate_only']['sharpe'])}, joint current {f(m['joint_current_gates']['sharpe'])}, "
             f"joint proposed {f(m['joint_with_proposed_val_gate']['sharpe'])}")
    L.append("  world                     S     1-test   P(dev)  P(val)  JOINT   | val*   JOINT*")
    for r in rep["power"]:
        pv = "   -  " if r["p_val_current"] is None else f"{r['p_val_current']:.3f}"
        pp = "   -  " if r["p_val_proposed"] is None else f"{r['p_val_proposed']:.3f}"
        jp = "   -  " if r["p_joint_proposed"] is None else f"{r['p_joint_proposed']:.3f}"
        L.append(f"  {r['world']:<24}{r['true_net_sharpe']:6.2f}  {r['single_test_all_years']:.3f}   "
                 f"{r['p_dev']:.3f}   {pv}   {r['p_joint_current']:.3f}   | {pp}  {jp}")
    L.append("  years for 80% power:  S   single  dev-only  joint(current)  joint(proposed)")
    for y in rep["years_for_power"]:
        L.append(f"                    {y['true_net_sharpe']:5.2f}  {f(y['single_test']):>6}  "
                 f"{f(y['dev_gate_only']):>8}  {f(y['joint_current']):>14}  {f(y['joint_proposed']):>15}")
    L.append(f"  VERDICT (current gates): {rep['verdict']}   [joint@0.7 = {rep['joint_power_at_0.7']:.3f}, "
             f"false-pass = {rep['false_pass_zero_net']:.4f}]"
             + (f";  with proposed val gate: {rep['verdict_with_proposed_val_gate']}"
                if rep.get("verdict_with_proposed_val_gate") else ""))
    return "\n".join(L)
