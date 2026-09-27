"""Development / validation for the registered FX hedge-rebalancing book.  PYTHONPATH=. .venv/bin/python -m research.fx_hedge_rebal.evaluate dev"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from research.fx_hedge_rebal import core as c
from research.struct_common import ROOT, registered, sharpe

OUT = ROOT / "reports" / "fx_hedge_rebal"
PLAN, UNLOCK = "research/fx_hedge_rebal/PLAN.md", "research/fx_hedge_rebal/VALIDATION_UNLOCK.md"
DEV, VAL = ("2015-01-01", "2020-12-31"), ("2021-01-01", "2026-08-31")
N_PERM, SEED = 2000, 20260923


def run_window(w):
    ev = c.events(*w)
    days = pd.bdate_range(*w)
    res = {"window": list(w), "events_valid": int((ev["sign"].notna() & ev["ret"].notna()).sum()), "books": {}}
    for k, cost in c.COSTS.items():
        b = c.daily_book(ev, "sign", cost, days)
        ok = ev["sign"].notna() & ev["ret"].notna()
        res["books"][k] = {"sharpe": sharpe(b), "ann_mean": float(b.mean() * 252),
                           "mean_bps_per_event": float((ev.loc[ok, "sign"] * ev.loc[ok, "ret"] - 2 * cost).mean() * 1e4)}
    ev["one"] = 1.0
    cu = c.daily_book(ev, "one", c.COSTS["base"], days)
    res["C_USDSHORT"] = {"sharpe": sharpe(cu), "ann_mean": float(cu.mean() * 252)}
    ok = ev["sign"].notna() & ev["ret"].notna()
    e = ev[ok].copy()
    e["pnl"] = e["sign"] * e["ret"]
    res["hit_rate"] = float((e["pnl"] > 0).mean())
    res["per_pair_bps"] = {k: [float(g["pnl"].mean() * 1e4), int(len(g))] for k, g in e.groupby("ccy")}
    res["by_year_bps"] = {int(k): float(g["pnl"].mean() * 1e4) for k, g in e.groupby(e["D"].dt.year)}
    q = e["D"].dt.month.isin([3, 6, 9, 12])
    res["quarter_end_vs_other_bps"] = [float(e.loc[q, "pnl"].mean() * 1e4), float(e.loc[~q, "pnl"].mean() * 1e4)]
    e["t"] = pd.qcut(e["rel"].abs(), 3, labels=False)
    res["rel_tercile_bps"] = {int(k): float(g["pnl"].mean() * 1e4) for k, g in e.groupby("t")}
    base = res["books"]["base"]["sharpe"]
    T = len(days) / 252
    gate = 1.8 / np.sqrt(T)
    rng = np.random.default_rng(SEED)
    perm, passes = [], 0
    for _ in range(N_PERM):
        evp = ev.copy()
        for ccy, g in evp.groupby("ccy"):
            evp.loc[g.index, "sign"] = rng.permutation(g["sign"].to_numpy())
        bb = c.daily_book(evp, "sign", c.COSTS["base"], days)
        bs = c.daily_book(evp, "sign", c.COSTS["stress"], days)
        v = sharpe(bb)
        perm.append(v)
        passes += int(v >= gate and bs.mean() > 0)
    perm = np.array(perm)
    res.update({"years": T, "gate": float(gate), "perm_p": float((np.sum(perm >= base) + 1) / (N_PERM + 1)),
                "perm_mean_sd_q95": [float(perm.mean()), float(perm.std()), float(np.quantile(perm, .95))],
                "P_pass_given_null": passes / N_PERM})
    tag = "dev" if w == DEV else "validation"
    ev.to_csv(OUT / f"{tag}_events.csv", index=False)
    return res


def run(mode):
    OUT.mkdir(parents=True, exist_ok=True)
    if not registered(PLAN):
        raise SystemExit("PLAN not registered")
    if mode == "dev":
        if (OUT / "dev_results.json").exists():
            raise SystemExit("already run")
        r = run_window(DEV)
        r["selected"] = bool(r["books"]["base"]["sharpe"] >= r["gate"] and r["books"]["stress"]["ann_mean"] > 0 and r["perm_p"] < 0.05)
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
