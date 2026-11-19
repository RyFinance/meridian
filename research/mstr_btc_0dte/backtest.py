"""Backtest: buy the nearest-to-the-money option on MSTR at the open, direction from BTC's off-hours move.
Mon: off-hours = Fri 16:00 -> Mon 09:30 ET; option = that week's Friday expiry, exit at Monday's option close print.
Fri: off-hours = Thu 16:00 -> Fri 09:30 ET; option = 0DTE, exit at intrinsic vs official close.
Signals (direction):
  RAW   sign(btc_off)                                  -- the literal idea
  UNDER sign(beta*btc_off - mstr_gap), |.| >= THRESH   -- MSTR opened away from what BTC implies; bet on catch-up
        beta = trailing 250-trading-day OLS of mstr_gap on btc_off, using only prior days.
Strike: OTM1 = first out-of-the-money strike that traded (cheapest that is closest to ITM); ITM1 sensitivity.
Entry = option's daily open print (first trade). No bid/ask exists, so costs: half-spread max($0.05, 4% of premium)
per side + $0.65/contract per side; stress doubles both."""
import numpy as np, pandas as pd
from pathlib import Path
H = Path(__file__).parent
SPLIT = pd.Timestamp("2024-08-08")
THRESH = 0.01

def load():
    p = pd.read_parquet(H / "daily_panel.parquet")
    m = pd.read_parquet(H / "mstr_daily_yf.parquet")[["Open", "Close"]]
    f = np.where(m.index < SPLIT, 10.0, 1.0)  # yfinance is split-adjusted; option strikes are not
    m = m.assign(open_raw=m.Open * f, close_raw=m.Close * f)
    p = p.join(m[["open_raw", "close_raw"]])
    # trailing beta of the gap on btc_off (all weekdays), shifted so day t uses only < t
    cov = (p.btc_off * p.mstr_gap).rolling(250, min_periods=120).mean() - p.btc_off.rolling(250, min_periods=120).mean() * p.mstr_gap.rolling(250, min_periods=120).mean()
    beta = (cov / p.btc_off.rolling(250, min_periods=120).var(ddof=0)).shift(1)
    p["under"] = beta * p.btc_off - p.mstr_gap
    o = pd.read_parquet(H.parents[1] / "data/lse/options_mstr/MSTR.parquet")
    o["d"] = pd.to_datetime(o.ts).dt.tz_localize(None).dt.normalize()
    o["expiry"] = pd.to_datetime(o.expiry)
    o = o[(o.volume > 0) & (o.open > 0)]
    return p, o

def trades(p, o, signal, strike_mode, stress=1.0):
    out = []
    og = dict(tuple(o[o.d.isin(p.index)].groupby("d")))
    for d, r in p[p.dow.isin([0, 4])].iterrows():
        s = np.sign(r.btc_off) if signal == "RAW" else (np.sign(r.under) if abs(r.under) >= THRESH else 0)
        if not np.isfinite(s) or s == 0 or d not in og:
            continue
        ch = og[d]
        exp = ch.expiry[ch.expiry >= d].min()
        if pd.isna(exp) or (exp - d).days > 4:
            continue
        typ = "C" if s > 0 else "P"
        c = ch[(ch.expiry == exp) & (ch.opt_type == typ)]
        S = r.open_raw
        if typ == "C":
            cand = c[c.strike >= S].sort_values("strike") if strike_mode == "OTM1" else c[c.strike < S].sort_values("strike", ascending=False)
        else:
            cand = c[c.strike <= S].sort_values("strike", ascending=False) if strike_mode == "OTM1" else c[c.strike > S].sort_values("strike")
        if cand.empty:
            continue
        k = cand.iloc[0]
        if abs(k.strike / S - 1) > 0.05:  # nearest traded strike too far away: skip
            continue
        if exp == d:  # 0DTE: settle at intrinsic vs official close
            exitpx = max(r.close_raw - k.strike, 0) if typ == "C" else max(k.strike - r.close_raw, 0)
        else:
            exitpx = k.close
        hs = lambda x: stress * max(0.05, 0.04 * x)
        cost_in = k.open + hs(k.open) + stress * 0.0065
        proceeds = max(exitpx - hs(exitpx), 0) - stress * 0.0065 if exitpx > 0 else 0.0
        out.append(dict(date=d, dow=r.dow, typ=typ, strike=k.strike, spot=S, dte=(exp - d).days, entry=k.open,
                        exit=exitpx, ret=proceeds / cost_in - 1, gross=exitpx / k.open - 1, vol=k.volume,
                        sig=r.btc_off if signal == "RAW" else r.under, mstr_day=r.mstr_day))
    return pd.DataFrame(out).set_index("date")

def summarize(t, label):
    if t.empty:
        return
    g = lambda x: f"n={len(x):3d} win={np.mean(x.ret > 0):.2f} mean={x.ret.mean():+.3f} med={x.ret.median():+.3f} gross={x.gross.mean():+.3f} t={x.ret.mean() / x.ret.std() * np.sqrt(len(x)):+.2f}"
    print(f"{label:28s} ALL {g(t)}")
    for dw, nm in [(0, "Mon"), (4, "Fri")]:
        print(f"{'':28s} {nm} {g(t[t.dow == dw])}")
    print(f"{'':28s} pre-2023-07 {g(t[t.index < '2023-07-01'])} | post {g(t[t.index >= '2023-07-01'])}")

if __name__ == "__main__":
    p, o = load()
    res = {}
    for sig in ["RAW", "UNDER"]:
        for sm in ["OTM1", "ITM1"]:
            for st in [1.0, 2.0]:
                t = trades(p, o, sig, sm, st)
                res[(sig, sm, st)] = t
                summarize(t, f"{sig} {sm} cost x{st:g}")
    # placebo: random direction, same days/strikes
    rng = np.random.default_rng(0)
    pr = p.copy(); pr["btc_off"] = rng.choice([-1, 1], len(pr)) * 0.01
    summarize(trades(pr, o, "RAW", "OTM1"), "PLACEBO random dir OTM1")
    pd.to_pickle(res, H / "trades.pkl")
