"""Steps 2-3: pre-market fair-value gap vs BTC-implied FV and vs MSTRUSDT perp; trade-rule grid.
Builds a per-(day, time) panel for ALL days (saved), but `python fvgap.py dev` only prints DEV stats.
The TEST half is evaluated only by test_rules.py with frozen rules."""
import sys

import numpy as np
import pandas as pd

from common import DEV, TEST, H, at, load_btc, load_daily, load_mstr, load_perp, tstat

NY = "America/New_York"
TIMES = ["07:00", "08:00", "09:00", "09:20", "09:25"]
BETA_WIN, BETA_MIN = 40, 25


def ts(d, hm):
    return pd.Timestamp(f"{pd.Timestamp(d).date()} {hm}").tz_localize(NY)


def half_spread(hm):
    return 15.0 if hm < "08:00" else 6.0


def build_panel():
    m, btc, perp, y = load_mstr(), load_btc(), load_perp(), load_daily()
    y = y[y.index >= "2026-02-02"].copy()
    y["prev_close"] = y.Close.shift(1)
    y["prev_day"] = pd.Series(y.index, index=y.index).shift(1)
    # daily gap regression inputs (prior 16:00 -> 09:30)
    y["b_gap"] = [np.log(at(btc, ts(d, "09:30")) / at(btc, ts(p, "16:00"))) if pd.notna(p) else np.nan
                  for d, p in zip(y.index, y.prev_day)]
    y["m_gap"] = np.log(y.Open / y.prev_close)
    betas = []
    for i in range(len(y)):
        w = y.iloc[max(0, i - BETA_WIN):i].dropna(subset=["b_gap", "m_gap"])
        betas.append(np.polyfit(w.b_gap, w.m_gap, 1)[0] if len(w) >= BETA_MIN else np.nan)
    y["beta"] = betas  # uses strictly prior days
    px = {d: g for d, g in m.groupby("date")}
    rows = []
    for d, r in y.iterrows():
        if d < pd.Timestamp("2026-04-29") or d > pd.Timestamp(TEST[1]) or d not in px or np.isnan(r.beta):
            continue
        g = px[d]
        s = pd.Series(g.close.values, index=g.end)
        vol = pd.Series(g.volume.values, index=g.label)
        cl = pd.Series(g.close.values, index=g.label)
        if (g.hm < 900).sum() < 100:  # RTH-only day in the vault, no pre-market data
            continue
        t16 = ts(r.prev_day, "16:00")
        b16, p16 = at(btc, t16), at(perp, t16)
        basis = np.log(r.prev_close / p16)
        def last_print(t, maxage=5):
            w = s[(s.index <= t) & (s.index > t - pd.Timedelta(minutes=maxage))]
            return (w.iloc[-1], (t - w.index[-1]).seconds // 60) if len(w) else (np.nan, np.nan)
        p935, _ = last_print(ts(d, "09:35")); p1000, _ = last_print(ts(d, "10:00"))
        for hm in TIMES:
            t = ts(d, hm)
            pre, age = last_print(t)
            fv = r.prev_close * np.exp(r.beta * np.log(at(btc, t) / b16))
            pv = at(perp, t) * np.exp(basis)
            # entry: first bar labelled at t (covers t..t+1), i.e. the print right after the signal
            ent = cl.get(t, np.nan); ev = vol.get(t, np.nan)
            rows.append(dict(date=d, hm=hm, beta=r.beta, prev_close=r.prev_close, pre=pre, age=age, fv=fv, perp_fv=pv,
                             gap_fv=1e4 * np.log(pre / fv), gap_perp=1e4 * np.log(pre / pv),
                             btc_ret_since16=1e4 * np.log(at(btc, t) / b16), open=r.Open,
                             tgt_open=1e4 * np.log(r.Open / pre), tgt_935=1e4 * np.log(p935 / pre),
                             tgt_1000=1e4 * np.log(p1000 / pre),
                             entry=ent, entry_vol=ev, ret_entry_open=1e4 * np.log(r.Open / ent)))
    return pd.DataFrame(rows)


def trades(p, gapcol, hm, thr, stress=1.0, notional=100_000):
    x = p[(p.hm == hm) & (p[gapcol].abs() > thr) & p.entry.notna()].copy()
    x["dir"] = -np.sign(x[gapcol])
    comm_bp = 2 * 0.005 / x.entry * 1e4
    cost = stress * (half_spread(hm) + 2.0) + comm_bp
    x["gross_bp"] = x.dir * x.ret_entry_open
    x["net_bp"] = x.gross_bp - cost
    x["fillable_usd"] = np.where(x.entry_vol > 0, 0.10 * x.entry_vol * x.entry, np.nan)
    x["filled_usd"] = np.minimum(x.fillable_usd, notional)
    return x


def summarize(x):
    if len(x) == 0:
        return dict(n=0)
    return dict(n=len(x), mean_gross=x.gross_bp.mean(), mean_net=x.net_bp.mean(), win=(x.net_bp > 0).mean(),
                t_net=tstat(x.net_bp), med_fillable_usd=x.fillable_usd.median(),
                pct_days_vol_reported=100 * (x.entry_vol > 0).mean())


if __name__ == "__main__":
    pf = H / "fv_panel.parquet"
    p = build_panel() if "--rebuild" in sys.argv or not pf.exists() else pd.read_parquet(pf)
    p.to_parquet(pf)
    dev = p[(p.date >= DEV[0]) & (p.date <= DEV[1])]
    print(f"DEV days in panel: {dev.date.nunique()}  beta median {dev.beta.median():.2f} "
          f"[{dev.beta.min():.2f},{dev.beta.max():.2f}]  print age med {dev.age.median()} max {dev.age.max()}")
    out = []
    for gc in ("gap_fv", "gap_perp"):
        for hm in TIMES:
            x = dev[dev.hm == hm].dropna(subset=[gc, "tgt_open"])
            rec = dict(gap=gc, hm=hm, n=len(x), gap_sd=x[gc].std(), gap_absmed=x[gc].abs().median())
            for tg in ("tgt_open", "tgt_935", "tgt_1000"):
                z = x.dropna(subset=[tg])
                b, a = np.polyfit(z[gc], z[tg], 1)
                res = z[tg] - (a + b * z[gc])
                se = res.std(ddof=2) / (z[gc].std(ddof=1) * np.sqrt(len(z)))
                rec[f"corr_{tg}"] = z[gc].corr(z[tg]); rec[f"slope_{tg}"] = b; rec[f"t_{tg}"] = b / se
            out.append(rec)
    o = pd.DataFrame(out)
    pd.set_option("display.width", 250)
    print("\n== DEV: does gap predict move to open/09:35/10:00? (lag hypothesis => negative slope; -1 = full catch-up)")
    print(o.round(3).to_string(index=False))
    o.to_csv(H / "fvgap_dev_regress.csv", index=False)
    g = []
    for gc in ("gap_fv", "gap_perp"):
        for hm in TIMES:
            for thr in (25, 50, 100, 150):
                s = summarize(trades(dev, gc, hm, thr)); s2 = summarize(trades(dev, gc, hm, thr, stress=2.0))
                g.append(dict(gap=gc, hm=hm, thr=thr, **s, mean_net_stress=s2.get("mean_net")))
    g = pd.DataFrame(g)
    print("\n== DEV trade grid (enter next print after hm when |gap|>thr, fade gap, exit official open)")
    print(g.round(2).to_string(index=False))
    g.to_csv(H / "fvgap_dev_grid.csv", index=False)
