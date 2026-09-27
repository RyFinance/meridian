"""Frozen BOOK -> instrument target weights -> vehicle target weights (no returns are used anywhere here).

Instrument weights. For holding month h, the paper BOOK holds sleeve S with scaled weight k_h w_{S,h}
(``book/weights.csv`` ``scaled_weight``) and sleeve S holds W_{S,h-1,i} (component ``weights.parquet``, formed at
signal month h-1). The book-level target notional of instrument i (fraction of NAV) is
    x_{h,i} = sum_S k_h w_{S,h} W_{S,h-1,i}
and the core contributes k_h w_{CORE,h} * core_weight_j to instrument ``CORE:<ticker>``.

Vehicle weights. Each instrument has an ordered candidate list [{vehicle, from}] (spec params). At month h the first
candidate whose ``from`` month is <= h and whose vehicle is available at h is used; none -> the instrument's weight is
dropped (recorded). Long/flat variants clip x at zero at the INSTRUMENT level before mapping. Instruments mapping to
one vehicle are summed. Finally the vehicle vector is scaled by c_h = min(1, gross_cap / sum_v |y_v|) (never up).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _months(s) -> pd.PeriodIndex:
    return pd.PeriodIndex(pd.Series(s).astype(str), freq="M")


def component_weights_wide(long: pd.DataFrame) -> pd.DataFrame:
    """signal_month x market_id weights (formed at the signal month-end)."""
    d = long.copy()
    d["signal_month"] = _months(d["signal_month"])
    return d.pivot_table(index="signal_month", columns="market_id", values="weight", aggfunc="sum").fillna(0.0)


def instrument_weights(book_w: pd.DataFrame, comp_w: dict, core: dict) -> pd.DataFrame:
    """book_w: long (month, sleeve, scaled_weight); comp_w: {sleeve: long weights}; core: {"sleeve", "markets",
    "weights"}. Returns holding month x instrument target weights (fraction of NAV)."""
    bw = book_w.copy()
    bw["month"] = _months(bw["month"])
    K = bw.pivot_table(index="month", columns="sleeve", values="scaled_weight", aggfunc="sum").fillna(0.0)
    months = K.index
    parts = []
    for s in K.columns:
        k = K[s]
        if s == core["sleeve"]:
            cw = pd.DataFrame({f"CORE:{m}": k * w for m, w in zip(core["markets"], core["weights"])}, index=months)
            parts.append(cw)
            continue
        if s not in comp_w:
            raise ValueError(f"book sleeve {s} has no component weights")
        W = component_weights_wide(comp_w[s])
        W.index = W.index + 1                                   # formed at h-1, held in h
        W = W.reindex(months).fillna(0.0)
        parts.append(W.mul(k, axis=0))
    X = pd.concat(parts, axis=1)
    X = X.T.groupby(level=0).sum().T                            # same instrument in several sleeves -> summed
    return X.reindex(sorted(X.columns), axis=1)


def choose_vehicle(cands: list, h: pd.Period, available) -> str | None:
    for c in cands:
        v = c.get("vehicle")
        if v is None:
            continue
        if c.get("from") is not None and h < pd.Period(c["from"], "M"):
            continue
        if available(v, h):
            return v
    return None


def vehicle_targets(X: pd.DataFrame, mapping: dict, available, *, long_only: bool, gross_cap: float):
    """Returns (Y months x vehicles, info frame per month, dropped long frame, chosen-vehicle long frame)."""
    unknown = [c for c in X.columns if c not in mapping]
    if unknown:
        raise ValueError(f"instruments without a mapping entry: {unknown}")
    Xc = X.clip(lower=0.0) if long_only else X
    rows, drops, chosen = {}, [], []
    info = []
    for h in X.index:
        y = {}
        lost_gross = 0.0
        for i in X.columns:
            xi = float(Xc.at[h, i])
            if xi == 0.0:
                continue
            v = choose_vehicle(mapping[i], h, available)
            if v is None:
                drops.append({"month": str(h), "instrument": i, "weight": xi})
                lost_gross += abs(xi)
                continue
            chosen.append({"month": str(h), "instrument": i, "vehicle": v, "weight": xi})
            y[v] = y.get(v, 0.0) + xi
        g = float(sum(abs(v) for v in y.values()))
        c = min(1.0, gross_cap / g) if g > 0 else 1.0
        rows[h] = {v: c * w for v, w in y.items()}
        info.append({"month": h, "paper_gross": float(X.loc[h].abs().sum()),
                     "clipped_gross": float(Xc.loc[h].abs().sum()), "dropped_gross": lost_gross,
                     "mapped_gross": g, "scale": c, "gross": c * g,
                     "net": c * float(sum(y.values()))})
    Y = pd.DataFrame.from_dict(rows, orient="index").reindex(X.index).fillna(0.0)
    Y = Y.reindex(sorted(Y.columns), axis=1)
    return Y, pd.DataFrame(info).set_index("month"), pd.DataFrame(drops), pd.DataFrame(chosen)


def first_active_month(Y: pd.DataFrame):
    nz = Y.abs().sum(axis=1) > 0
    return nz[nz].index.min() if nz.any() else None


def paper_decomposition(X: pd.DataFrame, R: pd.DataFrame) -> pd.Series:
    """sum_i x_{h,i} R_{h,i} over instruments with a return (a diagnostic against the BOOK's sleeve_ret)."""
    Rr = R.reindex(index=X.index, columns=X.columns)
    return (X * Rr.fillna(0.0)).sum(axis=1).where(Rr.notna().any(axis=1), np.nan)
