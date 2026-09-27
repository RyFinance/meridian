"""Treasury auction demand surprise -> post-auction yield reversal (research/tsy_auction_demand/PLAN.md). Frozen by the plan."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
AUCT = ROOT / "data" / "c4" / "tsy_auctions"
FRED = ROOT / "data" / "c4" / "fred"
BUCKET_SERIES = {2: "DGS2", 3: "DGS3", 5: "DGS5", 7: "DGS7", 10: "DGS10", 20: "DGS20", 30: "DGS30"}
HOLD, DUR, SCALE = 5, 7.0, 4.0
N_MED, MIN_MED, N_SD, MIN_SD, CLIP = 6, 4, 12, 6, 2.0
COSTS = {"gross": 0.0, "base": 2e-4, "stress": 6e-4}          # price units per side per unit |w|


def bucket(m: float) -> int:
    for lim, b in ((2.5, 2), (3.5, 3), (6.0, 5), (8.5, 7), (15.0, 10), (25.0, 20)):
        if m < lim:
            return b
    return 30


def load_auctions() -> pd.DataFrame:
    rows = []
    for f in sorted(AUCT.glob("auctions_query_p*.json")):
        rows += json.loads(f.read_text())["data"]
    d = pd.DataFrame(rows)
    d = d[d.security_type.isin(["Note", "Bond"]) & (d.inflation_index_security != "Yes") & (d.floating_rate != "Yes")]
    d = d[~d.bid_to_cover_ratio.isin(["null", None, ""])].copy()
    d["auction_date"] = pd.to_datetime(d.auction_date)
    d["btc"] = d.bid_to_cover_ratio.astype(float)
    m = (pd.to_datetime(d.maturity_date) - pd.to_datetime(d.issue_date)).dt.days / 365.25
    d["bucket"] = m.map(bucket)
    return d[["auction_date", "cusip", "security_term", "bucket", "btc"]].sort_values(["auction_date", "bucket"]).reset_index(drop=True)


def signals(d: pd.DataFrame) -> pd.DataFrame:
    out = []
    for b, g in d.groupby("bucket"):
        g = g.sort_values("auction_date").copy()
        med = g.btc.shift(1).rolling(N_MED, min_periods=MIN_MED).median()
        g["surprise"] = g.btc - med
        sd = g.surprise.shift(1).rolling(N_SD, min_periods=MIN_SD).std(ddof=1)
        g["z"] = (g.surprise / sd).clip(-CLIP, CLIP)
        g["w"] = -g["z"]                                            # weak demand -> long duration (fixed direction)
        out.append(g)
    return pd.concat(out).dropna(subset=["w"]).sort_values("auction_date").reset_index(drop=True)


def yields() -> pd.DataFrame:
    Y = {}
    for b, s in BUCKET_SERIES.items():
        x = pd.read_csv(FRED / f"{s}.csv")
        x.columns = ["date", "v"]
        Y[b] = pd.Series(pd.to_numeric(x.v, errors="coerce").to_numpy(), index=pd.to_datetime(x.date))
    Y = pd.DataFrame(Y)
    Y[30] = Y[30].fillna(Y[20])                                     # DGS30 gap 2002-02..2006-02
    return Y.dropna(how="all")


def book(ev: pd.DataFrame, Y: pd.DataFrame, cost_key: str, window: tuple[str, str], w_col: str = "w") -> tuple[pd.Series, pd.DataFrame]:
    """Calendar-time daily return of the event book over the window's yield dates; per-event records."""
    cost = COSTS[cost_key]
    days = Y.loc[window[0]:window[1]].index
    pnl = pd.Series(0.0, index=Y.index)
    recs = []
    ev = ev[(ev.auction_date >= window[0]) & (ev.auction_date <= window[1])]
    for _, e in ev.iterrows():
        y = Y[e.bucket].dropna()
        if e.auction_date not in y.index:
            continue
        i = y.index.get_loc(e.auction_date)
        if i + HOLD >= len(y):
            continue
        seg = y.iloc[i:i + HOLD + 1]
        dy = seg.diff().iloc[1:]                                    # pct points
        r = e[w_col] * (-dy / 100.0) * DUR / SCALE
        r.iloc[0] -= cost * abs(e[w_col]) / SCALE
        r.iloc[-1] -= cost * abs(e[w_col]) / SCALE
        pnl.loc[r.index] += r.to_numpy()
        recs.append({"auction_date": e.auction_date, "bucket": e.bucket, "w": e[w_col],
                     "dy_bp": float((seg.iloc[-1] - seg.iloc[0]) * 100), "event_ret": float(r.sum() * SCALE)})
    return pnl.reindex(days).fillna(0.0), pd.DataFrame(recs)
