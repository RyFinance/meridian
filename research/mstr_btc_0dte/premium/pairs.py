"""MSTR vs BTC relative value: trade the residual of log(MSTR) on log(BTC) back toward its rolling mean.
Signal at 16:00 ET close of day t (MSTR close, BTC at 16:00); execution at the NEXT session's 09:30 open
(MSTR official open, BTC at 09:30). Position: z>Z -> short MSTR / long beta x BTC; z<-Z -> long MSTR / short beta x BTC.
Exit when |z|<0.5 or after H sessions, at the open. Gross notional 1.0 (MSTR leg) + beta (BTC leg), scored on the
MSTR leg's notional. Costs: MSTR 3 bp/side + $0.005/sh; BTC leg 5 bp/side; carry: MSTR short borrow 2%/yr,
BTC leg 5%/yr either way (futures basis/funding or spot borrow), prorated by calendar days."""
import numpy as np, pandas as pd
from pathlib import Path
H0 = Path(__file__).parent
P = pd.read_parquet(H0 / "panel.parquet")

def run(L=40, Z=2.0, HOLD=10, BW=120, start=None, end=None, stress=1.0):
    d = P.copy()
    lm, lb = np.log(d.mstr), np.log(d.btc)
    cov = (lm.diff()).rolling(BW).cov(lb.diff()); var = lb.diff().rolling(BW).var()
    beta = (cov / var).clip(0.3, 3.0)
    r = lm - beta * lb
    # residual measured with the SAME beta over the window: use returns-based spread instead (robust to beta drift)
    spread = (lm.diff() - beta.shift(1) * lb.diff()).cumsum()
    z = (spread - spread.rolling(L).mean()) / spread.rolling(L).std()
    d = d.assign(z=z, beta=beta.shift(1))
    idx = d.index
    pos, rows, i = 0, [], 0
    trades = []
    while i < len(idx) - 1:
        t = idx[i]
        if pos == 0 and np.isfinite(d.z.iloc[i]) and abs(d.z.iloc[i]) >= Z:
            pos = -1 if d.z.iloc[i] > 0 else 1
            j0 = i + 1; bta = d.beta.iloc[i]
            e_m, e_b = d.mstr_open.iloc[j0], d.btc_open.iloc[j0]
            j = j0
            while j < len(idx) - 1 and (j - j0) < HOLD and abs(d.z.iloc[j]) > 0.5:
                j += 1
            x_m, x_b = d.mstr_open.iloc[min(j + 1, len(idx) - 1)], d.btc_open.iloc[min(j + 1, len(idx) - 1)]
            days = (idx[min(j + 1, len(idx) - 1)] - idx[j0]).days
            gross = pos * (np.log(x_m / e_m) - bta * np.log(x_b / e_b))
            cost = stress * (2 * (3e-4 + 0.005 / e_m) + bta * 2 * 5e-4)
            carry = stress * days / 365 * ((0.02 if pos < 0 else 0.0) + bta * 0.05)
            trades.append(dict(entry=idx[j0], exit=idx[min(j + 1, len(idx) - 1)], side=pos, beta=bta, days=days,
                               gross=gross, net=gross - cost - carry))
            i = j + 1; pos = 0
        else:
            i += 1
    t = pd.DataFrame(trades)
    if t.empty: return t
    if start: t = t[t.entry >= start]
    if end: t = t[t.entry <= end]
    return t

def stats(t, years):
    if t is None or len(t) < 3: return {"n": 0 if t is None else len(t)}
    x = t.net
    return {"n": len(t), "win": round((x > 0).mean(), 2), "mean_bp": round(x.mean() * 1e4, 1), "t": round(x.mean() / x.std() * np.sqrt(len(x)), 2),
            "total": round(x.sum(), 3), "per_yr": round(x.sum() / years, 3), "avg_days": round(t.days.mean(), 1)}
