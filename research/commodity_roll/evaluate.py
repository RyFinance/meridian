"""Development / validation for the registered commodity roll book.  PYTHONPATH=. .venv/bin/python -m research.commodity_roll.evaluate dev"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from research.commodity_roll import core as c
from research.return_search.run import cash_rates
from research.struct_common import ROOT, centred_block_p, etf, null_pass_rate, registered, sharpe

OUT = ROOT / "reports" / "commodity_roll"
PLAN, UNLOCK = "research/commodity_roll/PLAN.md", "research/commodity_roll/VALIDATION_UNLOCK.md"
DEV, VAL = ("2006-07-21", "2016-12-30"), ("2017-01-03", "2026-09-17")
ALPHA = 0.025


def run_window(w):
    res = {"window": list(w), "books": {}}
    series = {}
    for k in c.COSTS:
        b, P = c.book(w, k)
        series[k] = b
        nav = (1 + b).cumprod()
        res["books"][k] = {"sharpe": sharpe(b), "ann_mean": float(b.mean() * 252), "max_dd": float((nav / nav.cummax() - 1).min())}
        if k == "base":
            res["per_pair"] = {p: {"sharpe": sharpe(P[p].dropna()), "ann_mean": float(P[p].dropna().mean() * 252),
                                   "first": str(P[p].first_valid_index().date())} for p in P}
            res["by_year"] = {int(y): float(g.sum()) for y, g in b.groupby(b.index.year)}
            res["pair_by_year"] = {p: {int(y): float(g.sum()) for y, g in P[p].dropna().groupby(P[p].dropna().index.year)} for p in P}
    b = series["base"]
    T = len(b) / 252
    gate = 1.8 / np.sqrt(T)
    rf = cash_rates(etf("SPY").index, "2026-09-18")
    spy_ex = (etf("SPY").pct_change() - rf).reindex(b.index).fillna(0)
    front = pd.concat([etf(t).pct_change() for t in ("USO", "UNG", "GSG")], axis=1).mean(axis=1).reindex(b.index).fillna(0)
    X = np.column_stack([np.ones(len(b)), spy_ex, front])
    beta = np.linalg.lstsq(X, b.to_numpy(), rcond=None)[0]
    res.update({"years": T, "gate": float(gate), "beta_spy": float(beta[1]), "beta_front_basket": float(beta[2]),
                "alpha_ann_after_betas": float(beta[0] * 252),
                "bootstrap_p": centred_block_p(b.to_numpy()),
                "P_pass_given_null": null_pass_rate(b.to_numpy(), series["stress"].reindex(b.index).fillna(0).to_numpy(), gate, ALPHA)})
    tag = "dev" if w == DEV else "validation"
    pd.DataFrame(series).to_csv(OUT / f"{tag}_daily.csv")
    return res


def run(mode):
    OUT.mkdir(parents=True, exist_ok=True)
    if not registered(PLAN):
        raise SystemExit("PLAN not registered")
    if mode == "dev":
        if (OUT / "dev_results.json").exists():
            raise SystemExit("already run")
        r = run_window(DEV)
        r["selected"] = bool(r["books"]["base"]["sharpe"] >= r["gate"] and r["books"]["stress"]["ann_mean"] > 0 and r["bootstrap_p"] < ALPHA)
        (OUT / "dev_results.json").write_text(json.dumps(r, indent=2))
        print(json.dumps({k: v for k, v in r.items() if k not in ("pair_by_year",)}, indent=1))
    elif mode == "validation":
        if not registered(UNLOCK):
            raise SystemExit("validation locked")
        if not json.loads((OUT / "dev_results.json").read_text())["selected"]:
            raise SystemExit("not selected")
        (OUT / "validation_results.json").write_text(json.dumps(run_window(VAL), indent=2))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "dev")
