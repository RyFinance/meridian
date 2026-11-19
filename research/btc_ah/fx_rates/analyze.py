"""FX / Treasury futures overnight move -> US ETF / rate-sensitive stock open-to-close and first-hour rules.

Timeline per ET session D (prior session P):
  16:00 P  : futures = close of 15:00 bar; ETF = close of 15:30 bar (regular close).
  09:00 D  : decision. futures = close of 08:00 bar; ETF pre-market = close of 08:00 bar (prepost).
  09:30 D  : entry at ETF open (09:30 bar open). Exits: first hour = close of 09:30 bar (10:30 print);
             open->close = close of 15:30 bar (16:00).
Residual gap R = ETF pre-open move - beta * futures move, beta = expanding OLS on prior sessions only (min 40).
sigma_R = expanding std of prior R. z = R / sigma_R (prior-only).
Costs: ETF 2 bp per side. Worst-fill variant: buy at bar high, sell at bar low (and mirror for shorts).
Sealed holdout: nothing after 2026-08-10. Dev: D < 2025-06-01. Check: 2025-06-01 .. 2026-08-10.
"""
import numpy as np, pandas as pd, itertools, json
from pathlib import Path
H = Path(__file__).parent; C = H / "cache"
CUT = pd.Timestamp("2026-08-10").date()
SPLIT = pd.Timestamp("2025-06-01").date()
COST = 0.0002
NMIN = 40
SIGS = {"6E": "6E_F", "6J": "6J_F", "6B": "6B_F", "ZN": "ZN_F", "ZB": "ZB_F"}
PAIRS = [("6E", "FXE"), ("6E", "UUP"), ("6J", "FXY"), ("6B", "FXB"), ("ZN", "IEF"), ("ZB", "TLT"),
         ("ZB", "TMF"), ("ZB", "TBT"), ("ZB", "XLU"), ("ZB", "XHB"), ("ZB", "ITB"), ("ZB", "KRE")]


def load(name):
    d = pd.read_parquet(C / f"{name}_1h.parquet")
    d = d[d.index.date <= CUT][["open", "high", "low", "close"]].astype(float).dropna()
    key = d.index.strftime("%Y-%m-%d %H:%M")
    return dict(zip(key, zip(d.open, d.high, d.low, d.close)))


def px(m, date, hhs, field):
    for hh in hhs:
        v = m.get(f"{date} {hh}")
        if v is not None:
            return v[field]
    return np.nan


def bar(m, date, hh):
    return m.get(f"{date} {hh}")


def build(sig, tgt, maps, days):
    Sm, Tm = maps[SIGS[sig]], maps[tgt]
    rows = []
    for i in range(1, len(days)):
        D, P = days[i], days[i - 1]
        f16 = px(Sm, P, ["15:00", "14:00"], 3)
        f09 = px(Sm, D, ["08:00", "07:00"], 3)
        e16 = px(Tm, P, ["15:30"], 3)
        e09 = px(Tm, D, ["08:00", "07:00"], 3)
        b = bar(Tm, D, "09:30")
        bc = bar(Tm, D, "15:30")
        if any(np.isnan(x) for x in [f16, f09, e16, e09]) or b is None or bc is None:
            continue
        rows.append(dict(D=D, rS=np.log(f09 / f16), G=np.log(e09 / e16),
                         o=b[0], h=b[1], l=b[2], c1=b[3],
                         cl=bc[3], hC=bc[1], lC=bc[2], gap=np.log(b[0] / e09)))
    return pd.DataFrame(rows)


def add_resid(df):
    n = len(df); beta = np.full(n, np.nan); sig = np.full(n, np.nan)
    R = np.full(n, np.nan)
    r = df.rS.values; g = df.G.values
    for i in range(n):
        if i >= NMIN:
            rr, gg = r[:i], g[:i]
            v = np.var(rr, ddof=1)
            beta[i] = np.cov(rr, gg, ddof=1)[0, 1] / v if v > 0 else np.nan
        if not np.isnan(beta[i]):
            R[i] = g[i] - beta[i] * r[i]
        if i >= NMIN and np.sum(~np.isnan(R[:i])) >= NMIN:
            sig[i] = np.nanstd(R[:i], ddof=1)
    df["beta"] = beta; df["R"] = R; df["sigR"] = sig; df["z"] = df.R / df.sigR
    return df


def ret(dirn, entry, exit_, worst=None):
    """simple return net of 2 bp per side. worst: (entry_worst, exit_worst)."""
    if worst is None:
        return dirn * (exit_ / entry - 1) - 2 * COST
    ew, xw = worst
    if dirn > 0:
        return xw / ew - 1 - 2 * COST
    return -(xw / ew - 1) - 2 * COST


def trades(df, dirn_sign, horizon, k, worst=False):
    """one row per session. dirn_sign: +1 follow residual, -1 fade residual."""
    d = df.dropna(subset=["z"]).copy()
    d = d[np.abs(d.z) >= k] if k > 0 else d
    d = d[d.R != 0]
    dirn = dirn_sign * np.sign(d.R)
    out = []
    for idx, row in d.iterrows():
        s = dirn.loc[idx]
        if horizon == "H1":
            x, xw_l, xw_s = row.c1, row.l, row.h
        else:
            x, xw_l, xw_s = row.cl, row.lC, row.hC
        if not worst:
            out.append(ret(s, row.o, x))
        else:
            if s > 0:
                out.append(ret(1, None, None, worst=(row.h, xw_l)))
            else:
                out.append(ret(-1, None, None, worst=(row.l, xw_s)))
    return pd.DataFrame({"D": d.D.values, "dirn": dirn.values, "net": out})


def stats(x):
    x = np.asarray(x, float)
    n = len(x)
    if n < 2:
        return dict(n=n, win=np.nan, mean=np.nan, t=np.nan, avgw=np.nan, avgl=np.nan)
    sd = x.std(ddof=1)
    return dict(n=n, win=(x > 0).mean(), mean=x.mean(), t=x.mean() / (sd / np.sqrt(n)) if sd > 0 else np.nan,
                avgw=x[x > 0].mean() if (x > 0).any() else np.nan,
                avgl=x[x <= 0].mean() if (x <= 0).any() else np.nan)


def ols(x, y):
    X = np.column_stack([np.ones(len(x)), x])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ b
    s2 = res @ res / (len(y) - 2)
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    return b[1], b[1] / se[1]


def main():
    maps = {k: load(k) for k in set(list(SIGS.values()) + [t for _, t in PAIRS])}
    base = maps["FXE_1h"] if False else None
    days_all = sorted({k[:10] for k in maps["FXE"] if k.endswith("09:30")}) if False else None
    # sessions = dates with a 09:30 bar on the ETF side
    keys = [k for k in maps["FXE"] if k.endswith("09:30")]
    days = sorted({k[:10] for k in keys})
    days = [pd.Timestamp(d).date() for d in days]
    days = [d.strftime("%Y-%m-%d") for d in days]
    pairs_data = {}
    for sig, tgt in PAIRS:
        df = build(sig, tgt, maps, days)
        df = add_resid(df)
        df["D"] = pd.to_datetime(df.D).dt.date
        pairs_data[(sig, tgt)] = df
        print(f"{sig}->{tgt}: sessions {len(df)} first {df.D.min()} last {df.D.max()}", flush=True)
    # diagnostics: pass-through (pre-open beta) and gap/drift after open, by pair and sample
    diag = []
    for (sig, tgt), df in pairs_data.items():
        for lab, m in [("dev", df.D < SPLIT), ("check", (df.D >= SPLIT))]:
            d = df[m].dropna(subset=["beta"])
            if len(d) < 30:
                continue
            b_pre, t_pre = ols(d.rS.values, d.G.values)
            b_gap, t_gap = ols(d.R.values, d.gap.values)
            b_oc, t_oc = ols(d.R.values, np.log(d.cl / d.o).values)
            diag.append(dict(pair=f"{sig}->{tgt}", sample=lab, n=len(d), beta_preopen=b_pre, t_beta=t_pre,
                             gap_on_R=b_gap, t_gap=t_gap, drift_open_close_on_R=b_oc, t_drift=t_oc))
    dg = pd.DataFrame(diag)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print("\nDIAGNOSTICS (slopes; 1.0 = full pass-through, >0 drift = continuation)")
    print(dg.round(3).to_string(index=False))
    dg.to_csv(H / "diagnostics.csv", index=False)

    # rule grid: 12 pairs x {follow, fade} x {H1, OC} x k in {0, 0.5, 1.0}  = 144 variants
    rows = []
    trade_store = {}
    for (sig, tgt), df in pairs_data.items():
        for fam, sgn in [("follow", 1), ("fade", -1)]:
            for hz in ["H1", "OC"]:
                for k in [0.0, 0.5, 1.0]:
                    tr = trades(df, sgn, hz, k)
                    flip = trades(df, -sgn, hz, k)
                    name = f"{sig}->{tgt}|{fam}|{hz}|k{k}"
                    trade_store[name] = (tr, flip)
                    for lab, m in [("dev", tr.D < SPLIT), ("check", tr.D >= SPLIT)]:
                        s = stats(tr.net[m]); f = stats(flip.net[flip.D.map(lambda d: (d < SPLIT) if lab == "dev" else (d >= SPLIT))])
                        rows.append(dict(variant=name, sample=lab, **{f"{a}": b for a, b in s.items()},
                                         flip_mean=f["mean"], flip_t=f["t"]))
    res = pd.DataFrame(rows)
    res.to_pickle(H / "grid_results.pkl")
    pd.to_pickle(trade_store, H / "trade_store.pkl")
    dev = res[res["sample"] == "dev"].set_index("variant")
    chk = res[res["sample"] == "check"].set_index("variant")
    print(f"\nVARIANTS TESTED: {len(dev)}")
    dev_ok = dev[(dev.n >= 50)].sort_values("t", ascending=False)
    print(f"dev variants with n>=50 and dev t>2: {(dev_ok.t > 2).sum()}; dev t>3.0: {(dev_ok.t > 3).sum()}")
    print("\nTOP 10 DEV (ranked by dev net t):")
    cols = ["n", "win", "mean", "t", "flip_mean", "flip_t"]
    top_dev = dev_ok.head(10)[cols]
    print(top_dev.round(4).to_string())
    top3 = list(dev_ok.index[:3])
    print("\nTOP 3 DEV -> CHECK:")
    print(pd.concat([dev.loc[top3, cols].add_prefix("dev_"), chk.loc[top3, cols].add_prefix("chk_")], axis=1).round(4).to_string())
    print("\nCHECK-ONLY ranking of the same 144 (look at chk for reference, not selection):")
    print(chk[chk.n >= 30].sort_values("t", ascending=False).head(5)[cols].round(4).to_string())
    json.dump({"top3": top3, "n_variants": int(len(dev))}, open(H / "top3.json", "w"))
    # per-year and worst-fill for top 3
    for name in top3:
        tr, flip = trade_store[name]
        tr = tr.copy(); tr["yr"] = pd.to_datetime(tr.D).dt.year
        print(f"\n{name} per-year net mean:", tr.groupby("yr").net.agg(["count", "mean"]).round(4).to_dict())
        sig, tgt = name.split("|")[0].split("->")
        df = pairs_data[(sig, tgt)]
        wf = trades(df, 1 if "follow" in name else -1, "H1" if "H1" in name else "OC", float(name.split("k")[-1]), worst=True)
        print(f"  worst-fill net: n {len(wf)} mean {wf.net.mean():.4f} t {stats(wf.net)['t']:.2f}")


if __name__ == "__main__":
    main()
