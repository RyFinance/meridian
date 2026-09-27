"""Synthetic calibration of survivorship bias in cross-sectional long-short spreads.

Workload C, research cycle 4 (2026-09-24). SYNTHETIC DATA ONLY - no real prices are read.

Model (daily; one firm per 'slot'; a dead firm is replaced the same evening by a small entrant):
  x_it   log distance to a default barrier (x <= 0  => performance delisting). The barrier grows with the
         expected equity return, so x has log drift  mu_i - 0.5 (sigma_i^2 + beta_i^2 s_m^2)  (volatility drag).
  equity return on day t (to the last traded price):  r = exp(dx + g dt) - 1
  mu_i   firm-level expected-return heterogeneity (N(0, mu_disp)); mu_disp > 0 creates a TRUE momentum
         premium and makes 'growing into the index' persistent (needed to reproduce the repo's momentum finding)
  performance delisting: extra delisting return D = -L, L ~ Beta, mean loss_mean (Shumway 1997 about 0.30
         NYSE/AMEX performance delistings; Shumway & Warther 1999 about 0.55 Nasdaq)
  M&A exit: hazard lam_ma, +premium jump on the exit day (announcement), then gone
  index: top-K by size (x + log shares), reconstituted every 252 days with a retention buffer (members stay
         while rank < buffer*K), which gives S&P-like churn; the last reconstitution is 'today'.

Views of the same simulated world (what a researcher's data would show):
  TRUE_ALL      every listed firm, delisting returns included                              (reference A)
  LAST_ALL      every listed firm, delisting return missing (last traded price)         -> Shumway-type bias
  SURV_ALL      only firms still listed at the sample end ('listed today')              -> e.g. LSE 3,855 live stocks
  PIT_K_TRUE    point-in-time index members, delisting returns included                   (reference B)
  TODAY_K       today's index members, all dates                                         -> repo data/raw, data/multiasset/stocks
  PIT_K_TODAY   PIT members at t AND today's members                                      -> repo cache + PIT mask (momentum_verification arm B)
  PIT_K_LIVE    PIT members at t AND still listed today (any size)                        -> PIT mask on an all-live-stocks cache
Bias = view spread - reference spread, paired on the same dates, annualised (x 252/h).

Signals (equal-weight quintile long-short, formed at close t0, held h days, re-formed every h days):
  DISTRESS_rho  s = rho * z(-x) + sqrt(1-rho^2) * noise, noise redrawn every rebalance (a short-horizon signal
                with loading rho on distress; its implied correlation with next-year delisting is reported)
  REVERSAL      s = -(past h-day return)                  (long losers / short winners)
  MOMENTUM      s = return over (t0-252, t0-21]
Sign convention: spread = TOP quintile of s minus BOTTOM quintile.
  DISTRESS: + bias = data make distressed names look better than they are = AGAINST 'distressed / heavily shorted
            names underperform', IN FAVOUR of 'buy distressed'.
  REVERSAL: + bias = in favour of reversal.   MOMENTUM: + bias = in favour of momentum.

Outputs: reports/survivorship_audit/sim_results.csv, sim_bias_summary.csv, sim_index_calibration.csv,
         sim_summary.json, sim_bias_vs_horizon.png

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python research/survivorship_audit/survivor_sim.py
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/survivorship_audit"
OUT.mkdir(parents=True, exist_ok=True)
DT = 1.0 / 252
HORIZONS = (1, 5, 21, 63, 252)
RHOS = (0.0, 0.3, 0.6)


@dataclass
class Params:
    name: str = "base"
    N: int = 3000                 # listed firms (slots)
    K: int = 450                  # index size (15%, cf. S&P 500 / ~3,500 US listed)
    buffer: float = 2.0           # members retained at reconstitution while size rank < buffer*K
    burn_years: int = 12
    meas_years: int = 12
    g: float = 0.07               # expected equity return (annual)
    s_m: float = 0.16             # market factor vol
    sig_med: float = 0.30         # median idiosyncratic vol
    sig_disp: float = 0.45        # log-sd of idiosyncratic vol across firms
    mu_disp: float = 0.0          # sd of firm-level expected-return offsets (annual)
    entry_x_mean: float = 1.8     # mean log distance-to-barrier of entrants (calibrates the delisting rate)
    lam_ma: float = 0.03          # M&A exit hazard per year
    ma_prem_mean: float = 0.25
    ma_prem_sd: float = 0.15
    loss_mean: float = 0.30       # mean loss at a performance delisting
    loss_conc: float = 2.0        # Beta concentration a+b (low = U-shaped: many near 0 and near -100%)
    logshare_sd_init: float = 1.5
    entrant_logshare_mean: float = -1.0
    entrant_logshare_sd: float = 1.0
    seeds: tuple = (1, 2, 3)


def _new_firms(rng, n, p: Params, entrant: bool):
    x = p.entry_x_mean * rng.gamma(2.0, 0.5, n)
    sig = np.clip(p.sig_med * np.exp(p.sig_disp * rng.standard_normal(n)), 0.10, 1.50)
    beta = np.clip(1.0 + 0.3 * rng.standard_normal(n), 0.2, 2.0)
    mu = p.mu_disp * rng.standard_normal(n)
    if entrant:
        ls = p.entrant_logshare_mean + p.entrant_logshare_sd * rng.standard_normal(n)
    else:
        ls = p.logshare_sd_init * rng.standard_normal(n)
    return x, sig, beta, mu, ls


def simulate_world(p: Params, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    N = p.N
    D = (p.burn_years + p.meas_years) * 252
    x, sig, beta, mu, ls = _new_firms(rng, N, p, entrant=False)
    fid = np.arange(N, dtype=np.int64)
    next_id = N
    first_day = [-10_000] * N
    last_day: dict[int, int] = {}
    kind: dict[int, str] = {}
    G_last = np.zeros((D + 1, N))
    G_true = np.zeros((D + 1, N))
    ID_end = np.zeros((D + 1, N), dtype=np.int64)
    X_end = np.zeros((D + 1, N), dtype=np.float32)
    S_end = np.zeros((D + 1, N), dtype=np.float32)
    ID_end[0], X_end[0], S_end[0] = fid, x, x + ls
    a, b = p.loss_mean * p.loss_conc, (1 - p.loss_mean) * p.loss_conc
    perf_by_day = np.zeros(D + 1, dtype=np.int32)
    ma_by_day = np.zeros(D + 1, dtype=np.int32)
    for t in range(1, D + 1):
        f = p.s_m * np.sqrt(DT) * rng.standard_normal()
        dx = (beta * f + sig * np.sqrt(DT) * rng.standard_normal(N)
              + (mu - 0.5 * (sig ** 2 + (beta * p.s_m) ** 2)) * DT)
        x = x + dx
        glast = dx + p.g * DT
        perf = x <= 0.0
        ma = (~perf) & (rng.random(N) < p.lam_ma * DT)
        if ma.any():
            prem = np.clip(p.ma_prem_mean + p.ma_prem_sd * rng.standard_normal(ma.sum()), -0.2, 1.5)
            glast[ma] += np.log1p(prem)
        gtrue = glast.copy()
        if perf.any():
            L = np.clip(rng.beta(a, b, perf.sum()), 0.0, 0.995)
            gtrue[perf] += np.log1p(-L)
        G_last[t] = G_last[t - 1] + glast
        G_true[t] = G_true[t - 1] + gtrue
        dead = perf | ma
        if dead.any():
            idx = np.flatnonzero(dead)
            for j in idx:
                last_day[int(fid[j])] = t
                kind[int(fid[j])] = "perf" if perf[j] else "ma"
            perf_by_day[t], ma_by_day[t] = int(perf.sum()), int(ma.sum())
            nx, ns, nb, nm, nl = _new_firms(rng, len(idx), p, entrant=True)
            x[idx], sig[idx], beta[idx], mu[idx], ls[idx] = nx, ns, nb, nm, nl
            new_ids = np.arange(next_id, next_id + len(idx))
            next_id += len(idx)
            fid[idx] = new_ids
            first_day.extend([t] * len(idx))
        ID_end[t], X_end[t], S_end[t] = fid, x, x + ls
    burn = p.burn_years * 252
    yrs = (D - burn) / 252
    ld = np.full(next_id, 10 ** 9, dtype=np.int64)
    for k, v in last_day.items():
        ld[k] = v
    kind_arr = np.array([kind.get(k, "alive") for k in range(next_id)])
    return dict(G_last=G_last, G_true=G_true, ID_end=ID_end, X_end=X_end, S_end=S_end,
                last_day=ld, first_day=np.array(first_day, dtype=np.int64), kind=kind_arr, D=D, burn=burn,
                perf_rate=float(perf_by_day[burn + 1:].sum() / (N * yrs)),
                ma_rate=float(ma_by_day[burn + 1:].sum() / (N * yrs)))


def build_index(w: dict, p: Params) -> tuple[dict, list]:
    """Annual reconstitution with a retention buffer; the final reconstitution is day D ('today')."""
    D = w["D"]
    n_ids = len(w["last_day"])
    recon_days = sorted(range(D, -1, -252))
    mem: dict[int, np.ndarray] = {}
    prev = np.zeros(n_ids, bool)
    for r in recon_days:
        ids = w["ID_end"][r]
        rank = np.empty(p.N, int)
        rank[np.argsort(-w["S_end"][r])] = np.arange(p.N)
        cur = np.zeros(n_ids, bool)
        keep = prev[ids] & (rank < p.buffer * p.K)
        cur[ids[keep]] = True
        need = p.K - int(keep.sum())
        if need > 0:
            cand = [i for i in ids[np.argsort(rank)] if not cur[i]][:need]
            cur[np.array(cand, dtype=np.int64)] = True
        mem[r] = cur
        prev = cur
    return mem, recon_days


def index_calibration(w: dict, p: Params, mem: dict, recon_days: list, seed: int) -> pd.DataFrame:
    """Per year before 'today': share of PIT members still in today's index (cf. repo: 98% / 77% at 7y / 50% at 18y),
    share still listed, annual membership exit rate and member performance-delisting rate."""
    D, ld, kind = w["D"], w["last_day"], w["kind"]
    today = mem[D]
    rows = []
    for i, r in enumerate(recon_days):
        m = mem[r]
        ids = np.flatnonzero(m)
        nxt = mem[recon_days[i + 1]] if i + 1 < len(recon_days) else None
        exit_rate = float((~nxt[ids]).mean()) if nxt is not None else np.nan
        died_perf = float(((ld[ids] <= r + 252) & (kind[ids] == "perf")).mean()) if r + 252 <= D else np.nan
        rows.append({"scenario": p.name, "seed": seed, "years_before_today": round((D - r) / 252, 1),
                     "share_in_today_index": float(today[ids].mean()),
                     "share_still_listed": float((ld[ids] > D).mean()),
                     "member_exit_rate_next_year": exit_rate,
                     "member_perf_delist_rate_next_year": died_perf})
    return pd.DataFrame(rows)


def _quintile_ls(s: np.ndarray, r: np.ndarray):
    n = len(s)
    if n < 25:
        return (np.nan,) * 4
    order = np.argsort(s, kind="stable")
    q = n // 5
    bot, top = r[order[:q]].mean(), r[order[-q:]].mean()
    return top - bot, top, bot, r.mean()


def evaluate_world(w: dict, p: Params, seed: int, mem: dict, recon_days: list) -> pd.DataFrame:
    rng = np.random.default_rng(10_000 + seed)
    D, burn = w["D"], w["burn"]
    G_last, G_true, ID_end, X_end = w["G_last"], w["G_true"], w["ID_end"], w["X_end"]
    ld, fd = w["last_day"], w["first_day"]
    today = mem[D]
    rd = np.array(recon_days)
    cols = np.arange(p.N)
    ref_of = {"TRUE_ALL": "TRUE_ALL", "LAST_ALL": "TRUE_ALL", "SURV_ALL": "TRUE_ALL",
              "PIT_K_TRUE": "PIT_K_TRUE", "TODAY_K": "PIT_K_TRUE", "PIT_K_TODAY": "PIT_K_TRUE",
              "PIT_K_LIVE": "PIT_K_TRUE"}
    rows = []
    for h in HORIZONS:
        dates = np.arange(burn, D - h + 1, h)
        acc: dict = {}
        xs_disp, pb = [], []
        for t0 in dates:
            ids = ID_end[t0]
            ok = (t0 - fd[ids]) >= 252
            end = np.minimum(t0 + h, ld[ids])
            r_last = np.expm1(G_last[end, cols] - G_last[t0, cols])
            r_true = np.expm1(G_true[end, cols] - G_true[t0, cols])
            alive_end = ld[ids] > D
            pit = mem[int(rd[rd <= t0].max())][ids]
            in_today = today[ids]
            views = {"TRUE_ALL": (ok, r_true), "LAST_ALL": (ok, r_last), "SURV_ALL": (ok & alive_end, r_last),
                     "PIT_K_TRUE": (ok & pit, r_true), "TODAY_K": (ok & in_today, r_last),
                     "PIT_K_TODAY": (ok & pit & in_today, r_last), "PIT_K_LIVE": (ok & pit & alive_end, r_last)}
            past_h = G_last[t0, cols] - G_last[t0 - h, cols]
            mom = G_last[t0 - 21, cols] - G_last[t0 - 252, cols]
            noise = rng.standard_normal(p.N)
            negx = -X_end[t0].astype(float)
            if len(xs_disp) < 300:
                xs_disp.append(np.std(np.log1p(r_true[ok])))
                if t0 + 252 <= D:
                    dl = ((ld[ids] <= t0 + 252) & (w["kind"][ids] == "perf")).astype(float)[ok]
                    zx = (negx[ok] - negx[ok].mean()) / (negx[ok].std() + 1e-12)
                    if dl.std() > 0:
                        for rho in RHOS:
                            srho = rho * zx + np.sqrt(1 - rho ** 2) * noise[ok]
                            pb.append((rho, float(np.corrcoef(srho, dl)[0, 1])))
            for vname, (mask, r) in views.items():
                if mask.sum() < 25:
                    continue
                zx = negx[mask]
                zx = (zx - zx.mean()) / (zx.std() + 1e-12)
                sigs = {"REVERSAL": -past_h[mask], "MOMENTUM": mom[mask]}
                for rho in RHOS:
                    sigs[f"DISTRESS_{rho:.1f}"] = rho * zx + np.sqrt(1 - rho ** 2) * noise[mask]
                rr = r[mask]
                for sname, s in sigs.items():
                    acc.setdefault((vname, sname), []).append((t0,) + _quintile_ls(s, rr))
        sd_h = float(np.nanmean(xs_disp))
        pbc = pd.DataFrame(pb, columns=["rho", "c"]).groupby("rho")["c"].mean().to_dict() if pb else {}
        for (vname, sname), lst in acc.items():
            v = pd.DataFrame(lst, columns=["t0", "spread", "top", "bot", "all"]).set_index("t0")
            ref = pd.DataFrame(acc[(ref_of[vname], sname)],
                               columns=["t0", "spread", "top", "bot", "all"]).set_index("t0")
            j = v.join(ref, rsuffix="_ref", how="inner")
            ann = 252.0 / h
            rows.append({
                "scenario": p.name, "seed": seed, "h": h, "view": vname, "reference": ref_of[vname],
                "signal": sname, "n_periods": len(j),
                "spread_ann": j["spread"].mean() * ann, "spread_ref_ann": j["spread_ref"].mean() * ann,
                "bias_spread_ann": (j["spread"] - j["spread_ref"]).mean() * ann,
                "bias_top_ann": (j["top"] - j["top_ref"]).mean() * ann,
                "bias_bot_ann": (j["bot"] - j["bot_ref"]).mean() * ann,
                "bias_universe_ann": (j["all"] - j["all_ref"]).mean() * ann,
                "bias_spread_per_period": (j["spread"] - j["spread_ref"]).mean(),
                "xs_sd_h": sd_h,
                "pbcorr_perfdelist_rho0.3": pbc.get(0.3, np.nan), "pbcorr_perfdelist_rho0.6": pbc.get(0.6, np.nan),
                "perf_delist_rate": w["perf_rate"], "ma_rate": w["ma_rate"],
            })
    return pd.DataFrame(rows)


S8 = tuple(range(1, 9))
S4 = (1, 2, 3, 4)
SCENARIOS = [
    Params(name="base_perf3_L30", entry_x_mean=1.8, loss_mean=0.30, seeds=S8),
    Params(name="base_perf3_L30_mu6", entry_x_mean=1.8, loss_mean=0.30, mu_disp=0.06, seeds=S8),
    Params(name="base_perf3_L30_mu15", entry_x_mean=1.8, loss_mean=0.30, mu_disp=0.15, seeds=S4),
    Params(name="nasdaq_perf6_L55", entry_x_mean=1.2, loss_mean=0.55, seeds=S4),
    Params(name="lowdistress_perf1_L30", entry_x_mean=4.5, loss_mean=0.30, seeds=S4),
    Params(name="base_L15", entry_x_mean=1.8, loss_mean=0.15, seeds=S4),
    Params(name="base_noMA", entry_x_mean=1.8, loss_mean=0.30, lam_ma=0.0, seeds=S4),
]


def ic_equivalent(bias_per_period: float, xs_sd_h: float) -> float:
    """Equal-weight quintile spread ~ IC * 2.8 * cross-sectional sd (normal scores); invert for the bias."""
    return bias_per_period / (2.8 * xs_sd_h) if xs_sd_h > 0 else np.nan


def main(quick: bool = False) -> None:
    t_start = time.time()
    frames, cal = [], []
    scen = SCENARIOS[:1] if quick else SCENARIOS
    for p in scen:
        for sd in (p.seeds[:1] if quick else p.seeds):
            w = simulate_world(p, sd)
            mem, recon = build_index(w, p)
            cal.append(index_calibration(w, p, mem, recon, sd))
            frames.append(evaluate_world(w, p, sd, mem, recon))
            print(f"{p.name} seed {sd}: perf-delist {w['perf_rate']:.3f}/yr, M&A {w['ma_rate']:.3f}/yr, "
                  f"{time.time() - t_start:.0f}s", flush=True)
            del w
    res = pd.concat(frames, ignore_index=True)
    res["ic_equiv_bias"] = [ic_equivalent(b, s) for b, s in zip(res["bias_spread_per_period"], res["xs_sd_h"])]
    res.to_csv(OUT / "sim_results.csv", index=False)
    calib = pd.concat(cal, ignore_index=True)
    calib.to_csv(OUT / "sim_index_calibration.csv", index=False)
    keys = ["scenario", "view", "signal", "h"]
    agg = res.groupby(keys)[["bias_spread_ann", "bias_top_ann", "bias_bot_ann", "bias_universe_ann",
                             "ic_equiv_bias", "spread_ref_ann", "perf_delist_rate", "ma_rate", "xs_sd_h",
                             "pbcorr_perfdelist_rho0.3", "pbcorr_perfdelist_rho0.6"]].mean().reset_index()
    sem = res.groupby(keys)["bias_spread_ann"].sem().rename("bias_spread_ann_sem").reset_index()
    agg = agg.merge(sem, on=keys)
    agg.to_csv(OUT / "sim_bias_summary.csv", index=False)
    yard = {}
    for h in HORIZONS:
        xs = float(res.loc[res["h"] == h, "xs_sd_h"].mean())
        yard[str(h)] = {"xs_sd_h": round(xs, 4),
                        "gross_quintile_spread_ann_if_IC_0.01": round(0.01 * 2.8 * xs * 252 / h, 4),
                        "gross_quintile_spread_ann_if_IC_0.02": round(0.02 * 2.8 * xs * 252 / h, 4)}
    cal_sum = (calib.assign(yb=calib["years_before_today"].round())
               .groupby(["scenario", "yb"])[["share_in_today_index", "share_still_listed",
                                             "member_exit_rate_next_year", "member_perf_delist_rate_next_year"]]
               .mean().round(3))
    summary = {
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "scenarios": [asdict(p) for p in scen],
        "realised_rates": res.groupby("scenario")[["perf_delist_rate", "ma_rate"]].mean().round(4).to_dict(),
        "alpha_yardstick_by_h": yard,
        "index_calibration_selected": {f"{k[0]}|{int(k[1])}y": v for k, v in
                                       cal_sum.loc[(slice(None), [1, 7, 12, 18, 23]), :].to_dict("index").items()},
        "repo_anchor_pit_coverage": "S&P PIT members priced by today's cache: 98% (2026), 94.5% (2025), 77% (2019, 7y), "
                                    "62% (2013, 13y), 50% (2008, 18y) - reports/momentum_verification_20260919",
        "runtime_s": round(time.time() - t_start, 1),
    }
    (OUT / "sim_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    _plot(agg)
    print(json.dumps(summary["realised_rates"], indent=1))


def _plot(agg: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.4), sharex=True)
    panels = [("SURV_ALL", "listed-today universe vs truth"),
              ("PIT_K_TODAY", "PIT index ∩ today's members vs PIT truth"),
              ("TODAY_K", "today's index members vs PIT truth")]
    sigs = [("DISTRESS_0.0", "#9aa0a6"), ("DISTRESS_0.3", "#e8a33d"), ("DISTRESS_0.6", "#c0392b"),
            ("REVERSAL", "#2e86c1"), ("MOMENTUM", "#27ae60")]
    for row, scen in enumerate(["base_perf3_L30", "base_perf3_L30_mu6"]):
        base = agg[agg.scenario == scen]
        for ax, (view, title) in zip(axes[row], panels):
            for sig, col in sigs:
                d = base[(base.view == view) & (base.signal == sig)].sort_values("h")
                ax.plot(d["h"], 100 * d["bias_spread_ann"], marker="o", label=sig, color=col)
            ax.axhline(0, color="k", lw=0.6)
            ax.set_xscale("log")
            ax.set_xticks(list(HORIZONS)); ax.set_xticklabels([str(h) for h in HORIZONS])
            ax.set_title(f"{title}\n[{scen}]", fontsize=9)
            if row == 1:
                ax.set_xlabel("holding horizon h (trading days)")
        axes[row][0].set_ylabel("bias in top-minus-bottom spread (%/yr)")
    axes[0][0].legend(fontsize=8)
    fig.suptitle("Synthetic survivorship bias by holding horizon (annualised; paired against the true world)", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "sim_bias_vs_horizon.png", dpi=120)


if __name__ == "__main__":
    import sys
    main(quick="--quick" in sys.argv)
