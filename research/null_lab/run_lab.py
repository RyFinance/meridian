"""Run the null-world calibration grid through the project's engines and gates.

    PYTHONPATH=. .venv/bin/python -m research.null_lab.run_lab [--worlds 4000] [--workers 3] [--only C1,S1]

Writes reports/null_lab/worlds/<config>.json (summary) and <config>.npz (per-world, per-candidate
Sharpes, stress means and pass flags). Every config is seeded from its position in CONFIGS.
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "null_lab" / "worlds"
BASE_SEED = 20260923

# min circular-shift offsets: >= 12 months AND >= signal lookback + holding period + margin, so a
# "lead" shift cannot put the holding-period return inside the signal's own look-back window.
MIN_OFF = {"country": 12,            # months (91-day look-back, 1-month hold)
           "stock_mom": 64,          # weeks (12-1 momentum: 52-week look-back + 1-week hold + margin)
           "stock_rev": 52,          # weeks (21-day look-back)
           "daily_252": 315,         # days  (252-day look-back + 21-day hold + margin)
           "daily_r2": 252}          # days  (R2 drift since last reset; short memory)

CONFIGS = [
    # id, engine, signal, path
    ("C1", "country", "shift", "real"), ("C2", "country", "shift", "boot"),
    ("C3", "country", "ar1", "real"), ("C4", "country", "ar1", "boot"),
    ("C5", "country", "perm", "real"), ("C6", "country", "perm", "boot"),
    ("S1", "stock", "shift_mom", "real"), ("S2", "stock", "shift_mom", "boot"),
    ("S3", "stock", "shift_rev", "real"), ("S4", "stock", "shift_rev", "boot"),
    ("S5", "stock", "ar1_mom", "real"), ("S6", "stock", "ar1_mom", "boot"),
    ("S7", "stock", "perm_mom", "real"),
    ("T1", "spy_cash", "shift_tsmom", "real"), ("T2", "spy_cash", "shift_tsmom", "boot"),
    ("T3", "spy_cash", "ar1_tsmom", "real"), ("T4", "spy_cash", "ar1_tsmom", "boot"),
    ("A1", "spy_cash_active", "shift_tsmom", "real"), ("A2", "spy_cash_active", "shift_tsmom", "boot"),
    ("A3", "spy_cash_active", "ar1_tsmom", "real"), ("A4", "spy_cash_active", "ar1_tsmom", "boot"),
    ("I1", "spy_ief", "shift_r2", "real"), ("I2", "spy_ief", "shift_r2", "boot"),
    ("I3", "spy_ief", "ar1_r2", "real"), ("I4", "spy_ief", "ar1_r2", "boot"),
    ("I5", "spy_ief", "shift_tsmom", "real"), ("I6", "spy_ief", "shift_tsmom", "boot"),
]
HORIZONS = {"country": (1, 2, 3, 4, 5), "stock": (1, 2, 3, 4, 5, 6), "spy_cash": (1, 2, 3, 4, 5),
            "spy_cash_active": (1, 2, 3, 4, 5), "spy_ief": (1, 2, 3, 4, 5, 6, 8, 10)}


def build(engine_name: str, signal: str, path: str):
    from research.null_lab import engines as E
    from research.null_lab.api import builders
    from research.null_lab.gates import Gate
    if engine_name == "country":
        eng = E.CountryEngine()
        real = eng.real_signal()
        sb = {"shift": lambda: builders.shift(real, MIN_OFF["country"]),
              "ar1": lambda: builders.ar1(real, 12),
              "perm": lambda: builders.permute(real)}[signal]()
        gate = Gate(k=4, block=21, seed=20260923)
        split = eng.windows["dev"].end_day
        n_days = len(eng.cal)
    elif engine_name == "stock":
        eng = E.StockEngine()
        kind = "mom_12_1" if signal.endswith("mom") else "rev_1m"
        real = eng.price_signal(kind)
        if signal.startswith("shift"):
            sb = builders.shift(real, MIN_OFF["stock_mom" if kind == "mom_12_1" else "stock_rev"])
        elif signal.startswith("ar1"):
            sb = builders.ar1(real, 52)
        else:
            sb = builders.permute(real)
        gate = Gate(k=4, block=8, seed=20260918)
        split = int(eng.windows["dev"]["x"][-1])
        n_days = len(eng.cal)
    else:
        book = "spy_ief" if engine_name == "spy_ief" else "spy_cash"
        eng = E.TimingEngine(book, active=engine_name.endswith("active"))
        if book == "spy_cash":
            real = eng.real_signal("tsmom")
            sb = builders.shift(real, MIN_OFF["daily_252"]) if signal.startswith("shift") else \
                builders.ar1_series(real, "binary01")
            gate = Gate(k=4, block=21, seed=20260923)
        else:
            if signal.endswith("r2"):
                real = eng.real_signal("r2")
                sb = builders.shift(real, MIN_OFF["daily_r2"]) if signal.startswith("shift") else \
                    builders.ar1_series(real, "continuous")
            else:
                real = eng.real_signal("tsmom")
                sb = builders.shift(real, MIN_OFF["daily_252"])
            gate = Gate(k=4, block=21, seed=20260918)
        split = eng.windows["dev"][1]
        n_days = len(eng.cal)
    pb = builders.bootstrap_paths(n_days, 21, split=split) if path == "boot" else None
    return eng, sb, pb, gate


def run_one(args) -> str:
    cid, engine_name, signal, path, worlds = args
    from research.null_lab.api import run_null
    idx = [c[0] for c in CONFIGS].index(cid)
    eng, sb, pb, gate = build(engine_name, signal, path)
    chunk = 125 if engine_name == "stock" else (250 if path == "boot" else 500)
    res = run_null(sb, eng, gate, n_worlds=worlds, seed=BASE_SEED + 1000 * idx, path_builder=pb,
                   chunk=chunk, horizons=HORIZONS[engine_name])
    arrays = res.pop("arrays")
    res.update({"config": cid, "engine_key": engine_name, "signal_key": signal, "path_key": path,
                "signal_params": getattr(sb, "params", None)})
    OUT.mkdir(parents=True, exist_ok=True)
    keep = {k: v.astype(np.float32) if v.dtype != bool else v for k, v in arrays.items()
            if k in ("sr_dev", "sr_val", "stress_mean_dev", "stress_mean_val", "p_val", "pass_dev", "pass_val",
                     "pass_both")}
    np.savez_compressed(OUT / f"{cid}.npz", **keep)
    (OUT / f"{cid}.json").write_text(json.dumps(res, indent=1, default=float))
    c = res["candidate"]
    return (f"{cid} {engine_name}/{signal}/{path} {res['seconds']}s  P(dev)={c['p_pass_dev']['p']:.4f} "
            f"P(both)={c['p_pass_both']['p']:.4f} SRdev {c['sr_dev']['mean']:+.2f}±{c['sr_dev']['sd']:.2f} "
            f"SRval {c['sr_val']['mean']:+.2f}±{c['sr_val']['sd']:.2f} fam P(dev)={res['family']['p_any_pass_dev']['p']:.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worlds", type=int, default=4000)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    todo = [c for c in CONFIGS if not a.only or c[0] in a.only.split(",")]
    # heavy stock configs first so the pool drains evenly
    todo.sort(key=lambda c: (c[1] != "stock", c[1] != "country"))
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for line in ex.map(run_one, [(c[0], c[1], c[2], c[3], a.worlds) for c in todo]):
            print(line, flush=True)
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
