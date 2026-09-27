"""Synthetic 40k-path event-size demonstration for the proposed A4 patch.

No historical or validation returns are loaded. The uncapped comparator is
the erroneous use of a daily effective-N figure as an event count, *not* the
actual A4 calibrated-p procedure (which never consumes effective N).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.stats import norm


def main() -> None:
    paths, clusters, per_cluster = 40_000, 19, 8
    rho, daily_neff = .35, 2964.8634
    rng = np.random.default_rng(20260926)
    common = rng.normal(size=(paths, clusters, 1))
    idio = rng.normal(size=(paths, clusters, per_cluster))
    x = (rho ** .5 * common + (1 - rho) ** .5 * idio).reshape(paths, -1)
    m = x.shape[1]
    z_base = x.mean(axis=1) / x.std(axis=1, ddof=1)
    true_design_effect = 1 + (per_cluster - 1) * rho
    neff_event = m / true_design_effect
    centered = x - x.mean(axis=1, keepdims=True)
    variance = np.mean(centered * centered, axis=1)
    group_sums = centered.reshape(paths, clusters, per_cluster).sum(axis=2)
    cluster_d = np.maximum(1, (clusters / (clusters - 1)) *
                           np.sum(group_sums * group_sums, axis=1) / (m * variance))
    lags = round(m ** (1 / 3))
    lrv = variance.copy()
    for lag in range(1, lags + 1):
        lrv += 2 * (1 - lag / (lags + 1)) * np.mean(centered[:, lag:] * centered[:, :-lag], axis=1) * (m - lag) / m
    hac_d = np.maximum(1, lrv / variance)
    estimated_neff = m / np.maximum(cluster_d, hac_d)
    critical = norm.isf(.05)
    counts = {
        "uncapped_daily_N_as_events": int(np.count_nonzero(z_base * np.sqrt(daily_neff) > critical)),
        "event_count_only_cap": int(np.count_nonzero(z_base * np.sqrt(m) > critical)),
        "estimated_event_cluster_cap": int(np.count_nonzero(z_base * np.sqrt(estimated_neff) > critical)),
        "event_count_and_cluster_cap": int(np.count_nonzero(z_base * np.sqrt(neff_event) > critical)),
    }
    out = {"paths": paths, "seed": 20260926, "null": "zero mean Gaussian, 19 independent clusters of eight events, within-cluster ICC 0.35",
           "event_count": m, "daily_effective_n_proxy": daily_neff,
           "event_design_effect": true_design_effect, "event_effective_n_oracle": neff_event,
           "median_estimated_effective_n": float(np.median(estimated_neff)),
           "alpha": .05, "false_pass_counts": counts,
           "false_pass_rates": {k: v / paths for k, v in counts.items()},
           "note": "This demonstrates misuse of N in an event t; actual A4 calibrated p is independent of N and is not represented by the uncapped comparator."}
    target = Path("reports/sol_beyond_menu/event_n_simulation.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
