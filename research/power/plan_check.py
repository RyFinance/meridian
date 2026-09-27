"""research.power.plan_check -- registration-time power check (Protocol Amendment 2, N5 power disclosure).

    PYTHONPATH=. .venv/bin/python -m research.power.plan_check research/power/examples/<spec>.json [--out reports/power]
                                                                [--mc 2000] [--strict]

Reads a JSON design spec (schema: research/power/design_schema.json), writes reports/power/<name>.json and
reports/power/<name>.txt, prints the text table, and returns a verdict:
  DECISIVE   joint dev+validation power at true net Sharpe 0.7 >= 50% and P(pass both | S=0) <= 5%
  MARGINAL   joint power at 0.7 in [25%, 50%) (or false-pass in (5%, 10%])
  INCAPABLE  joint power at 0.7 < 25%, or false-pass > 10%
--strict sets the exit code (0 DECISIVE / 1 MARGINAL / 2 INCAPABLE). --mc N adds a Monte Carlo check of the
two-stage numbers (reduced series model, literal gate legs).
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import pathlib
import sys

from research.power import designs as DS
from research.power import gates as G
from research.power import report as R
from research.power.core import SHARPE_GRID, Autocorr, SeriesModel, batch_alpha, single_test_power, years_single_test

SCHEMA = pathlib.Path(__file__).with_name("design_schema.json")


def validate(spec: dict) -> None:
    try:
        import jsonschema
    except ImportError:  # pragma: no cover
        return
    jsonschema.validate(spec, json.loads(SCHEMA.read_text()))


def _deep_update(d: dict, u: dict) -> dict:
    out = copy.deepcopy(d)
    for k, v in u.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_update(out[k], v)
        else:
            out[k] = v
    return out


def _clean(x):
    if isinstance(x, float):
        return None if (math.isnan(x)) else (x if math.isfinite(x) else ("inf" if x > 0 else "-inf"))
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if hasattr(x, "item"):
        return _clean(x.item())
    return x


def _alpha(spec, k):
    a = spec.get("power", {}).get("alpha", "auto")
    return batch_alpha(k) if a == "auto" else float(a)


# ---------------------------------------------------------------------------------------------- standard designs
def run_spec(spec: dict, mc_paths: int = 0) -> dict:
    validate(spec)
    if spec["design"] == "sleeve_screen":
        return run_sleeve_screen(spec)
    d = DS.build(spec["design"], spec["params"], spec["name"])
    g = spec.get("gates", {})
    dg, vg, pg, info = R.gates_from_spec(g, d)
    w = spec["windows"]
    pw = spec.get("power", {})
    rep = R.evaluate(d, dev_years=w["dev_years"], val_years=w.get("val_years"), dev_gate=dg, val_gate=vg,
                     pav_gate=pg, alpha=_alpha(spec, info["batch_k"]), power=pw.get("power", 0.8),
                     grid=tuple(pw.get("sharpe_grid", SHARPE_GRID)), val_multiplier=pw.get("val_multiplier", 1.0),
                     dev_estimate=pw.get("dev_estimate"), name=spec["name"], gate_info=info)
    rep["description"] = spec.get("description", "")
    rep["assumptions"] = spec.get("assumptions", [])
    rep["scenarios"] = [scenario(spec, sc, info) for sc in spec.get("scenarios", [])]
    if mc_paths:
        rep["mc_check"] = mc_check(d.series, w, dg, vg, pg, mc_paths)
    return _clean(rep)


def scenario(spec: dict, sc: dict, info: dict) -> dict:
    """One sensitivity row: override params, report implied net Sharpe and what it buys."""
    params = _deep_update(spec["params"], sc.get("params", {}))
    d = DS.build(spec["design"], params, spec["name"])
    g = _deep_update(spec.get("gates", {}), sc.get("gates", {}))
    dg, vg, pg, _ = R.gates_from_spec(g, d)
    w = _deep_update(spec["windows"], sc.get("windows", {}))
    Yd, Yv = w["dev_years"], w.get("val_years")
    Yt = Yd + (Yv or 0)
    S = d.implied.get("sharpe_net")
    a = _alpha(spec, info["batch_k"])
    row = {"label": sc.get("label", json.dumps(sc.get("params", {}))), "overrides": sc,
           "n_eff_units": d.n_eff_units, "deff_cross": d.deff_cross, "implied_sharpe_net": S,
           "implied_sharpe_gross": d.implied.get("sharpe_gross", d.implied.get("sharpe_gross_linear_book")),
           "turnover": d.implied.get("turnover_one_way_per_leg"), "cost_drag_sharpe": d.implied.get("cost_drag_sharpe")}
    mde1 = G.solve_mde(lambda s: single_test_power(s, d.series, Yt, a))
    row["mde_sharpe_single_test"] = mde1
    row["mde_natural_single_test"] = d.natural_from_sharpe(mde1)
    mdej = G.mde_joint(d.series, Yd, dg, d.series, Yv, pg if Yv else None)
    row["mde_sharpe_joint_proposed"] = mdej
    row["mde_natural_joint_proposed"] = d.natural_from_sharpe(mdej) if math.isfinite(mdej) else None
    if S is not None:
        row["single_test_power_at_implied"] = float(single_test_power(S, d.series, Yt, a))
        row["joint_current_at_implied"] = G.joint_pass(S, d.series, Yd, dg, d.series, Yv, vg)["p_joint"]
        row["joint_proposed_at_implied"] = G.joint_pass(S, d.series, Yd, dg, d.series, Yv, pg if Yv else None)["p_joint"]
        row["years_80_single_test_at_implied"] = years_single_test(S, d.series, a) if S > 0 else math.inf
        row["years_80_joint_proposed_at_implied"] = G.years_joint(S, d.series, dg, d.series, pg if Yv else None,
                                                                  Yd / Yt) if S > 0 else math.inf
        row["years_80_joint_current_at_implied"] = G.years_joint(S, d.series, dg, d.series, vg, Yd / Yt) if S > 0 else math.inf
    row["joint_current_at_0.7"] = G.joint_pass(0.7, d.series, Yd, dg, d.series, Yv, vg)["p_joint"]
    row["verdict_current"] = R.verdict(row["joint_current_at_0.7"], G.joint_pass(0.0, d.series, Yd, dg, d.series, Yv, vg)["p_joint"])
    return row


def mc_check(ser: SeriesModel, w: dict, dg, vg, pg, n_paths: int) -> list[dict]:
    from research.power import simulate as M
    if ser.autocorr.model not in ("ar1", "overlap", "ar1_overlap", "lrv"):
        return []
    ser_mc = SeriesModel(ser.periods_per_year, ser.autocorr, 0.0, 0.0, None, ser.null_D)
    out = []
    for S in (0.0, 0.5, 0.7, 1.0):
        for lab, v in (("current", vg), ("proposed", pg)):
            if v is None and lab == "proposed":
                continue
            an = G.joint_pass(S, ser_mc, w["dev_years"], dg, ser_mc, w.get("val_years"), v)["p_joint"]
            mc = M.mc_two_stage(ser_mc, S, w["dev_years"], w.get("val_years") or 0, dg, v, n_paths=n_paths,
                                seed_salt=("plan_check", lab), ideal_null=True)
            out.append({"S": S, "val_gate": lab, "analytic_joint": an, "mc_joint": mc["p_joint"],
                        "mc_se": mc["mc_se_joint"]})
    return out


# ---------------------------------------------------------------------------------------------- sleeve screen
def run_sleeve_screen(spec: dict) -> dict:
    p = spec["params"]
    ac = Autocorr.from_spec(p["autocorr"])
    ser = SeriesModel(p["periods_per_year"], ac)
    w = spec["windows"]
    grid = spec.get("power", {}).get("sharpe_grid", list(SHARPE_GRID))
    m, rho = int(p["m_real"]), float(p["rho"])
    factor = math.sqrt(m * (1 + (m - 1) * rho)) / m if m else 0.0   # per-sleeve s giving an ideal-book Sharpe of 1
    rows = []
    for S in [0.0] + list(grid):
        s = S * factor
        mm = m if S > 0 else 0
        r = G.sleeve_screen_power(s, k=p["k"], m_real=mm, rho=rho, incl_sharpe=p["incl_sharpe"],
                                  dev_years=w["dev_years"], hold_years=w["val_years"], sleeve_series=ser,
                                  hold_t=p.get("hold_t", 2.0))
        rows.append({"ideal_book_sharpe": S, "per_sleeve_sharpe": s, **r})
    fp = rows[0]["p_joint"]
    j07 = next(r["p_joint"] for r in rows if abs(r["ideal_book_sharpe"] - 0.7) < 1e-9)
    return _clean({"name": spec["name"], "design": "sleeve_screen", "inputs": p, "windows": w,
                   "description": spec.get("description", ""), "assumptions": spec.get("assumptions", []),
                   "power": rows, "joint_power_at_0.7": j07, "false_pass_zero_net": fp,
                   "verdict": R.verdict(j07, fp), "verdict_rule": R.VERDICT_RULE,
                   "notes": ["grid = Sharpe of the ideal book (all m_real real sleeves, no nulls); the screen "
                             "dilutes it with noise sleeves (P(include | null) above)"]})


def text(rep: dict) -> str:
    if rep["design"] == "sleeve_screen":
        L = [f"{rep['name']} [sleeve_screen] k={rep['inputs']['k']} m_real={rep['inputs']['m_real']}"]
        L.append("  ideal-book S  per-sleeve s  P(incl|real)  P(incl|null)  E[#null incl]  JOINT")
        for r in rep["power"]:
            L.append(f"  {r['ideal_book_sharpe']:12.2f} {r['per_sleeve_sharpe']:13.3f} {r['p_include_real']:13.3f}"
                     f" {r['p_include_null']:13.3f} {r['expected_null_included']:14.2f}  {r['p_joint']:.3f}")
        L.append(f"  VERDICT: {rep['verdict']}  [joint@0.7 = {rep['joint_power_at_0.7']:.3f}, false-pass = "
                 f"{rep['false_pass_zero_net']:.4f}]")
        return "\n".join(L)
    s = R.text_table(rep)
    if rep.get("scenarios"):
        s += "\n  scenarios: label | n_eff | implied net S | joint(cur) | joint(prop) | yrs80 single | yrs80 joint(prop) | MDE natural (joint prop)"
        f = lambda x: "inf" if x in (None, "inf") or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.3g}"
        for r in rep["scenarios"]:
            s += (f"\n   {r['label'][:44]:<44} {f(r['n_eff_units'])} | {f(r['implied_sharpe_net'])} | "
                  f"{f(r.get('joint_current_at_implied'))} | {f(r.get('joint_proposed_at_implied'))} | "
                  f"{f(r.get('years_80_single_test_at_implied'))} | {f(r.get('years_80_joint_proposed_at_implied'))} | "
                  f"{f(r.get('mde_natural_joint_proposed'))}")
    if rep.get("mc_check"):
        s += "\n  MC check (joint): " + "; ".join(f"S={r['S']} {r['val_gate']}: {r['analytic_joint']:.3f} vs "
                                                 f"{r['mc_joint']:.3f}" for r in rep["mc_check"])
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="+")
    ap.add_argument("--out", default="reports/power")
    ap.add_argument("--mc", type=int, default=0)
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv)
    worst = 0
    for path in a.spec:
        spec = json.loads(pathlib.Path(path).read_text())
        rep = run_spec(spec, a.mc)
        out = pathlib.Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{spec['name']}.json").write_text(json.dumps(rep, indent=1))
        t = text(rep)
        (out / f"{spec['name']}.txt").write_text(t + "\n")
        print(t)
        print()
        worst = max(worst, {"DECISIVE": 0, "MARGINAL": 1, "INCAPABLE": 2}[rep["verdict"]])
    return worst if a.strict else 0


if __name__ == "__main__":
    sys.exit(main())
