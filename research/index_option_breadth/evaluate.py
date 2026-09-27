"""Frozen index-option volume development test; never loads 2020+ returns."""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.credit_lead.evaluate import Inputs, CreditEngine, CreditGate, stats, paired_p, concentration
from research.null_lab.api import builders, run_null


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/lse/index_option_breadth"
OUT = ROOT / "reports/index_option_breadth"
END = pd.Timestamp("2019-12-31")
SEED = 20260923


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def asset(symbol: str, fields=("open", "close")) -> pd.DataFrame:
    path = ROOT / (f"data/multiasset/etf/{symbol}.parquet" if symbol != "VIX" else "data/multiasset/vol/VIX.parquet")
    d = pd.read_parquet(path, columns=["date", *fields], filters=[("date", "<=", END)])
    d = d.set_index("date").sort_index()
    if d.empty or d.index.max() > END or d.index.duplicated().any():
        raise RuntimeError(f"Bad {symbol} date extent")
    if not np.isfinite(d.to_numpy(float)).all() or (d <= 0).any().any():
        raise RuntimeError(f"Bad {symbol} values")
    return d


def build_inputs() -> Inputs:
    spy, ief, vix = asset("SPY"), asset("IEF"), asset("VIX", fields=("close",))
    dates = spy.index.intersection(ief.index).sort_values()
    dates = dates[(dates >= "2014-06-01") & (dates <= END)]
    source = pd.read_parquet(SOURCE / "weekly_2014_2019.parquet")
    # Sunday week labels may extend into January while their underlying prints
    # stop at the 2019-12-31 source cutoff.
    if source.week_start.max() > END or (source[["put_volume", "call_volume"]] <= 0).any().any():
        raise RuntimeError("Invalid option volume source")
    source["period"] = source.week_start.dt.to_period("W-SUN")
    if source.period.duplicated().any():
        raise RuntimeError("Duplicate source weeks")
    weeks = source.set_index("period").sort_index()
    dev = dates[(dates >= "2015-07-06") & (dates <= END)]
    decisions = pd.DatetimeIndex(dev.to_series().groupby(dev.to_period("W-SUN")).first().to_numpy(dtype="datetime64[ns]"))
    day_week = pd.Series(dates, index=dates).groupby(dates.to_period("W-SUN")).last()
    real, c1, c2 = [], [], []
    audit = []
    for decision in decisions:
        signal_week = decision.to_period("W-SUN") - 1
        prior_week = signal_week - 1
        row = weeks.loc[signal_week] if signal_week in weeks.index else None
        history = weeks.loc[signal_week - 52: signal_week - 1]
        available = bool(row is not None and row.option_days >= 3 and len(history) == 52 and
                         (history.option_days >= 3).all())
        weight = 0.5
        if available:
            q = np.log(row.put_volume / row.call_volume)
            hist_q = np.log(history.put_volume / history.call_volume)
            weight = float(q < float(hist_q.median()))
        real.append(weight)
        if signal_week not in day_week.index or prior_week not in day_week.index:
            c1.append(0.5); c2.append(0.5)
        else:
            now, old = day_week.loc[signal_week], day_week.loc[prior_week]
            c1.append(float(spy.loc[now, "close"] > spy.loc[old, "close"]))
            if now in vix.index and old in vix.index:
                c2.append(float(vix.loc[now, "close"] < vix.loc[old, "close"]))
            else:
                c2.append(0.5)
        audit.append({"decision": decision.date().isoformat(), "signal_week": str(signal_week),
                      "available": available})

    day_dates, next_dates = dev[:-1], dev[1:]
    r_spy = spy.loc[next_dates, "open"].to_numpy() / spy.loc[day_dates, "open"].to_numpy() - 1
    r_ief = ief.loc[next_dates, "open"].to_numpy() / ief.loc[day_dates, "open"].to_numpy() - 1
    decision_ix = np.searchsorted(decisions.to_numpy(), day_dates.to_numpy(), side="right") - 1
    if (decision_ix < 0).any() or (decision_ix >= len(decisions)).any():
        raise RuntimeError("Invalid weekly decision mapping")
    hashes = {f"{s}_price": digest(ROOT / (f"data/multiasset/etf/{s}.parquet" if s != "VIX" else "data/multiasset/vol/VIX.parquet"))
              for s in ("SPY", "IEF", "VIX")}
    hashes["weekly_options"] = digest(SOURCE / "weekly_2014_2019.parquet")
    return Inputs(day_dates, decisions, decision_ix, r_spy, r_ief,
                  np.asarray(real), np.asarray(c1), np.asarray(c2), audit, hashes)


class OptionEngine(CreditEngine):
    name = "Index ETF option-volume balance, weekly development only"


def main() -> None:
    inp = build_inputs()
    engine = OptionEngine(inp)
    real = engine.run(inp.real_weights[None, :])
    direct = np.zeros(len(inp.dates))
    prev = None
    for k, w in enumerate(inp.real_weights):
        ix = np.flatnonzero(inp.month_index == k)
        direct[ix] = w * inp.spy_open_returns[ix] + (1 - w) * inp.ief_open_returns[ix]
        direct[ix[0]] -= 0.0003 if prev is None else 0.0006 * abs(w - prev)
        prev = w
    np.testing.assert_allclose(direct, real[("dev", "portfolio_base")][0], atol=1e-15, rtol=0)

    years = (date(2019, 12, 31) - date(2015, 7, 6)).days / 365.25
    threshold = 1.8 / np.sqrt(years)
    gate = CreditGate(dev_sharpe=threshold, k=1)
    observed = gate.evaluate(real, 252, windows=("dev",))
    null = run_null(builders.shift(inp.real_weights, min_offset=52), engine, gate,
                    n_worlds=5000, seed=SEED, family_size=1, with_composite=False, dev_only=True)
    active = real[("dev", "base")][0]
    null_sr = null["arrays"]["sr_dev"][:, 0]
    p_observed = (1 + int(np.sum(null_sr >= stats(active)["sharpe"]))) / (len(null_sr) + 1)
    fixed_half = engine._portfolio(np.full((1, len(inp.monthly_dates)), 0.5), 0.0003)[0]
    reverse = engine._portfolio((1 - inp.real_weights)[None, :], 0.0003)[0]
    yearly = {}
    for year in sorted(set(inp.dates.year)):
        mask = inp.dates.year == year
        yearly[str(year)] = {"strategy_total": float(real[("dev", "portfolio_base")][0][mask].sum()),
                             "active_total": float(active[mask].sum()),
                             "active_sharpe": stats(active[mask])["sharpe"]}
    result = {"status": "PASS_DEVELOPMENT_ONLY" if bool(observed["pass_dev"][0]) else "FAIL_DEVELOPMENT",
              "plan_sha256": digest(ROOT / "research/index_option_breadth/PLAN.md"),
              "engine_dependency_sha256": digest(ROOT / "research/credit_lead/evaluate.py"),
              "input_hashes": inp.input_hashes,
              "window": ["2015-07-06", "2019-12-31"], "years": years,
              "days": len(inp.dates), "decisions": len(inp.monthly_dates),
              "source_weeks_available": int(sum(x["available"] for x in inp.decisions)),
              "neutral_fallback": int(sum(not x["available"] for x in inp.decisions)),
              "first_decision": inp.decisions[0], "last_decision": inp.decisions[-1],
              "spy_exposure_fraction": float(real[("dev", "matched_weight")][0]),
              "dev_active_sharpe_gate": threshold,
              "strategy_base": stats(real[("dev", "portfolio_base")][0]),
              "strategy_stress": stats(real[("dev", "portfolio_stress")][0]),
              "c0_matched": stats(real[("dev", "c0_base")][0]),
              "fixed_50_50": stats(fixed_half),
              "c1_spy_momentum": stats(engine.c1),
              "c2_vix_change": stats(engine.c2),
              "p1_reverse": stats(reverse),
              "active_c0_base": stats(active),
              "active_c0_stress": stats(real[("dev", "stress")][0]),
              "vs_c1": stats(real[("dev", "vs_c1")][0]),
              "vs_c2": stats(real[("dev", "vs_c2")][0]),
              "paired_bootstrap_p": {"c0": paired_p(active),
                                     "c1": paired_p(real[("dev", "vs_c1")][0]),
                                     "c2": paired_p(real[("dev", "vs_c2")][0])},
              "null": {"p_full_dev_pass": null["candidate"]["p_pass_dev"],
                       "p_active_sharpe_at_least_observed": p_observed,
                       "sr_dev": null["candidate"]["sr_dev"],
                       "signal": null["signal"], "worlds": null["n_worlds"]},
              "best_12m_removed": concentration(inp.dates, active, 12),
              "best_24m_removed": concentration(inp.dates, active, 24),
              "yearly": yearly,
              "validation": "LOCKED: no 2020+ option volume or ETF return loaded"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dev_results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
