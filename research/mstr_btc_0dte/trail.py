"""Let-winners-run rule on 1-minute MSTR option prints (dev 2020-23 days from engine.prepare).
Buy the option BTC's overnight move points to (calls if up), strike `steps` from the money, at minute `entry`.
Exit on the first minute (after entry) where the sellable value hits:
  hard stop: value <= cost * (1 - sl)
  trailing:  once value >= cost * (1 + arm), stop = peak * (1 - trail)  (peak = highest sellable value so far)
or at the time stop `tmax` minutes after 09:30. Fills: base / worst as in engine.py."""
import itertools, pickle
from dataclasses import dataclass, asdict
import numpy as np, pandas as pd
from pathlib import Path
from research.mstr_btc_0dte.engine import half_spread, COMM
H = Path(__file__).parent

@dataclass(frozen=True)
class Trail:
    steps: int = 1; entry: int = 1; sl: float = 0.2; arm: float = 0.1; trail: float = 0.1; tmax: int = 390
    fills: str = "base"; flip: bool = False

def trade(day, r):
    if day.btc == 0: return None
    s = (1 if day.btc > 0 else -1) * (-1 if r.flip else 1); typ = "C" if s > 0 else "P"
    sp0 = day.spot.get(r.entry, np.nan)
    if not np.isfinite(sp0): return None
    strikes = sorted(k for (t, k), b in day.bars.items() if t == typ and ((b.index >= r.entry) & (b.index <= r.entry + 4)).any())
    if not strikes: return None
    otm = 1 if typ == "C" else -1
    lad = sorted(strikes, key=lambda k: otm * k); atm = min(strikes, key=lambda k: abs(k - sp0)); i = lad.index(atm)
    if r.steps > 0 and otm * (atm - sp0) < 0: i += 1
    i += max(r.steps - 1, 0) if r.steps > 0 else r.steps
    if not 0 <= i < len(lad): return None
    k = lad[i]; b = day.bars[(typ, k)]
    eb = b[(b.index >= r.entry) & (b.index <= r.entry + 4)]
    if eb.empty: return None
    e = eb.iloc[0]; em = int(eb.index[0]); w = r.fills == "worst"
    cost = (max(e.high, e.close + half_spread(e.close)) if w else e.close + half_spread(e.close)) + COMM
    later = b[(b.index > em) & (b.index <= r.tmax)]
    if later.empty: return None
    val = ((np.minimum(later.low, later.close - half_spread(later.close)) if w else later.close - half_spread(later.close)).clip(lower=0) - COMM)
    peak, armed, out, why = -1e9, False, None, "time"
    for m, v in val.items():
        if v <= cost * (1 - r.sl) and not armed: out, why = v, "stop"; break
        if v >= cost * (1 + r.arm): armed = True
        peak = max(peak, v)
        if armed and v <= peak * (1 - r.trail): out, why = v, "trail"; break
    if out is None: out = float(val.iloc[-1])
    return {"date": day.d, "ret": out / cost - 1, "why": why}

def run(days, r):
    rows = [x for x in (trade(d, r) for d in days) if x]
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()

def st(t):
    if len(t) < 20: return {"n": len(t)}
    x = t.ret
    return {"n": len(x), "win": round((x > 0).mean(), 3), "mean": round(x.mean(), 4), "t": round(x.mean() / x.std() * np.sqrt(len(x)), 2),
            "avg_win": round(x[x > 0].mean(), 3), "avg_loss": round(x[x <= 0].mean(), 3)}

if __name__ == "__main__":
    days = pickle.load(open(H / "dev_days.pkl", "rb"))
    rows = []
    for steps, entry, sl, arm, trail, tmax in itertools.product([-1, 0, 1], [1, 15, 30], [0.1, 0.2, 0.3], [0.05, 0.15, 0.3], [0.1, 0.2, 0.35], [120, 390]):
        r = Trail(steps, entry, sl, arm, trail, tmax)
        row = asdict(r)
        for f in ("base", "worst"):
            row.update({f"{f}_{k}": v for k, v in st(run(days, Trail(**{**asdict(r), "fills": f}))).items()})
        rows.append(row)
    g = pd.DataFrame(rows).drop(columns=["fills", "flip"]); g.to_csv(H / "trail_dev_grid.csv", index=False)
    pd.set_option("display.width", 250)
    print(len(g), "rules; share base mean>0: %.2f, both>0: %.2f" % ((g.base_mean > 0).mean(), ((g.base_mean > 0) & (g.worst_mean > 0)).mean()))
    print(g.sort_values("worst_t", ascending=False).head(15).to_string(index=False))
    for c in ["steps", "entry", "sl", "arm", "trail", "tmax"]:
        print(c, g.groupby(c)[["base_mean", "worst_mean"]].mean().round(4).to_dict("index"))
