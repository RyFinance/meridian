import numpy as np, pandas as pd
from pathlib import Path
from research.mstr_btc_0dte.backtest import load, trades, summarize, THRESH
H = Path(__file__).parent
p, o = load()
pa = p.copy(); pa["btc_off"] = -pa.btc_off
summarize(trades(pa, o, "RAW", "OTM1"), "ANTI-signal RAW OTM1")
# paired: signal vs anti on the same days, gross return-on-premium difference
s, a = trades(p, o, "RAW", "OTM1"), trades(pa, o, "RAW", "OTM1")
j = s.gross.to_frame("s").join(a.gross.rename("a"), how="inner"); dd = j.s - j.a
print(f"paired signal-minus-anti gross: n={len(dd)} mean={dd.mean():+.3f} t={dd.mean()/dd.std()*np.sqrt(len(dd)):+.2f}")
# shares: long/short MSTR open->close, 3 bps per side
print("\nSHARES open->close, 3bp/side cost (bps per trade, annualised Sharpe if traded only these days)")
for nm, cond, sig in [("RAW Mon", p.dow == 0, np.sign(p.btc_off)), ("RAW Fri", p.dow == 4, np.sign(p.btc_off)),
                      ("UNDER Mon", (p.dow == 0) & (p.under.abs() >= THRESH), np.sign(p.under)),
                      ("UNDER Fri", (p.dow == 4) & (p.under.abs() >= THRESH), np.sign(p.under)),
                      ("UNDER Mon+Fri", p.dow.isin([0, 4]) & (p.under.abs() >= THRESH), np.sign(p.under))]:
    r = (sig[cond] * p.mstr_day[cond] - 0.0006).dropna()
    for lab, x in [("all", r), ("<2023-07", r[r.index < "2023-07-01"]), (">=2023-07", r[r.index >= "2023-07-01"])]:
        print(f"  {nm:14s} {lab:10s} n={len(x):3d} mean={x.mean()*1e4:+6.1f}bp win={np.mean(x>0):.2f} t={x.mean()/x.std()*np.sqrt(len(x)):+.2f} Sharpe/yr={x.mean()/x.std()*np.sqrt(len(x)/((x.index[-1]-x.index[0]).days/365.25)):+.2f}")
