"""Development / validation for pd_inventory.  PYTHONPATH=. .venv/bin/python -m research.pd_inventory.evaluate dev"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from research.pd_inventory import core as c
from research.struct_common import ROOT, centred_block_p, null_pass_rate, registered, sharpe

OUT = ROOT / "reports" / "pd_inventory"
PLAN, UNLOCK = "research/pd_inventory/PLAN.md", "research/pd_inventory/VALIDATION_UNLOCK.md"
DEV, VAL = ("1998-05-01", "2012-06-29"), ("2012-07-02", "2026-08-31")
ALPHA, SEED, N_SHIFT = 0.05, 20260925, 1000


def run_window(w):
    res = {"window": list(w), "books": {}}
    A = {}
    for k in c.COSTS:
        b, a, W = c.book(w, k)
        A[k] = a
        res["books"][k] = {"sharpe": sharpe(b), "ann_mean": float(b.mean() * 252),
                           "active_sharpe": sharpe(a), "active_ann": float(a.mean() * 252)}
    a = A["base"]
    T = len(a) / 252
    res["years"], res["gate"] = T, float(1.8 / np.sqrt(T))
    res["mean_weight"] = float(W.mean())
    res["bootstrap_p"] = centred_block_p(a.to_numpy(), block=21, draws=5000, seed=SEED)
    res["P_pass_given_null"] = null_pass_rate(a.to_numpy(), A["stress"].to_numpy(), res["gate"], ALPHA)
    # reported only: circular shift of the weekly signal by >= 52 weeks
    sig = c.signal(c.inventory())
    rng = np.random.default_rng(SEED)
    sh = []
    for _ in range(N_SHIFT):
        k = int(rng.integers(52, len(sig) - 52))
        s2 = sig.copy()
        s2["w"] = np.roll(sig.w.to_numpy(), k)
        days = c.dgs10().loc[w[0]:w[1]].index
        _, a2, _ = c.book(w, "base", w_override=c.weights_daily(s2, days))
        sh.append(sharpe(a2))
    sh = np.array(sh)
    res["shift_null_reported"] = {"p": float((np.sum(sh >= res["books"]["base"]["active_sharpe"]) + 1) / (N_SHIFT + 1)),
                                  "mean_sd": [float(sh.mean()), float(sh.std())]}
    res["active_by_year"] = {int(y): float(g.sum()) for y, g in a.groupby(a.index.year)}
    tag = "dev" if w == DEV else "validation"
    pd.DataFrame(A).to_csv(OUT / f"{tag}_daily_active.csv")
    return res


def run(mode):
    OUT.mkdir(parents=True, exist_ok=True)
    if not registered(PLAN):
        raise SystemExit("PLAN not registered")
    if mode == "dev":
        if (OUT / "dev_results.json").exists():
            raise SystemExit("already run")
        r = run_window(DEV)
        b, s = r["books"]["base"], r["books"]["stress"]
        r["selected"] = bool(b["active_sharpe"] >= r["gate"] and s["active_ann"] > 0 and r["bootstrap_p"] < ALPHA)
        (OUT / "dev_results.json").write_text(json.dumps(r, indent=2))
        print(json.dumps(r, indent=1))
    elif mode == "validation":
        if not registered(UNLOCK):
            raise SystemExit("validation locked")
        if not json.loads((OUT / "dev_results.json").read_text())["selected"]:
            raise SystemExit("not selected")
        r = run_window(VAL)
        b, s = r["books"]["base"], r["books"]["stress"]
        r["passed"] = bool(r["bootstrap_p"] < ALPHA and b["active_sharpe"] >= 0.30 and s["active_sharpe"] >= 0.30)
        (OUT / "validation_results.json").write_text(json.dumps(r, indent=2))
        print(json.dumps(r, indent=1))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "dev")
