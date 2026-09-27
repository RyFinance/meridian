"""Development / validation for the registered sector month-end book S.  PYTHONPATH=. .venv/bin/python -m research.sector_month_end.evaluate dev"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from research.sector_month_end import core as c
from research.struct_common import ROOT, centred_block_p, etf, registered, sharpe
from research.tsy_month_end.core import weights

OUT = ROOT / "reports" / "sector_month_end"
PLAN, UNLOCK = "research/sector_month_end/PLAN.md", "research/sector_month_end/VALIDATION_UNLOCK.md"
DEV, VAL = ("2003-01-02", "2014-12-31"), ("2015-01-02", "2026-08-31")
N_SHIFT, SEED = 1000, 20260924


def run_window(w):
    res = {"window": list(w), "books": {}}
    act = {}
    for k in c.COSTS:
        S, C, d = c.book(w, k)
        a = (S - C).dropna()
        act[k] = a
        res["books"][k] = {"active_sharpe": sharpe(a), "active_ann": float(a.mean() * 252)}
        if k == "base":
            P, Cc = d["P"], d["C"]
            res["per_sector"] = {s: {"active_sharpe": sharpe((P[s] - Cc[s]).dropna()), "active_ann": float((P[s] - Cc[s]).dropna().mean() * 252),
                                     "first": str(P[s].first_valid_index().date())} for s in P}
    a = act["base"]
    T = len(a) / 252
    gate = 1.8 / np.sqrt(T)
    res.update({"years": T, "gate": float(gate), "bootstrap_p": centred_block_p(a.to_numpy())})
    # gating null: circular shift of the holding calendar (same shift for all sectors)
    rng = np.random.default_rng(SEED)
    sh, passes = [], 0
    for _ in range(N_SHIFT):
        k = int(rng.integers(5, 250 * 10))
        fn = lambda sess, k=k: pd.Series(np.roll(weights(sess, "last").to_numpy(), k % len(sess)), index=sess)
        Sb, Cb, _ = c.book(w, "base", fn)
        Ss, Cs, _ = c.book(w, "stress", fn)
        ab, as_ = (Sb - Cb).dropna(), (Ss - Cs).dropna()
        v = sharpe(ab)
        sh.append(v)
        passes += int(v >= gate and as_.mean() > 0)
    sh = np.array(sh)
    res["shift_null"] = {"n": N_SHIFT, "p": float((np.sum(sh >= res["books"]["base"]["active_sharpe"]) + 1) / (N_SHIFT + 1)),
                         "mean_sd": [float(np.nanmean(sh)), float(np.nanstd(sh))],
                         "q95_q99": [float(np.nanquantile(sh, .95)), float(np.nanquantile(sh, .99))], "P_pass_given_null": passes / N_SHIFT}
    # diagnostics
    months = a.groupby(a.index.to_period("M")).sum()
    q = months.index.month.isin([3, 6, 9, 12])
    res["quarter_end_vs_other_bps"] = [float(months[q].mean() * 1e4), float(months[~q].mean() * 1e4)]
    plac = {}
    for kpos in range(3, 16):
        Sp, Cp, _ = c.book(w, "base", lambda sess, kpos=kpos: weights(sess, kpos))
        plac[kpos] = sharpe((Sp - Cp).dropna())
    res["placebo_positions_active_sharpe"] = plac
    tlt = etf("TLT").pct_change().reindex(a.index)
    wt = weights(a.index, "last").shift(1).fillna(0)
    tlt_win = (wt * tlt).groupby(a.index.to_period("M")).sum()
    res["corr_monthly_with_TLT_window"] = float(np.corrcoef(months.reindex(tlt_win.index).fillna(0), tlt_win.fillna(0))[0, 1])
    res["active_by_year"] = {int(y): float(g.sum()) for y, g in a.groupby(a.index.year)}
    tag = "dev" if w == DEV else "validation"
    pd.DataFrame(act).to_csv(OUT / f"{tag}_daily_active.csv")
    return res


def run(mode):
    OUT.mkdir(parents=True, exist_ok=True)
    if not registered(PLAN):
        raise SystemExit("PLAN not registered")
    if mode == "dev":
        if (OUT / "dev_results.json").exists():
            raise SystemExit("already run")
        r = run_window(DEV)
        r["selected"] = bool(r["books"]["base"]["active_sharpe"] >= r["gate"] and r["books"]["stress"]["active_ann"] > 0 and r["shift_null"]["p"] < 0.05)
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
