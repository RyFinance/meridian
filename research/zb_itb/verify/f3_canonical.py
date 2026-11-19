"""Canonical F3 backtest on frozen yfinance data. Exact bar labels only (no fallbacks), start-labeled bars.
Signal: d = sign(ln(ZB close of 60m bar starting 08:00 ET on D / ZB close of bar starting 15:00 ET on prev session)).
Trade ITB 09:30->10:30. Entry variants: 'h1' = 60m bar Open; 'off' = official daily Open (MOO fill). Exit = 60m bar Close."""
import numpy as np, pandas as pd
C = "research/zb_itb/verify/yf_cache/"
def ld(f):
    d = pd.read_parquet(C + f); d.index = d.index.tz_convert("America/New_York"); return d
def build(etf="ITB", zbfile="ZB_F_60m.parquet"):
    import os
    z, e = ld(zbfile), ld(f"{etf}_60m.parquet")
    e1d = pd.read_parquet(C + f"{etf}_1d.parquet") if os.path.exists(C + f"{etf}_1d.parquet") else pd.DataFrame(columns=["Open"])
    first = e[e.index.time == pd.Timestamp("09:30").time()]
    days = list(first.index.normalize()); rows = []
    for i in range(1, len(days)):
        D, prev = days[i], days[i - 1]
        t0, t1 = prev + pd.Timedelta(hours=15), D + pd.Timedelta(hours=8)
        if t0 not in z.index or t1 not in z.index: rows.append(dict(date=D.date(), d=np.nan)); continue
        p0, p1 = z.loc[t0, "Close"], z.loc[t1, "Close"]
        b = first.iloc[i]; dd = pd.Timestamp(D.date())
        rows.append(dict(date=D.date(), P0=p0, P1=p1, m=np.log(p1 / p0), d=np.sign(np.log(p1 / p0)), entry_h1=b.Open,
                         entry_off=e1d.loc[dd, "Open"] if dd in e1d.index else np.nan, exit=b.Close,
                         gap=np.log(b.Open / e.loc[e.index < D].Close.iloc[-1]) if (e.index < D).any() else np.nan))
    r = pd.DataFrame(rows).set_index("date"); r.index = pd.to_datetime(r.index)
    r["g_h1"] = r.d * np.log(r.exit / r.entry_h1); r["g_off"] = r.d * np.log(r.exit / r.entry_off)
    return r
def stats(p, label=""):
    p = p.dropna(); p = p[p != 0] if False else p
    yrs = max((p.index[-1] - p.index[0]).days / 365.25, 1e-9); eq = np.exp(p.cumsum())
    return dict(label=label, n=int((p != 0).sum()), mean_bp=p.mean() * 1e4, t=p.mean() / p.std() * np.sqrt(len(p)), win=(p[p != 0] > 0).mean(),
                cagr=(eq.iloc[-1] ** (1 / yrs) - 1) * 100, sharpe=p.mean() / p.std() * np.sqrt(252), maxdd=(eq / eq.cummax() - 1).min() * 100)
if __name__ == "__main__":
    r = build(); r.to_csv("research/zb_itb/verify/f3_trades_canonical.csv")
    tr = r[r.d.notna() & (r.d != 0)]
    print("days", len(r), "no-signal (missing bar)", int(r.d.isna().sum()), "zero move", int((r.d == 0).sum()), "trades", len(tr))
    out = []
    for ent in ["h1", "off"]:
        net = tr[f"g_{ent}"] - 0.0004
        for lab, msk in [("all", slice(None)), ("<=2026-08-10", tr.index <= "2026-08-10"), ("holdout", tr.index > "2026-08-10")]:
            out.append(stats(net[msk], f"{ent} {lab}"))
        lo = (np.where(tr.d > 0, tr[f"g_{ent}"] - 0.0004, 0.0)); out.append(stats(pd.Series(lo, index=tr.index), f"{ent} long-only all"))
    print(pd.DataFrame(out).round(2).to_string(index=False))
    print("entry diff (h1 vs official) on trade days: mean signed advantage of h1 entry (bp):", round(((tr.g_h1 - tr.g_off) * 1e4).mean(), 2), "| days |diff|>10bp:", int(((tr.g_h1 - tr.g_off).abs() * 1e4 > 10).sum()))
