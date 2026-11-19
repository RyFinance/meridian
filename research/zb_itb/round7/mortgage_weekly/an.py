"""Round 7 mortgage_weekly: three ideas on ITB (SPY placebo, ZB/TNX/PMMS inputs). Run from quant_v7.
Costs 2 bp/side => 4 bp round trip per trade. Splits: daily = dev <=2018-12-31, check 2019+; 60m = dev 2024-05-28..2025-06-30, check 2025-07-01..2026-10-16."""
import sys, os, shutil, numpy as np, pandas as pd
sys.path.insert(0, ".")
from research.zb_itb.verify.f3_canonical import build as f3build
C = "research/zb_itb/round7/mortgage_weekly/cache/"; VC = "research/zb_itb/verify/yf_cache/"
for f in ["SPY_1d", "SPY_60m"]:
    if not os.path.exists(C + f + ".parquet"): shutil.copy(VC + f + ".parquet", C + f + ".parquet")
RT, END, NY = 4e-4, pd.Timestamp("2026-10-16"), "America/New_York"
DSPLIT, DEV_D, CHK_D = pd.Timestamp("2018-12-31"), (pd.Timestamp("1990-01-01"), pd.Timestamp("2018-12-31")), (pd.Timestamp("2019-01-01"), END)
DEV_6, CHK_6 = (pd.Timestamp("2024-05-28"), pd.Timestamp("2025-06-30")), (pd.Timestamp("2025-07-01"), END)

def rd(n):
    d = pd.read_parquet(C + n + ".parquet")
    if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
    idx = pd.DatetimeIndex(d.index)
    if idx.tz is not None: idx = idx.tz_convert(NY).tz_localize(None) if False else idx.tz_convert(NY)
    d.index = idx
    return d[~d.index.duplicated()].sort_index()

def daily(n):
    d = rd(n); d.index = pd.DatetimeIndex(d.index).tz_localize(None).normalize() if d.index.tz is not None else d.index.normalize()
    return d

I, Z, T, S_ = daily("ITB_1d"), daily("ZB_F_1d"), daily("TNX_1d"), daily("SPY_1d")
D = pd.DataFrame({"io": I.Open, "ic": I.Close, "zc": Z.Close, "tc": T.Close, "so": S_.Open, "sc": S_.Close}).dropna()
D = D[D.index <= END]
I60, S60 = rd("ITB_60m"), rd("SPY_60m")
I60_time = I60.index
def bar(df, date, hhmm, col):
    ts = pd.Timestamp(f"{date.date()} {hhmm}").tz_localize(NY)
    return df.loc[ts, col] if ts in df.index else np.nan
PM = pd.read_csv(C + "MORTGAGE30US.csv", parse_dates=["observation_date"]).set_index("observation_date")["MORTGAGE30US"]
PM = pd.to_numeric(PM, errors="coerce").dropna()
W = pd.DataFrame({"P": PM}); W["X"] = W.P.diff()
def tnx_at(x):
    j = T.index.searchsorted(x, side="right") - 1
    return T.Close.iloc[j] if j >= 0 else np.nan
W["Y"] = [tnx_at(t - pd.Timedelta(days=1)) - tnx_at(t - pd.Timedelta(days=8)) for t in W.index]
W["beta"] = (W.X.expanding(min_periods=104).cov(W.Y) / W.Y.expanding(min_periods=104).var()).shift(1)
W["S"] = W.X - W.beta * W.Y
W["zS"] = W.S / W.S.expanding(min_periods=104).std().shift(1)
W = W[(W.index >= D.index[0]) & (W.index <= END)].dropna(subset=["S", "zS"])

def stats(x):
    x = pd.Series(x).dropna(); n = len(x)
    if n < 3: return dict(n=n, bp=np.nan, t=np.nan, hit=np.nan)
    return dict(n=n, bp=x.mean() * 1e4, t=x.mean() / x.std(ddof=1) * np.sqrt(n), hit=(x > 0).mean())

def trades_to_net(tr, flip=False, spy=False):
    ret = tr.ret_spy if spy else tr.ret_itb
    p = -tr.pos if flip else tr.pos
    return pd.Series(p * ret.values - RT, index=tr.index)

VARIANTS = {}  # name -> (trades df with date,pos,ret_itb,ret_spy), dev, chk
# ---- Idea 1: weekly PMMS surprise ----
def idea1_daily(sigcol, thr=None):
    rows = []
    for t in W.index:
        if t not in D.index: continue
        i = D.index.get_loc(t)
        if i + 1 >= len(D) or (D.index[i + 1] - t).days > 4: continue
        s = W.loc[t, sigcol]
        if thr is not None and abs(W.loc[t, "zS"]) < thr: continue
        if s == 0: continue
        rows.append(dict(date=t, pos=np.sign(-s), ret_itb=np.log(D.ic.iloc[i + 1] / D.ic.iloc[i]), ret_spy=np.log(D.sc.iloc[i + 1] / D.sc.iloc[i])))
    return pd.DataFrame(rows).set_index("date")
def idea1_60(sigcol, thr=None, to_fri=False):
    rows = []
    for t in W.index:
        if t not in D.index or t < DEV_6[0] - pd.Timedelta(days=7): continue
        o1 = bar(I60, t, "12:30:00", "Open"); c1 = bar(I60, t, "15:30:00", "Close")
        so1 = bar(S60, t, "12:30:00", "Open"); sc1 = bar(S60, t, "15:30:00", "Close")
        s = W.loc[t, sigcol]
        if thr is not None and abs(W.loc[t, "zS"]) < thr: continue
        if np.isnan(o1) or np.isnan(c1) or s == 0: continue
        i = D.index.get_loc(t)
        if to_fri:
            if i + 1 >= len(D) or (D.index[i + 1] - t).days > 4: continue
            ri, rs = np.log(D.ic.iloc[i + 1] / o1), np.log(D.sc.iloc[i + 1] / so1)
        else:
            ri, rs = np.log(c1 / o1), np.log(sc1 / so1)
        rows.append(dict(date=t, pos=np.sign(-s), ret_itb=ri, ret_spy=rs))
    return pd.DataFrame(rows).set_index("date")
VARIANTS["1A PMMS surprise S, Thu close->Fri close (daily)"] = (idea1_daily("S"), DEV_D, CHK_D)
VARIANTS["1B as 1A, |zS|>0.5 only"] = (idea1_daily("S", 0.5), DEV_D, CHK_D)
VARIANTS["1C raw PMMS change X, Thu close->Fri close"] = (idea1_daily("X"), DEV_D, CHK_D)
VARIANTS["1D PMMS surprise S, 60m Thu 12:30->16:00"] = (idea1_60("S"), DEV_6, CHK_6)
VARIANTS["1E PMMS surprise S, 60m Thu 12:30->Fri close"] = (idea1_60("S", to_fri=True), DEV_6, CHK_6)
VARIANTS["1F as 1D, |zS|>0.5 only"] = (idea1_60("S", 0.5), DEV_6, CHK_6)

# ---- Idea 2: multi-day rate trend -> next-day ITB open->close ----
TNX5 = (D.tc - D.tc.shift(5)) * 100
ZB5 = np.log(D.zc / D.zc.shift(5))
def idea2(sig, sgn, use_thr):
    a = sig.abs()
    thr = a.expanding(min_periods=250).quantile(0.7).shift(1) if use_thr else pd.Series(0.0, index=D.index)
    pos = sgn * np.sign(sig) * (a > thr)
    pos_prev = pos.shift(1)
    tr = pd.DataFrame({"pos": pos_prev, "ret_itb": np.log(D.ic / D.io), "ret_spy": np.log(D.sc / D.so)})
    tr = tr[tr.pos != 0].dropna()
    return tr
VARIANTS["2A TNX 5d chg (bp), next-day ITB open->close"] = (idea2(TNX5, -1, False), DEV_D, CHK_D)
VARIANTS["2B as 2A, top-30% |chg| only"] = (idea2(TNX5, -1, True), DEV_D, CHK_D)
VARIANTS["2C ZB 5d return, next-day ITB open->close"] = (idea2(ZB5, +1, False), DEV_D, CHK_D)
VARIANTS["2D as 2C, top-30% |ret| only"] = (idea2(ZB5, +1, True), DEV_D, CHK_D)

# ---- Idea 3: ITB vs ZB daily residual, past-only rolling beta; trade ITB close(t+1) -> close(t+1+k) ----
rI, rZ = np.log(D.ic / D.ic.shift(1)), np.log(D.zc / D.zc.shift(1))
beta = (rI.rolling(120).cov(rZ) / rZ.rolling(120).var()).shift(1)
e = rI - beta * rZ
zE = e / e.rolling(120).std().shift(1)
zR = rI / rI.rolling(120).std().shift(1)
def idea3(z, thr, k):
    rows, free = [], 0
    n = len(D); idx = D.index
    for i in range(130, n - 1 - k):
        if i < free or np.isnan(z.iloc[i]) or abs(z.iloc[i]) <= thr: continue
        j0, j1 = i + 1, i + 1 + k
        rows.append(dict(date=idx[i], pos=-np.sign(z.iloc[i]),
                         ret_itb=np.log(D.ic.iloc[j1] / D.ic.iloc[j0]), ret_spy=np.log(S_.Close.reindex(idx).iloc[j1] / S_.Close.reindex(idx).iloc[j0])))
        free = j1
    return pd.DataFrame(rows).set_index("date")
for thr in [1.0, 2.0]:
    for k in [1, 3, 5]:
        VARIANTS[f"3 resid(ITB|ZB) thr {thr} hold {k}d"] = (idea3(zE, thr, k), DEV_D, CHK_D)
for k in [1, 3, 5]:
    VARIANTS[f"3 raw ITB z thr 2.0 hold {k}d"] = (idea3(zR, 2.0, k), DEV_D, CHK_D)

# ---- report ----
rows, main = [], []
for name, (tr, dev, chk) in VARIANTS.items():
    tr = tr.copy()
    for lab, flip, spy in [("main", False, False), ("flip", True, False), ("SPY", False, True)]:
        net = trades_to_net(tr, flip, spy)
        d, c = stats(net[(net.index >= dev[0]) & (net.index <= dev[1])]), stats(net[(net.index >= chk[0]) & (net.index <= chk[1])])
        rows.append(dict(variant=name, ctrl=lab, dev_n=d["n"], dev_bp=d["bp"], dev_t=d["t"], chk_n=c["n"], chk_bp=c["bp"], chk_t=c["t"], chk_hit=c["hit"]))
R = pd.DataFrame(rows)
R.to_csv(C.replace("cache/", "") + "results.csv", index=False)
pd.set_option("display.width", 250)
print(R.round(2).to_string(index=False))
print("\nmain variants tried:", sum(1 for k in VARIANTS))
# overnight control for idea 2 (2024-05+ with f3 overnight d)
r3 = f3build("ITB")
dn = r3["d"].reindex(D.index)
for name in ["2A TNX 5d chg (bp), next-day ITB open->close", "2C ZB 5d return, next-day ITB open->close"]:
    tr = VARIANTS[name][0]
    sub = tr[tr.index >= pd.Timestamp("2024-05-28")].copy()
    nxt = [D.index[D.index.get_loc(t) + 1] for t in sub.index if D.index.get_loc(t) + 1 < len(D)]
    y = np.log(D.ic / D.io).reindex(nxt).values
    x1 = sub.pos.values[:len(y)]
    dd = dn.reindex(nxt).values
    ok = ~np.isnan(y) & ~np.isnan(dd)
    X = np.column_stack([np.ones(ok.sum()), x1[ok], dd[ok]])
    # trade-direction variable alone and controlling for overnight d (sign)
    beta_hat, *_ = np.linalg.lstsq(X, y[ok], rcond=None)
    res = y[ok] - X @ beta_hat; s2 = res @ res / (ok.sum() - 3)
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    print(f"overnight control 2024+ {name}: n={ok.sum()} pos coef={beta_hat[1]*1e4:.1f}bp t={beta_hat[1]/se[1]:.2f} | overnight d coef t={beta_hat[2]/se[2]:.2f}")
