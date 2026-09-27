"""Section 3: regime-ordering sensitivity and single-sequence dependence.

Terminal wealth of a fixed daily return sequence is a product and so is EXACTLY invariant to any
reordering of the days (the portfolio returns here are already net of their own rebalancing, so
reordering them ignores only second-order weight-drift interactions). What reordering moves is the
path: drawdowns, time under water, wealth at intermediate horizons, and whether a sequential kill
rule would have fired before a good stretch arrived. This module quantifies those, and asks how much
each candidate's history depends on its single best contiguous 12 or 24 months.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.future_lab import engines as E
from research.future_lab import paths as PA
from research.future_lab.forward import MONTH_DAYS, rule_decisions


def monthly_episodes(dates: pd.DatetimeIndex, labels: np.ndarray) -> list[tuple[int, int]]:
    """Regime episodes: each calendar month takes the (causal) regime label of its first trading
    day; an episode is a maximal run of consecutive months with the same label. Returns row ranges."""
    month = pd.Series(dates.to_period("M"), index=np.arange(len(dates)))
    first = month.ne(month.shift()).to_numpy()
    starts = np.flatnonzero(first)
    mlab = np.asarray(labels)[starts]
    ep_starts = [starts[0]]
    for i in range(1, len(starts)):
        if mlab[i] != mlab[i - 1]:
            ep_starts.append(starts[i])
    bounds = ep_starts + [len(dates)]
    return [(int(bounds[i]), int(bounds[i + 1])) for i in range(len(bounds) - 1)]


def permuted_orders(episodes: list[tuple[int, int]], n_perm: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    blocks = [np.arange(a, b) for a, b in episodes]
    out = np.empty((n_perm, sum(len(b) for b in blocks)), dtype=np.int32)
    for i in range(n_perm):
        order = rng.permutation(len(blocks))
        out[i] = np.concatenate([blocks[j] for j in order])
    return out


def order_metrics(R: np.ndarray, C: np.ndarray, RF: np.ndarray, h3: int = 756) -> dict[str, np.ndarray]:
    W = PA.wealth(R)
    Wc = PA.wealth(C)
    h = min(h3, R.shape[-1])
    return {"terminal": W[..., -1], "max_dd": PA.max_drawdown(W),
            "underwater_years": PA.longest_underwater(W) / 252,
            "cagr_first_3y": PA.cagr(W[..., h - 1], h),
            "active_first_3y": W[..., h - 1] / Wc[..., h - 1] - 1}


def best_window(x_log: np.ndarray, w: int) -> tuple[int, float]:
    cs = np.r_[0.0, np.cumsum(x_log)]
    sums = cs[w:] - cs[:-w]
    i = int(np.argmax(sums))
    return i, float(sums[i])


def _summary(R, C, RF) -> dict:
    x = R - RF
    a = R - C
    W = np.cumprod(1 + R)
    return {"cagr": float(W[-1] ** (252 / len(R)) - 1),
            "excess_sharpe": float(x.mean() / x.std(ddof=1) * np.sqrt(252)),
            "active_ann": float(a.mean() * 252),
            "ir_vs_control": float(a.mean() / a.std(ddof=1) * np.sqrt(252)) if a.std() > 0 else float("nan"),
            "max_dd": float(PA.max_drawdown(W[None])[0])}


def removal_drop(R, C, RF, w: int, key: str) -> tuple[float, float]:
    """Drop in excess Sharpe ('excess') or IR vs control ('active') from removing the best w-day
    window by that same criterion. Works on 2-D arrays (paths x days). Returns (drop, full stat)."""
    if key == "excess":
        z = np.log1p(R) - np.log1p(RF)
        d = R - RF
    else:
        z = np.log1p(R) - np.log1p(C)
        d = R - C
    cs = np.concatenate([np.zeros((z.shape[0], 1)), np.cumsum(z, axis=1)], axis=1)
    sums = cs[:, w:] - cs[:, :-w]
    i = sums.argmax(axis=1)
    n = d.shape[1]
    cols = np.arange(n)[None]
    keep = ~((cols >= i[:, None]) & (cols < i[:, None] + w))
    full = d.mean(axis=1) / d.std(axis=1, ddof=1) * np.sqrt(252)
    dk = np.where(keep, d, np.nan)
    rem = np.nanmean(dk, axis=1) / np.nanstd(dk, axis=1, ddof=1) * np.sqrt(252)
    return full - rem, full


def run_candidate(panel, cand: dict, rule: dict, params: dict, n_perm: int, n_boot: int, seed: int,
                  block_sb: float) -> dict:
    dates = panel.dates
    R = panel.returns[cand["series"]].to_numpy()
    C = panel.returns[cand["control"]].to_numpy() if cand.get("control") else panel.rf.to_numpy()
    RF = panel.rf.to_numpy()
    n = len(R)
    out: dict = {"n_days": n}
    # ---- 1. regime-episode permutation
    eps = monthly_episodes(dates, panel.regimes["vol_tercile"].to_numpy())
    orders = permuted_orders(eps, n_perm, seed)
    om = order_metrics(R[orders], C[orders], RF[orders])
    actual = order_metrics(R[None], C[None], RF[None])
    out["episodes"] = {"count": len(eps), "median_len_days": float(np.median([b - a for a, b in eps]))}
    perm = {}
    for k, v in om.items():
        a = float(actual[k][0])
        perm[k] = {"actual": a, **PA.q(v), "actual_percentile": float((v < a).mean() + 0.5 * (v == a).mean())}
    perm["terminal"]["max_abs_rel_deviation"] = float(np.max(np.abs(om["terminal"] / actual["terminal"][0] - 1)))
    out["regime_permutation"] = perm
    # rule applied to history as if it were forward data from inception
    act_p = (R[orders] - C[orders]) if cand.get("control") else None
    rdd = PA.running_max_dd(PA.wealth(R[orders]))[:, MONTH_DAYS - 1::MONTH_DAYS]
    dec = rule_decisions((R - RF)[orders], act_p, rdd, rule, params)
    rdd0 = PA.running_max_dd(PA.wealth(R[None]))[:, MONTH_DAYS - 1::MONTH_DAYS]
    dec0 = rule_decisions((R - RF)[None], (R - C)[None] if cand.get("control") else None, rdd0, rule, params)
    names = {0: "continue", 1: "kill_sharpe", 2: "kill_drawdown", 3: "revert_to_control", 4: "promote"}
    out["rule_on_history"] = {
        "months_checked": dec["months"],
        "actual_order": {"decision": names[int(dec0["code"][0])], "month": int(dec0["first_month"][0])},
        "permuted": {names[c]: float((dec["code"] == c).mean()) for c in names},
    }
    kill_mask = ((dec["code"] == 1) | (dec["code"] == 2)) & (dec["first_month"] > 0) & (dec["first_month"] <= 24)
    out["rule_on_history"]["permuted_kill_within_24m"] = float(kill_mask.mean())
    # ---- 2. best contiguous windows: removal, relocation, and how unusual the concentration is
    boot_idx = E.stationary_indices(n, n_boot, n, block_sb, seed + 7)
    Rb, Cb, RFb = R[boot_idx], C[boot_idx], RF[boot_idx]
    windows = {}
    full = _summary(R, C, RF)
    for w_name, w in (("12m", 252), ("24m", 504)):
        for key in (("excess", "active") if cand.get("control") else ("excess",)):
            z = (np.log1p(R) - np.log1p(RF)) if key == "excess" else (np.log1p(R) - np.log1p(C))
            i, s = best_window(z, w)
            keep = np.r_[0:i, i + w:n]
            removed = _summary(R[keep], C[keep], RF[keep])
            total = float(z.sum())
            # relocation of the block to every 21-day offset of the remaining sequence
            rest = keep
            blk = np.arange(i, i + w)
            positions = range(0, len(rest) + 1, MONTH_DAYS)
            reloc = np.stack([np.r_[rest[:p], blk, rest[p:]] for p in positions]).astype(np.int32)
            rm = order_metrics(R[reloc], C[reloc], RF[reloc])
            rdd_r = PA.running_max_dd(PA.wealth(R[reloc]))[:, MONTH_DAYS - 1::MONTH_DAYS]
            dec_r = rule_decisions((R - RF)[reloc], (R - C)[reloc] if cand.get("control") else None, rdd_r, rule, params)
            killed = ((dec_r["code"] == 1) | (dec_r["code"] == 2))
            drop_obs = full["excess_sharpe" if key == "excess" else "ir_vs_control"] - removed[
                "excess_sharpe" if key == "excess" else "ir_vs_control"]
            drop_boot, _ = removal_drop(Rb, Cb, RFb, w, key)
            windows[f"{w_name}_{key}"] = {
                "start": str(dates[i].date()), "end": str(dates[i + w - 1].date()),
                "window_log_gain": s, "total_log_gain": total,
                "share_of_total": s / total if abs(total) > 1e-9 else float("nan"),
                "full": full, "removed": removed,
                "stat_drop_observed": float(drop_obs),
                "stat_drop_bootstrap": PA.q(drop_boot),
                "p_boot_drop_ge_observed": float((drop_boot >= drop_obs).mean()),
                "relocated": {"max_dd": PA.q(rm["max_dd"], (0.0, 0.5, 1.0)),
                              "cagr_first_3y": PA.q(rm["cagr_first_3y"], (0.0, 0.5, 1.0)),
                              "active_first_3y": PA.q(rm["active_first_3y"], (0.0, 0.5, 1.0)),
                              "rule_kill_share": float(killed.mean()), "positions": len(reloc)},
            }
    out["best_windows"] = windows
    return out
