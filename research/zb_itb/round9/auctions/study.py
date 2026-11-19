"""Round 9 / auctions: does ZB's move during the Treasury auction-result hour lead ITB intraday or overnight?
Frozen caches only (no network). Start-labeled 60m bars, America/New_York.
Signal d = sign(log(Close[ZB bar starting T] / Open[ZB bar starting T])), T = 13:00 (or 11:30 when the 2024 sample says so -> bar 11:00? no: see EVENT_BAR).
Trades (per event date D, direction d):
  intra : ITB open of bar 14:30 -> close of bar 15:30 on D
  over  : ITB open of bar 14:30 on D -> close of bar 09:30 on D+1 (i.e. 10:30 next day)
Costs 2 bp/side = 4 bp round trip. Dev 2024-05-28..2025-06-30, check 2025-07-01..2026-10-16.
"""
import re, json, numpy as np, pandas as pd
from pathlib import Path
REPO = Path("/Users/rytty/CCP/quant_v7")
C = REPO / "research/zb_itb/verify/yf_cache"
OUT = REPO / "research/zb_itb/round9/auctions"
RT = 0.0004  # 2 bp/side = 4 bp round trip (same convention as verify/f3_canonical.py)
DEV_END = pd.Timestamp("2025-06-30")
START = pd.Timestamp("2024-05-28")
END = pd.Timestamp("2026-10-16")

def ld(f):
    d = pd.read_parquet(C / f)
    d.index = d.index.tz_convert("America/New_York")
    return d[~d.index.duplicated()].sort_index()

ZB, ITB, SPY = ld("ZB_F_60m.parquet"), ld("ITB_60m.parquet"), ld("SPY_60m.parquet")

# ---- auction calendar (local FiscalData file: dates + tenor, no times/yields) ----
raw = json.load(open(REPO / "data/treasury/auctions_fiscaldata_raw.json"))["data"]
def tenor(term):
    m = re.match(r"(\d+)-Year(?: (\d+)-Month)?", term)
    if not m: return None
    y = int(m.group(1)) + (int(m.group(2)) / 12 if m.group(2) else 0)
    t = round(y)
    return t if t in (2, 3, 5, 7, 10, 20, 30) else None
au = []
for r in raw:
    if r.get("inflation_index_security") != "No" or r.get("floating_rate") != "No": continue  # drop TIPS and FRNs
    t = tenor(r["security_term"])
    if t is None: continue
    au.append(dict(date=pd.Timestamp(r["auction_date"]), tenor=t, type=r["security_type"], reopen=r["reopening"]))
au = pd.DataFrame(au)
au = au[(au.date >= START) & (au.date <= END)]

# ---- 2024 sample: closing time and high/avg yields (notes only, 2023-12..2024-12) ----
samp = json.load(open(REPO / "data/public_scout/treasury_auctions/notes_2024_sample.json"))
sm = pd.DataFrame([dict(date=pd.Timestamp(r["auctionDate"][:10]), tenor=tenor(r["securityTerm"]),
                        close=r.get("closingTimeCompetitive", ""), hy=r.get("highYield") or r.get("highInvestmentRate"),
                        avg=r.get("averageMedianYield")) for r in samp])
sm = sm.dropna(subset=["tenor"])
sm["hy"] = pd.to_numeric(sm.hy, errors="coerce"); sm["avg"] = pd.to_numeric(sm.avg, errors="coerce")
sm["hour"] = sm.close.map(lambda s: 11 if s.startswith("11:30") else 13 if s.startswith("01:00") else np.nan)
sm["tail_bp"] = (sm.hy - sm.avg) * 100
# result time: sample value where present, else 13:00 (documented assumption)
hour_map = sm.groupby("date").hour.max()
au["hour"] = au.date.map(hour_map).fillna(13).astype(int)
dates = au.groupby("date").agg(hour=("hour", "max"), n_auc=("tenor", "size"), tenors=("tenor", lambda s: ",".join(map(str, sorted(set(s)))))).reset_index()
AUC = set(dates.date)

def bar(df, ts):
    return df.loc[ts] if ts in df.index else None

NY = "America/New_York"
def ts(D, h, m=0):
    return pd.Timestamp(D).tz_localize(NY) + pd.Timedelta(hours=h, minutes=m)
sessions = sorted(set(pd.Timestamp(x.date()) for x in ITB.index))
sessions = [s for s in sessions if START <= s <= END]
rows = []
for i, D in enumerate(sessions):
    if i + 1 >= len(sessions): break
    nxt = sessions[i + 1]
    zb_h = dates.set_index("date").hour.get(D, 13)  # auction hour; non-auction days use 13:00 as control
    zb_bar = bar(ZB, ts(D, int(zb_h)))
    if zb_bar is None: continue
    m = np.log(zb_bar.Close / zb_bar.Open)
    if m == 0: continue
    d = np.sign(m)
    e_in = bar(ITB, ts(D, 14, 30))
    x_in = bar(ITB, ts(D, 15, 30))
    x_on = bar(ITB, ts(nxt, 9, 30))
    spy_in, spy_x = bar(SPY, ts(D, 14, 30)), bar(SPY, ts(D, 15, 30))
    spy_on = bar(SPY, ts(nxt, 9, 30))
    if e_in is None or x_in is None: continue
    intra = d * np.log(x_in.Close / e_in.Open) - RT
    over = d * np.log(x_on.Close / e_in.Open) - RT if x_on is not None else np.nan
    p_intra = d * np.log(spy_x.Close / spy_in.Open) - RT if spy_in is not None and spy_x is not None else np.nan
    p_over = d * np.log(spy_on.Close / spy_in.Open) - RT if spy_in is not None and spy_on is not None else np.nan
    rows.append(dict(date=D, d=d, zb_move_bp=m * 1e4, auction=D in AUC, hour=int(zb_h),
                     intra=intra, over=over, spy_intra=p_intra, spy_over=p_over))
ev = pd.DataFrame(rows).set_index("date")
ev["period"] = np.where(ev.index <= DEV_END, "dev", "check")
ev.to_csv(OUT / "events.csv")

def st(x):
    x = x.dropna()
    if len(x) < 3: return dict(n=len(x), mean_bp=np.nan, t=np.nan, hit=np.nan)
    return dict(n=len(x), mean_bp=x.mean() * 1e4, t=x.mean() / x.std(ddof=1) * np.sqrt(len(x)), hit=(x > 0).mean())

def table(mask_fn, rows_):
    out = []
    for name, col in rows_:
        for per in ["dev", "check", "all"]:
            s = ev[col]
            m = mask_fn(ev) & ((ev.period == per) if per != "all" else True)
            out.append(dict(group=name, period=per, **st(s[m])))
    return pd.DataFrame(out)

A = ev[ev.auction]; N = ev[~ev.auction]
print("sessions in window", len(sessions), "| auction dates", len(AUC), "| auction-day events", len(A), "| control days", len(N))
print("auction dates per period:", A.period.value_counts().to_dict())
print("hour assumption: sample-known", int(sm.hour.notna().sum()), "auction dates in sample; hour==11 in", int((dates.hour == 11).sum()))

cols = [("intra", "intra"), ("over", "over")]
res = []
for lab, mask in [("AUCTION day, ZB hour", ev.auction), ("CONTROL non-auction day, ZB 13:00 hour", ~ev.auction)]:
    for name, col in cols:
        for per in ["dev", "check", "all"]:
            mm = mask & ((ev.period == per) if per != "all" else True)
            res.append(dict(group=lab, leg=name, period=per, **st(ev.loc[mm, col])))
# FLIP: opposite direction on auction days
for name, col in cols:
    flip = -ev.loc[ev.auction, col] - 2 * RT  # net=g-RT, flipped net=-g-RT=-net-2RT
    for per in ["dev", "check", "all"]:
        mm = (flip.index.map(lambda x: ev.loc[x, "period"]) == per) if per != "all" else np.ones(len(flip), bool)
        res.append(dict(group="FLIP auction days (opposite dir)", leg=name, period=per, **st(flip[mm])))
# PLACEBO SPY on auction days, same rule
for name, col in [("intra", "spy_intra"), ("over", "spy_over")]:
    for per in ["dev", "check", "all"]:
        mm = ev.auction & ((ev.period == per) if per != "all" else True)
        res.append(dict(group="PLACEBO SPY auction days", leg=name, period=per, **st(ev.loc[mm, col])))
R = pd.DataFrame(res)
R.to_csv(OUT / "summary.csv", index=False)
pd.set_option("display.width", 200)
print(R.round(2).to_string(index=False))

# Tail proxy (2024 notes sample only): high minus average yield, vs ZB auction-hour move sign
t = sm.dropna(subset=["tail_bp"]).copy()
t = t[t.date >= START]
t = t.merge(ev[["zb_move_bp", "intra", "over"]], left_on="date", right_index=True, how="left")
print("\nTAIL proxy (hy - avg yield, 2024 notes sample, n=%d with events):" % t.intra.notna().sum())
tt = t.dropna(subset=["intra"])
if len(tt) > 3:
    print("corr(tail_bp, zb_move_bp) =", round(np.corrcoef(tt.tail_bp, tt.zb_move_bp)[0, 1], 3))
    for lab, msk in [("tail>=median", tt.tail_bp >= tt.tail_bp.median()), ("tail<median", tt.tail_bp < tt.tail_bp.median())]:
        s = tt.loc[msk]
        print(lab, "n", len(s), "intra mean bp", round(s.intra.mean() * 1e4, 2), "over mean bp", round(s.over.mean() * 1e4, 2))
    print("sign-of-tail x intra: mean(sgn(tail)*intra) bp", round((np.sign(tt.tail_bp) * tt.intra).mean() * 1e4, 2), "t", round((np.sign(tt.tail_bp) * tt.intra).mean() / (np.sign(tt.tail_bp) * tt.intra).std() * np.sqrt(len(tt)), 2))

# ---- Diagnostics and strict subset ----
from scipy import stats as sps
a_i, c_i = ev.loc[ev.auction, "intra"], ev.loc[~ev.auction, "intra"]
w = sps.ttest_ind(a_i, c_i, equal_var=False)
print("\nDIFF auction minus control, intra net: %.2f bp, Welch t %.2f" % ((a_i.mean() - c_i.mean()) * 1e4, w.statistic))
a_o, c_o = ev.loc[ev.auction, "over"].dropna(), ev.loc[~ev.auction, "over"].dropna()
w2 = sps.ttest_ind(a_o, c_o, equal_var=False)
print("DIFF auction minus control, overnight net: %.2f bp, Welch t %.2f" % ((a_o.mean() - c_o.mean()) * 1e4, w2.statistic))

# contemporaneous response: ITB 13:30 bar (closest overlap) vs ZB 13:00 bar (does ITB react at all?)
diag = []
for D, r in ev[ev.auction].iterrows():
    h = int(dates.set_index("date").hour.get(D, 13))
    ib = bar(ITB, ts(D, h, 30)); zb = bar(ZB, ts(D, h))  # ITB bars are :30-labeled; 13:30 bar = 13:30-14:30
    if ib is None or zb is None: continue
    diag.append((np.log(zb.Close / zb.Open), np.log(ib.Close / ib.Open)))
diag = np.array(diag)
if len(diag) > 5:
    beta = np.polyfit(diag[:, 0], diag[:, 1], 1)[0]
    print("same-hour ITB on ZB (auction days): n %d, corr %.2f, beta %.3f" % (len(diag), np.corrcoef(diag.T)[0, 1], beta))
    print("ZB hour move sd %.1f bp, ITB hour move sd %.1f bp" % (diag[:, 0].std() * 1e4, diag[:, 1].std() * 1e4))

# strict subset: 10-year and 30-year benchmark auctions (new issue or reopening)
bench = au.assign(d_=au.date).groupby("date").tenor.apply(lambda s: set(s))
strict = [D for D in ev[ev.auction].index if bench.get(D, set()) & {10, 30}]
es = ev.loc[strict]
print("\nSTRICT 10y/30y auction days: n %d (dev %d, check %d)" % (len(es), (es.period == 'dev').sum(), (es.period == 'check').sum()))
for per in ["dev", "check", "all"]:
    x = es if per == "all" else es[es.period == per]
    s = st(x.intra); o = st(x.over)
    print("  %-5s intra n %3d mean %6.2f bp t %5.2f | over mean %6.2f bp t %5.2f" % (per, s["n"], s["mean_bp"], s["t"], o["mean_bp"], o["t"]))
