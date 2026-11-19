"""ONE-SHOT validation of the 2 registered candidates (research/mstr_btc_0dte/CANDIDATES.md)
on the locked window 2024-01-01..2026-09-17. No re-tuning; both fill models; per-year gate.

Run ONLY after pull_1m.py has written all validation chunks (cursor reaches 2026-09-18).
    PYTHONPATH=. .venv/bin/python research/mstr_btc_0dte/run_validation.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[2]))
from research.mstr_btc_0dte.engine import Rule, grid as engine_grid
from research.mstr_btc_0dte.spreads import Spread, grid as spread_grid
from research.mstr_btc_0dte import engine as eng
from research.mstr_btc_0dte import spreads as spr

H = Path(__file__).parent


def one(days: list, name: str, fn, fill: str):
    import dataclasses
    spec = dataclasses.replace(fn[0], fills=fill)  # Spread/Rule are frozen dataclasses
    t = fn[1](days, spec)
    if t.empty:
        return {"candidate": name, "fills": fill, "n": 0}
    x = t.ret
    y = t.index.year
    by_year = {str(yr): round(float(v.mean()), 4) for yr, v in x.groupby(y)}
    return {"candidate": name, "fills": fill, "n": int(len(x)), "mean": float(x.mean()),
            "t": float(x.mean() / x.std() * np.sqrt(len(x))) if x.std() > 0 else 0.0,
            "win": float((x > 0).mean()), "worst": float(x.min()), "p05": float(x.quantile(0.05)),
            "by_year": by_year}


def main() -> None:
    import pickle
    cache = H / "val_days_full.pkl"
    if cache.exists():
        days = pickle.load(open(cache, "rb"))
        print(f"loaded {len(days)} validation days from {cache.name}", flush=True)
    else:
        print("preparing validation days (engine.prepare('validation'))...", flush=True)
        days = eng.prepare("validation")
        pickle.dump(days, open(cache, "wb"))
    print(f"validation days: {len(days)}  [{days[0].d.date()} .. {days[-1].d.date()}]", flush=True)
    # The vault holds Mon/Fri sessions only: 2024-01-01..2026-08-10 is ~133 weeks x 2 minus US holidays
    # (~237 days); the panel (BTC 16:00 ET) ends 2026-08-10.  200 is a data-integrity floor, not a target.
    if len(days) < 200:
        raise SystemExit(f"only {len(days)} days loaded -- data incomplete, REFUSING to run validation")

    c1 = (Spread(short_steps=2, width=1, entry_min=5, tp=0.5, sl=None, min_btc=0.0, both=True), spr.backtest)
    c2 = (Rule(side="sell", strike_steps=4, entry_min=5, tp=None, sl=None, stop_min=390, min_btc=0.0), eng.backtest)
    rows = []
    for name, (spec, fn) in (("C1_IC_v1", c1), ("C2_NNV_v1", c2)):
        for f in ("base", "worst"):
            r = one(days, name, (spec, fn), f)
            rows.append(r)
            print(json.dumps(r, default=str), flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(H / "validation_results.csv", index=False)

    print("\nGATES (mean>0 both fills; base t>=1.96; no 2024/25/26 year mean <= -0.10 under ANY fill model):")
    import ast
    gates = {}
    for name in ("C1_IC_v1", "C2_NNV_v1"):
        g = out[out.candidate == name].set_index("fills")
        if "n" in g.columns and (g.n.isna() | (g.n == 0)).all():
            print(f"{name}: NO TRADES — investigate")
            gates[name] = {"PASS": False, "why": "no trades"}
            continue
        ok_mean = bool((g["mean"] > 0).all())
        ok_t = float(g.loc["base", "t"]) >= 1.96
        bad_years = {}
        for f in g.index:
            yrs = g.loc[f, "by_year"]
            if isinstance(yrs, str):
                yrs = ast.literal_eval(yrs)
            for k, v in (yrs or {}).items():
                if str(k) in ("2024", "2025", "2026") and float(v) <= -0.10:
                    bad_years[f"{f}/{k}"] = float(v)
        verdict = "PASS" if (ok_mean and ok_t and not bad_years) else "FAIL"
        gates[name] = {"mean_pos_both_fills": ok_mean, "base_t": float(g.loc["base", "t"]),
                       "base_t_ge_1p96": ok_t, "bad_years_any_fill": bad_years, "PASS": verdict == "PASS"}
        print(f"{name}: mean>0 both fills={ok_mean}, base t={g.loc['base','t']:.2f} (>=1.96? {ok_t}), "
              f"bad_years={bad_years or 'none'} -> {verdict}")
    (H / "validation_results_C1C2.json").write_text(
        json.dumps({"candidates": json.loads(out.to_json(orient="index")), "gates": gates}, indent=2, default=str))
    print("wrote validation_results_C1C2.json")


if __name__ == "__main__":
    main()
