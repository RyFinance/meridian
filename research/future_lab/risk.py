"""Section 2: path-risk analytics per candidate, per resampling method.

For each panel and method one joint simulation (N paths x 5 years of trading days) is drawn; every
candidate in the panel and its control are read off the same simulated dates. Horizons 1/3/5 years
are prefixes of the same 5-year path.
"""
from __future__ import annotations

import numpy as np

from research.future_lab import engines as E
from research.future_lab import paths as PA
from research.future_lab.data import Panel

HORIZONS = {"1y": 252, "3y": 756, "5y": 1260}
LEVERAGE = (1.0, 1.5, 2.0)
COST_SHOCKS_BPS = (10, 25)
DD_LEVELS = (0.20, 0.30)


def candidate_arrays(sim: dict, panel: Panel, cand: dict) -> dict:
    cols = list(panel.returns.columns)
    tcols = list(panel.turnover.columns)
    R = sim["R"][cols.index(cand["series"])]
    C = sim["R"][cols.index(cand["control"])] if cand.get("control") else sim["RF"]
    TO = sim["TO"][tcols.index(cand["series"])] if cand["series"] in tcols else np.zeros_like(R)
    CTO = (sim["TO"][tcols.index(cand["control"])] if cand.get("control") in tcols else np.zeros_like(R))
    return {"R": R, "C": C, "RF": sim["RF"], "TO": TO, "CTO": CTO}


def no_edge_shift(panel: Panel, cand: dict) -> float:
    """Constant daily shift that sets the candidate's historical mean equal to its control's
    (for SPY, whose control is T-bills: excess mean zero)."""
    r = panel.returns[cand["series"]]
    c = panel.returns[cand["control"]] if cand.get("control") else panel.rf
    return float(c.mean() - r.mean())


def control_trades_under_shock(cand: dict) -> bool:
    """Cost shocks hit the control too only when the control is a tradable portfolio that trades
    (SPY/GLD). PEAD's timing-matched controls are counterfactual placements, so the shock is
    charged to the strategy alone (it represents single-name execution cost)."""
    return cand.get("control") == "spy_gld"


def candidate_risk(a: dict, shift: float, cand: dict) -> dict:
    R, C, RF, TO, CTO = a["R"], a["C"], a["RF"], a["TO"], a["CTO"]
    out: dict = {"horizons": {}, "leverage": {}, "cost_shock": {}, "no_edge": {}}
    for hname, h in HORIZONS.items():
        m = PA.horizon_metrics(R, RF, h)
        Wc = PA.wealth(C[:, :h])[:, -1]
        d = {k: PA.q(v) for k, v in m.items() if k in ("cagr", "sharpe", "max_dd", "underwater_years")}
        d["mean_sharpe"] = float(np.nanmean(m["sharpe"]))
        d["sd_sharpe"] = float(np.nanstd(m["sharpe"]))
        for lvl in DD_LEVELS:
            d[f"p_dd_gt_{int(lvl * 100)}"] = float((m["max_dd"] < -lvl).mean())
        d["p_under_control"] = float((m["terminal"] < Wc).mean())
        act = R[:, :h] - C[:, :h]
        sd = act.std(axis=1, ddof=1)
        ir = np.divide(act.mean(axis=1), sd, out=np.full(sd.shape, np.nan), where=sd > 0) * np.sqrt(252)
        d["mean_ir_vs_control"] = float(np.nanmean(ir))
        d["sd_ir_vs_control"] = float(np.nanstd(ir))
        out["horizons"][hname] = d
    for L in LEVERAGE:
        RL = PA.levered(R, RF, L)
        W = PA.wealth(RL)
        entry = {}
        for hname, h in HORIZONS.items():
            entry[hname] = {"p_ruin": float((W[:, :h].min(axis=1) < PA.RUIN_LEVEL).mean()),
                            "p_dd_gt_30": float((PA.max_drawdown(W[:, :h]) < -0.30).mean()),
                            "median_cagr": float(np.median(PA.cagr(W[:, h - 1], h)))}
        out["leverage"][f"{L:g}x"] = entry
    h3 = HORIZONS["3y"]
    ctl_shock = control_trades_under_shock(cand)
    for bps in (0,) + COST_SHOCKS_BPS:
        x = bps / 1e4
        Rs = R - x * TO
        Cs = C - x * CTO if ctl_shock else C
        m5 = PA.horizon_metrics(Rs, RF, HORIZONS["5y"])
        out["cost_shock"][f"+{bps}bps"] = {
            "annual_drag": float(x * TO.mean() * 252),
            "median_cagr_5y": float(np.median(m5["cagr"])), "median_sharpe_5y": float(np.nanmedian(m5["sharpe"])),
            "p_under_control_3y": float((PA.wealth(Rs[:, :h3])[:, -1] < PA.wealth(Cs[:, :h3])[:, -1]).mean()),
            "control_also_shocked": ctl_shock}
    Rn = R + shift
    W = PA.wealth(Rn)
    Wc3 = PA.wealth(C[:, :h3])[:, -1]
    W2 = PA.wealth(PA.levered(Rn, RF, 2.0))
    out["no_edge"] = {"daily_shift": shift, "annual_shift": shift * 252,
                      "median_cagr_5y": float(np.median(PA.cagr(W[:, -1], HORIZONS["5y"]))),
                      "p_dd_gt_20_5y": float((PA.max_drawdown(W) < -0.2).mean()),
                      "p_dd_gt_30_5y": float((PA.max_drawdown(W) < -0.3).mean()),
                      "p_under_control_3y": float((W[:, h3 - 1] < Wc3).mean()),
                      "p_ruin_2x_5y": float((W2.min(axis=1) < PA.RUIN_LEVEL).mean())}
    return out


def running_dd_by_month(R: np.ndarray, months: int = 60, month_days: int = 21) -> np.ndarray:
    """Running max drawdown at each month-end (paths x months)."""
    W = PA.wealth(R[:, : months * month_days])
    rdd = PA.running_max_dd(W)
    return rdd[:, month_days - 1:: month_days][:, :months]


def run_panel(panel: Panel, cands: dict, methods, n_paths: int, horizon: int, seed: int,
              keep_paths_for: tuple = ()) -> tuple[dict, dict, dict]:
    """Returns (results[cand][method], block info, kept arrays for charts[cand][method])."""
    ret = panel.returns.to_numpy()
    rf = panel.rf.to_numpy()
    tov = panel.turnover.to_numpy()
    labels = {k: panel.regimes[k].to_numpy() for k in ("vol_tercile", "dd_state")}
    blocks = E.panel_block_length(ret)
    results = {c: {} for c in cands}
    kept = {c: {} for c in cands}
    meta = {"block_length": {"sb": blocks["sb"], "cb": blocks["cb"],
                             "per_column": {panel.returns.columns[j]: v for j, v in blocks["per_column"].items()}},
            "method_info": {}}
    for mi, method in enumerate(methods):
        sim = E.simulate_panel(method, ret, rf, tov, labels, blocks, n_paths, horizon, seed + 1000 * mi)
        meta["method_info"][method] = sim["info"]
        for cname, cand in cands.items():
            a = candidate_arrays(sim, panel, cand)
            results[cname][method] = candidate_risk(a, no_edge_shift(panel, cand), cand)
            if cname in keep_paths_for:
                W = PA.wealth(a["R"])
                kept[cname][method] = {
                    "wealth_q": np.quantile(W, [0.05, 0.25, 0.5, 0.75, 0.95], axis=0)[:, 20::21],
                    "max_dd_5y": PA.max_drawdown(W).astype(np.float32),
                    "running_dd_month": running_dd_by_month(a["R"]).astype(np.float32),
                }
        del sim
    return results, meta, kept
