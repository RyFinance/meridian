"""Development / validation for the registered MBS convexity book.  PYTHONPATH=. .venv/bin/python -m research.mbs_convexity.evaluate dev"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from research.mbs_convexity import core as c
from research.return_search.run import cash_rates
from research.struct_common import ROOT, centred_block_p, etf, null_pass_rate, registered, sharpe

OUT = ROOT / "reports" / "mbs_convexity"
PLAN, UNLOCK = "research/mbs_convexity/PLAN.md", "research/mbs_convexity/VALIDATION_UNLOCK.md"
DEV, VAL = ("2007-03-16", "2016-12-30"), ("2017-01-03", "2026-09-17")
ALPHA = 0.025


def run_window(w):
    res = {"window": list(w), "books": {}}
    series = {}
    for k in c.COSTS:
        b, H = c.book(w, k)
        series[k] = b
        nav = (1 + b).cumprod()
        res["books"][k] = {"sharpe": sharpe(b), "ann_mean": float(b.mean() * 252), "max_dd": float((nav / nav.cummax() - 1).min())}
    b = series["base"]
    T = len(b) / 252
    gate = 1.8 / np.sqrt(T)
    rf = cash_rates(etf("SPY").index, "2026-09-18")
    spy_ex = (etf("SPY").pct_change() - rf).reindex(b.index).fillna(0)
    hyg_ex = (etf("HYG").pct_change() - rf).reindex(b.index).fillna(0)
    X = np.column_stack([np.ones(len(b)), spy_ex, hyg_ex])
    beta = np.linalg.lstsq(X, b.to_numpy(), rcond=None)[0]
    Hs = H.loc[b.index[0]:b.index[-1]]
    res.update({"years": T, "gate": float(gate), "first_live": str(b.index[0].date()),
                "beta_spy": float(beta[1]), "beta_hyg": float(beta[2]), "alpha_ann_after_betas": float(beta[0] * 252),
                "mean_hedge": {k: float(v) for k, v in Hs.mean().items()},
                "by_year": {int(y): float(g.sum()) for y, g in b.groupby(b.index.year)},
                "contrib_2008": float(b.loc["2008"].sum()) if "2008" in b.index.year.astype(str) else None,
                "contrib_2013": float(b.loc["2013"].sum()),
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
        print(json.dumps(r, indent=1))
    elif mode == "validation":
        if not registered(UNLOCK):
            raise SystemExit("validation locked")
        if not json.loads((OUT / "dev_results.json").read_text())["selected"]:
            raise SystemExit("not selected")
        (OUT / "validation_results.json").write_text(json.dumps(run_window(VAL), indent=2))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "dev")
