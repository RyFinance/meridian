# Overnight home-market gap -> US-listed ETF/ADR tests. Sealed holdout: all loads filtered <= 2026-08-10.
import numpy as np, pandas as pd
from pathlib import Path
DATA = Path(__file__).parent / "data"
CUT = pd.Timestamp("2026-08-10")
D_SPLIT = pd.Timestamp("2022-06-30")   # daily: dev <= 2022-06, check 2022-07..
I_SPLIT = pd.Timestamp("2025-06-30")   # 60m: sample starts 2023-11, dev to 2025-06, check after
ETF = {"EWJ","DXJ","FXI","KWEB","MCHI","EWY","EWT","INDA","EWZ","EWW","EWG","EWU","EZU","VGK"}
ASIA = [("EWJ","N225"),("DXJ","N225"),("FXI","HSI"),("KWEB","HSI"),("MCHI","HSI"),("EWY","KS11"),
        ("EWT","TWII"),("TSM","2330.TW"),("BABA","9988.HK"),("PDD","HSI"),("JD","HSI"),("BIDU","HSI"),
        ("SONY","N225"),("TM","N225")]
EURO = [("EWG","GDAXI"),("EWU","FTSE"),("EZU","STOXX50E"),("VGK","STOXX50E"),("ASML","STOXX50E"),
        ("SAP","GDAXI"),("NVO","STOXX50E"),("HSBC","FTSE")]

def clean(t): return t.replace("^","").replace("=","_").replace(".","_")
def cps(t): return 0.0002 if t in ETF else 0.0003   # per side

def ld(kind, t):
    df = pd.read_parquet(DATA / f"{kind}_{clean(t)}.parquet")
    idx = pd.DatetimeIndex(df.index)
    if kind == "daily":
        idx = idx.tz_localize(None) if idx.tz is not None else idx
        df.index = idx.normalize(); df = df[df.index <= CUT]
    else:
        if idx.tz is not None: idx = idx.tz_convert("America/New_York")
        df.index = idx
        df = df[df.index.tz_localize(None) < CUT + pd.Timedelta(days=1)]
    return df.sort_index()

def trades(e, thr, d, sig):
    """e: event frame with sig, entry/exit OHLC. d=+1 continuation, -1 fade. returns net, net_worst, flip net."""
    s = np.sign(e[sig]); m = (e[sig].abs() > thr) & (s != 0)
    p = d * s
    gross = p * (e.ex_c / e.en_o - 1)
    worst = np.where(p > 0, e.ex_l / e.en_h - 1, 1 - e.ex_h / e.en_l)
    c2 = 2 * e.cost
    net = gross - c2
    netw = worst - c2
    flip = -gross - c2
    return pd.DataFrame({"date": e.index, "net": net, "netw": netw, "flip": flip})[m.values]

# ---------- event builders ----------
def ev_daily(A, H):
    a = ld("daily", A); h = ld("daily", H)
    hret = h.Close / h.Close.shift(1) - 1
    e = pd.DataFrame(index=a.index)
    e["en_o"] = a.Open; e["en_h"] = a.High; e["en_l"] = a.Low
    e["ex_c"] = a.Close; e["ex_h"] = a.High; e["ex_l"] = a.Low
    e["sig"] = hret.reindex(a.index)                       # home session on the same date (closed before US open)
    e["gap"] = a.Open / a.Close.shift(1) - 1               # diagnostic only (uses the open)
    e["cost"] = cps(A)
    # next home return after US date D (home session D+1 opens after US close D) for idea 2
    pos = np.searchsorted(h.index.values, a.index.values, side="right")
    e["nxt"] = np.where(pos < len(h), hret.values[np.minimum(pos, len(h) - 1)], np.nan)
    return e.dropna(subset=["en_o", "ex_c", "sig"])

def ev_intra_asia(A, H):
    """Entry at 10:30 ET bar open, exit at 15:30 bar close (16:00). Signal uses home day D (closed pre-US) and gap known by 10:30."""
    a = ld("intraday", A); a_d = ld("daily", A); h = ld("daily", H)
    hret = (h.Close / h.Close.shift(1) - 1)
    rows = []
    for D, g in a.groupby(a.index.normalize()):
        D = D.tz_localize(None)
        b930 = g[g.index.strftime("%H:%M") == "09:30"]; b1030 = g[g.index.strftime("%H:%M") == "10:30"]
        b1530 = g[g.index.strftime("%H:%M") == "15:30"]
        if len(b930) != 1 or len(b1030) != 1 or len(b1530) != 1: continue
        if D not in hret.index or D not in a_d.index: continue
        prev = a_d.Close[a_d.index < D]
        if len(prev) == 0: continue
        gap = b930.Close.iloc[0] / prev.iloc[-1] - 1
        rows.append((D, b1030.Open.iloc[0], b1030.High.iloc[0], b1030.Low.iloc[0],
                     b1530.Close.iloc[0], b1530.High.iloc[0], b1530.Low.iloc[0], hret[D], gap))
    e = pd.DataFrame(rows, columns=["date","en_o","en_h","en_l","ex_c","ex_h","ex_l","hret","gap"]).set_index("date")
    e["sig_raw"] = e.hret
    e["sig_res"] = e.hret - e.gap
    e["cost"] = cps(A)
    return e.dropna()

def ev_europe(A, E):
    """Entry at ADR/ETF 10:30 ET bar open, exit at same bar close (11:30 ET, Europe closes 11:30 ET).
    S = Europe move 09:00->10:00 ET (last bar closed by 10:00). Residual = S - ADR move 09:30->10:30."""
    a = ld("intraday", A); x = ld("intraday", E)
    rows = []
    for D, g in a.groupby(a.index.normalize()):
        D = D.tz_localize(None)
        def at(df, hm):
            r = df[df.index.strftime("%H:%M") == hm]
            return r.iloc[0] if len(r) == 1 else None
        b0930 = at(g, "09:30"); b1030 = at(g, "10:30")
        if b0930 is None or b1030 is None: continue
        xd = x[x.index.tz_localize(None).normalize() == D]
        e9 = at(xd, "08:00"); e10 = at(xd, "09:00")   # label = bar start; bar 09:00 closes at 10:00
        if e9 is None or e10 is None: continue
        S = np.log(e10.Close / e9.Close)
        adr_move = np.log(b1030.Open / b0930.Open)
        rows.append((D, b1030.Open, b1030.High, b1030.Low, b1030.Close, b1030.High, b1030.Low, S, S - adr_move))
    e = pd.DataFrame(rows, columns=["date","en_o","en_h","en_l","ex_c","ex_h","ex_l","S","res"]).set_index("date")
    e["sig_S"] = e.S; e["sig_res"] = e.res
    e["cost"] = cps(A)
    return e.dropna()

# ---------- run ----------
def summarize(tr, split):
    n = len(tr)
    if n == 0: return None
    m = tr.net.mean(); sd = tr.net.std(ddof=1)
    yrs = tr.groupby(tr.date.dt.year).net.mean().round(5).to_dict()
    return dict(split=split, n=n, win=(tr.net > 0).mean(), mean=m, t=m / (sd / np.sqrt(n)) if n > 1 else np.nan,
                avg_win=tr.net[tr.net > 0].mean(), avg_loss=tr.net[tr.net <= 0].mean(),
                mean_worst=tr.netw.mean(), flip_mean=tr.flip.mean(), years=yrs)

if __name__ == "__main__":
    rules = []; out = {}
    # ---- Idea 1a: daily home-session return (home closed before US open), ADR/ETF open->close
    for A, H in ASIA:
        e = ev_daily(A, H)
        for thr in [0.0, 0.005, 0.01, 0.02]:
            for d in [1, -1]:
                tr = trades(e, thr, d, "sig")
                for split, mask in [("dev", tr.date <= D_SPLIT), ("check", tr.date > D_SPLIT)]:
                    s = summarize(tr[mask], split)
                    if s: rules.append(dict(idea="1a_daily", pair=f"{A}/{H}", thr=thr, dir="cont" if d > 0 else "fade", **s))
        out[f"{A}/{H}_daily_e"] = e
    # ---- Idea 1b: 60m entry 10:30, raw home signal and gap-residual signal
    for A, H in ASIA:
        e = ev_intra_asia(A, H)
        for sig in ["sig_raw", "sig_res"]:
            for d in [1, -1]:
                tr = trades(e, 0.0, d, sig)
                for split, mask in [("dev", tr.date <= I_SPLIT), ("check", tr.date > I_SPLIT)]:
                    s = summarize(tr[mask], split)
                    if s: rules.append(dict(idea="1b_60m_1030", pair=f"{A}/{H}", thr=0.0, sig=sig, dir="cont" if d > 0 else "fade", **s))
    # ---- Idea 3: Europe overlap (60m), entry 10:30 ET, exit 11:30 ET
    for A, E in EURO:
        e = ev_europe(A, E)
        for sig in ["sig_S", "sig_res"]:
            for thr in [0.0, 0.003]:
                for d in [1, -1]:
                    tr = trades(e, thr, d, sig)
                    for split, mask in [("dev", tr.date <= I_SPLIT), ("check", tr.date > I_SPLIT)]:
                        s = summarize(tr[mask], split)
                        if s: rules.append(dict(idea="3_europe_1030", pair=f"{A}/{E}", thr=thr, sig=sig, dir="cont" if d > 0 else "fade", **s))
    R = pd.DataFrame(rules)
    R.to_pickle(Path(__file__).parent / "rules.pkl")
    print("rows", len(R), "families", R.idea.value_counts().to_dict())
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(R[R.split=="dev"].groupby("idea").size())
