"""Clean grid (replaces the pre-market residual design, which is invalid: every yfinance pre-market bar has zero
volume, so the 09:00 ETF price is a stale print).

Family A' (residual gap, the brief's rule): all regular-hours prints.
  Overnight futures move r_S = ln(fut 08:00-bar close / fut 15:00-bar close) (known at 09:00).
  ETF gap G = ln(ETF 09:30 open / ETF 15:30-bar close (16:00)).
  Residual R = G - beta * r_S, beta = expanding OLS on prior sessions (min 40); z = R / expanding sd(R).
  Decision at the 09:30-bar close (= 10:30 print), entry at the 10:30 bar open.
  H1 exit = close of 10:30 bar (11:30 print). OC exit = close of 15:30 bar (16:00).
  Follow = trade sign(R); fade = -sign(R). Threshold k on |z| in {0, 0.5, 1.0}.
Family C (sensitivity, no ETF residual): trade sign(r_S) on z_S, entry at 09:30 open (decision at 09:00),
  exit H1 = close of 09:30 bar, or OC.
Costs: 2 bp per side (ETF, regular hours). Worst fill: buy at bar high, sell at bar low (mirror for shorts).
Dev: session date < 2025-06-01. Check: 2025-06-01 .. 2026-08-10. Nothing after 2026-08-10 is loaded.
"""
import numpy as np, pandas as pd, json
from pathlib import Path
import analyze as A

H = Path(__file__).parent
COST = 0.0002


def load_all():
    names = ["6E_F", "6J_F", "6B_F", "ZN_F", "ZB_F"] + sorted({t for _, t in A.PAIRS})
    return {k: A.load(k) for k in names}


def sessions(maps):
    keys = [k for k in maps["FXE"] if k.endswith("09:30")]
    return sorted({pd.Timestamp(k[:10]).strftime("%Y-%m-%d") for k in keys})


def build_clean(sig, tgt, maps, days):
    Sm, Tm = maps[A.SIGS[sig]], maps[tgt]
    rows = []
    for i in range(1, len(days)):
        D, P = days[i], days[i - 1]
        f16 = A.px(Sm, P, ["15:00", "14:00"], 3)
        f09 = A.px(Sm, D, ["08:00", "07:00"], 3)
        c16 = A.px(Tm, P, ["15:30"], 3)
        b930, b1030, bc = A.bar(Tm, D, "09:30"), A.bar(Tm, D, "10:30"), A.bar(Tm, D, "15:30")
        if any(np.isnan(x) for x in [f16, f09, c16]) or None in (b930, b1030, bc):
            continue
        rows.append(dict(D=pd.Timestamp(D).date(), rS=np.log(f09 / f16), G=np.log(b930[0] / c16),
                         # family A' entry at 10:30 open
                         a_o=b1030[0], a_h=b1030[1], a_l=b1030[2], a_c=b1030[3],
                         cl=bc[3], lC=bc[2], hC=bc[1],
                         # family C entry at 09:30 open
                         c_o=b930[0], c_h=b930[1], c_l=b930[2], c_c=b930[3]))
    return pd.DataFrame(rows)


def expanding_resid(df):
    n = len(df); r = df.rS.values; g = df.G.values
    beta = np.full(n, np.nan); R = np.full(n, np.nan); sigR = np.full(n, np.nan)
    for i in range(n):
        if i >= A.NMIN:
            v = np.var(r[:i], ddof=1)
            beta[i] = np.cov(r[:i], g[:i], ddof=1)[0, 1] / v if v > 0 else np.nan
        if not np.isnan(beta[i]):
            R[i] = g[i] - beta[i] * r[i]
        if i >= A.NMIN and np.sum(~np.isnan(R[:i])) >= A.NMIN:
            sigR[i] = np.nanstd(R[:i], ddof=1)
    df["beta"] = beta; df["R"] = R; df["sigR"] = sigR; df["z"] = df.R / df.sigR
    # expanding z-score of raw futures move for family C
    sig_r = np.full(n, np.nan)
    for i in range(A.NMIN, n):
        sig_r[i] = np.std(r[:i], ddof=1)
    df["zS"] = df.rS / sig_r
    return df


def trade_frame(df, fam, sgn, hz, k, worst=False):
    d = df.dropna(subset=["z", "zS"]).copy()
    sig_col = "z" if fam == "A" else "zS"
    d = d[np.abs(d[sig_col]) >= k] if k > 0 else d
    base = d.R if fam == "A" else d.rS
    d = d[base != 0]
    dirn = sgn * np.sign(base.loc[d.index].values)
    if fam == "A":
        entry, eh, el = d.a_o.values, d.a_h.values, d.a_l.values
        if hz == "H1":
            ex, exw_long, exw_short = d.a_c.values, d.a_l.values, d.a_h.values
        else:
            ex, exw_long, exw_short = d.cl.values, d.lC.values, d.hC.values
    else:
        entry, eh, el = d.c_o.values, d.c_h.values, d.c_l.values
        if hz == "H1":
            ex, exw_long, exw_short = d.c_c.values, d.c_l.values, d.c_h.values
        else:
            ex, exw_long, exw_short = d.cl.values, d.lC.values, d.hC.values
    if not worst:
        net = dirn * (ex / entry - 1) - 2 * COST
    else:
        net = np.where(dirn > 0, exw_long / eh - 1, -(exw_short / el - 1)) - 2 * COST
    return pd.DataFrame({"D": d.D.values, "dirn": dirn, "net": net})


def main():
    maps = load_all()
    days = sessions(maps)
    data = {}
    for sig, tgt in A.PAIRS:
        df = expanding_resid(build_clean(sig, tgt, maps, days))
        data[(sig, tgt)] = df
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)

    # diagnostics on regular-hours prints only
    diag = []
    for (sig, tgt), df in data.items():
        for lab, m in [("dev", df.D < A.SPLIT), ("check", df.D >= A.SPLIT)]:
            d = df[m].dropna(subset=["beta"])
            if len(d) < 30:
                continue
            b_pre, t_pre = A.ols(d.rS.values, d.G.values)
            b_cont, t_cont = A.ols(d.R.values, np.log(d.cl / d.a_o).values)
            b_1h, t_1h = A.ols(d.R.values, np.log(d.a_c / d.a_o).values)
            diag.append(dict(pair=f"{sig}->{tgt}", sample=lab, n=len(d), beta_open_gap=b_pre, t_beta=t_pre,
                             post1030_drift_on_R=b_cont, t_drift=t_cont, first_hour_after1030_on_R=b_1h, t_1h=t_1h))
    dg = pd.DataFrame(diag)
    print("DIAGNOSTICS (regular hours): beta_open_gap = overnight ETF gap on futures move (1.0 = full pass-through);"
          " drift = post-10:30 move on residual (>0 continuation, <0 reversal)")
    print(dg.round(3).to_string(index=False))
    dg.to_csv(H / "diagnostics_clean.csv", index=False)

    rows, store = [], {}
    for fam in ["A", "C"]:
        for (sig, tgt), df in data.items():
            for sgn, dname in [(1, "follow"), (-1, "fade")]:
                for hz in ["H1", "OC"]:
                    for k in [0.0, 0.5, 1.0]:
                        name = f"{fam}:{sig}->{tgt}|{dname}|{hz}|k{k}"
                        tr = trade_frame(df, fam, sgn, hz, k)
                        fl = trade_frame(df, fam, -sgn, hz, k)
                        store[name] = (tr, fl)
                        for lab, m in [("dev", tr.D < A.SPLIT), ("check", tr.D >= A.SPLIT)]:
                            s = A.stats(tr.net[m])
                            fm = (fl.D < A.SPLIT) if lab == "dev" else (fl.D >= A.SPLIT)
                            f = A.stats(fl.net[fm])
                            rows.append(dict(variant=name, fam=fam, sample=lab, **s,
                                             flip_mean=f["mean"], flip_t=f["t"]))
    res = pd.DataFrame(rows)
    res.to_pickle(H / "clean_grid.pkl")
    pd.to_pickle(store, H / "clean_store.pkl")
    cols = ["n", "win", "mean", "t", "avgw", "avgl", "flip_mean", "flip_t"]
    for fam in ["A", "C"]:
        dev = res[(res["sample"] == "dev") & (res.fam == fam)].set_index("variant")
        chk = res[(res["sample"] == "check") & (res.fam == fam)].set_index("variant")
        ok = dev[dev.n >= 50].sort_values("t", ascending=False)
        print(f"\n=== family {fam}: variants {len(dev)}; dev n>=50 with t>2: {(ok.t > 2).sum()}; "
              f"dev max t {ok.t.max():.2f}; dev t>3: {(ok.t > 3).sum()}")
        print("TOP 5 DEV:")
        print(ok.head(5)[cols].round(4).to_string())
        top3 = list(ok.index[:3])
        print("TOP 3 DEV -> CHECK:")
        print(pd.concat([dev.loc[top3, ["n", "mean", "t", "flip_mean", "flip_t"]].add_prefix("dev_"),
                         chk.loc[top3, ["n", "win", "mean", "t", "flip_mean", "flip_t"]].add_prefix("chk_")],
                        axis=1).round(4).to_string())
        for name in top3:
            tr, fl = store[name]
            t2 = tr.copy(); t2["yr"] = pd.to_datetime(t2.D).dt.year
            per = t2.groupby("yr").net.agg(["count", "mean"]).round(4)
            wf = trade_frame(data[tuple(name.split(":")[1].split("|")[0].split("->"))], fam,
                             1 if "|follow|" in name else -1, "H1" if "|H1|" in name else "OC",
                             float(name.split("|k")[-1]), worst=True)
            print(f"  {name} per-year:\n{per.to_string()}")
            print(f"  worst-fill: n {len(wf)} mean {wf.net.mean():.4f} t {A.stats(wf.net)['t']:.2f}")
        if fam == "A":
            json.dump({"top3": top3, "variants": int(len(dev))}, open(H / "top3_clean.json", "w"))
    print(f"\nTOTAL valid variants: {res.variant.nunique()}")


if __name__ == "__main__":
    main()
