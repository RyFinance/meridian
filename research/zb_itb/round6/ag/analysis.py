"""Round 6 'ag': grain futures overnight move (CBOT, ZC/ZS/ZW) -> US ag/food equities & ETFs, 09:30 entry.
Bars are START-labeled (yfinance). Signal: grain bar labeled 08:00 ET (ends 09:00) vs bar labeled 14:00 ET on prev
equity session (last grain bar ending <= 16:00 ET; grains have no 15:00 bar since day session ends 14:20 ET).
Dev = 2024-05-28..2025-06-30, check = 2025-07-01..2026-10-16. Outputs csv to this folder."""
import itertools, numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).parent; DATA = HERE / "data"
DEV = (pd.Timestamp("2024-05-28"), pd.Timestamp("2025-06-30"))
CHK = (pd.Timestamp("2025-07-01"), pd.Timestamp("2026-10-16"))
GRAINS = {"ZC": "ZC_F", "ZS": "ZS_F", "ZW": "ZW_F"}
GROUPS = {
    "LONG_STK": (+1, ["ADM","BG","ANDE","CTVA","FMC","MOS","CF","NTR","DE","AGCO","CNH"]),
    "LONG_ETF": (+1, ["MOO","CORN","SOYB","WEAT"]),
    "PROC":     (-1, ["GIS","CAG","TSN","PPC","HRL"]),
}
ETFS = {"MOO","CORN","SOYB","WEAT","SPY"}
NAMES = [n for g in GROUPS.values() for n in g[1]]

def ld(f):
    d = pd.read_parquet(DATA / f)
    d.index = d.index.tz_convert("America/New_York") if d.index.tz is not None else d.index
    return d

# ---- grain signal per equity session D ----
spy60 = ld("SPY_60m.parquet")
cal = sorted(set(spy60.index[spy60.index.strftime("%H:%M") == "09:30"].tz_localize(None).normalize()))
cal = [d for d in cal if d >= pd.Timestamp("2024-05-27")]  # need prev-session ref
g = {k: ld(f"{v}_60m.parquet") for k, v in GRAINS.items()}
for k in g:  # exact-label lookups: label -> close, keyed by date
    g[k] = g[k].assign(date=g[k].index.tz_localize(None).normalize(), hm=g[k].index.strftime("%H:%M"))
def gclose(k, date, hm):
    x = g[k]; r = x[(x.date == date) & (x.hm == hm)]
    return float(r.Close.iloc[0]) if len(r) == 1 else np.nan
sig_rows = []
for i in range(1, len(cal)):
    D, P = cal[i], cal[i - 1]
    row = dict(date=D, prev=P)
    for k in GRAINS:
        ref, sig = gclose(k, P, "14:00"), gclose(k, D, "08:00")
        row[f"m_{k}"] = np.log(sig / ref) if (np.isfinite(ref) and np.isfinite(sig)) else np.nan
    sig_rows.append(row)
S = pd.DataFrame(sig_rows).set_index("date")
S["m_COMB"] = S[["m_ZC","m_ZS","m_ZW"]].mean(axis=1, skipna=False)
print("calendar days", len(S), "| valid signal days per series:", {c: int(S[c].notna().sum()) for c in ["m_ZC","m_ZS","m_ZW","m_COMB"]})
print("zero-move days (COMB):", int((S.m_COMB == 0).sum()))

# ---- equity legs ----
def legs(name):
    d1 = ld(f"{name}_1d.parquet"); d1.index = pd.DatetimeIndex(d1.index).tz_localize(None).normalize()
    m = ld(f"{name}_60m.parquet"); m = m.assign(date=m.index.tz_localize(None).normalize(), hm=m.index.strftime("%H:%M"))
    out = {}
    b930 = m[m.hm == "09:30"].set_index("date"); b1030 = m[m.hm == "10:30"].set_index("date")
    L = pd.DataFrame(index=S.index)
    L["off"] = d1.Open.reindex(L.index)
    L["h1"] = b930.Open.reindex(L.index)
    L["exit1030"] = b930.Close.reindex(L.index)
    L["exit1130"] = b1030.Close.reindex(L.index)
    L["exitcl"] = d1.Close.reindex(L.index)
    # ADV in $M over dev
    dv = (d1.Close * d1.Volume).loc[DEV[0]:DEV[1]]
    adv = dv.median() / 1e6
    return L, adv

LEG, ADV = {}, {}
for n in NAMES + ["SPY"]:
    LEG[n], ADV[n] = legs(n)

def cost_bp(n):  # per side (brief tiers): ADV>=$200M 2bp; $5-200M small/mid or ETF<$20M 5bp; <$5M thin 10bp
    a = ADV[n]
    if a < 5: return 10
    if a < 200: return 5
    return 2
COST = {n: cost_bp(n) for n in NAMES + ["SPY"]}

SIGNALS = ["m_COMB", "m_ZC", "m_ZS", "m_ZW"]
ENTRIES = ["off", "h1"]
EXITS = ["exit1030", "exit1130", "exitcl"]
ENTRY_LABEL = {"off": "MOO(daily open)", "h1": "09:30 bar open"}
EXIT_LABEL = {"exit1030": "10:30", "exit1130": "11:30", "exitcl": "close"}

GROSS = {"on": False}
def trades(n, sigcol, entry, exitc, sense):
    """per-day net return for name n; sense = +1 expected, -1 flip. Returns Series indexed by date."""
    L = LEG[n]; m = S[sigcol]; sgn = np.sign(m)
    r = np.log(L[exitc] / L[entry])
    gross = sense * sgn * r
    net = gross - (0.0 if GROSS["on"] else 2 * COST[n] / 1e4)
    return net.where(sgn != 0).dropna()

def basket(names, sigcol, entry, exitc, sense):
    frames = []
    for n in names:
        t = trades(n, sigcol, entry, exitc, sense)
        frames.append(t.rename(n))
    M = pd.concat(frames, axis=1)
    return M.mean(axis=1, skipna=True).dropna(), M

def stats(x):
    x = x.dropna()
    if len(x) < 3: return dict(n=len(x), mean_bp=np.nan, t=np.nan, win=np.nan)
    return dict(n=len(x), mean_bp=x.mean() * 1e4, t=x.mean() / x.std(ddof=1) * np.sqrt(len(x)), win=(x > 0).mean())

def in_win(idx, w): return (idx >= w[0]) & (idx <= w[1])

rows = []
variants = list(itertools.product(SIGNALS, ENTRIES, EXITS))
for gname, (sense, names) in GROUPS.items():
    for sigcol, ent, ex in variants:
        b, M = basket(names, sigcol, ent, ex, sense)
        flip_b, _ = basket(names, sigcol, ent, ex, -sense)
        GROSS["on"] = True; gb, _ = basket(names, sigcol, ent, ex, sense); GROSS["on"] = False
        for split, w in [("dev", DEV), ("check", CHK)]:
            bb = b[in_win(b.index, w)]; fb = flip_b[in_win(flip_b.index, w)]; gg = gb[in_win(gb.index, w)]
            st = stats(bb); fs = stats(fb); gs = stats(gg)
            pn = M[in_win(M.index, w)]; pt = pn.stack().dropna()
            rows.append(dict(group=gname, sense=sense, signal=sigcol, entry=ENTRY_LABEL[ent], exit=EXIT_LABEL[ex], split=split,
                             basket_n=st["n"], basket_mean_bp=st["mean_bp"], basket_t=st["t"], basket_win=st["win"],
                             trade_n=len(pt), trade_mean_bp=pt.mean()*1e4 if len(pt) else np.nan,
                             flip_mean_bp=fs["mean_bp"], flip_t=fs["t"],
                             gross_mean_bp=gs["mean_bp"], gross_t=gs["t"]))
R = pd.DataFrame(rows)
R.to_csv(HERE / "group_results.csv", index=False)

# per-name results
nrows = []
for n in NAMES:
    sense = [s for s, nm in GROUPS.values() if n in nm][0]
    for sigcol, ent, ex in variants:
        t = trades(n, sigcol, ent, ex, sense)
        for split, w in [("dev", DEV), ("check", CHK)]:
            st = stats(t[in_win(t.index, w)])
            nrows.append(dict(name=n, sign=sense, cost_bp=COST[n], adv_musd=round(ADV[n],1), signal=sigcol, entry=ENTRY_LABEL[ent],
                              exit=EXIT_LABEL[ex], split=split, n=st["n"], mean_bp=st["mean_bp"], t=st["t"], win=st["win"]))
P = pd.DataFrame(nrows); P.to_csv(HERE / "name_results.csv", index=False)

# SPY placebo, same rules (sense +1), and per-name flip count
sp = []
for sigcol, ent, ex in variants:
    t = trades("SPY", sigcol, ent, ex, +1)
    for split, w in [("dev", DEV), ("check", CHK)]:
        st = stats(t[in_win(t.index, w)])
        sp.append(dict(signal=sigcol, entry=ENTRY_LABEL[ent], exit=EXIT_LABEL[ex], split=split, n=st["n"], mean_bp=st["mean_bp"], t=st["t"], win=st["win"]))
SP = pd.DataFrame(sp); SP.to_csv(HERE / "spy_placebo.csv", index=False)

print("\nCOST/ADV (dev median $M):")
print(pd.Series({n: f"{ADV[n]:.1f}M / {COST[n]}bp" for n in NAMES + ['SPY']}).to_string())
print("\nNames with no data: LNDC (empty), K (empty). Included:", len(NAMES), "names")
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print("\nGROUP-LEVEL (dev) top 6 by basket t per group:")
dv = R[R.split == "dev"].copy()
for gname in GROUPS:
    x = dv[dv.group == gname].sort_values("basket_t", ascending=False).head(6)
    print(x[["group","signal","entry","exit","basket_n","basket_mean_bp","basket_t","basket_win","trade_n","trade_mean_bp","flip_mean_bp","flip_t","gross_mean_bp","gross_t"]].round(2).to_string(index=False))
print("\nGROUP-LEVEL (check) same rules as dev top-6 of each group:")
ck = R[R.split == "check"]
for gname in GROUPS:
    top = dv[dv.group == gname].sort_values("basket_t", ascending=False).head(6)
    keys = top[["signal","entry","exit"]].values.tolist()
    x = ck[(ck.group == gname)]
    x = x[[ [s,e,ex] in keys for s,e,ex in zip(x.signal, x.entry, x.exit)]]
    print(x[["group","signal","entry","exit","basket_n","basket_mean_bp","basket_t","basket_win","trade_n","trade_mean_bp","flip_mean_bp","flip_t","gross_mean_bp","gross_t"]].round(2).to_string(index=False))
print("\nSPY placebo (dev and check) for m_COMB, MOO entry:")
print(SP[(SP.signal=="m_COMB")].round(2).to_string(index=False))
print("\nVariant count: group-level", len(R)//2, "rules per split,", len(P)//2, "per-name rules; SPY", len(SP)//2)
S.to_csv(HERE / "signals.csv")
