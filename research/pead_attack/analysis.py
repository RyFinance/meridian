"""Pre-registered analysis (PLAN.md sections 4-7): p-values, decision rule, decomposition, diagnostics.

Run after placebo.py: PYTHONPATH=. .venv/bin/python -m research.pead_attack.analysis
Writes reports/pead_attack/results.json, pvalues.csv, decomposition.csv, real_book_daily.csv
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import norm

from research.common.inference import sharpe_ci
from research.pead_attack.common import OUT, Inputs, book_stats
from research.pead_attack.engine import kelly_sizes, simulate
from research.pead_attack.marking import mark_book
from research.pead_attack.placebo import FAMILIES, holdout_bounds, subwindow_sharpes

PRIMARY = ("P1", "sharpe")
STATS = ["sharpe", "cagr", "capm_alpha", "ff6_alpha"]
ALPHA = 0.05
AUDIT = OUT.parent / "pead_audit" / "results.json"


def p_upper(real: float, dist: np.ndarray) -> float:
    """One-sided: probability a placebo book does at least as well; +1 (Phipson-Smyth) correction."""
    dist = np.asarray(dist, dtype=float)
    dist = dist[np.isfinite(dist)]
    return float((1 + np.sum(dist >= real)) / (len(dist) + 1))


def holm(pvals: dict[str, float]) -> dict[str, float]:
    keys = sorted(pvals, key=pvals.get)
    m, out, running = len(keys), {}, 0.0
    for i, k in enumerate(keys):
        running = max(running, min(1.0, (m - i) * pvals[k]))
        out[k] = running
    return out


def classify(p: dict) -> str:
    """PLAN section 5 decision rule. H1 (primary): P1 Sharpe p <= 0.05. H2: beats generic post-announcement
    exposure, i.e. P3 Sharpe p <= 0.05 AND P1L CAPM-alpha p <= 0.05 (both, unadjusted)."""
    h1 = p[("P1", "sharpe")] <= ALPHA
    h2 = p[("P3", "sharpe")] <= ALPHA and p[("P1L", "capm_alpha")] <= ALPHA
    if h1 and h2:
        return "A: SELECTION EDGE (model ranking beats random selection and generic post-announcement exposure)"
    if h1:
        return "B: SELECTION SIGNAL WITHOUT EDGE OVER GENERIC EXPOSURE"
    if h2:
        return "C: EXPOSURE EDGE WITHOUT MODEL SKILL (beats generic long exposure, not random selection)"
    return "D: EVENT-EXPOSURE PRODUCT (neither H1 nor H2)"


def years_for_power(effect_ann: float, vol_ann: float, alpha: float = 0.05, power: float = 0.80) -> float:
    if effect_ann <= 0:
        return float("inf")
    return float(((norm.ppf(1 - alpha) + norm.ppf(power)) * vol_ann / effect_ann) ** 2)


def main() -> dict:
    inp = Inputs()
    real = simulate(inp.stream, inp.p_real, inp.size_real, inp.sign_prod)
    m = mark_book(real["trades"], inp.px_mark, inp.col, inp.rf)
    ex = m["ret"] - inp.rf
    R = book_stats(m["ret"], inp.rf, inp.calendar, m["gross"], full=True)
    names, bounds = holdout_bounds(inp)
    R.update({"n_trades": int(len(real["trades"])), "long_share": float((real["trades"]["sign"] > 0).mean()),
              "sharpe_ci95": sharpe_ci(ex, 252, block=21),
              **dict(zip(["sharpe_ha", "sharpe_hb", "sharpe_hc"], subwindow_sharpes(ex, bounds)))})
    R["holdout_windows"] = {n: [str(inp.dates[a].date()), str(inp.dates[b - 1].date())] for n, (a, b) in zip(names, bounds)}
    pd.DataFrame({"ret": m["ret"], "excess": ex, "nav": m["nav"], "gross": m["gross"], "rf": inp.rf},
                 index=inp.dates).to_csv(OUT / "real_book_daily.csv")

    draws = {f: pd.read_csv(OUT / f"placebo_draws_{f}.csv") for f in FAMILIES}
    pv, rows = {}, []
    for f, d in draws.items():
        for s in STATS + ["cagr_expmatch", "sharpe_ha", "sharpe_hb", "sharpe_hc"]:
            if s not in d:
                continue
            real_v = R["cagr"] if s == "cagr_expmatch" else R[s]
            p = p_upper(real_v, d[s].to_numpy())
            if s in STATS:
                pv[(f, s)] = p
            rows.append({"family": f, "stat": s, "real": real_v, "placebo_mean": float(d[s].mean()),
                         "placebo_median": float(d[s].median()), "q025": float(d[s].quantile(.025)),
                         "q975": float(d[s].quantile(.975)), "q95": float(d[s].quantile(.95)),
                         "p_upper": p, "n_draws": int(d[s].notna().sum()),
                         "killed_share": float(d["killed"].mean()), "mean_trades": float(d["n_trades"].mean()),
                         "mean_long_share": float(d["long_share"].mean()), "mean_gross": float(d["avg_gross"].mean())})
    table = pd.DataFrame(rows)
    secondary = {f"{f}:{s}": p for (f, s), p in pv.items() if (f, s) != PRIMARY}
    adj = holm(secondary)
    table["p_holm_secondary"] = [adj.get(f"{r.family}:{r.stat}", np.nan) if (r.family, r.stat) != PRIMARY and r.stat in STATS
                                 else np.nan for r in table.itertuples()]
    table.to_csv(OUT / "pvalues.csv", index=False)

    # -- decomposition (PLAN 6) -------------------------------------------------------------------
    mkt = inp.calendar["mkt_rf"].fillna(0).to_numpy()
    E = float(ex.mean() * 252)
    beta_part = R["capm_beta"] * float(mkt.mean() * 252)
    a1, a1l = float(draws["P1"]["capm_alpha"].mean()), float(draws["P1L"]["capm_alpha"].mean())
    dec = [{"component": "market beta (beta_R x mean Mkt-RF)", "ann_excess_return": beta_part},
           {"component": "generic post-announcement premium (mean alpha, P1L)", "ann_excess_return": a1l},
           {"component": "SUE-sign direction on random selection (mean alpha P1 - P1L)", "ann_excess_return": a1 - a1l},
           {"component": "model selection residual (alpha_R - mean alpha P1)", "ann_excess_return": R["capm_alpha"] - a1}]
    total = sum(r["ann_excess_return"] for r in dec)
    for r in dec:
        r["share_of_total"] = r["ann_excess_return"] / E
    dec.append({"component": "total = real book mean excess return", "ann_excess_return": total, "share_of_total": total / E})
    f1, f1l = float(draws["P1"]["ff6_alpha"].mean()), float(draws["P1L"]["ff6_alpha"].mean())
    dec_ff6 = {"alpha_R_ff6": R["ff6_alpha"], "mean_alpha_P1L_ff6": f1l, "mean_alpha_P1_minus_P1L_ff6": f1 - f1l,
               "selection_residual_ff6": R["ff6_alpha"] - f1}
    pd.DataFrame(dec).to_csv(OUT / "decomposition.csv", index=False)
    s1 = draws["P1"]["sharpe"]
    sharpe_split = {"real": R["sharpe"], "p1_mean": float(s1.mean()), "p1_median": float(s1.median()),
                    "selection_share_of_sharpe": (R["sharpe"] - float(s1.mean())) / R["sharpe"],
                    "p1l_mean": float(draws["P1L"]["sharpe"].mean()), "p3_mean": float(draws["P3"]["sharpe"].mean()),
                    "p1_minimum_detectable_sharpe_gap_5pct": float(s1.quantile(.95) - s1.median())}

    # -- diagnostics (PLAN 7) --------------------------------------------------------------------
    diag = {}
    p_pit = inp.events["pit_calibrated_proba"].to_numpy(dtype=float)
    pit = simulate(inp.stream, p_pit, kelly_sizes(p_pit, inp.b), inp.sign_prod)
    mp = mark_book(pit["trades"], inp.px_mark, inp.col, inp.rf)
    D1 = book_stats(mp["ret"], inp.rf, inp.calendar, mp["gross"], full=True)
    D1.pop("ff6_loadings")
    D1["n_trades"] = int(len(pit["trades"]))
    D1["percentile_in_P1_sharpe"] = float((s1 < D1["sharpe"]).mean())
    D1["trade_overlap_with_real"] = float(len(set(pit["trades"]["event"]) & set(real["trades"]["event"])) / len(real["trades"]))
    diag["D1_point_in_time_liquidity_rank"] = D1
    mf = mark_book(real["trades"], inp.px_mark, inp.col, inp.rf, exit_day_cash_fix=True)
    D2 = book_stats(mf["ret"], inp.rf, inp.calendar, mf["gross"])
    diag["D2_exit_day_cash_fix"] = {"sharpe": D2["sharpe"], "cagr": D2["cagr"], "capm_alpha": D2["capm_alpha"],
                                    "sharpe_change": D2["sharpe"] - R["sharpe"]}
    te = float(draws["P1"]["diff_vol_ann"].mean())
    gap = float(draws["P1"]["diff_mean_ann"].mean())
    diag["D4_forward_power"] = {
        "paired_vs_random_shadow": {"hist_mean_excess_gap_ann": gap, "tracking_error_ann": te,
                                    "corr_real_vs_P1": float(draws["P1"]["corr_with_real"].mean()),
                                    "years_for_80pct_power_at_hist_gap": years_for_power(gap, te)},
        "unpaired_sharpe_vs_zero_years_80pct": years_for_power(R["sharpe"], 1.0),
        "unpaired_sharpe_gap_vs_P1_mean_years_80pct": years_for_power(R["sharpe"] - float(s1.mean()), np.sqrt(2)),
    }
    audit = json.loads(AUDIT.read_text())["wide_5p0"]
    context = {"audit_universe_control_sharpe": audit["control_same_trades_in_universe_avg"]["sharpe"],
               "audit_spy_control_sharpe": audit["control_same_trades_in_SPY"]["sharpe"]}
    out = {"real_book": R, "pvalues_primary": {"family": PRIMARY[0], "stat": PRIMARY[1], "p": pv[PRIMARY]},
           "pvalues": {f"{f}:{s}": p for (f, s), p in pv.items()}, "pvalues_holm_secondary": adj,
           "classification": classify(pv), "decomposition_capm": dec, "decomposition_ff6": dec_ff6,
           "sharpe_split": sharpe_split, "diagnostics": diag, "context": context,
           "n_draws": {f: int(len(d)) for f, d in draws.items()}}
    (OUT / "results.json").write_text(json.dumps(out, indent=1, default=float))
    return out


if __name__ == "__main__":
    res = main()
    print(json.dumps({k: res[k] for k in ["pvalues_primary", "classification", "sharpe_split"]}, indent=1, default=float))
