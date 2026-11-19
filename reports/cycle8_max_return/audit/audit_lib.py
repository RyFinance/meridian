"""Independent cycle-8 audit helpers. Does NOT import research/cycle8/engine.

Own monthly simulator (vectorised over paths), own sleeve rebuild from the frozen snapshot, own stationary bootstrap.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "data/cycle8/snapshot_store/versions/cycle8_v1/view"
OUT = ROOT / "reports/cycle8_max_return/out"
AUD = ROOT / "reports/cycle8_max_return/audit"

# declared costs (menu.py COST / COST_OVERLAY, re-typed by hand from FRAMEWORK §4.4 + ADDENDUM_1 §3)
COST = {"EQ": 0.0005, "BOND": 0.0005, "GOLD": 0.0010, "TREND": 0.0020, "CASH": 0.0}
COST_OV = {"X_TREND": 0.0002, "X_BOND": 0.0002}

# item specs: funded {sleeve: w}, overlay {col: w}
ITEMS = {
    "P1u": ({"EQ": 1.0}, {}),
    "P3": ({"EQ": 0.6, "BOND": 0.4}, {}),
    "P4": ({"EQ": 0.48, "BOND": 0.32, "GOLD": 0.10, "TREND": 0.10}, {}),
    "P6a": ({"EQ": 1.0}, {"X_TREND": 0.5}),
}


def me(ix):
    return pd.DatetimeIndex(ix).to_period("M").to_timestamp("M")


def eqcol(L):
    return "EQ_G_tfsa" if L == 1.0 else "EQ_G_margin"


def sim(R, X, mr, cash, w, o, L, cf, co, check_margin=True):
    """Own monthly simulator.

    R (P,T,n) funded sleeve returns; X (P,T,m) overlay excess; mr, cash (P,T) monthly rates;
    w (n,) funded weights; o (m,) overlay weights. Rebalance to L*w*E at each month start (cost on |trade|),
    loan = funded - E pays mr (earns cash if negative). Overlay notional L*o*E; P&L = notional * x.
    Month-end margin check: equity < 0.30*funded + 0.10*|overlay| -> scale down to restore 35/30 of requirement,
    1% cost on sold. equity <= 0 -> ruin.
    Returns wealth (P, T+1), calls (P,).
    """
    P, T, n = R.shape
    m = X.shape[2]
    E = np.ones(P)
    A = np.zeros((P, n))
    O = np.zeros((P, m))
    alive = np.ones(P, bool)
    W = np.ones((P, T + 1))
    calls = np.zeros(P, int)
    for t in range(T):
        At = L * w[None, :] * E[:, None]
        Ot = L * o[None, :] * E[:, None]
        if t > 0:
            tc = (np.abs(At - A) * cf).sum(1) + (np.abs(Ot - O) * co).sum(1)
            E = E - tc
            At = L * w[None, :] * E[:, None]
            Ot = L * o[None, :] * E[:, None]
        At[~alive] = 0
        Ot[~alive] = 0
        loan = At.sum(1) - E
        rate = np.where(loan > 0, mr[:, t], cash[:, t])
        A = At * (1 + R[:, t, :])
        O = Ot
        E = A.sum(1) - loan * (1 + rate) + (O * X[:, t, :]).sum(1)
        dead = alive & (E <= 0)
        alive &= ~dead
        E = np.where(alive, E, 0.0)
        A[~alive] = 0
        O[~alive] = 0
        if check_margin and (L > 1 or o.any()):
            gA = A.sum(1)
            req = 0.30 * gA + 0.10 * np.abs(O).sum(1)
            hit = alive & (E < req)
            if hit.any():
                k = np.clip((E - 0.01 * gA) / (0.35 / 0.30 * req - 0.01 * gA), 0, 1)
                k = np.where(hit, k, 1.0)
                E = E - 0.01 * (1 - k) * gA
                A = A * k[:, None]
                O = O * k[:, None]
                calls += hit
        W[:, t + 1] = E
    return W, calls


def item_arrays(M, item, L, xcol_override=None):
    f, ov = ITEMS[item]
    cols = [eqcol(L) if s == "EQ" else s for s in f]
    w = np.array(list(f.values()))
    cf = np.array([COST[s] for s in f])
    ocols = list(ov)
    o = np.array(list(ov.values())) if ov else np.zeros(1)
    co = np.array([COST_OV[c] for c in ocols]) if ov else np.zeros(1)
    need = cols + ocols + ["MRATE", "CASH"]
    return cols, ocols, w, o, cf, co, need


def hist(M, item, L, start=None, end=None):
    cols, ocols, w, o, cf, co, need = item_arrays(M, item, L)
    Mw = M[need].dropna()
    Mw = Mw.loc["1971-02":]
    if start:
        Mw = Mw.loc[start:]
    if end:
        Mw = Mw.loc[:end]
    R = Mw[cols].values[None]
    X = Mw[ocols].values[None] if ocols else np.zeros((1, len(Mw), 1))
    W, calls = sim(R, X, Mw["MRATE"].values[None], Mw["CASH"].values[None], w, o, L, cf, co)
    wser = pd.Series(W[0, 1:], index=Mw.index)
    r = wser / pd.Series(W[0, :-1], index=Mw.index) - 1
    return r, int(calls[0])


def stats(r, rf):
    r = r.dropna()
    rf = rf.reindex(r.index)
    w = np.r_[1.0, (1 + r.values).cumprod()]
    yrs = len(r) / 12
    ex = r - rf
    dd = 1 - w / np.maximum.accumulate(w)
    return {"start": f"{r.index[0]:%Y-%m}", "end": f"{r.index[-1]:%Y-%m}", "months": len(r),
            "cagr": w[-1] ** (1 / yrs) - 1, "vol": r.std() * np.sqrt(12),
            "sharpe": ex.mean() / ex.std() * np.sqrt(12), "maxdd": dd.max()}


def sb_idx(n, T, P, mb, rng):
    """Own stationary bootstrap: geometric blocks, circular."""
    idx = np.empty((P, T), np.int64)
    cur = rng.integers(0, n, P)
    for t in range(T):
        if t > 0:
            jump = rng.random(P) < 1 / mb
            cur = np.where(jump, rng.integers(0, n, P), (cur + 1) % n)
        idx[:, t] = cur
    return idx


def boot(Mw, item, L, P=10000, mb=24, H=240, seed=1, tols=(0.25, 0.35, 0.50)):
    cols, ocols, w, o, cf, co, need = item_arrays(Mw, item, L)
    D = Mw[need].dropna()
    arr = D.values
    rng = np.random.default_rng(seed)
    idx = sb_idx(len(arr), H, P, mb, rng)
    Z = arr[idx]
    nf, no = len(cols), len(ocols)
    R = Z[:, :, :nf]
    X = Z[:, :, nf:nf + no] if no else np.zeros((P, H, 1))
    W, calls = sim(R, X, Z[:, :, -2], Z[:, :, -1], w, o, L, cf, co)
    dd = (1 - W / np.maximum.accumulate(W, 1)).max(1)
    out = {f"p_dd{int(t*100)}": float((dd > t).mean()) for t in tols}
    out["p_ruin"] = float((W[:, -1] <= 0).mean())
    out["n_months"] = len(D)
    out["window"] = f"{D.index[0]:%Y-%m}..{D.index[-1]:%Y-%m}"
    return out
