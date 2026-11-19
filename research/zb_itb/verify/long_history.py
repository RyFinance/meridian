"""Long-history test of the mechanism with tradable timing, LSE vault 5m bars (regular session), 2010-01..2026-09-16.
Signal (rates, known by 09:30-09:35): sign of TLT's move from prior 16:00 close to its 09:30 open ('gap') or to 09:35 ('gap5').
Trade: equal-weight homebuilder basket (DHI LEN PHM TOL KBH NVR), entry at 09:35 bar open, exit at 10:30 (close of 10:25 bar) or 16:00.
Reference (not MOO-tradable): entry at the builders' 09:30 open with the TLT gap signal (simultaneous opens)."""
import glob, numpy as np, pandas as pd
V = "research/zb_itb/verify/vault/"
BUILDERS = ["DHI", "LEN", "PHM", "TOL", "KBH", "NVR"]
def load(sym, tf="5m"):
    fs = sorted(glob.glob(f"{V}{sym}_{tf}_*.parquet"))
    if not fs: return None
    d = pd.concat([pd.read_parquet(f) for f in fs]).drop_duplicates("ts")
    d["et"] = d.ts.dt.tz_localize("UTC").dt.tz_convert("America/New_York")
    d = d[(d.et.dt.hour * 60 + d.et.dt.minute >= 570) & (d.et.dt.hour * 60 + d.et.dt.minute < 960)]
    d["day"] = d.et.dt.tz_localize(None).dt.normalize(); d["hm"] = d.et.dt.strftime("%H:%M")
    return d
def daily(sym, tf="5m"):
    d = load(sym, tf)
    if d is None: return None
    g = d.groupby("day")
    out = pd.DataFrame({"o930": d[d.hm == "09:30"].set_index("day").open, "o935": d[d.hm == "09:35"].set_index("day").open,
                        "c1025": d[d.hm == "10:25"].set_index("day").close, "last": g.close.last()})
    out["prev_close"] = out["last"].shift(); out["c935"] = out.o935
    return out
if __name__ == "__main__":
    tlt = daily("TLT"); B = {s: daily(s) for s in BUILDERS}
    sig = pd.DataFrame({"gap": np.sign(np.log(tlt.o930 / tlt.prev_close)), "gap5": np.sign(np.log(tlt.o935 / tlt.prev_close))})
    rets = {}
    for s, b in B.items():
        rets[s] = pd.DataFrame({"r935_1030": np.log(b.c1025 / b.o935), "r930_1030": np.log(b.c1025 / b.o930), "r935_close": np.log(b["last"] / b.o935)})
    def basket(col): return pd.concat({s: r[col] for s, r in rets.items()}, axis=1).mean(axis=1, skipna=True)
    res = pd.DataFrame({"gap": sig.gap, "gap5": sig.gap5, "b935_1030": basket("r935_1030"), "b930_1030": basket("r930_1030"), "b935_close": basket("r935_close")}).dropna()
    res = res[res.gap != 0]
    C = 3 / 1e4  # per side, stock basket
    variants = {"TRADABLE gap -> 09:35-10:30": res.gap * res.b935_1030 - 2 * C,
                "TRADABLE gap5 -> 09:35-10:30": res.gap5 * res.b935_1030 - 2 * C,
                "TRADABLE gap -> 09:35-close": res.gap * res.b935_close - 2 * C,
                "reference gap -> 09:30-10:30 (simultaneous)": res.gap * res.b930_1030 - 2 * C}
    res.to_parquet("research/zb_itb/verify/long_history_panel.parquet")
    def row(p): p = p.dropna(); return f"n {len(p):4d} mean {p.mean()*1e4:+6.1f}bp t {p.mean()/p.std()*np.sqrt(len(p)):+5.2f} win {(p>0).mean():.2f} Sharpe {p.mean()/p.std()*np.sqrt(252):+.2f}"
    for k, p in variants.items():
        print(f"== {k}\n   ALL {row(p)}")
        for a, b in [("2010", "2014"), ("2015", "2019"), ("2020", "2023"), ("2024", "2026")]:
            print(f"   {a}-{b} {row(p[(p.index >= a) & (p.index <= b + '-12-31')])}")
    p = variants["TRADABLE gap -> 09:35-10:30"]
    print("per-year (TRADABLE gap -> 09:35-10:30):", " ".join(f"{y}:{g.mean()*1e4:+.0f}" for y, g in p.groupby(p.index.year)))
    for s in ["SPY", "XLU", "KRE", "HD", "LOW", "BLDR", "IEF"]:
        b = daily(s)
        if b is None: print(f"placebo {s}: no data"); continue
        x = (res.gap * np.log(b.c1025 / b.o935).reindex(res.index) - 2 * C).dropna()
        print(f"other {s}: {row(x)} | 2010-23 {row(x[x.index < '2024'])}")
