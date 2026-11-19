"""NAIL long-history panel (2016+) for the desk's research tab.
Signal: d = sign(TLT last pre-market trade 08:00-09:25 ET / TLT 15:59 close prev session), the tradable bond proxy
from alpaca_check/confirm.py (futures hourly data only starts 2024). Trade: NAIL 09:30 open -> 10:29 close, Alpaca SIP 1m.
regime_corr = past-only 60d corr(ITB, TLT daily log returns); the live switch trades only when it is > 0."""
import glob, numpy as np, pandas as pd

B = "research/zb_itb/alpaca_check/bars/"
C = "research/zb_itb/verify/yf_cache/"
OUT = "research/zb_itb/verify/long_history_panel_NAIL.parquet"


def daily(sym):
    d = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(f"{B}{sym}_*.parquet"))])
    d["day"] = d.t.dt.tz_localize(None).dt.normalize(); d["mins"] = d.t.dt.hour * 60 + d.t.dt.minute
    return pd.DataFrame({
        "o930": d[d.mins == 570].groupby("day").o.first(), "c1029": d[d.mins == 629].groupby("day").c.last(),
        "c1559": d[d.mins == 959].groupby("day").c.last(),
        "pre925": d[(d.mins >= 480) & (d.mins <= 565)].sort_values("t").groupby("day").c.last(),
    }).sort_index()


if __name__ == "__main__":
    tlt, nail = daily("TLT"), daily("NAIL")
    sig = np.sign(np.log(tlt.pre925 / tlt.c1559.shift()))
    ri = pd.read_parquet(C + "ITB_1d.parquet")["Adj Close"]; rt = pd.read_parquet(C + "TLT_1d.parquet")["Adj Close"]
    corr = np.log(ri).diff().rolling(60).corr(np.log(rt).diff()).shift()
    p = pd.DataFrame({"d": sig, "ret": np.log(nail.c1029 / nail.o930)}).dropna()
    p = p[p.d != 0]
    p["regime_corr"] = corr.reindex(p.index)
    p.to_parquet(OUT)
    net = p.d * p.ret - 10e-4
    on = net[p.regime_corr > 0]
    for lab, x in [("all", net), ("switch on", on)]:
        print(f"{lab:10s} n {len(x)} mean {x.mean()*1e4:+.1f}bp t {x.mean()/x.std()*np.sqrt(len(x)):+.2f} {x.index[0].date()}..{x.index[-1].date()}")
