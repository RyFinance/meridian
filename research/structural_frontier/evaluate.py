"""Development-only evaluation of the frozen structural-return preregistration."""
from __future__ import annotations

from calendar import monthrange
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "research/structural_frontier/PLAN.md"
REGISTRY = ROOT / "research/preregistrations.jsonl"
OUT = ROOT / "reports/structural_frontier"
DATA = ROOT / "data/lse/structural_frontier"
SEED, WORLDS = 20260923, 5000
ALPHA = 0.05 / 3


def digest(p: Path) -> str:
    return sha256(p.read_bytes()).hexdigest()


def guard() -> None:
    h = digest(PLAN)
    if not any(json.loads(line).get("file") == "research/structural_frontier/PLAN.md" and
               json.loads(line).get("sha256") == h and
               json.loads(line).get("results_computed_before_registration") is False
               for line in REGISTRY.read_text().splitlines() if line.strip()):
        raise RuntimeError("Frozen structural plan is not registered")


def etf(symbol: str, end: str, fields=("open",)) -> pd.DataFrame:
    p = ROOT / f"data/multiasset/etf/{symbol}.parquet"
    d = pd.read_parquet(p, columns=["date", *fields], filters=[("date", "<=", pd.Timestamp(end))])
    d = d.set_index("date").sort_index()
    if d.empty or d.index.max() > pd.Timestamp(end) or d.index.duplicated().any():
        raise RuntimeError(f"Bad {symbol} extent")
    if not np.isfinite(d.to_numpy(float)).all() or (d <= 0).any().any():
        raise RuntimeError(f"Bad {symbol} prices")
    return d


def monthly_mix(dates: pd.DatetimeIndex, returns: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Daily interval return for a mix rebalanced only at each month's first open."""
    if returns.shape[0] != len(dates) - 1 or returns.shape[1] != len(weights):
        raise ValueError("Mix shape mismatch")
    w = np.asarray(weights, float).copy()
    out = np.zeros(len(returns))
    for i, r in enumerate(returns):
        if i and dates[i].to_period("M") != dates[i - 1].to_period("M"):
            w = np.asarray(weights, float).copy()
        out[i] = float(np.dot(w, r))
        w = w * (1 + r) / (1 + out[i])
    return out


def sharpe(x: np.ndarray, periods: int) -> float:
    s = np.std(x, ddof=1)
    return float(np.mean(x) / s * np.sqrt(periods)) if s > 0 else float("nan")


def stats(x: np.ndarray, periods: int) -> dict:
    x = np.asarray(x, float)
    nav = np.cumprod(1 + x)
    peak = np.maximum.accumulate(np.r_[1., nav])
    return {"annual_mean": float(x.mean() * periods), "sharpe": sharpe(x, periods),
            "total_return": float(nav[-1] - 1),
            "max_drawdown": float(np.min(np.r_[1., nav] / peak - 1))}


def null_calibration(base: np.ndarray, stress: np.ndarray, periods: int,
                     sr_gate: float, block: int, extra: np.ndarray | None = None) -> dict:
    """Paired centered circular-block worlds for a fixed, unconditional return stream."""
    x, xs = np.asarray(base, float), np.asarray(stress, float)
    ex = None if extra is None else np.asarray(extra, float)
    n = len(x)
    if n < block * 3 or xs.shape != x.shape or (ex is not None and ex.shape != x.shape):
        raise ValueError("Invalid paired null inputs")
    rng = np.random.default_rng(SEED)
    null_means, null_sharpes, null_stress, null_extra = [], [], [], []
    mu = float(x.mean())
    for start in range(0, WORLDS, 200):
        batch = min(200, WORLDS - start)
        first = rng.integers(0, n, size=(batch, int(np.ceil(n / block))))
        ix = ((first[:, :, None] + np.arange(block)) % n).reshape(batch, -1)[:, :n]
        sample = x[ix] - mu
        sample_stress = xs[ix] - mu
        null_means.extend(sample.mean(axis=1).tolist())
        null_stress.extend(sample_stress.mean(axis=1).tolist())
        sd = sample.std(axis=1, ddof=1)
        null_sharpes.extend((sample.mean(axis=1) / sd * np.sqrt(periods)).tolist())
        if ex is not None:
            null_extra.extend((ex[ix] - ex.mean()).mean(axis=1).tolist())
    m = np.asarray(null_means)
    s = np.asarray(null_sharpes)
    st = np.asarray(null_stress)
    p_obs = float((1 + np.sum(m >= mu)) / (WORLDS + 1))
    # A world in the far-right 1/60 tail of this centered null passes the
    # preregistered one-sided 0.05/3 bootstrap criterion.
    p_world = (1 + np.sum(m[:, None] >= m[None, :], axis=0)) / (WORLDS + 1)
    passed = (s >= sr_gate) & (st > 0) & (p_world < ALPHA)
    if ex is not None:
        passed &= np.asarray(null_extra) > 0
    pass_prob = float(passed.mean())
    ci = np.quantile(m + mu, [0.025, 0.975]) * periods
    return {"worlds": WORLDS, "block": block, "seed": SEED,
            "null_method": "paired mean-centered circular block bootstrap",
            "p_observed_one_sided": p_obs,
            "p_full_development_pass_null": pass_prob,
            "pass_probability_mc_se": float(np.sqrt(pass_prob * (1 - pass_prob) / WORLDS)),
            "annual_mean_95pct_block_ci": [float(ci[0]), float(ci[1])],
            "null_active_sharpe_quantiles": {str(q): float(np.quantile(s, q)) for q in (.05, .5, .95, .99)}}


def rolling_removal(dates: pd.DatetimeIndex, active: np.ndarray, months: int, periods: int) -> dict:
    latest = dates[-1] - pd.DateOffset(months=months)
    best = None
    for start in dates:
        if start > latest:
            break
        end = start + pd.DateOffset(months=months)
        mask = (dates >= start) & (dates < end)
        total = float(active[mask].sum())
        if best is None or total > best[0]:
            best = (total, start, end, mask)
    return {"removed_start": str(best[1].date()), "removed_end_exclusive": str(best[2].date()),
            "remaining": stats(active[~best[3]], periods)}


def term() -> dict:
    end = "2014-12-31"
    book = {s: etf(s, end) for s in ("IEF", "SHY", "TLT", "SPY")}
    dates = book["IEF"].index
    for d in book.values():
        dates = dates.intersection(d.index)
    dates = dates[(dates >= "2003-01-02") & (dates <= end)].sort_values()
    ret = {s: d.loc[dates[1:], "open"].to_numpy() / d.loc[dates[:-1], "open"].to_numpy() - 1
           for s, d in book.items()}
    base, stress = ret["IEF"].copy(), ret["IEF"].copy()
    base[[0, -1]] -= .0003
    stress[[0, -1]] -= .0009
    barbell = monthly_mix(dates, np.column_stack([ret["TLT"], ret["SHY"]]), np.array([1 / 3, 2 / 3]))
    active, stress_active = base - ret["SHY"], stress - ret["SHY"]
    n_years = (dates[-1].date() - dates[0].date()).days / 365.25
    threshold = 1.8 / np.sqrt(n_years)
    null = null_calibration(active, stress_active, 252, threshold, 21)
    passed = bool(sharpe(active, 252) >= threshold and stress_active.mean() > 0 and
                  null["p_observed_one_sided"] < ALPHA)
    daydates = dates[:-1]
    return {"family": "Treasury term premium A", "status": "PASS_DEVELOPMENT_ONLY" if passed else "FAIL_DEVELOPMENT",
            "validation": "LOCKED; no 2015+ ETF price loaded", "plan_sha256": digest(PLAN),
            "inputs_sha256": {s: digest(ROOT / f"data/multiasset/etf/{s}.parquet") for s in book},
            "window": [str(dates[0].date()), str(dates[-1].date())], "years": n_years,
            "days": len(daydates), "active_sharpe_gate": threshold,
            "candidate_base": stats(base, 252), "candidate_stress": stats(stress, 252),
            "c0_shy": stats(ret["SHY"], 252), "c1_barbell": stats(barbell, 252),
            "active_vs_c0": stats(active, 252), "active_stress_vs_c0": stats(stress_active, 252),
            "vs_c1": stats(base - barbell, 252), "null": null,
            "correlation_active_spy_minus_shy": float(np.corrcoef(active, ret["SPY"] - ret["SHY"])[0, 1]),
            "annual_active_sum": {str(y): float(active[daydates.year == y].sum()) for y in sorted(set(daydates.year))},
            "best_12m_removed": rolling_removal(daydates, active, 12, 252),
            "best_24m_removed": rolling_removal(daydates, active, 24, 252)}


def credit() -> dict:
    end = "2016-12-30"
    book = {s: etf(s, end) for s in ("HYG", "LQD", "SHY", "SPY")}
    dates = book["HYG"].index
    for d in book.values():
        dates = dates.intersection(d.index)
    dates = dates[(dates >= "2008-01-02") & (dates <= end)].sort_values()
    ret = {s: d.loc[dates[1:], "open"].to_numpy() / d.loc[dates[:-1], "open"].to_numpy() - 1
           for s, d in book.items()}
    base, stress = ret["HYG"].copy(), ret["HYG"].copy()
    base[[0, -1]] -= .0005
    stress[[0, -1]] -= .0015
    c0 = monthly_mix(dates, np.column_stack([ret["LQD"], ret["SHY"]]), np.array([1 / 3, 2 / 3]))
    c1 = monthly_mix(dates, np.column_stack([ret["SPY"], ret["SHY"]]), np.array([1 / 4, 3 / 4]))
    active, stress_active, vs_c1 = base - c0, stress - c0, base - c1
    n_years = (dates[-1].date() - dates[0].date()).days / 365.25
    threshold = 1.8 / np.sqrt(n_years)
    null = null_calibration(active, stress_active, 252, threshold, 21, extra=vs_c1)
    passed = bool(sharpe(active, 252) >= threshold and stress_active.mean() > 0 and
                  null["p_observed_one_sided"] < ALPHA and vs_c1.mean() > 0)
    daydates = dates[:-1]
    factor = ret["SPY"] - ret["SHY"]
    beta = float(np.cov(active, factor, ddof=1)[0, 1] / np.var(factor, ddof=1))
    return {"family": "High-yield credit carry B", "status": "PASS_DEVELOPMENT_ONLY" if passed else "FAIL_DEVELOPMENT",
            "validation": "LOCKED; no 2017+ ETF price loaded", "plan_sha256": digest(PLAN),
            "inputs_sha256": {s: digest(ROOT / f"data/multiasset/etf/{s}.parquet") for s in book},
            "window": [str(dates[0].date()), str(dates[-1].date())], "years": n_years,
            "days": len(daydates), "active_sharpe_gate": threshold,
            "candidate_base": stats(base, 252), "candidate_stress": stats(stress, 252),
            "c0_lqd_shy": stats(c0, 252), "c1_spy_shy": stats(c1, 252),
            "active_vs_c0": stats(active, 252), "active_stress_vs_c0": stats(stress_active, 252),
            "vs_c1": stats(vs_c1, 252), "null": null,
            "beta_active_to_spy_minus_shy": beta,
            "correlation_active_spy_minus_shy": float(np.corrcoef(active, factor)[0, 1]),
            "annual_active_sum": {str(y): float(active[daydates.year == y].sum()) for y in sorted(set(daydates.year))},
            "best_12m_removed": rolling_removal(daydates, active, 12, 252),
            "best_24m_removed": rolling_removal(daydates, active, 24, 252)}


def third_friday(year: int, month: int) -> pd.Timestamp:
    fifteenth = pd.Timestamp(year, month, 15)
    return fifteenth + pd.Timedelta(days=(4 - fifteenth.weekday()) % 7)


def option() -> dict:
    spot_path = DATA / "TLT_spot_raw_2014_2022.parquet"
    option_path = DATA / "TLT_options_2014_2022.parquet"
    us3m_path = DATA / "US3M_2014_2022.parquet"
    spot = pd.read_parquet(spot_path, columns=["date", "close", "adj_close"],
                           filters=[("date", "<=", pd.Timestamp("2022-12-16"))]).set_index("date").sort_index()
    opt = pd.read_parquet(option_path, columns=["ts", "expiry", "opt_type", "strike", "osi", "close", "volume"],
                          filters=[("ts", "<=", pd.Timestamp("2022-11-30", tz="UTC"))])
    opt = opt[opt.opt_type == "P"].copy()
    opt["date"] = opt.ts.dt.tz_localize(None).dt.normalize()
    opt["expiry"] = pd.to_datetime(opt.expiry)
    rates = pd.read_parquet(us3m_path, filters=[("date", "<=", pd.Timestamp("2022-12-16"))])
    rates = rates[(rates.date.dt.dayofweek < 5)].set_index("date").value.astype(float).sort_index()
    if spot.index.max() > pd.Timestamp("2022-12-16") or opt.date.max() > pd.Timestamp("2022-11-30"):
        raise RuntimeError("Validation input leaked")
    cycles = []
    for year in range(2014, 2023):
        for month in range(1, 13):
            target = third_friday(year, month)
            if not (pd.Timestamp("2014-06-01") <= target <= pd.Timestamp("2022-11-30")):
                continue
            decisions = spot.index[(spot.index <= target) & (spot.index >= target - pd.Timedelta(days=2))]
            if not len(decisions):
                raise RuntimeError(f"No decision session around {target}")
            decision = decisions[-1]
            next_session = spot.index[spot.index > decision]
            if not len(next_session):
                raise RuntimeError("No next entry session")
            entry = next_session[0]
            next_month = target + pd.offsets.MonthBegin(1)
            expiry_target = third_friday(next_month.year, next_month.month)
            q = opt[(opt.date == decision) & ((opt.expiry - expiry_target).dt.days.abs() <= 1) &
                    (opt.volume >= 100)].copy()
            if q.empty:
                raise RuntimeError("Source QA expected a selected put each cycle")
            q["expiry_gap"] = (q.expiry - expiry_target).dt.days.abs()
            q["strike_gap"] = (q.strike - float(spot.loc[decision, "close"])).abs()
            q = q.sort_values(["expiry_gap", "expiry", "strike_gap", "strike"], ascending=[True, True, True, True])
            selected = q.iloc[0]
            print_on_entry = opt[(opt.date == entry) & (opt.osi == selected.osi)]
            if len(print_on_entry) != 1:
                raise RuntimeError("Selected put lacks a unique next-session print")
            last = spot.index[(spot.index <= selected.expiry) & (spot.index >= selected.expiry - pd.Timedelta(days=2))]
            if not len(last):
                raise RuntimeError("No settlement session")
            settle = last[-1]
            if settle <= entry or settle > pd.Timestamp("2022-12-16"):
                raise RuntimeError("Cycle crosses validation boundary")
            day_index = spot.index[(spot.index >= entry) & (spot.index <= settle)]
            cash_wealth = 1.0
            for d, nxt in zip(day_index[:-1], day_index[1:]):
                known = rates.index[rates.index < d]
                if not len(known) or (d - known[-1]).days > 7:
                    raise RuntimeError(f"US3M not point-in-time available at {d}")
                y = float(rates.loc[known[-1]]) / 100
                cash_wealth *= 1 + y * (nxt - d).days / 365
            cash = cash_wealth - 1
            raw_settle = float(spot.loc[settle, "close"])
            adj_return = float(spot.loc[settle, "adj_close"] / spot.loc[entry, "adj_close"] - 1)
            k, premium = float(selected.strike), float(print_on_entry.iloc[0]["close"])
            intrinsic = max(k - raw_settle, 0.0)
            assigned = intrinsic > 0
            base_fee = .05 + .0065 + (float(assigned) * (.05 + .0065))
            stress_fee = .15 + .01 + (float(assigned) * (.15 + .01))
            candidate_base = cash + (premium - intrinsic - base_fee) / k
            candidate_stress = cash + (premium - intrinsic - stress_fee) / k
            c0, c1, c2 = .5 * adj_return + .5 * cash, cash, adj_return
            cycles.append({"decision": decision, "entry": entry, "settle": settle,
                           "expiry": selected.expiry, "osi": selected.osi,
                           "strike": k, "decision_volume": int(selected.volume),
                           "premium": premium, "payoff": intrinsic, "assigned": assigned,
                           "cash": cash, "tlt_total": adj_return,
                           "candidate_base": candidate_base, "candidate_stress": candidate_stress,
                           "c0": c0, "c1": c1, "c2": c2})
    frame = pd.DataFrame(cycles)
    if len(frame) != 102 or frame.entry.duplicated().any():
        raise RuntimeError("Development option cycle count differs from source QA")
    x = frame.candidate_base.to_numpy() - frame.c0.to_numpy()
    xs = frame.candidate_stress.to_numpy() - frame.c0.to_numpy()
    xc = frame.candidate_base.to_numpy() - frame.c1.to_numpy()
    years = (frame.settle.iloc[-1].date() - frame.entry.iloc[0].date()).days / 365.25
    threshold = 1.8 / np.sqrt(years)
    null = null_calibration(x, xs, 12, threshold, 3, extra=xc)
    passed = bool(sharpe(x, 12) >= threshold and xs.mean() > 0 and xc.mean() > 0 and
                  null["p_observed_one_sided"] < ALPHA)
    OUT.mkdir(parents=True, exist_ok=True)
    frame.assign(decision=frame.decision.dt.strftime("%Y-%m-%d"),
                 entry=frame.entry.dt.strftime("%Y-%m-%d"),
                 settle=frame.settle.dt.strftime("%Y-%m-%d"),
                 expiry=frame.expiry.dt.strftime("%Y-%m-%d")).to_csv(OUT / "option_dev_cycles.csv", index=False)
    return {"family": "TLT monthly put insurance C", "status": "PASS_DEVELOPMENT_ONLY" if passed else "FAIL_DEVELOPMENT",
            "validation": "LOCKED; no 2023+ option, spot or rate return loaded",
            "plan_sha256": digest(PLAN),
            "inputs_sha256": {p.name: digest(p) for p in (spot_path, option_path, us3m_path)},
            "window": [str(frame.entry.iloc[0].date()), str(frame.settle.iloc[-1].date())],
            "years": years, "cycles": len(frame), "active_sharpe_gate": threshold,
            "candidate_base": stats(frame.candidate_base.to_numpy(), 12),
            "candidate_stress": stats(frame.candidate_stress.to_numpy(), 12),
            "c0_half_tlt": stats(frame.c0.to_numpy(), 12), "c1_bills": stats(frame.c1.to_numpy(), 12),
            "c2_full_tlt": stats(frame.c2.to_numpy(), 12),
            "active_vs_c0": stats(x, 12), "active_stress_vs_c0": stats(xs, 12),
            "premium_vs_cash": stats(xc, 12), "null": null,
            "assigned_share": float(frame.assigned.mean()),
            "median_premium_per_share": float(frame.premium.median()),
            "median_payoff_per_share": float(frame.payoff.median()),
            "worst_cycle": {"entry": str(frame.loc[frame.candidate_base.idxmin(), "entry"].date()),
                            "candidate_return": float(frame.candidate_base.min()),
                            "active_return": float(x[frame.candidate_base.idxmin()])},
            "annual_active_sum": {str(y): float(x[frame.entry.dt.year == y].sum()) for y in sorted(set(frame.entry.dt.year))},
            "execution_caveat": "LSE option close is a trade print; no historical bid/ask or precise print time"}


def main(name: str) -> None:
    guard()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}_dev_results.json"
    if path.exists():
        raise SystemExit(f"Development result already exists: {path}")
    result = {"term": term, "credit": credit, "option": option}[name]()
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ("family", "status", "window", "years", "active_sharpe_gate",
                                               "active_vs_c0", "active_stress_vs_c0", "null")}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
