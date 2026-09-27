"""Researcher degrees of freedom on null data: pick the best of k construction variants in development.

    PYTHONPATH=. .venv/bin/python -m research.null_lab.dof [--worlds 1000]

For each null world one null signal is drawn (circular shift of a real signal). A grid of 36
construction variants is built from it; for k in (1, 4, 10, 25) a random subset of k variants is
"tried" and the one with the best development net Sharpe is kept, exactly as a researcher would. We
record that variant's development Sharpe (in-sample inflation), whether it clears the development
gate, and what it does in the later, untouched window.

Variants use the engines' own accounting (StockEngine.backtest, CountryEngine.simulate); only the
book construction changes:
  stock  : quantile {3, 5, 10} x signal smoothing {1, 4, 13} weeks x weights {equal, rank}
           x rebalance every {1, 4} weeks (drifted book held in between)
  country: smoothing {1, 2, 3} months x legs {n//4, n//3, n//2} x weights {inverse-vol, equal}
           x rebalance every {1, 2} months
"""
from __future__ import annotations

import argparse
import itertools
import json
import time
from pathlib import Path

import numpy as np

from research.null_lab import engines as E
from research.null_lab import generators as G
from research.null_lab.engines import sharpe, stable_ranks
from research.null_lab.gates import Gate

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "null_lab"
KS = (1, 4, 10, 25)


def smooth(x: np.ndarray, m: int) -> np.ndarray:
    """Trailing mean over the last m grid points along axis 1 (NaN-aware; NaN if none)."""
    if m == 1:
        return x
    f = np.isfinite(x)
    v = np.where(f, x, 0.0)
    cs = np.concatenate([np.zeros_like(v[:, :1]), np.cumsum(v, axis=1)], axis=1)
    cn = np.concatenate([np.zeros_like(v[:, :1]), np.cumsum(f, axis=1)], axis=1)
    s = cs[:, m:] - cs[:, :-m]
    n = cn[:, m:] - cn[:, :-m]
    head_s, head_n = cs[:, 1:m], cn[:, 1:m]
    s = np.concatenate([head_s, s], axis=1)
    n = np.concatenate([head_n, n], axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, s / n, np.nan)


# ---------------------------------------------------------------------------------------------------
# stock variants
# ---------------------------------------------------------------------------------------------------
def stock_weights(score: np.ndarray, q: int, weighting: str, min_names: int = 25) -> np.ndarray:
    ranks, n = stable_ranks(score)
    lo = np.zeros(n.shape)
    hi = np.zeros(n.shape)
    for u in np.unique(n):
        if u >= 1:
            e = np.quantile(np.arange(1, u + 1, dtype=float), [1 / q, 1 - 1 / q])
            lo[n == u], hi[n == u] = e
    fin = np.isfinite(score)
    bot = fin & (ranks <= lo[..., None])
    top = fin & (ranks > hi[..., None])
    if weighting == "equal":
        wt, wb = top.astype(float), bot.astype(float)
    else:
        wt = np.where(top, ranks - hi[..., None], 0.0)
        wb = np.where(bot, lo[..., None] + 1 - ranks, 0.0)
    st, sb = wt.sum(-1, keepdims=True), wb.sum(-1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        w = np.where(st > 0, wt / st, 0.0) - np.where(sb > 0, wb / sb, 0.0)
    return np.where((n >= min_names)[..., None], w, 0.0)


def hold(weights: np.ndarray, R: np.ndarray, every: int) -> np.ndarray:
    """Rebalance to target every `every` periods; in between carry the drifted book (no trades)."""
    if every == 1:
        return weights
    out = weights.copy()
    Rb = np.broadcast_to(R, weights.shape)
    for k in range(1, weights.shape[1]):
        if k % every:
            pw, pr = out[:, k - 1], Rb[:, k - 1]
            g = (pw * pr).sum(-1, keepdims=True)
            has = np.abs(pw).sum(-1, keepdims=True) > 0
            with np.errstate(invalid="ignore", divide="ignore"):
                out[:, k] = np.where(has, pw * (1 + pr) / (1 + g), pw)
    return out


def stock_variant_returns(eng: E.StockEngine, sig: np.ndarray, variants: list, R: dict) -> dict:
    """{variant index: {(window, cost): (W, K)}}"""
    res = {}
    cache = {}
    for vi, (q, m, wt, every) in enumerate(variants):
        if m not in cache:
            cache[m] = smooth(sig, m)
        w_all = stock_weights(cache[m], q, wt)
        out = {}
        for wn in ("dev", "val"):
            w = hold(w_all[:, eng.windows[wn]["sig_idx"]], R[wn], every)
            for cn in ("base", "stress"):
                out[(wn, cn)] = eng.backtest(w, R[wn], wn, eng.ev.COSTS[cn])
        res[vi] = out
    return res


# ---------------------------------------------------------------------------------------------------
# country variants
# ---------------------------------------------------------------------------------------------------
def country_weights(score: np.ndarray, vol: np.ndarray, legs: str, weighting: str) -> np.ndarray:
    ranks, n = stable_ranks(score)
    k = {"n4": n // 4, "n3": n // 3, "n2": n // 2}[legs]
    fin = np.isfinite(score)
    top = fin & (ranks > (n - k)[..., None])
    bot = fin & (ranks <= k[..., None])
    base = 1.0 / np.broadcast_to(vol, score.shape) if weighting == "invvol" else np.ones(score.shape)
    wt, wb = np.where(top, base, 0.0), np.where(bot, base, 0.0)
    st, sb = wt.sum(-1, keepdims=True), wb.sum(-1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        w = np.where(st > 0, wt / st, 0.0) - np.where(sb > 0, wb / sb, 0.0)
    return np.where(((k >= 1) & (n >= 3))[..., None], w, 0.0)


def country_variant_returns(eng: E.CountryEngine, sig: np.ndarray, variants: list) -> dict:
    O, C = eng.prices(None, sig.shape[0])
    vol = eng.vol_at_signals(C)
    res = {}
    cache = {}
    for vi, (m, legs, wt, every) in enumerate(variants):
        if m not in cache:
            cache[m] = smooth(sig, m)
        w_all = country_weights(cache[m], vol, legs, wt)
        out = {}
        for wn in ("dev", "val"):
            win = eng.windows[wn]
            keep = np.arange(len(win.sig_idx)) % every == 0
            sub = E.Window(wn, win.sig_idx[keep], win.entry_day[keep], win.end_day)
            for cn in ("base", "stress"):
                out[(wn, cn)] = eng.simulate(w_all[:, sub.sig_idx], O, C, sub, eng.ev.COSTS[cn])
        res[vi] = out
    return res


# ---------------------------------------------------------------------------------------------------
def select(results: dict, gate: Gate, periods: int, rng: np.random.Generator, n_variants: int) -> dict:
    """results {vi: gate.evaluate output}; returns per-k selection statistics."""
    W = len(results[0]["sr_dev"])
    sr_dev = np.stack([results[v]["sr_dev"] for v in range(n_variants)], axis=1)       # (W, V)
    out = {"variant_sr_dev_mean": float(np.nanmean(sr_dev)), "variant_sr_dev_sd": float(np.nanstd(sr_dev)),
           "mean_pairwise_corr_dev_sr_across_variants": float(np.nanmean(np.corrcoef(sr_dev.T)[np.triu_indices(n_variants, 1)]))}
    for k in KS:
        pick = np.stack([rng.choice(n_variants, size=k, replace=False) for _ in range(W)])
        cand_sr = np.take_along_axis(sr_dev, pick, axis=1)
        best = pick[np.arange(W), np.nanargmax(cand_sr, axis=1)]

        def g(key):
            return np.array([results[b][key][i] for i, b in enumerate(best)])
        sd, sv = g("sr_dev"), g("sr_val")
        pdv, pb = g("pass_dev").astype(bool), g("pass_both").astype(bool)
        pv05 = (sv >= gate.val_sharpe) & (g("stress_mean_val") > 0) & (np.nan_to_num(g("p_val"), nan=1) < 0.05)
        out[f"k{k}"] = {
            "best_dev_sr_mean": float(sd.mean()), "best_dev_sr_q50": float(np.median(sd)),
            "best_dev_sr_q95": float(np.quantile(sd, 0.95)),
            "inflation_vs_k1": None,
            "p_best_passes_dev": float(pdv.mean()), "p_best_passes_dev_se": float(np.sqrt(pdv.mean() * (1 - pdv.mean()) / W)),
            "best_val_sr_mean": float(sv.mean()), "best_val_sr_mean_given_dev_pass": float(sv[pdv].mean()) if pdv.any() else None,
            "p_pass_both_alpha_0125": float(pb.mean()),
            "p_pass_both_alpha_05": float((pdv & pv05).mean()),
            "p_val_gate_given_dev_pass_alpha_05": float(pv05[pdv].mean()) if pdv.any() else None,
            "n_worlds": W,
        }
    for k in KS:
        out[f"k{k}"]["inflation_vs_k1"] = out[f"k{k}"]["best_dev_sr_mean"] - out["k1"]["best_dev_sr_mean"]
    return out


def run(worlds: int = 1000, seed: int = 555, chunk: int = 125) -> dict:
    rng = np.random.default_rng(seed)
    report = {}
    # ---------------- stock --------------------------------------------------------------------
    se = E.StockEngine()
    real = se.price_signal("mom_12_1")
    sv = list(itertools.product((3, 5, 10), (1, 4, 13), ("equal", "rank"), (1, 4)))
    gate_s = Gate(k=4, block=8, seed=20260918)
    Rw = {wn: se.period_returns(None, wn) for wn in ("dev", "val")}
    for label, make in (("stock_shift_mom", lambda n: np.stack([G.circular_shift(real, int(o), 64)
                                                                   for o in G.draw_offsets(real.shape[0], 64, n, rng)])),
                        ("stock_ar1_phi0.8_fe0.2", lambda n: G.ar1_panel(real.shape[0], real.shape[1], 0.8, rng,
                                                                          fe_share=0.2, worlds=n))):
        t0 = time.time()
        acc = {v: [] for v in range(len(sv))}
        done = 0
        while done < worlds:
            n = min(chunk, worlds - done)
            sig = make(n)
            out = stock_variant_returns(se, sig, sv, Rw)
            for v, o in out.items():
                acc[v].append(gate_s.evaluate(o, se.periods))
            done += n
        res = {v: {k: np.concatenate([r[k] for r in rows]) for k in rows[0] if np.ndim(rows[0][k])}
               for v, rows in acc.items()}
        report[label] = select(res, gate_s, se.periods, rng, len(sv))
        report[label]["variants"] = [list(map(str, x)) for x in sv]
        report[label]["seconds"] = round(time.time() - t0, 1)
        print(label, json.dumps({k: report[label][k] for k in ("k1", "k4", "k10", "k25")}, default=float)[:900], flush=True)
    # ---------------- country ------------------------------------------------------------------
    ce = E.CountryEngine()
    realc = ce.real_signal()
    cv = list(itertools.product((1, 2, 3), ("n4", "n3", "n2"), ("invvol", "equal"), (1, 2)))
    gate_c = Gate(k=4, block=21, seed=20260923)
    t0 = time.time()
    acc = {v: [] for v in range(len(cv))}
    done = 0
    while done < worlds:
        n = min(500, worlds - done)
        sig = np.stack([G.circular_shift(realc, int(o), 12) for o in G.draw_offsets(realc.shape[0], 12, n, rng)])
        out = country_variant_returns(ce, sig, cv)
        for v, o in out.items():
            acc[v].append(gate_c.evaluate(o, ce.periods))
        done += n
    res = {v: {k: np.concatenate([r[k] for r in rows]) for k in rows[0] if np.ndim(rows[0][k])} for v, rows in acc.items()}
    report["country_shift"] = select(res, gate_c, ce.periods, rng, len(cv))
    report["country_shift"]["variants"] = [list(map(str, x)) for x in cv]
    report["country_shift"]["seconds"] = round(time.time() - t0, 1)
    print("country_shift", json.dumps({k: report["country_shift"][k] for k in ("k1", "k4", "k10", "k25")}, default=float)[:900], flush=True)
    report["meta"] = {"worlds": worlds, "seed": seed, "ks": KS,
                      "val_gate": "Sharpe >= 0.75, stress mean > 0, bootstrap p < alpha (0.05/4 and 0.05 shown)",
                      "dev_gate": "Sharpe >= 0.5, stress mean > 0"}
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worlds", type=int, default=1000)
    a = ap.parse_args()
    rep = run(a.worlds)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dof.json").write_text(json.dumps(rep, indent=1, default=float))


if __name__ == "__main__":
    main()
