"""Monte Carlo size of the structural development gate under zero-premium paths.

Synthetic, not a strategy backtest. Uses the production BootstrapP implementation.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from research.null_lab.gates import BootstrapP

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/structural_null_calibration_20260923"
SEED = 741953
WORLDS = 3000
N = 2016                 # eight development years
PER_YEAR = 252
BLOCK = 21


def sample(kind: str, rng: np.random.Generator) -> np.ndarray:
    if kind == "carry_crash":
        # Rare large negative days, offset by frequent positive compensation so E[r]=0.
        crash = rng.random((WORLDS, N)) < 0.005
        x = rng.normal(0, 1, (WORLDS, N)) + 12 * (0.005 - crash)
    elif kind == "long_only_active":
        # A common equity shock cancels in an exposure-matched comparison.
        common = rng.standard_t(5, (WORLDS, N))
        candidate = 0.65 * common + rng.normal(0, .6, (WORLDS, N))
        control = 0.65 * common
        x = candidate - control
    elif kind == "long_short":
        x = rng.standard_t(5, (WORLDS, N)) / np.sqrt(5/3)
    elif kind == "relative_value":
        noise = rng.normal(0, 1, (WORLDS, N + 1))
        x = noise[:, 1:] - 0.6 * noise[:, :-1]
    elif kind == "timing":
        innovation = rng.normal(0, 1, (WORLDS, N))
        x = np.zeros_like(innovation)
        for t in range(1, N):
            x[:, t] = .35 * x[:, t-1] + innovation[:, t]
    elif kind == "event":
        mask = rng.random((WORLDS, N)) < 0.05
        x = mask * rng.standard_t(4, (WORLDS, N)) / np.sqrt(2)
    else:
        raise ValueError(kind)
    # Net excess null: zero-mean *after* costs. A positive cost drag would lower false passes.
    return x.astype(np.float64)


def main():
    rng = np.random.default_rng(SEED)
    boot = BootstrapP(N, BLOCK, draws=3000, seed=20260923)
    gate = 1.8 / np.sqrt(N / PER_YEAR)
    rows = []
    for kind in ("carry_crash", "long_only_active", "long_short", "relative_value", "timing", "event"):
        family_pass = []
        for sibling in range(3):
            x = sample(kind, rng)
            sr = x.mean(axis=1) / x.std(axis=1, ddof=1) * np.sqrt(PER_YEAR)
            eligible = sr >= gate
            # BootstrapP performs the exact circular-block p algorithm, batched.
            p = np.ones(WORLDS)
            p[eligible] = boot.pvalues(x[eligible])
            pass_single = eligible & (p < .05)
            pass_three = eligible & (p < .05/3)
            family_pass.append(pass_three)
            if sibling == 0:
                first = (sr.copy(), eligible.copy(), pass_single.copy(), pass_three.copy())
        sr, eligible, pass_single, pass_three = first
        any_three = np.stack(family_pass).any(axis=0)
        rows.append({"archetype": kind, "worlds": WORLDS, "gate_sharpe": float(gate),
                     "p_sharpe_only": float(eligible.mean()),
                     "p_full_single_alpha_0_05": float(pass_single.mean()),
                     "p_full_batch3_alpha_0_0167": float(pass_three.mean()),
                     "mc_se_batch3": float(np.sqrt(pass_three.mean()*(1-pass_three.mean())/WORLDS)),
                     "p_any_of_three_independent_null_siblings": float(any_three.mean()),
                     "mc_se_any_three": float(np.sqrt(any_three.mean()*(1-any_three.mean())/WORLDS)),
                     "median_null_sharpe": float(np.median(sr)),
                     "null_sharpe_p95": float(np.quantile(sr, .95))})
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"seed": SEED, "periods": N, "block": BLOCK, "bootstrap_draws": 3000,
              "note": "Zero-mean after-cost archetypes; family result uses three independent siblings per world. The structural plan used 5000 bootstrap draws.",
              "rows": rows}
    (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
