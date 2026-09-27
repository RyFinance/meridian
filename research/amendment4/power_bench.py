"""research.amendment4.power_bench -- Section 5: joint (dev + validation) power at realistic effect sizes under the
CORRECTED gates, for representative designs built with research.power.designs (via the A4 validators).

Corrected gates (k = k_val = 1):
  dev   S_hat >= 1.8/sqrt(Y_d), calibrated p <= 0.05, stress mean > 0                      (Amendment 2, unchanged)
  val   calibrated p <= 0.05 AND S_hat >= 0.30, applied to the STRESS-cost series (rule R4) (=> net passes too)
Analytic: every leg is a threshold on S_hat; the calibrated test's threshold is c_n * sqrt(D / Y) where c_n is the
(1 - alpha) quantile of the calibrated statistic under an iid Gaussian null at the design's n (fixed-b bandwidth
makes c_n > z_alpha: e.g. 1.73 vs 1.645 at n = 120). P(S_hat >= h) uses the Lo/Opdyke SE of research.power.
Stress drag d = 0.1 Sharpe units (A2's convention) and d = 0 are both reported.
Key cells are re-run literally by Monte Carlo (>= 20,000 paths, calibrated test with B = 159 null draws).
"""
from __future__ import annotations

import functools
import math

import numpy as np
import pandas as pd
from scipy import stats

from research.amendment4 import calib, dgp, gating
from research.amendment4.validators import build_validated

SHARPES = (0.25, 0.30, 0.40, 0.70)


CV_GRID = (60, 90, 120, 180, 240, 300, 360, 480, 600, 900, 1200)


def calibrated_cv(n: int, alpha: float) -> float:
    """(1 - alpha) quantile of the calibrated statistic (Bartlett t with the fixed-b bandwidth) under an iid N(0,1)
    null, i.e. the calibrated test's critical value when the fitted null is iid. It depends on n only through the
    bandwidth rule; n is snapped to CV_GRID (n > 1200 uses 1200: the fixed-b limit is reached)."""
    g = min(CV_GRID, key=lambda v: abs(v - min(n, 1200)))
    return _cv(g, round(alpha, 6))


@functools.lru_cache(maxsize=None)
def _cv(n: int, alpha: float, paths: int = 200000) -> float:
    rng = np.random.default_rng([n, 7])
    L = calib.stat_lags(n)
    out = [calib.nw_t_batch(np.ascontiguousarray(rng.standard_normal((20000, n))), L) for _ in range(paths // 20000)]
    return float(np.quantile(np.concatenate(out), 1 - alpha))


def analytic_joint(series, q, dev_years, val_years, S, drag, k=1, k_val=1, floor=0.30):
    nd, nv = int(round(q * dev_years)), int(round(q * val_years))
    D = series.D_null if series.null_D is not None else series.D1
    a_d, a_v = 0.05 / k, 0.05 / k_val
    cd = calibrated_cv(nd, a_d)
    cv = calibrated_cv(nv, a_v)
    h_dev = max((2.4 if k >= 4 else 1.8) / math.sqrt(dev_years), cd * math.sqrt(D / dev_years), drag)
    h_val = max(cv * math.sqrt(D / val_years), floor) + drag
    se_d = float(series.se(S, dev_years))
    se_v = float(series.se(S, val_years))
    p_dev = float(stats.norm.sf((h_dev - S) / se_d))
    p_val = float(stats.norm.sf((h_val - S) / se_v))
    return p_dev, p_val, p_dev * p_val, h_dev, h_val


def designs_list():
    out = []
    for q, ac, lab in ((252, 0.05, "single series, daily (AR 0.05)"), (12, 0.0, "single series, monthly (iid)"),
                       (12, 0.1, "single series, monthly (AR 0.1)")):
        d, _ = build_validated("timeseries", {"periods_per_year": q, "autocorr": ac})
        out.append((lab, d, [(10, 10), (15, 15), (25, 25)], None))
    for epy in (500, 5000):
        d, _ = build_validated("event_study", {"events_per_year": epy, "car_sd": 0.08, "hold_days": 20, "icc": 0.02,
                                               "concurrency": {"model": "uniform_poisson"},
                                               "portfolio_autocorr": 0.05})
        out.append((f"event study {epy}/yr (hold 20d, CAR sd 8%, icc 0.02; calendar-time daily)", d,
                    [(10, 10), (15, 15), (25, 25)], "mean net CAR per event (bp)"))
    for K, rho in ((40, 0.2), (50, 0.3), (60, 0.4)):
        d, _ = build_validated("panel", {"n_markets": K, "periods_per_year": 12, "rho": rho, "autocorr": 0.05,
                                         "skew": 0.5, "exkurt": 2.0})
        out.append((f"trend-like panel {K} markets, rho {rho}, monthly (skew +0.5)", d, [(10, 10), (15, 15), (20, 20)],
                    "per-market net Sharpe"))
    d, _ = build_validated("long_short", {"n_assets": 1000, "periods_per_year": 12, "ic": 0.03, "cs_dispersion": 0.08,
                                          "quantile": 0.1, "rho_resid": 0.2, "rho_signal": 0.3,
                                          "signal_autocorr": 0.8, "cost_bps_one_way": 10.0,
                                          "spread_autocorr": 0.05},
                           provenance={"rho_source": "factor_share_declared"})
    out.append(("cross-sectional long-short, 1000 names, deciles, monthly, 10bp", d, [(10, 10), (15, 15), (25, 25)],
                "mean IC per period needed (net of costs)"))
    d, _ = build_validated("carry", {"n_assets": 20, "periods_per_year": 12, "rho": 0.3, "autocorr": 0.0,
                                     "skew": dgp.crash_moments(0.2 / 12, -6.0)["skew"],
                                     "exkurt": dgp.crash_moments(0.2 / 12, -6.0)["exkurt"]})
    out.append(("carry with crashes (lambda 0.2/yr, -6 sd), monthly", d, [(10, 10), (15, 15), (25, 25)],
                "per-asset net Sharpe"))
    return out


def run_analytic(drags=(0.1, 0.0)):
    rows = []
    for lab, d, windows, nat in designs_list():
        q = d.series.periods_per_year
        for dy, vy in windows:
            for drag in drags:
                for S in SHARPES:
                    pd_, pv, pj, hd, hv = analytic_joint(d.series, q, dy, vy, S, drag)
                    row = {"design": lab, "dev_years": dy, "val_years": vy, "true_net_sharpe": S, "stress_drag_sr": drag,
                           "P_dev": pd_, "P_val": pv, "P_joint": pj, "h_dev": hd, "h_val": hv,
                           "D": d.series.D1, "kappa_at_S": float(math.sqrt(d.series.kappa2(S))),
                           "certifies_50pct": pj >= 0.5, "certifies_80pct": pj >= 0.8}
                    if nat:
                        v = d.natural_from_sharpe(S)
                        row["natural_unit"] = nat
                        row["natural_value_needed"] = v * 1e4 if "bp" in nat else v
                    rows.append(row)
        # years (each window, equal split) for 50% / 80% joint power at S = 0.4 and 0.25, drag 0.1
        for drag in drags:
            for S in (0.25, 0.3, 0.4, 0.7):
                for target in (0.5, 0.8):
                    y = _years_needed(d.series, q, S, drag, target)
                    rows.append({"design": lab, "true_net_sharpe": S, "stress_drag_sr": drag,
                                 "years_each_window_for_target": y, "target_joint_power": target})
    return pd.DataFrame(rows)


def _years_needed(series, q, S, drag, target):
    for y in range(5, 1001, 1):
        if analytic_joint(series, q, y, y, S, drag)[2] >= target:
            return y
    return float("inf")


# ---------------------------------------------------------------------------------------------- MC key cells
def _panel_book(P, n, rng, K, rho, s_m, q, phi=0.05):
    """EW book of K one-factor Gaussian markets (exact book-level simulation: the mean of K iid idiosyncratic
    N(0,1) is N(0, 1/K)), each market AR(1) phi in time; per-market Sharpe s_m, so book Sharpe = s_m sqrt(N_eff)."""
    F = dgp.ar1(P, n, rng, phi)
    E = dgp.ar1(P, n, rng, phi)
    book = math.sqrt(rho) * F + math.sqrt((1 - rho) / K) * E
    return book / math.sqrt(rho + (1 - rho) / K) + s_m * math.sqrt(K / (1 + (K - 1) * rho)) / math.sqrt(q)


def _event_series(P, n, rng, epy, car_sd, h, icc, S, deff):
    lam = epy / 252.0
    arr = rng.poisson(lam, size=(P, n + h - 1)).astype(float)
    cs = np.concatenate([np.zeros((P, 1)), np.cumsum(arr, axis=1)], axis=1)
    A = cs[:, h:h + n] - cs[:, :n]
    mean_car = S * car_sd * math.sqrt(deff / epy)
    mu_d, sd_d = mean_car / h, car_sd / math.sqrt(h)
    F = rng.standard_normal((P, n))
    Z = rng.standard_normal((P, n))
    return A * mu_d + sd_d * (math.sqrt(icc) * A * F + np.sqrt((1 - icc) * A) * Z)


def mc_cell(kind, S, dy, vy, paths=20000, drag=0.1, seed=20261002, chunk=5000, **kw):
    q = kw.get("q", 12)
    nd, nv = int(round(q * dy)), int(round(q * vy))
    okd_all, okv_all = [], []
    for i0 in range(0, paths, chunk):
        P = min(chunk, paths - i0)
        rng = np.random.default_rng([seed, i0, int(S * 1000), dy])
        if kind == "ts":
            X = dgp.ar1(P, nd + nv, rng, kw.get("phi", 0.0)) + S / math.sqrt(q)
        elif kind == "panel":
            K, rho = kw["K"], kw["rho"]
            neff = K / (1 + (K - 1) * rho)
            X = _panel_book(P, nd + nv, rng, K, rho, S / math.sqrt(neff), q)
        elif kind == "crash":
            X = dgp.crash(P, nd + nv, rng, 0.2 / 12, -6.0) + S / math.sqrt(q)
        elif kind == "event":
            X = _event_series(P, nd + nv, rng, kw["epy"], 0.08, 20, 0.02, S, kw["deff"])
        else:
            raise ValueError(kind)
        sd = X[:, :].std(axis=1, keepdims=True)
        c = drag / math.sqrt(q) * sd                      # extra stress cost, drag Sharpe units
        dev, val = np.ascontiguousarray(X[:, :nd]), np.ascontiguousarray(X[:, nd:])
        crash = kw.get("crash")
        okd_all.append(gating.dev_gate(dev, dev - c, q, seed=seed + i0, crash=crash))
        okv_all.append(gating.val_gate(val, val - c, q, stress_rule="R4_gate", seed=seed + 7 + i0, crash=crash))
    okd, okv = np.concatenate(okd_all), np.concatenate(okv_all)
    pj = float((okd & okv).mean())
    return {"P_dev_mc": float(okd.mean()), "P_val_mc": float(okv.mean()), "P_joint_mc": pj,
            "mc_se_joint": math.sqrt(max(pj * (1 - pj), 1e-12) / paths)}


def run_mc(paths=20000):
    from research.power import designs
    cells = [
        ("single series, monthly (iid)", "ts", dict(q=12), [(10, 10, 0.4), (10, 10, 0.7), (25, 25, 0.4), (25, 25, 0.25)]),
        ("single series, daily (AR 0.05)", "ts", dict(q=252, phi=0.05), [(15, 15, 0.4)]),
        ("trend-like panel 50 markets, rho 0.3, monthly (skew +0.5)", "panel", dict(q=12, K=50, rho=0.3),
         [(20, 20, 0.4), (20, 20, 0.7)]),
        ("carry with crashes (lambda 0.2/yr, -6 sd), monthly", "crash", dict(q=12), [(15, 15, 0.4)]),
        ("carry with crashes, declared crash layer", "crash", dict(q=12, crash=(0.2 / 12, -6.0)), [(15, 15, 0.4)]),
    ]
    ev = designs.event_study(events_per_year=500, car_sd=0.08, hold_days=20, icc=0.02,
                             concurrency={"model": "uniform_poisson"}, portfolio_autocorr=0.05)
    cells.append(("event study 500/yr (hold 20d, CAR sd 8%, icc 0.02; calendar-time daily)", "event",
                  dict(q=252, epy=500, deff=ev.deff_cross), [(10, 10, 0.4)]))
    analytic = {}
    for lab, d, _, _ in designs_list():
        analytic[lab] = d
    rows = []
    for lab, kind, kw, specs in cells:
        for dy, vy, S in specs:
            r = mc_cell(kind, S, dy, vy, paths=paths, **kw)
            dname = lab if lab in analytic else "carry with crashes (lambda 0.2/yr, -6 sd), monthly"
            d = analytic[dname]
            a = analytic_joint(d.series, d.series.periods_per_year, dy, vy, S, 0.1)
            rows.append({"design": lab, "dev_years": dy, "val_years": vy, "true_net_sharpe": S, "stress_drag_sr": 0.1,
                         "P_joint_analytic": a[2], **r, "paths": paths})
            print(f"[power-mc] {lab} {dy}+{vy} S={S}: mc {r['P_joint_mc']:.3f} analytic {a[2]:.3f}", flush=True)
    return pd.DataFrame(rows)


def run(mc_paths=20000):
    return run_analytic(), run_mc(mc_paths)
