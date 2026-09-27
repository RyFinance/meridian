"""Development and validation runs for the registered FX news-continuation candidates.

  PYTHONPATH=. .venv/bin/python -m research.fx_news.evaluate qa     # volatility-profile timestamp QA (|returns| only, dev years)
  PYTHONPATH=. .venv/bin/python -m research.fx_news.evaluate dev
  PYTHONPATH=. .venv/bin/python -m research.fx_news.evaluate validation   # needs VALIDATION_UNLOCK.md registered

Rules are in research/fx_news/PLAN.md.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from research.fx_news import events as evs

ROOT = Path(__file__).resolve().parents[2]
FX_DIR = ROOT / "data" / "fx_1m"
OUT = ROOT / "reports" / "fx_news"
PREREG = ROOT / "research" / "preregistrations.jsonl"
PLAN = "research/fx_news/PLAN.md"
UNLOCK = "research/fx_news/VALIDATION_UNLOCK.md"

DEV = ("2015-01-01", "2020-12-31")
VAL = ("2021-01-01", "2026-09-16")
ENTRY_MIN = 15
HOLD = {"F1": 120, "F2": 1440}        # exit minute after the release
ENTRY_LOOKBACK_MIN = 5
EXIT_LOOKBACK_MIN = {"F1": 5, "F2": 3 * 1440}
COSTS = {"gross": 0.0, "base": 1.0e-4, "stress": 3.0e-4}      # per side, per unit notional
N_PERM, SEED, BLOCK, DRAWS = 2000, 20260923, 21, 5000
PAIRS = sorted({p for p, _ in evs.PAIRS.values()})


# -- guards -----------------------------------------------------------------------------------------
def _registered(path: str) -> bool:
    if not (ROOT / path).exists():
        return False
    digest = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    return any(json.loads(l).get("file") == path and json.loads(l).get("sha256") == digest
               for l in PREREG.read_text().splitlines())


# -- prices -----------------------------------------------------------------------------------------
def load_closes(start: str, end: str) -> dict[str, pd.Series]:
    lo, hi = pd.Timestamp(start) - pd.Timedelta(days=4), pd.Timestamp(end) + pd.Timedelta(days=4)
    out = {}
    for p in PAIRS:
        parts = []
        for f in sorted(FX_DIR.glob(f"{p}_*.parquet")):
            yr = int(f.stem.split("_")[1])
            if yr < lo.year or yr > hi.year:
                continue
            d = pd.read_parquet(f, columns=["ts", "close"])
            parts.append(d)
        s = pd.concat(parts).drop_duplicates("ts").set_index("ts")["close"].sort_index()
        out[p] = s[(s.index >= lo) & (s.index <= hi)]
    return out


def price_at(s: pd.Series, t: np.ndarray, lookback_min: int) -> np.ndarray:
    """Close of the last 1m bar that ENDS at or before t (bar-start ≤ t − 1 min), within lookback."""
    idx = s.index.values
    pos = np.searchsorted(idx, (t - np.timedelta64(1, "m")), side="right") - 1
    ok = pos >= 0
    out = np.full(len(t), np.nan)
    got = idx[np.clip(pos, 0, None)]
    ok &= (t - np.timedelta64(1, "m") - got) <= np.timedelta64(lookback_min, "m")
    out[ok] = s.values[pos[ok]]
    return out


def currency_returns(groups: pd.DataFrame, closes: dict, t_from: np.ndarray, t_to: np.ndarray,
                     lb_from: int, lb_to: int) -> np.ndarray:
    """Return of 'currency up' between two times for each event group; USD = equal 6-pair basket."""
    legs = {}
    for ccy, (pair, orient) in evs.PAIRS.items():
        a = price_at(closes[pair], t_from, lb_from)
        b = price_at(closes[pair], t_to, lb_to)
        legs[ccy] = orient * (b / a - 1.0)
    r = np.full(len(groups), np.nan)
    ccy = groups["ccy"].to_numpy()
    for c in evs.PAIRS:
        m = ccy == c
        r[m] = legs[c][m]
    m = ccy == "USD"
    r[m] = -np.nanmean(np.vstack([legs[c][m] for c in evs.USD_BASKET]), axis=0) if m.any() else r[m]
    return r


# -- statistics -------------------------------------------------------------------------------------
def daily_series(pnl: np.ndarray, exit_day: np.ndarray, days: pd.DatetimeIndex) -> pd.Series:
    s = pd.Series(pnl).groupby(exit_day).sum()
    return s.reindex(days, fill_value=0.0)


def sharpe(x: np.ndarray) -> float:
    sd = x.std(ddof=1)
    return float(x.mean() / sd * np.sqrt(252)) if sd > 0 else float("nan")


def block_bootstrap_p(x: np.ndarray) -> float:
    n = len(x)
    c = x - x.mean()
    rng = np.random.default_rng(SEED)
    nb = int(np.ceil(n / BLOCK))
    starts = rng.integers(0, n, size=(DRAWS, nb))
    idx = (starts[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(DRAWS, -1)[:, :n] % n
    return float((np.sum(c[idx].mean(axis=1) >= x.mean()) + 1) / (DRAWS + 1))


def summarize(events: pd.DataFrame, sign: np.ndarray, R: np.ndarray, days, cost: float) -> dict:
    pnl = sign * R - 2 * cost
    d = daily_series(pnl, events["exit_day"].to_numpy(), days).to_numpy()
    return {"events": int(len(pnl)), "mean_bps": float(np.mean(pnl) * 1e4),
            "hit_rate": float(np.mean(pnl > 0)), "daily_sharpe": sharpe(d),
            "ann_mean_units": float(d.mean() * 252), "ann_vol_units": float(d.std(ddof=1) * np.sqrt(252)),
            "bootstrap_p": block_bootstrap_p(d)}


# -- runs -------------------------------------------------------------------------------------------
def event_table(window: tuple[str, str], hold_key: str):
    rel = evs.releases(*window)
    g = evs.event_groups(rel)
    g = g[(g["t0"] >= pd.Timestamp(window[0])) & (g["t0"] < pd.Timestamp(window[1]) + pd.Timedelta(days=1))]
    g = g[g["ccy"] != "CHF"].reset_index(drop=True)
    closes = load_closes(*window)
    t0 = g["t0"].to_numpy(dtype="datetime64[ns]")
    t_in = t0 + np.timedelta64(ENTRY_MIN, "m")
    t_out = t0 + np.timedelta64(HOLD[hold_key], "m")
    g["R"] = currency_returns(g, closes, t_in, t_out, ENTRY_LOOKBACK_MIN, EXIT_LOOKBACK_MIN[hold_key])
    g["react"] = currency_returns(g, closes, t0, t_in, ENTRY_LOOKBACK_MIN, ENTRY_LOOKBACK_MIN)
    xd = pd.to_datetime(t_out).normalize()
    wd = xd.dayofweek
    g["exit_day"] = xd - pd.to_timedelta(np.where(wd == 5, 1, np.where(wd == 6, 2, 0)), unit="D")  # weekend -> Friday price
    days = pd.bdate_range(window[0], window[1])
    n_all = len(g)
    g = g[np.isfinite(g["R"]) & np.isfinite(g["react"]) & g["exit_day"].isin(days)].reset_index(drop=True)
    return g, days, n_all


def evaluate(window, candidates=("F1", "F2"), tag: str = "dev") -> dict:
    res = {"window": list(window), "candidates": {}}
    for k in candidates:
        g, days, n_all = event_table(window, k)
        R, s = g["R"].to_numpy(), g["sign"].to_numpy().astype(float)
        out = {"event_groups_total": int(n_all), "event_groups_priced": int(len(g))}
        for label, c in COSTS.items():
            out[label] = summarize(g, s, R, days, c)
        # controls
        out["C_REACT_base"] = summarize(g, np.sign(g["react"].to_numpy()), R, days, COSTS["base"])
        out["C_ALL_base"] = summarize(g, np.ones(len(g)), R, days, COSTS["base"])
        corr_sign_react = float(np.corrcoef(s, np.sign(g["react"].to_numpy()))[0, 1])
        out["corr_surprise_sign_vs_reaction_sign"] = corr_sign_react
        # permutation null: shuffle trade signs within (currency, category-set) strata
        rng = np.random.default_rng(SEED)
        strata = (g["ccy"] + "|" + g["categories"]).to_numpy()
        exit_day = g["exit_day"].to_numpy()
        perm_sr, perm_pass = [], 0
        gate = 1.8 / np.sqrt(len(days) / 252)
        for _ in range(N_PERM):
            sp = s.copy()
            for st in np.unique(strata):
                m = np.flatnonzero(strata == st)
                sp[m] = rng.permutation(sp[m])
            db = daily_series(sp * R - 2 * COSTS["base"], exit_day, days).to_numpy()
            ds = daily_series(sp * R - 2 * COSTS["stress"], exit_day, days).to_numpy()
            sr = sharpe(db)
            perm_sr.append(sr)
            perm_pass += int(sr >= gate and ds.mean() > 0)
        perm_sr = np.array(perm_sr)
        out["dev_gate_sharpe"] = float(gate)
        out["perm_p_one_sided"] = float((np.sum(perm_sr >= out["base"]["daily_sharpe"]) + 1) / (N_PERM + 1))
        out["perm_sharpe_mean_sd"] = [float(perm_sr.mean()), float(perm_sr.std())]
        out["P_pass_given_null"] = float(perm_pass / N_PERM)
        # descriptive breakdowns (base cost)
        pnl = s * R - 2 * COSTS["base"]
        out["by_ccy_mean_bps"] = {c: [float(pnl[g["ccy"] == c].mean() * 1e4), int((g["ccy"] == c).sum())]
                                  for c in sorted(g["ccy"].unique())}
        cat1 = g["categories"].str.split(",").str[0]
        out["by_category_mean_bps"] = {c: [float(pnl[cat1 == c].mean() * 1e4), int((cat1 == c).sum())]
                                       for c in sorted(cat1.unique())}
        yr = g["t0"].dt.year
        out["by_year"] = {int(y): {"mean_bps": float(pnl[yr == y].mean() * 1e4), "n": int((yr == y).sum()),
                                   "daily_sharpe": sharpe(daily_series(pnl[yr == y], exit_day[yr == y],
                                                                       days[days.year == y]).to_numpy())}
                          for y in sorted(yr.unique())}
        out["gross_continuation_bps_by_reaction_size"] = _by_reaction(g, s, R)
        res["candidates"][k] = out
        g.assign(pnl_base=pnl).to_parquet(OUT / f"{tag}_{k}_events.parquet")
        print(k, {kk: (round(v["daily_sharpe"], 3), round(v["mean_bps"], 3)) for kk, v in out.items()
                  if isinstance(v, dict) and "daily_sharpe" in v}, "perm_p", round(out["perm_p_one_sided"], 4),
              "P(pass|null)", out["P_pass_given_null"], flush=True)
    return res


def _by_reaction(g, s, R) -> dict:
    q = pd.qcut(np.abs(g["react"]), 5, labels=False, duplicates="drop")
    return {int(k): float((s * R)[q == k].mean() * 1e4) for k in sorted(np.unique(q))}


def qa() -> None:
    """Direction-free timestamp check: mean |1m return| of the traded pair around corrected t0, dev years."""
    rel = evs.releases(*DEV)
    g = evs.event_groups(rel)
    g = g[(g["ccy"] != "CHF") & (g["ccy"] != "USD")]
    closes = load_closes(*DEV)
    prof = {}
    for ccy, (pair, _) in evs.PAIRS.items():
        m = g["ccy"] == ccy
        if not m.any():
            continue
        s = closes[pair]
        lr = np.log(s).diff().abs()
        t0 = g.loc[m, "t0"].to_numpy(dtype="datetime64[ns]")
        rows = []
        for k in range(-150, 151):
            t = t0 + np.timedelta64(k, "m")
            v = lr.reindex(pd.DatetimeIndex(t)).to_numpy()
            rows.append(np.nanmean(v) * 1e4)
        prof[ccy] = rows
    usd = g  # USD checked via EURUSD
    rel_us = evs.event_groups(evs.releases(*DEV))
    t0 = rel_us.loc[rel_us["ccy"] == "USD", "t0"].to_numpy(dtype="datetime64[ns]")
    lr = np.log(closes["EURUSD"]).diff().abs()
    prof["USD(EURUSD)"] = [np.nanmean(lr.reindex(pd.DatetimeIndex(t0 + np.timedelta64(k, "m"))).to_numpy()) * 1e4
                           for k in range(-150, 151)]
    peaks = {c: int(np.nanargmax(v) - 150) for c, v in prof.items()}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "qa_timestamp_profile.json").write_text(json.dumps({"peak_minute_offset": peaks,
                                                               "profile_bps": prof}, indent=1))
    print("peak minute of mean |1m return| relative to corrected t0:", peaks)


def run(mode: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if mode == "qa":
        qa()
        return
    if not _registered(PLAN):
        raise SystemExit("PLAN not registered with a matching hash")
    if mode == "dev":
        if (OUT / "dev_results.json").exists():
            raise SystemExit("development already run")
        res = evaluate(DEV)
        sel = []
        for k, v in res["candidates"].items():
            if (v["base"]["daily_sharpe"] >= v["dev_gate_sharpe"] and v["stress"]["ann_mean_units"] > 0
                    and v["perm_p_one_sided"] < 0.05):
                sel.append(k)
        res["selected"] = sel
        res["code_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        (OUT / "dev_results.json").write_text(json.dumps(res, indent=2))
        print("selected:", sel)
    elif mode == "validation":
        if not _registered(UNLOCK):
            raise SystemExit("validation locked")
        if (OUT / "validation_results.json").exists():
            raise SystemExit("validation already run")
        sel = json.loads((OUT / "dev_results.json").read_text())["selected"]
        if not sel:
            raise SystemExit("nothing selected")
        res = evaluate(VAL, tuple(sel), tag="validation")
        (OUT / "validation_results.json").write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "dev")
