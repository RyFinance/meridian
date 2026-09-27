"""Resampling engines. All are seeded, vectorised across paths, and draw whole rows of a joint
panel (same historical date for every series), which preserves the contemporaneous correlation
between strategy, control, market and T-bills.

- `politis_white`: data-driven expected block length (Politis & White 2004, with the Patton,
  Politis & White 2009 correction), for the stationary and the circular block bootstrap.
- `stationary_indices`: Politis-Romano (1994) stationary bootstrap, geometric block lengths.
- `circular_indices`: circular block bootstrap, fixed block length.
- `fit_markov` / `simulate_markov`: first-order Markov chain for a causal regime label.
- `regime_indices`: regime-conditioned block bootstrap. A regime path is simulated from the fitted
  chain (so regime durations are realistic); rows come from a stationary bootstrap run inside the
  current regime's own chronological subsample, restarted at every simulated regime switch.
- `fit_gjr_t` / `fhs_simulate`: filtered historical simulation. A GJR-GARCH(1,1) volatility with
  Student-t quasi-likelihood is fitted to each series' excess return (mean fixed at the sample mean
  so every method is centred on the same history); standardised residual VECTORS are then drawn
  jointly by date and pushed through each series' variance recursion. Variance targeting
  (omega = sample variance x (1 - persistence), persistence capped at 0.995) keeps the simulated
  unconditional volatility equal to the historical one.

No IID Gaussian draws are used anywhere.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numba import njit
from scipy.optimize import minimize
from scipy.special import gammaln

MAX_PERSISTENCE = 0.995
# FHS is flagged not credible for a series when its median simulated path volatility is below this
# fraction of the historical volatility (the fitted variance process does not reproduce the sample).
FHS_MIN_PATH_VOL_RATIO = 0.6


# ---------------------------------------------------------------- block length
def politis_white(x: np.ndarray) -> dict[str, float]:
    """Optimal expected block length for the stationary (SB) and circular (CB) bootstrap of the
    mean of one series (Politis & White 2004; Patton, Politis & White 2009)."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    e = x - x.mean()
    b_max = np.ceil(min(3 * np.sqrt(n), n / 3))
    kn = max(5, int(np.sqrt(np.log10(n))))
    m_max = int(np.ceil(np.sqrt(n))) + kn
    cv = 2 * np.sqrt(np.log10(n) / n)
    acv = np.zeros(m_max + 1)
    rho = np.zeros(m_max + 1)
    opt_m = None
    for i in range(m_max + 1):
        cp = e[i:] @ e[: n - i]
        acv[i] = cp / n
        if i > 0:
            rho[i] = abs(cp) / np.sqrt((e[i:] @ e[i:]) * (e[: n - i] @ e[: n - i]))
        if i >= kn and opt_m is None and np.all(rho[i - kn + 1: i + 1] < cv):
            opt_m = i - kn
    m = 2 * max(opt_m, 1) if opt_m is not None else m_max
    m = min(m, m_max)
    g = 0.0
    lr = acv[0]
    for k in range(1, m + 1):
        lam = 1.0 if k / m <= 0.5 else 2 * (1 - k / m)
        g += 2 * lam * k * acv[k]
        lr += 2 * lam * acv[k]
    if lr <= 0 or g == 0:
        return {"sb": 1.0, "cb": 1.0, "m": float(m)}
    b_sb = (2 * g ** 2 / (2 * lr ** 2)) ** (1 / 3) * n ** (1 / 3)
    b_cb = (2 * g ** 2 / (4 / 3 * lr ** 2)) ** (1 / 3) * n ** (1 / 3)
    return {"sb": float(min(max(b_sb, 1.0), b_max)), "cb": float(min(max(b_cb, 1.0), b_max)), "m": float(m)}


def panel_block_length(returns: np.ndarray) -> dict:
    """Block length for a joint panel: the maximum Politis-White length over every column's
    returns AND absolute returns. Path risk (drawdowns, ruin) depends on volatility clustering,
    which lives in |r|; the mean-based length on r alone is usually 1-3 days and would destroy it."""
    per = {}
    for j in range(returns.shape[1]):
        a = politis_white(returns[:, j])
        b = politis_white(np.abs(returns[:, j]))
        per[j] = {"r_sb": a["sb"], "abs_sb": b["sb"], "r_cb": a["cb"], "abs_cb": b["cb"]}
    sb = max(max(v["r_sb"], v["abs_sb"]) for v in per.values())
    cb = max(max(v["r_cb"], v["abs_cb"]) for v in per.values())
    return {"sb": sb, "cb": cb, "per_column": per}


# ---------------------------------------------------------------- index samplers
def stationary_indices(n: int, n_paths: int, horizon: int, mean_block: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    p = 1.0 / mean_block
    idx = np.empty((n_paths, horizon), dtype=np.int32)
    idx[:, 0] = rng.integers(0, n, n_paths)
    for t in range(1, horizon):
        new = rng.random(n_paths) < p
        cont = (idx[:, t - 1] + 1) % n
        idx[:, t] = np.where(new, rng.integers(0, n, n_paths), cont)
    return idx


def circular_indices(n: int, n_paths: int, horizon: int, block: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    block = max(1, int(round(block)))
    nb = int(np.ceil(horizon / block))
    starts = rng.integers(0, n, size=(n_paths, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_paths, -1)[:, :horizon] % n
    return idx.astype(np.int32)


def fit_markov(labels: np.ndarray, n_states: int | None = None) -> np.ndarray:
    """Maximum-likelihood transition matrix of a first-order chain from one observed label path."""
    labels = np.asarray(labels, dtype=int)
    k = int(labels.max()) + 1 if n_states is None else n_states
    counts = np.zeros((k, k))
    np.add.at(counts, (labels[:-1], labels[1:]), 1)
    rows = counts.sum(axis=1, keepdims=True)
    P = np.divide(counts, rows, out=np.zeros_like(counts), where=rows > 0)
    for i in range(k):  # a state never left in-sample (or never seen) is made absorbing-safe
        if rows[i, 0] == 0:
            P[i, i] = 1.0
    return P


def stationary_distribution(P: np.ndarray) -> np.ndarray:
    w, v = np.linalg.eig(P.T)
    pi = np.real(v[:, np.argmin(np.abs(w - 1))])
    pi = np.abs(pi) / np.abs(pi).sum()
    return pi


def simulate_markov(P: np.ndarray, init: np.ndarray, n_paths: int, horizon: int, rng) -> np.ndarray:
    cum = np.cumsum(P, axis=1)
    cum[:, -1] = 1.0
    s = np.empty((n_paths, horizon), dtype=np.int16)
    s[:, 0] = rng.choice(len(init), size=n_paths, p=init)
    for t in range(1, horizon):
        u = rng.random(n_paths)
        s[:, t] = (u[:, None] > cum[s[:, t - 1]]).sum(axis=1)
    return s


def mean_durations(P: np.ndarray) -> np.ndarray:
    d = 1 - np.diag(P)
    return np.divide(1.0, d, out=np.full(len(d), np.inf), where=d > 0)


def regime_indices(labels: np.ndarray, n_paths: int, horizon: int, mean_block: float, seed: int,
                   P: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Regime-conditioned block bootstrap. Returns (row indices, simulated regime path).

    Each regime's days form a chronological pool. While the simulated regime stays the same, a path
    continues to the next day of that pool (circularly) with probability 1 - 1/mean_block, i.e. a
    stationary bootstrap run inside the regime's own subsample; on a regime switch or a block end it
    starts afresh at a uniform position of the new regime's pool. Every day of a regime therefore has
    exactly one predecessor and is drawn with equal probability (continuing along raw history instead
    under-samples the first days of each regime run, e.g. the start of a drawdown, and biases the
    mean upward). Cost: blocks are spliced at regime switches and at pool run boundaries."""
    rng = np.random.default_rng(seed)
    labels = np.asarray(labels, dtype=int)
    n = len(labels)
    P = fit_markov(labels) if P is None else P
    k = P.shape[0]
    freq = np.bincount(labels, minlength=k) / n
    s = simulate_markov(P, freq, n_paths, horizon, rng)
    pools = [np.flatnonzero(labels == j) for j in range(k)]
    size = np.array([len(p) for p in pools])
    if np.any(size[np.unique(s)] == 0):
        raise ValueError("simulated a regime with no historical days")
    off = np.r_[0, np.cumsum(size)[:-1]]
    flat = np.concatenate(pools)
    p_new = 1.0 / mean_block
    pos = (rng.random(n_paths) * size[s[:, 0]]).astype(np.int64)
    idx = np.empty((n_paths, horizon), dtype=np.int32)
    idx[:, 0] = flat[off[s[:, 0]] + pos]
    for t in range(1, horizon):
        st = s[:, t]
        cont = (s[:, t - 1] == st) & (rng.random(n_paths) >= p_new)
        fresh = (rng.random(n_paths) * size[st]).astype(np.int64)
        pos = np.where(cont, (pos + 1) % size[st], fresh)
        idx[:, t] = flat[off[st] + pos]
    return idx, s


# ---------------------------------------------------------------- GJR-GARCH-t / FHS
@njit(cache=True)
def _gjr_var(e, omega, alpha, gamma, beta, h0):
    n = e.shape[0]
    h = np.empty(n)
    h[0] = h0
    for t in range(1, n):
        neg = 1.0 if e[t - 1] < 0 else 0.0
        h[t] = omega + (alpha + gamma * neg) * e[t - 1] ** 2 + beta * h[t - 1]
    return h


def _t_nll(params, e, var):
    """Variance-targeted GJR-t: omega = var * (1 - persistence), so the model's unconditional
    variance equals the sample variance (keeps every method centred on the same history)."""
    alpha, gamma, beta, nu = params
    pers = alpha + gamma / 2 + beta
    if alpha < 0 or beta < 0 or alpha + gamma < 0 or pers >= MAX_PERSISTENCE or nu <= 2.05 or nu > 200:
        return 1e10
    omega = var * (1 - pers)
    h = _gjr_var(e, omega, alpha, gamma, beta, var)
    if np.any(h <= 0):
        return 1e10
    z2 = e ** 2 / h
    ll = (gammaln((nu + 1) / 2) - gammaln(nu / 2) - 0.5 * np.log(np.pi * (nu - 2))
          - 0.5 * np.log(h) - (nu + 1) / 2 * np.log1p(z2 / (nu - 2)))
    return -float(ll.sum())


@dataclass
class GJRFit:
    mu: float
    omega: float
    alpha: float
    gamma: float
    beta: float
    nu: float
    scale: float
    h_last: float
    h_bar: float
    persistence: float
    converged: bool

    def as_dict(self) -> dict:
        return {k: float(v) if not isinstance(v, bool) else v for k, v in self.__dict__.items()}


def fit_gjr_t(x: np.ndarray) -> tuple[GJRFit, np.ndarray]:
    """Fit GJR-GARCH(1,1) with Student-t likelihood to x (mean fixed at the sample mean).
    Returns the fit and standardised residuals z_t = (x_t - mu) / sqrt(h_t) (in the original scale)."""
    x = np.asarray(x, dtype=float)
    scale = 100.0 / x.std()  # work in units where the std is 100 "bp"-ish for conditioning
    mu = x.mean()
    e = (x - mu) * scale
    var = e.var()
    best = None
    for a0, g0, b0 in [(0.05, 0.05, 0.88), (0.02, 0.10, 0.85), (0.10, 0.05, 0.80), (0.03, 0.02, 0.94), (0.20, 0.05, 0.60)]:
        res = minimize(_t_nll, np.array([a0, g0, b0, 8.0]), args=(e, var), method="Nelder-Mead",
                       options={"maxiter": 4000, "xatol": 1e-7, "fatol": 1e-7})
        if best is None or res.fun < best.fun:
            best = res
    alpha, gamma, beta, nu = best.x
    pers = alpha + gamma / 2 + beta
    omega = var * (1 - pers)
    h = _gjr_var(e, omega, alpha, gamma, beta, var)
    z = e / np.sqrt(h)
    fit = GJRFit(mu=mu, omega=omega, alpha=alpha, gamma=gamma, beta=beta, nu=nu, scale=scale,
                 h_last=float(h[-1]), h_bar=float(var), persistence=float(pers),
                 converged=bool(best.fun < 1e9))
    return fit, z


def fhs_simulate(fits: list[GJRFit], z: np.ndarray, n_paths: int, horizon: int, seed: int,
                 start: str = "unconditional") -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """Filtered historical simulation. z: (n_dates, n_series) standardised residuals; one date's
    residual vector is drawn for all series at once. Returns (simulated excess returns
    [n_series, n_paths, horizon], drawn date indices [n_paths, horizon], per-series diagnostics).

    The empirical residuals are skewed, so E[1(z<0) z^2] (kappa) is not the 1/2 that the Student-t
    fit assumes; plugging them into the fitted recursion unchanged makes SPY's variance process
    explosive (persistence > 1). The asymmetry coefficient is therefore rescaled, gamma_sim =
    gamma * 0.5 / kappa, which keeps the fitted persistence alpha + gamma/2 + beta and the fitted
    average news impact; omega = sample variance x (1 - persistence) keeps the unconditional variance
    equal to history. Diagnostics report how the simulated path volatility compares with history.
    """
    rng = np.random.default_rng(seed)
    n = z.shape[0]
    zc = (z - z.mean(axis=0)) / z.std(axis=0)  # re-standardise the empirical innovations
    d = rng.integers(0, n, size=(n_paths, horizon)).astype(np.int32)
    out = np.empty((len(fits), n_paths, horizon))
    diag = []
    for j, f in enumerate(fits):
        kappa = float(np.mean(np.where(zc[:, j] < 0, zc[:, j] ** 2, 0.0)))
        a, b = f.alpha, f.beta
        g = f.gamma * 0.5 / kappa if kappa > 0 else f.gamma
        pers = a + g * kappa + b
        omega = f.h_bar * (1 - pers)
        h = np.full(n_paths, f.h_bar if start == "unconditional" else f.h_last)
        for t in range(horizon):
            e = np.sqrt(h) * zc[d[:, t], j]
            out[j, :, t] = e
            h = omega + (a + g * (e < 0)) * e ** 2 + b * h
        vol_ratio = float(np.sqrt((out[j] ** 2).mean() / f.h_bar))
        path_vol = np.median(out[j].std(axis=1)) / np.sqrt(f.h_bar)
        out[j] = out[j] / f.scale + f.mu
        diag.append({"kappa": kappa, "gamma_sim": float(g), "persistence_sim": float(pers),
                     "sim_rms_vol_over_hist": vol_ratio, "sim_median_path_vol_over_hist": float(path_vol),
                     "residual_kurtosis": float(np.mean(zc[:, j] ** 4)),
                     "credible": bool(path_vol >= FHS_MIN_PATH_VOL_RATIO)})
    return out, d, diag


# ---------------------------------------------------------------- dispatcher
METHODS = ("stationary", "circular", "regime_vol", "regime_dd", "fhs_gjr_t")


def simulate_panel(method: str, returns: np.ndarray, rf: np.ndarray, turnover: np.ndarray,
                   labels: dict[str, np.ndarray], blocks: dict, n_paths: int, horizon: int, seed: int,
                   mean_shift: np.ndarray | None = None) -> dict:
    """Simulate a joint panel. returns: (n, J) total returns; rf: (n,); turnover: (n, K).
    mean_shift (J,) is added to every simulated daily return (used for no-edge centring and for
    operating-characteristic simulations). Returns dict with 'R' (J, N, H), 'RF' (N, H), 'TO' (K, N, H)."""
    n, J = returns.shape
    info = {}
    if method == "fhs_gjr_t":
        ex = returns - rf[:, None]
        fits, zs = zip(*(fit_gjr_t(ex[:, j]) for j in range(J)))
        z = np.column_stack(zs)
        sim, d, diag = fhs_simulate(list(fits), z, n_paths, horizon, seed)
        RF = rf[d]
        R = sim + RF[None]
        TO = np.stack([turnover[d, k] for k in range(turnover.shape[1])]) if turnover.size else np.empty((0,))
        info["fits"] = [f.as_dict() | dg for f, dg in zip(fits, diag)]
    else:
        if method == "stationary":
            idx = stationary_indices(n, n_paths, horizon, blocks["sb"], seed)
        elif method == "circular":
            idx = circular_indices(n, n_paths, horizon, int(round(blocks["cb"])), seed)
        elif method in ("regime_vol", "regime_dd"):
            lab = labels["vol_tercile" if method == "regime_vol" else "dd_state"]
            idx, _ = regime_indices(lab, n_paths, horizon, blocks["sb"], seed)
            P = fit_markov(lab)
            info["transition"] = P.tolist()
            info["mean_duration_days"] = mean_durations(P).tolist()
        else:
            raise ValueError(method)
        R = np.stack([returns[idx, j] for j in range(J)])
        RF = rf[idx]
        TO = np.stack([turnover[idx, k] for k in range(turnover.shape[1])]) if turnover.size else np.empty((0,))
    if mean_shift is not None:
        R = R + np.asarray(mean_shift)[:, None, None]
    return {"R": R, "RF": RF, "TO": TO, "info": info}
