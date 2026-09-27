"""Is the frozen 21-day centred block bootstrap calibrated for this series?  DEV data only.
PYTHONPATH=. .venv/bin/python -m research.audit_funding_stat.null_calibration"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats

from research.audit_funding_stat.lockpanel import OUT
from research.struct_common import centred_block_p

ANN, ALPHA, SEED = 365, 0.025, 777


def fast_block_p(x, block=21, draws=1000, rng=None):
    n = len(x); cx = x - x.mean()
    idx = (rng.integers(0, n, size=(draws, -(-n // block)))[:, :, None] + np.arange(block)).reshape(draws, -1)[:, :n] % n
    return (np.sum(cx[idx].mean(axis=1) >= x.mean()) + 1) / (draws + 1)


def stationary_p(x, mean_block, draws=5000, seed=SEED):
    """Politis-Romano stationary bootstrap of the mean-centred series; one-sided p for mean <= 0."""
    rng = np.random.default_rng(seed)
    n = len(x); cx = x - x.mean(); pgeo = 1.0 / mean_block
    means = np.empty(draws)
    for d in range(draws):
        idx = np.empty(n, dtype=int); i = rng.integers(n)
        for t in range(n):
            if t > 0 and rng.random() < pgeo:
                i = rng.integers(n)
            else:
                i = (i + 1) % n if t > 0 else i
            idx[t] = i
        means[d] = cx[idx].mean()
    return float((np.sum(means >= x.mean()) + 1) / (draws + 1))


def sharpe(x):
    return x.mean() / x.std(ddof=1) * np.sqrt(ANN)


def gate_pass(b, s, gate, rng):
    return sharpe(b) >= gate and s.mean() > 0 and fast_block_p(b, 21, 400, rng) < ALPHA


def main():
    ser = pd.read_csv(OUT / "series_dev.csv", index_col=0, parse_dates=True)
    d = pd.read_csv(OUT.parent / "crypto_funding_xs" / "corrected" / "dev_daily.csv", index_col=0, parse_dates=True)
    b = ser["base"].to_numpy(); n = len(b); vol = b.std(ddof=1)
    stress_drag = float((d["base"] - d["stress"]).mean())
    gate = 1.8 / np.sqrt(n / ANN)
    res = {"n": n, "gate": gate, "stress_drag_daily": stress_drag}

    # ---- alternative p-values on the ACTUAL series
    alt = {"frozen_circular_b21": centred_block_p(b, 21, 5000, 20260925)}
    for bl in (63, 126):
        alt[f"circular_b{bl}"] = centred_block_p(b, bl, 5000, 20260925)
    for mb in (5, 21, 63, 126):
        alt[f"stationary_mean{mb}"] = stationary_p(b, mb, 3000)
    s = ser["base"]
    for lab, per in (("quarterly", "Q"), ("half_year", "6M")):
        g = s.groupby(s.index.to_period("Q")).sum() if per == "Q" else s.groupby([s.index.year, s.index.month > 6]).sum()
        t = g.mean() / (g.std(ddof=1) / np.sqrt(len(g)))
        alt[f"t_{lab}_sums(n={len(g)})"] = float(stats.t.sf(t, len(g) - 1))
    import statsmodels.api as sm
    for L in (21, 63, 126):
        m = sm.OLS(b, np.ones(n)).fit(cov_type="HAC", cov_kwds={"maxlags": L})
        alt[f"HAC_NW_lag{L}"] = float(stats.norm.sf(m.tvalues[0]))
    # wild/sign-flip on monthly sums (symmetric null; conservative under skew)
    mo = s.groupby(s.index.to_period("M")).sum().to_numpy()
    rng = np.random.default_rng(SEED)
    flips = rng.choice([-1, 1], size=(20000, len(mo)))
    alt["monthly_signflip"] = float((np.sum((flips * mo).mean(axis=1) >= mo.mean()) + 1) / 20001)
    res["p_actual_series"] = alt

    # ---- size of the FROZEN test (and full gate) under calibrated null processes (all mean 0, daily vol matched)
    cx = b - b.mean()
    rng = np.random.default_rng(SEED)
    R = 1500

    def garch_jump(skew_sign, lam=0.01, jmean=5.0):
        w, a, bb = 0.05, 0.10, 0.85
        z = rng.standard_t(5, n) / np.sqrt(5 / 3); h = np.empty(n); e = np.empty(n); h[0] = 1.0
        for t in range(n):
            if t: h[t] = w + a * e[t - 1] ** 2 + bb * h[t - 1]
            e[t] = np.sqrt(h[t]) * z[t]
        j = (rng.random(n) < lam) * rng.exponential(jmean, n) * skew_sign
        x = e + j - lam * jmean * skew_sign
        return x / x.std() * vol

    def regime(L, m):
        st = np.empty(n); st[0] = rng.choice([-1, 1])
        sw = rng.random(n) < 1.0 / L
        for t in range(1, n):
            st[t] = -st[t - 1] if sw[t] else st[t - 1]
        e = rng.choice(cx, n, replace=True)
        x = e + m * st
        return x - 0.0  # unconditional mean zero (symmetric states)

    def stat_boot(mb):
        idx = np.empty(n, dtype=int); i = rng.integers(n)
        for t in range(n):
            i = rng.integers(n) if (t == 0 or rng.random() < 1 / mb) else (i + 1) % n
            idx[t] = i
        return cx[idx]

    procs = {
        "iid_normal": lambda: rng.normal(0, vol, n),
        "iid_resample_empirical (skew 1.9, kurt 23)": lambda: rng.choice(cx, n, replace=True),
        "garch_t5_pos_jumps (skew>0)": lambda: garch_jump(+1),
        "garch_t5_neg_jumps (carry crash, skew<0)": lambda: garch_jump(-1),
        "stationary_boot_empirical_mean_block_63": lambda: stat_boot(63),
        "regime_switch_L180_m0.001 (+/-0.37/yr)": lambda: regime(180, 0.001),
        "regime_switch_L365_m0.002 (+/-0.73/yr)": lambda: regime(365, 0.002),
        "regime_switch_L365_m0.003 (+/-1.10/yr)": lambda: regime(365, 0.003),
    }
    size = {}
    for name, f in procs.items():
        ps, passes, sk = [], 0, []
        for _ in range(R):
            x = f()
            if name.startswith("regime"):
                x = x  # keep in-sample mean as generated (true mean 0)
            p = fast_block_p(x, 21, 400, rng)
            ps.append(p); sk.append(stats.skew(x))
            if p < ALPHA and sharpe(x) >= gate and (x - stress_drag).mean() > 0:
                passes += 1
        ps = np.array(ps)
        size[name] = {"size_at_0.025": float(np.mean(ps < 0.025)), "size_at_0.05": float(np.mean(ps < 0.05)),
                      "size_at_0.0026": float(np.mean(ps <= 0.0026)),
                      "P_full_gate_pass": passes / R, "median_skew": float(np.median(sk))}
        print(name, size[name], flush=True)
    res["frozen_test_size_under_null"] = size
    res["calibrated_P_pass_given_null_worst"] = max(v["P_full_gate_pass"] for k, v in size.items() if not k.startswith("regime_switch_L365"))
    # calibrated p: fraction of null draws (each process) whose frozen p <= observed 0.0026 -> max over non-extreme processes
    res["calibrated_p_for_observed_0.0026"] = {k: v["size_at_0.0026"] for k, v in size.items()}
    (OUT / "null_calibration.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
