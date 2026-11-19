"""Instrument filter and new-sample window metrics (FRAMEWORK §4, §5), recomputed from the frozen engine's
MONTHLY series with the frozen A4 / engine inference functions. The engine's own metrics are computed on the whole
history (and around the cycle-6 post-publication cutoff), so none of them is used as a cycle-7 headline.

Exact definitions (all on holding months m of the engine's net series, one-session lag, per FRAMEWORK §4):
- window W = {m : start <= m < end_exclusive}; the engine runs on the full loaded history (warm-up), then only
  months in W are evaluated.
- active (rank / calendar-shuffle controls): net.ret - control.net on common months in W (the engine's rule).
- active (always-long control): controls.matched_active(net.ret, control.net, ratio, W) with
  ratio = controls.exposure_ratio(net.net_exposure, control.net_exposure): m-bar is the mean ratio over W
  (the engine's rule applied to the evaluated window; with no window it reproduces active_full_window exactly).
- 2x costs (multiplier c = cost_mult_sensitivity): book = net.ret_before_cost - c * net.cost. The engine's control
  frame carries only net and stress (= before-cost - s * cost, s = spec stress multiplier; the placebo control is
  the mean of per-book series, which is linear), so control cost = (control.net - control.stress) / (s - 1) and the
  control at c = control.net - (c - 1) * control cost (exactly before-cost - c * cost, own cost for the always-long
  control). Active at c uses the same m-bar rule. The same identity is checked on the book against its direct value.
- p: inference.calibrated_p (spec B, crash layer, bandwidth fraction, overlap), seed s0 + offset.
- CI: inference.calibrated_ci at 0.90 and 0.95 (both always), primary level = inference.ci_level(n, crash, ...),
  B = spec ci_B, seed s0 + offset. The control's seed is never changed.
- SE_i (FRAMEWORK §5): research.amendment4.ci._est(x, L), L = calib.stat_lags(n) (fixed-b 0.10, not the spec's
  bandwidth); monthly Sharpe s and its influence-function HAC SE se_s.
- best-year share of positive P&L: yearly sums Y_y of monthly active returns; max_y Y_y / sum_y max(Y_y, 0)
  (None if no year is positive).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from research.amendment4 import calib
from research.amendment4 import ci as a4ci
from research.cycle6.engine import controls, inference
from research.cycle6.engine import io as eio

from .common import GuardError


# ------------------------------------------------------------------------------------------------ filter
def filtered_universe(snapshot_root, membership, params: dict, flt: dict) -> list[str]:
    cands = eio.load_candidates(snapshot_root, membership)
    uni = eio.universe(cands, params["class"])
    if flt.get("class") != params["class"]:
        raise GuardError(f"instrument_filter class {flt.get('class')} != spec class {params['class']}")
    inc, exc = flt.get("include_market_ids"), flt.get("exclude_market_ids")
    unknown = set(flt) - {"class", "include_market_ids", "exclude_market_ids", "instrument_list_sha256", "note"}
    if unknown:
        raise GuardError(f"instrument_filter has unsupported keys {sorted(unknown)}")
    if inc is not None and exc is not None:
        raise GuardError("instrument_filter: give include_market_ids OR exclude_market_ids, not both")
    if inc is not None:
        missing = sorted(set(map(str, inc)) - set(uni))
        if missing:
            raise GuardError(f"include_market_ids not PASS in class {params['class']}: {missing}")
        ids = sorted(set(map(str, inc)))
    elif exc is not None:
        ids = sorted(set(uni) - set(map(str, exc)))
    else:
        ids = list(uni)
    if not ids:
        raise GuardError("instrument filter leaves no instruments")
    return ids


def apply_filter(data: dict, ids: list[str]) -> dict:
    """Restrict the loaded engine data dict to ``ids`` (as if the membership file listed only them)."""
    missing = [i for i in ids if i not in data["daily"].columns]
    if missing:
        raise ValueError(f"filtered instruments absent from the daily panel: {missing}")
    out = dict(data)
    out["daily"] = data["daily"][ids].dropna(how="all")
    out["universe"] = list(ids)
    out["signal_inputs"] = {k: v.reindex(columns=ids) for k, v in data["signal_inputs"].items()}
    return out


# ------------------------------------------------------------------------------------------------ window
def window_mask(idx: pd.PeriodIndex, start, end_exclusive) -> np.ndarray:
    m = np.ones(len(idx), bool)
    if start:
        m &= idx >= pd.Period(start, "M")
    if end_exclusive:
        m &= idx < pd.Period(end_exclusive, "M")
    return m


def _win(s, start, end_exclusive):
    return s[window_mask(s.index, start, end_exclusive)]


def control_cost(control: pd.DataFrame, stress_mult: float) -> pd.Series:
    if abs(stress_mult - 1.0) < 1e-12:
        raise ValueError("stress multiplier 1: control cost not identifiable from net/stress")
    return (control["net"] - control["stress"]) / (stress_mult - 1.0)


def active_series(res: dict, params: dict, start, end_exclusive, cost_mult: float) -> dict:
    net, control = res["net"], res["control"]
    s_mult = float(params["costs"]["stress_multiplier"])
    book_c = net["ret_before_cost"] - cost_mult * net["cost"]
    book_frame = pd.DataFrame({"net": net["ret"], "stress": res["stress"]["ret"].reindex(net.index)})
    book_c_via_stress = net["ret"] - (cost_mult - 1.0) * control_cost(book_frame, s_mult)
    lin_err = float((book_c - book_c_via_stress).abs().max()) if len(book_c) else 0.0
    ctl_c = control["net"] - (cost_mult - 1.0) * control_cost(control, s_mult)
    idx_all = net.index.intersection(control.index)
    win_idx = idx_all[window_mask(idx_all, start, end_exclusive)]
    if params["control"]["type"] == "always_long":
        ratio = controls.exposure_ratio(net["net_exposure"], control["net_exposure"])
        act, mbar = controls.matched_active(net["ret"], control["net"], ratio, win_idx)
        act_c, mbar_c = controls.matched_active(book_c, ctl_c, ratio, win_idx)
    else:
        act = (net["ret"] - control["net"]).reindex(win_idx)
        act_c = (book_c - ctl_c).reindex(win_idx)
        mbar = mbar_c = None
    return {"active": act.dropna(), "active_c": act_c.dropna(), "book_c": book_c.reindex(win_idx),
            "control_c": ctl_c.reindex(win_idx), "mbar": mbar, "mbar_c": mbar_c, "stress_identity_max_err": lin_err,
            "window_index": win_idx}


# ------------------------------------------------------------------------------------------------ stats
def se_if(x) -> dict:
    """FRAMEWORK §5 SE_i: A4 influence-function HAC SE of the monthly Sharpe (ci._est, L = stat_lags(n))."""
    x = np.ascontiguousarray(np.asarray(pd.Series(x).dropna(), float))
    n = x.size
    if n < 24:
        return {"n": int(n), "note": "fewer than 24 months"}
    L = calib.stat_lags(n)
    m, se_m, s, se_s = a4ci._est(x, L)
    return {"n": int(n), "L": int(L), "mean_m": float(m), "se_mean_m": float(se_m), "sharpe_m": float(s),
            "se_sharpe_m": float(se_s), "sharpe_ann": float(s * math.sqrt(12)),
            "se_sharpe_ann": float(se_s * math.sqrt(12))}


def best_year_share(x: pd.Series) -> dict:
    x = pd.Series(x).dropna()
    if x.empty:
        return {"share": None}
    ys = x.groupby(x.index.year).sum()
    pos = float(ys[ys > 0].sum())
    if pos <= 0:
        return {"share": None, "note": "no positive year", "by_year": {int(k): float(v) for k, v in ys.items()}}
    return {"share": float(ys.max() / pos), "best_year": int(ys.idxmax()),
            "by_year": {int(k): float(v) for k, v in ys.items()}}


def inference_block(x: pd.Series, inf: dict, offset: int) -> dict:
    seed = int(inf["seed"]) + int(offset)
    pk = dict(B=inf["B"], seed=seed, crash=inf.get("crash"), bandwidth_fraction=inf["bandwidth_fraction"],
              overlap=inf.get("overlap", 1))
    x = x.dropna()
    n = len(x)
    lev = inference.ci_level(n, bool(inf.get("crash")), inf.get("ci_level", 0.90), inf.get("ci_level_crash_short", 0.95))
    ci_B = inf.get("ci_B", 499)
    c90 = inference.calibrated_ci(x, level=0.90, B=ci_B, seed=seed)
    c95 = inference.calibrated_ci(x, level=0.95, B=ci_B, seed=seed)
    return {"offset": int(offset), "seed": seed, "p": inference.calibrated_p(x, **pk), "ci_level_primary": lev,
            "ci_primary": c95 if abs(lev - 0.95) < 1e-12 else (c90 if abs(lev - 0.90) < 1e-12 else
                                                              inference.calibrated_ci(x, level=lev, B=ci_B, seed=seed)),
            "ci_90": c90, "ci_95": c95}


def window_metrics(res: dict, params: dict, sample: dict, universe: list[str]) -> tuple[dict, dict]:
    mw = sample["month_window"]
    start, end = mw["start"], mw["end_exclusive"]
    cmult = float(sample["cost_mult_sensitivity"])
    inf = params["inference"]
    a = active_series(res, params, start, end, cmult)
    act, act_c = a["active"], a["active_c"]
    net_w = _win(res["net"], start, end)
    gross_w = _win(res["gross"], start, end)
    ctl_w = _win(res["control"], start, end)
    W = res["W"]
    held = W.shift(1).reindex(act.index)
    held_ids = sorted(c for c in held.columns if (held[c].fillna(0) != 0).any()) if len(held) else []
    seeds = [inference_block(act, inf, o) for o in sample["seeds_offsets"]]
    head = seeds[0]
    pk0 = dict(B=inf["B"], seed=int(inf["seed"]), crash=inf.get("crash"),
               bandwidth_fraction=inf["bandwidth_fraction"], overlap=inf.get("overlap", 1))
    n = int(len(act))
    out = {
        "window": {"start": start, "end_exclusive": end,
                   "first": str(act.index[0]) if n else None, "last": str(act.index[-1]) if n else None},
        "n_months": n, "feasible_min24": n >= 24,
        "universe": list(universe), "n_universe": len(universe),
        "instruments_held_in_window": held_ids, "n_instruments_held_in_window": len(held_ids),
        "n_held_per_month": ({"min": int(net_w["n_held"].min()), "median": float(net_w["n_held"].median()),
                              "max": int(net_w["n_held"].max())} if len(net_w) else None),
        "control": params["control"], "crash_declared": bool(inf.get("crash")),
        "mbar_window": a["mbar"],
        "active": {**inference.basic_stats(act), "p": head["p"], "ci_level_primary": head["ci_level_primary"],
                   "ci_primary": head["ci_primary"], "ci_90": head["ci_90"], "ci_95": head["ci_95"],
                   "se_if": se_if(act), "best_year_share_positive_pnl": best_year_share(act),
                   "years": inference.calendar_years(act)},
        "seeds": [{k: v for k, v in s.items()} for s in seeds],
        "cost_sensitivity": {"multiplier": cmult, "mbar_window": a["mbar_c"],
                             "active": {**inference.basic_stats(act_c),
                                        "mean_m": float(act_c.mean()) if len(act_c) else None,
                                        "p": inference.calibrated_p(act_c, **pk0)},
                             "book": inference.basic_stats(a["book_c"].dropna()),
                             "control": inference.basic_stats(a["control_c"].dropna()),
                             "stress_identity_max_err": a["stress_identity_max_err"],
                             "method": "ret_before_cost - c*cost; control cost = (net - stress)/(s - 1)"},
        "net_window": inference.basic_stats(net_w["ret"]) if len(net_w) else {"n": 0},
        "gross_window": inference.basic_stats(gross_w["ret"]) if len(gross_w) else {"n": 0},
        "control_window": inference.basic_stats(ctl_w["net"]) if len(ctl_w) else {"n": 0},
        "engine_full_history": {k: res["metrics"].get(k) for k in ("defined_months", "n_eligible_defined_months")},
    }
    frames = {"net": net_w, "gross": gross_w, "control": ctl_w,
              "active": pd.DataFrame({"active": act, f"active_cost{cmult:g}x": act_c,
                                      f"book_cost{cmult:g}x": a["book_c"], f"control_cost{cmult:g}x": a["control_c"]})}
    return out, frames
