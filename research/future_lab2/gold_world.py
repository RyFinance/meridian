"""Six explicit forward worlds for momentum_gold_v1 (50% SPMO / 50% GLD, first-session-close
decision, next-open fill, 5 bp/side base cost; reports/momentum_gold_20260919/forward_paper_spec.json).
First forward decision 2026-10-01.

Unit of observation: daily net total return, jointly with its control (50% SPY / 50% GLD, same
mechanics and costs) and the daily T-bill rate, exactly as research.future_lab.data.load_gold()
draws its "gold" panel -- but read here from reports/momentum_gold_20260919/ (the directory named
in this brief) rather than reports/momentum_gold_audit_20260921/ (a related but not byte-identical
export). Every draw pulls a whole historical date, so the strategy/control/rf correlation (about
0.89 in 2017-2019, 0.94 in 2020-2026) is preserved.

There is no publication event for a fund construction like this, so W1/W2 use the closest available
analogue: the report's own two-part split, "earlier" (2017-01..2019-12, pre-dates SPMO's momentum
strength showing up net of costs) and "later" (2020-01..2026-09, the regime the live paper record
will actually start in). This is explicit and, unlike TLT, not tied to a discovery/publication date;
see LIMITATIONS in the report.

Worlds:
  W0  null      -- the candidate's mean is shifted to equal the control's mean (no active edge);
                   full-history (2017-2026) pool otherwise unchanged.
  W1  "earlier" -- block-bootstrap of the 2017-2019 joint pool as observed.
  W2  "later"   -- block-bootstrap of the 2020-2026 joint pool as observed (closest thing to "the
                   regime forward data will start in").
  W3  decay     -- `later` pool's control path as observed; the active (candidate-control) residual
                   is demeaned and re-centred on a mean that decays linearly from the `later` active
                   mean to zero over 60 months, flat thereafter.
  W4  regime shift -- full-history pool, both legs' deviations from their own means scaled x1.5
                   (vol x1.5). No separate correlation-flip clause is specified for this candidate
                   in the brief (it is stated "for TLT" only).
  W5  cost shock -- `later` pool, both legs charged an extra 5 bp x (that day's own historical
                   turnover), on top of the 5 bp/side base cost already embedded in the input NAV
                   series.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from research.future_lab import engines as E
from research.return_search.run import cash_rates

ROOT = Path(__file__).resolve().parents[2]
GOLD_DIR = ROOT / "reports" / "momentum_gold_20260919"
FORWARD_SPEC_PATH = GOLD_DIR / "forward_paper_spec.json"
END = "2026-09-17"
LATER_CUTOFF = "2020-01-01"      # reports/momentum_gold_20260919/REPORT.md: "later_evaluation": 2020-2026
EXTRA_COST_PER_SIDE = 5e-4        # W5: "+5 bp per side" (applied as bps x turnover, as in future_lab.risk)
DECAY_MONTHS = 60
MONTH_DAYS = 21

WORLDS = ("W0", "W1", "W2", "W3", "W4", "W5")
WORLD_LABEL = {
    "W0": "null (no active edge over SPY/GLD)",
    "W1": "'earlier' (2017-2019) regime continues",
    "W2": "'later' (2020-2026) regime continues",
    "W3": "active edge decays to zero over 5 years",
    "W4": "regime shift: both legs' vol x1.5, means unchanged",
    "W5": "cost shock: +5 bp/side x turnover on top of the later regime",
}
WORLD_HAS_EDGE = {"W0": False, "W1": True, "W2": True, "W3": "decaying", "W4": True, "W5": True}


def load_daily() -> pd.DataFrame:
    """Joint daily frame: strat (SPMO/GLD), ctrl (SPY/GLD), rf, and each leg's own turnover."""
    mg = pd.read_csv(GOLD_DIR / "momentum_gold_full_base.csv", index_col=0, parse_dates=True)
    sg = pd.read_csv(GOLD_DIR / "market_gold_full_base.csv", index_col=0, parse_dates=True)
    if not mg.index.equals(sg.index):
        raise ValueError("momentum_gold and market_gold date indices do not match")
    rf = cash_rates(mg.index, END)
    df = pd.DataFrame({"strat": mg["return"], "ctrl": sg["return"], "rf": rf.to_numpy(),
                       "tov_strat": mg["turnover"], "tov_ctrl": sg["turnover"]}, index=mg.index)
    if df.isna().any().any():
        raise ValueError("missing values in momentum_gold daily panel")
    return df


def pools() -> dict[str, pd.DataFrame]:
    df = load_daily()
    later = df.index >= pd.Timestamp(LATER_CUTOFF)
    return {"all": df, "earlier": df.loc[~later], "later": df.loc[later]}


def block_lengths(pl: dict[str, pd.DataFrame]) -> dict[str, float]:
    """Politis-White expected block length (trading days) of each pool's active (strat-ctrl) series."""
    return {k: max(E.politis_white((v["strat"] - v["ctrl"]).to_numpy())["sb"], 1.0) for k, v in pl.items()}


def _draw(pool: pd.DataFrame, n_paths: int, horizon: int, block: float, seed: int) -> dict[str, np.ndarray]:
    idx = E.stationary_indices(len(pool), n_paths, horizon, block, seed)
    cols = {c: pool[c].to_numpy() for c in pool.columns}
    return {c: v[idx] for c, v in cols.items()}


def simulate(world: str, n_paths: int, horizon: int, seed: int, pl: dict | None = None,
            blocks: dict | None = None) -> dict[str, np.ndarray]:
    """Returns {'R': strat, 'C': ctrl, 'RF': rf}, each (n_paths, horizon) daily returns."""
    pl = pl or pools()
    blocks = blocks or block_lengths(pl)
    all_df, earlier_df, later_df = pl["all"], pl["earlier"], pl["later"]

    if world == "W0":
        shift = float(all_df["ctrl"].mean() - all_df["strat"].mean())
        d = _draw(all_df, n_paths, horizon, blocks["all"], seed)
        return {"R": d["strat"] + shift, "C": d["ctrl"], "RF": d["rf"]}
    if world == "W1":
        d = _draw(earlier_df, n_paths, horizon, blocks["earlier"], seed)
        return {"R": d["strat"], "C": d["ctrl"], "RF": d["rf"]}
    if world == "W2":
        d = _draw(later_df, n_paths, horizon, blocks["later"], seed)
        return {"R": d["strat"], "C": d["ctrl"], "RF": d["rf"]}
    if world == "W3":
        idx = E.stationary_indices(len(later_df), n_paths, horizon, blocks["later"], seed)
        ctrl = later_df["ctrl"].to_numpy()[idx]
        rf = later_df["rf"].to_numpy()[idx]
        active = (later_df["strat"] - later_df["ctrl"]).to_numpy()
        active_mean = float(active.mean())
        res = (active - active_mean)[idx]
        t = np.arange(1, horizon + 1)
        frac = np.clip(1.0 - t / DECAY_MONTHS, 0.0, None)
        mean_t = active_mean * frac
        strat = ctrl + res + mean_t[None, :]
        return {"R": strat, "C": ctrl, "RF": rf}
    if world == "W4":
        idx = E.stationary_indices(len(all_df), n_paths, horizon, blocks["all"], seed)
        mu_s, mu_c = float(all_df["strat"].mean()), float(all_df["ctrl"].mean())
        strat = mu_s + 1.5 * (all_df["strat"].to_numpy()[idx] - mu_s)
        ctrl = mu_c + 1.5 * (all_df["ctrl"].to_numpy()[idx] - mu_c)
        rf = all_df["rf"].to_numpy()[idx]
        return {"R": strat, "C": ctrl, "RF": rf}
    if world == "W5":
        d = _draw(later_df, n_paths, horizon, blocks["later"], seed)
        strat = d["strat"] - EXTRA_COST_PER_SIDE * d["tov_strat"]
        ctrl = d["ctrl"] - EXTRA_COST_PER_SIDE * d["tov_ctrl"]
        return {"R": strat, "C": ctrl, "RF": d["rf"]}
    raise ValueError(world)
