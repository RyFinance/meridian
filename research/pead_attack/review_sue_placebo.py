"""Code review + reproduction of research/edge_sue_placebo.py (reports/edge_sue_placebo/).

Recomputes every published number WITHOUT calling edge_sue_placebo.main() (which would overwrite
its own report folder). The same RNG stream is replayed: 10,000 event-level within-date permutations,
then (optionally) the 300 portfolio-harness permutations, from default_rng(17092026).

Extra checks added by the review (reported, not used to change the old verdict; the two new
event-level statistics are gated behind --extras and were run only after PLAN.md was registered):
- s1 and s2 are monotone transforms of each other under within-date permutation when no SUE is exactly
  zero, so their p-values must coincide (they do: 0.2918 both);
- share of events on single-event dates (the permutation cannot move them);
- the event-level p-values with the +1 (Phipson-Smyth) correction;
- the |SUE|>=1 statistic in SPY-excess units and restricted to the production window (2021-08..2025-06);
- timing: the event study enters next open after the reaction day; the production bot enters at the
  reaction day's close (a design difference, not look-ahead).

Run: PYTHONPATH=. .venv/bin/python -m research.pead_attack.review_sue_placebo [--portfolio]
Writes reports/pead_attack/sue_placebo_review.json only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.edge_sue_placebo import N_PERM_EVENT, N_PERM_PORT, SEED, within_date_permutations

ROOT = Path(__file__).resolve().parents[2]
EVENTS = ROOT / "reports/edge_executable_probe/events.parquet"
PUBLISHED = ROOT / "reports/edge_sue_placebo/results.json"
OUT = ROOT / "reports/pead_attack/sue_placebo_review.json"
PROD_WINDOW = ("2021-08-11", "2025-06-27")


def p_two(true_v: float, dist: np.ndarray) -> float:
    """The original's two-sided p (no +1 correction)."""
    return float(min((dist <= true_v).mean(), (dist >= true_v).mean()) * 2)


def p_two_corrected(true_v: float, dist: np.ndarray) -> float:
    n = len(dist)
    lo = (1 + (dist <= true_v).sum()) / (n + 1)
    hi = (1 + (dist >= true_v).sum()) / (n + 1)
    return float(min(1.0, 2 * min(lo, hi)))


def event_stats(sig: np.ndarray, rf: np.ndarray) -> tuple[float, float, float]:
    up, dn = sig > 0, sig < 0
    s1 = np.mean(np.sign(sig) * rf)
    s2 = (rf[up].mean() - rf[dn].mean()) / 2
    s3 = rf[np.abs(sig) >= 1].mean()
    return s1, s2, s3


def main(portfolio: bool = False, extras: bool = False) -> dict:
    events = pd.read_parquet(EVENTS)
    published = json.loads(PUBLISHED.read_text())
    codes = pd.factorize(events.date)[0]
    sig = events.signal.to_numpy(dtype=float)
    rf = events.raw_forward.to_numpy()
    ex = events.spy_excess.to_numpy()
    s1, s2, s3 = event_stats(sig, rf)
    true = {"s1_signed_mean_bps": s1 * 1e4, "s2_long_short_spread_bps": s2 * 1e4, "s3_abs_sue_ge1_mean_bps": s3 * 1e4}

    rng = np.random.default_rng(SEED)
    dist = np.empty((N_PERM_EVENT, 3))
    ex_s3 = np.empty(N_PERM_EVENT)
    win = ((events.date >= PROD_WINDOW[0]) & (events.date <= PROD_WINDOW[1])).to_numpy()
    win_s2 = np.empty(N_PERM_EVENT)
    for k, perm in enumerate(within_date_permutations(sig, codes, N_PERM_EVENT, rng)):
        dist[k] = event_stats(perm, rf)
        ex_s3[k] = ex[np.abs(perm) >= 1].mean()
        pw = perm[win]
        win_s2[k] = (rf[win][pw > 0].mean() - rf[win][pw < 0].mean()) / 2
    dist *= 1e4
    reproduced_p = {"s1_p": p_two(true["s1_signed_mean_bps"], dist[:, 0]),
                    "s2_p": p_two(true["s2_long_short_spread_bps"], dist[:, 1]),
                    "s3_p": p_two(true["s3_abs_sue_ge1_mean_bps"], dist[:, 2])}
    pub_p = published["event_placebo_p"]
    date_sizes = events.groupby("date").size()
    singleton_share = float((events.date.map(date_sizes) == 1).mean())
    true_ex_s3 = float(ex[np.abs(sig) >= 1].mean())
    true_win_s2 = float((rf[win][sig[win] > 0].mean() - rf[win][sig[win] < 0].mean()) / 2)
    out = {
        "input_sha256": hashlib.sha256(EVENTS.read_bytes()).hexdigest(),
        "input_sha256_matches_published_spec": hashlib.sha256(EVENTS.read_bytes()).hexdigest()
        == json.loads((ROOT / "reports/edge_sue_placebo/specification.json").read_text())["input_sha256"][
            "reports/edge_executable_probe/events.parquet"],
        "n_events": int(len(events)),
        "true_event_stats_bps": true,
        "published_true_event_stats_bps": {k: published["true_event_stats"][k] for k in true},
        "reproduced_event_p": reproduced_p,
        "published_event_p": {k: pub_p[k] for k in reproduced_p},
        "event_p_match": all(abs(reproduced_p[k] - pub_p[k]) < 1e-12 for k in reproduced_p),
        "event_p_plus1_corrected": {
            "s1_p": p_two_corrected(true["s1_signed_mean_bps"], dist[:, 0]),
            "s2_p": p_two_corrected(true["s2_long_short_spread_bps"], dist[:, 1]),
            "s3_p": p_two_corrected(true["s3_abs_sue_ge1_mean_bps"], dist[:, 2])},
        "s1_s2_rank_correlation_across_perms": float(pd.Series(dist[:, 0]).corr(pd.Series(dist[:, 1]), method="spearman")),
        "n_sue_exactly_zero": int((sig == 0).sum()),
        "singleton_date_event_share": singleton_share,
        "s2_placebo_quantiles_bps": np.quantile(dist[:, 1], [0.025, 0.5, 0.975]).tolist(),
        "s2_minimum_detectable_one_sided_5pct_bps": float(np.quantile(dist[:, 1], 0.95) - np.median(dist[:, 1])),
        "timing_note": "events enter at the next session open after the reaction day "
                       "(edge_executable_probe.py:91,97); the production bot fills at the reaction day's close.",
    }
    if extras:  # new event-level statistics: computed only after PLAN.md registration (PLAN section 6)
        out["extra_s3_spy_excess_bps"] = {"true": true_ex_s3 * 1e4, "p_two": p_two_corrected(true_ex_s3, ex_s3),
                                          "placebo_ci": (np.quantile(ex_s3, [0.025, 0.975]) * 1e4).tolist()}
        out["extra_s2_production_window_2021_08_2025_06_bps"] = {
            "n": int(win.sum()), "true": true_win_s2 * 1e4, "p_two": p_two_corrected(true_win_s2, win_s2),
            "placebo_ci": (np.quantile(win_s2, [0.025, 0.975]) * 1e4).tolist()}
    if portfolio:
        from research.edge_first_backtest import PERIODS, load_panel, metrics, simulate
        spy = pd.read_parquet(ROOT / "data/raw_legacy/SPY.parquet").set_index("timestamp").sort_index()
        spy.index = pd.to_datetime(spy.index).tz_localize(None).normalize()
        calendar = spy.index
        ev = events.copy()
        ev["entry_i"] = calendar.get_indexer(ev.entry_date)
        tickers = sorted(ev.ticker.unique())
        col = {t: j for j, t in enumerate(tickers)}
        opens, _, ff = load_panel(tickers, calendar)
        arm_fns = {"pead_long_short": lambda s: 1 if s > 0 else (-1 if s < 0 else 0),
                   "pead_large_sue_long": lambda s: 1 if s >= 1 else 0}
        conf_lo, conf_hi = PERIODS["confirmation"]
        port = {a: {"full": [], "conf": []} for a in arm_fns}
        for perm in within_date_permutations(sig, codes, N_PERM_PORT, rng):
            e2 = ev.copy()
            e2["signal"] = perm
            for arm, fn in arm_fns.items():
                daily, *_ = simulate(fn, opens, ff, col, e2, 10.0)
                port[arm]["full"].append(metrics(daily, calendar, calendar.min(), calendar.max())["sharpe"])
                port[arm]["conf"].append(metrics(daily, calendar, conf_lo, conf_hi)["sharpe"])
        rep = {}
        for arm, fn in arm_fns.items():
            daily, *_ = simulate(fn, opens, ff, col, ev, 10.0)
            full_true = metrics(daily, calendar, calendar.min(), calendar.max())["sharpe"]
            conf_true = metrics(daily, calendar, conf_lo, conf_hi)["sharpe"]
            f, c = np.array(port[arm]["full"]), np.array(port[arm]["conf"])
            rep[arm] = {"full_sharpe": full_true, "conf_sharpe": conf_true,
                        "full_p": p_two(full_true, f), "conf_p": p_two(conf_true, c),
                        "full_ci95": np.quantile(f, [.025, .975]).tolist(),
                        "published_full_p": published["portfolio_p"][arm]["full_p"],
                        "published_conf_p": published["portfolio_p"][arm]["conf_p"],
                        "published_full_sharpe": published["portfolio_true"][arm]["full_sharpe"]}
        out["portfolio_reproduction"] = rep
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, default=float))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--portfolio", action="store_true")
    ap.add_argument("--extras", action="store_true")
    a = ap.parse_args()
    res = main(a.portfolio, a.extras)
    print(json.dumps({k: v for k, v in res.items() if k != "portfolio_reproduction"}, indent=1, default=float))
    if "portfolio_reproduction" in res:
        print(json.dumps(res["portfolio_reproduction"], indent=1, default=float))
