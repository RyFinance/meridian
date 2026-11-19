"""Robustness battery for F3 on the 2024-05..2026-10 yfinance sample (frozen cache). Official-open entry unless noted."""
import numpy as np, pandas as pd
from research.zb_itb.verify.f3_canonical import build, ld, stats, C
rng = np.random.default_rng(20261018)
r = build(); tr = r[r.d.notna() & (r.d != 0)].copy()
z = ld("ZB_F_60m.parquet"); e = ld("ITB_60m.parquet")
def tstat(p): p = p.dropna(); return p.mean() / p.std() * np.sqrt(len(p))
line = lambda lab, p: print(f"  {lab:34s} n {p.notna().sum():4d} mean {p.mean()*1e4:+6.1f}bp t {tstat(p):+5.2f} win {(p.dropna()>0).mean():.2f}")
print("1) COSTS per side (official open entry):")
for c in [0, 1, 2, 3, 5, 8, 10]:
    s = stats(tr.g_off - 2 * c / 1e4); print(f"  {c:2d}bp/side: mean {s['mean_bp']:+.1f}bp t {s['t']:+.2f} CAGR {s['cagr']:+.0f}% Sharpe {s['sharpe']:.2f} maxDD {s['maxdd']:.0f}%")
print("2) EXIT TIME (entry official open; exit = close of 60m bar starting at):")
for h in ["09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30"]:
    ex = e[e.index.strftime("%H:%M") == h].Close; ex.index = pd.to_datetime(ex.index.date)
    line(f"exit at end of {h} bar", tr.d * np.log(ex.reindex(tr.index) / tr.entry_off) - 0.0004)
print("3) SIGNAL SIZE |m| quintiles (net 2bp/side):")
tr["q"] = pd.qcut(tr.m.abs(), 5, labels=False)
for q, g in tr.groupby("q"): line(f"|m| Q{q+1} ({g.m.abs().min()*1e4:.0f}-{g.m.abs().max()*1e4:.0f}bp)", g.g_off - 0.0004)
print("4) WHICH PART OF THE OVERNIGHT MOVE? (P_08:00 = close of bar starting 07:00)")
p08 = pd.Series({d: z.loc[d + pd.Timedelta(hours=7), "Close"] if (d + pd.Timedelta(hours=7)) in z.index else np.nan for d in pd.to_datetime(tr.index).tz_localize("America/New_York")})
p08.index = tr.index; m_on = np.log(p08 / tr.P0); m_0809 = np.log(tr.P1 / p08)
r_itb = np.log(tr.exit / tr.entry_off)
line("sign(16:00->08:00) only", np.sign(m_on) * r_itb - 0.0004); line("sign(08:00->09:00) only", np.sign(m_0809) * r_itb - 0.0004)
big0809 = m_0809.abs() > m_0809.abs().quantile(0.8)
line("full signal, big 08-09 move days (top20%)", (tr.g_off - 0.0004)[big0809]); line("full signal, other days", (tr.g_off - 0.0004)[~big0809])
print("5) SIDES / DAYS / CONCENTRATION:")
line("long days (d=+1)", (tr.g_off - 0.0004)[tr.d > 0]); line("short days (d=-1)", (tr.g_off - 0.0004)[tr.d < 0])
for dow, g in tr.groupby(tr.index.dayofweek): line(f"weekday {'MTWRF'[dow]}", g.g_off - 0.0004)
net = (tr.g_off - 0.0004).sort_values(ascending=False)
print(f"  median trade {net.median()*1e4:+.1f}bp | total {net.sum()*100:.1f}% | top-10 days {net.head(10).sum()*100:.1f}% | ex top-10 mean {net.iloc[10:].mean()*1e4:+.1f}bp t {tstat(net.iloc[10:]):+.2f} | ex top&bottom 5% mean {net.iloc[int(.05*len(net)):int(.95*len(net))].mean()*1e4:+.1f}bp")
mo = (tr.g_off - 0.0004).groupby(tr.index.to_period("M")).sum()
print(f"  months {len(mo)}, positive {int((mo>0).sum())}, worst month {mo.min()*100:.1f}%, best {mo.max()*100:.1f}%")
print("  monthly %:", " ".join(f"{p.strftime('%y%m')}:{v*100:+.1f}" for p, v in mo.items()))
print("6) PERMUTATION (shuffle signs across days, 20k) and BLOCK BOOTSTRAP (10-day blocks, 10k):")
g = tr.g_off.values; dd = tr.d.values; ra = g * dd  # raw ITB first-hour return
obs = np.mean(g); perm = np.array([np.mean(rng.permutation(dd) * ra) for _ in range(20000)])
print(f"  observed gross mean {obs*1e4:.1f}bp; permutation p = {(perm >= obs).mean():.5f} (null 99th pct {np.quantile(perm, .99)*1e4:.1f}bp)")
n = len(g); B = 10; sh = []
for _ in range(10000):
    idx = np.concatenate([np.arange(s, min(s + B, n)) for s in rng.integers(0, n, n // B + 1)])[:n]
    x = g[idx] - 0.0004; sh.append(x.mean() / x.std() * np.sqrt(252))
print(f"  annual Sharpe 95% CI [{np.quantile(sh, .025):.2f}, {np.quantile(sh, .975):.2f}], P(Sharpe<1) = {(np.array(sh) < 1).mean():.4f}")
print("7) MECHANISM: regress ITB first-hour return on d, ZB first-hour return, ITB gap sign")
zf = pd.Series({d: np.log(z.loc[d + pd.Timedelta(hours=10), "Close"] / z.loc[d + pd.Timedelta(hours=9), "Close"]) if (d + pd.Timedelta(hours=10)) in z.index and (d + pd.Timedelta(hours=9)) in z.index else np.nan
                for d in pd.to_datetime(tr.index).tz_localize("America/New_York")}); zf.index = tr.index
print(f"  does ZB itself continue 09:00-10:00 after the overnight move? sign-aligned ZB 09-10 mean {np.nanmean(tr.d*zf)*1e4:+.2f}bp t {tstat(tr.d*zf):+.2f}")
X = pd.DataFrame({"const": 1, "d": tr.d, "zb_0910": zf, "gap_sign": np.sign(tr.gap)}).dropna(); y = r_itb.reindex(X.index)
b, *_ = np.linalg.lstsq(X.values, y.values, rcond=None); res = y.values - X.values @ b
se = np.sqrt(np.diag(np.linalg.inv(X.values.T @ X.values)) * res.var(ddof=X.shape[1]))
print("  OLS coefs (bp) / t:", {k: f"{v*1e4:+.1f} / {v/s:+.2f}" for k, v, s in zip(X.columns, b, se)})
print("8) OTHER INSTRUMENTS, same ZB signal, 09:30->10:30 (60m open entry), net 2bp/side:")
for etf in ["ITB", "XHB", "DHI", "LEN", "PHM", "TOL", "KBH", "NVR", "VNQ", "IWM", "XLU", "KRE", "TLT", "SPY"]:
    rr = build(etf) if etf != "ITB" else r; t2 = rr[rr.d.notna() & (rr.d != 0)]
    line(etf, t2.g_h1 - 0.0004)
print("9) ZN (10y) instead of ZB:")
rz = build("ITB", "ZN_F_60m.parquet"); t3 = rz[rz.d.notna() & (rz.d != 0)]; line("ZN signal -> ITB", t3.g_off - 0.0004)
print(f"  ZB/ZN sign agreement: {(np.sign(rz.m) == np.sign(r.m)).mean():.2f}")
