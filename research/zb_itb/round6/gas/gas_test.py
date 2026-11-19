"""Round 6: overnight NG=F / CL=F signal -> gas and oil equities, first hour (09:30 open -> 10:30 / 11:30 / close).
Signal: d = sign(log(FUT 08:00-bar close on D / FUT 15:00-bar close on prev session)); start-labeled bars.
Entry: daily Open (MOO). Exits: 09:30-bar close (10:30), 10:30-bar close (11:30), daily Close.
Net = gross - 2 * side_bp (round trip). Side cost by median dev $ADV: >=300M 2bp, 20M-300M 5bp, <20M 10bp.
"""
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).parent; DATA = HERE / "data"; NY = "America/New_York"
DEV = (pd.Timestamp("2024-05-28"), pd.Timestamp("2025-06-30"))
CHK = (pd.Timestamp("2025-07-01"), pd.Timestamp("2026-10-16"))
EXITS = {"1030": "x1030", "1130": "x1130", "close": "xc"}
GAS = ["EQT", "RRC", "AR", "CNX", "EXE", "LNG", "NFE", "KOLD", "BOIL", "FCG"]
OIL = ["XOP", "OIH", "RIG", "VAL", "NOG", "MTDR", "SM", "FRO", "STNG", "USO", "XLE"]
MISSING = ["CTRA", "CHK", "SWN", "TELL", "CIVI"]
EXCLUDE = ["NFE"]  # 60m vs daily prices inconsistent (split-type breaks); unusable

def load(sym, iv):
    f = DATA / f"{sym.replace('=', '_')}_{iv}.parquet"
    if not f.exists(): return None
    d = pd.read_parquet(f)
    if iv == "60m":
        d.index = d.index.tz_convert(NY) if d.index.tz is not None else d.index.tz_localize(NY)
    else:
        d.index = pd.DatetimeIndex(d.index).tz_localize(None).normalize()
    return d.sort_index()

SPY1d = load("SPY", "1d")
SESS = [d for d in SPY1d.index if d >= pd.Timestamp("2024-05-01") and d <= pd.Timestamp("2026-10-16")]
def at(ts): return ts.tz_localize(NY)

def signal(fut):
    out = {}
    for i in range(1, len(SESS)):
        D, P = SESS[i], SESS[i - 1]
        t1, t0 = at(D + pd.Timedelta(hours=8)), at(P + pd.Timedelta(hours=15))
        if t1 in fut.index and t0 in fut.index:
            m = np.log(fut.at[t1, "Close"] / fut.at[t0, "Close"])
            out[D] = np.sign(m) if m != 0 else np.nan
    return pd.Series(out, dtype=float)

BAD = {}
def target(sym):
    d1, d60 = load(sym, "1d"), load(sym, "60m")
    if d1 is None or d60 is None: return None
    rows = {}
    for D in SESS:
        if D not in d1.index: continue
        o, c = d1.at[D, "Open"], d1.at[D, "Close"]
        b930, b1030 = at(D + pd.Timedelta(hours=9.5)), at(D + pd.Timedelta(hours=10.5))
        if b930 not in d60.index or b1030 not in d60.index or not np.isfinite(o): continue
        if abs(np.log(d60.at[b930, "Open"] / o)) > 0.2: BAD[sym] = BAD.get(sym, 0) + 1; continue  # split-type break check only (>20%)
        rows[D] = {"x1030": np.log(d60.at[b930, "Close"] / o), "x1130": np.log(d60.at[b1030, "Close"] / o),
                   "xc": np.log(c / o), "adv": (d1.loc[:D].tail(60)["Close"] * d1.loc[:D].tail(60)["Volume"]).median()}
    return pd.DataFrame(rows).T.astype(float)

def side_cost(adv, etf=False):
    if adv >= 300e6: return 2.0
    if adv >= 20e6: return 5.0
    return 10.0

def stats(x):
    x = x.dropna()
    n = len(x)
    if n < 5: return dict(n=n, mean=np.nan, t=np.nan, hit=np.nan)
    return dict(n=n, mean=x.mean() * 1e4, t=x.mean() / x.std(ddof=1) * np.sqrt(n), hit=(x > 0).mean())

FUT = {"NG": signal(load("NG=F", "60m")), "CL": signal(load("CL=F", "60m"))}
print("signal counts NG:", FUT["NG"].value_counts(dropna=False).to_dict())
print("signal counts CL:", FUT["CL"].value_counts(dropna=False).to_dict())

# sanity check on bar timing: 09:30 bar open should equal daily open for SPY
s60 = load("SPY", "60m"); bad = []
for D in SESS[-300:]:
    b = at(D + pd.Timedelta(hours=9.5))
    if b in s60.index: bad.append(abs(s60.at[b, "Open"] / SPY1d.at[D, "Open"] - 1))
print(f"timing check SPY 09:30 bar open vs daily open: n={len(bad)}, median abs diff={np.median(bad)*1e4:.2f} bp")

TG = {}
for s in [x for x in GAS + OIL + ["SPY"] if x not in EXCLUDE]:
    t = target(s)
    if t is None: print("no data:", s); continue
    TG[s] = t
    print(f"{s}: dropped(open mismatch)={BAD.get(s,0)} days={len(t)} dev={len(t.loc[DEV[0]:DEV[1]])} chk={len(t.loc[CHK[0]:CHK[1]])} "
          f"ADV(med)=${t.adv.median()/1e6:.0f}M cost={side_cost(t.adv.median())}bp")

def run(sig_name, sym, sign=1, exit_key="x1030"):
    t = TG[sym]; d = FUT[sig_name].reindex(t.index).dropna() * sign
    d = d[d != 0]
    cost = side_cost(t.adv.median()) if sym != "SPY" else 2.0
    g = (d * t.loc[d.index, exit_key]).dropna()
    net = g - 2 * cost / 1e4
    res = {}
    for w, (a, b) in {"dev": DEV, "chk": CHK}.items():
        res[w] = stats(net.loc[a:b])
    return res, cost

rows = []
# primary families: NG -> gas names, CL -> oil names; controls: SPY placebo, flip (sign -1), wrong-signal (CL->gas, NG->oil)
fam = [("NG", s, "gas") for s in GAS if s in TG] + [("CL", s, "oil") for s in OIL if s in TG]
ctrl = [("NG", "SPY", "placebo"), ("CL", "SPY", "placebo")] + \
       [("CL", s, "wrong") for s in GAS if s in TG] + [("NG", s, "wrong") for s in OIL if s in TG]
for sig, s, kind in fam + ctrl:
    for ek, col in EXITS.items():
        res, cost = run(sig, s, 1, col)
        rows.append(dict(family=kind, sig=sig, sym=s, exit=ek, cost=cost,
                         dev_n=res["dev"]["n"], dev_bp=res["dev"]["mean"], dev_t=res["dev"]["t"],
                         chk_n=res["chk"]["n"], chk_bp=res["chk"]["mean"], chk_t=res["chk"]["t"], chk_hit=res["chk"]["hit"]))
        if kind in ("gas", "oil", "placebo"):
            res2, _ = run(sig, s, -1, col)
            rows[-1].update(flip_dev_bp=res2["dev"]["mean"], flip_dev_t=res2["dev"]["t"],
                            flip_chk_bp=res2["chk"]["mean"], flip_chk_t=res2["chk"]["t"])
R = pd.DataFrame(rows)
R.to_csv(HERE / "gas_results.csv", index=False)
pd.set_option("display.width", 250)
print(R.round(2).to_string(index=False))
print("total variants (all rows):", len(R), "| primary family rows:", int((R.family.isin(['gas','oil'])).sum()))
