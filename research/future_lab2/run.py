"""Alternate-futures lab v2 (Workstream C4): run every section and write reports/future_lab2/.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.future_lab2.run [--fast]

Seeded end to end (SEED below, the project's fixed seed). Read-only on every existing input;
writes only under reports/future_lab2/. Imports research.future_lab (engines, forward, paths, risk)
but does not edit anything under research/future_lab/ or reports/future_lab/.

This quantifies, for six explicit and hand-specified forward worlds (not resamples of observed
history alone), how long until forward data could confirm or kill tsy_month_end_v1 and
momentum_gold_v1 under a simple, pre-declared sequential rule. It is not new evidence of an edge,
and it cannot anticipate a regime, shock or structural break absent from the historical samples the
worlds are built from (2003-2026 for TLT, 2017-2026 for SPMO/GLD).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from research.future_lab import forward as F
from research.future_lab2 import gold_world as G
from research.future_lab2 import rule as RU
from research.future_lab2 import tsy_world as T

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "future_lab2"
SEED = 20260924
CHECKPOINTS = (12, 24, 36, 60, 120)
MONTH_DAYS = 21
HORIZON_MONTHS = 120
MONITORING_SPEC = ROOT / "reports" / "future_lab" / "monitoring_rule_spec.json"
TSY_SPEC = ROOT / "research" / "forward_audit" / "tsy_month_end_v1_spec.json"
WORLD_SEED = {"W0": 0, "W1": 1, "W2": 2, "W3": 3, "W4": 4, "W5": 5}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return float(o) if np.isfinite(o) else None
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def month_key(days: int) -> str:
    return f"{days // MONTH_DAYS}m"


# ---------------------------------------------------------------- tsy_month_end_v1
def run_tsy(n_paths: int) -> dict:
    pl = T.pools()
    blocks = T.block_lengths(pl)
    means = T.world_means(pl)
    sigma = float(pl["all"].std(ddof=1))
    mu0, mu2, mu1 = means["mu0_null_net"], means["mu_post_net"], means["mu_pre_net"]

    dist, sprt_oc = {}, {}
    for w in T.WORLDS:
        X = T.simulate(w, n_paths, HORIZON_MONTHS, SEED + WORLD_SEED[w], pl, blocks)
        dist[w] = RU.dist_tstat_sharpe(X, ann_factor=12, checkpoints=CHECKPOINTS)
        sres = RU.sprt_run(X, mu0=mu0, mu1=mu2, sigma=sigma, alpha=0.05, beta=0.2)
        summ = RU.sprt_summary(sres, CHECKPOINTS)
        summ.update(world=w, label=T.WORLD_LABEL[w], ground_truth_has_edge=T.WORLD_HAS_EDGE[w],
                   world_mean_net=float(X.mean()), world_sd_net=float(X.std(ddof=1)))
        sprt_oc[w] = summ

    power = {"sigma": sigma, "mu0_null_net": mu0, "mu_pre_net": mu1, "mu_post_net": mu2,
            "months_needed_80pow_W0_vs_W1": RU.fixed_sample_months_needed(mu1 - mu0, sigma),
            "months_needed_80pow_W0_vs_W2": RU.fixed_sample_months_needed(mu2 - mu0, sigma)}
    for cp in CHECKPOINTS:
        power[f"power_at_{cp}m_W0_vs_W1"] = RU.fixed_sample_power(cp, mu1 - mu0, sigma)
        power[f"power_at_{cp}m_W0_vs_W2"] = RU.fixed_sample_power(cp, mu2 - mu0, sigma)
    n_check = int(np.ceil(power["months_needed_80pow_W0_vs_W2"]))
    if np.isfinite(n_check) and 0 < n_check <= 20_000:
        # Monte Carlo check of the analytic z-test power: same test the formula assumes (KNOWN,
        # pre-declared sigma in the denominator, not each path's own estimated std -- that would be
        # a different, lower-powered t-test).
        Xc = T.simulate("W2", min(n_paths, 4000), n_check, SEED + 555, pl, blocks)
        z = (Xc.mean(axis=1) - mu0) * np.sqrt(n_check) / sigma  # test statistic for H0: mean = mu0
        power["power_check_mc_at_months_needed_W0_vs_W2"] = float((z > RU.Z_ALPHA).mean())
        power["months_needed_mc_n"] = n_check

    return {"pools_n": {k: int(len(v)) for k, v in pl.items()}, "block_lengths": blocks,
            "world_means": means, "sigma": sigma, "dist": dist, "sprt": sprt_oc, "power": power,
            "frozen_rule": "not applicable: reports/future_lab/monitoring_rule_spec.json has no "
                          "tsy_month_end_v1 candidate entry (only pead_2x, pead_2p5, spmo_gld, "
                          "spy_gld, spy). The proposed SPRT (proposed_forward_rule_tsy_month_end_v1.json) "
                          "is the pre-declared rule for this candidate."}


# ---------------------------------------------------------------- momentum_gold_v1
def gold_monthly_active(Rr: np.ndarray, Cc: np.ndarray) -> np.ndarray:
    n_paths, H = Rr.shape
    m = H // MONTH_DAYS
    act = Rr[:, : m * MONTH_DAYS] - Cc[:, : m * MONTH_DAYS]
    return act.reshape(n_paths, m, MONTH_DAYS).sum(axis=2)


def run_gold(n_paths: int) -> dict:
    pl = G.pools()
    blocks = G.block_lengths(pl)
    horizon_days = HORIZON_MONTHS * MONTH_DAYS

    spec = json.loads(MONITORING_SPEC.read_text())
    if not F.verify_spec(spec):
        raise ValueError("reports/future_lab/monitoring_rule_spec.json hash mismatch: edited after freezing")
    frozen_cand = spec["candidates"]["spmo_gld"]
    frozen_params = frozen_cand["parameters"]
    frozen_rule = spec["rule"]

    hist, later, earlier = pl["all"], pl["later"], pl["earlier"]
    hist_active_m = (hist["strat"] - hist["ctrl"]).groupby(hist.index.to_period("M")).sum().to_numpy()
    later_active_m = (later["strat"] - later["ctrl"]).groupby(later.index.to_period("M")).sum().to_numpy()
    earlier_active_m = (earlier["strat"] - earlier["ctrl"]).groupby(earlier.index.to_period("M")).sum().to_numpy()
    sigma = float(hist_active_m.std(ddof=1))
    mu0, mu2, mu1 = 0.0, float(later_active_m.mean()), float(earlier_active_m.mean())

    dist, sprt_oc, frozen_oc = {}, {}, {}
    for w in G.WORLDS:
        sim = G.simulate(w, n_paths, horizon_days, SEED + 1000 + WORLD_SEED[w], pl, blocks)
        Rr, Cc, RFf = sim["R"], sim["C"], sim["RF"]
        day_cps = [c * MONTH_DAYS for c in CHECKPOINTS]
        dist[w] = {
            "excess_over_rf": RU.dist_tstat_sharpe(Rr - RFf, 252, day_cps, key_fn=month_key),
            "active_vs_control": RU.dist_tstat_sharpe(Rr - Cc, 252, day_cps, key_fn=month_key),
        }
        act_m = gold_monthly_active(Rr, Cc)
        sres = RU.sprt_run(act_m, mu0=mu0, mu1=mu2, sigma=sigma, alpha=0.05, beta=0.2)
        summ = RU.sprt_summary(sres, CHECKPOINTS)
        summ.update(world=w, label=G.WORLD_LABEL[w], ground_truth_has_edge=G.WORLD_HAS_EDGE[w],
                   world_active_monthly_mean=float(act_m.mean()))
        sprt_oc[w] = summ
        frozen_oc[w] = RU.apply_frozen_rule(Rr, Cc, RFf, frozen_rule, frozen_params, checkpoints=(12, 24, 36, 60))
        del sim, Rr, Cc, RFf, act_m

    power = {"sigma_active_monthly": sigma, "mu0_null": mu0, "mu_earlier_W1": mu1, "mu_later_W2": mu2,
            "months_needed_80pow_W0_vs_W1_earlier": RU.fixed_sample_months_needed(mu1 - mu0, sigma),
            "months_needed_80pow_W0_vs_W2_later": RU.fixed_sample_months_needed(mu2 - mu0, sigma)}
    for cp in CHECKPOINTS:
        power[f"power_at_{cp}m_W0_vs_W1"] = RU.fixed_sample_power(cp, mu1 - mu0, sigma)
        power[f"power_at_{cp}m_W0_vs_W2"] = RU.fixed_sample_power(cp, mu2 - mu0, sigma)

    return {"pools_n": {k: int(len(v)) for k, v in pl.items()}, "block_lengths": blocks,
            "sprt_calibration": {"sigma": sigma, "mu0": mu0, "mu_earlier": mu1, "mu_later": mu2},
            "dist": dist, "sprt": sprt_oc, "frozen_rule_oc": frozen_oc, "power": power,
            "frozen_rule_params_used": frozen_params, "frozen_rule_definition": frozen_rule,
            "frozen_rule_forward_start": frozen_cand["forward_start"],
            "frozen_rule_spec_sha256": spec["sha256"]}


# ---------------------------------------------------------------- proposed TLT SPRT spec
def build_proposed_rule(tsy: dict) -> dict:
    p = tsy["power"]
    A, B = RU.sprt_bounds(0.05, 0.2)
    body = {
        "spec_version": "future_lab2.proposed_sprt.v1",
        "status": "PROPOSED, UNREGISTERED. Not a pre-specified rule until its sha256 is registered "
                 "in research/preregistrations.jsonl before forward data (after 2026-09-24) is used "
                 "to evaluate it. The director decides whether to register it.",
        "candidate": "tsy_month_end_v1",
        "frozen_candidate_spec": "research/forward_audit/tsy_month_end_v1_spec.json",
        "rule_type": "Wald SPRT (Sequential Probability Ratio Test), one look per calendar month, "
                     "on the monthly window excess return net of the frozen base cost.",
        "statistic": {
            "definition": "x_n = (window n's TLT return over its 3 held sessions, minus the T-bill "
                          "return accrued over the same sessions) minus 4 bp (base cost, 2 bp/side x "
                          "2 sides: entry + exit). Equivalently: win_ex - 0.0004, where win_ex "
                          "reproduces reports/audit_tsy/e_postpub.json's window_ex figures exactly.",
            "look_cadence": "one look at the close of each month's last held session (the same close "
                            "that ends book M's position), i.e. one look per month, matching the "
                            "~12 windows/year of the frozen spec.",
        },
        "hypotheses": {
            "H0_kill": f"true mean = {p['mu0_null_net']:.6f} (gross edge exactly zero; base cost still paid)",
            "H1_confirm": f"true mean = {p['mu0_null_net'] + (p['mu_post_net'] - p['mu0_null_net']):.6f} "
                          "(the post-publication, 2019-10..2026-08 sample mean, net of base cost -- "
                          "world W2 in reports/future_lab2/results.json)",
        },
        "parameters": {"mu0": p["mu0_null_net"], "mu1": p["mu_post_net"], "sigma": p["sigma"],
                       "alpha": 0.05, "beta": 0.2, "A_upper_confirm": A, "B_lower_kill": B},
        "sigma_source": "sample std (ddof=1) of win_ex over the full 2003-01..2026-08 history "
                        "(284 months; reports/audit_tsy/c_months_{dev,val}.csv), fixed and not "
                        "re-estimated on forward data.",
        "decision_rule": [
            "LLR_n = sum_{i=1}^{n} (mu1-mu0)/sigma^2 * (x_i - (mu0+mu1)/2), cumulative over months.",
            f"CONFIRM (accept H1) at the first month where LLR_n >= A = {A:.4f}.",
            f"KILL (accept H0) at the first month where LLR_n <= B = {B:.4f}.",
            "Otherwise CONTINUE. Decisions are terminal.",
            "At 120 months (10 years) with no decision: END_NO_DECISION -- stays forward observation "
            "only; this cap is a reporting convention of this lab, not part of the SPRT itself, which "
            "in principle continues until it exits (mu1-mu0)/sigma^2)-scaled boundaries.",
        ],
        "max_months_reported": HORIZON_MONTHS,
        "evaluator": "research.future_lab2.rule.sprt_run(X, mu0, mu1, sigma, alpha=0.05, beta=0.2), "
                    "X = the realised monthly x_n sequence from forward_start onward",
        "forward_start": "2026-09-24 (per reports/tsy_month_end/ADDENDUM_AUDIT_2026-09-23.md: forward "
                         "judgement uses only data after this date, with official closes)",
        "operating_characteristics": {
            "months_needed_80pow_fixed_sample_W0_vs_W1": p["months_needed_80pow_W0_vs_W1"],
            "months_needed_80pow_fixed_sample_W0_vs_W2": p["months_needed_80pow_W0_vs_W2"],
            "note": "The SPRT is sequential and on average decides faster than the fixed-sample test "
                   "above at the same alpha/beta, but the fixed-sample number is the right answer to "
                   "'how long for 80% power' since the SPRT's own decision time is itself a random "
                   "variable (see sprt_oc.csv / results.json for its simulated distribution per world).",
            "full_operating_characteristics": "reports/future_lab2/tsy_sprt.csv and results.json (tsy.sprt), "
                                              "simulated under W0-W5, 8000+ paths, seed 20260924",
        },
        "not_evidence": "mu1 and sigma are estimated from already-observed history, including the same "
                        "window effect this rule will judge. The rule tests whether forward data is "
                        "consistent with that history; it cannot anticipate a regime absent from it. "
                        "It also does not use a haircut/sceptical-prior structure the way "
                        "research/future_lab/forward.py's Bayesian rule does -- it is deliberately the "
                        "simplest classical rule that matches the brief's alpha/beta request.",
        "limitations": [
            "sigma is treated as known and fixed; in truth it is estimated once from 284 months of "
            "history and could itself be wrong (e.g. under W4's vol x1.5, the true sigma is 50% higher "
            "than what this rule assumes, which changes its effective alpha/beta -- see W4's row in "
            "tsy_sprt.csv, where the rule's actual error rates drift from the nominal 5%/20%).",
            "H1 is pinned to the post-publication mean; a candidate that is real but weaker (e.g. W3's "
            "decaying edge) will often drift into KILL well before it would under W2, because the "
            "rule has no notion of a time-varying mean.",
            "The rule only ever chooses between exactly two points (mu0, mu1); it is not a test of "
            "'is there some edge', only of 'does the data look like mu0 or like mu1'.",
        ],
    }
    body = clean(body)
    body["sha256"] = F.canonical_hash(body)
    return body


# ---------------------------------------------------------------- flat tables + charts
def flat_dist_table(dist_by_world: dict, candidate: str, measure: str = "") -> list[dict]:
    rows = []
    for w, by_cp in dist_by_world.items():
        for cp, d in by_cp.items():
            rows.append({"candidate": candidate, "measure": measure, "world": w, "checkpoint": cp,
                        "tstat_p05": d["tstat"]["p05"], "tstat_p50": d["tstat"]["p50"], "tstat_p95": d["tstat"]["p95"],
                        "sharpe_p05": d["sharpe"]["p05"], "sharpe_p50": d["sharpe"]["p50"], "sharpe_p95": d["sharpe"]["p95"],
                        "p_tstat_gt_1645": d["p_tstat_gt_1645"], "p_sharpe_gt_0": d["p_sharpe_gt_0"]})
    return rows


def flat_sprt_table(sprt_by_world: dict, candidate: str) -> list[dict]:
    rows = []
    for w, s in sprt_by_world.items():
        base = {"candidate": candidate, "world": w, "label": s["label"],
               "ground_truth_has_edge": s["ground_truth_has_edge"], "p_confirm_by_cap": s["p_confirm"],
               "p_kill_by_cap": s["p_kill"], "p_undecided_at_cap": s["p_undecided_at_cap"],
               "median_months_to_decision": s["median_months_to_decision"],
               "p05_months_to_decision": s["p05_months_to_decision"], "p95_months_to_decision": s["p95_months_to_decision"]}
        for cp, d in s["by_checkpoint"].items():
            row = dict(base, checkpoint=cp, **d)
            rows.append(row)
    return rows


def flat_frozen_table(frozen_by_world: dict, candidate: str) -> list[dict]:
    rows = []
    for w, res in frozen_by_world.items():
        for cp, d in res["operating_characteristics"].items():
            rows.append({"candidate": candidate, "world": w, "checkpoint": cp,
                        "median_months_to_decision": res["median_months_to_decision"],
                        "p_undecided_at_cap": res["p_undecided_at_cap"], **d})
    return rows


def charts(tsy: dict, gold: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"W0": "#8a8a86", "W1": "#184f95", "W2": "#2a78d6", "W3": "#eb6834", "W4": "#1baf7a", "W5": "#c23b6f"}
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.5))
    for row, (name, sprt) in enumerate([("tsy_month_end_v1", tsy["sprt"]), ("momentum_gold_v1", gold["sprt"])]):
        ax_kill, ax_confirm = axes[row]
        for w, s in sprt.items():
            xs = [int(k[:-1]) for k in s["by_checkpoint"]]
            kills = [s["by_checkpoint"][k]["p_kill_by"] for k in s["by_checkpoint"]]
            confirms = [s["by_checkpoint"][k]["p_confirm_by"] for k in s["by_checkpoint"]]
            ax_kill.plot(xs, kills, marker="o", color=colors[w], label=f"{w}: {s['label']}")
            ax_confirm.plot(xs, confirms, marker="o", color=colors[w], label=f"{w}: {s['label']}")
        for ax, title in ((ax_kill, "P(SPRT decides KILL by month t)"), (ax_confirm, "P(SPRT decides CONFIRM by month t)")):
            ax.set_title(f"{name}\n{title}", fontsize=9)
            ax.set_xlabel("months since forward start")
            ax.set_ylim(-0.02, 1.02)
            ax.set_xticks([12, 24, 36, 60, 120])
            ax.grid(True, color="#e1e0d9", lw=0.8)
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=7.5, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Proposed/frozen sequential rule, simulated under 6 explicit worlds (seed 20260924)", fontsize=11)
    fig.tight_layout(rect=(0, 0.08, 1, 0.96))
    fig.savefig(out / "decision_time_distributions.png", dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main(fast: bool = False) -> dict:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    n_tsy, n_gold = (2000, 800) if fast else (10_000, 4000)

    tsy = run_tsy(n_tsy)
    print(f"[{time.time() - t0:6.1f}s] tsy_month_end_v1 done", flush=True)
    gold = run_gold(n_gold)
    print(f"[{time.time() - t0:6.1f}s] momentum_gold_v1 done", flush=True)

    proposed = build_proposed_rule(tsy)
    (OUT / "proposed_forward_rule_tsy_month_end_v1.json").write_text(json.dumps(proposed, indent=1, allow_nan=False))

    import pandas as pd
    pd.DataFrame(flat_dist_table(tsy["dist"], "tsy_month_end_v1", "window_excess_net")).to_csv(OUT / "tsy_dist.csv", index=False)
    pd.DataFrame(flat_sprt_table(tsy["sprt"], "tsy_month_end_v1")).to_csv(OUT / "tsy_sprt.csv", index=False)
    rows = flat_dist_table({w: d["excess_over_rf"] for w, d in gold["dist"].items()}, "momentum_gold_v1", "excess_over_rf")
    rows += flat_dist_table({w: d["active_vs_control"] for w, d in gold["dist"].items()}, "momentum_gold_v1", "active_vs_control")
    pd.DataFrame(rows).to_csv(OUT / "gold_dist.csv", index=False)
    pd.DataFrame(flat_sprt_table(gold["sprt"], "momentum_gold_v1")).to_csv(OUT / "gold_sprt.csv", index=False)
    pd.DataFrame(flat_frozen_table(gold["frozen_rule_oc"], "momentum_gold_v1")).to_csv(OUT / "gold_frozen_rule.csv", index=False)

    charts(tsy, gold, OUT)

    code_files = sorted((ROOT / "research" / "future_lab2").glob("*.py"))
    inputs = [ROOT / "reports/audit_tsy/c_months_dev.csv", ROOT / "reports/audit_tsy/c_months_val.csv",
             ROOT / "reports/audit_tsy/e_postpub.json", TSY_SPEC,
             ROOT / "reports/momentum_gold_20260919/momentum_gold_full_base.csv",
             ROOT / "reports/momentum_gold_20260919/market_gold_full_base.csv",
             ROOT / "reports/momentum_gold_20260919/forward_paper_spec.json", MONITORING_SPEC]
    manifest = {"seed": SEED, "fast": fast, "n_paths_tsy": n_tsy, "n_paths_gold": n_gold,
               "horizon_months": HORIZON_MONTHS, "checkpoints_months": list(CHECKPOINTS),
               "runtime_seconds": round(time.time() - t0, 1),
               "code_sha256": {str(p.relative_to(ROOT)): sha(p) for p in code_files},
               "input_sha256": {str(p.relative_to(ROOT)): sha(p) for p in inputs},
               "proposed_rule_sha256": proposed["sha256"]}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))

    results = {"tsy_month_end_v1": tsy, "momentum_gold_v1": gold}
    (OUT / "results.json").write_text(json.dumps(clean(results), indent=1, allow_nan=False))
    print(f"[{time.time() - t0:6.1f}s] done", flush=True)
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    main(ap.parse_args().fast)
