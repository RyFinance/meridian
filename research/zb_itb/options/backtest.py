"""Options version of the ZB -> homebuilder first-hour rule, on real OPRA 1m prints (LSE vault), 2024-05-29..2026-09-16.
Each signal day and stock: BUY a call (d=+1) or put (d=-1). Expiry bucket: nearest expiry with DTE in [lo, hi]. Strike: ATM / 1 OTM / 1 ITM by the
stock's 09:30 open. Entry: first print in 09:30-09:34. Exit: last print in 10:25-10:35 (fallback: last print 10:35-10:45, flagged).
Fills: base = print close +/- half-spread max($0.03, 3% px); stress = max($0.06, 6% px); worst = also bar high/low. Commission $0.65/contract/side.
Return on premium paid. Compared with the stock trade on the same days (vault 1m, 09:30 open -> 10:30)."""
import glob, numpy as np, pandas as pd
from research.zb_itb.verify.f3_canonical import build
from research.zb_itb.verify.long_history import load
D = "research/zb_itb/options/data/"
sig = build(); sig = sig[sig.d.notna() & (sig.d != 0)].d; sig = sig[(sig.index >= "2024-05-29") & (sig.index <= "2026-09-16")]
COMM = 0.65 / 100   # per share-equivalent (contract = 100 shares)
def hs(px, mode): return np.maximum(0.03, 0.03 * px) if mode == "base" else np.maximum(0.06, 0.06 * px)
rows = []
for sym in ["DHI", "LEN", "PHM", "TOL", "KBH"]:
    fs = sorted(glob.glob(f"{D}{sym}_*.parquet"))
    if not fs: print(sym, "no option data"); continue
    o = pd.concat([pd.read_parquet(f) for f in fs])
    ts = pd.to_datetime(o.ts); ts = ts.dt.tz_localize("UTC") if ts.dt.tz is None else ts
    o["et"] = ts.dt.tz_convert("America/New_York").dt.tz_localize(None); o["day"] = o.et.dt.normalize()
    o["hm"] = o.et.dt.strftime("%H:%M"); o["exp"] = pd.to_datetime(o.expiry); o["dte"] = (o.exp - o.day).dt.days
    o["typ"] = o.opt_type.str.upper().str[0]
    st = load(sym, "1m"); spot = st.sort_values("et").groupby("day").open.first(); s1030 = st[st.hm == "10:29"].set_index("day").close
    og = {k: g for k, g in o.groupby("day")}
    for day, d in sig.items():
        if day not in og or day not in spot.index: continue
        g = og[day]; typ = "C" if d > 0 else "P"; S = spot[day]
        for blo, bhi, blab in [(0, 3, "0-3d"), (4, 10, "4-10d"), (11, 45, "11-45d")]:
            ge = g[(g.typ == typ) & g.dte.between(blo, bhi)]
            if ge.empty: continue
            ge = ge[ge.exp == ge.exp.min()]
            ks = np.sort(ge.strike.unique());
            if len(ks) == 0: continue
            iatm = int(np.argmin(np.abs(ks - S)))
            for slab, off in [("ATM", 0), ("OTM1", 1 if typ == "C" else -1), ("ITM1", -1 if typ == "C" else 1)]:
                i = iatm + off
                if not 0 <= i < len(ks): continue
                c = ge[ge.strike == ks[i]].sort_values("et")
                ent = c[(c.hm >= "09:30") & (c.hm <= "09:34")]; ex = c[(c.hm >= "10:25") & (c.hm <= "10:35")]; fb = False
                if ex.empty: ex = c[(c.hm > "10:35") & (c.hm <= "10:45")]; fb = True
                if ent.empty or ex.empty: rows.append(dict(sym=sym, day=day, bucket=blab, strike=slab, traded=False)); continue
                e, x = ent.iloc[0], ex.iloc[-1]
                r = dict(sym=sym, day=day, d=d, bucket=blab, strike=slab, traded=True, fallback=fb, px_in=e.close, dte=int(e.dte),
                         stock_ret=d * np.log(s1030.get(day, np.nan) / S))
                for mode in ["base", "stress"]:
                    pin = e.close + hs(e.close, mode) + COMM; pout = max(x.close - hs(x.close, mode), 0) - COMM
                    r[f"ret_{mode}"] = pout / pin - 1
                pin_w = max(e.high, e.close + hs(e.close, "base")) + COMM; pout_w = max(min(x.low, x.close - hs(x.close, "base")), 0) - COMM
                r["ret_worst"] = pout_w / pin_w - 1; r["gross"] = x.close / e.close - 1
                rows.append(r)
R = pd.DataFrame(rows); R.to_parquet("research/zb_itb/options/trades.parquet")
T = R[R.traded == True]
print(f"signal days {len(sig)}; option legs attempted {len(R)}, tradable (print at entry & exit) {len(T)} ({len(T)/max(len(R),1):.0%}), exit fallbacks {int(T.fallback.sum())}")
def line(x, lab):
    t = lambda s: s.mean() / s.std() * np.sqrt(len(s))
    print(f"  {lab:14s} n {len(x):4d} | prem ${x.px_in.median():.2f} | gross {x.gross.mean()*100:+5.1f}% | base {x.ret_base.mean()*100:+5.1f}% (t {t(x.ret_base):+.2f}, win {(x.ret_base>0).mean():.0%}) "
          f"| stress {x.ret_stress.mean()*100:+5.1f}% | worst {x.ret_worst.mean()*100:+5.1f}% | same-day stock {x.stock_ret.mean()*1e4:+.0f}bp")
for (b, s), x in T.groupby(["bucket", "strike"]): line(x, f"{b} {s}")
print("all legs:"); line(T, "ALL")
