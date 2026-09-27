"""Synthetic data-generating processes for the A2 power audit. Synthetic data only.

Every generator returns (net, stress) arrays of shape (W, n) whose TRUE annualised net Sharpe
(mean / marginal sd * sqrt(ppy)) equals the requested S (exactly, or by construction to O(1e-3)).
The stress series is the net series minus an extra cost; unless stated, extra stress drag = 0.10 Sharpe units.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import lfilter

STRESS_DRAG_SR = 0.10


def _finish(z, S, ppy, stress_drag_sr=STRESS_DRAG_SR):
    """z: zero-mean unit-marginal-variance noise. Adds mean for Sharpe S; stress = net - drag."""
    mu = S / np.sqrt(ppy)
    net = z + mu
    stress = net - stress_drag_sr / np.sqrt(ppy)
    return net, stress


# ---------------------------------------------------------------- simple univariate
def iid_normal(W, n, S, ppy, rng, **kw):
    return _finish(rng.standard_normal((W, n)), S, ppy, kw.get("stress_drag_sr", STRESS_DRAG_SR))


def ar1(W, n, S, ppy, rng, phi=0.0, **kw):
    e = rng.standard_normal((W, n + 200))
    z = lfilter([1.0], [1.0, -phi], e, axis=1)[:, 200:] * np.sqrt(1 - phi ** 2)
    return _finish(z, S, ppy, kw.get("stress_drag_sr", STRESS_DRAG_SR))


def student_t(W, n, S, ppy, rng, df=4.0, **kw):
    z = rng.standard_t(df, size=(W, n)) / np.sqrt(df / (df - 2.0))
    return _finish(z, S, ppy, kw.get("stress_drag_sr", STRESS_DRAG_SR))


def carry_crash(W, n, S, ppy, rng, lam_per_year=0.2, jump_sd_mult=6.0, **kw):
    """Carry: steady positive drift + rare negative jumps (crashes). Normalised to unit variance.

    x = d + e - J * Bernoulli(lam), e ~ N(0,1), J = jump_sd_mult (in diffusion sd units, J deterministic
    size with small N(0,0.5) dispersion). Mean is then re-set so that the TRUE mean (including crashes)
    gives Sharpe S; i.e. under H0 the carry exactly pays for its crashes.
    """
    lam = lam_per_year / ppy
    jumps = rng.random((W, n)) < lam
    Jsz = jump_sd_mult + 0.5 * rng.standard_normal((W, n))
    raw = rng.standard_normal((W, n)) - jumps * Jsz
    m = -lam * jump_sd_mult
    var = 1.0 + lam * (jump_sd_mult ** 2 + 0.25) - lam ** 2 * jump_sd_mult ** 2
    z = (raw - m) / np.sqrt(var)
    return _finish(z, S, ppy, kw.get("stress_drag_sr", STRESS_DRAG_SR))


def stoch_vol(W, n, S, ppy, rng, persist=0.98, volvol=0.15, **kw):
    """Log-SV noise, normalised to unit marginal variance (vol clustering, 'noisy' design)."""
    h = lfilter([1.0], [1.0, -persist], rng.standard_normal((W, n + 300)) * volvol, axis=1)[:, 300:]
    var_h = volvol ** 2 / (1 - persist ** 2)
    sig = np.exp(h)
    z = sig * rng.standard_normal((W, n)) / np.sqrt(np.exp(2 * var_h))
    return _finish(z, S, ppy, kw.get("stress_drag_sr", STRESS_DRAG_SR))


def long_short(W, n, S, ppy, rng, beta_res=0.1, mkt_sr=0.4, persist=0.98, volvol=0.12, **kw):
    """Dollar-neutral long-short: SV idiosyncratic spread + small residual market beta.

    TRUE net mean (alpha + beta_res * market premium) is set to give Sharpe S; under H0 the book's
    alpha exactly offsets the leaked premium (mean-zero null, N1)."""
    idio = stoch_vol(W, n, 0.0, ppy, rng, persist=persist, volvol=volvol, stress_drag_sr=0.0)[0]
    mkt = rng.standard_normal((W, n))  # unit-var market shocks; premium absorbed in mean
    z = np.sqrt(1 - beta_res ** 2) * idio + beta_res * mkt
    return _finish(z, S, ppy, kw.get("stress_drag_sr", STRESS_DRAG_SR))


# ---------------------------------------------------------------- long-only timing with exposure control
def long_only_timing(W, n, S, ppy, rng, mkt_sr=0.4, p_stay=0.95, pi_on=0.6, cost_sr=0.05, **kw):
    """Daily long-only timing book: exposure e_t in {0,1} (Markov), market Sharpe 0.4.

    Under H1 the market's conditional mean is higher when e_t=1: r_t = mu_m + delta (e_t - pi) + eps.
    Returns dict with 'raw' (e_t r_t - cost) and 'active' ((e_t - ebar) r_t - cost) series; delta chosen
    so the ACTIVE net series has true Sharpe S (H0: S=0 means timing exactly pays its costs).
    """
    # Markov chain with stationary prob pi_on and stay prob p_stay for the 'on' state
    p10 = 1 - p_stay  # on->off
    p01 = p10 * pi_on / (1 - pi_on)  # off->on
    e = np.empty((W, n))
    cur = rng.random(W) < pi_on
    u = rng.random((W, n))
    for t in range(n):
        cur = np.where(cur, u[:, t] >= p10, u[:, t] < p01)
        e[:, t] = cur
    sig = 1.0
    mu_m = mkt_sr / np.sqrt(ppy) * sig
    eps = rng.standard_normal((W, n)) * sig
    turn = np.abs(np.diff(e, axis=1, prepend=e[:, :1]))
    cpt = cost_sr / np.sqrt(ppy) * sig / max(2 * pi_on * p10, 1e-9)  # cost per switch -> drag cost_sr in raw-sd units
    var_e = pi_on * (1 - pi_on)
    sd_active = sig * np.sqrt(var_e)
    # E[active net] = delta*var_e - cpt*E[turn]; E[turn] = 2*pi*p10
    Eturn = 2 * pi_on * p10
    delta = (S / np.sqrt(ppy) * sd_active + cpt * Eturn) / var_e
    r = mu_m + delta * (e - pi_on) + eps
    ebar = e.mean(axis=1, keepdims=True)
    raw = e * r - cpt * turn
    active = (e - ebar) * r - cpt * turn
    raw_st = raw - cpt * turn  # stress = double cost
    act_st = active - cpt * turn
    return {"raw": (raw, raw_st), "active": (active, act_st)}


# ---------------------------------------------------------------- clustered events -> calendar time
def event_cluster(W, T_years, S, rng, events_per_year=40, cluster=3, icc=0.3, ppy=52, **kw):
    """Weekly calendar-time portfolio of clustered events. Returns dict with the weekly series and the
    event-level returns (for a naive independent-events test)."""
    n = int(round(T_years * ppy))
    n_cl = int(round(events_per_year / cluster * T_years))
    q = n_cl / n
    v = icc + (1 - icc) / cluster  # var of within-week equal-weight event mean (sigma_e = 1)
    Sw = S / np.sqrt(ppy)
    mu = Sw * np.sqrt(q * v / (q * q - Sw * Sw * q * (1 - q))) if S != 0 else 0.0
    # choose event weeks
    keys = rng.random((W, n))
    wk = np.argsort(keys, axis=1)[:, :n_cl]
    c = rng.standard_normal((W, n_cl))
    ei = rng.standard_normal((W, n_cl, cluster))
    ev = mu + np.sqrt(icc) * c[:, :, None] + np.sqrt(1 - icc) * ei  # (W, n_cl, cluster)
    wret = ev.mean(axis=2)
    X = np.zeros((W, n))
    np.put_along_axis(X, wk, wret, axis=1)
    cost_drag = kw.get("stress_drag_sr", 0.10) / np.sqrt(ppy) * np.sqrt(q * v)  # approx sd units
    stress = X - np.where(X != 0, cost_drag / q, 0.0)
    return {"weekly": (X, stress), "events": ev.reshape(W, -1), "mu_event": mu}


# ---------------------------------------------------------------- cross-sectional quintile panel
def xs_quintile(W, n_months, rng, N=300, ic=0.02, tilt=0.3, mkt_vol=0.045, style_vol=0.03,
                idio_vol=0.10, beta_sd=0.3, chunk=100, want_pooled=True):
    """Monthly N-asset one-factor (+ one zero-premium style factor) panel.

    r_it = beta_i f_t + gamma_i h_t + idio_vol * e_it          (f, h zero-mean: mean-zero null)
    s_it = sqrt(1 - tilt^2) * (a e_it + sqrt(1-a^2) u_it) + tilt * gamma_i,   a = ic / sqrt(1 - tilt^2)
    so corr(s_it, e_it) = ic (the IC w.r.t. the idiosyncratic return), and the signal carries a
    persistent tilt on the style loading gamma_i. Returns the top-minus-bottom quintile series (W, n)
    and (optionally) the naive pooled-OLS t-stat of r on s over all N*T observations.
    """
    a = ic / np.sqrt(1 - tilt ** 2)
    q = N // 5
    ls = np.empty((W, n_months))
    tpool = np.empty(W)
    for s in range(0, W, chunk):
        w = min(chunk, W - s)
        beta = 1 + beta_sd * rng.standard_normal((w, 1, N))
        gam = rng.standard_normal((w, 1, N))
        f = mkt_vol * rng.standard_normal((w, n_months, 1))
        h = style_vol * rng.standard_normal((w, n_months, 1))
        e = rng.standard_normal((w, n_months, N))
        u = rng.standard_normal((w, n_months, N))
        sig = np.sqrt(1 - tilt ** 2) * (a * e + np.sqrt(1 - a ** 2) * u) + tilt * gam
        r = beta * f + gam * h + idio_vol * e
        del u
        order = np.argsort(sig, axis=2)
        top = np.take_along_axis(r, order[:, :, -q:], axis=2).mean(axis=2)
        bot = np.take_along_axis(r, order[:, :, :q], axis=2).mean(axis=2)
        ls[s : s + w] = top - bot
        if want_pooled:
            # pooled OLS slope t-stat with iid SEs (month-demeaned = cross-sectional regressions pooled)
            sc = sig - sig.mean(axis=2, keepdims=True)
            rc = r - r.mean(axis=2, keepdims=True)
            sxx = (sc * sc).sum(axis=(1, 2))
            bhat = (sc * rc).sum(axis=(1, 2)) / sxx
            resid = rc - bhat[:, None, None] * sc
            s2 = (resid * resid).sum(axis=(1, 2)) / (n_months * N - n_months - 1)
            tpool[s : s + w] = bhat / np.sqrt(s2 / sxx)
    return ls, tpool
