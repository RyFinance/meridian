"""Development / validation for tsy_auction_demand.  PYTHONPATH=. .venv/bin/python -m research.tsy_auction_demand.evaluate dev"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from research.struct_common import ROOT, centred_block_p, null_pass_rate, registered, sharpe
from research.tsy_auction_demand import core as c

OUT = ROOT / "reports" / "tsy_auction_demand"
PLAN, UNLOCK = "research/tsy_auction_demand/PLAN.md", "research/tsy_auction_demand/VALIDATION_UNLOCK.md"
DEV, VAL = ("2000-01-01", "2012-12-31"), ("2013-01-01", "2026-08-31")
ALPHA_DEV, ALPHA_VAL, SEED, N_PERM = 0.025, 0.05, 20260925, 1000


def run_window(w):
    ev = c.signals(c.load_auctions())
    Y = c.yields()
    res = {"window": list(w), "books": {}}
    S = {}
    for k in c.COSTS:
        s, recs = c.book(ev, Y, k, w)
        S[k] = s
        res["books"][k] = {"sharpe": sharpe(s), "ann_mean": float(s.mean() * 252)}
        if k == "base":
            R = recs
    b = S["base"]
    T = len(b) / 252
    res["years"], res["n_events"] = T, int(len(R))
    res["gate"] = float(1.8 / np.sqrt(T))
    res["bootstrap_p"] = centred_block_p(b.to_numpy(), block=21, draws=5000, seed=SEED)
    res["P_pass_given_null_bootstrap"] = null_pass_rate(b.to_numpy(), S["stress"].to_numpy(), res["gate"], ALPHA_DEV)
    # permutation placebo: shuffle w within bucket (breaks the demand link, keeps exposure profile)
    rng = np.random.default_rng(SEED)
    wind = ev[(ev.auction_date >= w[0]) & (ev.auction_date <= w[1])].copy()
    ps = []
    for _ in range(N_PERM):
        wind["wp"] = wind.groupby("bucket")["w"].transform(lambda x: rng.permutation(x.to_numpy()))
        s, _ = c.book(wind, Y, "base", w, w_col="wp")
        ps.append(sharpe(s))
    ps = np.array(ps)
    res["perm"] = {"p": float((np.sum(ps >= res["books"]["base"]["sharpe"]) + 1) / (N_PERM + 1)),
                   "mean_sd": [float(ps.mean()), float(ps.std())], "P_sharpe_ge_gate": float(np.mean(ps >= res["gate"]))}
    # descriptives
    R["pnl_bp_7dur"] = R.w * (-R.dy_bp) * c.DUR / 100 * 100      # bp of price per unit w
    wk = R.auction_date.dt.to_period("W")
    g = R.groupby(wk).pnl_bp_7dur.sum()
    res["event_mean_bp"] = float(R.pnl_bp_7dur.mean())
    res["event_t_week_clustered"] = float(g.mean() / g.std(ddof=1) * np.sqrt(len(g)))
    res["by_bucket_bp"] = {int(k): [float(v.mean()), int(len(v))] for k, v in R.groupby("bucket").pnl_bp_7dur}
    res["by_year"] = {int(y): float(v.sum()) for y, v in b.groupby(b.index.year)}
    res["weak_vs_strong_bp_dy"] = {"weak(w>0)": float(R[R.w > 0].dy_bp.mean()), "strong(w<0)": float(R[R.w < 0].dy_bp.mean())}
    ev1 = wind.assign(one=1.0)
    s1, _ = c.book(ev1, Y, "base", w, w_col="one")
    res["control_unconditional_long_sharpe"] = sharpe(s1)
    tag = "dev" if w == DEV else "validation"
    pd.DataFrame(S).to_csv(OUT / f"{tag}_daily.csv")
    R.to_csv(OUT / f"{tag}_events.csv", index=False)
    return res


def run(mode):
    OUT.mkdir(parents=True, exist_ok=True)
    if not registered(PLAN):
        raise SystemExit("PLAN not registered")
    if mode == "dev":
        if (OUT / "dev_results.json").exists():
            raise SystemExit("already run")
        r = run_window(DEV)
        r["selected"] = bool(r["books"]["base"]["sharpe"] >= r["gate"] and r["books"]["stress"]["ann_mean"] > 0
                             and r["bootstrap_p"] < ALPHA_DEV)
        (OUT / "dev_results.json").write_text(json.dumps(r, indent=2))
        print(json.dumps(r, indent=1))
    elif mode == "validation":
        if not registered(UNLOCK):
            raise SystemExit("validation locked")
        if not json.loads((OUT / "dev_results.json").read_text())["selected"]:
            raise SystemExit("not selected")
        r = run_window(VAL)
        r["passed"] = bool(r["bootstrap_p"] < ALPHA_VAL and r["books"]["stress"]["ann_mean"] > 0 and r["books"]["base"]["sharpe"] >= 0.30)
        (OUT / "validation_results.json").write_text(json.dumps(r, indent=2))
        print(json.dumps(r, indent=1))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "dev")
