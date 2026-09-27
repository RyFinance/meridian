"""research.power.core -- statistics shared by every design.

Everything in this package is analytic or synthetic. No project price data is read here.

Notation
--------
q        periods per year of the tested calendar-time return series (252 daily, 52 weekly, 12 monthly)
Y        years of data in one window; n = q * Y periods
S        TRUE annualised Sharpe ratio of the tested series (S = s * sqrt(q), s = per-period Sharpe)
S_hat    its estimate, annualised the way this project does it (mean / sd * sqrt(q))
rho_k    autocorrelation of the tested series at lag k
D1       long-run variance ratio of the series (the time-series "design effect"):
             Var(mean_hat) = sigma^2 * D1 / n,
             D1 = 1 + 2 * sum_{k>=1} (1 - k/n) rho_k                    (Bartlett / Newey-West population form)
         AR(1): D1 -> (1 + phi) / (1 - phi);  H-period overlapping sums of iid returns: D1 -> H.
D2       the same ratio for the squared series; for a Gaussian process corr(x_t^2, x_{t+k}^2) = rho_k^2.
kappa^2  Y * Var(S_hat).  null_lab calls sd(S_hat) * sqrt(Y) "kappa" and measured 0.85-1.4 on this project's engines.

Sharpe-ratio standard error
---------------------------
Lo (2002, FAJ 58(4)) for serially correlated returns (delta method with a HAC long-run covariance),
Mertens (2002) and Opdyke (2007, J. Asset Management 8(5)) for skewness and kurtosis:

    Var(s_hat) ~= [ D1  -  g3 * s * D13  +  (g4 - 1)/4 * s^2 * D2 ] / n

g3 = skewness, g4 = raw kurtosis (3 for Gaussian), D13 ~= sqrt(D1 * D2) (documented approximation: the
cross term is exactly zero for symmetric returns and exact for iid returns). With D1 = D2 = D13 = 1 this is
Mertens/Opdyke's iid formula; with g3 = 0, g4 = 3 it is Lo's iid result (1 + s^2/2)/n. Annualised:

    Var(S_hat) = q * Var(s_hat) = kappa^2(S) / Y.

Tests and gates on S_hat
------------------------
Every gate in this project is a set of one-sided legs on the SAME estimate S_hat (Sharpe >= c/sqrt(T),
stress mean > 0, p < alpha under a mean-centred null, HAC t >= t0). To first order all legs are monotone in
S_hat, so a gate is "S_hat >= h" with h the maximum of the leg thresholds (see gates.py), and

    P(pass | S) = 1 - Phi( (h - S) / sqrt(kappa^2(S) / Y) ).

The null legs use the variance the null procedure itself sees: a mean-centred circular/moving block
bootstrap with block length b estimates the long-run variance like a Bartlett kernel of bandwidth b
(Kuensch 1989; Lahiri 2003, ch. 3), so its effective D is D_boot(b) = 1 + 2 sum_{k<b} (1 - k/b) rho_k.
A Newey-West HAC with L lags has D_NW(L) = 1 + 2 sum_{k<=L} (1 - k/(L+1)) rho_k.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np
from scipy import optimize, stats

SEED = 20260924
SHARPE_GRID = (0.3, 0.5, 0.7, 1.0)
NULL_WORLDS = {"cost_drag_null": -0.30, "zero_net_null": 0.0, "structural_leak": 0.05}
DEFAULT_POWER = 0.80
FAMILY_ALPHA = 0.05            # Protocol Amendment 2, N2: alpha = 0.05 / k within the workstream batch
MAX_LAG = 20000

_N = stats.norm


class CorrelationAssumptionError(ValueError):
    """Raised when a panel / event / cross-sectional design is asked to treat correlated units as independent."""


class IndependenceWarning(UserWarning):
    """Loud warning: the caller explicitly overrode the independence refusal."""


def batch_alpha(k: int, family_alpha: float = FAMILY_ALPHA) -> float:
    """Amendment 2 N2: the p threshold is 0.05/k, k = candidates registered in the same workstream batch."""
    if k < 1:
        raise ValueError("batch size k must be >= 1")
    return family_alpha / float(k)


def z_upper(alpha: float) -> float:
    """Upper-tail standard-normal quantile z_{1-alpha}."""
    return float(_N.isf(alpha))


def p_exceed(threshold, S, se):
    """P(S_hat >= threshold) for S_hat ~ N(S, se^2). Vectorised."""
    return _N.sf((np.asarray(threshold, float) - np.asarray(S, float)) / np.asarray(se, float))


# --------------------------------------------------------------------------------------------- autocorrelation
@dataclass(frozen=True)
class Autocorr:
    """Autocorrelation model of a tested (per-period) return series.

    model:
      'ar1'          rho_k = phi^k
      'overlap'      H-period overlapping sums of iid returns, rho_k = (H - k)/H for k < H (Hansen-Hodrick)
      'ar1_overlap'  H-period overlapping sums of an AR(1) series
      'overlap_persistent'  IC series of a signal with period-to-period autocorrelation phi measured against
                     H-period overlapping forward returns: rho_k = phi^k (H - k)/H (phi = 1: pure Hansen-Hodrick;
                     phi = 0: a signal refreshed every period gives NO overlap autocorrelation)
      'acf'          explicit rho_1, rho_2, ... (zero beyond the list)
      'lrv'          only the long-run variance ratio D is known (e.g. backed out of a family's own null sd:
                     D = (sd_null(S_hat) * sqrt(Y))^2). D2 is then taken as max(D, 1).
    """

    model: str
    phi: float = 0.0
    horizon: int = 1
    rho: tuple = ()
    D: float | None = None

    # -------------------------------------------------------------- construction
    @staticmethod
    def from_spec(spec: Any) -> "Autocorr":
        """Accepts a float (AR(1) phi), an Autocorr, or a dict {'model': ..., ...}. None is refused."""
        if spec is None:
            raise TypeError("autocorrelation must be given explicitly (e.g. 0.0, {'model': 'ar1', 'phi': 0.1}, "
                            "{'model': 'overlap', 'horizon': 5}, {'model': 'lrv', 'D': 1.3})")
        if isinstance(spec, Autocorr):
            return spec
        if isinstance(spec, (int, float)):
            return Autocorr("ar1", phi=float(spec))
        if isinstance(spec, dict):
            m = spec.get("model", "ar1")
            if m == "iid":
                return Autocorr("ar1", phi=0.0)
            if m == "ar1":
                return Autocorr("ar1", phi=float(spec["phi"]))
            if m == "overlap":
                return Autocorr("overlap", horizon=int(spec["horizon"]))
            if m == "ar1_overlap":
                return Autocorr("ar1_overlap", phi=float(spec["phi"]), horizon=int(spec["horizon"]))
            if m == "overlap_persistent":
                return Autocorr("overlap_persistent", phi=float(spec["phi"]), horizon=int(spec["horizon"]))
            if m == "acf":
                return Autocorr("acf", rho=tuple(float(x) for x in spec["rho"]))
            if m == "lrv":
                return Autocorr("lrv", D=float(spec["D"]))
            raise ValueError(f"unknown autocorrelation model {m!r}")
        raise TypeError(f"cannot interpret autocorrelation spec {spec!r}")

    def to_dict(self) -> dict:
        if self.model == "ar1":
            return {"model": "ar1", "phi": self.phi}
        if self.model == "overlap":
            return {"model": "overlap", "horizon": self.horizon}
        if self.model in ("ar1_overlap", "overlap_persistent"):
            return {"model": self.model, "phi": self.phi, "horizon": self.horizon}
        if self.model == "acf":
            return {"model": "acf", "rho": list(self.rho)}
        return {"model": "lrv", "D": self.D}

    @property
    def is_zero(self) -> bool:
        if self.model == "ar1":
            return self.phi == 0.0
        if self.model == "overlap":
            return self.horizon <= 1
        if self.model == "acf":
            return not any(self.rho)
        if self.model == "lrv":
            return self.D == 1.0
        return False

    # -------------------------------------------------------------- ACF
    def _natural_max_lag(self) -> int:
        if self.model == "ar1":
            if abs(self.phi) < 1e-15:
                return 1
            return int(min(MAX_LAG, max(1, math.ceil(math.log(1e-14) / math.log(abs(self.phi))))))
        if self.model in ("overlap", "overlap_persistent"):
            return max(1, self.horizon - 1)
        if self.model == "ar1_overlap":
            base = Autocorr("ar1", phi=self.phi)._natural_max_lag()
            return int(min(MAX_LAG, base + self.horizon))
        if self.model == "acf":
            return max(1, len(self.rho))
        return 1

    def rho_k(self, max_lag: int | None = None) -> np.ndarray:
        """rho_1 .. rho_max_lag (numpy array)."""
        L = self._natural_max_lag() if max_lag is None else int(max_lag)
        k = np.arange(1, L + 1, dtype=float)
        if self.model == "ar1":
            return self.phi ** k
        if self.model == "overlap":
            H = float(self.horizon)
            return np.clip((H - k) / H, 0.0, None)
        if self.model == "overlap_persistent":
            H = float(self.horizon)
            return self.phi ** k * np.clip((H - k) / H, 0.0, None)
        if self.model == "ar1_overlap":
            H = self.horizon
            d = np.arange(-(H - 1), H, dtype=float)
            w = H - np.abs(d)

            def gam(kk):
                return np.sum(w[None, :] * self.phi ** np.abs(kk[:, None] + d[None, :]), axis=1)

            g0 = gam(np.array([0.0]))[0]
            return gam(k) / g0
        if self.model == "acf":
            r = np.zeros(L)
            m = min(L, len(self.rho))
            r[:m] = np.asarray(self.rho[:m], float)
            return r
        raise ValueError("'lrv' model has no explicit autocorrelation function")

    # -------------------------------------------------------------- variance ratios
    def D1(self, n: int | None = None) -> float:
        """Long-run variance ratio of the mean. n=None -> asymptotic."""
        if self.model == "lrv":
            return float(self.D)
        if self.model == "ar1" and n is None:
            p = self.phi
            return (1 + p) / (1 - p)
        if self.model == "overlap" and n is None:
            return float(self.horizon)
        L = self._natural_max_lag() if n is None else min(n - 1, max(self._natural_max_lag(), 1))
        L = max(L, 1)
        r = self.rho_k(L)
        k = np.arange(1, L + 1, dtype=float)
        w = np.ones(L) if n is None else (1 - k / n)
        return float(1 + 2 * np.sum(w * r))

    def D2(self, n: int | None = None) -> float:
        """Variance ratio of the squared series (Gaussian: rho_k^2)."""
        if self.model == "lrv":
            return float(max(self.D, 1.0))
        L = self._natural_max_lag() if n is None else min(n - 1, max(self._natural_max_lag(), 1))
        L = max(L, 1)
        r = self.rho_k(L)
        k = np.arange(1, L + 1, dtype=float)
        w = np.ones(L) if n is None else (1 - k / n)
        return float(1 + 2 * np.sum(w * r ** 2))

    def bartlett(self, bandwidth: int) -> float:
        """Expected D seen by a block bootstrap with block length b (Bartlett window b, weights 1 - k/b)."""
        if self.model == "lrv":
            return float(self.D)
        b = int(bandwidth)
        if b <= 1:
            return 1.0
        k = np.arange(1, b, dtype=float)
        return float(1 + 2 * np.sum((1 - k / b) * self.rho_k(b - 1)))

    def newey_west(self, lags: int) -> float:
        """Expected (population) Newey-West D with L lags (Bartlett weights 1 - k/(L+1))."""
        if self.model == "lrv":
            return float(self.D)
        L = int(lags)
        if L <= 0:
            return 1.0
        k = np.arange(1, L + 1, dtype=float)
        return float(1 + 2 * np.sum((1 - k / (L + 1)) * self.rho_k(L)))


def nw_default_lags(n: int) -> int:
    """Newey-West (1994) plug-in rule floor(4 (n/100)^(2/9))."""
    return int(math.floor(4 * (max(n, 1) / 100.0) ** (2.0 / 9.0)))


def size_with_estimated_variance(alpha: float, D_true: float, D_est: float) -> float:
    """Actual one-sided size of a nominal-alpha test whose variance uses D_est while the truth is D_true."""
    return float(_N.sf(z_upper(alpha) * math.sqrt(D_est / D_true)))


# --------------------------------------------------------------------------------------------- design effects
def kish_deff(mean_cluster_size: float, icc: float, cluster_size_cv: float = 0.0) -> float:
    """Kish (1965) / Moulton (1986, 1990) design effect with unequal cluster sizes:
    deff = 1 + ((1 + cv^2) * m_bar - 1) * icc.  (1 + cv^2) m_bar is the size-weighted mean cluster size."""
    m_w = (1.0 + cluster_size_cv ** 2) * mean_cluster_size
    return 1.0 + (m_w - 1.0) * icc


def breadth_eff(n: float, rho_bar: float) -> float:
    """Effective number of independent bets among n equicorrelated bets (Grinold-Kahn breadth with correlation;
    also the variance of an equal-weight portfolio): N_eff = N / (1 + (N - 1) rho_bar)."""
    n = np.asarray(n, float)
    return n / (1.0 + (n - 1.0) * rho_bar)


def block_mean_corr(sizes: Iterable[int], rho_within: float, rho_between: float) -> float:
    """Average pairwise correlation of K units in blocks (regions/sectors)."""
    sizes = np.asarray(list(sizes), float)
    K = sizes.sum()
    within_pairs = np.sum(sizes * (sizes - 1))
    all_pairs = K * (K - 1)
    return float((within_pairs * rho_within + (all_pairs - within_pairs) * rho_between) / all_pairs)


# --------------------------------------------------------------------------------------------- series model
@dataclass(frozen=True)
class SeriesModel:
    """The tested calendar-time return series, reduced to what the Sharpe sampling distribution depends on."""

    periods_per_year: float
    autocorr: Autocorr
    skew: float = 0.0
    exkurt: float = 0.0
    null_block: int | None = None   # block length of the gating block bootstrap; None -> null variance = truth
    null_D: float | None = None     # explicit D the null procedure sees (overrides null_block)

    @property
    def D1(self) -> float:
        return self.autocorr.D1()

    @property
    def D2(self) -> float:
        return self.autocorr.D2()

    @property
    def D_null(self) -> float:
        if self.null_D is not None:
            return float(self.null_D)
        if self.null_block:
            return self.autocorr.bartlett(self.null_block)
        return self.D1

    def kappa2(self, S):
        """Y * Var(S_hat) at true annualised Sharpe S (Lo 2002 / Mertens 2002 / Opdyke 2007)."""
        S = np.asarray(S, float)
        s = S / math.sqrt(self.periods_per_year)
        D1, D2 = self.D1, self.D2
        D13 = math.sqrt(D1 * D2)
        k2 = D1 - self.skew * s * D13 + (self.exkurt + 2.0) / 4.0 * s ** 2 * D2
        return np.maximum(k2, 1e-9)

    def se(self, S, years):
        """sd of the annualised Sharpe estimate over `years`."""
        return np.sqrt(self.kappa2(S) / np.asarray(years, float))

    def se_null(self, years):
        """sd of S_hat as seen by the gating null (mean-centred => S = 0 in the resampled world)."""
        return np.sqrt(self.D_null / np.asarray(years, float))

    def to_dict(self) -> dict:
        return {"periods_per_year": self.periods_per_year, "autocorr": self.autocorr.to_dict(),
                "skew": self.skew, "exkurt": self.exkurt, "null_block": self.null_block,
                "null_D": self.null_D, "D1": self.D1, "D2": self.D2, "D_null": self.D_null,
                "kappa_at_0": float(math.sqrt(self.kappa2(0.0)))}


# --------------------------------------------------------------------------------------------- one-sided test helpers
def single_test_power(S, series: SeriesModel, years: float, alpha: float):
    """Power of the one-sided test 'S_hat / se_null >= z_{1-alpha}' (HAC-t / bootstrap-p test at level alpha)."""
    h = z_upper(alpha) * series.se_null(years)
    return p_exceed(h, S, series.se(S, years))


def solve_mde(prob_fn, target: float = DEFAULT_POWER, lo: float = 0.0, hi: float = 30.0) -> float:
    """Smallest S with prob_fn(S) >= target (prob_fn increasing in S). inf if unreachable."""
    f = lambda S: float(prob_fn(S)) - target
    if f(hi) < 0:
        return float("inf")
    if f(lo) >= 0:
        return lo
    return float(optimize.brentq(f, lo, hi, xtol=1e-6))


def solve_years(prob_of_years, target: float = DEFAULT_POWER, lo: float = 0.05, hi: float = 2000.0) -> float:
    """Smallest Y with prob_of_years(Y) >= target, assuming prob increases in Y over the searched range.
    Returns inf when the target is unreachable even at `hi` years (e.g. a fixed Sharpe gate above the true S)."""
    f = lambda logY: float(prob_of_years(math.exp(logY))) - target
    a, b = math.log(lo), math.log(hi)
    fb = f(b)
    if fb < 0:
        return float("inf")
    if f(a) >= 0:
        return lo
    return float(math.exp(optimize.brentq(f, a, b, xtol=1e-7)))


def mde_single_test(series: SeriesModel, years: float, alpha: float, power: float = DEFAULT_POWER) -> float:
    return solve_mde(lambda S: single_test_power(S, series, years, alpha), power)


def years_single_test(S: float, series: SeriesModel, alpha: float, power: float = DEFAULT_POWER) -> float:
    """Closed form: Y = ((z_alpha sqrt(D_null) + z_beta kappa(S)) / S)^2."""
    if S <= 0:
        return float("inf")
    za, zb = z_upper(alpha), z_upper(1 - power)
    return float(((za * math.sqrt(series.D_null) + zb * math.sqrt(float(series.kappa2(S)))) / S) ** 2)


def require_explicit_corr(value, name: str, *, units_share_shocks: bool, assume_independent: str | None,
                          context: str) -> float:
    """Refuse to treat correlated units as independent.

    - `value` None -> TypeError (the parameter has no default by design).
    - value == 0 where units share shocks (panels, event clusters, cross-sections) -> CorrelationAssumptionError,
      unless `assume_independent` is a non-empty written justification, in which case an IndependenceWarning is
      raised loudly and the justification is recorded in the report.
    """
    if value is None:
        raise TypeError(f"{context}: '{name}' must be given explicitly; there is no default by design")
    v = float(value)
    if units_share_shocks and v == 0.0:
        if not assume_independent or not str(assume_independent).strip():
            raise CorrelationAssumptionError(
                f"{context}: {name}=0 treats correlated units as independent. Real {context} units share "
                f"shocks (same dates, same factors). Pass a measured/assumed {name} > 0, or pass "
                f"assume_independent='<written justification>' to override (a loud warning is recorded).")
        warnings.warn(f"{context}: {name}=0 accepted ONLY because assume_independent={assume_independent!r}. "
                      f"Effective observations are probably overstated.", IndependenceWarning, stacklevel=3)
    return v
