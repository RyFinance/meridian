"""Simulated-futures lab: run every section and write reports/future_lab/.

Run: PYTHONPATH=. .venv/bin/python -m research.future_lab.run [--fast]

Seeded end to end (SEED below). Read-only on every input. It quantifies the uncertainty and path
risk of history already observed; it is not new evidence of an edge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from research.future_lab import engines as E
from research.future_lab import forward as F
from research.future_lab import ordering as O
from research.future_lab import paths as PA
from research.future_lab import risk as RK
from research.future_lab.data import CANDIDATES, LONG_CANDIDATES, ROOT, load_all

OUT = ROOT / "reports" / "future_lab"
SEED = 20260923
FROZEN_ON = "2026-09-23"
MAIN = ("pead_2x", "pead_2p5", "spmo_gld", "spy_gld", "spy")
MONITORED = ("pead_2x", "pead_2p5", "spmo_gld")
FORWARD_START = {"pead_2x": "2026-09-24", "pead_2p5": "2026-09-24", "spmo_gld": "2026-10-02",
                 "spy_gld": "2026-10-02", "spy": "2026-10-02"}
HAIRCUT = 0.5  # prior mean = 50% of the backtest estimate (selection / multiple-testing haircut)
METHOD_LABEL = {"stationary": "Stationary bootstrap", "circular": "Circular block", "regime_vol": "Regime (vol tercile)",
                "regime_dd": "Regime (drawdown)", "fhs_gjr_t": "FHS GJR-GARCH-t"}
COLORS = {"stationary": "#2a78d6", "circular": "#eb6834", "regime_vol": "#1baf7a", "regime_dd": "#eda100",
          "fhs_gjr_t": "#e87ba4"}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e1e0d9", "#fcfcfb"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def hist_stats(panel, cand) -> dict:
    r = panel.returns[cand["series"]]
    c = panel.returns[cand["control"]] if cand.get("control") else panel.rf
    rf = panel.rf
    x, xc, a = r - rf, c - rf, r - c
    n = len(r)
    sd = lambda s: float(s.std(ddof=1) * np.sqrt(252))
    return {"start": str(panel.dates[0].date()), "end": str(panel.dates[-1].date()), "days": n, "years": n / 252,
            "cagr": float((1 + r).prod() ** (252 / n) - 1),
            "control_cagr": float((1 + c).prod() ** (252 / n) - 1),
            "excess_sharpe": float(x.mean() / x.std(ddof=1) * np.sqrt(252)),
            "control_excess_sharpe": float(xc.mean() / xc.std(ddof=1) * np.sqrt(252)) if xc.std() > 0 else 0.0,
            "ann_excess_mean": float(x.mean() * 252), "ann_vol": sd(r),
            "control_ann_excess_mean": float(xc.mean() * 252), "control_ann_vol": sd(c),
            "corr_excess_with_control": float(x.corr(xc)) if xc.std() > 0 else 0.0,
            "active_ann": float(a.mean() * 252), "tracking_error": sd(a),
            "ir_vs_control": float(a.mean() / a.std(ddof=1) * np.sqrt(252)),
            "max_dd": float(PA.max_drawdown(np.cumprod(1 + r.to_numpy())[None])[0]),
            "annual_turnover": float(panel.turnover[cand["series"]].mean() * 252) if cand["series"] in panel.turnover else 0.0}


def credible_methods(meta: dict, panel, cand: dict) -> list[str]:
    """All bootstrap methods, plus FHS only when its fitted variance process reproduces the
    historical volatility of both the candidate and its control (see engines.FHS_MIN_PATH_VOL_RATIO)."""
    fits = meta[cand["panel"]]["method_info"]["fhs_gjr_t"]["fits"]
    cols = list(panel.returns.columns)
    need = [cand["series"]] + ([cand["control"]] if cand.get("control") else [])
    ok = all(fits[cols.index(c)]["credible"] for c in need)
    return [m for m in E.METHODS if m != "fhs_gjr_t" or ok]


def running_dd_sb(panel, col: str, n_paths: int, block: float, seed: int, chunk: int = 5000) -> np.ndarray:
    R = panel.returns[col].to_numpy()
    out = []
    for i in range(0, n_paths, chunk):
        idx = E.stationary_indices(len(R), min(chunk, n_paths - i), F.MAX_MONTHS * F.MONTH_DAYS, block, seed + i)
        out.append(RK.running_dd_by_month(R[idx]))
    return np.concatenate(out)


def oc_scenarios(panel, cand, hs) -> dict:
    """Daily mean shifts applied to the candidate for operating-characteristic simulations."""
    r = panel.returns[cand["series"]]
    ex_mean = float((r - panel.rf).mean())
    c = panel.returns[cand["control"]] if cand.get("control") else panel.rf
    sc = {"as_backtested": 0.0, "half_sharpe": -HAIRCUT * ex_mean, "zero_sharpe": -ex_mean}
    if cand.get("control"):
        sc["no_edge_vs_control"] = float(c.mean() - r.mean())
    return sc


def run_oc(panel, cand, params, rule, method, shifts: dict, n_paths, seed) -> dict:
    cols = [cand["series"]] + ([cand["control"]] if cand.get("control") else [])
    ret = panel.returns[cols].to_numpy()
    rf = panel.rf.to_numpy()
    labels = {k: panel.regimes[k].to_numpy() for k in ("vol_tercile", "dd_state")}
    blocks = E.panel_block_length(panel.returns.to_numpy())
    sim = E.simulate_panel(method, ret, rf, np.empty((len(rf), 0)), labels, blocks, n_paths,
                           F.MAX_MONTHS * F.MONTH_DAYS, seed)
    out = {}
    sd_ex = float((panel.returns[cand["series"]] - panel.rf).std(ddof=1))
    for name, s in shifts.items():
        R = sim["R"][0] + s
        C = sim["R"][1] if cand.get("control") else None
        rdd = RK.running_dd_by_month(R)
        dec = F.rule_decisions(R - sim["RF"], (R - C) if C is not None else None, rdd, rule, params)
        oc = F.summarize_oc(dec)
        hist_ex = float((panel.returns[cand["series"]] - panel.rf).mean()) + s
        out[name] = {"true_sharpe_hist_scale": hist_ex / sd_ex * np.sqrt(252), **oc}
    return out


def clean(o):
    """JSON-safe copy: non-finite floats become None (strict JSON has no Infinity/NaN)."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return float(o) if np.isfinite(o) else None
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def fmt_pct(x, d=0):
    return f"{x * 100:.{d}f}%"


def charts(kept: dict, params: dict, panels: dict, out: Path, cred: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.titlecolor": INK, "figure.facecolor": SURFACE,
                         "axes.facecolor": SURFACE, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
                         "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False})
    # --- fan charts
    fig, axes = plt.subplots(1, 5, figsize=(17, 4.2), sharey=False)
    months = np.arange(1, 61)
    for ax, c in zip(axes, MAIN):
        k = kept[c]
        sb = k["stationary"]["wealth_q"]
        ax.fill_between(months, sb[0], sb[4], color="#b7d3f6", lw=0, label="SB 5-95%")
        ax.fill_between(months, sb[1], sb[3], color="#6da7ec", lw=0, label="SB 25-75%")
        ax.plot(months, sb[2], color="#184f95", lw=2, label="SB median")
        for m in ("circular", "regime_vol", "regime_dd", "fhs_gjr_t"):
            if m in cred[c]:
                ax.plot(months, k[m]["wealth_q"][0], color=COLORS[m], lw=1.4, label=f"{METHOD_LABEL[m]} 5th pct")
        ax.axhline(1.0, color=INK2, lw=0.8)
        ax.set_title(CANDIDATES[c]["label"] + ("" if "fhs_gjr_t" in cred[c] else "\n(FHS omitted: not credible)"),
                     fontsize=10)
        ax.set_xlabel("months")
        ax.set_xticks([12, 24, 36, 48, 60])
    axes[0].set_ylabel("wealth (start = 1)")
    h, l = axes[2].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=7, fontsize=8, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Five-year wealth fans, stationary bootstrap, with each other method's 5th percentile "
                 "(resampled history, not a forecast)", color=INK, fontsize=11)
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(out / "fan_charts.png", dpi=150)
    plt.close(fig)
    # --- drawdown distributions + kill boundaries
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.4))
    grid = np.linspace(0, 0.6, 121)
    for ax, c in zip(axes.flat, MAIN):
        for m in E.METHODS:
            if m not in cred[c]:
                continue
            dd = -kept[c][m]["max_dd_5y"]
            ax.plot(grid * 100, [(dd > g).mean() for g in grid], color=COLORS[m], lw=2, label=METHOD_LABEL[m])
        for lvl in (20, 30):
            ax.axvline(lvl, color=INK2, lw=0.8)
        ax.set_title(CANDIDATES[c]["label"] + ("" if "fhs_gjr_t" in cred[c] else " (FHS omitted)"), fontsize=10)
        ax.set_xlabel("5-year max drawdown worse than (%)")
        ax.set_ylabel("probability")
        ax.set_ylim(0, 1)
    ax = axes.flat[5]
    for c, col in zip(MONITORED, ("#2a78d6", "#eb6834", "#1baf7a")):
        b = -np.asarray(params[c]["dd_boundary"]) * 100
        ax.plot(months, b, color=col, lw=2, label=CANDIDATES[c]["label"])
        ax.annotate(f"{b[-1]:.0f}%", (60, b[-1]), textcoords="offset points", xytext=(4, -3), fontsize=8, color=INK2)
    ax.set_title("Drawdown kill boundary (99th pct of resampled\nrunning max drawdown by elapsed month)", fontsize=10)
    ax.set_xlabel("months since forward start")
    ax.set_ylabel("drawdown that triggers a kill (%)")
    ax.invert_yaxis()
    ax.legend(fontsize=8, loc="lower left")
    h, l = axes.flat[2].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=5, fontsize=9, bbox_to_anchor=(0.5, 0.0))
    fig.suptitle("P(5-year max drawdown worse than x), by resampling method; vertical lines at 20% and 30%",
                 color=INK, fontsize=11)
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    fig.savefig(out / "drawdown_distributions.png", dpi=150)
    plt.close(fig)


def flat_tables(risk: dict, forward: dict, oc: dict, ordering: dict) -> dict[str, pd.DataFrame]:
    rows, lev, cost = [], [], []
    for c, by_m in risk.items():
        for m, r in by_m.items():
            for h, d in r["horizons"].items():
                rows.append({"candidate": c, "method": m, "horizon": h, "cagr_p05": d["cagr"]["p05"],
                             "cagr_p50": d["cagr"]["p50"], "cagr_p95": d["cagr"]["p95"],
                             "sharpe_p05": d["sharpe"]["p05"], "sharpe_p50": d["sharpe"]["p50"],
                             "sharpe_p95": d["sharpe"]["p95"], "max_dd_p50": d["max_dd"]["p50"],
                             "max_dd_p05": d["max_dd"]["p05"], "underwater_years_p50": d["underwater_years"]["p50"],
                             "underwater_years_p95": d["underwater_years"]["p95"],
                             "p_dd_gt_20": d["p_dd_gt_20"], "p_dd_gt_30": d["p_dd_gt_30"],
                             "p_under_control": d["p_under_control"]})
            for L, e in r["leverage"].items():
                for h, d in e.items():
                    lev.append({"candidate": c, "method": m, "leverage": L, "horizon": h, **d})
            for s, d in r["cost_shock"].items():
                cost.append({"candidate": c, "method": m, "shock": s, **d})
    fw = pd.DataFrame([{"candidate": c, **{k: v for k, v in d.items() if not isinstance(v, dict)}} for c, d in forward.items()])
    ocr = []
    for c, by_m in oc.items():
        for m, sc in by_m.items():
            for s, d in sc.items():
                for cp, v in d.items():
                    if isinstance(v, dict):
                        ocr.append({"candidate": c, "method": m, "scenario": s, "true_sharpe": d["true_sharpe_hist_scale"],
                                    "checkpoint": cp, **v})
    orr = []
    for c, d in ordering.items():
        p = d["regime_permutation"]
        orr.append({"candidate": c, "window": "regime_permutation", "max_dd_actual": p["max_dd"]["actual"],
                    "max_dd_p05": p["max_dd"]["p05"], "max_dd_p50": p["max_dd"]["p50"], "max_dd_p95": p["max_dd"]["p95"],
                    "cagr_first_3y_actual": p["cagr_first_3y"]["actual"], "cagr_first_3y_p05": p["cagr_first_3y"]["p05"],
                    "cagr_first_3y_p95": p["cagr_first_3y"]["p95"],
                    "terminal_max_abs_rel_deviation": p["terminal"]["max_abs_rel_deviation"]})
        for w, e in d["best_windows"].items():
            orr.append({"candidate": c, "window": w, "start": e["start"], "end": e["end"], "share_of_total": e["share_of_total"],
                        "cagr_full": e["full"]["cagr"], "cagr_removed": e["removed"]["cagr"],
                        "sharpe_full": e["full"]["excess_sharpe"], "sharpe_removed": e["removed"]["excess_sharpe"],
                        "active_full": e["full"]["active_ann"], "active_removed": e["removed"]["active_ann"],
                        "ir_full": e["full"]["ir_vs_control"], "ir_removed": e["removed"]["ir_vs_control"],
                        "p_boot_drop_ge_observed": e["p_boot_drop_ge_observed"],
                        "relocated_max_dd_worst": e["relocated"]["max_dd"]["p00"],
                        "relocated_max_dd_best": e["relocated"]["max_dd"]["p100"],
                        "relocated_rule_kill_share": e["relocated"]["rule_kill_share"]})
    return {"path_risk": pd.DataFrame(rows), "leverage_ruin": pd.DataFrame(lev), "cost_shocks": pd.DataFrame(cost),
            "forward_design": fw, "oc_table": pd.DataFrame(ocr), "ordering_summary": pd.DataFrame(orr)}


def main(fast: bool = False) -> dict:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    n_paths, n_bound, n_oc, n_perm, n_boot = (800, 2000, 600, 300, 300) if fast else (5000, 20000, 4000, 2000, 2000)
    panels = load_all()
    groups = [("pead", {k: v for k, v in CANDIDATES.items() if v["panel"] == "pead"}),
              ("gold", {k: v for k, v in CANDIDATES.items() if v["panel"] == "gold"}),
              ("long", LONG_CANDIDATES)]
    risk, meta, kept = {}, {}, {}
    for gi, (pname, cands) in enumerate(groups):
        res, m, kp = RK.run_panel(panels[pname], cands, E.METHODS, n_paths, max(RK.HORIZONS.values()),
                                  SEED + 100 * gi, keep_paths_for=tuple(cands))
        risk.update(res)
        kept.update(kp)
        meta[pname] = m
        print(f"[{time.time() - t0:6.0f}s] path risk done: {pname}", flush=True)

    # ---------------- section 4: forward design parameters
    rule = json.loads(json.dumps(F.DEFAULT_RULE))
    params, forward, oc = {}, {}, {}
    for ci, c in enumerate(MAIN):
        cand = CANDIDATES[c]
        panel = panels[cand["panel"]]
        hs = hist_stats(panel, cand)
        cred = credible_methods(meta, panel, cand)
        k_sr = {m: risk[c][m]["horizons"]["5y"]["sd_sharpe"] * np.sqrt(5) for m in cred}
        k_ir = {m: risk[c][m]["horizons"]["5y"]["sd_ir_vs_control"] * np.sqrt(5) for m in cred}
        ksr, kir = k_sr["stationary"], k_ir["stationary"]
        se_hist_sr, se_hist_ir = ksr / np.sqrt(hs["years"]), kir / np.sqrt(hs["years"])
        rdd = running_dd_sb(panel, cand["series"], n_bound, meta[cand["panel"]]["block_length"]["sb"], SEED + 7000 + ci)
        bound = F.dd_boundary(rdd, rule["kill_drawdown"]["percentile"])
        false_alarm = {"stationary_calibration_paths": F.boundary_false_alarm(rdd, bound)}
        for m in E.METHODS:
            false_alarm[m] = F.boundary_false_alarm(kept[c][m]["running_dd_month"].astype(float), bound)
        params[c] = {"prior_sharpe_mean": HAIRCUT * hs["excess_sharpe"], "prior_sharpe_sd": se_hist_sr, "k_sharpe": ksr,
                     "prior_ir_mean": HAIRCUT * hs["ir_vs_control"], "prior_ir_sd": se_hist_ir, "k_ir": kir,
                     "skeptical_sharpe_sd": F.sceptical_sd(hs["excess_sharpe"]),
                     "skeptical_ir_sd": F.sceptical_sd(hs["ir_vs_control"]),
                     "dd_boundary": [float(x) for x in bound]}
        z = F.Z_ALPHA + F.Z_BETA
        fw = {"label": cand["label"], "control": cand.get("control") or "T-bills", "credible_methods": cred,
              "sharpe_hat": hs["excess_sharpe"], "ir_hat": hs["ir_vs_control"],
              "corr_with_control": hs["corr_excess_with_control"], "tracking_error": hs["tracking_error"],
              "ir_from_formula": F.paired_ir(hs["ann_excess_mean"], hs["control_ann_excess_mean"], hs["ann_vol"],
                                             hs["control_ann_vol"], hs["corr_excess_with_control"]) if cand.get("control") else hs["excess_sharpe"],
              "k_sharpe": ksr, "k_ir": kir, "k_sharpe_min": min(k_sr.values()), "k_sharpe_max": max(k_sr.values()),
              "k_ir_min": min(k_ir.values()), "k_ir_max": max(k_ir.values()),
              "backtest_years": hs["years"], "se_sharpe_backtest": se_hist_sr, "se_ir_backtest": se_hist_ir,
              "months_vs_zero_at_hat": 12 * F.years_needed(hs["excess_sharpe"], ksr),
              "months_vs_zero_at_half": 12 * F.years_needed(HAIRCUT * hs["excess_sharpe"], ksr),
              "months_vs_zero_iid_at_hat": 12 * F.years_needed(hs["excess_sharpe"], 1.0),
              "months_vs_zero_at_hat_method_range": [12 * F.years_needed(hs["excess_sharpe"], min(k_sr.values())),
                                                     12 * F.years_needed(hs["excess_sharpe"], max(k_sr.values()))],
              "months_vs_control_at_hat": 12 * F.years_needed(hs["ir_vs_control"], kir),
              "months_vs_control_at_half": 12 * F.years_needed(HAIRCUT * hs["ir_vs_control"], kir),
              "months_vs_control_at_hat_method_range": [12 * F.years_needed(hs["ir_vs_control"], min(k_ir.values())),
                                                        12 * F.years_needed(hs["ir_vs_control"], max(k_ir.values()))],
              "assurance_vs_zero_36m": F.assurance(3, hs["excess_sharpe"], se_hist_sr, ksr),
              "assurance_vs_zero_36m_haircut": F.assurance(3, HAIRCUT * hs["excess_sharpe"], se_hist_sr, ksr),
              "assurance_vs_control_36m": F.assurance(3, hs["ir_vs_control"], se_hist_ir, kir),
              "power_vs_zero_36m_at_hat": F.power_at(3, hs["excess_sharpe"], ksr),
              "dd_boundary_12m": float(bound[11]), "dd_boundary_36m": float(bound[35]), "dd_boundary_60m": float(bound[59]),
              "dd_false_alarm": false_alarm, "k_sharpe_by_method": k_sr, "k_ir_by_method": k_ir, "hist": hs, "z_sum": z}
        forward[c] = fw
        shifts = oc_scenarios(panel, cand, hs)
        oc[c] = {"stationary": run_oc(panel, cand, params[c], rule, "stationary", shifts, n_oc, SEED + 8000 + ci)}
        keep_sc = {k: v for k, v in shifts.items() if k in ("as_backtested", "no_edge_vs_control", "zero_sharpe")}
        for mi, m in enumerate(E.METHODS[1:]):
            oc[c][m] = run_oc(panel, cand, params[c], rule, m, keep_sc, n_oc, SEED + 8100 + 10 * ci + mi)
        print(f"[{time.time() - t0:6.0f}s] forward design done: {c}", flush=True)

    # ---------------- section 3: ordering
    ordering = {}
    for ci, c in enumerate(MAIN):
        cand = CANDIDATES[c]
        panel = panels[cand["panel"]]
        ordering[c] = O.run_candidate(panel, cand, rule, params[c], n_perm, n_boot, SEED + 9000 + ci,
                                      meta[cand["panel"]]["block_length"]["sb"])
        print(f"[{time.time() - t0:6.0f}s] ordering done: {c}", flush=True)

    # ---------------- outputs
    cred_all = {c: credible_methods(meta, panels[CANDIDATES[c]["panel"]], CANDIDATES[c]) for c in MAIN}
    charts(kept, params, panels, OUT, cred_all)
    tables = flat_tables(risk, forward, oc, ordering)
    for name, df in tables.items():
        df.to_csv(OUT / f"{name}.csv", index=False)
    spec = build_spec(rule, params, forward, oc)
    (OUT / "monitoring_rule_spec.json").write_text(json.dumps(clean(spec), indent=1, allow_nan=False))
    code_files = sorted((ROOT / "research" / "future_lab").glob("*.py"))
    inputs = [ROOT / "reports/pead_audit/wide_5p0_curves.csv", ROOT / "reports/pead_audit/wide_2p5_curves.csv",
              ROOT / "live_backtest/state/sweep_wide_5p0_ledger.jsonl", ROOT / "live_backtest/state/sweep_wide_2p5_ledger.jsonl",
              ROOT / "reports/momentum_gold_audit_20260921/momentum_gold_full.csv",
              ROOT / "reports/momentum_gold_audit_20260921/market_gold_full.csv",
              ROOT / "data/multiasset/etf/SPY.parquet", ROOT / "data/multiasset/etf/GLD.parquet",
              ROOT / "data/multiasset/rates/IRX.parquet"]
    manifest = {"seed": SEED, "fast": fast, "n_paths": n_paths, "n_boundary_paths": n_bound, "n_oc_paths": n_oc,
                "n_permutations": n_perm, "n_order_bootstrap": n_boot, "horizon_days": max(RK.HORIZONS.values()),
                "runtime_seconds": round(time.time() - t0, 1),
                "code_sha256": {str(p.relative_to(ROOT)): sha(p) for p in code_files},
                "input_sha256": {str(p.relative_to(ROOT)): sha(p) for p in inputs},
                "spec_sha256": spec["sha256"]}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    results = {"meta": {pn: {"block_length": {"sb": m["block_length"]["sb"], "cb": m["block_length"]["cb"],
                                              "per_column": m["block_length"]["per_column"]},
                             "method_info": m["method_info"]} for pn, m in meta.items()},
               "regime_thresholds_spy_vol63": panels["gold"].regimes.attrs.get("vol_thresholds"),
               "risk": risk, "forward": forward, "oc": oc, "ordering": ordering, "params": params,
               "panel_dates": {k: [str(p.dates[0].date()), str(p.dates[-1].date()), len(p.dates)] for k, p in panels.items()}}
    (OUT / "results.json").write_text(json.dumps(clean(results), indent=1, allow_nan=False))
    print(f"[{time.time() - t0:6.0f}s] done", flush=True)
    return results


def build_spec(rule: dict, params: dict, forward: dict, oc: dict) -> dict:
    series_def = {
        "pead_2x": "Daily net total return of the PEAD bot's marked NAV at 2x sizing (5% positions), accounted as in "
                   "research/pead_audit/mtm_audit.py: every open position marked to the close daily, 10 bps round trip, "
                   "idle cash earning T-bills. Only genuinely forward events count (no backfilled ledger events).",
        "pead_2p5": "As pead_2x but at the live 2.5% position size.",
        "spmo_gld": "Daily net total return of momentum_gold_v1 (reports/momentum_gold_20260919/forward_paper_spec.json): "
                    "50% SPMO / 50% GLD, first-session-close decision, next-open fills, 5 bps per side.",
        "spy_gld": "Reference only: 50% SPY / 50% GLD with the same rebalancing and cost rules as spmo_gld.",
        "spy": "Reference only: SPY adjusted total return, buy and hold.",
    }
    control_def = {
        "pead_2x": "Same forward trades (dates, direction, notional) placed in the equal-weight average of the trading "
                   "universe (research/pead_audit/mtm_audit.mtm_book with substitute=universe index); the SPY-substitute "
                   "control is reported alongside but not used for decisions.",
        "pead_2p5": "As pead_2x control, for the 2.5% book.",
        "spmo_gld": "50% SPY / 50% GLD, same decision, fill and cost rules (the frozen benchmark in the paper spec).",
        "spy_gld": "SPY adjusted total return.",
        "spy": "T-bills (no active comparison).",
    }
    rf_def = {"pead_2x": "Fama-French daily risk-free rate (as in mtm_audit)", "pead_2p5": "Fama-French daily risk-free rate",
              "spmo_gld": "research.return_search.run.cash_rates (13-week T-bill, IRX, lagged one day)",
              "spy_gld": "research.return_search.run.cash_rates", "spy": "research.return_search.run.cash_rates"}
    cands = {}
    for c, p in params.items():
        fw = forward[c]
        o = oc[c]["stationary"]
        cands[c] = {
            "candidate": c, "role": "candidate" if c in MONITORED else "reference",
            "series": series_def[c], "control": CANDIDATES[c].get("control"), "control_definition": control_def[c],
            "risk_free": rf_def[c], "forward_start": FORWARD_START[c],
            "parameters": {k: (float(v) if not isinstance(v, list) else v) for k, v in p.items()},
            "backtest_reference": {"sharpe_hat": fw["sharpe_hat"], "ir_hat": fw["ir_hat"], "years": fw["backtest_years"],
                                   "window": [fw["hist"]["start"], fw["hist"]["end"]],
                                   "annual_turnover": fw["hist"]["annual_turnover"]},
            "operating_characteristics_stationary_bootstrap": o,
            "implementation_checks": [
                "REVIEW if trailing 3-month realised cost per side exceeds the backtest assumption by more than 25 bps "
                "(the largest cost shock simulated in reports/future_lab).",
                "REVIEW if annualised forward turnover is outside 0.5x-1.5x of backtest_reference.annual_turnover "
                "after 6 months.",
                "REVIEW if any signal-day fill is missing or a position is carried at cost instead of marked.",
            ],
        }
    body = {
        "spec_version": "future_lab.monitoring.v1",
        "frozen_on": FROZEN_ON,
        "status": "PROPOSED. It becomes pre-specified only once its sha256 is registered in research/preregistrations.jsonl "
                  "before each candidate's forward_start. Parameters must not be re-estimated on forward data.",
        "not_evidence": "Priors, SE inflation and drawdown boundaries are estimated from already-observed history. "
                        "The rule tests whether forward data is consistent with that history; it cannot anticipate "
                        "regimes absent from it.",
        "evaluator": "research.future_lab.forward.evaluate_from_spec('reports/future_lab/monitoring_rule_spec.json', "
                     "name, daily_df) (verifies this sha256, then applies the rule mechanically)",
        "inputs": {"daily_df_columns": {"ret": "candidate daily net total return", "rf": "daily T-bill return",
                                        "control_ret": "control daily net total return (omit for spy)"}},
        "rule": rule,
        "rule_text": [
            "Looks: at each calendar month-end close, once >= 21 forward trading days exist. months_elapsed = "
            "round(trading_days / 21).",
            "Statistics: annualised Sharpe of daily excess returns (ret - rf) since forward_start; annualised IR of "
            "daily active returns (ret - control_ret); running max drawdown of the candidate NAV since forward_start.",
            "Posterior: Normal prior N(m, s^2) on the true annualised Sharpe (or IR); the forward estimate is treated "
            "as N(true, k^2 / years). posterior precision = 1/s^2 + years/k^2; posterior mean = (m/s^2 + "
            "estimate*years/k^2) / precision.",
            "Futility prior (kill / revert): m = prior_sharpe_mean (= 0.5 x backtest Sharpe), s = prior_sharpe_sd "
            "(= resampled SE of the backtest Sharpe); likewise prior_ir_mean / prior_ir_sd for the IR.",
            "Promotion prior (sceptical): m = 0, s = skeptical_sharpe_sd (= backtest Sharpe / 1.645) and "
            "skeptical_ir_sd; only forward data can carry a promotion.",
            "KILL_DRAWDOWN (checked first, any look): running max drawdown deeper than dd_boundary[months_elapsed-1].",
            "KILL_SHARPE (months_elapsed >= 6): futility-prior posterior P(Sharpe > 0.30) < 0.10.",
            "REVERT_TO_CONTROL (months_elapsed >= 24): futility-prior posterior P(IR vs control > 0) < 0.10 -> hold "
            "the control instead.",
            "PROMOTE (months_elapsed >= 24): sceptical-prior posterior P(Sharpe > 0) >= 0.95 AND sceptical-prior "
            "posterior P(IR > 0) >= 0.90 AND no open implementation REVIEW. Promotion means eligibility for sizing "
            "beyond paper/small size, not certainty.",
            "Decisions are terminal. At 60 months with no decision: END_NO_DECISION (the candidate stays a benchmark).",
        ],
        "candidates": cands,
    }
    body = clean(body)
    body["sha256"] = F.canonical_hash(body)
    return body


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    main(ap.parse_args().fast)
