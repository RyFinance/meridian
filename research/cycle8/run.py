"""Cycle 8 runner: every menu item x leverage (FRAMEWORK §3-§6, ADDENDUM_1). One run, outputs to --out.

usage: python -m research.cycle8.run --proc <snapshot proc dir> --out reports/cycle8_max_return/out
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.cycle8.engine import core, letf, metrics as MX, sleeves as SL
from research.cycle8.engine.menu import ANSWER_ITEMS, COST, COST_OVERLAY, MENU, RP_SLEEVES, eq_col, levels

W_MAIN_START = "1971-02"
W_COMMON = ("1988-01", "2026-05")
SEED = 20260928
TOL = (0.25, 0.35, 0.50)


# ----------------------------------------------------------------------------- daily panel
def month_key(idx):
    return pd.DatetimeIndex(idx).to_period("M").to_timestamp("M")


def daily_proxies(d: dict, days: pd.DatetimeIndex) -> pd.DataFrame:
    """Daily proxy returns per sleeve on the Ken French trading calendar (NaN where no proxy)."""
    eqd = d["eq_daily"].reindex(days)
    fx = d["fx_daily"]["USDCAD"].reindex(days.union(d["fx_daily"].index)).ffill().reindex(days)
    fxr = fx / fx.shift(1) - 1
    comp_cad = pd.DataFrame({"US": (1 + eqd["US_usd"]) * (1 + fxr) - 1, "CA": eqd["CA_cad"],
                             "DXNA": (1 + eqd["DXNA_usd"]) * (1 + fxr) - 1, "EM": (1 + eqd["EM_usd"]) * (1 + fxr) - 1})
    comp_h = pd.DataFrame({"US": eqd["US_usd"], "CA": eqd["CA_cad"], "DXNA": eqd["DXNA_usd"], "EM": eqd["EM_usd"]})
    w = pd.Series(SL.EQ_W)

    def blend(c, wts):
        av = c.notna()
        ww = av.mul(wts, axis=1)
        tot = ww.sum(1)
        return (c.fillna(0) * ww).sum(1) / tot.where(tot > 0)

    bd = d["bond_daily"].reindex(days)
    gd = d["gold_daily"]["gold_usd_gcf"].reindex(days.union(d["gold_daily"].index)).ffill(limit=3).reindex(days)
    out = pd.DataFrame(index=days)
    out["EQ_G"] = blend(comp_cad, w)
    out["EQ_GH"] = blend(comp_h, w)
    out["BOND"] = blend(pd.DataFrame({"CA": bd["CA10_ret"], "US": bd["US10_ret"]}), pd.Series({"CA": 0.6, "US": 0.4}))
    g = (gd / gd.shift(1)) * (1 + fxr) - 1
    out["GOLD"] = g.where(gd.index >= pd.Timestamp("2000-09-01"))
    out["TREND"] = np.nan
    out["CASH"] = np.nan
    out["X_TREND"] = np.nan
    out["X_BOND"] = out["BOND"]
    return out


def spread_month(proxy: pd.Series, total: float, additive=False) -> np.ndarray:
    """Daily path for one month that compounds (or sums, for overlays) exactly to `total`."""
    n = len(proxy)
    if not np.isfinite(total):
        return np.full(n, np.nan)
    p = proxy.values
    if additive:
        if np.isnan(p).any():
            return np.full(n, total / n)
        return p + (total - p.sum()) / n
    if np.isnan(p).any() or (p <= -1).any():
        return np.full(n, (1 + total) ** (1 / n) - 1)
    lg = np.log1p(p)
    return np.expm1(lg + (np.log1p(total) - lg.sum()) / n)


def build_daily(M: pd.DataFrame, prox: pd.DataFrame, cols, start, end) -> pd.DataFrame:
    days = prox.loc[pd.Timestamp(start).to_period("M").start_time:pd.Timestamp(end) + pd.offsets.MonthEnd(0)].index
    mk = month_key(days)
    out = {}
    for c in cols:
        base = c.replace("_tfsa", "").replace("_margin", "")
        pc = prox[base] if base in prox else pd.Series(np.nan, index=prox.index)
        vals = np.empty(len(days))
        for m in np.unique(mk):
            sel = mk == m
            vals[sel] = spread_month(pc.loc[days[sel]], M.at[m, c], additive=c.startswith("X_"))
        out[c] = vals
    return pd.DataFrame(out, index=days)


# ----------------------------------------------------------------------------- items
def item_columns(item, L):
    spec = MENU[item]
    funded = spec["funded"]
    names = list(RP_SLEEVES) if funded == "RISK_PARITY" else list(funded)
    fcols = [eq_col(n, L) for n in names]
    ocols = list(spec["overlay"])
    return names, fcols, ocols


def rp_weights(M: pd.DataFrame, fcols) -> pd.DataFrame:
    vol = M[fcols].rolling(36, min_periods=36).std().shift(1)
    inv = 1 / vol
    return inv.div(inv.sum(1), axis=0)


def item_window(M, item, L, start=W_MAIN_START):
    names, fcols, ocols = item_columns(item, L)
    ok = M[fcols + ocols + ["MRATE", "CASH"]].notna().all(1)
    if MENU[item]["funded"] == "RISK_PARITY":
        ok &= rp_weights(M, fcols).notna().all(1)
    ok = ok.loc[start:]
    months = ok.index[ok]
    return months[0], months[-1]


def run_hist(M, prox, item, L, spread_extra=0.0, start=W_MAIN_START):
    names, fcols, ocols = item_columns(item, L)
    a, b = item_window(M, item, L, start)
    Mw = M.loc[a:b].copy()
    Mw["MRATE"] = Mw["MRATE"] + spread_extra / 12
    Dd = build_daily(Mw, prox, fcols + ocols, a, b)
    mk = month_key(Dd.index)
    nd = pd.Series(mk).map(pd.Series(mk).value_counts()).values
    carry = np.stack([Mw["MRATE"].reindex(mk).values / nd, Mw["CASH"].reindex(mk).values / nd], -1)[None]
    rebal = np.r_[True, mk[1:] != mk[:-1]]
    if MENU[item]["funded"] == "RISK_PARITY":
        w = rp_weights(M, fcols).loc[a:b].reindex(mk).values[None]
    else:
        w = np.array([MENU[item]["funded"][n] for n in names])
    o = np.array([MENU[item]["overlay"][c] for c in ocols]) if ocols else np.zeros(1)
    X = Dd[ocols].values[None] if ocols else np.zeros((1, len(Dd), 1))
    res = core.simulate(Dd[fcols].values[None], X, carry, w, o, L,
                        np.array([COST[n] for n in names]),
                        np.array([COST_OVERLAY[c] for c in ocols]) if ocols else np.zeros(1), rebal)
    wd = pd.Series(res["wealth"][0, 1:], index=Dd.index)
    wm = wd.groupby(mk).last()
    wm0 = pd.concat([pd.Series([1.0], index=[wm.index[0] - pd.offsets.MonthEnd(1)]), wm])
    r = (wm0 / wm0.shift(1) - 1).iloc[1:]
    r[wm0.shift(1).iloc[1:] <= 0] = 0.0
    daily_dd = MX.drawdowns(np.r_[1.0, wd.values]).max()
    return r, {"calls": int(res["calls"][0]), "ruined": bool(res["ruined"][0]), "maxdd_daily": daily_dd,
               "turnover_ann": res["turnover"][0] / (len(r) / 12)}


# ----------------------------------------------------------------------------- P7
def run_p7(d, M):
    eqd = d["eq_daily"]["US_usd"].dropna()
    bd = d["bond_daily"]["US20_ret"]
    rf = d["rf_usd_daily"]["rf_usd"]
    days = eqd.index[(eqd.index >= "1971-01-01") & (eqd.index <= "2026-08-31")]
    fx = d["fx_daily"]["USDCAD"].reindex(days.union(d["fx_daily"].index)).ffill().reindex(days)
    fxr = (fx / fx.shift(1) - 1).fillna(0.0)
    b = bd.reindex(days).fillna(0.0)          # bond market holidays: zero return
    out = {}
    for tag, (e, t) in {"P7-2x": ("SSO", "UBT"), "P7-3x": ("UPRO", "TMF")}.items():
        ke, se, ee, _ = letf.SPEC[e]
        kt, st, et, _ = letf.SPEC[t]
        re_ = letf.letf_daily(eqd.reindex(days), rf, ke, se, ee)
        rt_ = letf.letf_daily(b, rf, kt, st, et)
        R = np.stack([((1 + re_) * (1 + fxr) - 1).values, ((1 + rt_) * (1 + fxr) - 1).values], -1)[None]
        mk = month_key(days)
        rebal = np.r_[True, mk[1:] != mk[:-1]]
        carry = np.zeros((1, len(days), 2))
        res = core.simulate(R, np.zeros((1, len(days), 1)), carry, np.array([0.6, 0.4]), np.zeros(1), 1.0,
                            np.array([0.0015, 0.0015]), np.zeros(1), rebal)
        wd = pd.Series(res["wealth"][0, 1:], index=days)
        wm = wd.groupby(mk).last()
        wm0 = pd.concat([pd.Series([1.0], index=[wm.index[0] - pd.offsets.MonthEnd(1)]), wm])
        r = (wm0 / wm0.shift(1) - 1).iloc[1:].loc[W_MAIN_START:]
        out[tag] = (r, {"calls": 0, "ruined": bool(res["ruined"][0]),
                        "maxdd_daily": MX.drawdowns(np.r_[1.0, wd.values]).max(), "turnover_ann": np.nan},
                    {"eq_letf": re_, "tsy_letf": rt_})
    return out


# ----------------------------------------------------------------------------- bootstrap
def bootstrap_item(M, item, L, P=10000, mean_block=24, T_eval=360, burn=36, seed=SEED, p7=None, spread_extra=0.0):
    if item.startswith("P7"):
        r = p7.loc[W_MAIN_START:].dropna()
        cols = pd.DataFrame({"R": r, "MRATE": M["MRATE"].reindex(r.index), "CASH": M["CASH"].reindex(r.index)})
        fcols, ocols, names = ["R"], [], ["R"]
        a, b = r.index[0], r.index[-1]
        W = cols
    else:
        names, fcols, ocols = item_columns(item, L)
        a, b = item_window(M, item, L)
        start = M.index[M.index.get_loc(a) - burn] if MENU[item]["funded"] == "RISK_PARITY" else a
        W = M.loc[start:b, fcols + ocols + ["MRATE", "CASH"]].copy()
        W["MRATE"] += spread_extra / 12
    arr = W.values
    n = len(arr)
    rng = np.random.default_rng(seed)
    T = burn + T_eval
    idx = MX.stationary_indices(n, T, P, mean_block, rng)
    Z = arr[idx]                                           # (P, T, k)
    k_f, k_o = len(fcols), len(ocols)
    Rf = Z[:, burn:, :k_f]
    X = Z[:, burn:, k_f:k_f + k_o] if k_o else np.zeros((P, T_eval, 1))
    carry = np.stack([Z[:, burn:, -2], Z[:, burn:, -1]], -1)
    if not item.startswith("P7") and MENU[item]["funded"] == "RISK_PARITY":
        allR = Z[:, :, :k_f]
        cs = np.cumsum(np.concatenate([np.zeros((P, 1, k_f)), allR], 1), 1)
        cs2 = np.cumsum(np.concatenate([np.zeros((P, 1, k_f)), allR ** 2], 1), 1)
        t = np.arange(burn, T)
        s1 = cs[:, t, :] - cs[:, t - 36, :]
        s2 = cs2[:, t, :] - cs2[:, t - 36, :]
        var = (s2 - s1 ** 2 / 36) / 35
        inv = 1 / np.sqrt(np.maximum(var, 1e-12))
        w = inv / inv.sum(2, keepdims=True)
        cf = np.array([COST[n] for n in names])
    elif item.startswith("P7"):
        w = np.array([1.0])
        cf = np.zeros(1)
    else:
        w = np.array([MENU[item]["funded"][n] for n in names])
        cf = np.array([COST[n] for n in names])
    o = np.array([MENU[item]["overlay"][c] for c in ocols]) if ocols else np.zeros(1)
    co = np.array([COST_OVERLAY[c] for c in ocols]) if ocols else np.zeros(1)
    res = core.simulate(Rf, X, carry, w, o, L if not item.startswith("P7") else 1.0, cf, co, np.ones(T_eval, bool))
    out = {"boot_window": f"{a:%Y-%m}..{b:%Y-%m}", "boot_n": n}
    for H in (120, 240, 360):
        dd = core.max_drawdown(res["wealth"][:, :H + 1])
        for tol in TOL:
            out[f"p_dd{int(tol * 100)}_{H // 12}y"] = float((dd > tol).mean())
        out[f"p_ruin_{H // 12}y"] = float((res["wealth"][:, H] <= 0).mean())
    out["calls_mean_30y"] = float(res["calls"].mean())
    return out


# ----------------------------------------------------------------------------- W_US1926 (ADDENDUM_1 §7)
def us1926(d):
    eq = d["eq_monthly"]["US_usd"]
    rt = d["rates_monthly"]
    idx = eq.index
    rf = rt["rf_usd_ret"].reindex(idx)
    Mu = pd.DataFrame(index=idx)
    Mu["EQ_G_tfsa"] = eq - SL.FEE["EQ"] / 12
    Mu["EQ_G_margin"] = Mu["EQ_G_tfsa"]
    Mu["BOND"] = d["bond_monthly"]["US10_ret"].reindex(idx) - SL.FEE["BOND"] / 12
    Mu["CASH"] = rf
    Mu["MRATE"] = rf + SL.MARGIN_SPREAD / 12
    days = d["eq_daily"]["US_usd"].dropna().index
    days = days[days <= "2026-08-31"]
    px = pd.DataFrame(index=days)
    px["EQ_G"] = d["eq_daily"]["US_usd"].reindex(days)
    px["BOND"] = d["bond_daily"]["US10_ret"].reindex(days)
    px["CASH"] = np.nan
    rets, extra = {}, {}
    for item in ("P1u", "P2", "P3"):
        for L in levels(item):
            r, info = run_hist(Mu, px, item, L, start="1926-07")
            rets[f"US_{item}@{L}"], extra[f"US_{item}@{L}"] = r, info
    return Mu, rets, extra


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proc", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--paths", type=int, default=10000)
    ap.add_argument("--membership", default=None, help="snapshot membership artifact (recorded only)")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    proc = Path(args.proc)
    d = SL.load(proc)
    d["rf_usd_daily"] = pd.read_parquet(proc / "rf_usd_daily.parquet")
    M = SL.monthly_sleeves(d)
    M.to_parquet(out / "sleeves_monthly.parquet")
    cpi = d["cpi_ca_monthly"]["CPI_CA"]
    days = d["eq_daily"]["US_usd"].dropna().index
    days = days[(days >= "1971-01-01") & (days <= "2026-08-31")]
    prox = daily_proxies(d, days)

    rets, extra = {}, {}
    for item in MENU:
        for L in levels(item):
            key = f"{item}@{L}"
            r, info = run_hist(M, prox, item, L)
            rets[key], extra[key] = r, info
            print(key, f"{r.index[0]:%Y-%m}..{r.index[-1]:%Y-%m}", flush=True)
    p7 = run_p7(d, M)
    for tag, (r, info, _) in p7.items():
        rets[f"{tag}@1.0"], extra[f"{tag}@1.0"] = r, info
    pd.DataFrame(rets).to_parquet(out / "item_returns_monthly.parquet")

    # --- sensitivity: margin spread +3.0% instead of +1.5% (historical only for L > 1)
    sens = {}
    for item in ANSWER_ITEMS:
        for L in levels(item):
            if L > 1:
                r, info = run_hist(M, prox, item, L, spread_extra=0.015)
                sens[f"{item}@{L}"] = (r, info)

    # --- metrics
    rf = M["CASH"]
    rows, crisis = [], []
    p3 = rets["P3@1.0"]
    for key, r in rets.items():
        s = MX.summary(r, rf, cpi)
        s.update(extra[key])
        s["key"] = key
        s["item"], s["L"] = key.split("@")[0], float(key.split("@")[1])
        s["hurdle_p3_sharpe"] = MX.summary(p3.loc[r.index[0]:r.index[-1]], rf, sharpe_ci=False)["sharpe"]
        rc = r.loc[W_COMMON[0]:W_COMMON[1]]
        if len(rc) and rc.index[0] == pd.Timestamp(W_COMMON[0]) + pd.offsets.MonthEnd(0):
            sc = MX.summary(rc, rf, cpi, sharpe_ci=False)
            s.update({f"common_{k}": sc[k] for k in ("cagr", "cagr_real", "vol", "sharpe", "maxdd", "worst12")})
        rows.append(s)
        for name, (cr, cdd) in MX.crisis_table(r).items():
            crisis.append({"key": key, "crisis": name, "cum_return": cr, "max_dd": cdd})
    for key, (r, info) in sens.items():
        s = MX.summary(r, rf, cpi, sharpe_ci=False)
        rows_s = {"key": key, "sens_margin3_cagr": s["cagr"], "sens_margin3_sharpe": s["sharpe"],
                  "sens_margin3_maxdd": s["maxdd"], "sens_margin3_calls": info["calls"]}
        next(x for x in rows if x["key"] == key).update(rows_s)
    tab = pd.DataFrame(rows).set_index("key")

    # --- bootstrap + Kelly
    for key in tab.index:
        item, L = key.split("@")[0], float(key.split("@")[1])
        p7r = rets[key] if item.startswith("P7") else None
        b24 = bootstrap_item(M, item, L, P=args.paths, mean_block=24, p7=p7r)
        b12 = bootstrap_item(M, item, L, P=args.paths, mean_block=12, p7=p7r)
        for k, v in b24.items():
            tab.loc[key, k] = v
        for tol in TOL:
            tab.loc[key, f"b12_p_dd{int(tol * 100)}_20y"] = b12[f"p_dd{int(tol * 100)}_20y"]
        if L > 1 and item in ANSWER_ITEMS:
            b3 = bootstrap_item(M, item, L, P=args.paths, mean_block=24, spread_extra=0.015)
            for tol in TOL:
                tab.loc[key, f"sens_margin3_p_dd{int(tol * 100)}_20y"] = b3[f"p_dd{int(tol * 100)}_20y"]
        print("boot", key, flush=True)
    for item in list(MENU) + ["P7-2x", "P7-3x"]:
        r1 = rets[f"{item}@1.0"]
        k = MX.kelly(r1.values, M["MRATE"].reindex(r1.index).values)
        for key in tab.index:
            if key.split("@")[0] == item:
                for kk, v in k.items():
                    tab.loc[key, kk] = v
    tab["imprudent_gt_half_kelly"] = tab["L"] > tab["half_kelly"]
    tab.to_csv(out / "item_table.csv")
    pd.DataFrame(crisis).to_csv(out / "crisis_table.csv", index=False)
    # P7 validation series
    pd.DataFrame({f"{t}_{k}": v for t, (_, _, s) in p7.items() for k, v in s.items()}).to_parquet(
        out / "p7_letf_daily_sim.parquet")
    # RP realised weights
    rp = rp_weights(M, [eq_col(n, 1.0) for n in RP_SLEEVES]).dropna()
    rp.to_csv(out / "p5_weights.csv")
    # --- supplementary US 1926+ (USD)
    Mu, ur, ue = us1926(d)
    urows, ucr = [], []
    for key, r in ur.items():
        s_ = MX.summary(r, Mu["CASH"], d["cpi_ca_monthly"]["CPI_US"].ffill())
        s_.update(ue[key])
        s_["key"] = key
        urows.append(s_)
        for name, (cr, cdd) in MX.crisis_table(r, {**MX.CRISES_US1926, **MX.CRISES}).items():
            ucr.append({"key": key, "crisis": name, "cum_return": cr, "max_dd": cdd})
    pd.DataFrame(urows).set_index("key").to_csv(out / "us1926_table.csv")
    pd.DataFrame(ucr).to_csv(out / "us1926_crisis.csv", index=False)
    pd.DataFrame(ur).to_parquet(out / "us1926_returns.parquet")
    json.dump({"W_MAIN_START": W_MAIN_START, "W_COMMON": W_COMMON, "paths": args.paths, "seed": SEED},
              open(out / "run_meta.json", "w"), indent=1)
    print("done")


if __name__ == "__main__":
    main()
