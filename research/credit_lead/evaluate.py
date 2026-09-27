"""Frozen LSE HY/IG credit-information development test (no validation data loaded)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.null_lab.api import builders, run_null
from research.null_lab.engines import sharpe
from research.null_lab.gates import BootstrapP, Gate


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/lse/credit_lead"
OUT = ROOT / "reports/credit_lead"
BASE_COST = 0.0003
STRESS_COST = 0.0009
SEED = 20260923


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def etf(symbol: str) -> pd.DataFrame:
    path = ROOT / f"data/multiasset/etf/{symbol}.parquet"
    d = pd.read_parquet(path, columns=["date", "open", "close"],
                        filters=[("date", "<=", pd.Timestamp("2020-12-31"))])
    d = d.set_index("date").sort_index()
    if d.empty or d.index.max() > pd.Timestamp("2020-12-31") or d.index.duplicated().any():
        raise RuntimeError(f"Bad {symbol} date extent")
    if not np.isfinite(d[["open", "close"]].to_numpy(float)).all() or (d[["open", "close"]] <= 0).any().any():
        raise RuntimeError(f"Bad {symbol} prices")
    return d


def credit(symbol: str) -> pd.Series:
    d = pd.read_parquet(INPUT / f"{symbol}_dev.parquet")
    if d.date.max() > pd.Timestamp("2020-12-31") or d.date.duplicated().any() or not (d.symbol == symbol).all():
        raise RuntimeError(f"Bad {symbol} data")
    s = d.set_index("date").value.astype(float).sort_index()
    if not np.isfinite(s.to_numpy()).all() or (s <= 0).any():
        raise RuntimeError(f"Nonpositive/nonfinite {symbol} level")
    return s


@dataclass
class Inputs:
    dates: pd.DatetimeIndex
    monthly_dates: pd.DatetimeIndex
    month_index: np.ndarray
    spy_open_returns: np.ndarray
    ief_open_returns: np.ndarray
    real_weights: np.ndarray
    c1_weights: np.ndarray
    c2_weights: np.ndarray
    decisions: list[dict]
    input_hashes: dict


def build_inputs() -> Inputs:
    spy, ief, hyg, lqd = (etf(s) for s in ("SPY", "IEF", "HYG", "LQD"))
    dates = spy.index.intersection(ief.index).sort_values()
    dates = dates[(dates >= "2010-01-01") & (dates <= "2020-12-31")]
    hy, ig = credit("USD_LIQ_HY"), credit("USD_LIQ_IG")
    common_credit = hy.index.intersection(ig.index).intersection(dates).sort_values()
    ratio = np.log(hy.reindex(common_credit).to_numpy() / ig.reindex(common_credit).to_numpy())
    if len(common_credit) < 2000:
        raise RuntimeError("Insufficient credit overlap")

    dev = dates[(dates >= "2012-01-01") & (dates <= "2020-12-31")]
    monthly = dev.to_series().groupby(dev.to_period("M")).first().to_numpy(dtype="datetime64[ns]")
    monthly = pd.DatetimeIndex(monthly)
    decisions: list[dict] = []
    real, c1, c2 = [], [], []
    for decision in monthly:
        prev_month = decision.to_period("M") - 1
        prior = dates[dates.to_period("M") == prev_month]
        if len(prior) < 2:
            raise RuntimeError(f"Prior month absent for {decision}")
        cutoff = prior[-2]
        cutoff_ix = int(dates.get_loc(cutoff))
        eligible = common_credit[common_credit <= cutoff]
        credit_weight = 0.5
        last_credit = None
        signal = None
        if len(eligible) >= 21:
            last_credit = eligible[-1]
            age = cutoff_ix - int(dates.get_loc(last_credit))
            if age <= 3:
                ix = int(common_credit.get_loc(last_credit))
                signal = float(ratio[ix] - ratio[ix - 20])
                credit_weight = float(signal > 0)
        real.append(credit_weight)

        old_date = dates[cutoff_ix - 20]
        spy_signal = float(np.log(spy.loc[cutoff, "close"] / spy.loc[old_date, "close"]))
        c1.append(float(spy_signal > 0))
        if cutoff in hyg.index and old_date in hyg.index and cutoff in lqd.index and old_date in lqd.index:
            etf_signal = float(np.log((hyg.loc[cutoff, "close"] / lqd.loc[cutoff, "close"]) /
                                      (hyg.loc[old_date, "close"] / lqd.loc[old_date, "close"])))
            c2.append(float(etf_signal > 0))
        else:
            c2.append(0.5)
        decisions.append({"decision": decision.date().isoformat(), "credit_cutoff": cutoff.date().isoformat(),
                          "last_credit": last_credit.date().isoformat() if last_credit is not None else None,
                          "credit_age_us_sessions": (cutoff_ix - int(dates.get_loc(last_credit))) if last_credit is not None else None,
                          "credit_available": signal is not None})

    # Each row is held from the day's adjusted open to the next adjusted open.
    day_dates = dev[:-1]
    next_dates = dev[1:]
    r_spy = spy.loc[next_dates, "open"].to_numpy() / spy.loc[day_dates, "open"].to_numpy() - 1
    r_ief = ief.loc[next_dates, "open"].to_numpy() / ief.loc[day_dates, "open"].to_numpy() - 1
    month_ix = np.searchsorted(monthly.to_numpy(), day_dates.to_numpy(), side="right") - 1
    if np.any(month_ix < 0) or np.any(month_ix >= len(monthly)):
        raise RuntimeError("Month index out of bounds")
    hashes = {f"{s}_etf": digest(ROOT / f"data/multiasset/etf/{s}.parquet") for s in ("SPY", "IEF", "HYG", "LQD")}
    hashes.update({f"{s}_credit": digest(INPUT / f"{s}_dev.parquet") for s in ("USD_LIQ_HY", "USD_LIQ_IG")})
    return Inputs(day_dates, monthly, month_ix, r_spy, r_ief,
                  np.asarray(real), np.asarray(c1), np.asarray(c2), decisions, hashes)


class CreditEngine:
    name = "LSE HY-IG monthly equity/bond rotation, dev only"
    periods = 252

    def __init__(self, inp: Inputs):
        self.inp = inp
        self.c1 = self._portfolio(inp.c1_weights[None, :], BASE_COST)[0]
        self.c2 = self._portfolio(inp.c2_weights[None, :], BASE_COST)[0]

    def _portfolio(self, weights: np.ndarray, cost: float) -> np.ndarray:
        w = np.atleast_2d(np.asarray(weights, float))
        if w.shape[1] != len(self.inp.monthly_dates) or ((w < 0) | (w > 1)).any():
            raise ValueError("Invalid monthly allocation")
        daily = w[:, self.inp.month_index]
        ret = daily * self.inp.spy_open_returns + (1 - daily) * self.inp.ief_open_returns
        month_first = np.flatnonzero(np.r_[True, np.diff(self.inp.month_index) != 0])
        # Initial buy costs one side of total notional; a switch trades both ETF legs.
        ret[:, month_first[0]] -= cost
        if len(month_first) > 1:
            change = np.abs(w[:, 1:] - w[:, :-1])
            ret[:, month_first[1:]] -= 2 * cost * change
        return ret

    def run(self, signals: np.ndarray, paths=None) -> dict:
        if paths is not None:
            raise ValueError("No price-path resampling registered")
        w = np.atleast_2d(np.asarray(signals, float))
        base = self._portfolio(w, BASE_COST)
        stress = self._portfolio(w, STRESS_COST)
        daily_w = w[:, self.inp.month_index]
        matched = daily_w.mean(axis=1)
        basic = matched[:, None] * self.inp.spy_open_returns + (1 - matched[:, None]) * self.inp.ief_open_returns
        c0_base = basic.copy(); c0_base[:, 0] -= BASE_COST
        c0_stress = basic.copy(); c0_stress[:, 0] -= STRESS_COST
        return {("dev", "base"): base - c0_base,
                ("dev", "stress"): stress - c0_stress,
                ("dev", "portfolio_base"): base,
                ("dev", "portfolio_stress"): stress,
                ("dev", "c0_base"): c0_base,
                ("dev", "vs_c1"): base - self.c1,
                ("dev", "vs_c2"): base - self.c2,
                ("dev", "matched_weight"): matched}


class CreditGate(Gate):
    def evaluate(self, out: dict, periods: int, windows=("dev", "val"), horizons=()) -> dict:
        if windows != ("dev",):
            raise ValueError("This engine is development-only")
        result = super().evaluate(out, periods, windows=windows, horizons=horizons)
        result["pass_dev"] &= (out[("dev", "vs_c1")].mean(axis=1) > 0)
        result["pass_dev"] &= (out[("dev", "vs_c2")].mean(axis=1) > 0)
        return result


def stats(returns: np.ndarray) -> dict:
    x = np.asarray(returns, float)
    wealth = np.cumprod(1 + x)
    peak = np.maximum.accumulate(np.r_[1., wealth])
    return {"annual_mean": float(x.mean() * 252), "sharpe": float(sharpe(x[None, :], 252)[0]),
            "max_drawdown": float(np.min(np.r_[1., wealth] / peak - 1)),
            "total_return": float(wealth[-1] - 1)}


def paired_p(x: np.ndarray) -> float:
    return float(BootstrapP(len(x), 21, 5000, SEED).pvalues(np.asarray(x)[None, :])[0])


def concentration(dates: pd.DatetimeIndex, x: np.ndarray, months: int) -> dict:
    best = None
    latest_start = dates[-1] - pd.DateOffset(months=months)
    for start in dates:
        if start > latest_start:
            break
        end = start + pd.DateOffset(months=months)
        mask = (dates >= start) & (dates < end)
        total = float(x[mask].sum())
        if best is None or total > best[0]:
            best = (total, start, end, mask)
    return {"removed_start": best[1].date().isoformat(), "removed_end_exclusive": best[2].date().isoformat(),
            "removed_sum": best[0], "remaining": stats(x[~best[3]])}


def main() -> None:
    inp = build_inputs()
    engine = CreditEngine(inp)
    real = engine.run(inp.real_weights[None, :])
    # Exactness test against a separate month-by-month arithmetic construction.
    direct = np.zeros(len(inp.dates))
    prev_w = None
    for k, w in enumerate(inp.real_weights):
        ix = np.flatnonzero(inp.month_index == k)
        if not len(ix):
            continue
        direct[ix] = w * inp.spy_open_returns[ix] + (1 - w) * inp.ief_open_returns[ix]
        direct[ix[0]] -= BASE_COST if prev_w is None else 2 * BASE_COST * abs(w - prev_w)
        prev_w = w
    np.testing.assert_allclose(direct, real[("dev", "portfolio_base")][0], atol=1e-15, rtol=0)

    t_years = (date(2020, 12, 31) - date(2012, 1, 1)).days / 365.25
    threshold = 1.8 / np.sqrt(t_years)
    gate = CreditGate(dev_sharpe=threshold, k=1)
    observed = gate.evaluate(real, 252, windows=("dev",))
    shifted = run_null(builders.shift(inp.real_weights, min_offset=12), engine, gate,
                       n_worlds=5000, seed=SEED, family_size=1, with_composite=False,
                       dev_only=True)
    active = real[("dev", "base")][0]
    null_sharpe = shifted["arrays"]["sr_dev"][:, 0]
    p_observed = (1 + int(np.sum(null_sharpe >= stats(active)["sharpe"]))) / (len(null_sharpe) + 1)
    fixed_half = engine._portfolio(np.full((1, len(inp.monthly_dates)), 0.5), BASE_COST)[0]
    reverse = engine._portfolio((1 - inp.real_weights)[None, :], BASE_COST)[0]
    per_year = {}
    for year in sorted(set(inp.dates.year)):
        mask = inp.dates.year == year
        per_year[str(year)] = {"strategy_total": float(real[("dev", "portfolio_base")][0][mask].sum()),
                               "active_total": float(active[mask].sum()),
                               "active_sharpe": stats(active[mask])["sharpe"]}
    out = {"status": "PASS_DEVELOPMENT_ONLY" if bool(observed["pass_dev"][0]) else "FAIL_DEVELOPMENT",
           "plan_sha256": digest(ROOT / "research/credit_lead/PLAN.md"),
           "input_hashes": inp.input_hashes,
           "window": ["2012-01-01", "2020-12-31"], "years": t_years,
           "n_days": len(inp.dates), "n_decisions": len(inp.monthly_dates),
           "decision_audit": {"credit_available": int(sum(x["credit_available"] for x in inp.decisions)),
                              "neutral_fallback": int(sum(not x["credit_available"] for x in inp.decisions)),
                              "max_credit_age_sessions": max(x["credit_age_us_sessions"] for x in inp.decisions if x["credit_available"]),
                              "first": inp.decisions[0], "last": inp.decisions[-1]},
           "spy_exposure_fraction": float(real[("dev", "matched_weight")][0]),
           "dev_active_sharpe_gate": threshold,
           "strategy_base": stats(real[("dev", "portfolio_base")][0]),
           "strategy_stress": stats(real[("dev", "portfolio_stress")][0]),
           "c0_matched": stats(real[("dev", "c0_base")][0]),
           "fixed_50_50": stats(fixed_half),
           "c1_spy_momentum": stats(engine.c1),
           "c2_hyg_lqd": stats(engine.c2),
           "p1_reverse": stats(reverse),
           "active_c0_base": stats(active),
           "active_c0_stress": stats(real[("dev", "stress")][0]),
           "vs_c1": stats(real[("dev", "vs_c1")][0]),
           "vs_c2": stats(real[("dev", "vs_c2")][0]),
           "paired_bootstrap_p": {"c0": paired_p(active),
                                  "c1": paired_p(real[("dev", "vs_c1")][0]),
                                  "c2": paired_p(real[("dev", "vs_c2")][0])},
           "null": {"p_full_dev_pass": shifted["candidate"]["p_pass_dev"],
                    "p_active_sharpe_at_least_observed": p_observed,
                    "sr_dev": shifted["candidate"]["sr_dev"],
                    "signal": shifted["signal"], "worlds": shifted["n_worlds"]},
           "best_12m_removed": concentration(inp.dates, active, 12),
           "best_24m_removed": concentration(inp.dates, active, 24),
           "yearly": per_year,
           "validation": "LOCKED: no 2021+ credit or ETF return was loaded"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dev_results.json").write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
