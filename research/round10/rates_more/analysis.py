"""rates_more: do sister equities respond to the SAME ZB overnight signal as the ITB rule (09:30 open -> 10:30)?

Signal (identical to research/zb_itb/verify/f3_canonical.py, reproduced to 1e-16 on the 569 ITB trades):
  d = sign(ln(ZB 60m Close, bar 08:00 ET on D / ZB 60m Close, bar 15:00 ET on prev equity day)).
  Bars are START-labeled, so the 08:00 bar closes at 09:00 ET: no look-ahead.
Core rule (pre-registered, no selection): long if d>0, short if d<0; entry = official daily Open (09:30 auction);
  exit = close of the 60m 09:30 bar (10:30 ET). Round-trip cost = 2 x per-side bp.
  Tiers (decided from USD median daily dollar volume, sample-wide): ETFs 2 bp/side; names with median ADV < $20m
  10 bp/side ("thin"); all others 5 bp/side. Sensitivity: uniform 5 bp/side and gross (0 bp).
Dev-selection grid (6 variants): direction {same, flip} x exit {10:30, 11:30 (10:30-bar close), 16:00 (daily close)}.
Split: dev = first 55% of the 571 common trade days; check = remaining 45%.
Verdict thresholds (fixed before the run): EDGE = group basket net >0 in dev and check, check t >= 2.7
  (two-sided Bonferroni 0.05/7 groups), and >= half of member names net-positive in check.
  WEAK = basket net >0 in dev and check but not EDGE. NONE otherwise.
"""
import os, math, numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
ZB_PATH = "/Users/rytty/CCP/quant_v7/research/zb_itb/verify/yf_cache/ZB_F_60m.parquet"  # read-only reuse of ZB 60m pull
ZB5_PATH = "/Users/rytty/CCP/quant_v7/research/zb_itb/verify/yf_cache/ZB_F_5m.parquet"
ITB_CANON = "/Users/rytty/CCP/quant_v7/research/zb_itb/verify/f3_trades_canonical.csv"
NY = "America/New_York"
GROUPS = {
    "auto": "CVNA KMX AN LAD ABG PAG ALLY CACC",
    "rv_boat_hvac": "THO WGO LCII BC MBUU MCFT POOL LII CARR WSO",
    "mortgage_services": "FAF FNF UHAL FTDR PRCH",
    "timber": "WY RYN LPX UFPI BCC",
    "housing_banks": "FLG WAL BKU TFSL",
    "canada": "EQB.TO MKP.TO FC.TO",
}
ETF = {"ITB", "SPY"}
PREV_TESTED = {"CVNA", "ALLY", "POOL", "FNF"}  # brief: already tested null
GROUP_OF = {t: g for g, ts in GROUPS.items() for t in ts.split()}
GROUP_OF.update({"ITB": "reference", "SPY": "placebo"})
ALL = sorted(GROUP_OF)
fn = lambda t: t.replace(".", "_")
cache = lambda t, iv: os.path.join(CACHE, f"{fn(t)}_{iv}.parquet")

def bars60(path):
    d = pd.read_parquet(path); d.index = d.index.tz_convert(NY)
    day = d.index.strftime("%Y-%m-%d"); hh = d.index.strftime("%H:%M")
    return {k: (o, c) for k, o, c in zip(zip(day, hh), d.Open.values, d.Close.values)}

def daily(path):
    d = pd.read_parquet(path)
    days = [x.date().isoformat() for x in d.index]
    return {k: (o, c, v) for k, o, c, v in zip(days, d.Open.values, d.Close.values, d.Volume.values)}

# ---------- 1. bar-labeling checks ----------
ib = pd.read_parquet(cache("ITB", "60m")); ib.index = ib.index.tz_convert(NY)
g = pd.Series(ib.index.strftime("%H:%M"), index=ib.index.strftime("%Y-%m-%d")).groupby(level=0)
print("LABEL 1 ITB 60m: first bar = 09:30 on %.1f%% of days, last bar = 15:30 on %.1f%% (start-labeled)"
      % ((g.first() == "09:30").mean() * 100, (g.last() == "15:30").mean() * 100))
zb = bars60(ZB_PATH)
zb5 = pd.read_parquet(ZB5_PATH); zb5.index = zb5.index.tz_convert(NY)
m5 = dict(zip(zip(zb5.index.strftime("%Y-%m-%d"), zb5.index.strftime("%H:%M")), zb5.Close.values))
diffs = [abs(zb[(D, "08:00")][1] / m5[(D, "08:55")] - 1) * 1e4 for (D, hh) in list(zb) if hh == "08:00" and (D, "08:55") in m5]
print("LABEL 2 ZB: 60m 08:00 bar Close vs 5m 08:55 bar Close, median |diff| = %.3f bp, n=%d (08:00 bar closes 09:00)"
      % (np.median(diffs), len(diffs)))
for t in ["ITB", "SPY", "WSO", "EQB.TO"]:
    b = bars60(cache(t, "60m")); dl = daily(cache(t, "1d"))
    o = [abs(b[(D, "09:30")][0] / dl[D][0] - 1) * 1e4 for D in dl if (D, "09:30") in b]
    c = [abs(b[(D, "15:30")][1] / dl[D][1] - 1) * 1e4 for D in dl if (D, "15:30") in b]
    print("LABEL 3 %-7s median |60m 09:30 Open - daily Open| = %.2f bp; |60m 15:30 Close - daily Close| = %.2f bp"
          % (t, np.median(o), np.median(c)))

# ---------- 2. ZB overnight signal on the ITB equity calendar ----------
mdays = sorted(set(ib.index.strftime("%Y-%m-%d")))
sig = {}
for i in range(1, len(mdays)):
    D, prev = mdays[i], mdays[i - 1]
    p0, p1 = zb.get((prev, "15:00")), zb.get((D, "08:00"))
    if p0 is None or p1 is None: continue
    m = math.log(p1[1] / p0[1])
    if m != 0: sig[D] = int(np.sign(m))
trade_days = sorted(sig)
cut = trade_days[int(round(0.55 * len(trade_days)))]
CUT = pd.Timestamp(cut)
print(f"\nSIGNAL: {len(trade_days)} trade days {trade_days[0]}..{trade_days[-1]}; dev/check cut = {cut} "
      f"(dev n={sum(d < cut for d in trade_days)}, check n={sum(d >= cut for d in trade_days)})")

# ---------- 3. per-name trades ----------
fx = daily(cache("CAD=X", "1d"))  # CAD per USD; holidays missing in FX -> forward-fill last known rate
fx_s = pd.Series({k: v[1] for k, v in fx.items()}).sort_index()
def trades(t):
    b = bars60(cache(t, "60m")); dl = daily(cache(t, "1d")); rows = []
    for D in trade_days:
        if (D, "09:30") not in b or (D, "10:30") not in b or D not in dl: continue
        entry, x1600 = dl[D][0], dl[D][1]; x1030, x1130 = b[(D, "09:30")][1], b[(D, "10:30")][1]
        if min(entry, x1030, x1130, x1600) <= 0: continue
        rate = fx_s.loc[:D].iloc[-1] if t.endswith(".TO") else 1.0
        usd_vol = dl[D][1] * dl[D][2] / rate
        d = sig[D]
        rows.append(dict(date=pd.Timestamp(D), d=d, usd_vol=usd_vol,
                         g_1030=d * math.log(x1030 / entry), g_1130=d * math.log(x1130 / entry), g_1600=d * math.log(x1600 / entry)))
    return pd.DataFrame(rows).set_index("date")
TR = {t: trades(t) for t in ALL}

def side_bp(t):  # tiered cost, per side
    if t in ETF: return 2.0
    return 10.0 if TR[t].usd_vol.median() < 20e6 else 5.0
SIDE = {t: side_bp(t) for t in ALL}
ADV = {t: TR[t].usd_vol.median() / 1e6 for t in ALL}

# ITB reproduction against the canonical file
can = pd.read_csv(ITB_CANON, index_col=0, parse_dates=True).g_off.dropna() - 0.0004
itb_net = TR["ITB"].g_1030 - 2 * SIDE["ITB"] / 1e4
com = itb_net.index.intersection(can.index)
print(f"ITB reproduction vs f3_trades_canonical.csv: n={len(com)} trades, max |diff| = {np.max(np.abs(itb_net[com] - can[com])):.1e}")

# ---------- 4. stats ----------
def st(x):
    x = pd.Series(x).dropna(); n = len(x)
    if n < 3: return dict(n=n, mean_bp=np.nan, med_bp=np.nan, t=np.nan, p=np.nan, win=np.nan)
    m, s = x.mean(), x.std()
    t = m / s * math.sqrt(n) if s > 0 else np.nan
    return dict(n=n, mean_bp=m * 1e4, med_bp=x.median() * 1e4, t=t, p=math.erfc(abs(t) / math.sqrt(2)), win=(x > 0).mean())
def split(s): return s[s.index < CUT], s[s.index >= CUT]

VARS = {f"{lab}_{ex}": (sg, ex) for sg, lab in [(1, "same"), (-1, "flip")] for ex in ["1030", "1130", "1600"]}
def net(t, var, cost_side=None):
    sg, ex = VARS[var]; tr = TR[t]
    c = 2 * (SIDE[t] if cost_side is None else cost_side) / 1e4
    return sg * tr["g_" + ex] - c

rows = []
for t in ALL:
    s = net(t, "same_1030")
    dv, cv = split(s); fd, fc = split(net(t, "flip_1030"))
    _, gchk = split(TR[t].g_1030); gdev, _ = split(TR[t].g_1030), None
    rec = dict(ticker=t, group=GROUP_OF[t], side_bp=SIDE[t], adv_usd_m=round(ADV[t], 1), prev_tested=t in PREV_TESTED,
               first=str(TR[t].index.min().date()))
    for k, v in st(dv).items(): rec["dev_" + k] = v
    for k, v in st(cv).items(): rec["chk_" + k] = v
    rec["chk_gross_mean_bp"] = st(split(TR[t].g_1030)[1])["mean_bp"]
    rec["chk_flip_mean_bp"] = st(fc)["mean_bp"]; rec["chk_flip_t"] = st(fc)["t"]
    rec["corr_itb"] = 1.0 if t == "ITB" else s.corr(itb_net)
    best = None
    for var in VARS:
        d1, c1 = split(net(t, var))
        s1 = st(d1)
        if s1["n"] >= 30 and (best is None or s1["t"] > best[1]["t"]): best = (var, s1, st(c1))
    if best:
        rec["sel_var"] = best[0]; rec["sel_dev_t"] = best[1]["t"]; rec["sel_chk_mean_bp"] = best[2]["mean_bp"]; rec["sel_chk_t"] = best[2]["t"]
    rows.append(rec)
R = pd.DataFrame(rows)
R.to_csv(os.path.join(HERE, "results_by_name.csv"), index=False)
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 40)
cols = ["ticker", "group", "side_bp", "adv_usd_m", "first", "dev_n", "dev_mean_bp", "dev_med_bp", "dev_t", "chk_n", "chk_mean_bp",
        "chk_med_bp", "chk_t", "chk_win", "chk_gross_mean_bp", "chk_flip_mean_bp", "chk_flip_t", "corr_itb", "sel_var", "sel_chk_mean_bp", "sel_chk_t", "prev_tested"]
print("\nPER NAME, core rule (same direction, 09:30 open -> 10:30 close), net of tier cost")
print(R[cols].round(2).to_string(index=False))

# ---------- 5. group baskets (equal weight across names trading that day) ----------
def basket(names, mk):
    frame = pd.DataFrame({t: mk(t) for t in names})
    return frame.mean(axis=1)
def baskets(cost_mode):
    cs = {"tier": lambda t: None, "uniform5": lambda t: 5.0 if t not in ETF else 2.0, "gross": lambda t: 0.0}[cost_mode]
    out = []
    for g in list(GROUPS) + ["placebo", "reference"]:
        names = ([t for t in GROUPS[g].split()] if g in GROUPS else ["SPY"] if g == "placebo" else ["ITB"])
        b = basket(names, lambda t: net(t, "same_1030", cs(t)))
        d1, c1 = split(b)
        dv, cv = st(d1), st(c1)
        out.append(dict(cost=cost_mode, group=g, n_names=len(names), dev_mean_bp=dv["mean_bp"], dev_t=dv["t"], dev_n=dv["n"],
                        chk_mean_bp=cv["mean_bp"], chk_t=cv["t"], chk_n=cv["n"], chk_win=cv["win"],
                        frac_names_pos_chk=np.mean([st(split(net(t, 'same_1030', cs(t)))[1])["mean_bp"] > 0 for t in names]),
                        corr_itb=1.0 if g == "reference" else b.corr(itb_net)))
    return pd.DataFrame(out)
B = pd.concat([baskets(m) for m in ["tier", "uniform5", "gross"]], ignore_index=True)
B.to_csv(os.path.join(HERE, "results_baskets.csv"), index=False)
print("\nGROUP BASKETS, core rule (tier = primary; uniform5 / gross = sensitivity)")
print(B.round(2).to_string(index=False))

# ---------- 6. multiplicity ----------
core = R[~R.ticker.isin(["ITB", "SPY"])]
pc = core.chk_p.dropna(); m = len(pc)
bh = np.sort(pc.values); ranks = np.arange(1, m + 1); q = np.minimum.accumulate((bh * m / ranks)[::-1])[::-1]
print(f"\nMULTIPLICITY: {m} core-name tests on check (two-sided). raw p<0.05: {(pc < 0.05).sum()}; "
      f"Bonferroni 0.05/{m}: {(pc < 0.05 / m).sum()}; BH q<0.05: {(q < 0.05).sum()}")
print(core[core.chk_p < 0.05][["ticker", "group", "side_bp", "chk_mean_bp", "chk_t", "chk_gross_mean_bp", "dev_mean_bp", "dev_t"]].round(2).to_string(index=False))
