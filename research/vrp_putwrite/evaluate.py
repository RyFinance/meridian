"""Development / validation for the registered SPY put-writing candidate PW.

  PYTHONPATH=. .venv/bin/python -m research.vrp_putwrite.evaluate dev
"""
from __future__ import annotations

import hashlib
import json
import sys

import numpy as np
import pandas as pd

from research.common.inference import deflated_sharpe
from research.return_search.run import cash_rates
from research.vrp_putwrite import core as c

ROOT = c.ROOT
OUT = ROOT / "reports" / "vrp_putwrite"
PREREG = ROOT / "research" / "preregistrations.jsonl"
PLAN, UNLOCK = "research/vrp_putwrite/PLAN.md", "research/vrp_putwrite/VALIDATION_UNLOCK.md"
DEV, VAL = ("2014-06-01", "2019-12-31"), ("2020-01-01", "2026-08-31")
SEED, DRAWS, BLOCK, N_TRIALS = 20260924, 10000, 3, 120


def _registered(p):
    f = ROOT / p
    if not f.exists():
        return False
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    return any(json.loads(l).get("file") == p and json.loads(l).get("sha256") == h for l in PREREG.read_text().splitlines())


def nw(y, X, lags=3):
    X = np.column_stack([np.ones(len(y))] + ([X] if X is not None else []))
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    u = y - X @ b
    xu = X * u[:, None]
    S = xu.T @ xu
    for L in range(1, lags + 1):
        g = xu[L:].T @ xu[:-L]
        S += (1 - L / (lags + 1)) * (g + g.T)
    V = np.linalg.inv(X.T @ X) @ S @ np.linalg.inv(X.T @ X)
    return b, b / np.sqrt(np.diag(V))


def boot_p(x):
    n, cx = len(x), x - x.mean()
    rng = np.random.default_rng(SEED)
    idx = (rng.integers(0, n, size=(DRAWS, -(-n // BLOCK)))[:, :, None] + np.arange(BLOCK)).reshape(DRAWS, -1)[:, :n] % n
    return float((np.sum(cx[idx].mean(axis=1) >= x.mean()) + 1) / (DRAWS + 1))


def run_window(w):
    spy = c.load_spy_raw()
    cy = c.cycles(c.load_puts(), spy, *w)
    daily_rf = cash_rates(spy.index, str(spy.index[-1].date()))
    rf = np.array([float((1 + daily_rf.loc[(daily_rf.index > e) & (daily_rf.index <= x)]).prod() - 1)
                   for e, x in zip(cy["entry"], cy["expiry"])])
    spy_ex = cy["adj_ret_spy"].to_numpy() - rf
    ppy = len(cy) / ((cy["expiry"].iloc[-1] - cy["entry"].iloc[0]).days / 365.25)
    res = {"window": list(w), "cycles": int(len(cy)), "ok_cycles": int((cy["status"] == "ok").sum()),
           "periods_per_year": ppy, "books": {}}
    ctrl = 0.5 * spy_ex
    for k, cost in c.COSTS.items():
        r = c.excess_returns(cy, cost).to_numpy()
        act = r - ctrl
        b, t = nw(r, spy_ex)
        nav = np.cumprod(1 + r + rf)
        res["books"][k] = {"sharpe": float(r.mean() / r.std(ddof=1) * np.sqrt(ppy)), "ann_excess": float(r.mean() * ppy),
                           "cagr_total": float(nav[-1] ** (ppy / len(r)) - 1),
                           "max_dd": float((nav / np.maximum.accumulate(nav) - 1).min()),
                           "beta": float(b[1]), "alpha_ann": float(b[0] * ppy), "alpha_t": float(t[0]),
                           "active_sharpe": float(act.mean() / act.std(ddof=1) * np.sqrt(ppy)),
                           "active_ann": float(act.mean() * ppy), "active_boot_p": boot_p(act),
                           "worst_cycle": float(r.min()), "hit_rate": float((r > 0).mean())}
    rb = c.excess_returns(cy, c.COSTS["base"]).to_numpy()
    res["control_half_spy"] = {"sharpe": float(ctrl.mean() / ctrl.std(ddof=1) * np.sqrt(ppy)), "ann_excess": float(ctrl.mean() * ppy)}
    res["spy"] = {"sharpe": float(spy_ex.mean() / spy_ex.std(ddof=1) * np.sqrt(ppy)), "ann_excess": float(spy_ex.mean() * ppy)}
    ok = cy["status"] == "ok"
    ins = ((cy["premium"] - np.maximum(cy["strike"] - cy["spot_x"], 0)) / cy["strike"])[ok]
    res["insurance_premium_per_cycle"] = {"mean_pct": float(ins.mean() * 100), "t": float(ins.mean() / ins.std(ddof=1) * np.sqrt(len(ins)))}
    res["deflated_sharpe_prob"] = deflated_sharpe(rb - ctrl, N_TRIALS, (0.5 ** 2) / ppy)
    res["by_year_base"] = {int(y): float(np.prod(1 + rb[cy["entry"].dt.year == y]) - 1) for y in sorted(cy["entry"].dt.year.unique())}
    res["by_year_active"] = {int(y): float((rb - ctrl)[cy["entry"].dt.year == y].sum()) for y in sorted(cy["entry"].dt.year.unique())}
    tag = "dev" if w == DEV else "validation"
    cy.assign(rf=rf, spy_ex=spy_ex, r_base=rb, control=ctrl).to_csv(OUT / f"{tag}_cycles.csv", index=False)
    return res


def run(mode):
    OUT.mkdir(parents=True, exist_ok=True)
    if not _registered(PLAN):
        raise SystemExit("PLAN not registered")
    if mode == "dev":
        if (OUT / "dev_results.json").exists():
            raise SystemExit("already run")
        r = run_window(DEV)
        T = (pd.Timestamp(DEV[1]) - pd.Timestamp(DEV[0])).days / 365.25
        r["gate"] = 1.8 / np.sqrt(T)
        b, s = r["books"]["base"], r["books"]["stress"]
        r["selected"] = bool(b["active_sharpe"] >= r["gate"] and s["active_ann"] > 0 and b["alpha_ann"] > 0 and b["active_boot_p"] < 0.05)
        (OUT / "dev_results.json").write_text(json.dumps(r, indent=2))
        print(json.dumps({k: r[k] for k in ("cycles", "ok_cycles", "gate", "books", "control_half_spy", "spy",
                                             "insurance_premium_per_cycle", "deflated_sharpe_prob", "selected")}, indent=1))
    elif mode == "validation":
        if not _registered(UNLOCK):
            raise SystemExit("validation locked")
        if not json.loads((OUT / "dev_results.json").read_text())["selected"]:
            raise SystemExit("not selected")
        (OUT / "validation_results.json").write_text(json.dumps(run_window(VAL), indent=2))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "dev")
