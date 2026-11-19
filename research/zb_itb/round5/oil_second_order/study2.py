"""Clean run. Start-labeled bars. d = sign(futures 08:00 bar close / prior 15:00 bar close), both ET.
Entry = 09:30 bar Open. Exits: 10:30 = close of 09:30 bar; 11:30 = close of 10:30 bar; close = last regular bar close.
Net = sgn * d * log(exit/entry) - round trip cost. sgn=-1 is the brief's hypothesis for oil users; +1 is the flip."""
import pandas as pd, numpy as np
C = "research/zb_itb/round5/oil_second_order/cache/"
DEV = (pd.Timestamp("2024-05-28"), pd.Timestamp("2025-06-30"))
CHK = (pd.Timestamp("2025-07-01"), pd.Timestamp("2026-10-16"))
EX = ["10:30", "11:30", "close"]
def ld(f):
    d = pd.read_parquet(C + f); d.index = d.index.tz_convert("America/New_York"); return d
def T(s): return pd.Timestamp(s).time()
def day_index(x):
    return x.index.normalize().tz_localize(None)

def signal(fut):
    f = ld(f"{fut}_60m.parquet")
    c8 = f[f.index.time == T("08:00")]; c15 = f[f.index.time == T("15:00")]
    return pd.Series(c8.Close.values, index=day_index(c8)), pd.Series(c15.Close.values, index=day_index(c15))

def prices(stock):
    e = ld(f"{stock}_60m.parquet"); g = pd.DataFrame(index=pd.Index(sorted(set(day_index(e))), name="day"))
    rows = {}
    for day, gg in e.groupby(day_index(e)):
        o = gg[gg.index.time == T("09:30")]; x1 = gg[gg.index.time == T("09:30")]; x2 = gg[gg.index.time == T("10:30")]
        reg = gg[gg.index.time <= T("15:30")]
        if len(o) == 0 or len(x1) == 0 or len(x2) == 0 or len(reg) == 0: continue
        rows[day] = dict(entry=o.Open.iloc[0], **{"10:30": x1.Close.iloc[0], "11:30": x2.Close.iloc[0], "close": reg.Close.iloc[-1]})
    return pd.DataFrame(rows).T

def dsig(fut):
    c8, c15 = signal(fut)
    days = sorted(set(day_index(ld("SPY_60m.parquet"))))
    d = {}
    for i in range(1, len(days)):
        D, P = days[i], days[i - 1]
        if D in c8.index and P in c15.index:
            d[D] = np.sign(np.log(c8[D] / c15[P]))
    return pd.Series(d)

def adv(stock):
    x = pd.read_parquet(C + f"{stock}_1d.parquet")
    return float((x["Close"] * x["Volume"]).tail(250).median())

def cost_bp(stock):
    return 2.0 if adv(stock) >= 1e8 else 5.0

def net_series(stock, fut, sgn, exit_):
    p = prices(stock); d = dsig(fut)
    idx = p.index.intersection(d.index)
    g = np.log(p.loc[idx, exit_].astype(float) / p.loc[idx, "entry"].astype(float))
    s = (sgn * d.loc[idx] * g).where(d.loc[idx] != 0).dropna()
    return s - 2 * cost_bp(stock) / 1e4

def uncond(stock, exit_):
    p = prices(stock)
    return np.log(p[exit_].astype(float) / p["entry"].astype(float))

def st(x):
    x = x.dropna()
    if len(x) < 5: return dict(n=len(x), mean=np.nan, t=np.nan, win=np.nan)
    return dict(n=len(x), mean=x.mean() * 1e4, t=x.mean() / x.std() * np.sqrt(len(x)), win=(x > 0).mean() * 100)
def split(s):
    return s[(s.index >= DEV[0]) & (s.index <= DEV[1])], s[(s.index >= CHK[0]) & (s.index <= CHK[1])]

GROUPS = {
    "oil": {"airlines": ["JETS", "DAL", "UAL", "AAL", "LUV", "ALK"], "cruise": ["CCL", "RCL", "NCLH"],
            "truck_parcel": ["ODFL", "JBHT", "FDX", "UPS"], "chem": ["DOW", "LYB"], "refiners": ["VLO", "MPC", "PSX"]},
    "ng": {"utilities": ["XLU", "NEE", "DUK"], "fertilizer": ["CF", "NTR"]},
}
FUT = {"oil": "CL_F", "ng": "NG_F"}
CTRL = {"oil": ["SPY", "USO", "XLE"], "ng": ["SPY"]}

rows = []; series = {}
for sig, grp in GROUPS.items():
    for gname, names in grp.items():
        for stock in names + CTRL[sig]:
            role = "control" if stock in CTRL[sig] else "name"
            for ex in EX:
                for sgn in [-1, +1]:
                    s = net_series(stock, FUT[sig], sgn, ex)
                    series[(sig, stock, ex, sgn)] = s
                    dv, ck = split(s)
                    rows.append(dict(signal=sig, group=gname, name=stock, role=role, exit=ex, sign="-d" if sgn < 0 else "+d",
                                     cost=cost_bp(stock), adv_musd=round(adv(stock) / 1e6), dev_n=st(dv)["n"], dev_mean=st(dv)["mean"], dev_t=st(dv)["t"],
                                     dev_win=st(dv)["win"], chk_n=st(ck)["n"], chk_mean=st(ck)["mean"], chk_t=st(ck)["t"], chk_win=st(ck)["win"]))
                    if sgn < 0 and role == "name":
                        u = uncond(stock, ex).dropna()
                        rows[-1]["drift_always_short_bp"] = round(-st(u)["mean"], 2)
R = pd.DataFrame(rows)
R.to_csv("research/zb_itb/round5/oil_second_order/results_clean.csv", index=False)

# Composite baskets (equal weight across names, pre-specified sign -d, one trade per name per day)
comp = []
for sig, grp in GROUPS.items():
    names = [n for g in grp.values() for n in g]
    for ex in EX:
        for sgn in [-1, +1]:
            M = pd.concat([series[(sig, n, ex, sgn)].rename(n) for n in names], axis=1)
            cs = M.mean(axis=1)
            dv, ck = split(cs)
            comp.append(dict(basket=sig, exit=ex, sign="-d" if sgn < 0 else "+d", names=len(names), dev_n=st(dv)["n"], dev_mean=st(dv)["mean"], dev_t=st(dv)["t"], chk_n=st(ck)["n"], chk_mean=st(ck)["mean"], chk_t=st(ck)["t"], chk_win=st(ck)["win"]))
C2 = pd.DataFrame(comp)
C2.to_csv("research/zb_itb/round5/oil_second_order/composite.csv", index=False)

pd.set_option("display.width", 260); pd.set_option("display.max_rows", 400)
print("=== PER NAME (names only) ===")
print(R[R.role == "name"].round(2).to_string(index=False))
print("=== CONTROLS ===")
print(R[R.role == "control"].round(2).to_string(index=False))
print("=== COMPOSITE BASKETS ===")
print(C2.round(2).to_string(index=False))
n_name = int((R.role == "name").sum()); print("name variants:", n_name, "| all rows incl controls:", len(R))
