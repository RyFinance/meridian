"""Cycle 8b (cycle-9 item 2): cycle 8 rerun with the live-fund trend sleeve and daily drawdown evaluation.

Implements research/cycle9/FRAMEWORK.md Part B (C1-C4) on top of the frozen cycle-8 code (imported unchanged).

usage: python -m research.cycle9.run8b --proc8 <cycle8 view>/proc --cma8 <cycle8 view>/cma --live <cycle9 view>/live
                                        --out reports/cycle9/cycle8b/out [--paths 10000]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.cycle8 import forward as FW
from research.cycle8 import run as R8
from research.cycle8.engine import core, metrics as MX, sleeves as SL
from research.cycle8.engine.menu import ANSWER_ITEMS, COST, COST_OVERLAY, MENU, RP_SLEEVES, eq_col, levels

TREND_END = "2026-05"
SLOTS = 23                      # max trading days in a month (padding days carry zero return and zero carry)
TOL = (0.25, 0.35, 0.50)
CHUNK = 500


# ----------------------------------------------------------------------------- C1: trend sleeve
def trend_input(panel: pd.DataFrame, ts: pd.Series, variant: str = "primary") -> tuple[pd.Series, dict]:
    """USD excess X_t (net of fees) for 1985-01..TREND_END per FRAMEWORK C1. variant: primary | s1_unscaled | s2_full_haircut."""
    panel = panel.sort_index()
    n = panel.notna().sum(1)
    e1 = panel.mean(1).where(n >= 3)
    e1 = e1.loc[:TREND_END]
    defined = e1.notna()
    # live-era start: first month from which E1 is defined for every month through TREND_END
    rev = defined[::-1].cumprod()[::-1].astype(bool)
    live = e1[rev]
    if not len(live):
        raise ValueError("E1 (>= 3 funds) is not defined at the end of the trend window")
    live_start = live.index[0]
    fund_vol = panel.std() * np.sqrt(12)
    med_vol = float(fund_vol.median())
    k = 1.0 if variant == "s1_unscaled" else med_vol / float(live.std() * np.sqrt(12))
    L = k * live
    tsw = ts.loc["1985-01":TREND_END]
    ts_live = tsw.reindex(L.index)
    rho = float(L.mean() / ts_live.mean())
    k_pre = float(L.std() / ts_live.std())
    pre = tsw.loc[: live_start - pd.offsets.MonthEnd(1)]
    info = {"variant": variant, "live_start": f"{live_start:%Y-%m}", "live_months": int(len(L)), "k": k,
            "median_fund_vol": med_vol, "e1_vol_live": float(live.std() * np.sqrt(12)), "rho": rho, "k_pre": k_pre,
            "live_mean_ann": float(L.mean() * 12), "live_vol_ann": float(L.std() * np.sqrt(12)),
            "ts_live_mean_ann": float(ts_live.mean() * 12), "pre_months": int(len(pre))}
    if len(pre):
        m_pre = float(pre.mean())
        level = float(L.mean()) if variant == "s2_full_haircut" else rho * m_pre
        X_pre = k_pre * (pre - m_pre) + level
        info.update({"ts_pre_mean_ann": m_pre * 12, "x_pre_mean_ann": float(X_pre.mean() * 12),
                     "x_pre_vol_ann": float(X_pre.std() * np.sqrt(12))})
        X = pd.concat([X_pre, L])
    else:
        X = L.loc["1985-01":]
        info["note"] = "live era covers the whole trend window"
    X.index.name = "date"
    return X, info


def load_all(proc8: Path, live: Path, variant: str):
    d = SL.load(proc8)
    d["rf_usd_daily"] = pd.read_parquet(proc8 / "rf_usd_daily.parquet")
    panel = pd.read_csv(live / "panel_monthly_excess.csv", index_col=0, parse_dates=True)
    panel.index = panel.index.to_period("M").to_timestamp("M")
    ts = d["trend_monthly"]["tsmom_excess"]
    X, info = trend_input(panel, ts, variant)
    tm = pd.DataFrame({"tsmom_excess": X})
    d["trend_monthly"] = tm
    return d, info


def set_drag_zero():
    SL.FEE["TREND_DRAG"] = 0.0          # live records are already net of all fees (C1)


def daily_trend_proxy(prox: pd.DataFrame, d: dict, live: Path) -> pd.DataFrame:
    """C3: equal-weight daily NAV returns of included funds (USD) as the trend sleeve's intramonth proxy."""
    f = live / "daily_ew.csv"
    if not f.exists():
        return prox
    dew = pd.read_csv(f, index_col=0, parse_dates=True)["ew_ret"]
    days = prox.index
    fx = d["fx_daily"]["USDCAD"].reindex(days.union(d["fx_daily"].index)).ffill().reindex(days)
    fxr = fx / fx.shift(1) - 1
    r = dew.reindex(days)
    prox = prox.copy()
    prox["TREND"] = (1 + r) * (1 + fxr) - 1
    prox["X_TREND"] = r
    return prox


# ----------------------------------------------------------------------------- C2: daily bootstrap
def month_blocks(Dd: pd.DataFrame, carry_m: pd.DataFrame):
    """Daily frame -> (nm, SLOTS, k) padded returns and (nm, SLOTS, 2) per-day carry [margin, cash]."""
    mk = R8.month_key(Dd.index)
    months = pd.Index(np.unique(mk))
    k = Dd.shape[1]
    D = np.zeros((len(months), SLOTS, k))
    C = np.zeros((len(months), SLOTS, 2))
    vals = Dd.values
    pos = 0
    for i, m in enumerate(months):
        nd = int((mk == m).sum())
        if nd > SLOTS:
            raise ValueError(f"{m}: {nd} trading days > {SLOTS}")
        D[i, :nd] = vals[pos:pos + nd]
        C[i, :nd, 0] = carry_m.at[m, "MRATE"] / nd
        C[i, :nd, 1] = carry_m.at[m, "CASH"] / nd
        pos += nd
    return months, D, C


def daily_boot(D, C, n_f, w, o, L, cf, co, P, mean_block, seed, burn=36, T_eval=360, rp_monthly=None,
               horizons=(120, 240, 360)):
    """Stationary bootstrap over months carrying full daily paths; daily-step simulation with the cycle-8 engine."""
    nm = D.shape[0]
    rng = np.random.default_rng(seed)
    T = burn + T_eval
    idx_all = MX.stationary_indices(nm, T, P, mean_block, rng)
    rebal = np.zeros(T_eval * SLOTS, bool)
    rebal[::SLOTS] = True
    out_dd = {H: [] for H in horizons}
    ruin = {H: [] for H in horizons}
    calls = []
    for s in range(0, P, CHUNK):
        idx = idx_all[s:s + CHUNK]
        Pc = idx.shape[0]
        ev = idx[:, burn:]
        Z = D[ev].reshape(Pc, T_eval * SLOTS, D.shape[2])
        Cz = C[ev].reshape(Pc, T_eval * SLOTS, 2)
        Rf = Z[:, :, :n_f]
        X = Z[:, :, n_f:] if Z.shape[2] > n_f else np.zeros((Pc, T_eval * SLOTS, 1))
        if rp_monthly is not None:
            allR = rp_monthly[idx]                                    # (Pc, T, n_f)
            cs = np.cumsum(np.concatenate([np.zeros((Pc, 1, n_f)), allR], 1), 1)
            cs2 = np.cumsum(np.concatenate([np.zeros((Pc, 1, n_f)), allR ** 2], 1), 1)
            t = np.arange(burn, T)
            s1 = cs[:, t, :] - cs[:, t - 36, :]
            s2 = cs2[:, t, :] - cs2[:, t - 36, :]
            var = (s2 - s1 ** 2 / 36) / 35
            inv = 1 / np.sqrt(np.maximum(var, 1e-12))
            wm = inv / inv.sum(2, keepdims=True)
            ww = np.repeat(wm, SLOTS, axis=1)
        else:
            ww = w
        res = core.simulate(Rf, X, Cz, ww, o, L, cf, co, rebal)
        W = res["wealth"]
        for H in horizons:
            out_dd[H].append(core.max_drawdown(W[:, :H * SLOTS + 1]))
            ruin[H].append(W[:, H * SLOTS] <= 0)
        calls.append(res["calls"])
    out = {}
    for H in horizons:
        dd = np.concatenate(out_dd[H])
        for tol in TOL:
            out[f"pd_dd{int(tol * 100)}_{H // 12}y"] = float((dd > tol).mean())
        out[f"pd_ruin_{H // 12}y"] = float(np.concatenate(ruin[H]).mean())
    out["pd_calls_mean_30y"] = float(np.concatenate(calls).mean())
    return out


def boot_item(M, prox, item, L, P, mean_block, seed, spread_extra=0.0):
    names, fcols, ocols = R8.item_columns(item, L)
    a, b = R8.item_window(M, item, L)
    is_rp = MENU[item]["funded"] == "RISK_PARITY"
    start = M.index[M.index.get_loc(a) - 36] if is_rp else a
    Mw = M.loc[start:b].copy()
    Mw["MRATE"] = Mw["MRATE"] + spread_extra / 12
    Dd = R8.build_daily(Mw, prox, fcols + ocols, start, b)
    months, D, C = month_blocks(Dd, Mw)
    w = None if is_rp else np.array([MENU[item]["funded"][n] for n in names])
    o = np.array([MENU[item]["overlay"][c] for c in ocols]) if ocols else np.zeros(1)
    cf = np.array([COST[n] for n in names])
    co = np.array([COST_OVERLAY[c] for c in ocols]) if ocols else np.zeros(1)
    rpm = M.loc[start:b, fcols].values if is_rp else None
    out = daily_boot(D, C, len(fcols), w, o, L, cf, co, P, mean_block, seed, rp_monthly=rpm)
    out["boot_window"] = f"{months[0]:%Y-%m}..{months[-1]:%Y-%m}"
    return out


def boot_p7(p7_daily: pd.DataFrame, M, P, mean_block, seed):
    Dd = p7_daily.loc["1971-02-01":"2026-08-31"]
    months, D, C = month_blocks(Dd, M)
    return daily_boot(D, C, 2, np.array([0.6, 0.4]), np.zeros(1), 1.0, np.array([0.0015, 0.0015]), np.zeros(1),
                      P, mean_block, seed)


def p7_daily_cad(d):
    eqd = d["eq_daily"]["US_usd"].dropna()
    days = eqd.index[(eqd.index >= "1971-01-01") & (eqd.index <= "2026-08-31")]
    fx = d["fx_daily"]["USDCAD"].reindex(days.union(d["fx_daily"].index)).ffill().reindex(days)
    fxr = (fx / fx.shift(1) - 1).fillna(0.0)
    b = d["bond_daily"]["US20_ret"].reindex(days).fillna(0.0)
    rf = d["rf_usd_daily"]["rf_usd"]
    out = {}
    from research.cycle8.engine import letf
    for tag, (e, t) in {"P7-2x": ("SSO", "UBT"), "P7-3x": ("UPRO", "TMF")}.items():
        ke, se, ee, _ = letf.SPEC[e]
        kt, st, et, _ = letf.SPEC[t]
        re_ = letf.letf_daily(eqd.reindex(days), rf, ke, se, ee)
        rt_ = letf.letf_daily(b, rf, kt, st, et)
        out[tag] = pd.DataFrame({"E": (1 + re_) * (1 + fxr) - 1, "T": (1 + rt_) * (1 + fxr) - 1}, index=days)
    return out


# ----------------------------------------------------------------------------- main
def run_all(args, variant="primary", items=None, sens=True):
    proc8, live = Path(args.proc8), Path(args.live)
    d, info = load_all(proc8, live, variant)
    set_drag_zero()
    M = SL.monthly_sleeves(d)
    cpi = d["cpi_ca_monthly"]["CPI_CA"]
    days = d["eq_daily"]["US_usd"].dropna().index
    days = days[(days >= "1971-01-01") & (days <= "2026-08-31")]
    prox = daily_trend_proxy(R8.daily_proxies(d, days), d, live)
    rets, extra, boots = {}, {}, {}
    items = items or list(MENU)
    for item in items:
        for L in levels(item):
            key = f"{item}@{L}"
            r, inf = R8.run_hist(M, prox, item, L)
            rets[key], extra[key] = r, inf
            b = boot_item(M, prox, item, L, args.paths, 24, R8.SEED)
            if sens:
                b12 = boot_item(M, prox, item, L, args.paths, 12, R8.SEED)
                b.update({f"b12_{k}": v for k, v in b12.items() if k.startswith("pd_dd")})
                if L > 1 and item in ANSWER_ITEMS:
                    b3 = boot_item(M, prox, item, L, args.paths, 24, R8.SEED, spread_extra=0.015)
                    b.update({f"m3_{k}": v for k, v in b3.items() if k.startswith("pd_dd")})
            boots[key] = b
            print(variant, key, flush=True)
    if variant == "primary":
        p7 = R8.run_p7(d, M)
        p7d = p7_daily_cad(d)
        for tag, (r, inf, _) in p7.items():
            key = f"{tag}@1.0"
            rets[key], extra[key] = r, inf
            boots[key] = boot_p7(p7d[tag], M, args.paths, 24, R8.SEED)
    rf = M["CASH"]
    p3 = rets.get("P3@1.0")
    rows = []
    for key, r in rets.items():
        s = MX.summary(r, rf, cpi)
        s.update(extra[key])
        s.update(boots[key])
        s["key"], s["item"], s["L"] = key, key.split("@")[0], float(key.split("@")[1])
        if p3 is not None:
            s["hurdle_p3_sharpe"] = MX.summary(p3.loc[r.index[0]:r.index[-1]], rf, sharpe_ci=False)["sharpe"]
        rows.append(s)
    tab = pd.DataFrame(rows).set_index("key")
    return d, M, rets, tab, info


def forward_and_answer(M, tab, rets, proc8, cma8, out):
    Mc = M.loc[FW.W_COMMON[0]:FW.W_COMMON[1]]
    cols = ["EQ_G_tfsa", "EQ_GH_tfsa", "BOND", "GOLD", "TREND", "CASH", "X_TREND", "X_BOND"]
    cov = Mc[cols].cov() * 12
    sig = pd.Series({"EQ_G": np.sqrt(cov.loc["EQ_G_tfsa", "EQ_G_tfsa"]), "BOND": np.sqrt(cov.loc["BOND", "BOND"])})
    S = FW.sleeve_cmas(pd.read_csv(Path(cma8) / "cma_mapped.csv"), sig)
    med = {k: float(pd.to_numeric(S[k]).median()) for k in ["EQ_G", "BOND", "GOLD", "TREND_gross", "CASH", "INFL"]}
    rp = R8.rp_weights(M, [eq_col(n, 1.0) for n in RP_SLEEVES]).loc[FW.W_COMMON[0]:FW.W_COMMON[1]].mean()
    rp.index = [c.replace("_tfsa", "") for c in rp.index]
    dp = pd.read_parquet(Path(proc8) / "eq_monthly.parquet")["US_dp"].dropna().iloc[-1]
    wht = 100 * (0.45 * 0.15 * dp + 0.25 * 0.10 * 0.03 + 0.05 * 0.10 * 0.025)
    rows = []
    for key in tab.index:
        item, L = key.split("@")[0], float(key.split("@")[1])
        if item.startswith("P7"):
            continue
        res = {s: FW.fwd_item(S.loc[s], item, L, rp, cov, wht) for s in FW.SOURCES}
        ar, geo, sd = FW.fwd_item(pd.Series(med), item, L, rp, cov, wht)
        rows.append({"key": key, "fwd_arith": ar, "fwd_geo": geo, "fwd_sd": sd,
                     "fwd_geo_min": min(v[1] for v in res.values()), "fwd_geo_max": max(v[1] for v in res.values())})
    T = tab.join(pd.DataFrame(rows).set_index("key"))
    T["eligible_sharpe"] = T["sharpe"] >= T["hurdle_p3_sharpe"] - 1e-12
    ans = []
    for tol in TOL:
        t = int(tol * 100)
        T[f"eligible_{t}"] = T["item"].isin(ANSWER_ITEMS) & (T[f"pd_dd{t}_20y"] < 0.10) & T["eligible_sharpe"]
        T[f"hist_daily_breach_{t}"] = T["maxdd_daily"] > tol
        el = T[T[f"eligible_{t}"]].sort_values(["fwd_geo", "L"], ascending=[False, True])
        unf = el[~el[f"hist_daily_breach_{t}"]]
        ans.append({"tolerance": t, "answer": el.index[0] if len(el) else None,
                    "answer_flag_breached_in_history": bool(el[f"hist_daily_breach_{t}"].iloc[0]) if len(el) else None,
                    "best_unflagged": unf.index[0] if len(unf) else None,
                    "best_levered_eligible": el[el.L > 1].index[0] if (el.L > 1).any() else None,
                    "n_eligible": len(el), "eligible": ";".join(el.index)})
    T.to_csv(out / "final_table.csv")
    pd.DataFrame(ans).to_csv(out / "answer.csv", index=False)
    return T, pd.DataFrame(ans)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proc8", required=True)
    ap.add_argument("--cma8", required=True)
    ap.add_argument("--live", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--paths", type=int, default=10000)
    ap.add_argument("--membership", default=None)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    d, M, rets, tab, info = run_all(args, "primary")
    M.to_parquet(out / "sleeves_monthly.parquet")
    pd.DataFrame(rets).to_parquet(out / "item_returns_monthly.parquet")
    crisis = []
    for key, r in rets.items():
        for name, (cr, cdd) in MX.crisis_table(r).items():
            crisis.append({"key": key, "crisis": name, "cum_return": cr, "max_dd": cdd})
    pd.DataFrame(crisis).to_csv(out / "crisis_table.csv", index=False)
    for item in list(MENU) + ["P7-2x", "P7-3x"]:
        r1 = rets[f"{item}@1.0"]
        k = MX.kelly(r1.values, M["MRATE"].reindex(r1.index).values)
        for key in tab.index:
            if key.split("@")[0] == item:
                for kk, v in k.items():
                    tab.loc[key, kk] = v
    tab["imprudent_gt_half_kelly"] = tab["L"] > tab["half_kelly"]
    T, ans = forward_and_answer(M, tab, rets, args.proc8, args.cma8, out)
    sens_info = {}
    for v in ("s1_unscaled", "s2_full_haircut"):
        _, Mv, rv, tv, iv = run_all(args, v, items=["P3", "P4", "P5", "P6a"], sens=False)
        sens_info[v] = iv
        Tv, av = forward_and_answer(Mv, tv, rv, args.proc8, args.cma8, out / v) if (out / v).mkdir(exist_ok=True) is None else (None, None)
    json.dump({"primary": info, **sens_info, "paths": args.paths, "seed": R8.SEED}, open(out / "trend_input_info.json", "w"),
              indent=1, default=str)
    print(ans.to_string())


if __name__ == "__main__":
    main()
