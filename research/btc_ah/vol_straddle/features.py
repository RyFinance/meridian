"""Overnight BTC features per trading night (Mon/Fri MSTR session). Bars stamped <= 09:28 ET only (known by 09:29).
Night for trading day d = [previous weekday 16:00 ET, d 09:29 ET). Dev stage: BTC data kept < 2024-01-01."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
BTC = "/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet"
DEV_STAGE_END = pd.Timestamp("2024-01-01")  # dev stage loads nothing at/after this date


def load_btc() -> pd.DataFrame:
    b = pd.read_parquet(BTC)
    t = b.timestamp.dt.tz_convert("America/New_York").dt.tz_localize(None)
    df = pd.DataFrame({"t": t, "o": b.open.values, "h": b.high.values, "l": b.low.values, "c": b.close.values})
    df = df[df.t < DEV_STAGE_END].sort_values("t").reset_index(drop=True)
    return df


def nights(btc: pd.DataFrame, start="2020-07-01", end="2023-12-29") -> pd.DataFrame:
    wd = pd.bdate_range(start, end)  # weekday trading-night mornings
    t = btc.t.values
    rows = []
    for w in wd:
        pw = w - pd.offsets.BDay(1)
        s = pd.Timestamp(pw) + pd.Timedelta(hours=16)
        e = pd.Timestamp(w) + pd.Timedelta(hours=9, minutes=29)
        i0 = np.searchsorted(t, np.datetime64(s), "left")
        i1 = np.searchsorted(t, np.datetime64(e), "left")
        g = btc.iloc[i0:i1]
        if len(g) < 600:
            continue
        px0 = g.o.iloc[0]
        px1 = g.c.iloc[-1]
        lr = np.diff(np.log(np.concatenate([[px0], g.c.values])))
        hours = (e - s).total_seconds() / 3600
        rvh = np.sqrt(np.sum(lr ** 2) / hours)
        p08 = g[g.t < pd.Timestamp(w) + pd.Timedelta(hours=8)].c
        p08 = p08.iloc[-1] if len(p08) else np.nan
        early = p08 / px0 - 1
        late = px1 / p08 - 1
        net = px1 / px0 - 1
        rng = (g.h.max() - g.l.min()) / px0
        rows.append(dict(date=w, dow=w.dayofweek, net=net, rng=rng, rvh=rvh, early=early, late=late,
                         late_share=abs(late) / (abs(early) + abs(late) + 1e-12),
                         ratio=rng / max(abs(net), 1e-4), nbars=len(g)))
    n = pd.DataFrame(rows).set_index("date")
    # trailing 20 PRIOR nights (weekday nights, excluding the current one)
    past = n.rvh.shift(1).rolling(20, min_periods=20)
    n["rv_z20"] = (n.rvh - past.mean()) / past.std()
    n["rv_mr20"] = n.rvh / past.median()
    return n


if __name__ == "__main__":
    btc = load_btc()
    n = nights(btc)
    p = pd.read_parquet("/Users/rytty/CCP/quant_v7/research/mstr_btc_0dte/daily_panel.parquet")
    j = n.join(p[["btc_off"]], how="inner")
    print("nights", len(n), "matched to panel", len(j), "corr(net, btc_off)=", round(j.net.corr(j.btc_off), 4))
    n.to_parquet(HERE / "night_features_dev.parquet")
    print(n.describe().T.round(4).to_string())
