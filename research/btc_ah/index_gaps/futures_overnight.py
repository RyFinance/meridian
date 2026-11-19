"""Overnight futures path (ES=F / NQ=F, 1h bars, ET) vs SPY / QQQ equity open.

Bars are labelled by START time in ET (yfinance). Segments (prices are bar CLOSES):
  asia   = 16:00 -> 02:00 ET   (close of bar starting 15:00 -> close of bar starting 01:00)
  europe = 02:00 -> 08:00 ET   (close of bar starting 01:00 -> close of bar starting 07:00)
  late   = 08:00 -> 09:00 ET   (close of bar starting 07:00 -> close of bar starting 08:00)
Everything the signal uses is known by 09:00 ET, before the 09:30 equity open.
Outcomes (SPY/QQQ): gap (prev close -> 09:30 open), first hour (09:30 open -> 10:30 close), open->close.
Sealed holdout: cut at 2026-08-10. Dev = <= 2025-06-30 (the futures sample starts 2024-05-24), check = after.
Costs: 2bp per side ETF = 4bp round trip, applied to any traded rule.
"""
import math
import numpy as np
import pandas as pd

C = "/Users/rytty/CCP/quant_v7/research/btc_ah/index_gaps/cache"
OUT = "/Users/rytty/CCP/quant_v7/research/btc_ah/index_gaps"
END = pd.Timestamp("2026-08-10")
SPLIT = pd.Timestamp("2025-06-30")
RT = 0.0004


def fut_close_at(fut, day, hour):
    """Close of the 1h bar that starts at (day, hour ET). Returns NaN if missing."""
    key = pd.Timestamp(day).tz_localize("America/New_York") + pd.Timedelta(hours=hour)
    return fut["Close"].get(key, np.nan)


def ols(y, X):
    X1 = np.column_stack([np.ones(len(y)), X])
    b, *_ = np.linalg.lstsq(X1, y, rcond=None)
    resid = y - X1 @ b
    s2 = resid @ resid / (len(y) - X1.shape[1])
    cov = s2 * np.linalg.inv(X1.T @ X1)
    se = np.sqrt(np.diag(cov))
    return b, b / se


def daily_frame(fut_sym, eq_sym):
    fut = pd.read_parquet(f"{C}/{fut_sym}_60m.parquet")
    fut.index = fut.index.tz_convert("America/New_York")
    fut = fut[fut.index.tz_localize(None) < END]
    eq = pd.read_parquet(f"{C}/{eq_sym}_1d.parquet")
    eq.index = pd.to_datetime(eq.index).tz_localize(None)
    eq = eq[eq.index <= END].astype(float)
    f = eq["Adj Close"] / eq["Close"]
    O = eq.Open * f
    Cc = eq.Close * f
    prevC = Cc.shift(1)
    h1 = pd.read_parquet(f"{C}/{eq_sym}_60m.parquet")
    h1.index = h1.index.tz_convert("America/New_York")
    h1 = h1[h1.index.tz_localize(None) < END]
    # first hour: 09:30 bar open -> 09:30 bar close (10:30)
    fh_close, fh_open = {}, {}
    for ts, row in h1.iterrows():
        if ts.hour == 9 and ts.minute == 30:
            d = ts.tz_localize(None).normalize()
            fh_close[d] = row["Close"] * (f.get(d, np.nan))
    rows = []
    days = eq.index[eq.index >= pd.Timestamp("2024-05-24")]
    prev_day = None
    for d in days:
        # prior 16:00 ET print = close of bar starting 15:00 on the previous trading day that has one
        prevd = d - pd.Timedelta(days=1)
        p16 = np.nan
        for k in range(1, 5):
            p16 = fut_close_at(fut, d - pd.Timedelta(days=k), 15)
            if not np.isnan(p16):
                break
        if np.isnan(p16):
            continue
        # ES trades from Sunday 18:00: the bar starts on calendar day d-1 (Sun-Thu). use the same-day list
        p01 = fut_close_at(fut, d, 1)   # 01:00 bar close = 02:00 ET
        p07 = fut_close_at(fut, d, 7)   # close of bar starting 07:00 = 08:00 ET
        p08 = fut_close_at(fut, d, 8)   # close at 09:00
        rows.append(dict(date=d, p16=p16, p01=p01, p07=p07, p08=p08,
                         O=O.get(d), C=Cc.get(d), PC=prevC.get(d), FH=fh_close.get(d, np.nan)))
    x = pd.DataFrame(rows).set_index("date").dropna()
    x["asia"] = np.log(x.p01 / x.p16)
    x["europe"] = np.log(x.p07 / x.p01)
    x["late"] = np.log(x.p08 / x.p07)
    x["gap"] = np.log(x.O / x.PC)
    x["fh"] = np.log(x.FH / x.O)
    x["oc"] = np.log(x.C / x.O)
    x["overnight"] = np.log(x.O / x.p16)
    return x


def run(fut_sym, eq_sym):
    x = daily_frame(fut_sym, eq_sym)
    print(f"\n### {fut_sym} vs {eq_sym}: n={len(x)} {x.index.min().date()} .. {x.index.max().date()}")
    print("sd (%)  asia {:.3f}  europe {:.3f}  late {:.3f}  gap {:.3f}  fh {:.3f}  oc {:.3f}".format(
        *(100 * x[c].std() for c in ["asia", "europe", "late", "gap", "fh", "oc"])))
    corr = x[["asia", "europe", "late", "gap", "fh", "oc"]].corr()
    print(corr.round(3).to_string())
    out = []
    for tgt in ["gap", "fh", "oc"]:
        for seg in [["asia"], ["europe"], ["late"], ["asia", "europe", "late"]]:
            b, t = ols(x[tgt].values, x[seg].values)
            out.append(dict(fut=fut_sym, target=tgt, regressors="+".join(seg),
                            beta=" ".join(f"{v:.2f}" for v in b[1:]),
                            t=" ".join(f"{v:.2f}" for v in t[1:]),
                            r2=1 - ((x[tgt] - (b[0] + x[seg].values @ b[1:])) ** 2).sum() / ((x[tgt] - x[tgt].mean()) ** 2).sum()))
    print(pd.DataFrame(out).round(4).to_string(index=False))
    # Rule: trade the eq at 09:30 in the sign of the segment move; exit at 16:00 close; 4bp RT
    rules = []
    for seg in ["asia", "europe", "late"]:
        for sgn_name, sg in [("follow", 1), ("fade", -1)]:
            p = sg * np.sign(x[seg].values)
            net = p * (np.exp(x.oc.values) - 1) - RT
            # classic arithmetic return: exit at close, entry at open
            net = p * (np.exp(x.oc.values) - 1) - RT
            for part, mask in [("dev", x.index <= SPLIT), ("chk", x.index > SPLIT)]:
                nn = net[mask]
                m = nn.mean()
                sd = nn.std(ddof=1)
                rules.append(dict(fut=fut_sym, seg=seg, rule=sgn_name, part=part, n=len(nn),
                                  win=(nn > 0).mean(), mean_bp=m * 1e4,
                                  t=m / (sd / math.sqrt(len(nn)))))
    return x, out, rules


def main():
    allrules = []
    tabs = []
    for fut_sym, eq_sym in [("ESF", "SPY"), ("NQF", "QQQ")]:
        x, out, rules = run(fut_sym, eq_sym)
        tabs.extend(out)
        allrules.extend(rules)
        x.to_csv(f"{OUT}/futures_overnight_{fut_sym}.csv")
    pd.DataFrame(tabs).to_csv(f"{OUT}/futures_regressions.csv", index=False)
    r = pd.DataFrame(allrules)
    r.to_csv(f"{OUT}/futures_rules.csv", index=False)
    print("\nRULES (intraday from 09:30 open to 16:00 close, 4bp RT):")
    print(r.round(3).to_string(index=False))
    print("FUTURES VARIANTS: rules", len(r) // 2, "(x dev/chk), regressions", len(tabs))


if __name__ == "__main__":
    main()
