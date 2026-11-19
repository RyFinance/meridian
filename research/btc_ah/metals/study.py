"""Metals overnight-gap study. Hourly yfinance bars (cached by pull.py), sealed at 2026-08-10.

Timeline (ET), all decisions use only data stamped before the decision time:
  16:00 prev  futures open (=price at 16:00); equity close = 15:30 RTH bar close (=16:00)
  08:00       futures 08:00 bar open (=08:00 price); equity 08:00 pre-market bar close (=09:00 price)
  09:00       futures 09:00 bar open (=09:00 price)  -> signals a,b,c use data up to 09:00
  09:30       equity entry (open of 09:30 bar) for signals a,b,c
  10:00       futures 10:00 bar open (=10:00 price) -> signal d; equity entry at 10:30 bar open
Holds: FH = close of the entry bar (1 hour); OC = close of 15:30 bar (16:00).
Variants: 4 signals x 2 thresholds (k sigma, k in {0,1}) x 2 holds = 16 per pair, 15 pairs = 240.
Follow = sign(signal). Flip (fade) is reported as the control.
Dev = trade date <= 2025-06-30, check = 2025-07-01..2026-08-10.
"""
from pathlib import Path
import numpy as np
import pandas as pd

H = Path(__file__).parent
C = H / "cache"
HOLDOUT = pd.Timestamp("2026-08-11", tz="America/New_York")
DEV_END = "2025-06-30"
PAIRS = [  # (metal, equity, cost bp per side): 2 liquid ETFs, 3 stocks, 10 for names that traded under $5 (KGC, AG, HL)
    ("GC_F", "GLD", 2), ("GC_F", "GDX", 2), ("GC_F", "GDXJ", 2), ("GC_F", "NUGT", 2),
    ("GC_F", "NEM", 3), ("GC_F", "GOLD", 3), ("GC_F", "AEM", 3), ("GC_F", "KGC", 10),
    ("SI_F", "SLV", 2), ("SI_F", "PAAS", 3), ("SI_F", "AG", 10), ("SI_F", "HL", 10),
    ("HG_F", "FCX", 3), ("HG_F", "SCCO", 3), ("HG_F", "COPX", 2),
]
WIN = 60   # past-only rolling window (trading days)
MINP = 40


def load(sym: str) -> pd.DataFrame:
    df = pd.read_parquet(C / f"{sym}.parquet")
    df = df[df.index < HOLDOUT]                       # sealed holdout, re-applied
    assert df.index.is_unique
    df = df.assign(d=df.index.strftime("%Y-%m-%d"), hm=df.index.strftime("%H:%M"))
    return df.set_index(["d", "hm"])[["open", "high", "low", "close"]].sort_index()


def get(df: pd.DataFrame, d: str, hm: str, col: str) -> float:
    try:
        v = df.at[(d, hm), col]
        return float(v)
    except KeyError:
        return np.nan


def day_table(metal: str, eq: str) -> pd.DataFrame:
    fm, em = load(metal), load(eq)
    eq_days = sorted({d for d, hm in em.index if hm == "15:30"})
    rows = []
    for i in range(1, len(eq_days)):
        dp, d = eq_days[i - 1], eq_days[i]
        r = dict(date=d, prev=dp)
        r["eq_close_prev"] = get(em, dp, "15:30", "close")
        r["eq_pm09"] = get(em, d, "08:00", "close")          # price at 09:00
        r["f16p"] = get(fm, dp, "16:00", "open")               # price at 16:00 prev
        r["f08"] = get(fm, d, "08:00", "open")
        r["f09"] = get(fm, d, "09:00", "open")
        r["f10"] = get(fm, d, "10:00", "open")
        for tag, hm in [("e930", "09:30"), ("e1030", "10:30")]:
            r[f"{tag}_o"] = get(em, d, hm, "open")
            r[f"{tag}_h"] = get(em, d, hm, "high")
            r[f"{tag}_l"] = get(em, d, hm, "low")
            r[f"{tag}_c"] = get(em, d, hm, "close")
        r["oc_c"] = get(em, d, "15:30", "close")
        r["oc_h"] = get(em, d, "15:30", "high")
        r["oc_l"] = get(em, d, "15:30", "low")
        rows.append(r)
    t = pd.DataFrame(rows).set_index("date")
    return t.dropna(subset=["eq_close_prev", "eq_pm09", "f16p", "f08", "f09", "f10",
                             "e930_o", "e930_c", "oc_c"])


def signals(t: pd.DataFrame) -> pd.DataFrame:
    """Each signal is known at its decision time; rolling stats use only prior days."""
    fut_on = np.log(t.f09 / t.f16p)
    eq_on = np.log(t.eq_pm09 / t.eq_close_prev)
    # past-only rolling OLS beta of equity overnight move on futures overnight move
    x, y = fut_on.shift(1), eq_on.shift(1)
    cov = (x * y).rolling(WIN, min_periods=MINP).mean() - x.rolling(WIN, min_periods=MINP).mean() * y.rolling(WIN, min_periods=MINP).mean()
    var = (x * x).rolling(WIN, min_periods=MINP).mean() - x.rolling(WIN, min_periods=MINP).mean() ** 2
    beta = cov / var
    s = {
        "a_fut_on": fut_on,                       # futures 16:00->09:00 raw
        "b_resid": beta * fut_on - eq_on,         # equity lag vs beta-implied move (+ = equity lagging)
        "c_comex": np.log(t.f09 / t.f08),         # futures 08:00->09:00 (COMEX open window)
        "d_london": np.log(t.f10 / t.f09),        # futures 09:00->10:00 (10:30 window proxy), entry 10:30
    }
    out = pd.DataFrame(index=t.index)
    for k, v in s.items():
        sig = v
        sd = sig.shift(1).rolling(WIN, min_periods=MINP).std()
        out[k] = sig
        out[k + "_sd"] = sd
    out["beta"] = beta
    return out


def trades(t: pd.DataFrame, sg: pd.DataFrame, cost: float, worst: bool = False) -> pd.DataFrame:
    recs = []
    for name in ["a_fut_on", "b_resid", "c_comex", "d_london"]:
        entry_tag = "e1030" if name == "d_london" else "e930"
        s = sg[name]
        sd = sg[name + "_sd"]
        for k in [0, 1]:
            ok = s.notna() & sd.notna() & (s.abs() > k * sd) & (s != 0)
            for hold in ["FH", "OC"]:
                idx = ok[ok].index
                for d in idx:
                    r = t.loc[d]
                    sign = 1.0 if s.loc[d] > 0 else -1.0
                    if not worst:
                        pin = r[f"{entry_tag}_o"]
                        pout = r[f"{entry_tag}_c"] if hold == "FH" else r["oc_c"]
                    else:
                        pin = r[f"{entry_tag}_h"] if sign > 0 else r[f"{entry_tag}_l"]
                        if hold == "FH":
                            pout = r[f"{entry_tag}_l"] if sign > 0 else r[f"{entry_tag}_h"]
                        else:
                            pout = r["oc_l"] if sign > 0 else r["oc_h"]
                    g = sign * (pout / pin - 1.0) * 1e4          # gross bp
                    c2 = 2 * cost                                 # round-trip cost bp
                    recs.append(dict(sig=name, k=k, hold=hold, date=d, sign=sign,
                                     gross=g, net=g - c2, flip_net=-g - c2))
    return pd.DataFrame(recs)


def stats(x: pd.Series) -> dict:
    n = len(x)
    if n < 2:
        return dict(n=n, mean=np.nan, t=np.nan, win=np.nan)
    sd = x.std(ddof=1)
    return dict(n=n, mean=x.mean(), t=x.mean() / (sd / np.sqrt(n)) if sd > 0 else np.nan,
                win=(x > 0).mean())


def main() -> None:
    all_tr = []
    for metal, eq, cost in PAIRS:
        t = day_table(metal, eq)
        sg = signals(t)
        tr = trades(t, sg, cost)
        tr["metal"], tr["eq"] = metal, eq
        all_tr.append(tr)
        print(f"{eq:5s} days={len(t)} trades={len(tr)}", flush=True)
    T = pd.concat(all_tr, ignore_index=True)
    T["period"] = np.where(T.date <= DEV_END, "dev", "check")
    T["year"] = T.date.str[:4]
    T.to_parquet(H / "all_trades.parquet", index=False)

    rows = []
    for (eq, sig, k, hold), g in T.groupby(["eq", "sig", "k", "hold"]):
        r = dict(eq=eq, sig=sig, k=k, hold=hold)
        for per in ["dev", "check"]:
            gg = g[g.period == per]
            s = stats(gg.net)
            r.update({f"{per}_n": s["n"], f"{per}_mean": s["mean"], f"{per}_t": s["t"], f"{per}_win": s["win"]})
            r[f"{per}_flip_mean"] = gg.flip_net.mean() if len(gg) else np.nan
            r[f"{per}_flip_t"] = stats(gg.flip_net)["t"]
        rows.append(r)
    R = pd.DataFrame(rows)
    R.to_csv(H / "variants_summary.csv", index=False)
    print("variants:", len(R))
    R.to_csv(H / "variants_summary.csv", index=False)


if __name__ == "__main__":
    main()
