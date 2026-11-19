"""Registered gate computation for the P1/P5 purchase-announcement rules.

Completion of the registered study (GATES_ADDENDUM.md, 2026-10-17 00:11:42):
the event trades were already produced by event_study.py.  This script only
evaluates the pre-registered statistic:

    P5 holdout excess = mean(net 5-session event return)
                        - mean(unconditional 5-session return, holdout sessions)
    bootstrap: resample holdout event net returns with replacement,
               10,000 draws, seed 20261017, subtract the fixed control mean,
               report the 2.5% quantile.
    PASS iff q025 > 0 AND net mean > 0.

Reads only frozen, already-produced inputs (mstr_daily_yf.parquet and the
p*_event_trades.csv files).  No network, no new data, no re-run of trades.
Writes gate_p1p5.json next to itself.

Disclosure (recorded before this script ran): ordinary_mstr_benchmark.csv
produced by event_study.py is a *daily* close-to-close summary; the registered
control is the same-holding-length (overlapping) mean, which is computed here
per the addendum text.  The verdict is also reported under the daily-return
control reading so the choice cannot flip the outcome.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DAILY = ROOT / "mstr_daily_yf.parquet"
SPLIT = pd.Timestamp("2022-12-31")
SEED = 20261017
DRAWS = 10_000
HOLDOUT = "holdout_2023_2026"
DEV = "development_2020_2022"


def control_mean(close: pd.Series, mask: np.ndarray, hold: int) -> tuple[float, int]:
    """Mean overlapping `hold`-session close-to-close return for masked sessions."""
    c = close.to_numpy(float)
    n = len(c)
    rets = c[hold:] / c[:-hold] - 1.0          # rets[i] = session i -> i+hold
    m = mask[: n - hold]
    return float(np.mean(rets[m])), int(m.sum())


def evaluate(rule: str, hold: int, daily: pd.DataFrame) -> dict:
    close = daily["Close"].astype(float)
    idx = pd.DatetimeIndex(daily.index).normalize()
    mask_hold = np.asarray(idx > SPLIT, dtype=bool)
    mask_dev = ~mask_hold

    ctrl_hold, n_hold = control_mean(close, mask_hold, hold)
    ctrl_dev, n_dev = control_mean(close, mask_dev, hold)

    t = pd.read_csv(HERE / f"{rule.lower()}_event_trades.csv")
    out: dict = {"rule": rule, "hold_sessions": hold, "samples": {}}
    for sample, ctrl, n_ctrl in ((HOLDOUT, ctrl_hold, n_hold), (DEV, ctrl_dev, n_dev)):
        a = t.loc[t["sample"] == sample, "net_return"].astype(float).to_numpy()
        rng = np.random.default_rng(SEED)
        draws = rng.choice(a, size=(DRAWS, len(a)), replace=True).mean(axis=1)
        out["samples"][sample] = {
            "n_events": int(len(a)),
            "event_net_mean": float(a.mean()),
            "event_net_boot_q025": float(np.quantile(draws, 0.025)),
            "control_mean_same_length": ctrl,
            "control_sessions": n_ctrl,
            "excess_mean": float(a.mean() - ctrl),
            "excess_boot_q025": float(np.quantile(draws - ctrl, 0.025)),
        }
    hold_d = out["samples"][HOLDOUT]
    out["primary_pass"] = bool(hold_d["excess_boot_q025"] > 0 and hold_d["event_net_mean"] > 0) if hold == 5 else None
    return out


def verdict_under_daily_control(rule: str) -> dict:
    """Same statistic, but subtracting the daily-return control (the reading
    used by event_study.py's own benchmark file). Reported for robustness."""
    daily = pd.read_parquet(DAILY).sort_index()
    close = daily["Close"].astype(float)
    idx = pd.DatetimeIndex(daily.index).normalize()
    mask_hold = np.asarray(idx > SPLIT, dtype=bool)
    ret = close.pct_change().to_numpy()
    ctrl_daily = float(ret[1:][mask_hold[1:]].mean()) if mask_hold[1:].any() else float("nan")
    t = pd.read_csv(HERE / f"{rule.lower()}_event_trades.csv")
    a = t.loc[t["sample"] == HOLDOUT, "net_return"].astype(float).to_numpy()
    rng = np.random.default_rng(SEED)
    draws = rng.choice(a, size=(DRAWS, len(a)), replace=True).mean(axis=1) - ctrl_daily
    return {"control_daily_mean": ctrl_daily, "excess_boot_q025": float(np.quantile(draws, 0.025)), "excess_mean": float(a.mean() - ctrl_daily)}


def main() -> None:
    daily = pd.read_parquet(DAILY).sort_index()
    res = {"seed": SEED, "draws": DRAWS, "daily_file": str(DAILY)}
    for rule, hold in (("P1", 1), ("P5", 5)):
        res[rule] = evaluate(rule, hold, daily)
        res[rule]["holdout_under_daily_control"] = verdict_under_daily_control(rule)
    (HERE / "gate_p1p5.json").write_text(json.dumps(res, indent=2) + "\n")
    for rule in ("P1", "P5"):
        for sample in (HOLDOUT, DEV):
            s = res[rule]["samples"][sample]
            print(f"{rule} {sample}: n={s['n_events']} event_mean={s['event_net_mean']:+.5f} "
                  f"ctrl={s['control_mean_same_length']:+.5f} excess={s['excess_mean']:+.5f} "
                  f"q025_excess={s['excess_boot_q025']:+.5f}")
        d = res[rule]["holdout_under_daily_control"]
        print(f"{rule} holdout under daily control: ctrl={d['control_daily_mean']:+.5f} "
              f"excess={d['excess_mean']:+.5f} q025={d['excess_boot_q025']:+.5f}")
    print(f"P5 primary_pass={res['P5']['primary_pass']}")
    print(f"P1 (secondary) q025>0 and mean>0: {bool(res['P1']['samples'][HOLDOUT]['excess_boot_q025'] > 0 and res['P1']['samples'][HOLDOUT]['event_net_mean'] > 0)}")


if __name__ == "__main__":
    main()
