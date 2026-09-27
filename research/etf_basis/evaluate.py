"""QA / development / validation for the registered bond-ETF basis book B.

  PYTHONPATH=. .venv/bin/python -m research.etf_basis.evaluate qa    # trigger counts only, no returns
  PYTHONPATH=. .venv/bin/python -m research.etf_basis.evaluate dev
"""
from __future__ import annotations

import hashlib
import json
import sys

import numpy as np
import pandas as pd

from research.etf_basis import core as c
from research.return_search.run import cash_rates

ROOT = c.ROOT
OUT = ROOT / "reports" / "etf_basis"
PREREG = ROOT / "research" / "preregistrations.jsonl"
PLAN, UNLOCK = "research/etf_basis/PLAN.md", "research/etf_basis/VALIDATION_UNLOCK.md"
DEV, VAL = ("2010-01-04", "2017-12-29"), ("2018-01-02", "2026-09-10")
SEED, N_SHIFT, MIN_SHIFT = 20260924, 500, 60


def _registered(p):
    f = ROOT / p
    if not f.exists():
        return False
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    return any(json.loads(l).get("file") == p and json.loads(l).get("sha256") == h for l in PREREG.read_text().splitlines())


def prepare(window):
    data = {}
    for etf, idx in c.PAIRS.items():
        df = c.load(etf, idx, window[1])
        sess = df["etf"].dropna().index
        data[etf] = {"df": df, "sess": sess, "bz": c.basis_z(df).reindex(sess), "oz": c.own_z(df).reindex(sess),
                     "px": df["etf"].reindex(sess)}
    return data


def qa():
    d = prepare(("2010-01-04", "2026-09-10"))
    out = {}
    for etf, v in d.items():
        bz, oz = v["bz"], v["oz"]
        yr = bz.index.year
        out[etf] = {"basis_trigger_days_by_year": {int(y): int((bz[yr == y] <= c.Z).sum()) for y in sorted(set(yr))},
                    "own_trigger_days_by_year": {int(y): int((oz[yr == y] <= c.Z).sum()) for y in sorted(set(yr))},
                    "overlap_share": float(((bz <= c.Z) & (oz <= c.Z)).sum() / max(1, (bz <= c.Z).sum())),
                    "corr_bz_oz": float(bz.corr(oz)), "first_valid_z": str(bz.first_valid_index().date())}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "qa.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def book(data, trig_key, window, cost, rf):
    parts = []
    for etf, v in data.items():
        sess = v["sess"][(v["sess"] >= pd.Timestamp(window[0])) & (v["sess"] <= pd.Timestamp(window[1]))]
        pos = c.positions(v[trig_key], v["sess"]).reindex(sess)
        parts.append(c.sleeve_returns(pos, v["px"].reindex(sess), rf.reindex(sess).fillna(0), cost).rename(etf))
    return pd.concat(parts, axis=1).fillna(0).mean(axis=1), parts


def run_window(window):
    data = prepare(window)
    allsess = sorted(set().union(*[set(v["sess"]) for v in data.values()]))
    rf = cash_rates(pd.DatetimeIndex(allsess), window[1])
    res = {"window": list(window), "books": {}}
    series = {}
    for key, name in (("bz", "B"), ("oz", "C_REV")):
        for k, cost in c.COSTS.items():
            r, _ = book(data, key, window, cost, rf)
            first = max(v["bz"].first_valid_index() for v in data.values())
            r = r.loc[first:]
            series[(name, k)] = r
            res["books"].setdefault(name, {})[k] = {"sharpe": c.sharpe(r), "ann_excess": float(r.mean() * 252)}
    # exposure-matched control: constant average position in each ETF
    exp_parts, avg = [], {}
    first = series[("B", "base")].index[0]
    for etf, v in data.items():
        sess = v["sess"][(v["sess"] >= first) & (v["sess"] <= pd.Timestamp(window[1]))]
        pos = c.positions(v["bz"], v["sess"]).reindex(sess)
        avg[etf] = float(pos.mean())
        r = v["px"].reindex(sess).pct_change().fillna(0) - rf.reindex(sess).fillna(0)
        exp_parts.append((avg[etf] * r).rename(etf))
    c_exp = pd.concat(exp_parts, axis=1).fillna(0).mean(axis=1)
    res["avg_position"] = avg
    T = len(series[("B", "base")]) / 252
    gate = 1.8 / np.sqrt(T)
    act = series[("B", "base")] - c_exp.reindex(series[("B", "base")].index).fillna(0)
    act_s = series[("B", "stress")] - c_exp.reindex(series[("B", "stress")].index).fillna(0)
    vs_rev = series[("B", "base")] - series[("C_REV", "base")].reindex(series[("B", "base")].index).fillna(0)
    res.update({"gate": float(gate), "years": T,
                "active_vs_exposure": {"sharpe": c.sharpe(act), "ann": float(act.mean() * 252), "stress_ann": float(act_s.mean() * 252)},
                "B_minus_C_REV": {"sharpe": c.sharpe(vs_rev), "ann": float(vs_rev.mean() * 252)},
                "per_trade_bps_base": {}})
    # per-trigger 5-day forward excess return (descriptive)
    for etf, v in data.items():
        sess = v["sess"]
        r = v["px"].pct_change()
        fwd = sum(r.shift(-(k + 2)) for k in range(c.HOLD))
        m = (v["bz"] <= c.Z) & (sess >= first) & (sess <= pd.Timestamp(window[1]))
        res["per_trade_bps_base"][etf] = {"n_trigger_days": int(m.sum()), "mean_fwd5_bps": float(fwd[m].mean() * 1e4),
                                          "uncond_fwd5_bps": float(fwd[(sess >= first) & (sess <= pd.Timestamp(window[1]))].mean() * 1e4)}
    # circular-shift null of the basis trigger series (clustering kept, alignment broken)
    rng = np.random.default_rng(SEED)
    null_sr, null_pass = [], 0
    for _ in range(N_SHIFT):
        parts, parts_s = [], []
        for etf, v in data.items():
            sess = v["sess"][(v["sess"] >= first) & (v["sess"] <= pd.Timestamp(window[1]))]
            bz = v["bz"].reindex(sess)
            s = int(rng.integers(MIN_SHIFT, len(sess) - MIN_SHIFT))
            shifted = pd.Series(np.roll(bz.to_numpy(), s), index=sess)
            pos = c.positions(shifted, sess)
            px, rr = v["px"].reindex(sess), rf.reindex(sess).fillna(0)
            ap = float(pos.mean())
            ex = px.pct_change().fillna(0) - rr
            parts.append((c.sleeve_returns(pos, px, rr, c.COSTS["base"]) - ap * ex).rename(etf))
            parts_s.append((c.sleeve_returns(pos, px, rr, c.COSTS["stress"]) - ap * ex).rename(etf))
        a = pd.concat(parts, axis=1).fillna(0).mean(axis=1)
        a_s = pd.concat(parts_s, axis=1).fillna(0).mean(axis=1)
        v_ = c.sharpe(a)
        null_sr.append(v_)
        null_pass += int(v_ >= gate and a_s.mean() > 0)
    null_sr = np.array(null_sr)
    res["shift_null"] = {"n": N_SHIFT, "p": float((np.sum(null_sr >= res["active_vs_exposure"]["sharpe"]) + 1) / (N_SHIFT + 1)),
                         "mean_sd": [float(np.nanmean(null_sr)), float(np.nanstd(null_sr))], "q95_q99": [float(np.nanquantile(null_sr, .95)), float(np.nanquantile(null_sr, .99))],
                         "P_pass_given_null": float(null_pass / N_SHIFT)}
    res["active_by_year"] = {int(y): float(g.sum()) for y, g in act.groupby(act.index.year)}
    tag = "dev" if window == DEV else "validation"
    pd.DataFrame({"B": series[("B", "base")], "C_REV": series[("C_REV", "base")], "C_EXP": c_exp}).to_csv(OUT / f"{tag}_daily.csv")
    return res


def run(mode):
    OUT.mkdir(parents=True, exist_ok=True)
    if mode == "qa":
        return qa()
    if not _registered(PLAN):
        raise SystemExit("PLAN not registered")
    if mode == "dev":
        if (OUT / "dev_results.json").exists():
            raise SystemExit("already run")
        r = run_window(DEV)
        r["selected"] = bool(r["active_vs_exposure"]["sharpe"] >= r["gate"] and r["active_vs_exposure"]["stress_ann"] > 0
                             and r["B_minus_C_REV"]["ann"] > 0 and r["shift_null"]["p"] < 0.05)
        (OUT / "dev_results.json").write_text(json.dumps(r, indent=2))
        print(json.dumps({k: v for k, v in r.items() if k != "active_by_year"}, indent=1))
    elif mode == "validation":
        if not _registered(UNLOCK):
            raise SystemExit("validation locked")
        if not json.loads((OUT / "dev_results.json").read_text())["selected"]:
            raise SystemExit("not selected")
        (OUT / "validation_results.json").write_text(json.dumps(run_window(VAL), indent=2))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "dev")
