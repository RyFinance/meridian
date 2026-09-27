"""Targeted survivorship-bias numbers for two named designs (SYNTHETIC ONLY; no real prices read).

Workload C, research cycle 4. Re-uses the world model in survivor_sim.py.

T1  Weekly (h=5) FINRA short-volume long-short on US stocks, 2018-2026 (last 8 years before 'today'):
    US large-cap world (index = top 15% by size), views TODAY_K (today's survivors only, the repo cache) and
    PIT_K_TODAY (PIT mask on the survivor cache); signal loading on distress rho in {0.1, 0.2, 0.3}.
    Also the 'all live US stocks' version (SURV_ALL) for a broad-universe variant.
T2  Binance USD-M perp funding cross-section, weekly (h=7 'days' on a 252-day clock; crypto-scaled vol):
    crypto world with ~15-25%/yr contract delistings, mean loss at death 60%, no M&A. Views: TRUE_ALL
    (archive incl. delisted contracts and their final settlement), LAST_ALL (archive but the final
    settlement gap missing - an upper bound on what the archive can still miss), SURV_ALL (a live-only symbol
    list, e.g. today's exchangeInfo or the LSE vault's 56 live coins). Carry's long leg (low / negative
    funding) is where dying contracts sit, so the relevant signal is DISTRESS_rho with rho > 0 read as
    'long low funding'.

Output: reports/survivorship_audit/targeted_bias.csv, targeted_bias.json
Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python research/survivorship_audit/targeted_bias.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import research.survivorship_audit.survivor_sim as sim

OUT = Path(__file__).resolve().parents[2] / "reports/survivorship_audit"


def run(p: sim.Params, seeds, last_years: int, h: int, rhos) -> pd.DataFrame:
    sim.HORIZONS = (h,)
    sim.RHOS = tuple(rhos)
    frames = []
    for sd in seeds:
        w = sim.simulate_world(p, sd)
        mem, rec = sim.build_index(w, p)
        w["burn"] = w["D"] - last_years * 252
        df = sim.evaluate_world(w, p, sd, mem, rec)
        df["perf_rate"] = w["perf_rate"]
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def summarise(df: pd.DataFrame, views) -> pd.DataFrame:
    d = df[df.view.isin(views)]
    g = d.groupby(["scenario", "view", "signal"])
    out = g[["bias_spread_ann", "bias_top_ann", "bias_bot_ann", "bias_universe_ann", "ic_equiv"]].mean()
    out["bias_spread_ann_sem"] = g["bias_spread_ann"].sem()
    out["perf_delist_rate"] = g["perf_rate"].mean()
    return out.reset_index()


def main() -> None:
    rows = []
    # ---- T1: US, weekly, last 8 years
    for p in [sim.Params(name="US_lowdistress_perf1", entry_x_mean=4.5, loss_mean=0.30, seeds=tuple(range(1, 9))),
              sim.Params(name="US_base_perf3", entry_x_mean=1.8, loss_mean=0.30, seeds=tuple(range(1, 9)))]:
        df = run(p, p.seeds, last_years=8, h=5, rhos=(0.0, 0.1, 0.2, 0.3))
        df["ic_equiv"] = df["bias_spread_per_period"] / (2.8 * df["xs_sd_h"])
        s = summarise(df, ["TODAY_K", "PIT_K_TODAY", "PIT_K_LIVE", "SURV_ALL"])
        s["design"] = "T1_FINRA_short_volume_weekly_2018_2026"
        rows.append(s)
    # ---- T2: crypto perps, weekly
    for p in [sim.Params(name="crypto_perp_death20_L60", N=400, K=100, sig_med=0.80, sig_disp=0.35, s_m=0.60,
                         entry_x_mean=2.2, loss_mean=0.60, lam_ma=0.0, burn_years=6, meas_years=6,
                         logshare_sd_init=1.0, seeds=tuple(range(1, 13)))]:
        df = run(p, p.seeds, last_years=6, h=5, rhos=(0.0, 0.2, 0.4))
        df["ic_equiv"] = df["bias_spread_per_period"] / (2.8 * df["xs_sd_h"])
        s = summarise(df, ["LAST_ALL", "SURV_ALL"])
        s["design"] = "T2_Binance_funding_xs_weekly"
        rows.append(s)
    res = pd.concat(rows, ignore_index=True)
    res.to_csv(OUT / "targeted_bias.csv", index=False)
    (OUT / "targeted_bias.json").write_text(res.round(5).to_json(orient="records", indent=1))
    pd.set_option("display.width", 250)
    print(res.round(4).to_string())


if __name__ == "__main__":
    main()
