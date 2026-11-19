"""Oil-futures overnight move -> US energy equities/ETFs at the open.
Intraday (1h, 2024-05..2026-08-10) and daily long-history (2000..2026-08-10) versions.
Sealed: every loaded frame is already filtered to <= 2026-08-10 by fetch.py.
Dev/check split: intraday dev <= 2025-06-30 (check 2025-07-01..2026-08-10);
daily dev <= 2022-06-30 (check 2022-07-01..2026-08-10).
"""
import numpy as np, pandas as pd
from pathlib import Path
C = Path(__file__).parent / "cache"
OUT = Path(__file__).parent
OIL_OF = {**{k: "CL_F" for k in ["USO","UCO","SCO","XLE","XOP","OIH","XOM","CVX","OXY","COP","DVN","FANG","APA","FRO","DHT","STNG","TNK"]},
          "BNO": "BZ_F", "UNG": "NG_F", "BOIL": "NG_F"}
ETF = {"USO","BNO","UCO","SCO","XLE","XOP","OIH","UNG","BOIL"}
COST_SIDE_BP = {i: (2.0 if i in ETF else 3.0) for i in OIL_OF}   # per side, bp
KS = [0.0, 0.5, 1.0, 2.0]
# OPEC+ weekend meetings (from memory, UNVERIFIED): Mondays after them
OPEC_MON = ["2024-06-03","2024-12-02","2025-03-03","2025-06-02","2025-07-07","2025-08-04",
            "2025-09-08","2025-10-06","2025-11-03","2025-12-01"]
DEV_END_I, DEV_END_D = pd.Timestamp("2025-06-30"), pd.Timestamp("2022-06-30")

def load(name, tf):
    return pd.read_parquet(C / f"{tf}_{name}.parquet")

def at(s, ts):
    return s.get(ts, np.nan)

def stats(df, col="net"):
    if len(df) == 0: return dict(n=0)
    x = df[col].values
    sd = x.std(ddof=1) if len(x) > 1 else np.nan
    yrs = df.groupby(df["date"].dt.year)[col].agg(["mean","count"])
    return dict(n=len(x), win=(x>0).mean(), mean_bp=x.mean()*1e4,
                t=x.mean()/(sd/np.sqrt(len(x))) if sd and sd>0 else np.nan,
                avg_win_bp=x[x>0].mean()*1e4 if (x>0).any() else np.nan,
                avg_loss_bp=x[x<=0].mean()*1e4 if (x<=0).any() else np.nan,
                per_year={int(y): (round(r["mean"]*1e4,1), int(r["count"])) for y, r in yrs.iterrows()})

# ---------------- INTRADAY ----------------
def intraday():
    oil = {o: load(o, "h1") for o in ["CL_F","BZ_F","NG_F"]}
    oilc = {o: d["Close"] for o, d in oil.items()}
    eq = {i: load(i, "h1") for i in OIL_OF}
    sessions = sorted(set(eq["USO"].index.normalize()))
    sessions = [s for s in sessions if s >= pd.Timestamp("2024-05-24")]
    # oil x per oil series, decision at 09:00 (bar 08:00 closes 09:00); start = 16:00 prev session (bar 15:00 close)
    rows = []
    for i in range(1, len(sessions)):
        P, D = sessions[i-1], sessions[i]
        r = {"date": D, "P": P, "weekend": (P.dayofweek == 4 and D.dayofweek == 0),
             "gapdays": (D - P).days}
        for o, s in oilc.items():
            st = at(s, P + pd.Timedelta(hours=15)); en = at(s, D + pd.Timedelta(hours=8))
            r[f"x_{o}"] = np.log(en / st) if (st > 0 and en > 0) else np.nan
        for ins in OIL_OF:
            e = eq[ins]["Close"]; eo = eq[ins]["Open"]
            r[f"pc_{ins}"] = at(e, P + pd.Timedelta(hours=15, minutes=30))
            r[f"o_{ins}"] = at(eo, D + pd.Timedelta(hours=9, minutes=30))
            r[f"c930_{ins}"] = at(e, D + pd.Timedelta(hours=9, minutes=30))
            r[f"o1030_{ins}"] = at(eo, D + pd.Timedelta(hours=10, minutes=30))
            r[f"c_{ins}"] = at(e, D + pd.Timedelta(hours=15, minutes=30))
        rows.append(r)
    T = pd.DataFrame(rows).dropna(subset=["x_CL_F"])
    T["weekend"] = T["weekend"].astype(bool)
    return T, eq

def intraday_trades(T):
    out = []
    dev = T["date"] <= DEV_END_I
    for ins, oil in OIL_OF.items():
        x = T[f"x_{oil}"]
        ok = T[f"pc_{ins}"].notna() & T[f"o_{ins}"].notna() & T[f"c_{ins}"].notna() & T[f"o1030_{ins}"].notna() & T[f"c930_{ins}"].notna() & x.notna()
        t = T[ok].copy()
        dv = dev[ok]
        gap = np.log(t[f"o_{ins}"] / t[f"pc_{ins}"])
        bx = np.polyfit(t.loc[dv, f"x_{oil}"], gap[dv], 1)
        beta = bx[0]
        e = gap - (bx[1] + beta * t[f"x_{oil}"])  # residual of open gap vs oil-implied
        sx = t.loc[dv, f"x_{oil}"].std(); se = e[dv].std()
        rc = COST_SIDE_BP[ins] * 2 / 1e4  # round trip
        ret_fh = t[f"c930_{ins}"] / t[f"o_{ins}"] - 1          # 09:30 open -> 10:30 close
        ret_oc = t[f"c_{ins}"] / t[f"o_{ins}"] - 1             # 09:30 open -> 16:00 close
        ret_res = t[f"c_{ins}"] / t[f"o1030_{ins}"] - 1        # 10:30 open -> 16:00 close
        base = pd.DataFrame({"date": t["date"], "inst": ins, "oil": oil, "x": t[f"x_{oil}"],
                             "e": e, "weekend": t["weekend"], "dev": dv, "gap": gap,
                             "gapbeta": beta, "ret_fh": ret_fh, "ret_oc": ret_oc, "ret_res": ret_res})
        base["year"] = base["date"].dt.year
        for k in KS:
            specs = [("X_FH", "x", sx, ret_fh), ("X_OC", "x", sx, ret_oc), ("E_RES", "e", se, ret_res)]
            for name, src, sd, ret in specs:
                v = base[src]
                sel = (v.abs() >= k * sd) if k > 0 else pd.Series(True, index=base.index)
                side = np.sign(v) * sel
                for flip in [1, -1]:
                    s = side * flip
                    m = s != 0
                    d = base[m].copy()
                    d["side"] = s[m]
                    d["gross"] = d["side"] * ret[m]
                    d["net"] = d["gross"] - rc
                    d["rule"] = f"{name}_k{k}"
                    d["variant"] = f"{name}|k={k}|{ins}|{'follow' if flip == 1 else 'FLIP'}"
                    d["kind"] = "follow" if flip == 1 else "flip"
                    out.append(d)
    return pd.concat(out, ignore_index=True)

def intraday_report(TR):
    res = []
    fol = TR[TR.kind == "follow"]
    for (rule, ins), g in fol.groupby(["rule", "inst"]):
        for part, gg in [("dev", g[g.dev]), ("check", g[~g.dev])]:
            s = stats(gg)
            res.append(dict(rule=rule, inst=ins, part=part, **{k: v for k, v in s.items() if k != "per_year"}))
    R = pd.DataFrame(res)
    return R

if __name__ == "__main__":
    import sys, json
    pd.set_option("display.width", 220); pd.set_option("display.max_rows", 500); pd.set_option("display.max_columns", 30)
    T, eq = intraday()
    print("intraday sessions", len(T), T["date"].min().date(), T["date"].max().date(), flush=True)
    print("oil x sd (dev):", {o: round(T.loc[T.date<=DEV_END_I, f'x_{o}'].std()*100, 2) for o in ["CL_F","BZ_F","NG_F"]})
    TR = intraday_trades(T)
    TR.to_parquet(OUT / "trades_intraday.parquet")
    R = intraday_report(TR)
    R.to_csv(OUT / "results_intraday.csv", index=False)
    print("variants (rule x instrument x k x direction), follow only:", TR[TR.kind=='follow'].variant.nunique())
