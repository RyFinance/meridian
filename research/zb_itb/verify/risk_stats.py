"""Risk-adjusted stats for F3 (official-open entry, 10:30 exit, 2bp/side) + win-rate filters (in-sample, exploratory)."""
import numpy as np, pandas as pd
from research.zb_itb.verify.f3_canonical import build
r = build(); t = r[r.d.notna() & (r.d != 0)].copy(); t["net"] = t.g_off - 0.0004
cal = pd.bdate_range(t.index.min(), t.index.max())
def stats(p, label):
    p = p.reindex(cal).fillna(0.0)                     # daily series incl. no-trade days
    tr = p[p != 0]; eq = np.exp(p.cumsum()); yrs = len(p) / 252
    dd = eq / eq.cummax() - 1; cagr = eq.iloc[-1] ** (1 / yrs) - 1
    down = p[p < 0]; sortino = p.mean() / np.sqrt((np.minimum(p, 0) ** 2).mean()) * np.sqrt(252)
    streak = max((len(list(g)) for k, g in __import__("itertools").groupby(tr < 0) if k), default=0)
    print(f"{label}\n  trades {len(tr)} | win {(tr>0).mean():.1%} | avg win {tr[tr>0].mean()*1e4:+.0f}bp avg loss {tr[tr<0].mean()*1e4:+.0f}bp | profit factor {tr[tr>0].sum()/-tr[tr<0].sum():.2f}"
          f"\n  CAGR {cagr*100:+.0f}% | ann vol {p.std()*np.sqrt(252)*100:.0f}% | Sharpe {p.mean()/p.std()*np.sqrt(252):.2f} | Sortino {sortino:.2f} | maxDD {dd.min()*100:.1f}% | Calmar {cagr/-dd.min():.1f}"
          f"\n  worst day {tr.min()*100:.1f}% | 1-day 95% VaR {-np.quantile(tr,.05)*100:.1f}% | longest losing streak {streak} | longest drawdown {(dd<0).astype(int).groupby((dd==0).cumsum()).sum().max()} days")
stats(t.net, "LONG/SHORT"); stats(t.net.where(t.d > 0), "LONG-ONLY")
print("\nWIN-RATE FILTERS (in-sample, 2024-26; picking one now would be overfitting):")
rz = build("ITB", "ZN_F_60m.parquet")[["d"]].rename(columns={"d": "dzn"}); t = t.join(rz)
t["gapsign"] = np.sign(t.gap); q = t.m.abs()
for lab, msk in [("all trades", slice(None)), ("ZB and ZN agree", t.d == t.dzn), ("|ZB move| > median", q > q.median()),
                 ("|ZB move| top 20%", q > q.quantile(.8)), ("ITB gap agrees with signal", t.gapsign == t.d), ("ITB gap disagrees", t.gapsign == -t.d)]:
    x = t.net[msk].dropna(); print(f"  {lab:28s} n {len(x):3d} win {(x>0).mean():.1%} mean {x.mean()*1e4:+.1f}bp t {x.mean()/x.std()*np.sqrt(len(x)):+.2f}")
