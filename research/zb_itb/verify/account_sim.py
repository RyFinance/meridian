"""Realistic account simulation for F3 on 2024-05-28..2026-10-16 (frozen yfinance data; official-open entry, 10:30 exit).
Each scenario: account type (margin>=25k long/short, PDT-limited margin, cash long-only), broker commissions, slippage, share rounding.
Prices: entry = official open (MOO auction fill) + entry_slip; exit = 10:30 bar close - exit_slip (half spread + impact).
Fees: SEC $27.80/$1M on sales (2026 rate assumed), FINRA TAF $0.000166/share sold (max $8.30). No borrow fee intraday."""
import numpy as np, pandas as pd
from research.zb_itb.verify.f3_canonical import build
r = build(); tr = r[r.d.notna() & (r.d != 0)].copy()
def comm(broker, shares, px):
    if broker == "zero": return 0.0
    if broker == "ibkr_fixed": return min(max(1.0, 0.005 * shares), 0.01 * shares * px)
    if broker == "ibkr_tiered": return max(0.35, 0.0035 * shares) + 0.0005 * shares  # + approx exchange/clearing
    raise ValueError(broker)
def sim(cap0, broker="zero", acct="margin25k", entry_slip=1.0, exit_slip=2.0, fractional=False, start=None, end=None):
    eq, rows, recent = cap0, [], []
    t = tr if start is None else tr[(tr.index >= start) & (tr.index <= (end or "2100"))]
    for day, x in t.iterrows():
        d = x.d
        if acct == "cash_long" and d < 0: rows.append((day, eq)); continue
        if acct == "pdt":
            recent = [q for q in recent if (day - q).days <= 6 and np.busday_count(q.date(), day.date()) < 5]
            if len(recent) >= 3: rows.append((day, eq)); continue
        pin = x.entry_off * (1 + d * entry_slip / 1e4)          # buy higher / short-sell lower
        pout = x.exit * (1 - d * exit_slip / 1e4)               # sell lower / cover higher
        sh = eq / pin if fractional else np.floor(eq / pin)
        if sh <= 0: rows.append((day, eq)); continue
        pnl = d * sh * (pout - pin)
        sold_px = pout if d > 0 else pin
        fees = 27.80e-6 * sh * sold_px + min(0.000166 * sh, 8.30) + comm(broker, sh, pin) + comm(broker, sh, pout)
        eq += pnl - fees; rows.append((day, eq))
        if acct == "pdt": recent.append(day)
    s = pd.Series(dict(rows)); s.index = pd.to_datetime(s.index)
    ret = np.log(s / s.shift().fillna(cap0)); yrs = (s.index[-1] - s.index[0]).days / 365.25
    mo = s.resample("ME").last().pct_change().fillna(s.resample("ME").last().iloc[0] / cap0 - 1)
    return dict(trades=int((ret != 0).sum()), final=s.iloc[-1], cagr=((s.iloc[-1] / cap0) ** (1 / yrs) - 1) * 100,
                sharpe=ret.mean() / ret.std() * np.sqrt(252), maxdd=((s / s.cummax()) - 1).min() * 100, worst_mo=mo.min() * 100, pos_mo=f"{int((mo>0).sum())}/{len(mo)}")
S = [("A ideal: margin>=$25k, long/short, $0 comm, 0.5/1bp slip", dict(cap0=100_000, entry_slip=0.5, exit_slip=1.0)),
     ("B realistic: margin>=$25k, long/short, $0 comm, 1/2bp", dict(cap0=100_000)),
     ("C stressed: margin>=$25k, long/short, $0 comm, 3/5bp", dict(cap0=100_000, entry_slip=3, exit_slip=5)),
     ("D IBKR Pro fixed, $100k, long/short, 1/2bp", dict(cap0=100_000, broker="ibkr_fixed")),
     ("E IBKR Pro fixed, $25k, long/short, 1/2bp", dict(cap0=25_000, broker="ibkr_fixed")),
     ("F PDT margin <$25k ($10k), max 3/5days, $0 comm", dict(cap0=10_000, acct="pdt")),
     ("G cash acct long-only, $10k, $0 comm, 1/2bp", dict(cap0=10_000, acct="cash_long")),
     ("H cash acct long-only, $2,500, whole shares", dict(cap0=2_500, acct="cash_long")),
     ("I cash acct long-only, $250, whole shares", dict(cap0=250, acct="cash_long")),
     ("J cash acct long-only, $250, IBKR $1 min", dict(cap0=250, acct="cash_long", broker="ibkr_fixed")),
     ("K cash acct long-only, $2,500, IBKR $1 min", dict(cap0=2_500, acct="cash_long", broker="ibkr_fixed"))]
out = []
for lab, kw in S:
    a = sim(**kw); h = sim(**kw, start="2026-08-11")
    out.append(dict(scenario=lab, start=kw["cap0"], trades=a["trades"], final=round(a["final"]), CAGR=round(a["cagr"], 1), Sharpe=round(a["sharpe"], 2),
                    maxDD=round(a["maxdd"], 1), worst_mo=round(a["worst_mo"], 1), pos_months=a["pos_mo"], holdout_ret=round((h["final"] / kw["cap0"] - 1) * 100, 1)))
pd.set_option("display.width", 250); print(pd.DataFrame(out).to_string(index=False))
print("period:", tr.index.min().date(), "->", tr.index.max().date(), "| holdout_ret = return over 2026-08-11..10-16 (46 sessions)")
