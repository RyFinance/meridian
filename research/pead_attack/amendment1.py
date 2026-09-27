"""PLAN_AMENDMENT_1 (exploratory): volatility-matched random selection (P1V vs P1W) and shadow-ensemble power (D5).

Run: PYTHONPATH=. .venv/bin/python -m research.pead_attack.amendment1 [--draws 5000] [--procs 4]
Writes reports/pead_attack/amendment1.json, placebo_draws_P1W.csv, placebo_draws_P1V.csv
"""
from __future__ import annotations

import argparse
import json
from multiprocessing import Pool

import numpy as np
import pandas as pd

from research.pead_attack import placebo as P
from research.pead_attack.analysis import STATS, p_upper, years_for_power
from research.pead_attack.common import OUT, Inputs, book_stats
from research.pead_attack.engine import simulate
from research.pead_attack.marking import mark_book
from research.pead_audit.mtm_audit import closes as mtm_closes

FAMS = {"P1W": 11, "P1V": 12}
VOL_WINDOW = 60


def pre_event_vol(inp: Inputs) -> np.ndarray:
    ev = inp.events
    px = mtm_closes(sorted(set(ev["ticker"])))
    vol = px.pct_change(fill_method=None).rolling(VOL_WINDOW, min_periods=40).std()
    out = np.full(len(ev), np.nan)
    for k, (t, d) in enumerate(zip(ev["ticker"], pd.to_datetime(ev["earnings_date_raw"]).dt.normalize())):
        loc = vol.index.searchsorted(d, side="left") - 1  # last session strictly before the announcement day
        if loc >= 0:
            out[k] = vol[t].iloc[loc]
    return out


def blocks(inp: Inputs, vol: np.ndarray, with_vol: bool) -> np.ndarray:
    S = np.flatnonzero(inp.stream.ev_scorable)
    iso = pd.to_datetime(inp.events["date"]).dt.isocalendar()
    week = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()[S]
    if not with_vol:
        return pd.factorize(week)[0]
    v = vol[S]
    terc = pd.qcut(pd.Series(v).rank(method="first"), 3, labels=False).to_numpy()
    return pd.factorize(pd.Series(week).astype(str) + "|" + pd.Series(terc).astype(str))[0]


_G: dict = {}


def _init():
    P._init()
    inp = P._INP
    vol = pre_event_vol(inp)
    _G.update(inp=inp, codes={"P1W": blocks(inp, vol, False), "P1V": blocks(inp, vol, True)})


def _draw(family: str, k: int):
    inp = _G["inp"]
    rng = np.random.default_rng([P.SEED, FAMS[family], k])
    S = np.flatnonzero(inp.stream.ev_scorable)
    src = S[P.within_date_permutation(_G["codes"][family], rng)]
    score = np.full(len(inp.events), np.nan)
    size = np.full(len(inp.events), np.nan)
    score[S], size[S] = inp.p_real[src], inp.size_real[src]
    return score, size, inp.sign_prod


def _chunk(args):
    family, k0, k1 = args
    rows = []
    for k in range(k0, k1):
        s, z, g = _draw(family, k)
        rows.append({"draw": k, **P.evaluate_book(_G["inp"], s, z, g, P._REAL_EX, P._BOUNDS, P._REAL_GROSS)})
    return family, rows


def shadow_power(inp: Inputs, real_ex: np.ndarray, n: int = 200) -> dict:
    series = []
    for k in range(n):
        s, z, g = P.draw_inputs(inp, "P1", k)
        m = mark_book(simulate(inp.stream, s, z, g)["trades"], inp.px_mark, inp.col, inp.rf)
        series.append(m["ret"] - inp.rf)
    X = np.array(series)
    out = {}
    for K in [1, 5, 20, 100, 200]:
        d = real_ex - X[:K].mean(axis=0)
        te, gap = float(d.std(ddof=1) * np.sqrt(252)), float(d.mean() * 252)
        out[str(K)] = {"tracking_error_ann": te, "gap_ann": gap, "years_80pct_power": years_for_power(gap, te)}
    return out


def main(n_draws: int = 5000, procs: int = 4, chunk: int = 250) -> dict:
    tasks = [(f, a, min(a + chunk, n_draws)) for f in FAMS for a in range(0, n_draws, chunk)]
    res: dict[str, list] = {f: [] for f in FAMS}
    with Pool(procs, initializer=_init) as pool:
        for f, rows in pool.imap_unordered(_chunk, tasks):
            res[f].extend(rows)
    inp = Inputs()
    real = simulate(inp.stream, inp.p_real, inp.size_real, inp.sign_prod)
    m = mark_book(real["trades"], inp.px_mark, inp.col, inp.rf)
    R = book_stats(m["ret"], inp.rf, inp.calendar, m["gross"], full=True)
    vol = pre_event_vol(inp)
    tr = real["trades"]
    S = inp.stream.ev_scorable
    out = {"real_trades_mean_pre_event_vol": float(np.nanmean(vol[tr["event"].to_numpy()])),
           "scorable_events_mean_pre_event_vol": float(np.nanmean(vol[S])),
           "kelly_pass_events_mean_pre_event_vol": float(np.nanmean(vol[S & (inp.size_real > 0)])),
           "families": {}}
    for f, rows in res.items():
        d = pd.DataFrame(rows).sort_values("draw")
        d.to_csv(OUT / f"placebo_draws_{f}.csv", index=False)
        out["families"][f] = {
            "n_draws": int(len(d)), "mean_vol": float(d["ann_vol"].mean()), "mean_beta": float(d["capm_beta"].mean()),
            **{f"{s}_placebo_mean": float(d[s].mean()) for s in STATS},
            **{f"{s}_p": p_upper(R[s], d[s].to_numpy()) for s in STATS},
            "alpha_gap": R["capm_alpha"] - float(d["capm_alpha"].mean())}
    gw, gv = out["families"]["P1W"]["alpha_gap"], out["families"]["P1V"]["alpha_gap"]
    out["reading"] = ("residual mostly a volatility tilt" if gv < 0.5 * gw
                      else "residual not explained by pre-event volatility")
    out["D5_shadow_ensemble_power"] = shadow_power(inp, m["ret"] - inp.rf)
    (OUT / "amendment1.json").write_text(json.dumps(out, indent=1, default=float))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=5000)
    ap.add_argument("--procs", type=int, default=4)
    a = ap.parse_args()
    print(json.dumps(main(a.draws, a.procs), indent=1, default=float))
