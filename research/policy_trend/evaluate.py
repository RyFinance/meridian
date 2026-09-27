"""Development / validation runs for the registered policy-trend candidate P1.

  PYTHONPATH=. .venv/bin/python -m research.policy_trend.evaluate dev
  PYTHONPATH=. .venv/bin/python -m research.policy_trend.evaluate validation   # needs VALIDATION_UNLOCK.md registered
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from research.policy_trend import core as c

ROOT = c.ROOT
OUT = ROOT / "reports" / "policy_trend"
PREREG = ROOT / "research" / "preregistrations.jsonl"
PLAN, UNLOCK = "research/policy_trend/PLAN.md", "research/policy_trend/VALIDATION_UNLOCK.md"
SIG_ALL = ("2010-06-30", "2026-08-31")
DEV = ("2011-07-29", "2018-12-31")        # signal month-ends; returns run to the next month-end
VAL = ("2019-01-31", "2026-08-31")
N_PERM, SEED, MIN_SHIFT = 2000, 20260923, 18


def _registered(path: str) -> bool:
    p = ROOT / path
    if not p.exists():
        return False
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    return any(json.loads(l).get("file") == path and json.loads(l).get("sha256") == h for l in PREREG.read_text().splitlines())


def block_p(x: np.ndarray, block: int = 3, draws: int = 5000) -> float:
    n, cx = len(x), x - x.mean()
    rng = np.random.default_rng(SEED)
    idx = (rng.integers(0, n, size=(draws, -(-n // block)))[:, :, None] + np.arange(block)).reshape(draws, -1)[:, :n] % n
    return float((np.sum(cx[idx].mean(axis=1) >= x.mean()) + 1) / (draws + 1))


def stats(x: pd.Series) -> dict:
    nav = (1 + x).cumprod()
    return {"months": int(len(x)), "sharpe": c.sharpe_m(x), "ann_mean": float(x.mean() * 12),
            "ann_vol": float(x.std(ddof=1) * np.sqrt(12)), "max_dd": float((nav / nav.cummax() - 1).min()),
            "t": float(x.mean() / x.std(ddof=1) * np.sqrt(len(x))), "bootstrap_p": block_p(x.to_numpy()),
            "by_year": {int(y): float((1 + g).prod() - 1) for y, g in x.groupby(x.index.year)}}


def run_window(window: tuple[str, str]) -> dict:
    y, px = c.load_yields(), c.load_indices()
    all_dates = c.month_ends(*SIG_ALL)
    z_all, lvl_all = c.signal_panel(y, all_dates)
    dates = all_dates[(all_dates >= pd.Timestamp(window[0])) & (all_dates <= pd.Timestamp(window[1]))]
    ret_dates = all_dates[(all_dates >= dates[0])][: len(dates) + 1]
    ret = c.period_returns(px, y, ret_dates)
    vol = c.index_vol(px, ret_dates[:-1])
    z, lvl = z_all.loc[ret.index], lvl_all.loc[ret.index]
    mom = px.reindex(pd.date_range(px.index.min(), px.index.max()), method="ffill")
    mom6 = (mom.reindex(ret.index) / mom.reindex(ret.index - pd.Timedelta(days=182)).to_numpy() - 1).where(z.notna())
    books = {"P1": c.book(z, vol, low_long=True),
             "C_MOM": c.book(mom6, vol, low_long=False),
             "C_RATE": c.book(lvl, vol, low_long=True)}
    res = {"window": list(window), "months": int(len(ret)), "books": {}}
    series = {}
    for b, w in books.items():
        res["books"][b] = {k: stats(c.pnl(w, ret, cost)) for k, cost in c.COSTS.items()}
        series[b] = c.pnl(w, ret, c.COSTS["base"])
        res["books"][b]["avg_names_per_leg"] = float((w > 0).sum(axis=1).mean())
        res["books"][b]["months_long"] = {k: int(v) for k, v in (w > 0).sum().items()}
        res["books"][b]["months_short"] = {k: int(v) for k, v in (w < 0).sum().items()}
        res["books"][b]["contribution_base"] = {k: float(v) for k, v in (w.loc[ret.index] * ret.fillna(0)).sum().items()}
    sr = res["books"]["P1"]["base"]["sharpe"]
    T = len(ret) / 12
    gate = 1.8 / np.sqrt(T)
    res["dev_gate_sharpe"] = float(gate)
    res["corr_base"] = pd.DataFrame(series).corr().round(4).to_dict()
    X = np.column_stack([np.ones(len(ret)), series["C_MOM"], series["C_RATE"]])
    beta = np.linalg.lstsq(X, series["P1"].to_numpy(), rcond=None)[0]
    res["P1_alpha_on_controls_ann"] = float(beta[0] * 12)
    # null 1: within-date permutation of z across eligible economies
    rng = np.random.default_rng(SEED)
    zv = z.to_numpy()
    perm_sr, perm_pass = [], 0
    for _ in range(N_PERM):
        zp = zv.copy()
        for i in range(len(zp)):
            m = np.flatnonzero(~np.isnan(zp[i]))
            zp[i, m] = rng.permutation(zp[i, m])
        wp = c.book(pd.DataFrame(zp, index=z.index, columns=z.columns), vol, True)
        xb, xs = c.pnl(wp, ret, c.COSTS["base"]), c.pnl(wp, ret, c.COSTS["stress"])
        s_ = c.sharpe_m(xb)
        perm_sr.append(s_)
        perm_pass += int(s_ >= gate and xs.mean() > 0)
    perm_sr = np.array(perm_sr)
    res["perm_p"] = float((np.sum(perm_sr >= sr) + 1) / (N_PERM + 1))
    res["perm_sharpe_mean_sd"] = [float(perm_sr.mean()), float(perm_sr.std())]
    res["P_pass_given_null_perm"] = float(perm_pass / N_PERM)
    # null 2: circular time-shift of the full z panel (signal structure kept, alignment destroyed)
    zfull = z_all.loc[all_dates]
    shift_sr, shift_pass = [], 0
    L = len(all_dates)
    for s in range(MIN_SHIFT, L - MIN_SHIFT + 1):
        zs = pd.DataFrame(np.roll(zfull.to_numpy(), s, axis=0), index=all_dates, columns=z.columns).loc[ret.index]
        wp = c.book(zs, vol, True)
        xb, xs = c.pnl(wp, ret, c.COSTS["base"]), c.pnl(wp, ret, c.COSTS["stress"])
        s_ = c.sharpe_m(xb)
        shift_sr.append(s_)
        shift_pass += int(s_ >= gate and xs.mean() > 0)
    shift_sr = np.array(shift_sr)
    res["shift_null"] = {"n_offsets": int(len(shift_sr)), "p": float((np.sum(shift_sr >= sr) + 1) / (len(shift_sr) + 1)),
                         "mean_sd": [float(np.nanmean(shift_sr)), float(np.nanstd(shift_sr))],
                         "P_pass_given_null": float(shift_pass / len(shift_sr))}
    pd.DataFrame(series).to_csv(OUT / f"{'dev' if window == DEV else 'validation'}_monthly_base.csv")
    books["P1"].to_csv(OUT / f"{'dev' if window == DEV else 'validation'}_P1_weights.csv")
    return res


def run(mode: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not _registered(PLAN):
        raise SystemExit("PLAN not registered")
    if mode == "dev":
        if (OUT / "dev_results.json").exists():
            raise SystemExit("development already run")
        res = run_window(DEV)
        p1 = res["books"]["P1"]
        res["selected"] = bool(p1["base"]["sharpe"] >= res["dev_gate_sharpe"] and p1["stress"]["ann_mean"] > 0
                               and res["perm_p"] < 0.05)
        res["code_sha256"] = {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest()
                              for f in ("research/policy_trend/core.py", "research/policy_trend/evaluate.py")}
        (OUT / "dev_results.json").write_text(json.dumps(res, indent=2))
        print(json.dumps({b: {k: round(v["sharpe"], 3) for k, v in d.items() if isinstance(v, dict) and "sharpe" in v}
                          for b, d in res["books"].items()}), "gate", round(res["dev_gate_sharpe"], 3),
              "perm_p", round(res["perm_p"], 4), "shift_p", round(res["shift_null"]["p"], 4), "selected", res["selected"])
    elif mode == "validation":
        if not _registered(UNLOCK):
            raise SystemExit("validation locked")
        if (OUT / "validation_results.json").exists():
            raise SystemExit("validation already run")
        if not json.loads((OUT / "dev_results.json").read_text())["selected"]:
            raise SystemExit("P1 not selected in development")
        (OUT / "validation_results.json").write_text(json.dumps(run_window(VAL), indent=2))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "dev")
