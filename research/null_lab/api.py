"""Reusable null-world API: "how often does this pipeline pass when there is no edge?"

    from research.null_lab.api import run_null, builders
    from research.null_lab.engines import CountryEngine
    from research.null_lab.gates import Gate

    eng = CountryEngine()
    sig = builders.shift(eng.real_signal(), min_offset=12)      # (a) circular shift, >= 12 months
    res = run_null(sig, eng, Gate(k=2), n_worlds=2000, seed=1)
    res["candidate"]["p_pass_dev"], res["candidate"]["p_pass_both"], res["family"]["p_any_pass_both"]

A *signal builder* is any callable (rng, n) -> n null signal arrays shaped like the engine's signal
grid ((n, K, N) for panel engines, (n, D) for timing engines). A *path builder* (optional) is
(rng, n) -> (n, D-1) source-day indices (stationary bootstrap of whole dates); None = the realised
price path. An *engine* has .run(signals, paths) -> {(window, cost): (n, T) returns} and .periods.

Each world is a family: `family_size - 1` independent null candidates plus (by default) their
composite (mean cross-sectional rank, or mean position for timing), all on the same return path.
"Per candidate" statistics use the first candidate of each world (independent across worlds);
pooled statistics over the independent candidates are also reported with world-clustered errors.
"""
from __future__ import annotations

import time
from typing import Callable

import numpy as np

from research.null_lab import generators as G
from research.null_lab.gates import Gate


# ==================================================================================================
# builders
# ==================================================================================================
class builders:
    """Factories for signal and path builders."""

    @staticmethod
    def shift(real: np.ndarray, min_offset: int) -> Callable:
        """(a) circular shift of the real panel/series by a uniform offset in [m, T - m]."""
        real = np.asarray(real, float)
        if real.ndim == 1:
            return _shift_series(real, min_offset)

        def f(rng, n):
            offs = G.draw_offsets(real.shape[0], min_offset, n, rng)
            return np.stack([G.circular_shift(real, int(o), min_offset) for o in offs])
        f.describe = f"circular shift >= {min_offset} periods"
        return f

    @staticmethod
    def ar1(real: np.ndarray, long_lag: int | None = None) -> Callable:
        """(b) per-asset AR(1) (+ fixed effect when long_lag given) with the real panel's lag-1 (and
        lag-`long_lag`) cross-sectional rank autocorrelation; the real NaN mask is re-applied."""
        real = np.asarray(real, float)
        rho1 = G.rank_autocorr(real, 1)
        rhoL = G.rank_autocorr(real, long_lag) if long_lag else None
        phi, s = G.match_persistence(rho1, rhoL, long_lag or 12)
        T, N = real.shape

        def f(rng, n):
            return G.apply_mask(G.ar1_panel(T, N, phi, rng, fe_share=s, worlds=n), real)
        f.describe = f"AR(1) phi={phi:.3f} fixed-effect share={s:.3f} (real rank autocorr lag1={rho1:.3f}" + \
            (f", lag{long_lag}={rhoL:.3f})" if long_lag else ")")
        f.params = {"phi": phi, "fe_share": s, "rho1_real": rho1, "rhoL_real": rhoL}
        return f

    @staticmethod
    def ar1_series(real: np.ndarray, kind: str) -> Callable:
        """(b) for single-asset timing. kind 'binary01' (in/out), 'sign' (+-1) or 'continuous'."""
        real = np.asarray(real, float)
        ok = np.isfinite(real)
        x = real[ok]
        rho1 = G.series_autocorr(real, 1)
        if kind == "continuous":
            phi = rho1
            mu, sd = x.mean(), x.std()

            def f(rng, n):
                z = G.ar1_panel(len(real), 1, phi, rng, worlds=n)[:, :, 0]
                return mu + sd * z
        else:
            hi = 1.0
            lo = 0.0 if kind == "binary01" else -1.0
            p_in = float(np.mean(x == hi))
            phi = G.binary_phi_for_switch_rate(p_in, rho1)
            from scipy.stats import norm
            q = norm.ppf(1 - p_in)

            def f(rng, n):
                z = G.ar1_panel(len(real), 1, phi, rng, worlds=n)[:, :, 0]
                return np.where(z > q, hi, lo)
        f.describe = f"AR(1) latent phi={phi:.4f} matched to lag-1 autocorr {rho1:.4f} ({kind})"
        f.params = {"phi": phi, "rho1_real": rho1}
        return f

    @staticmethod
    def permute(real: np.ndarray) -> Callable:
        """(c) within-date cross-sectional permutation (non-NaN slots)."""
        real = np.asarray(real, float)

        def f(rng, n):
            return np.stack([G.permute_cross_section(real, rng) for _ in range(n)])
        f.describe = "within-date cross-sectional permutation"
        return f

    @staticmethod
    def bootstrap_paths(n_days: int, mean_block: float, split: int | None = None) -> Callable:
        """(d) stationary bootstrap of whole dates over the engine calendar. With `split` (the last
        calendar index of the development region), days 0..split are resampled only from days
        1..split and later days only from later days, so each window keeps its own drift and
        volatility regime while the path itself is new."""
        def f(rng, n):
            if split is None:
                return G.stationary_bootstrap(n_days - 1, n_days, mean_block, rng, worlds=n)
            a = G.stationary_bootstrap(split, split + 1, mean_block, rng, worlds=n)
            m = n_days - 1 - split
            b = G.stationary_bootstrap(m, m, mean_block, rng, worlds=n) + split
            return np.concatenate([a, b], axis=1)
        f.describe = f"stationary bootstrap of whole dates, mean block {mean_block}" + \
            (", resampled within dev / within val" if split is not None else "")
        return f


def _shift_series(real: np.ndarray, m: int) -> Callable:
    first = int(np.flatnonzero(np.isfinite(real))[0])
    seg = real[first:]
    L = len(seg)
    if np.isnan(seg).any():
        raise ValueError("series has interior gaps")
    t = np.arange(len(real))

    def f(rng, n):
        offs = G.draw_offsets(L, m, n, rng)
        return np.stack([seg[(t - first - o) % L] for o in offs])
    f.describe = f"circular shift of the finite segment >= {m} periods"
    return f


# ==================================================================================================
# composite
# ==================================================================================================
def composite(sigs: list[np.ndarray]) -> np.ndarray:
    """Panels: mean cross-sectional percentile rank, NaN with < 2 inputs (options H4 rule).
    Series: mean position."""
    if sigs[0].ndim == 2:
        return np.mean(sigs, axis=0)
    ranks = []
    for s in sigs:
        r = np.argsort(np.argsort(np.where(np.isfinite(s), s, np.inf), axis=-1, kind="stable"), axis=-1, kind="stable") + 1.0
        n = np.isfinite(s).sum(-1, keepdims=True)
        with np.errstate(invalid="ignore", divide="ignore"):
            ranks.append(np.where(np.isfinite(s), r / n, np.nan))
    st = np.stack(ranks)
    cnt = np.isfinite(st).sum(0)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        m = np.nanmean(st, axis=0)
    m[cnt < 2] = np.nan
    return m


# ==================================================================================================
# run_null
# ==================================================================================================
def _prob(x: np.ndarray) -> dict:
    x = np.asarray(x, bool)
    p = float(x.mean())
    return {"p": p, "se": float(np.sqrt(max(p * (1 - p), 1e-12) / len(x))), "n": int(len(x))}


def _clustered(x: np.ndarray) -> dict:
    """x (W, c) booleans; mean with world-clustered SE."""
    per = x.mean(axis=1)
    return {"p": float(per.mean()), "se": float(per.std(ddof=1) / np.sqrt(len(per))), "n": int(x.size)}


def _dist(x: np.ndarray, years: float) -> dict:
    x = x[np.isfinite(x)]
    q = np.quantile(x, [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    sd = float(x.std(ddof=1))
    return {"mean": float(x.mean()), "sd": sd, "sd_x_sqrt_years": sd * np.sqrt(years),
            "q01": q[0], "q05": q[1], "q25": q[2], "q50": q[3], "q75": q[4], "q95": q[5], "q99": q[6],
            "mean_se": sd / np.sqrt(len(x)), "n": int(len(x))}


def run_null(signal_builder: Callable, engine, gate: Gate, n_worlds: int, seed: int,
             path_builder: Callable | None = None, family_size: int = 4, with_composite: bool = True,
             chunk: int = 500, horizons: tuple = (), dev_only: bool = False) -> dict:
    """Run `n_worlds` null families through `engine` and `gate`. Returns summary + raw arrays."""
    rng = np.random.default_rng(seed)
    n_ind = family_size - 1 if with_composite else family_size
    t0 = time.time()
    per_cand = []
    done = 0
    while done < n_worlds:
        n = min(chunk, n_worlds - done)
        paths = path_builder(rng, n) if path_builder is not None else None
        sigs = [signal_builder(rng, n) for _ in range(n_ind)]
        if with_composite:
            sigs.append(composite(sigs))
        rows = []
        for s in sigs:
            out = engine.run(s, paths)
            rows.append(gate.evaluate(out, engine.periods,
                                      windows=("dev",) if dev_only else ("dev", "val"),
                                      horizons=horizons))
        per_cand.append(rows)
        done += n
    # stack: arrays (W, family)
    keys = per_cand[0][0].keys()
    arr = {}
    for k in keys:
        v = [np.stack([rows[c][k] for c in range(len(rows))], axis=1) if np.ndim(rows[0][k]) else None
             for rows in per_cand]
        if v[0] is not None:
            arr[k] = np.concatenate(v, axis=0)
        else:
            arr[k] = per_cand[0][0][k]
    yd, yv = arr["years_dev"], arr.get("years_val")
    c0 = {k: v[:, 0] for k, v in arr.items() if isinstance(v, np.ndarray)}
    candidate = {
        "p_pass_dev": _prob(c0["pass_dev"]),
        "p_sharpe_dev_ge_gate": _prob(c0["sr_dev"] >= gate.dev_sharpe),
        "sr_dev": _dist(c0["sr_dev"], yd),
    }
    pooled = {"p_pass_dev": _clustered(arr["pass_dev"][:, :n_ind])}
    family = {"p_any_pass_dev": _prob(arr["pass_dev"].any(axis=1)),
              "mean_dev_passes": float(arr["pass_dev"].sum(axis=1).mean())}
    if not dev_only:
        candidate.update({
            "p_pass_val_gate": _prob(c0["pass_val"]),
            "p_pass_both": _prob(c0["pass_both"]),
            "p_val_given_dev": _prob(c0["pass_val"][c0["pass_dev"]]) if c0["pass_dev"].any() else None,
            "p_sharpe_val_ge_gate": _prob(c0["sr_val"] >= gate.val_sharpe),
            "sr_val": _dist(c0["sr_val"], yv),
            "corr_dev_val": float(np.corrcoef(c0["sr_dev"], c0["sr_val"])[0, 1]),
            "mean_val_sr_given_dev_pass": float(np.mean(c0["sr_val"][c0["pass_dev"]])) if c0["pass_dev"].any() else None,
        })
        pooled["p_pass_both"] = _clustered(arr["pass_both"][:, :n_ind])
        family["p_any_pass_both"] = _prob(arr["pass_both"].any(axis=1))
    res = {
        "n_worlds": int(n_worlds), "seed": int(seed), "family_size": family_size,
        "with_composite": with_composite, "seconds": round(time.time() - t0, 1),
        "signal": getattr(signal_builder, "describe", str(signal_builder)),
        "path": getattr(path_builder, "describe", "realised price path") if path_builder else "realised price path",
        "engine": engine.name,
        "gate": {"dev_sharpe": gate.dev_sharpe, "val_sharpe": gate.val_sharpe, "alpha": gate.alpha, "k": gate.k,
                 "block": gate.block, "draws": gate.draws},
        "years_dev": yd, "years_val": yv,
        "candidate": candidate,
        "pooled_independent": pooled,
        "family": family,
    }
    if with_composite:
        res["composite"] = {"p_pass_dev": _prob(arr["pass_dev"][:, -1]),
                            "sr_dev": _dist(arr["sr_dev"][:, -1], yd)}
        if not dev_only:
            res["composite"]["p_pass_both"] = _prob(arr["pass_both"][:, -1])
    hz = {}
    for k in arr:
        if k.startswith("sr_") and "_h" in k:
            wn, h = k[3:].split("_h")
            sr = arr[k][:, :n_ind].ravel()
            sm = arr[f"stress_mean_{wn}_h{h}"][:, :n_ind].ravel()
            d = _dist(sr, float(h))
            d["p_dev_gate"] = float(np.mean((sr >= gate.dev_sharpe) & (sm > 0)))
            d["p_sr_ge_dev_gate"] = float(np.mean(sr >= gate.dev_sharpe))
            d["p_stress_positive"] = float(np.mean(sm > 0))
            hz.setdefault(wn, {})[h] = d
    res["horizons"] = hz
    res["arrays"] = {k: v for k, v in arr.items() if isinstance(v, np.ndarray)}
    return res
