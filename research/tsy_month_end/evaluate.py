"""Development / validation for the registered Treasury month-end book M.

  PYTHONPATH=. .venv/bin/python -m research.tsy_month_end.evaluate dev
"""
from __future__ import annotations

import hashlib
import json
import sys

import numpy as np
import pandas as pd

from research.return_search.run import cash_rates
from research.tsy_month_end import core as c

ROOT = c.ROOT
OUT = ROOT / "reports" / "tsy_month_end"
PREREG = ROOT / "research" / "preregistrations.jsonl"
PLAN, UNLOCK = "research/tsy_month_end/PLAN.md", "research/tsy_month_end/VALIDATION_UNLOCK.md"
DEV, VAL = ("2003-01-02", "2014-12-31"), ("2015-01-02", "2026-08-31")
PLACEBO_K = range(3, 16)
SEED, DRAWS, BLOCK, N_SHIFT = 20260924, 10000, 21, 1000


def _registered(p):
    f = ROOT / p
    if not f.exists():
        return False
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    return any(json.loads(l).get("file") == p and json.loads(l).get("sha256") == h for l in PREREG.read_text().splitlines())


def boot_p(x):
    n, cx = len(x), x - x.mean()
    rng = np.random.default_rng(SEED)
    idx = (rng.integers(0, n, size=(DRAWS, -(-n // BLOCK)))[:, :, None] + np.arange(BLOCK)).reshape(DRAWS, -1)[:, :n] % n
    return float((np.sum(cx[idx].mean(axis=1) >= x.mean()) + 1) / (DRAWS + 1))


def active(w, px, rf, cost):
    r = c.returns(w, px, rf, cost)
    ctrl = float(w.mean()) * (px.pct_change().fillna(0.0) - rf)
    return r - ctrl, r


def run_window(win):
    px_all = c.load("TLT")
    px = px_all.loc[win[0]:win[1]]
    # use full months only
    sess = px.index
    rf = cash_rates(px_all.index, str(px_all.index[-1].date())).reindex(sess).fillna(0)
    res = {"window": list(win), "years": len(sess) / 252, "books": {}}
    w = c.weights(sess, "last")
    for k, cost in c.COSTS.items():
        a, r = active(w, px, rf, cost)
        res["books"][k] = {"sharpe": c.sharpe(r), "ann_excess": float(r.mean() * 252), "active_sharpe": c.sharpe(a),
                           "active_ann": float(a.mean() * 252), "active_boot_p": boot_p(a.to_numpy())}
    a_base, _ = active(w, px, rf, c.COSTS["base"])
    # per-window mean return (gross), and placebo positions
    rr = px.pct_change().fillna(0) - rf
    def window_mean(wk):
        held = wk.shift(1).fillna(0)
        by_m = (held * rr).groupby(sess.to_period("M")).sum()
        return float(by_m.mean() * 1e4)
    res["gross_bps_per_month_window"] = window_mean(w)
    plac = {}
    for k in PLACEBO_K:
        wk = c.weights(sess, k)
        ak, _ = active(wk, px, rf, c.COSTS["base"])
        plac[k] = {"active_sharpe": c.sharpe(ak), "gross_bps": window_mean(wk)}
    res["placebo"] = plac
    ps = np.array([v["active_sharpe"] for v in plac.values()])
    res["placebo_rank"] = float((np.sum(ps >= res["books"]["base"]["active_sharpe"]) + 1) / (len(ps) + 1))
    # gating null: random circular shifts of the holding calendar (breaks month alignment)
    rng = np.random.default_rng(SEED)
    sh, sh_pass = [], 0
    gate = 1.8 / np.sqrt(res["years"])
    for _ in range(N_SHIFT):
        k = int(rng.integers(5, len(sess) - 5))
        wk = pd.Series(np.roll(w.to_numpy(), k), index=sess)
        ab, _ = active(wk, px, rf, c.COSTS["base"])
        as_, _ = active(wk, px, rf, c.COSTS["stress"])
        v = c.sharpe(ab)
        sh.append(v)
        sh_pass += int(v >= gate and as_.mean() > 0)
    sh = np.array(sh)
    res["shift_null"] = {"n": N_SHIFT, "p": float((np.sum(sh >= res["books"]["base"]["active_sharpe"]) + 1) / (N_SHIFT + 1)),
                         "mean_sd": [float(sh.mean()), float(sh.std())], "q95_q99": [float(np.quantile(sh, .95)), float(np.quantile(sh, .99))],
                         "P_pass_given_null": float(sh_pass / N_SHIFT)}
    res["gate"] = 1.8 / np.sqrt(res["years"])
    res["active_by_year"] = {int(y): float(g.sum()) for y, g in a_base.groupby(a_base.index.year)}
    # IEF, same rule, descriptive
    ief = c.load("IEF").loc[win[0]:win[1]]
    ai, ri = active(c.weights(ief.index, "last"), ief, rf.reindex(ief.index).fillna(0), c.COSTS["base"])
    res["IEF_descriptive"] = {"active_sharpe": c.sharpe(ai), "active_ann": float(ai.mean() * 252)}
    tag = "dev" if win == DEV else "validation"
    pd.DataFrame({"M": c.returns(w, px, rf, c.COSTS["base"]), "active": a_base}).to_csv(OUT / f"{tag}_daily.csv")
    return res


def run(mode):
    OUT.mkdir(parents=True, exist_ok=True)
    if not _registered(PLAN):
        raise SystemExit("PLAN not registered")
    if mode == "dev":
        if (OUT / "dev_results.json").exists():
            raise SystemExit("already run")
        r = run_window(DEV)
        b, s = r["books"]["base"], r["books"]["stress"]
        r["selected"] = bool(b["active_sharpe"] >= r["gate"] and s["active_ann"] > 0 and r["shift_null"]["p"] < 0.05)
        (OUT / "dev_results.json").write_text(json.dumps(r, indent=2))
        print(json.dumps({k: v for k, v in r.items() if k not in ("active_by_year",)}, indent=1))
    elif mode == "validation":
        if not _registered(UNLOCK):
            raise SystemExit("validation locked")
        if not json.loads((OUT / "dev_results.json").read_text())["selected"]:
            raise SystemExit("not selected")
        (OUT / "validation_results.json").write_text(json.dumps(run_window(VAL), indent=2))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "dev")
