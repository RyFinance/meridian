"""MSTR opening-auction lag study: does BTC's 09:20-09:31 ET move lead MSTR's first 1-15 minutes?

Conventions
- BTC and MSTR bar timestamps are bar-OPEN times (verified: BTC open_t ~ close_{t-1}).
- Price "as of T" = close of the bar stamped T-1 (last trade strictly before T).
- MSTR official open O = open of the 09:30 ET bar.
- Sealed holdout: every load is filtered to dates <= 2026-08-10 (UTC cut at 2026-08-11 00:00).
- Dev = trade date <= 2022-06-30; check = 2022-07-01 .. 2026-08-10.
- Costs: 3 bp per side + 5 bp extra half-spread = 8 bp per side (0.0008).
- Worst fills: buys at bar high, sells at bar low, on the execution bar.
"""
import glob
import json
import os

import numpy as np
import pandas as pd

ROOT = "/Users/rytty/CCP/quant_v7"
OUT = os.path.join(ROOT, "research/btc_ah/auction")
BTC = "/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet"
DEV_DIR = os.path.join(ROOT, "research/mstr_btc_0dte/stock_1m_dev")
LSE = os.path.join(ROOT, "research/mstr_btc_0dte/mstr_stock_1m_lse.parquet")
NY = "America/New_York"
CUT = pd.Timestamp("2026-08-11", tz="UTC")  # exclusive: nothing dated after 2026-08-10
DEV_END = pd.Timestamp("2022-06-30").date()
COST = 0.0008  # 8 bp per side

M = lambda hh, mm: hh * 60 + mm  # ET minute-of-day
M_0919, M_0927, M_0929, M_0930 = M(9, 19), M(9, 27), M(9, 29), M(9, 30)
M_0931, M_0935, M_0940, M_0945 = M(9, 31), M(9, 35), M(9, 40), M(9, 45)

# ---------------- load BTC (bar open times, UTC) ----------------
b = pd.read_parquet(BTC)
b = b[b.timestamp < CUT]
et = b.timestamp.dt.tz_convert(NY)
mins = et.dt.hour * 60 + et.dt.minute
keep = (mins >= M(9, 15)) & (mins <= M(9, 50))
bb = pd.DataFrame({"date": et[keep].dt.date, "m": mins[keep], "c": b.close[keep], "o": b.open[keep]})
BTC_C = {(d, m): c for d, m, c in zip(bb.date, bb.m, bb.c)}
BTC_DAYS = set(bb.date)

# ---------------- load MSTR regular-hours window (UTC -> ET) ----------------
parts = []
for f in sorted(glob.glob(os.path.join(DEV_DIR, "*.parquet"))):
    d = pd.read_parquet(f)
    d = pd.DataFrame({"ts": pd.to_datetime(d["time"], utc=True), "o": d.open, "h": d.high, "l": d.low, "c": d.close})
    parts.append(d)
dev = pd.concat(parts, ignore_index=True)
lse = pd.read_parquet(LSE)
lse = pd.DataFrame({"ts": pd.to_datetime(lse["ts"]).dt.tz_localize("UTC"), "o": lse.open, "h": lse.high, "l": lse.low, "c": lse.close})
ms = pd.concat([dev, lse], ignore_index=True)
ms = ms[ms.ts < CUT]
met = ms.ts.dt.tz_convert(NY)
mmins = met.dt.hour * 60 + met.dt.minute
mk = (mmins >= M(9, 25)) & (mmins <= M(9, 50))
mm_ = pd.DataFrame({"date": met[mk].dt.date, "m": mmins[mk], "o": ms.o[mk], "h": ms.h[mk], "l": ms.l[mk], "c": ms.c[mk]})
MS = {(d, m): (o, h, l, c) for d, m, o, h, l, c in zip(mm_.date, mm_.m, mm_.o, mm_.h, mm_.l, mm_.c)}
MS_DAYS = set(mm_.date)
print("dev files:", len(parts), "dev rows:", len(dev), "lse rows:", len(lse), "kept (<=2026-08-10):", len(ms))

# ---------------- per-day features ----------------
NEEDED_M = list(range(M_0930, M_0945 + 1))
rows = []
for d in sorted(MS_DAYS & BTC_DAYS):
    need_ms = [(d, m) for m in NEEDED_M]
    need_btc = [(d, m) for m in (M_0919, M_0927, M_0929, M_0930)]
    if not all(k in MS for k in need_ms) or not all(k in BTC_C for k in need_btc):
        continue
    O = MS[(d, M_0930)][0]
    cM = {m: MS[(d, m)][3] for m in NEEDED_M}
    # BTC signals (price as of T = close of bar T-1)
    x1 = BTC_C[(d, M_0929)] / BTC_C[(d, M_0919)] - 1  # 09:20 -> 09:30
    x2 = BTC_C[(d, M_0929)] / BTC_C[(d, M_0927)] - 1  # 09:28 -> 09:30
    x3 = BTC_C[(d, M_0930)] / BTC_C[(d, M_0929)] - 1  # 09:30 -> 09:31
    r = {"date": d, "x1": x1, "x2": x2, "x3": x3}
    # regression targets: open-based (to 09:31,09:32,09:35,09:40,09:45) and post-09:31 based
    for T in (M_0931, M_0931 + 1, M_0935, M_0940, M_0945):
        r[f"yo_{T}"] = cM[T - 1] / O - 1
    for T in (M_0931 + 1, M_0935, M_0940, M_0945):
        r[f"yp_{T}"] = cM[T - 1] / cM[M_0930] - 1
    # bar fills
    r["e30_h"], r["e30_l"] = MS[(d, M_0930)][1], MS[(d, M_0930)][2]
    r["e31_h"], r["e31_l"] = MS[(d, M_0931)][1], MS[(d, M_0931)][2]
    for X in (M_0935, M_0940, M_0945):
        r[f"x{X}_h"], r[f"x{X}_l"] = MS[(d, X)][1], MS[(d, X)][2]
    rows.append(r)

F = pd.DataFrame(rows)
F["dataset"] = np.where(F.date <= DEV_END, "dev", "check")
F["year"] = pd.to_datetime(F.date).dt.year
print("days with full data:", len(F), " dev:", (F.dataset == "dev").sum(), " check:", (F.dataset == "check").sum())
print("date range:", F.date.min(), "->", F.date.max())

# ---------------- regressions ----------------
def ols(y, x):
    X = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    s2 = resid @ resid / (n - k)
    cov = s2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    r2 = 1 - (resid @ resid) / ((y - y.mean()) @ (y - y.mean()))
    return beta[1], beta[1] / se[1], r2, n


reg_rows = []
for kind, prefix in (("open-based", "yo_"), ("post-09:31", "yp_")):
    tcols = [c for c in F.columns if c.startswith(prefix)]
    for ycol in tcols:
        for xcol in ("x1", "x2", "x3"):
            for ds in ("dev", "check", "all"):
                sub = F if ds == "all" else F[F.dataset == ds]
                y = sub[ycol].values * 1e4  # bp
                x = sub[xcol].values * 1e4
                beta, t, r2, n = ols(y, x)
                reg_rows.append({"kind": kind, "y": ycol, "x": xcol, "set": ds, "n": n,
                                 "beta": round(beta, 4), "t": round(t, 2), "r2": round(r2, 4)})
REG = pd.DataFrame(reg_rows)
REG.to_csv(os.path.join(OUT, "regressions.csv"), index=False)

# ---------------- trade simulation ----------------
def trade_ret(direction, e_bar, x_bar):
    """e_bar/x_bar: (high, low). Long buys entry high, sells exit low. Short sells entry low, buys exit high."""
    if direction > 0:
        E = e_bar[0] * (1 + COST)
        X = x_bar[1] * (1 - COST)
        return X / E - 1
    E = e_bar[1] * (1 - COST)
    X = x_bar[0] * (1 + COST)
    return 1 - X / E


SIGNALS = {"x1_0920-0930": "x1", "x2_0928-0930": "x2", "x3_0930-0931": "x3"}
ENTRIES = {"E0930open": ("e30", ("x1", "x2")), "E0931open": ("e31", ("x1", "x2", "x3"))}
EXITS = {"X0935": M_0935, "X0940": M_0940, "X0945": M_0945}
THRS_BP = [0, 10, 25, 50]

variants = []
for sname, scol in SIGNALS.items():
    for ename, (ekey, allowed) in ENTRIES.items():
        if scol not in allowed:
            continue
        for xname, X in EXITS.items():
            for thr in THRS_BP:
                variants.append((sname, ename, xname, thr, scol, ekey, X))

trades = []
for v in variants:
    sname, ename, xname, thr, scol, ekey, X = v
    vname = f"{sname}|{ename}|{xname}|thr{thr}"
    for r in F.itertuples(index=False):
        sig = getattr(r, scol) * 1e4
        if abs(sig) < thr or sig == 0:
            continue
        d = 1 if sig > 0 else -1
        e_bar = (getattr(r, f"{ekey}_h"), getattr(r, f"{ekey}_l")) if ekey == "e30" else (r.e31_h, r.e31_l)
        x_bar = (getattr(r, f"x{X}_h"), getattr(r, f"x{X}_l"))
        for flipped in (False, True):
            dd = -d if flipped else d
            ret = trade_ret(dd, e_bar, x_bar)
            trades.append((vname, sname, ename, xname, thr, flipped, r.dataset, r.year, r.date, ret))

T = pd.DataFrame(trades, columns=["variant", "signal", "entry", "exit", "thr_bp", "flipped", "dataset", "year", "date", "net"])
T.to_csv(os.path.join(OUT, "trades.csv"), index=False)


def stats(g):
    n = len(g)
    if n < 2:
        return dict(n=n)
    w, l = g[g > 0], g[g <= 0]
    sd = g.std(ddof=1)
    return dict(n=n, win=round((g > 0).mean(), 3), mean_bp=round(g.mean() * 1e4, 2),
                t=round(g.mean() / (sd / np.sqrt(n)), 2) if sd > 0 else np.nan,
                avg_win_bp=round(w.mean() * 1e4, 1) if len(w) else np.nan,
                avg_loss_bp=round(l.mean() * 1e4, 1) if len(l) else np.nan)


summ = []
for vname, g in T[T.flipped == False].groupby("variant"):  # noqa: E712
    fl = T[(T.variant == vname) & (T.flipped == True)]  # noqa: E712
    for ds in ("dev", "check", "all"):
        sub = g if ds == "all" else g[g.dataset == ds]
        fsub = fl if ds == "all" else fl[fl.dataset == ds]
        s = stats(sub.net.values)
        f = stats(fsub.net.values)
        yr = sub.groupby("year").net.mean().mul(1e4).round(1).to_dict()
        summ.append({"variant": vname, "set": ds, **s,
                     "flip_mean_bp": f.get("mean_bp"), "flip_t": f.get("t"),
                     "per_year_bp": json.dumps({int(k): v for k, v in yr.items()})})
SUM = pd.DataFrame(summ)
SUM.to_csv(os.path.join(OUT, "variant_summary.csv"), index=False)

# ---------------- select on dev, report check ----------------
dev_rows = SUM[SUM.set == "dev"].copy()
chk_rows = SUM[SUM.set == "check"].set_index("variant")
dev_rows = dev_rows[dev_rows.n >= 30].sort_values("mean_bp", ascending=False)
top = dev_rows.head(3)

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 30)
print("\n=== REGRESSIONS (beta in bp per bp of BTC; t from OLS) ===")
print(REG[REG.set == "all"].to_string(index=False))
print("\n=== DEV TOP-15 by mean net (bp per trade, n>=30) ===")
print(dev_rows[["variant", "n", "win", "mean_bp", "t", "avg_win_bp", "avg_loss_bp", "flip_mean_bp", "flip_t"]].head(15).to_string(index=False))
print("\n=== TOP-3 DEV -> CHECK ===")
for _, r in top.iterrows():
    c = chk_rows.loc[r.variant]
    print(r.variant, "| dev n", r.n, "mean", r.mean_bp, "t", r.t, "flip", r.flip_mean_bp, "||",
          "check n", c.get("n"), "win", c.get("win"), "mean", c.get("mean_bp"), "t", c.get("t"),
          "flip", c.get("flip_mean_bp"), "flip_t", c.get("flip_t"))
print("\n=== ALL 60 VARIANTS (check set, sorted by check mean) ===")
print(SUM[SUM.set == "check"].sort_values("mean_bp", ascending=False)[["variant", "n", "win", "mean_bp", "t", "flip_mean_bp", "flip_t"]].to_string(index=False))
print("\nvariant count:", len(variants), "(signals x entries x exits x thresholds); flips are controls on the same rows")

# ---------------- DIAGNOSTIC (not part of the 60 primary rules) ----------------
# Edge decomposition: sig_net ~ +edge - penalty, flip_net ~ -edge - penalty  =>  edge = (sig-flip)/2, penalty = -(sig+flip)/2
# Open-fill sensitivity: fill at bar open instead of worst high/low, 8 bp per side kept.
diag = []
for vname, g in T[T.flipped == False].groupby("variant"):  # noqa: E712
    for ds in ("dev", "check"):
        sub = g[g.dataset == ds]
        fl = T[(T.variant == vname) & (T.flipped == True) & (T.dataset == ds)]  # noqa: E712
        if len(sub) < 10:
            continue
        s_m, f_m = sub.net.mean() * 1e4, fl.net.mean() * 1e4
        diag.append({"variant": vname, "set": ds, "n": len(sub), "sig_mean_bp": round(s_m, 1),
                     "flip_mean_bp": round(f_m, 1), "edge_bp": round((s_m - f_m) / 2, 1),
                     "penalty_bp": round(-(s_m + f_m) / 2, 1)})
DG = pd.DataFrame(diag)
DG.to_csv(os.path.join(OUT, "diag_edge_decomposition.csv"), index=False)
print("\n=== DIAG edge decomposition (dev, check) ===")
print(DG[DG.set == "check"].sort_values("edge_bp", ascending=False).head(12).to_string(index=False))
print(DG[DG.set == "dev"].sort_values("edge_bp", ascending=False).head(6).to_string(index=False))

# open-fill sensitivity for the 60 variants
def open_ret(direction, e_open, x_open):
    if direction > 0:
        return x_open * (1 - COST) / (e_open * (1 + COST)) - 1
    return 1 - (x_open * (1 + COST)) / (e_open * (1 - COST))

ofl = []
for v in variants:
    sname, ename, xname, thr, scol, ekey, X = v
    vname = f"{sname}|{ename}|{xname}|thr{thr}"
    for r in F.itertuples(index=False):
        sig = getattr(r, scol) * 1e4
        if abs(sig) < thr or sig == 0:
            continue
        d = 1 if sig > 0 else -1
        e_o = MS[(r.date, M_0930)][0] if ekey == "e30" else MS[(r.date, M_0931)][0]
        x_o = MS[(r.date, X)][0]
        ofl.append((vname, r.dataset, r.year, open_ret(d, e_o, x_o)))
OF = pd.DataFrame(ofl, columns=["variant", "dataset", "year", "net"])
osum = []
for vname, g in OF.groupby("variant"):
    for ds in ("dev", "check"):
        sub = g[g.dataset == ds].net.values
        if len(sub) >= 10:
            s = stats(sub)
            osum.append({"variant": vname, "set": ds, **s})
OS = pd.DataFrame(osum)
OS.to_csv(os.path.join(OUT, "diag_open_fill_summary.csv"), index=False)
print("\n=== DIAG open-fill (8bp/side) check top 8 by mean ===")
print(OS[OS.set == "check"].sort_values("mean_bp", ascending=False).head(8).to_string(index=False))
print("open-fill dev top 5:")
print(OS[OS.set == "dev"].sort_values("mean_bp", ascending=False).head(5).to_string(index=False))
