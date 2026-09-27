"""Development / validation for crypto_funding_xs.  PYTHONPATH=. .venv/bin/python -m research.crypto_funding_xs.evaluate dev"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from research.crypto_funding_xs import core as c
from research.struct_common import ROOT, centred_block_p, null_pass_rate, registered

OUT = ROOT / "reports" / "crypto_funding_xs"
PLAN, UNLOCK = "research/crypto_funding_xs/PLAN.md", "research/crypto_funding_xs/VALIDATION_UNLOCK.md"
DEV, VAL = ("2020-01-01", "2022-12-31"), ("2023-01-01", "2026-08-31")
ALPHA_DEV, ALPHA_VAL, SEED, N_PERM, ANN = 0.025, 0.05, 20260925, 500, 365


def sharpe(x):
    x = pd.Series(x).dropna()
    s = x.std(ddof=1)
    return float(x.mean() / s * np.sqrt(ANN)) if s > 0 else float("nan")


def run_window(w):
    syms = c.symbols()
    P, FIRST = c.panel(syms, *w)
    W = c.weights(P, FIRST, *w, stock_bases=c.tokenized_stock_bases() if w == VAL else set())
    res = {"window": list(w), "n_symbols_with_klines": len(FIRST),
           "days_dropped_small_universe": int(W.isna().all(axis=1).sum()), "books": {}}
    S = {}
    for k in c.COSTS:
        S[k] = c.returns(P, W, k)
        res["books"][k] = {"sharpe": sharpe(S[k]), "ann_mean": float(S[k].mean() * ANN),
                           "max_dd": float(((1 + S[k]).cumprod() / (1 + S[k]).cumprod().cummax() - 1).min())}
    b = S["base"]
    T = len(b) / ANN
    res["years"], res["gate"] = T, float(1.8 / np.sqrt(T))
    res["bootstrap_p"] = centred_block_p(b.to_numpy(), block=21, draws=5000, seed=SEED)
    res["P_pass_given_null_bootstrap"] = null_pass_rate(b.to_numpy(), S["stress"].reindex(b.index).fillna(0).to_numpy(),
                                                        res["gate"], ALPHA_DEV, ann=ANN)
    # decomposition: price vs funding legs
    Wf = W.fillna(0.0)
    O, C, F = (P[k].reindex(W.index) for k in ("O", "C", "FUND"))
    live = W.notna().all(axis=1)
    price = (Wf * (C / O - 1).fillna(0)).sum(axis=1)[live]
    fund = -(Wf * F.fillna(0)).sum(axis=1)[live]
    res["decomposition_ann"] = {"price": float(price.mean() * ANN), "funding": float(fund.mean() * ANN),
                                "turnover_per_day": float(Wf.diff().abs().sum(axis=1)[live].mean())}
    # benchmarks for beta (G1): equal-weight universe (all eligible) and BTC perp
    elig = (W.notna() & (P["C"].reindex(W.index).notna()))
    mkt = ((C / O - 1).where(Wf != 0).mean(axis=1))[live]
    btc = (C["BTCUSDT"] / O["BTCUSDT"] - 1)[live] if "BTCUSDT" in C else pd.Series(0.0, index=b.index)
    X = np.column_stack([np.ones(len(b)), mkt.reindex(b.index).fillna(0), btc.reindex(b.index).fillna(0)])
    beta = np.linalg.lstsq(X, b.to_numpy(), rcond=None)[0]
    res["beta"] = {"alpha_ann": float(beta[0] * ANN), "beta_held_ew": float(beta[1]), "beta_btc": float(beta[2])}
    res["by_year"] = {int(y): float(g.sum()) for y, g in b.groupby(b.index.year)}
    res["n_long_short_mean"] = float((Wf[live] > 0).sum(axis=1).mean()), float((Wf[live] < 0).sum(axis=1).mean())
    # placebo: daily cross-sectional shuffle of the signal
    rng = np.random.default_rng(SEED)
    ps = []
    for _ in range(N_PERM):
        Wp = c.weights(P, FIRST, *w, rng=rng, stock_bases=c.tokenized_stock_bases() if w == VAL else set())
        ps.append(sharpe(c.returns(P, Wp, "base")))
    ps = np.array(ps)
    res["placebo"] = {"p": float((np.sum(ps >= res["books"]["base"]["sharpe"]) + 1) / (N_PERM + 1)),
                      "mean_sd": [float(ps.mean()), float(ps.std())], "P_sharpe_ge_gate": float(np.mean(ps >= res["gate"]))}
    tag = "dev" if w == DEV else "validation"
    pd.DataFrame(S).to_csv(OUT / f"{tag}_daily.csv")
    W.to_parquet(OUT / f"{tag}_weights.parquet")
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
