"""Shared helpers for the A1 audit. Synthetic data only."""
from __future__ import annotations

import json
import math
import os
import pathlib
import zlib

import numpy as np

OUT = pathlib.Path(__file__).resolve().parents[2] / "reports" / "power_audit_a1"
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(OUT / ".mpl"))
AUDIT_SEED = 55_2026_0925   # deliberately different from research.power.core.SEED


def rng(*salt) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([AUDIT_SEED, *[zlib.crc32(repr(s).encode()) for s in salt]]))


def ar1_paths(g: np.random.Generator, shape, phi: float) -> np.ndarray:
    """Stationary unit-variance AR(1) along axis 1, written with an explicit recursion (independent of lfilter)."""
    e = g.standard_normal(shape)
    if phi == 0:
        return e
    x = np.empty(shape)
    x[:, 0] = e[:, 0]
    c = math.sqrt(1 - phi * phi)
    for t in range(1, shape[1]):
        x[:, t] = phi * x[:, t - 1] + c * e[:, t]
    return x


def binom_se(p: float, n: int) -> float:
    return math.sqrt(max(p * (1 - p), 1e-12) / n)


def dump(name: str, obj) -> None:
    def clean(x):
        if isinstance(x, dict):
            return {str(k): clean(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [clean(v) for v in x]
        if hasattr(x, "item"):
            x = x.item()
        if isinstance(x, float) and not math.isfinite(x):
            return str(x)
        return x
    (OUT / name).write_text(json.dumps(clean(obj), indent=1))


def write_csv(name: str, rows: list[dict]) -> None:
    import csv
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(OUT / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()})
