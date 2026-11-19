"""Cycle 8 portfolio engine (FRAMEWORK §3-§4), vectorised over bootstrap paths.

One generic step simulator serves both frequencies:
- monthly (bootstrap): one step per month, rebalance every step, margin checked at month-end;
- daily (historical): one step per trading day, rebalance on each month's first trading day, margin checked daily.

Funded sleeves are held at L * w_i of NAV, financed by a margin loan of (L - 1) * NAV (plus trading costs).
Unfunded overlays carry L * o_j * NAV of notional, fixed between rebalances, and book P&L = notional * excess return.
Margin requirement = MAINT_FUNDED * funded assets + MAINT_OVERLAY * |overlay notional| (ADDENDUM_1 §2).
"""
from __future__ import annotations

import numpy as np

MAINT_FUNDED = 0.30
MAINT_OVERLAY = 0.10
RESTORE = 0.35 / 0.30          # liquidate back to maintenance + 5-point buffer (scaled to the requirement)
LIQ_COST = 0.01                # paid on the amount sold in a forced liquidation


def margin_call(A, O, D, alive):
    """Scale all positions by k in [0, 1] so that equity = RESTORE * requirement, paying LIQ_COST on assets sold.

    A: (P, n) funded holdings; O: (P, m) overlay notionals; D: (P,) loan (negative = cash). Returns A, O, D, hit.
    Overlay P&L is booked into D (the cash/loan account) as it accrues, so equity = sum(A) - D.
    """
    E = A.sum(1) - D
    gA = A.sum(1)
    req = MAINT_FUNDED * gA + MAINT_OVERLAY * np.abs(O).sum(1)
    hit = alive & (E < req) & (E > 0)
    if not hit.any():
        return A, O, D, hit
    # after scaling by k: E' = E - LIQ_COST (1 - k) gA ; req' = k req ; want E' = RESTORE req'
    denom = RESTORE * req - LIQ_COST * gA
    with np.errstate(divide="ignore", invalid="ignore"):
        k = np.where(denom > 0, (E - LIQ_COST * gA) / denom, 0.0)
    k = np.where(hit, np.clip(k, 0.0, 1.0), 1.0)
    sold = (1 - k) * gA
    A = A * k[:, None]
    O = O * k[:, None]
    D = D - sold * (1 - LIQ_COST)
    return A, O, D, hit


def simulate(R, X, carry, w, o, L, cost_funded, cost_overlay, rebal):
    """Step simulation.

    R: (P, S, n) funded sleeve simple returns per step (net of fee/WHT drags);
    X: (P, S, m) overlay excess returns per step (net of drags);
    carry: (P, S, 2) per-step [margin rate on a positive loan, cash rate on a negative loan];
    w: (P, S, n) or (n,) target funded weights at 1.0x (sum to 1); o: (m,) overlay weights at 1.0x; L: leverage;
    cost_funded: (n,) one-way cost per unit notional traded; cost_overlay: (m,);
    rebal: (S,) bool, rebalance to target at the START of that step (first step must be True).

    Returns dict(wealth (P, S+1) equity after each step, calls (P,), ruined (P,), turnover (P,) total).
    """
    R = np.asarray(R, float)
    X = np.asarray(X, float)
    P, S, n = R.shape
    m = X.shape[2]
    o = np.asarray(o, float)
    cf = np.asarray(cost_funded, float)
    co = np.asarray(cost_overlay, float)
    wv = np.asarray(w, float)
    per_step_w = wv.ndim == 3
    A = np.zeros((P, n))
    O = np.zeros((P, m))
    D = -np.ones(P)                 # start with 1.0 of cash
    alive = np.ones(P, bool)
    wealth = np.empty((P, S + 1))
    wealth[:, 0] = 1.0
    calls = np.zeros(P, int)
    turnover = np.zeros(P)
    started = False
    for s in range(S):
        if rebal[s]:
            E = A.sum(1) - D
            ws = wv[:, s, :] if per_step_w else wv[None, :]
            At = L * ws * E[:, None]
            Ot = L * o[None, :] * E[:, None]
            if started:
                tr_a = np.abs(At - A)
                tr_o = np.abs(Ot - O)
                tc = (tr_a * cf[None, :]).sum(1) + (tr_o * co[None, :]).sum(1)
                turnover += np.where(E > 0, (tr_a.sum(1) + tr_o.sum(1)) / np.where(E > 0, E, 1), 0)
                E = E - tc
                At = L * ws * E[:, None]
                Ot = L * o[None, :] * E[:, None]
            else:
                started = True      # start fully invested, no entry cost (declared)
            A = np.where(alive[:, None], At, 0.0)
            O = np.where(alive[:, None], Ot, 0.0)
            D = np.where(alive, A.sum(1) - E, 0.0)
        # returns for the step
        A = A * (1 + R[:, s, :])
        pnl = (O * X[:, s, :]).sum(1)
        rate = np.where(D > 0, carry[:, s, 0], carry[:, s, 1])
        D = D * (1 + rate) - pnl
        E = A.sum(1) - D
        dead = alive & (E <= 0)
        if dead.any():
            alive &= ~dead
            A[dead] = 0.0
            O[dead] = 0.0
            D[dead] = 0.0
        if L > 1 or o.any() or np.any(wv.sum(axis=-1) * L > 1.0000001):
            A, O, D, hit = margin_call(A, O, D, alive)
            calls += hit
        wealth[:, s + 1] = np.where(alive, A.sum(1) - D, 0.0)
    return {"wealth": wealth, "calls": calls, "ruined": ~alive, "turnover": turnover}


def max_drawdown(wealth):
    """(P, S+1) -> (P,) maximum drawdown as a positive fraction (1.0 = ruin)."""
    peak = np.maximum.accumulate(wealth, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        dd = 1 - wealth / peak
    return np.nan_to_num(dd, nan=1.0).max(1)
