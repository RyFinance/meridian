"""Pre-registered portfolio-level placebo (research/pead_attack/PLAN.md sections 3-5).

Every book -- the real one and every placebo draw -- runs through the same engine (production rules,
reproduced trade for trade) and the same marking (mtm_audit.mtm_book accounting, idle cash at T-bills).
Only the per-event conviction score, size and direction change:

  P1   within-date permutation of the model's calibrated probabilities over the scorable events (primary);
       size = production quarter-Kelly of the permuted probability; direction = the event's own SUE sign
  P1L  P1's permutations, every position long (generic post-announcement exposure, exposure-matched)
  P1G  permutation over the whole window instead of within date (selection + timing)
  P2   SUE-sign only: every scorable event, uniform conviction (random order), 5% size, SUE-sign direction
  P3   all scorable events, no selection: uniform conviction (random order), 5% size, long

Seeds: numpy default_rng([20260923, family_id, draw]); P1L reuses P1's family id so draws are paired.
Run: PYTHONPATH=. .venv/bin/python -m research.pead_attack.placebo [--draws N] [--procs 4]
Writes reports/pead_attack/placebo_draws_<family>.csv
"""
from __future__ import annotations

import argparse
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

from research.pead_attack.common import OUT, Inputs, book_stats
from research.pead_attack.engine import simulate
from research.pead_attack.marking import mark_book

SEED = 20260923
N_DRAWS = 10_000
FIXED_SIZE = 0.05  # PRODUCTION_LIMITS.max_position_pct
FAMILIES = {  # name: (seed family id, score rule, size rule, direction rule)
    "P1": (1, "perm_within_date", "kelly", "sue"),
    "P1L": (1, "perm_within_date", "kelly", "long"),
    "P1G": (5, "perm_global", "kelly", "sue"),
    "P2": (2, "uniform", "fixed", "sue"),
    "P3": (3, "uniform", "fixed", "long"),
}

_INP: Inputs | None = None


def within_date_permutation(codes: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Index permutation that maps each element to a uniformly random element with the same code.
    Returns perm such that new_value[i] = value[perm[i]]."""
    order = np.argsort(codes, kind="stable")
    u = rng.random(len(codes))
    pw = np.lexsort((u, codes[order]))  # same code blocks, random order inside each block
    perm = np.empty(len(codes), dtype=int)
    perm[order] = order[pw]
    return perm


def draw_inputs(inp: Inputs, family: str, k: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    fam_id, score_rule, size_rule, dir_rule = FAMILIES[family]
    rng = np.random.default_rng([SEED, fam_id, k])
    S = np.flatnonzero(inp.stream.ev_scorable)
    n = len(inp.events)
    score = np.full(n, np.nan)
    size = np.full(n, np.nan)
    if score_rule == "perm_within_date":
        codes = pd.factorize(inp.events["date"].to_numpy()[S])[0]
        src = S[within_date_permutation(codes, rng)]
        score[S], size[S] = inp.p_real[src], inp.size_real[src]
    elif score_rule == "perm_global":
        src = S[rng.permutation(len(S))]
        score[S], size[S] = inp.p_real[src], inp.size_real[src]
    elif score_rule == "uniform":
        score[S] = rng.random(len(S))
        size[S] = FIXED_SIZE
    sign = inp.sign_prod if dir_rule == "sue" else np.ones(n)
    return score, size, sign


def subwindow_sharpes(ex: np.ndarray, bounds: list[tuple[int, int]]) -> list[float]:
    out = []
    for a, b in bounds:
        x = ex[a:b]
        out.append(float(x.mean() / x.std(ddof=1) * np.sqrt(252)))
    return out


def holdout_bounds(inp: Inputs) -> tuple[list[str], list[tuple[int, int]]]:
    from ml.validation import split_time_disjoint_panel
    from research.pead_attack.common import ROOT
    df = pd.read_parquet(ROOT / "data" / "pead_labeled_features_expanded.parquet", columns=["date"])
    _, parts = split_time_disjoint_panel(df, holding_period=20, min_rows_per_partition=100)
    starts = [pd.Timestamp(p.start) for p in parts if p.name.startswith("holdout")]
    idx = [int(inp.dates.searchsorted(s)) for s in starts] + [len(inp.dates)]
    return ["holdout_a", "holdout_b", "holdout_c"], [(idx[j], idx[j + 1]) for j in range(3)]


def evaluate_book(inp: Inputs, score, size, sign, real_ex: np.ndarray | None, bounds,
                  real_gross: float | None = None) -> dict:
    res = simulate(inp.stream, score, size, sign)
    m = mark_book(res["trades"], inp.px_mark, inp.col, inp.rf)
    st = book_stats(m["ret"], inp.rf, inp.calendar, m["gross"], full=True)
    st.pop("ff6_loadings", None)
    st.pop("ff6_days", None)
    tr = res["trades"]
    st.update({"n_trades": int(len(tr)), "long_share": float((tr["sign"] > 0).mean()) if len(tr) else np.nan,
               "killed": bool(res["killed"])})
    ex = m["ret"] - inp.rf
    for name, s in zip(["sharpe_ha", "sharpe_hb", "sharpe_hc"], subwindow_sharpes(ex, bounds)):
        st[name] = s
    if real_gross is not None and st["avg_gross"] > 0:
        k = real_gross / st["avg_gross"]  # PLAN 4: exposure-matched CAGR (excess return scaled to the real book's gross)
        st["cagr_expmatch"] = float(np.prod(1 + inp.rf + k * ex) ** (252 / len(ex)) - 1)
    if real_ex is not None:
        d = real_ex - ex
        st["diff_mean_ann"] = float(d.mean() * 252)
        st["diff_vol_ann"] = float(d.std(ddof=1) * np.sqrt(252))
        st["corr_with_real"] = float(np.corrcoef(real_ex, ex)[0, 1])
    return st


def _init():
    global _INP, _REAL_EX, _BOUNDS, _REAL_GROSS
    _INP = Inputs()
    real = simulate(_INP.stream, _INP.p_real, _INP.size_real, _INP.sign_prod)
    m = mark_book(real["trades"], _INP.px_mark, _INP.col, _INP.rf)
    _REAL_EX = m["ret"] - _INP.rf
    _REAL_GROSS = float(np.mean(m["gross"]))
    _BOUNDS = holdout_bounds(_INP)[1]


def _run_chunk(args):
    family, k0, k1 = args
    rows = []
    for k in range(k0, k1):
        score, size, sign = draw_inputs(_INP, family, k)
        rows.append({"draw": k, **evaluate_book(_INP, score, size, sign, _REAL_EX, _BOUNDS, _REAL_GROSS)})
    return family, rows


def main(n_draws: int = N_DRAWS, procs: int = 4, families: list[str] | None = None, chunk: int = 250) -> None:
    families = families or list(FAMILIES)
    tasks = [(f, a, min(a + chunk, n_draws)) for f in families for a in range(0, n_draws, chunk)]
    t0 = time.time()
    results: dict[str, list] = {f: [] for f in families}
    with Pool(procs, initializer=_init) as pool:
        for i, (f, rows) in enumerate(pool.imap_unordered(_run_chunk, tasks)):
            results[f].extend(rows)
            if (i + 1) % 10 == 0:
                print(f"{i + 1}/{len(tasks)} chunks, {time.time() - t0:.0f}s", flush=True)
    for f, rows in results.items():
        pd.DataFrame(rows).sort_values("draw").to_csv(OUT / f"placebo_draws_{f}.csv", index=False)
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=N_DRAWS)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--families", nargs="*")
    a = ap.parse_args()
    main(a.draws, a.procs, a.families)
