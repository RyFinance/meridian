"""FX second-order test. Signal: sign of FX 60m close 08:00 bar (ends 09:00 ET, day D) / 15:00 bar (ends 16:00 ET, prev trading day).
Trade: d * target, entry = target 1d Open (MOO, 09:30), exit = 60m 09:30 bar Close (10:30). Costs per side by dollar-volume tier."""
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).parent; C = HERE / "yf_cache"; NY = "America/New_York"
DEV0, DEV1 = pd.Timestamp("2024-05-28"), pd.Timestamp("2025-06-30")
CHK0, CHK1 = pd.Timestamp("2025-07-01"), pd.Timestamp("2026-10-16")
FXF = {"DXY": "DX-Y_NYB", "EUR": "6E_F", "JPY": "6J_F", "JPYX": "JPY_X", "AUD": "6A_F"}
SIGS = ["DXY", "EUR", "JPY", "JPYX", "AUD"]  # JPYX is used with a sign flip so that + = yen strong
# A priori (fixed before the run): target -> (strength signal, direction)
PRIOR = {"TM": ("JPY", -1), "HMC": ("JPY", -1), "SONY": ("JPY", -1), "MUFG": ("JPY", -1), "SMFG": ("JPY", -1), "EWJ": ("JPY", -1),
         "GDX": ("DXY", -1), "NEM": ("DXY", -1), "AEM": ("DXY", -1),
         "KO": ("DXY", -1), "PG": ("DXY", -1), "MCD": ("DXY", -1), "AAPL": ("DXY", -1), "MSFT": ("DXY", -1), "CAT": ("DXY", -1), "DE": ("DXY", -1),
         "EEM": ("DXY", -1), "EWZ": ("DXY", -1), "EWW": ("DXY", -1),
         "BHP": ("AUD", +1), "RIO": ("AUD", +1), "EWA": ("AUD", +1)}
TGT = list(PRIOR) + ["DXJ", "SPY"]  # DXJ: yen-hedged, no prior. SPY: placebo
PLACEBO = {"SPY"}

def l60(sym):
    d = pd.read_parquet(C / f"{sym}_60m.parquet"); d.index = d.index.tz_convert(NY); return d.sort_index()
def l1(sym):
    d = pd.read_parquet(C / f"{sym}_1d.parquet"); idx = pd.DatetimeIndex(d.index)
    if idx.tz is not None: idx = idx.tz_localize(None)
    d.index = idx.normalize(); return d.sort_index()

FX60 = {k: l60(v) for k, v in FXF.items()}

def panel(tgt):
    t60, t1 = l60(tgt), l1(tgt)
    days = sorted(set(t60.index[t60.index.time == pd.Timestamp("09:30").time()].date))
    rows = []
    for i in range(1, len(days)):
        D, P = pd.Timestamp(days[i]), pd.Timestamp(days[i - 1])
        if not (DEV0 <= D <= CHK1) or D not in t1.index: continue
        t0, tn = P.tz_localize(NY) + pd.Timedelta(hours=15), D.tz_localize(NY) + pd.Timedelta(hours=8)
        bar = D.tz_localize(NY) + pd.Timedelta(hours=9, minutes=30)
        if bar not in t60.index: continue
        r = {"date": D, "entry": t1.loc[D, "Open"], "exit": t60.loc[bar, "Close"]}
        for k, f in FX60.items():
            r[k] = np.sign(np.log(f.loc[tn, "Close"] / f.loc[t0, "Close"])) if (t0 in f.index and tn in f.index) else np.nan
        rows.append(r)
    p = pd.DataFrame(rows).set_index("date")
    p["gross"] = np.log(p.exit / p.entry)
    p["JPYX"] = -p["JPYX"]  # yen strength = -sign(USDJPY)
    p["JPYX_is_yen"] = True
    dv = (t1.Volume * t1.Close)[(t1.index >= DEV0) & (t1.index <= DEV1)].median()
    return p, dv

def tier(dv):
    # brief: 2bp/side liquid ETFs and large caps; 5bp for small/mid or ETFs under $20M/day (thin = 10bp, none here)
    return 2 if dv >= 20e6 else 5

def st(x):
    x = x.dropna(); n = len(x)
    if n < 5: return dict(n=n, bp=np.nan, t=np.nan, hit=np.nan)
    return dict(n=n, bp=x.mean() * 1e4, t=x.mean() / x.std(ddof=1) * np.sqrt(n), hit=(x > 0).mean())

PANEL, DV = {}, {}
for t in TGT:
    PANEL[t], DV[t] = panel(t)

rows, daily = [], {}
for t in TGT:
    p = PANEL[t]; cs = tier(DV[t])
    for s in SIGS:
        for d in (+1, -1):
            pos = d * p[s]
            m = pos.notna() & (pos != 0)
            net = (pos[m] * p.gross[m]) - 2 * cs / 1e4
            net5 = (pos[m] * p.gross[m]) - 2 * 5 / 1e4
            g = pos[m] * p.gross[m]
            dev, chk = net[(net.index >= DEV0) & (net.index <= DEV1)], net[(net.index >= CHK0) & (net.index <= CHK1)]
            sd, sc = st(dev), st(chk)
            gd, gc = st(g[(g.index >= DEV0) & (g.index <= DEV1)]), st(g[(g.index >= CHK0) & (g.index <= CHK1)])
            prior = PRIOR.get(t)
            kind = "primary" if (prior and prior == (s, d)) else ("flip" if (prior and prior == (s, -d)) else ("placebo-prior" if t in PLACEBO and False else "scan"))
            rows.append(dict(tgt=t, sig=s, dir=d, kind=kind, cost_side=cs, dv_musd=round(DV[t] / 1e6, 1),
                             dev_n=sd["n"], dev_bp=sd["bp"], dev_t=sd["t"], chk_n=sc["n"], chk_bp=sc["bp"], chk_t=sc["t"],
                             gdev_bp=gd["bp"], gdev_t=gd["t"], gchk_bp=gc["bp"], gchk_t=gc["t"], gall_t=st(g)["t"],
                             chk_hit=sc["hit"], chk_bp_at5=st(net5[(net5.index >= CHK0) & (net5.index <= CHK1)])["bp"],
                             all_t=st(net)["t"], all_bp=st(net)["bp"]))
            if kind == "primary": daily.setdefault(("primary", t), net); daily.setdefault(("pgross", t), g)
            if kind == "flip": daily.setdefault(("flip", t), net)
V = pd.DataFrame(rows)
V.to_csv(HERE / "variants.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)

print("PRIMARY (a priori signal and sign, fixed before run); flip = opposite sign on the same signal")
prim = V[V.kind.isin(["primary", "flip"])].copy()
print(prim[["tgt", "kind", "sig", "dir", "cost_side", "dv_musd", "gdev_bp", "gdev_t", "gchk_bp", "gchk_t", "dev_bp", "chk_bp", "chk_t", "chk_hit"]].round(2).to_string(index=False))

# pooled primary: equal-weight average across primary targets (excludes DXJ, SPY), per date
def pooled(kind, names):
    frames = [daily[(kind, t)].rename(t) for t in names if (kind, t) in daily]
    M = pd.concat(frames, axis=1); return M.mean(axis=1), M.shape[1]
prim_names = [t for t in PRIOR]
pp, k = pooled("primary", prim_names); pf, _ = pooled("flip", prim_names); pg, _ = pooled("pgross", prim_names)
for lab, ser in [("pooled primary NET (equal-weight, %d targets)" % k, pp), ("pooled flip NET", pf), ("pooled primary GROSS", pg)]:
    print(lab, "dev", {a: round(float(b), 2) for a, b in st(ser[(ser.index >= DEV0) & (ser.index <= DEV1)]).items()},
          "check", {a: round(float(b), 2) for a, b in st(ser[(ser.index >= CHK0) & (ser.index <= CHK1)]).items()})

print("\nSPY placebo, all 10 variants")
print(V[V.tgt == "SPY"][["sig", "dir", "gdev_bp", "gdev_t", "gchk_bp", "gchk_t", "dev_bp", "chk_bp", "chk_t"]].round(2).to_string(index=False))

print("\nEXPLORATORY SCAN: all variants, ranked by dev t (select on dev only)")
top = V.sort_values("dev_t", ascending=False).head(8)
print(top[["tgt", "sig", "dir", "kind", "gdev_bp", "gdev_t", "gchk_bp", "gchk_t", "chk_bp", "chk_t"]].round(2).to_string(index=False))
gt = V.sort_values("gdev_t", ascending=False).head(5)
print("top 5 by GROSS dev t:"); print(gt[["tgt", "sig", "dir", "kind", "gdev_bp", "gdev_t", "gchk_bp", "gchk_t", "chk_bp", "chk_t"]].round(2).to_string(index=False))
n_var = len(V)
print(f"\nvariants={n_var} (24 targets x 5 signals x 2 directions; unique tests={n_var//2})")
print("GROSS dev |t|>=2 (unique tests, direction chosen by sign):", int((V[V.dir==1].gdev_t.abs()>=2).sum()), "of", n_var//2)
print("GROSS dev t>=2 and check gross same sign and |check t|>=2:", int(((V.gdev_t>=2)&(V.gchk_t*np.sign(V.gdev_t)>=2)).sum()))
print("GROSS check |t|>=2 overall:", int((V.gchk_t.abs()>=2).sum()))
print("NET primary check t>=2:", int(((V.kind=='primary') & (V.chk_t>=2)).sum()), "of 22")
