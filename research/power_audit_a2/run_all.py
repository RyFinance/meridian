"""A2 independent MC audit of Amendment 2 (dev gate) + Amendment 3 (validation gate). Synthetic data only.

Run:  cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.power_audit_a2.run_all
Writes reports/power_audit_a2/*.csv|json|png
"""
from __future__ import annotations

import json
import sys
import time
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from research.power_audit_a2 import dgps as D
from research.power_audit_a2 import engine as E

OUT = Path("reports/power_audit_a2")
OUT.mkdir(parents=True, exist_ok=True)
FAST = "--fast" in sys.argv
W_MAIN = 4000 if FAST else 20000
W_GRID = 3000 if FAST else 10000
S_GRID = [0.0, 0.05, 0.23, 0.3, 0.5, 0.7, 1.0]


def rng_for(*key):
    return np.random.default_rng(zlib.crc32(repr(key).encode()))


def chunked(fn, W, chunk):
    outs = []
    for s in range(0, W, chunk):
        outs.append(fn(min(chunk, W - s), s))
    return outs


# ------------------------------------------------------------------ stage simulation
UNIVARIATE = {
    # name: (generator, ppy, kwargs)
    "iid_daily": (D.iid_normal, 252, {}),
    "iid_monthly": (D.iid_normal, 12, {}),
    "ar1_0.1_daily": (D.ar1, 252, {"phi": 0.1}),
    "ar1_0.3_daily": (D.ar1, 252, {"phi": 0.3}),
    "ar1_0.1_monthly": (D.ar1, 12, {"phi": 0.1}),
    "ar1_0.3_monthly": (D.ar1, 12, {"phi": 0.3}),
    "t4_daily": (D.student_t, 252, {"df": 4.0}),
    "t4_monthly": (D.student_t, 12, {"df": 4.0}),
    "carry_crash_monthly": (D.carry_crash, 12, {"lam_per_year": 0.2, "jump_sd_mult": 6.0}),
    "carry_crash_weekly": (D.carry_crash, 52, {"lam_per_year": 0.2, "jump_sd_mult": 12.0}),
    "stoch_vol_daily": (D.stoch_vol, 252, {}),
    "long_short_weekly": (D.long_short, 52, {}),
}


def stage_univariate(name, T, S, W, tag, b=None, extra=None):
    gen, ppy, kw = UNIVARIATE[name]
    kw = dict(kw)
    if extra:
        kw.update(extra)
    n = int(round(T * ppy))
    rng = rng_for(name, T, S, W, tag, b, tuple(sorted((extra or {}).items())))
    chunk = max(500, min(W, 4_000_000 // n))
    res = {"S": [], "p": [], "stress_pos": []}
    for s in range(0, W, chunk):
        w = min(chunk, W - s)
        net, st = gen(w, n, S, ppy, rng, **kw)
        r = E.stage_stats(net, st, ppy, rng, b=b)
        for k in res:
            res[k].append(r[k])
    out = {k: np.concatenate(v) for k, v in res.items()}
    out["T"] = n / ppy
    return out


def stage_timing(variant, T, S, W, tag):
    ppy = 252
    n = int(round(T * ppy))
    rng = rng_for("timing", variant, T, S, W, tag)
    res = {"S": [], "p": [], "stress_pos": []}
    for s in range(0, W, 2000):
        w = min(2000, W - s)
        d = D.long_only_timing(w, n, S, ppy, rng)
        net, st = d[variant]
        r = E.stage_stats(net, st, ppy, rng)
        for k in res:
            res[k].append(r[k])
    out = {k: np.concatenate(v) for k, v in res.items()}
    out["T"] = n / ppy
    return out


def stage_event(T, S, W, tag, icc=0.3):
    rng = rng_for("event", T, S, W, tag, icc)
    res = {"S": [], "p": [], "stress_pos": [], "p_naive": []}
    for s in range(0, W, 5000):
        w = min(5000, W - s)
        d = D.event_cluster(w, T, S, rng, icc=icc)
        net, st = d["weekly"]
        r = E.stage_stats(net, st, 52, rng)
        for k in ("S", "p", "stress_pos"):
            res[k].append(r[k])
        res["p_naive"].append(E.cbb_pvalue(d["events"], rng, b=1))  # events treated as independent
    out = {k: np.concatenate(v) for k, v in res.items()}
    out["T"] = int(round(T * 52)) / 52
    return out


def summarize(dev, val, k=1, label=None):
    pd_ = E.dev_pass(dev, k)
    pv_new = E.val_new_pass(val, 1)
    pv_old = E.val_old_pass(val, k)
    Pd, Pn, Po = pd_.mean(), pv_new.mean(), pv_old.mean()
    return {
        "P_dev": Pd,
        "P_val_new": Pn,
        "P_val_old": Po,
        "joint_new": Pd * Pn,  # independent windows: product is the exact joint, lower MC error
        "joint_old": Pd * Po,
        "joint_new_mc": (pd_ & pv_new).mean(),
        "joint_old_mc": (pd_ & pv_old).mean(),
        "rej05_single": (dev["p"] < 0.05).mean(),
        "rej0125_single": (dev["p"] < 0.0125).mean(),
        "rej01_single": (dev["p"] < 0.01).mean(),
        "sharpe_leg_dev": (dev["S"] >= 1.8 / np.sqrt(dev["T"])).mean(),
        "mean_Shat": dev["S"].mean(),
    }


# ------------------------------------------------------------------ E1: per-DGP table
def exp_dgp_table():
    rows = []
    T = 12.0
    for name in UNIVARIATE:
        for S in S_GRID:
            t0 = time.time()
            dev = stage_univariate(name, T, S, W_MAIN, "dev")
            val = stage_univariate(name, T, S, W_MAIN, "val")
            r = summarize(dev, val)
            r.update(dgp=name, S=S, T_dev=T, T_val=T, secs=round(time.time() - t0, 1))
            rows.append(r)
        print("E1", name, flush=True)
    for variant in ("raw", "active"):
        for S in S_GRID:
            dev = stage_timing(variant, T, S, W_MAIN // 2, "dev")
            val = stage_timing(variant, T, S, W_MAIN // 2, "val")
            r = summarize(dev, val)
            r.update(dgp=f"long_only_timing_{variant}", S=S, T_dev=T, T_val=T)
            rows.append(r)
        print("E1 timing", variant, flush=True)
    for icc in (0.3,):
        for S in S_GRID:
            dev = stage_event(T, S, W_MAIN, "dev", icc=icc)
            val = stage_event(T, S, W_MAIN, "val", icc=icc)
            r = summarize(dev, val)
            r.update(dgp=f"event_cluster_icc{icc}_weekly", S=S, T_dev=T, T_val=T,
                     rej05_naive_events=(dev["p_naive"] < 0.05).mean())
            rows.append(r)
        print("E1 events", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "dgp_table.csv", index=False)
    return df


# ------------------------------------------------------------------ E2: families k = 1, 2, 4 with correlation
def family_sim(k, rho, S_vec, T_dev, T_val, Wf, ppy=52, tag=""):
    """Returns per-family arrays of dev pass, new-val pass, old-val pass for each member (Wf, k)."""
    rng = rng_for("family", k, rho, tuple(S_vec), T_dev, T_val, Wf, tag)
    S_vec = np.asarray(S_vec, float)

    def gen(T):
        n = int(round(T * ppy))
        stats = {"S": [], "p": [], "stress_pos": []}
        chunk = max(200, 2_000_000 // (n * k))
        for s in range(0, Wf, chunk):
            w = min(chunk, Wf - s)
            c = rng.standard_normal((w, 1, n))
            z = np.sqrt(rho) * c + np.sqrt(1 - rho) * rng.standard_normal((w, k, n))
            net = z + (S_vec / np.sqrt(ppy))[None, :, None]
            st = net - D.STRESS_DRAG_SR / np.sqrt(ppy)
            r = E.stage_stats(net.reshape(w * k, n), st.reshape(w * k, n), ppy, rng)
            for key in stats:
                stats[key].append(r[key].reshape(w, k))
        out = {key: np.concatenate(v) for key, v in stats.items()}
        out["T"] = n / ppy
        return out

    dev, val = gen(T_dev), gen(T_val)
    dpass = E.dev_pass(dev, k)
    k_val = dpass.sum(axis=1, keepdims=True)
    vnew = E.val_new_pass(val, k_val)
    vold = E.val_old_pass(val, k)
    return dpass, vnew, vold


def exp_families():
    rows = []
    for k in (1, 2, 4):
        for rho in (0.0, 0.5, 0.9):
            if k == 1 and rho > 0:
                continue
            for scen, S_vec in (("all_null", [0.0] * k), ("all_0.7", [0.7] * k),
                                ("one_0.7_rest_null", [0.7] + [0.0] * (k - 1)),
                                ("all_leak_0.05", [0.05] * k), ("all_0.3", [0.3] * k)):
                if k == 1 and scen == "one_0.7_rest_null":
                    continue
                Wf = (60000 if scen in ("all_null", "all_leak_0.05") else 10000) // (1 if not FAST else 5)
                dp, vn, vo = family_sim(k, rho, S_vec, 12.0, 12.0, Wf, tag=scen)
                jn, jo = dp & vn, dp & vo
                S_arr = np.array(S_vec)
                null_mask = S_arr <= 0.05 if scen != "all_leak_0.05" else np.ones(k, bool)
                alt_mask = ~null_mask
                r = dict(k=k, rho=rho, scenario=scen, W_families=Wf,
                         dev_pass_per_cand=dp.mean(),
                         joint_new_per_cand=jn.mean(), joint_old_per_cand=jo.mean(),
                         fwer_new=(jn[:, null_mask].any(axis=1)).mean() if null_mask.any() else np.nan,
                         fwer_old=(jo[:, null_mask].any(axis=1)).mean() if null_mask.any() else np.nan,
                         power_true_new=jn[:, alt_mask].mean() if alt_mask.any() else np.nan,
                         power_true_old=jo[:, alt_mask].mean() if alt_mask.any() else np.nan,
                         any_true_new=(jn[:, alt_mask].any(axis=1)).mean() if alt_mask.any() else np.nan)
                rows.append(r)
            print("E2", k, rho, flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "family_rates.csv", index=False)
    return df


# ------------------------------------------------------------------ E3: power vs years (old vs new val gate)
def exp_length():
    rows = []
    for name in ("iid_monthly", "ar1_0.3_monthly", "iid_daily"):
        ppy = UNIVARIATE[name][1]
        for T in (3, 5, 8, 12, 16, 20, 30, 40):
            if name == "iid_daily" and T > 20:
                continue
            for S in (0.0, 0.23, 0.3, 0.5, 0.7, 1.0):
                dev = stage_univariate(name, T, S, W_GRID, "Ldev")
                val = stage_univariate(name, T, S, W_GRID, "Lval")
                r = summarize(dev, val)
                r.update(dgp=name, T_each=T, T_total=2 * T, S=S)
                rows.append(r)
        print("E3", name, flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "power_vs_years.csv", index=False)
    return df


# ------------------------------------------------------------------ E4: cross-sectional breadth
def exp_xs():
    rows = []
    Wx = 1500 if FAST else 5000
    n_m = 288  # 12y dev + 12y val, monthly
    N = 300
    for tilt in (0.0, 0.3, 0.6):
        for ic in (0.0, 0.01, 0.02, 0.03):
            rng = rng_for("xs", tilt, ic, Wx)
            ls, tpool = D.xs_quintile(Wx, n_m, rng, N=N, ic=ic, tilt=tilt)
            dev_x, val_x = ls[:, :144], ls[:, 144:]
            true_S = ls.mean() / ls.std() * np.sqrt(12)  # pooled over worlds: population Sharpe
            dev = E.stage_stats(dev_x, dev_x - 0.1 / np.sqrt(12) * ls.std(), 12, rng)
            val = E.stage_stats(val_x, val_x - 0.1 / np.sqrt(12) * ls.std(), 12, rng)
            r = summarize(dev, val)
            # naive-N: fundamental law IR = IC * sqrt(12 N) (x quintile transfer ~ 0.8 for top/bottom 20%)
            tc_quint = 2 * norm.pdf(norm.ppf(0.8)) / 0.2 / np.sqrt(2 / 0.2)  # transfer coeff of 20/20 sort
            S_naive = ic * np.sqrt(12 * N) * tc_quint
            se = 1 / np.sqrt(12)
            pdev_naive = norm.sf(max(1.8 / np.sqrt(12), 1.645 * se) - S_naive, scale=se) if True else 0
            pval_naive = norm.sf(max(0.30, 1.645 * se) - S_naive, scale=se)
            r.update(dgp="xs_quintile", tilt=tilt, IC=ic, N=N, true_S=true_S, naive_S_fundlaw=S_naive,
                     naive_joint_new=pdev_naive * pval_naive,
                     naive_N_eff=N, pooled_t_rej05=(tpool > 1.645).mean(),
                     pooled_t_mean=tpool.mean())
            rows.append(r)
            print("E4", tilt, ic, round(true_S, 3), flush=True)
    df = pd.DataFrame(rows)
    # breadth curve at fixed IC=0.02: true S vs N for tilt 0 / 0.3
    curve = []
    for tilt in (0.0, 0.3):
        for N in (25, 50, 100, 200, 400, 800):
            rng = rng_for("xs_curve", tilt, N)
            ls, _ = D.xs_quintile(400 if not FAST else 100, 240, rng, N=N, ic=0.02, tilt=tilt, want_pooled=False)
            curve.append(dict(tilt=tilt, N=N, true_S=ls.mean() / ls.std() * np.sqrt(12),
                              naive_S=0.02 * np.sqrt(12 * N) * 2 * norm.pdf(norm.ppf(0.8)) / 0.2 / np.sqrt(10)))
    pd.DataFrame(curve).to_csv(OUT / "xs_breadth_curve.csv", index=False)
    df.to_csv(OUT / "xs_breadth.csv", index=False)
    return df, pd.DataFrame(curve)


# ------------------------------------------------------------------ E5: vol / turnover / noise at equal net Sharpe
def exp_vol_turnover():
    rows = []
    T = 12.0
    # (a) turnover: extra stress drag in Sharpe units (stress = 2x base cost, so drag = base cost drag)
    for drag in (0.05, 0.3, 0.5, 0.7, 1.0, 1.5):
        for S in (0.0, 0.3, 0.7, 1.0):
            dev = stage_univariate("iid_daily", T, S, W_GRID, "tdev", extra={"stress_drag_sr": drag})
            val = stage_univariate("iid_daily", T, S, W_GRID, "tval", extra={"stress_drag_sr": drag})
            r = summarize(dev, val)
            r.update(family="turnover", design=f"stress_drag_{drag}", stress_drag_sr=drag, S=S,
                     true_stress_S=S - drag)
            rows.append(r)
    # (b) noise at equal true net Sharpe: estimator variance multiplier kappa^2 via AR(1) (daily)
    for phi in (-0.2, 0.0, 0.2, 0.4, 0.6):
        for S in (0.0, 0.3, 0.5, 0.7):
            dev = stage_univariate("ar1_0.1_daily", T, S, W_GRID, "ndev", extra={"phi": phi})
            val = stage_univariate("ar1_0.1_daily", T, S, W_GRID, "nval", extra={"phi": phi})
            r = summarize(dev, val)
            r.update(family="noise_kappa", design=f"ar1_{phi}", kappa2=(1 + phi) / (1 - phi), S=S)
            rows.append(r)
    # (c) 'noisy/concentrated' designs: fat tails + vol clustering at equal Sharpe, daily and monthly
    for nm in ("iid_daily", "stoch_vol_daily", "t4_daily", "iid_monthly", "t4_monthly", "carry_crash_monthly"):
        for S in (0.0, 0.3, 0.7):
            dev = stage_univariate(nm, T, S, W_GRID, "cdev")
            val = stage_univariate(nm, T, S, W_GRID, "cval")
            r = summarize(dev, val)
            r.update(family="tails", design=nm, S=S)
            rows.append(r)
    # (d) vol scale invariance check: sd x5 (Sharpe identical by construction -> identical pass rates)
    for S in (0.0, 0.7):
        rng = rng_for("volscale", S)
        n = 12 * 252
        base, _ = D.iid_normal(W_GRID, n, S, 252, rng)
        for scale in (1.0, 5.0):
            net = base * scale
            st = net - 0.1 / np.sqrt(252) * scale
            dev = E.stage_stats(net, st, 252, rng_for("vs_boot"))
            r = summarize(dev, dev)
            r.update(family="vol_scale", design=f"sd_x{scale}", S=S)
            rows.append(r)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "vol_turnover.csv", index=False)
    print("E5 done", flush=True)
    return df


# ------------------------------------------------------------------ E6: bootstrap coverage diagnostics
def exp_coverage():
    rows = []
    for name, T in (("iid_monthly", 12), ("ar1_0.3_monthly", 12), ("ar1_0.3_daily", 12), ("ar1_0.1_daily", 12),
                    ("carry_crash_monthly", 12), ("carry_crash_monthly", 5), ("carry_crash_weekly", 12),
                    ("t4_monthly", 12), ("t4_monthly", 5), ("iid_monthly", 5), ("ar1_0.3_monthly", 5)):
        ppy = UNIVARIATE[name][1]
        n = int(T * ppy)
        for b in (1, E.block_len(n), 2 * E.block_len(n)):
            st = stage_univariate(name, T, 0.0, W_MAIN, "cov", b=b)
            rows.append(dict(dgp=name, T=T, n=n, block=b, rej05=(st["p"] < 0.05).mean(),
                             rej025=(st["p"] < 0.025).mean(), rej0125=(st["p"] < 0.0125).mean(),
                             rej01=(st["p"] < 0.01).mean(),
                             sharpe_leg=(st["S"] >= 1.8 / np.sqrt(T)).mean(),
                             dev_pass_k1=E.dev_pass(st, 1).mean()))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "bootstrap_coverage.csv", index=False)
    print("E6 done", flush=True)
    return df


# ------------------------------------------------------------------ E7: replicate cycle-4 section 7 and section 4
def exp_replicate():
    rows = []
    # Section 7: tsy-like windows 12 + 11.6 y, D (kappa^2) = 1.4 via daily AR(1) phi = 1/6
    for label, phi in (("kappa2_1.4_ar1_daily", 1 / 6), ("kappa2_1.0_iid_daily", 0.0)):
        for S in (0.0, 0.05, 0.3, 0.5, 0.7, 1.0):
            dev = stage_univariate("ar1_0.1_daily", 12.0, S, W_MAIN, "s7dev", extra={"phi": phi})
            val = stage_univariate("ar1_0.1_daily", 11.6, S, W_MAIN, "s7val", extra={"phi": phi})
            pdv = E.dev_pass(dev, 1)
            v_old = E.val_old_pass(val, 1)
            v_new = E.val_new_pass(val, 1)
            v_new3 = E.val_new_pass(val, 3)
            v_half = (val["S"] >= 0.5 * dev["S"]) & (val["p"] < 0.05) & val["stress_pos"]
            rows.append(dict(table="sec7", model=label, S=S, P_dev=pdv.mean(),
                             P_val_old=v_old.mean(), joint_old=pdv.mean() * v_old.mean(),
                             P_val_new=v_new.mean(), joint_new=pdv.mean() * v_new.mean(),
                             joint_new_kval3=pdv.mean() * v_new3.mean(),
                             joint_half_dev=(pdv & v_half).mean(),
                             joint_new_mc=(pdv & v_new).mean()))
    print("E7 sec7", flush=True)
    # Section 4 retrospective: kappa^2 backed out of the report's own P_val(current gate) at S=0.7
    fams = {
        # name: (T_dev, T_val, k, dev_rule, P_val_report_at_0.7, ppy)
        "tsy_month_end": (12.0, 11.6, 1, "amend2", 0.44, 252),
        "commodity_roll": (10.4, 9.7, 2, "amend2", 0.42, 12),
        "fx_hedge_rebal": (6.0, 5.7, 1, "amend2", 0.45, 52),
        "IEF_SHY": (12.0, 11.7, 3, "amend2", 0.43, 252),
        "insider": (10.0, 10.5, 4, "flat0.5", 0.44, 252),
        "etf_hybrids": (12.0, 11.7, 5, "flat0.5", 0.44, 252),
    }
    for fam, (Td, Tv, k, rule, pv, ppy) in fams.items():
        se = 0.05 / -norm.ppf(pv)
        k2 = se * se * Tv
        phi = (k2 - 1) / (k2 + 1)
        for S in (0.0, 0.5, 0.7, 1.0):
            gen = "ar1_0.1_daily" if ppy == 252 else "ar1_0.1_monthly"
            if ppy == 52:
                gen = "long_short_weekly"
            extra = {"phi": phi} if ppy != 52 else None
            if ppy == 52:  # weekly AR via ar1 generator with ppy override: reuse ar1 directly
                gen = None
            if gen is None:
                n_d, n_v = int(Td * 52), int(Tv * 52)
                r_ = rng_for("retro", fam, S)
                net, st = D.ar1(W_MAIN, n_d, S, 52, r_, phi=phi)
                dev = E.stage_stats(net, st, 52, r_)
                net, st = D.ar1(W_MAIN, n_v, S, 52, r_, phi=phi)
                val = E.stage_stats(net, st, 52, r_)
            else:
                dev = stage_univariate(gen, Td, S, W_MAIN, f"r{fam}dev", extra=extra)
                val = stage_univariate(gen, Tv, S, W_MAIN, f"r{fam}val", extra=extra)
            if rule == "amend2":
                pdv = E.dev_pass(dev, k)
            else:
                pdv = (dev["S"] >= 0.5) & dev["stress_pos"]
            pdv_a2 = E.dev_pass(dev, k)
            rows.append(dict(table="sec4", model=fam, kappa2=k2, phi=phi, k=k, dev_rule=rule, S=S,
                             P_dev=pdv.mean(), P_dev_amend2=pdv_a2.mean(),
                             P_val_old=E.val_old_pass(val, k).mean(),
                             joint_old=pdv.mean() * E.val_old_pass(val, k).mean(),
                             P_val_new=E.val_new_pass(val, 1).mean(),
                             joint_new=pdv.mean() * E.val_new_pass(val, 1).mean(),
                             joint_new_amend2dev=pdv_a2.mean() * E.val_new_pass(val, 1).mean()))
        print("E7", fam, flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "replicate_cycle4.csv", index=False)
    return df


# ------------------------------------------------------------------ plots
def plots(len_df, vt_df, cov_df, xs_curve):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    d = len_df[len_df.dgp == "iid_monthly"]
    for S, col in ((0.3, "#8a8a8a"), (0.5, "#4c78a8"), (0.7, "#e45756"), (1.0, "#54a24b")):
        x = d[d.S == S]
        axes[0].plot(x.T_total, x.joint_new, "-o", color=col, ms=3, label=f"S={S} new gate")
        axes[0].plot(x.T_total, x.joint_old, "--", color=col, lw=1, label=f"S={S} old 0.75 gate")
    axes[0].axhline(0.8, color="k", lw=0.5)
    axes[0].set_xlabel("total years (dev = val)")
    axes[0].set_ylabel("joint pass probability")
    axes[0].set_title("Joint power vs length (iid monthly, k=1)")
    axes[0].legend(fontsize=7, ncol=2)
    t = vt_df[(vt_df.family == "turnover")]
    for S, col in ((0.0, "#8a8a8a"), (0.3, "#4c78a8"), (0.7, "#e45756"), (1.0, "#54a24b")):
        x = t[t.S == S]
        axes[1].plot(x.stress_drag_sr, x.joint_new, "-o", color=col, ms=3, label=f"net S={S}")
    axes[1].set_xlabel("stress-cost drag (Sharpe units) at equal net Sharpe")
    axes[1].set_ylabel("joint pass (new gate)")
    axes[1].set_yscale("symlog", linthresh=1e-3)
    axes[1].set_title("Turnover penalty via stress leg (iid daily, 12+12y)")
    axes[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "power_years_turnover.png", dpi=130)

    fig, ax = plt.subplots(figsize=(9, 4))
    c = cov_df[cov_df.block == cov_df.groupby(["dgp", "T"]).block.transform(lambda s: sorted(s)[1])]
    lab = c.dgp + " T=" + c["T"].astype(str)
    ax.barh(lab, c.rej05, color="#4c78a8", label="P(p<0.05|H0)")
    ax.barh(lab, c.rej0125, color="#e45756", label="P(p<0.0125|H0)")
    ax.axvline(0.05, color="#4c78a8", lw=0.8)
    ax.axvline(0.0125, color="#e45756", lw=0.8)
    ax.set_title("CBB (b = n^1/3) one-sided size under mean-zero null")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "bootstrap_size.png", dpi=130)

    fig, ax = plt.subplots(figsize=(6, 4))
    for tilt, col in ((0.0, "#4c78a8"), (0.3, "#e45756")):
        x = xs_curve[xs_curve.tilt == tilt]
        ax.plot(x.N, x.true_S, "-o", color=col, label=f"true Sharpe, tilt {tilt}")
    x = xs_curve[xs_curve.tilt == 0.0]
    ax.plot(x.N, x.naive_S, "k--", label="naive IC*sqrt(12N)*TC")
    ax.set_xscale("log")
    ax.set_xlabel("N assets")
    ax.set_ylabel("annualised Sharpe of Q5-Q1")
    ax.set_title("Breadth at IC 0.02: naive vs true")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "xs_breadth.png", dpi=130)


def main():
    t0 = time.time()
    rep = exp_replicate()
    cov = exp_coverage()
    fam = exp_families()
    e1 = exp_dgp_table()
    ln = exp_length()
    vt = exp_vol_turnover()
    xs, curve = exp_xs()
    plots(ln, vt, cov, curve)
    meta = dict(W_MAIN=W_MAIN, W_GRID=W_GRID, B=E.B_DEFAULT, block="round(n^(1/3)), circular, mean-centred",
                stress="net minus extra drag (default 0.10 Sharpe units)", fast=FAST,
                runtime_min=round((time.time() - t0) / 60, 1))
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2))
    print("done", meta, flush=True)


if __name__ == "__main__":
    main()
