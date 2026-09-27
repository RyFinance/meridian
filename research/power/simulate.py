"""research.power.simulate -- seeded Monte Carlo verifiers for every analytic formula in research.power.

Each verifier simulates synthetic data with the stated correlation structure and applies the decision rule the
way a practitioner would compute it (sample Sharpe with an estimated vol, a literal mean-centred circular block
bootstrap p, a literal Newey-West t, a calendar-time portfolio, cross-sectional Pearson ICs, literal quantile
sorts with realised turnover and costs, ...). The analytic value is then compared with the simulated one.

  timeseries      AR(1) / overlapping-horizon Gaussian paths; literal CBB p-value           (sim_series, mc_gate)
  two-stage       one continuous path split into dev and validation windows                 (mc_two_stage)
  event study     Poisson arrivals in earnings-style seasons, hold h days, one-factor daily  (mc_event_study)
                  cross-event correlation; calendar-time portfolio test vs naive event t
  cross-section   one-factor residuals with Rademacher (style/sector) loadings and a signal  (mc_cross_sectional_ic)
                  tilted to the same factor; overlapping-horizon IC autocorrelation
  long-short      the same structure with AR(1) signals, literal decile sorts, turnover, cost (mc_long_short)
  carry           common crash factor (normal + Bernoulli jump) + idiosyncratic noise, K assets (mc_carry)
  panel           block-correlated K markets x T periods, AR(1); naive pooled t vs EW book  (mc_panel)
  sleeve screen   k sleeves, m real, inclusion screen, hold-out HAC t on the book           (mc_sleeve_screen)

Everything is synthetic. No project data is read.
"""
from __future__ import annotations

import math
import zlib

import numpy as np
from scipy import stats
from scipy.signal import lfilter

from research.power.core import SEED, Autocorr, SeriesModel, z_upper
from research.power.designs import concurrency_profile, crash_moments
from research.power.gates import Gate


def rng_for(*salt) -> np.random.Generator:
    """Deterministic across processes (zlib.crc32, not Python's randomised str hash)."""
    return np.random.default_rng(np.random.SeedSequence([SEED, *[zlib.crc32(repr(s).encode()) for s in salt]]))


# ============================================================================================ series simulation
def sim_series(ac: Autocorr, n: int, n_paths: int, rng: np.random.Generator) -> np.ndarray:
    """Unit-variance stationary Gaussian series with the autocorrelation `ac`; shape (n_paths, n)."""
    model = ac.model
    phi = ac.phi
    if model == "lrv":
        D = float(ac.D)
        phi = (D - 1) / (D + 1)          # AR(1) with the same long-run variance ratio
        model = "ar1"
    if model == "ar1":
        e = rng.standard_normal((n_paths, n))
        e[:, 1:] *= math.sqrt(1 - phi * phi)
        return lfilter([1.0], [1.0, -phi], e, axis=1) if phi != 0 else e
    if model in ("overlap", "ar1_overlap"):
        H = ac.horizon
        if model == "overlap":
            base = rng.standard_normal((n_paths, n + H - 1))
            g0 = float(H)
        else:
            base = sim_series(Autocorr("ar1", phi=ac.phi), n + H - 1, n_paths, rng)
            d = np.arange(-(H - 1), H)
            g0 = float(np.sum((H - np.abs(d)) * ac.phi ** np.abs(d)))
        cs = np.concatenate([np.zeros((n_paths, 1)), np.cumsum(base, axis=1)], axis=1)
        return (cs[:, H:] - cs[:, :-H]) / math.sqrt(g0)
    raise ValueError(f"MC supports ar1 / overlap / ar1_overlap / lrv, not {model}")


def sharpe_ann(x: np.ndarray, q: float) -> np.ndarray:
    sd = x.std(axis=1, ddof=1)
    return x.mean(axis=1) / np.where(sd > 0, sd, np.nan) * math.sqrt(q)


def nw_lrv(x: np.ndarray, lags: int) -> np.ndarray:
    """Newey-West long-run variance per path (Bartlett weights)."""
    xc = x - x.mean(axis=1, keepdims=True)
    n = x.shape[1]
    v = np.sum(xc * xc, axis=1) / n
    for k in range(1, lags + 1):
        g = np.sum(xc[:, k:] * xc[:, :-k], axis=1) / n
        v = v + 2 * (1 - k / (lags + 1)) * g
    return v


def cbb_pvalue(x: np.ndarray, block: int, B: int, rng: np.random.Generator, chunk: int = 128) -> np.ndarray:
    """One-sided p of the mean under a mean-centred circular block bootstrap: p = (1 + #{mean* >= mean}) / (B + 1).
    Vectorised with circular block sums (a resampled mean is the average of ceil(n/b) random block sums)."""
    P, n = x.shape
    b = int(block)
    nb = int(math.ceil(n / b))
    out = np.empty(P)
    for i0 in range(0, P, chunk):
        xs = x[i0:i0 + chunk]
        m = xs.mean(axis=1, keepdims=True)
        xc = xs - m
        ext = np.concatenate([xc, xc[:, :b]], axis=1)
        cs = np.concatenate([np.zeros((xs.shape[0], 1)), np.cumsum(ext, axis=1)], axis=1)
        bsum = cs[:, b:b + n] - cs[:, :n]                           # (p, n) block sums starting at each t
        starts = rng.integers(0, n, size=(xs.shape[0], B, nb))
        means = np.take_along_axis(bsum, starts.reshape(xs.shape[0], -1), axis=1).reshape(
            xs.shape[0], B, nb).sum(axis=2) / (nb * b)
        out[i0:i0 + chunk] = (1 + np.sum(means >= m, axis=1)) / (B + 1)
    return out


def apply_gate(x_noise: np.ndarray, S: float, q: float, gate: Gate, ser: SeriesModel, *, B: int = 499,
               rng: np.random.Generator | None = None, nw_lags: int | None = None,
               ideal_null: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Apply `gate` literally to unit-vol noise paths shifted to true annual Sharpe S. Returns (pass, S_hat).
    p-leg: literal CBB (if ser.null_block) else a threshold at the analytic ideal-null quantile (ideal_null) or a
    literal Newey-West t (default)."""
    n = x_noise.shape[1]
    Y = n / q
    r = x_noise + S / math.sqrt(q)
    Sh = sharpe_ann(r, q)
    ok = np.ones(r.shape[0], bool)
    if gate.sharpe_abs is not None:
        ok &= Sh >= gate.sharpe_abs
    if gate.sharpe_c is not None:
        ok &= Sh >= gate.sharpe_c / math.sqrt(Y)
    if gate.natural_to_sharpe is not None:
        ok &= Sh >= gate.natural_to_sharpe
    if gate.stress_drag_sr:
        ok &= r.mean(axis=1) * math.sqrt(q) - gate.stress_drag_sr > 0   # stress mean > 0, fixed cost drag
    if gate.alpha is not None:
        if ser.null_block:
            p = cbb_pvalue(r, ser.null_block, B, rng or rng_for("cbb"))
            if gate.null_center_sr:
                raise ValueError("literal CBB is mean-centred; null_center_sr must be 0")
            ok &= p < gate.alpha
        elif ideal_null:
            ok &= Sh >= gate.null_center_sr + z_upper(gate.alpha) * math.sqrt(ser.D_null / Y)
        else:
            L = nw_lags if nw_lags is not None else _auto_lags(ser.autocorr, n)
            t = (r.mean(axis=1) - gate.null_center_sr / math.sqrt(q)) / np.sqrt(nw_lrv(r, L) / n)
            ok &= t >= z_upper(gate.alpha)
    if gate.hac_t is not None:
        L = nw_lags if nw_lags is not None else _auto_lags(ser.autocorr, n)
        t = r.mean(axis=1) / np.sqrt(nw_lrv(r, L) / n)
        ok &= t >= gate.hac_t
    if gate.both_halves_positive:
        h = n // 2
        ok &= (r[:, :h].mean(axis=1) > 0) & (r[:, h:].mean(axis=1) > 0)
    return ok, Sh


def _auto_lags(ac: Autocorr, n: int) -> int:
    if ac.model == "overlap":
        return 2 * ac.horizon
    if ac.model in ("ar1", "ar1_overlap") and abs(ac.phi) > 0:
        return int(min(n // 4, max(4, math.ceil(5 / (1 - abs(ac.phi))) + (ac.horizon if ac.model == "ar1_overlap" else 0))))
    return max(1, int(math.floor(4 * (n / 100) ** (2 / 9))))


def mc_gate(ser: SeriesModel, S: float, years: float, gate: Gate, n_paths: int = 4000, seed_salt="gate",
            B: int = 499, ideal_null: bool = False) -> dict:
    rng = rng_for(seed_salt, S, years)
    n = int(round(ser.periods_per_year * years))
    x = sim_series(ser.autocorr, n, n_paths, rng)
    ok, Sh = apply_gate(x, S, ser.periods_per_year, gate, ser, B=B, rng=rng, ideal_null=ideal_null)
    p = float(ok.mean())
    return {"p_pass": p, "mc_se": math.sqrt(max(p * (1 - p), 1e-12) / n_paths), "kappa_mc": float(np.nanstd(Sh) * math.sqrt(years)),
            "mean_S_hat": float(np.nanmean(Sh))}


def mc_two_stage(ser: SeriesModel, S: float, dev_years: float, val_years: float, dev_gate: Gate,
                 val_gate: Gate | None, n_paths: int = 4000, seed_salt="two_stage", B: int = 499,
                 ideal_null: bool = False) -> dict:
    """One continuous path of dev + val length, split; both gates applied literally."""
    rng = rng_for(seed_salt, S, dev_years, val_years)
    q = ser.periods_per_year
    nd, nv = int(round(q * dev_years)), int(round(q * (val_years or 0)))
    x = sim_series(ser.autocorr, nd + nv, n_paths, rng)
    okd, Shd = apply_gate(x[:, :nd], S, q, dev_gate, ser, B=B, rng=rng, ideal_null=ideal_null)
    if val_gate is None or nv == 0:
        pj = float(okd.mean())
        return {"p_dev": pj, "p_val": None, "p_joint": pj, "mc_se_joint": math.sqrt(max(pj * (1 - pj), 1e-12) / n_paths)}
    okv, Shv = apply_gate(x[:, nd:], S, q, val_gate, ser, B=B, rng=rng, ideal_null=ideal_null)
    if val_gate.fraction_of_dev is not None:
        okv &= Shv >= val_gate.fraction_of_dev * Shd
    both = okd & okv
    pj = float(both.mean())
    return {"p_dev": float(okd.mean()), "p_val": float(okv.mean()), "p_joint": pj,
            "mc_se_joint": math.sqrt(max(pj * (1 - pj), 1e-12) / n_paths)}


# ============================================================================================ event study
def _season_indicator(days_per_year: int, years: float, spec: dict) -> np.ndarray:
    nd = int(round(days_per_year * years))
    model = spec["model"]
    f = 1.0 if model == "uniform_poisson" else float(spec["season_fraction"])
    ns = int(spec.get("n_seasons", 4))
    ind = np.zeros(days_per_year)
    L = max(1, int(round(f * days_per_year / ns)))
    for j in range(ns):
        s0 = int(round(j * days_per_year / ns))
        ind[(s0 + np.arange(L)) % days_per_year] = 1.0
    return np.tile(ind, int(math.ceil(years)) + 1)[:nd]


def mc_event_study(*, events_per_year: float, car_sd: float, hold_days: int, icc: float, concurrency: dict,
                   mean_car: float, years: float, alpha: float = 0.05, sharpe_threshold: float | None = None,
                   n_paths: int = 4000, days_per_year: int = 252, seed_salt="events") -> dict:
    """Calendar-time portfolio of fixed-$ event positions. Daily abnormal return of an event: mu_d + sigma_d *
    (sqrt(icc) F_t + sqrt(1 - icc) e_it); the sum over the A_t active events is simulated exactly as
    A_t mu_d + sigma_d (sqrt(icc) A_t F_t + sqrt((1 - icc) A_t) Z_t). Returns rejection rates of
      - the calendar-time test  (S_hat >= threshold; threshold defaults to z_alpha / sqrt(Y), iid days),
      - the naive event-level t (sum CAR / N) / (car_sd / sqrt(N)) >= z_alpha that ignores the clustering,
    and the sd of the mean-CAR estimate across paths."""
    rng = rng_for(seed_salt, events_per_year, icc, mean_car, years)
    h = int(hold_days)
    nd = int(round(days_per_year * years))
    mu_d, sd_d = mean_car / h, car_sd / math.sqrt(h)
    model = concurrency["model"]
    chunk = max(1, int(2e7 // (nd + h)))
    cal_ok, naive_ok, mean_cars = [], [], []
    for i0 in range(0, n_paths, chunk):
        P = min(chunk, n_paths - i0)
        if model in ("seasonal_poisson", "uniform_poisson"):
            ind = _season_indicator(days_per_year, years + h / days_per_year + 1, concurrency)[: nd + h - 1]
            lam = events_per_year / (ind[:days_per_year].sum() if len(ind) >= days_per_year else ind.sum())
            arr = rng.poisson(lam * ind[None, :], size=(P, nd + h - 1)).astype(float)
        elif model == "clusters":
            m = int(round(concurrency["mean_size"]))
            n_cl = int(round(events_per_year * years / m))
            arr = np.zeros((P, nd + h - 1))
            # clusters evenly spaced (e.g. month-ends); windows do not overlap across clusters
            days = np.linspace(h - 1, nd + h - 2, n_cl, endpoint=False).astype(int)
            arr[:, days] = m
        else:
            raise ValueError("MC supports seasonal_poisson / uniform_poisson / clusters")
        cs = np.concatenate([np.zeros((P, 1)), np.cumsum(arr, axis=1)], axis=1)
        A = cs[:, h:h + nd] - cs[:, :nd]                     # active events on each of the nd days
        F = rng.standard_normal((P, nd))
        Z = rng.standard_normal((P, nd))
        X = A * mu_d + sd_d * (math.sqrt(icc) * A * F + np.sqrt((1 - icc) * A) * Z)
        # calendar-time Sharpe test
        Sh = sharpe_ann(X, days_per_year)
        thr = sharpe_threshold if sharpe_threshold is not None else z_upper(alpha) / math.sqrt(years)
        cal_ok.append(Sh >= thr)
        # event-level mean CAR = total P&L / N (sum CAR = sum over days of X, up to edge effects)
        tot_events = A.sum(axis=1) / h
        mcar = X.sum(axis=1) / np.maximum(tot_events, 1)
        mean_cars.append(mcar)
        naive_t = mcar / (car_sd / np.sqrt(np.maximum(tot_events, 1)))
        naive_ok.append(naive_t >= z_upper(alpha))
    cal_ok = np.concatenate(cal_ok)
    naive_ok = np.concatenate(naive_ok)
    mean_cars = np.concatenate(mean_cars)
    p = float(cal_ok.mean())
    return {"p_calendar": p, "mc_se": math.sqrt(max(p * (1 - p), 1e-12) / n_paths),
            "p_naive_event_t": float(naive_ok.mean()), "sd_mean_car": float(mean_cars.std()),
            "mean_mean_car": float(mean_cars.mean())}


# ============================================================================================ cross-section
def _cs_corr(s: np.ndarray, r: np.ndarray) -> np.ndarray:
    sc = s - s.mean(axis=-1, keepdims=True)
    rc = r - r.mean(axis=-1, keepdims=True)
    return np.sum(sc * rc, axis=-1) / np.sqrt(np.sum(sc * sc, axis=-1) * np.sum(rc * rc, axis=-1))


def mc_cross_sectional_ic(*, n_assets: int, n_periods: int, ic: float, rho_resid: float, rho_signal: float,
                          horizon: int = 1, signal_autocorr: float = 0.0, n_paths: int = 2000, alpha: float = 0.05,
                          seed_salt="ic") -> dict:
    """One-factor residuals u = sqrt(rho_resid) b F + sqrt(1-rho_resid) e with Rademacher (style / sector-half)
    loadings b; a signal s = sqrt(rho_signal) b S + sqrt(1-rho_signal) xi tilted to the same factor, both signal
    components AR(1) over time with `signal_autocorr`; r = IC s + sqrt(1-IC^2) u (unit unconditional variances).

    Statistic: the covariance IC_t = mean_i (s_i - s_bar)(r_i - r_bar) -- the P&L of the fixed-scale linear
    (IC-weighted) book, which is what a Sharpe gate on that book tests. The self-normalised Pearson IC is also
    reported: it shrinks when factor shocks inflate the per-period dispersion, so its sd is SMALLER than the
    breadth formula (the formula is conservative for Pearson / Spearman ICs).
    With horizon H > 1 the IC is taken against H-period overlapping forward returns (null only, ic = 0), which
    gives rho_k = signal_autocorr^k (H - k)/H."""
    rng = rng_for(seed_salt, n_assets, n_periods, ic, rho_resid, rho_signal, horizon, signal_autocorr)
    a, c = math.sqrt(rho_signal), math.sqrt(1 - rho_signal)
    H = int(horizon)
    ph = float(signal_autocorr)
    rb = rho_resid * rho_signal
    sd_an = math.sqrt((1 + (n_assets - 1) * rb) / n_assets)
    D = Autocorr("overlap_persistent", phi=ph, horizon=H).D1() if H > 1 else 1.0
    chunk = max(1, int(4e6 // (n_assets * (n_periods + H))))
    sd_ic, mean_ic, rej, rej_prac, sd_pear = [], [], [], [], []
    for i0 in range(0, n_paths, chunk):
        P = min(chunk, n_paths - i0)
        b = rng.choice([-1.0, 1.0], size=(P, 1, n_assets))
        T = n_periods + H
        e1 = rng.standard_normal((P, T, 1)); e1[:, 1:] *= math.sqrt(1 - ph * ph)
        e2 = rng.standard_normal((P, T, n_assets)); e2[:, 1:] *= math.sqrt(1 - ph * ph)
        S = lfilter([1.0], [1.0, -ph], e1, axis=1) if ph else e1
        xi = lfilter([1.0], [1.0, -ph], e2, axis=1) if ph else e2
        s = a * b * S + c * xi
        F = rng.standard_normal((P, T, 1))
        u = math.sqrt(rho_resid) * b * F + math.sqrt(1 - rho_resid) * rng.standard_normal((P, T, n_assets))
        sig = s[:, :n_periods]
        if H == 1:
            r = ic * sig + math.sqrt(1 - ic * ic) * u[:, 1:n_periods + 1]
        else:
            cs = np.concatenate([np.zeros((P, 1, n_assets)), np.cumsum(u, axis=1)], axis=1)
            r = (cs[:, 1 + H:1 + H + n_periods] - cs[:, 1:1 + n_periods]) / math.sqrt(H)
        sc = sig - sig.mean(axis=2, keepdims=True)
        rc = r - r.mean(axis=2, keepdims=True)
        ics = np.mean(sc * rc, axis=2)
        pear = np.sum(sc * rc, axis=2) / np.sqrt(np.sum(sc * sc, axis=2) * np.sum(rc * rc, axis=2))
        m = ics.mean(axis=1)
        sd_ic.append(ics.std(axis=1, ddof=1))
        sd_pear.append(pear.std(axis=1, ddof=1))
        mean_ic.append(m)
        rej.append(m / (sd_an * math.sqrt(D / n_periods)) >= z_upper(alpha))
        L = max(1, 2 * H) if H > 1 else 0
        lrv = nw_lrv(ics, L) if L else ics.var(axis=1, ddof=1)
        rej_prac.append(m / np.sqrt(lrv / n_periods) >= z_upper(alpha))
    sd_ic, mean_ic, sd_pear = np.concatenate(sd_ic), np.concatenate(mean_ic), np.concatenate(sd_pear)
    rej, rej_prac = np.concatenate(rej), np.concatenate(rej_prac)
    p = float(rej.mean())
    return {"sd_ic_mc": float(sd_ic.mean()), "sd_ic_analytic": sd_an, "sd_pearson_ic_mc": float(sd_pear.mean()),
            "sd_mean_ic_mc": float(mean_ic.std()), "sd_mean_ic_analytic": sd_an * math.sqrt(D / n_periods),
            "D_analytic": D, "p_reject": p, "p_reject_practitioner_hac": float(rej_prac.mean()),
            "mc_se": math.sqrt(max(p * (1 - p), 1e-12) / n_paths)}


def mc_long_short(*, n_assets: int, n_periods: int, ic: float, cs_dispersion: float, quantile: float,
                  rho_resid: float, rho_signal: float, signal_autocorr: float, cost_bps_one_way: float,
                  periods_per_year: float, sharpe_threshold: float, S_shift: float = 0.0, n_paths: int = 1000,
                  seed_salt="ls") -> dict:
    """Literal decile (quantile) long-short with AR(1) signals, realised turnover and costs. Returns mean/sd of the
    gross spread, realised one-way turnover per leg, gross and net Sharpe, and P(net S_hat >= sharpe_threshold)."""
    rng = rng_for(seed_salt, n_assets, n_periods, ic, rho_resid, rho_signal, signal_autocorr)
    N, T = n_assets, n_periods
    k = int(round(quantile * N))
    a, c = math.sqrt(rho_signal), math.sqrt(1 - rho_signal)
    ph = signal_autocorr
    cost = cost_bps_one_way / 1e4
    chunk = max(1, int(3e6 // (N * (T + 1))))
    gm, gs, tv, shg, shn, ok = [], [], [], [], [], []
    for i0 in range(0, n_paths, chunk):
        P = min(chunk, n_paths - i0)
        b = rng.choice([-1.0, 1.0], size=(P, 1, N))
        e1 = rng.standard_normal((P, T + 1, 1)); e1[:, 1:] *= math.sqrt(1 - ph * ph)
        e2 = rng.standard_normal((P, T + 1, N)); e2[:, 1:] *= math.sqrt(1 - ph * ph)
        Sf = lfilter([1.0], [1.0, -ph], e1, axis=1)
        xi = lfilter([1.0], [1.0, -ph], e2, axis=1)
        s = a * b * Sf + c * xi                                          # signal at t = 0..T
        F = rng.standard_normal((P, T, 1))
        u = math.sqrt(rho_resid) * b * F + math.sqrt(1 - rho_resid) * rng.standard_normal((P, T, N))
        r = cs_dispersion * (ic * s[:, :T] + math.sqrt(1 - ic * ic) * u)  # return over (t, t+1] predicted by s_t
        order = np.argsort(s[:, :T], axis=2)
        w = np.zeros((P, T, N))
        np.put_along_axis(w, order[:, :, -k:], 1.0 / k, axis=2)
        np.put_along_axis(w, order[:, :, :k], -1.0 / k, axis=2)
        spread = np.sum(w * r, axis=2)
        dw = np.abs(np.diff(w, axis=1)).sum(axis=2)                     # traded notional per rebalance (t >= 1)
        tcost = np.concatenate([dw[:, :1], dw], axis=1) * cost           # first period: assume steady-state cost
        net = spread - tcost
        gm.append(spread.mean(axis=1)); gs.append(spread.std(axis=1, ddof=1))
        tv.append(dw.mean(axis=1) / 4)
        shg.append(sharpe_ann(spread, periods_per_year))
        netS = net + S_shift * spread.std(axis=1, ddof=1)[:, None] / math.sqrt(periods_per_year)
        sh = sharpe_ann(netS, periods_per_year)
        shn.append(sh)
        ok.append(sh >= sharpe_threshold)
    cat = lambda z: np.concatenate(z)
    ok = cat(ok)
    p = float(ok.mean())
    return {"spread_mean_gross": float(cat(gm).mean()), "spread_mean_se": float(cat(gm).std() / math.sqrt(n_paths)),
            "spread_sd": float(cat(gs).mean()),
            "turnover_one_way_per_leg": float(cat(tv).mean()), "sharpe_gross": float(np.nanmean(cat(shg))),
            "sharpe_net": float(np.nanmean(cat(shn))), "p_pass": p, "mc_se": math.sqrt(max(p * (1 - p), 1e-12) / n_paths)}


# ============================================================================================ carry
def mc_carry(*, n_assets: int, rho: float, p_crash: float, jump_mean: float, jump_sd: float, S: float,
             periods_per_year: float, years: float, gate: Gate, ser: SeriesModel, n_paths: int = 4000,
             seed_salt="carry") -> dict:
    """K assets x_i = sqrt(rho) F + sqrt(1-rho) e_i, F a standardised normal + Bernoulli-jump crash factor, e_i
    Gaussian. EW book standardised to unit vol and shifted to annual Sharpe S. Checks the one-factor cumulant
    formula for skew/kurtosis, the Opdyke Sharpe SE and gate power."""
    rng = rng_for(seed_salt, n_assets, rho, p_crash, jump_mean, S, years)
    q = periods_per_year
    n = int(round(q * years))
    cm = crash_moments(p_crash, jump_mean, jump_sd)
    mJ = p_crash * jump_mean
    v = rho + (1 - rho) / n_assets
    chunk = max(1, int(2e7 // (n * n_assets)))
    Shs, oks, sk, ku = [], [], [], []
    for i0 in range(0, n_paths, chunk):
        P = min(chunk, n_paths - i0)
        I = rng.random((P, n)) < p_crash
        J = jump_mean + jump_sd * rng.standard_normal((P, n))
        F = (rng.standard_normal((P, n)) + I * J - mJ) / math.sqrt(cm["var"])
        e = rng.standard_normal((P, n, n_assets))
        port = math.sqrt(rho) * F + math.sqrt(1 - rho) * e.mean(axis=2)
        x = port / math.sqrt(v)
        ok, Sh = apply_gate(x, S, q, gate, ser, rng=rng, ideal_null=True)
        Shs.append(Sh); oks.append(ok)
        sk.append(stats.skew(x, axis=1)); ku.append(stats.kurtosis(x, axis=1))
    Sh = np.concatenate(Shs); ok = np.concatenate(oks)
    p = float(ok.mean())
    return {"p_pass": p, "mc_se": math.sqrt(max(p * (1 - p), 1e-12) / n_paths),
            "kappa_mc": float(np.std(Sh) * math.sqrt(years)), "skew_mc": float(np.mean(np.concatenate(sk))),
            "exkurt_mc": float(np.mean(np.concatenate(ku)))}


# ============================================================================================ panel
def mc_panel(*, n_markets: int, rho: float | None, blocks: dict | None, phi: float, S: float,
             periods_per_year: float, years: float, alpha: float = 0.05, n_paths: int = 3000,
             seed_salt="panel") -> dict:
    """K markets with correlation matrix R (equicorrelated or block), AR(1) in time, equal per-market Sharpe
    s = S / sqrt(N_eff). Returns P(EW-book t >= z_alpha) (iid-in-time SE rescaled by the true D, i.e. the ideal
    null) and the false-positive rate of a naive pooled test treating K*T cells as independent (at S=0)."""
    rng = rng_for(seed_salt, n_markets, rho, str(blocks), phi, S, years)
    K = n_markets
    if blocks:
        sizes = blocks["sizes"]
        R = np.full((K, K), blocks["rho_between"])
        i = 0
        for sz in sizes:
            R[i:i + sz, i:i + sz] = blocks["rho_within"]
            i += sz
    else:
        R = np.full((K, K), rho)
    np.fill_diagonal(R, 1.0)
    L = np.linalg.cholesky(R)
    rbar = (R.sum() - K) / (K * (K - 1))
    n_eff = K / (1 + (K - 1) * rbar)
    s_m = S / math.sqrt(n_eff)
    q = periods_per_year
    n = int(round(q * years))
    D = (1 + phi) / (1 - phi)
    chunk = max(1, int(1.5e7 // (n * K)))
    ok, naive = [], []
    for i0 in range(0, n_paths, chunk):
        P = min(chunk, n_paths - i0)
        e = rng.standard_normal((P, n, K)) @ L.T
        e[:, 1:, :] *= math.sqrt(1 - phi * phi)
        x = lfilter([1.0], [1.0, -phi], e, axis=1) if phi else e
        x = x + s_m / math.sqrt(q)
        book = x.mean(axis=2)
        t = book.mean(axis=1) / (book.std(axis=1, ddof=1) * math.sqrt(D / n))
        ok.append(t >= z_upper(alpha))
        flat = x.reshape(P, -1)
        tn = flat.mean(axis=1) / (flat.std(axis=1, ddof=1) / math.sqrt(n * K))
        naive.append(tn >= z_upper(alpha))
    ok = np.concatenate(ok); naive = np.concatenate(naive)
    p = float(ok.mean())
    return {"p_reject": p, "mc_se": math.sqrt(max(p * (1 - p), 1e-12) / n_paths),
            "p_naive_pooled": float(naive.mean()), "rho_bar": float(rbar), "n_eff": float(n_eff)}


# ============================================================================================ sleeve screen
def mc_sleeve_screen(*, s_sleeve: float, k: int, m_real: int, rho: float, incl_sharpe: float, dev_years: float,
                     hold_years: float, phi: float, periods_per_year: float, hold_t: float = 2.0,
                     n_paths: int = 3000, seed_salt="sleeves") -> dict:
    rng = rng_for(seed_salt, s_sleeve, k, m_real, rho, dev_years, hold_years)
    q = periods_per_year
    nd, nh = int(round(q * dev_years)), int(round(q * hold_years))
    n = nd + nh
    D = (1 + phi) / (1 - phi)
    mu = np.zeros(k)
    mu[:m_real] = s_sleeve / math.sqrt(q)
    chunk = max(1, int(1.5e7 // (n * k)))
    passes = []
    for i0 in range(0, n_paths, chunk):
        P = min(chunk, n_paths - i0)
        e = math.sqrt(rho) * rng.standard_normal((P, n, 1)) + math.sqrt(1 - rho) * rng.standard_normal((P, n, k))
        e[:, 1:, :] *= math.sqrt(1 - phi * phi)
        x = (lfilter([1.0], [1.0, -phi], e, axis=1) if phi else e) + mu
        dev, hold = x[:, :nd], x[:, nd:]
        Sh = dev.mean(axis=1) / dev.std(axis=1, ddof=1) * math.sqrt(q)          # (P, k)
        inc = Sh >= incl_sharpe
        cnt = inc.sum(axis=1)
        book = np.einsum("pnk,pk->pn", hold, inc) / np.maximum(cnt, 1)[:, None]
        t = book.mean(axis=1) / (book.std(axis=1, ddof=1) * math.sqrt(D / nh))
        passes.append((cnt > 0) & (t >= hold_t))
    ok = np.concatenate(passes)
    p = float(ok.mean())
    return {"p_joint": p, "mc_se": math.sqrt(max(p * (1 - p), 1e-12) / n_paths)}
