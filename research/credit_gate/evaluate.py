"""Development / validation for the registered credit gate G.

  PYTHONPATH=. .venv/bin/python -m research.credit_gate.evaluate dev
"""
from __future__ import annotations

import hashlib
import json
import sys

import numpy as np
import pandas as pd

from research.credit_gate import core as c

ROOT = c.ROOT
OUT = ROOT / "reports" / "credit_gate"
PREREG = ROOT / "research" / "preregistrations.jsonl"
PLAN, UNLOCK = "research/credit_gate/PLAN.md", "research/credit_gate/VALIDATION_UNLOCK.md"
DEV = ("2010-04-30", "2017-12-29")
VAL = ("2018-01-31", "2026-08-31")
ALL = ("2010-04-30", "2026-08-31")
MIN_SHIFT, SEED, BLOCK, DRAWS = 12, 20260923, 21, 5000


def _registered(p: str) -> bool:
    f = ROOT / p
    if not f.exists():
        return False
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    return any(json.loads(l).get("file") == p and json.loads(l).get("sha256") == h for l in PREREG.read_text().splitlines())


def block_p(x: np.ndarray) -> float:
    n, cx = len(x), x - x.mean()
    rng = np.random.default_rng(SEED)
    idx = (rng.integers(0, n, size=(DRAWS, -(-n // BLOCK)))[:, :, None] + np.arange(BLOCK)).reshape(DRAWS, -1)[:, :n] % n
    return float((np.sum(cx[idx].mean(axis=1) >= x.mean()) + 1) / (DRAWS + 1))


def run_window(window):
    end = window[1]
    px, rf = c.spy_and_cash(str((pd.Timestamp(end) + pd.Timedelta(days=40)).date()))
    ce = c.credit_series()
    me_all = c.month_end_sessions(px.index, *ALL)
    me = me_all[(me_all >= pd.Timestamp(window[0])) & (me_all <= pd.Timestamp(window[1]))]
    nxt = me_all[me_all > me[-1]][:1]
    stop = nxt[0] if len(nxt) else px.index[-1]
    days = px.index[(px.index > me[0]) & (px.index <= stop)]
    logpx = np.log(px)
    sig_g = pd.Series({t: c.signal_at(ce, t) for t in me})
    sig_t = pd.Series({t: float(logpx.loc[:t - pd.Timedelta(days=1)].iloc[-1] - logpx.loc[:t - pd.Timedelta(days=1)].iloc[-1 - c.LOOK]) for t in me})
    w_g = c.weights_from_signal(sig_g, px.index)
    w_t = c.weights_from_signal(sig_t, px.index)
    avg = float(w_g.loc[days].mean())
    w_e = pd.Series(avg, index=px.index)
    res = {"window": list(window), "months": int(len(me)), "avg_exposure_G": avg,
           "share_months_on_G": float((sig_g > 0).mean()), "share_months_on_TREND": float((sig_t > 0).mean()),
           "signal_agreement_G_vs_TREND": float(((sig_g > 0) == (sig_t > 0)).mean()), "books": {}}
    ex = {}
    for name, w in (("G", w_g), ("C_EXP", w_e), ("C_TREND", w_t), ("SPY", pd.Series(1.0, index=px.index))):
        res["books"][name] = {}
        for k, cost in c.COSTS.items():
            r = c.daily_returns(w, px, rf, cost).loc[days]
            e = r - rf.loc[days]
            nav = (1 + r).cumprod()
            res["books"][name][k] = {"excess_sharpe": c.sharpe(e), "cagr": float(nav.iloc[-1] ** (252 / len(r)) - 1),
                                     "max_dd": float((nav / nav.cummax() - 1).min()), "ann_excess": float(e.mean() * 252)}
            if k in ("base", "stress"):
                ex[(name, k)] = r
    T = len(days) / 252
    gate = 1.8 / np.sqrt(T)
    act = ex[("G", "base")] - ex[("C_EXP", "base")]
    act_s = ex[("G", "stress")] - ex[("C_EXP", "stress")]
    vs_t = ex[("G", "base")] - ex[("C_TREND", "base")]
    res.update({"gate": float(gate), "active_vs_exp": {"sharpe": c.sharpe(act), "ann_mean": float(act.mean() * 252),
               "stress_ann_mean": float(act_s.mean() * 252), "bootstrap_p": block_p(act.to_numpy())},
               "G_minus_TREND": {"sharpe": c.sharpe(vs_t), "ann_mean": float(vs_t.mean() * 252),
                                 "bootstrap_p": block_p(vs_t.to_numpy())}})
    # shift null on the monthly credit signal over the full 2010-2026 grid (signals only; dev returns only)
    sig_full = pd.Series({t: c.signal_at(ce, t) for t in me_all})
    sh, sh_pass = [], 0
    for s in range(MIN_SHIFT, len(me_all) - MIN_SHIFT + 1):
        rolled = pd.Series(np.roll(sig_full.to_numpy(), s), index=me_all).loc[me]
        wn = c.weights_from_signal(rolled, px.index)
        avg_n = float(wn.loc[days].mean())
        a_n = (c.daily_returns(wn, px, rf, c.COSTS["base"]) - c.daily_returns(pd.Series(avg_n, index=px.index), px, rf, c.COSTS["base"])).loc[days]
        a_s = (c.daily_returns(wn, px, rf, c.COSTS["stress"]) - c.daily_returns(pd.Series(avg_n, index=px.index), px, rf, c.COSTS["stress"])).loc[days]
        v = c.sharpe(a_n)
        sh.append(v)
        sh_pass += int(v >= gate and a_s.mean() > 0)
    sh = np.array(sh)
    res["shift_null"] = {"n": int(len(sh)), "p": float((np.sum(sh >= res["active_vs_exp"]["sharpe"]) + 1) / (len(sh) + 1)),
                         "mean_sd": [float(np.nanmean(sh)), float(np.nanstd(sh))], "P_pass_given_null": float(sh_pass / len(sh))}
    yrs = act.groupby(act.index.year).sum()
    res["active_by_year"] = {int(k): float(v) for k, v in yrs.items()}
    tag = "dev" if window == DEV else "validation"
    pd.DataFrame({"G": ex[("G", "base")], "C_EXP": ex[("C_EXP", "base")], "C_TREND": ex[("C_TREND", "base")]}).to_csv(OUT / f"{tag}_daily_base.csv")
    pd.DataFrame({"credit_signal": sig_g, "trend_signal": sig_t}).to_csv(OUT / f"{tag}_signals.csv")
    return res


def run(mode: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not _registered(PLAN):
        raise SystemExit("PLAN not registered")
    if mode == "dev":
        if (OUT / "dev_results.json").exists():
            raise SystemExit("development already run")
        r = run_window(DEV)
        r["selected"] = bool(r["active_vs_exp"]["sharpe"] >= r["gate"] and r["active_vs_exp"]["stress_ann_mean"] > 0
                             and r["G_minus_TREND"]["ann_mean"] > 0 and r["shift_null"]["p"] < 0.05)
        (OUT / "dev_results.json").write_text(json.dumps(r, indent=2))
        print(json.dumps({k: r[k] for k in ("avg_exposure_G", "signal_agreement_G_vs_TREND", "gate", "active_vs_exp",
                                             "G_minus_TREND", "shift_null", "selected")}, indent=1))
    elif mode == "validation":
        if not _registered(UNLOCK):
            raise SystemExit("validation locked")
        if not json.loads((OUT / "dev_results.json").read_text())["selected"]:
            raise SystemExit("not selected")
        (OUT / "validation_results.json").write_text(json.dumps(run_window(VAL), indent=2))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "dev")
