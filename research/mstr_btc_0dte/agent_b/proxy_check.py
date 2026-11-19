"""Post-validation sanity check (not used for any rule choice): real MSTR extended-hours minutes
(LSE vault, 2026-04-29..2026-08-10 overlap with BTC) vs proxies A/B. ts is naive UTC (08..23 = 04:00..19:59 EDT)."""
import sys
sys.path.insert(0, "/Users/rytty/CCP/quant_v7/research/mstr_btc_0dte/agent_b")
import numpy as np, pandas as pd
from common import OUT, mstr
m = pd.read_parquet("/Users/rytty/CCP/quant_v7/research/mstr_btc_0dte/mstr_stock_1m_lse.parquet")
m["ts"] = pd.to_datetime(m.ts).dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
m = m.set_index("ts").close.sort_index()
P = pd.read_parquet(OUT + "/panel.parquet").set_index("date")
M = mstr()
rows = []
for d, r in P[(P.index >= "2026-04-30") & (P.index <= "2026-08-10")].iterrows():
    if d not in M.index: continue
    prev = r.prev
    a20 = m[(m.index >= prev + pd.Timedelta("19h50min")) & (m.index < prev + pd.Timedelta("20h"))]
    a04 = m[(m.index >= d + pd.Timedelta("4h")) & (m.index < d + pd.Timedelta("4h10min"))]
    pc = m[(m.index >= prev + pd.Timedelta("15h59min")) & (m.index < prev + pd.Timedelta("16h"))]
    o = M.loc[d, "Open"]
    rows.append(dict(date=d, kind=r.kind, E20=r.E20, R20=r.R20, E04=r.E04, R04=r.R04, gap=M.loc[d, "gap"],
                     m20=np.log(o / a20.iloc[-1]) if len(a20) else np.nan,
                     m04=np.log(o / a04.iloc[0]) if len(a04) else np.nan))
X = pd.DataFrame(rows).set_index("date")
b = 0.95
for t in ["20", "04"]:
    x = X.dropna(subset=["m" + t, "R" + t])
    A = b * x["R" + t]; B = x.gap - b * x["E" + t]
    print(f"{t}: n={len(x)} corr(real,A)={x['m'+t].corr(A):.2f} corr(real,B)={x['m'+t].corr(B):.2f} "
          f"beta real~BTC_R={np.polyfit(x['R'+t], x['m'+t], 1)[0]:.2f} share of gap left={x['m'+t].abs().mean()/x.gap.abs().mean():.2f}")
    long = x[x["E" + t] > 0]
    g = np.exp(long["m" + t]) - 1
    print(f"   rule long if E>0 on REAL prints: n={len(long)} gross {g.mean()*1e4:+.1f} bp, net {(g-17.2e-4).mean()*1e4:+.1f} bp, "
          f"proxyA gross {(b*long['R'+t]).mean()*1e4:+.1f}, proxyB gross {(long.gap-b*long['E'+t]).mean()*1e4:+.1f}")
print("OLS real MSTR remainder on BTC E and R (does MSTR's extended-hours price lag BTC's E move?):")
for t in ["20", "04"]:
    x = X.dropna(subset=["m" + t, "R" + t, "E" + t])
    Z = np.column_stack([np.ones(len(x)), x["E" + t], x["R" + t]])
    co, *_ = np.linalg.lstsq(Z, x["m" + t], rcond=None)
    res = x["m" + t] - Z @ co
    se = np.sqrt(np.diag(np.linalg.inv(Z.T @ Z)) * res.var(ddof=3))
    print(f"  {t}: n={len(x)} coef_E={co[1]:.2f} (se {se[1]:.2f}) coef_R={co[2]:.2f} (se {se[2]:.2f}); gap~E+R: "
          + str(np.round(np.linalg.lstsq(Z, x.gap, rcond=None)[0][1:], 2)))
