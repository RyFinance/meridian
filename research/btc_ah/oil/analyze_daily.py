"""Daily long-history version: USO/peer open and close vs CL/BZ/NG daily move.
Timing-safe: signal x_P = ln(oil close P / oil close prior bar), CL daily close assumed = 14:30 ET settle (<16:00 P).
Trades: OD = equity open(D)->close(D); GAP = equity close(P)->open(D). Entries are at/after the signal time.
Daily residual rule is NOT run (gap is only known at the open, so it cannot be a pre-entry signal).
Dev <= 2022-06-30; check 2022-07-01..2026-08-10.
"""
import numpy as np, pandas as pd, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from analyze import OIL_OF, COST_SIDE_BP, KS, stats, DEV_END_D, C, OUT
pd.set_option("display.width", 220); pd.set_option("display.max_rows", 500)
def ld(n):
    return pd.read_parquet(C / f"d1_{n}.parquet")
oil = {o: ld(o) for o in ["CL_F","BZ_F","NG_F"]}
def oil_x(o):
    c = oil[o]["Close"]; c = c[c > 0]
    r = np.log(c / c.shift(1))
    r = r[r.abs() <= 0.25]          # drop roll / negative-price artifacts (documented)
    return r                        # indexed by session date; value known at that session close
out = []
for ins, o in OIL_OF.items():
    e = ld(ins)
    xs = oil_x(o)
    dates = e.index
    P_close = e["Close"].shift(1); P_date = pd.Series(dates, index=dates).shift(1)
    # signal for a trade on D = oil move through the previous equity session P (last oil bar <= P)
    xsig = pd.Series(xs.reindex(pd.DatetimeIndex(P_date.dropna().values), method="ffill").values,
                     index=P_date.dropna().index).reindex(dates)
    d = pd.DataFrame({"x": xsig, "o": e["Open"], "c": e["Close"], "pc": P_close}).dropna()
    d["gap"] = np.log(d["o"] / d["pc"])
    d = d[d.index >= pd.Timestamp("2000-01-01")]
    d["dev"] = d.index <= DEV_END_D
    d["year"] = d.index.year
    d["oil"] = o; d["inst"] = ins
    # trades returns (simple)
    d["ret_od"] = d["c"] / d["o"] - 1
    d["ret_gap"] = d["o"] / d["pc"] - 1
    rc = 2 * COST_SIDE_BP[ins] / 1e4
    sx = d.loc[d.dev, "x"].std()
    for k in KS:
        for hname, ret in [("OD", d["ret_od"]), ("GAP", d["ret_gap"])]:
            sel = (d["x"].abs() >= k * sx) if k > 0 else pd.Series(True, index=d.index)
            side = np.sign(d["x"]) * sel
            for flip in [1, -1]:
                s = side * flip; m = s != 0
                g = d[m].copy(); g["side"] = s[m]
                g["gross"] = g["side"] * ret[m]; g["net"] = g["gross"] - rc
                g["rule"] = f"D_{hname}_k{k}"; g["kind"] = "follow" if flip == 1 else "flip"
                g["variant"] = f"D_{hname}|k={k}|{ins}|{'follow' if flip==1 else 'FLIP'}"
                g["date"] = g.index
                out.append(g.reset_index(drop=True))
TR = pd.concat(out, ignore_index=True)
TR.to_parquet(OUT / "trades_daily.parquet")
res = []
fol = TR[TR.kind == "follow"]
for (rule, ins), g in fol.groupby(["rule","inst"]):
    for part, gg in [("dev", g[g.dev]), ("check", g[~g.dev])]:
        s = stats(gg, "net"); s.pop("per_year", None)
        res.append(dict(rule=rule, inst=ins, part=part, **s))
R = pd.DataFrame(res); R.to_csv(OUT / "results_daily.csv", index=False)
print("daily follow variants:", fol.variant.nunique(), "sessions:", TR.date.min().date(), TR.date.max().date())
D = R[R.part=="dev"].set_index(["rule","inst"]); Cc = R[R.part=="check"].set_index(["rule","inst"])
M = D[["n","mean_bp","t"]].join(Cc[["n","mean_bp","t"]], lsuffix="_dev", rsuffix="_chk")
M = M[M.n_dev >= 60].sort_values("t_dev", ascending=False)
print(M.head(12).round(2).to_string())
print("dev t>2:", (M.t_dev>2).sum(), "of", len(M), "; dev t>2 and check mean>0:", ((M.t_dev>2)&(M.mean_bp_chk>0)).sum())
print("check t>2 among all:", (Cc.t>2).sum(), " check t<-2:", (Cc.t<-2).sum(), "of", len(Cc))
