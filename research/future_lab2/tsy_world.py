"""Six explicit forward worlds for tsy_month_end_v1 (book M: TLT over the last 3 sessions of each
calendar month, T-bills otherwise; frozen spec research/forward_audit/tsy_month_end_v1_spec.json).

Unit of observation: one WINDOW per calendar month (~12/year), so "1 look" = "1 month" = "1 window"
throughout this module -- there is no daily granularity to add, because the whole point of book M
is that nothing happens outside the window.

Historical pool: reports/audit_tsy/c_months_{dev,val}.csv, column `win_ex` (window return in excess
of the T-bill accrued over the same 3 sessions; GROSS of the frozen spec's trading cost -- this
reproduces reports/audit_tsy/e_postpub.json's `window_ex` figures exactly, see tests). Costs are
applied here explicitly: base 2 bp/side, so BASE_COST_PER_WINDOW = 2 sides x 2 bp = 4 bp; the W5
cost-shock world adds a further 2 sides x 5 bp = 10 bp on top of that.

`pre` = 2003-01 .. 2019-09 (development + validation-before-2019-10); `post` = 2019-10 .. 2026-08,
the only stretch that postdates publication (Hartley & Schwarz, SSRN Aug 2019; AllocateSmartly,
Oct 2019 -- see reports/audit_tsy/REPORT.md section 6).

Worlds (all net of BASE_COST_PER_WINDOW unless noted):
  W0  null              -- gross edge exactly zero; block-bootstrap of the demeaned full-history
                            pool, net mean forced to -BASE_COST_PER_WINDOW (cost is still paid).
  W1  pre-pub strength   -- block-bootstrap of the `pre` pool as observed (net of base cost).
  W2  post-pub strength  -- block-bootstrap of the `post` pool as observed (net of base cost).
  W3  continuing decay   -- `post` pool's own (demeaned) shape/vol, with its mean decayed linearly
                            from the W2 net mean down to the W0 null net mean over 60 months, flat
                            thereafter.
  W4  regime shift       -- full-history pool, net mean unchanged, deviations from that mean scaled
                            x1.5 (vol x1.5). The stock-bond correlation flip is not separately
                            modelled here (see LIMITATIONS in run.py / the report): book M's own
                            series carries no explicit equity leg, and 2022 -- the actual
                            correlation-flip year -- was empirically one of the strategy's better
                            validation years (reports/audit_tsy/REPORT.md section 6), so a flip is
                            not assumed to hurt the mean.
  W5  cost shock         -- `post` pool net of BASE_COST_PER_WINDOW *and* the extra 10 bp/window
                            (2 sides x 5 bp) shock.

All resampling uses research.future_lab.engines.stationary_indices (Politis-Romano stationary
bootstrap, geometric blocks, expected length from Politis-White on each pool). No IID Gaussian
draws anywhere; every simulated window is a real historical window, possibly re-centred or rescaled.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from research.future_lab import engines as E

ROOT = Path(__file__).resolve().parents[2]
AUDIT_DIR = ROOT / "reports" / "audit_tsy"
SPEC_PATH = ROOT / "research" / "forward_audit" / "tsy_month_end_v1_spec.json"

BASE_COST_PER_SIDE = 2e-4       # frozen spec costs_bps_per_side.base = 2 bp
SHOCK_COST_PER_SIDE = 5e-4      # W5: "+5 bp per side"
SIDES = 2                       # entry + exit
BASE_COST_PER_WINDOW = SIDES * BASE_COST_PER_SIDE     # 4 bp
W5_EXTRA_PER_WINDOW = SIDES * SHOCK_COST_PER_SIDE      # 10 bp, additional to BASE_COST_PER_WINDOW
PUB_CUTOFF = "2019-10"          # Hartley & Schwarz Aug 2019 / AllocateSmartly Oct 2019
DECAY_MONTHS = 60               # W3: linear decay to the null level over 5 years

WORLDS = ("W0", "W1", "W2", "W3", "W4", "W5")
WORLD_LABEL = {
    "W0": "null (gross edge exactly zero)",
    "W1": "pre-publication strength continues",
    "W2": "post-publication strength continues",
    "W3": "continuing decay to zero over 5 years",
    "W4": "regime shift: window-return vol x1.5, mean unchanged",
    "W5": "cost shock: +5 bp/side on top of the post-publication world",
}
# Ground truth used to label SPRT/rule outcomes as correct/false (see rule.py, run.py).
WORLD_HAS_EDGE = {"W0": False, "W1": True, "W2": True, "W3": "decaying", "W4": True, "W5": True}


def load_window_history() -> pd.DataFrame:
    """One row per calendar month, 2003-01 .. 2026-08 (284 months), from the independent audit's
    month-level reconstruction (reports/audit_tsy/c_months_{dev,val}.csv). `win_ex` reproduces
    reports/audit_tsy/e_postpub.json's window_ex mean/t exactly on both sub-periods (tested)."""
    dev = pd.read_csv(AUDIT_DIR / "c_months_dev.csv")
    val = pd.read_csv(AUDIT_DIR / "c_months_val.csv")
    c = pd.concat([dev, val], ignore_index=True).drop_duplicates("month").sort_values("month")
    c = c.reset_index(drop=True)
    c["period"] = np.where(c["month"] < PUB_CUTOFF, "pre", "post")
    return c


def pools() -> dict[str, np.ndarray]:
    c = load_window_history()
    return {
        "all": c["win_ex"].to_numpy(dtype=float),
        "pre": c.loc[c["period"] == "pre", "win_ex"].to_numpy(dtype=float),
        "post": c.loc[c["period"] == "post", "win_ex"].to_numpy(dtype=float),
    }


def block_lengths(pl: dict[str, np.ndarray]) -> dict[str, float]:
    """Politis-White expected stationary-bootstrap block length (months) for each pool."""
    return {k: max(E.politis_white(v)["sb"], 1.0) for k, v in pl.items()}


def world_means(pl: dict[str, np.ndarray]) -> dict[str, float]:
    """Net-of-base-cost means that anchor each world (bp figures reproduce e_postpub.json before
    the cost subtraction)."""
    return {
        "mu0_null_net": -BASE_COST_PER_WINDOW,
        "mu_pre_net": float(pl["pre"].mean() - BASE_COST_PER_WINDOW),
        "mu_post_net": float(pl["post"].mean() - BASE_COST_PER_WINDOW),
        "mu_all_net": float(pl["all"].mean() - BASE_COST_PER_WINDOW),
        "mu_post_net_w5": float(pl["post"].mean() - BASE_COST_PER_WINDOW - W5_EXTRA_PER_WINDOW),
    }


def simulate(world: str, n_paths: int, horizon: int, seed: int, pl: dict | None = None,
            blocks: dict | None = None) -> np.ndarray:
    """Simulated net-of-base-cost window excess returns, shape (n_paths, horizon) in months."""
    pl = pl or pools()
    blocks = blocks or block_lengths(pl)
    all_g, pre_g, post_g = pl["all"], pl["pre"], pl["post"]
    mu0 = -BASE_COST_PER_WINDOW

    if world == "W0":
        dev = all_g - all_g.mean()
        idx = E.stationary_indices(len(dev), n_paths, horizon, blocks["all"], seed)
        return dev[idx] + mu0
    if world == "W1":
        idx = E.stationary_indices(len(pre_g), n_paths, horizon, blocks["pre"], seed)
        return pre_g[idx] - BASE_COST_PER_WINDOW
    if world == "W2":
        idx = E.stationary_indices(len(post_g), n_paths, horizon, blocks["post"], seed)
        return post_g[idx] - BASE_COST_PER_WINDOW
    if world == "W3":
        dev = post_g - post_g.mean()
        idx = E.stationary_indices(len(dev), n_paths, horizon, blocks["post"], seed)
        mu_post_net = float(post_g.mean() - BASE_COST_PER_WINDOW)
        t = np.arange(1, horizon + 1)
        frac = np.clip(1.0 - t / DECAY_MONTHS, 0.0, None)
        mean_t = mu0 + (mu_post_net - mu0) * frac
        return dev[idx] + mean_t[None, :]
    if world == "W4":
        dev = all_g - all_g.mean()
        idx = E.stationary_indices(len(dev), n_paths, horizon, blocks["all"], seed)
        mu_all_net = float(all_g.mean() - BASE_COST_PER_WINDOW)
        return mu_all_net + 1.5 * dev[idx]
    if world == "W5":
        idx = E.stationary_indices(len(post_g), n_paths, horizon, blocks["post"], seed)
        return post_g[idx] - BASE_COST_PER_WINDOW - W5_EXTRA_PER_WINDOW
    raise ValueError(world)
