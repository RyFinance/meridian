"""research.power.gates -- the project's development / validation gates as functions of S_hat, and two-stage power.

A gate is a set of one-sided legs on the annualised Sharpe estimate S_hat of the tested series:

  sharpe_c      S_hat >= c / sqrt(Y)                 (Amendment 2 N3: c = 1.8, or 2.4 for families of k >= 4)
  sharpe_abs    S_hat >= s0                          (old flat 0.5 dev gate; the 0.75 validation gate)
  alpha         p < alpha under a mean-centred null  ->  S_hat >= null_center + z_{1-alpha} * sqrt(D_null / Y)
  hac_t         HAC t >= t0                          ->  S_hat >= t0 * sqrt(D_null / Y)
  stress_drag   stress-cost mean > 0                 ->  S_hat >  (extra stress cost / vol)  [Sharpe units]
  both_halves   both halves' means > 0               (pead_2004_2014)
  fraction_of_dev (validation only) S_hat_val >= f * S_hat_dev  (an effect-size criterion)
  natural       (validation only) mean >= x in natural units (bp per event, IC, ...) via the design's linear map

To first order every leg is monotone in the same S_hat (the mean and the Sharpe move together given the vol),
so a gate reduces to S_hat >= h = max(legs). The Monte Carlo verifier (simulate.py) applies each leg literally,
including a literal mean-centred circular block bootstrap, and checks the reduction.

Dev and validation windows are disjoint, so their estimates are (to first order) independent:
    P(pass both | S) = P_dev(S) * P_val(S * val_multiplier)
except for a fraction-of-dev validation gate, where P(both) is integrated over the dev estimate.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np
from scipy import optimize, stats

from research.power.core import (DEFAULT_POWER, SeriesModel, p_exceed, solve_mde, solve_years, z_upper)

_N = stats.norm


@dataclass
class Gate:
    name: str = "gate"
    sharpe_abs: float | None = None
    sharpe_c: float | None = None
    alpha: float | None = None
    null_center_sr: float = 0.0
    hac_t: float | None = None
    stress_drag_sr: float | None = None
    both_halves_positive: bool = False
    fraction_of_dev: float | None = None
    natural_min: float | None = None          # validation criterion in natural units (needs a design map)
    natural_to_sharpe: float | None = None    # resolved Sharpe threshold for natural_min (set by report.py)
    description: str = ""

    def legs(self, series: SeriesModel, years: float) -> dict:
        L = {}
        if self.sharpe_abs is not None:
            L["sharpe_abs"] = float(self.sharpe_abs)
        if self.sharpe_c is not None:
            L["sharpe_c_over_sqrtT"] = float(self.sharpe_c / math.sqrt(years))
        if self.alpha is not None:
            L["p_lt_alpha"] = float(self.null_center_sr + z_upper(self.alpha) * float(series.se_null(years)))
        if self.hac_t is not None:
            L["hac_t"] = float(self.hac_t * float(series.se_null(years)))
        if self.stress_drag_sr is not None and self.stress_drag_sr > 0:
            L["stress_mean_gt_0"] = float(self.stress_drag_sr)
        if self.natural_to_sharpe is not None:
            L["natural_min"] = float(self.natural_to_sharpe)
        return L

    def threshold(self, series: SeriesModel, years: float) -> float:
        L = self.legs(series, years)
        return max(L.values()) if L else -math.inf

    def binding_leg(self, series: SeriesModel, years: float) -> str:
        L = self.legs(series, years)
        return max(L, key=L.get) if L else "none"

    def pass_prob(self, S, series: SeriesModel, years: float):
        """P(gate passes | true S). Vectorised over S (fraction_of_dev handled in joint_pass)."""
        S = np.asarray(S, float)
        h = self.threshold(series, years)
        se = series.se(S, years)
        if not self.both_halves_positive:
            return p_exceed(h, S, se)
        return np.vectorize(lambda s, e: _both_halves_prob(h, s, e))(S, se)

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v not in (None, False, "")}


def _both_halves_prob(h: float, S: float, se_full: float, n_grid: int = 4001) -> float:
    """P(S_hat >= h, S_hat1 > 0, S_hat2 > 0) with S_hat = (S1 + S2)/2, S_i iid N(S, 2 se^2) (equal halves)."""
    sh = se_full * math.sqrt(2.0)
    lo, hi = 0.0, max(S, 0.0) + 12 * sh
    x = np.linspace(lo, hi, n_grid)
    f = _N.pdf((x - S) / sh) / sh
    need = np.maximum(0.0, 2 * h - x)
    g = _N.sf((need - S) / sh)
    return float(np.trapezoid(f * g, x))


def amendment2_dev_gate(k: int, stress_drag_sr: float | None, null_center_sr: float = 0.0,
                        family_alpha: float = 0.05) -> Gate:
    """Protocol Amendment 2 development gate (N2 + N3): Sharpe >= 1.8/sqrt(T) (2.4 for k >= 4),
    stress mean > 0, and p < 0.05/k under a mean-zero null."""
    return Gate(name=f"A2_dev(k={k})", sharpe_c=2.4 if k >= 4 else 1.8, alpha=family_alpha / k,
                stress_drag_sr=stress_drag_sr, null_center_sr=null_center_sr,
                description="Sharpe >= c/sqrt(T), stress mean > 0, p < 0.05/k (mean-centred block bootstrap)")


def current_val_gate(k: int, stress_drag_sr: float | None, sharpe_abs: float = 0.75,
                     family_alpha: float = 0.05) -> Gate:
    """The registry's usual validation gate: Sharpe >= 0.75, stress mean > 0, p < 0.05/k."""
    return Gate(name=f"val_abs_{sharpe_abs}", sharpe_abs=sharpe_abs, alpha=family_alpha / k,
                stress_drag_sr=stress_drag_sr,
                description=f"Sharpe >= {sharpe_abs}, stress mean > 0, p < 0.05/k")


def power_aware_val_gate(k_val: int = 1, stress_drag_sr: float | None = None, floor: float | None = None,
                         alpha: float = 0.05) -> Gate:
    """PROPOSED (not registered) power-aware validation gate.

    Pass iff the validation-window HAC t (equivalently the mean-centred block-bootstrap p) clears the one-sided
    level alpha / k_val, the stress mean is > 0, and (optionally, if registered) S_hat_val >= floor.

    Size: P(pass | S = 0) <= alpha / k_val <= 5% (the stress and floor legs can only lower it).
    Power: for a Gaussian location family the one-sided threshold on the sufficient statistic is uniformly most
    powerful at its size (Karlin-Rubin), so no other gate on S_hat with the same size has more power at ANY S > 0,
    including the (winner's-curse-corrected) development estimate.
    """
    return Gate(name="PAV" + (f"+floor{floor}" if floor else ""), alpha=alpha / k_val, stress_drag_sr=stress_drag_sr,
                sharpe_abs=floor,
                description=f"validation HAC-t / bootstrap p < {alpha}/{k_val}, stress mean > 0"
                            + (f", S_hat >= {floor}" if floor else ""))


# --------------------------------------------------------------------------------------------- two-stage power
def joint_pass(S: float, dev_series: SeriesModel, dev_years: float, dev_gate: Gate,
               val_series: SeriesModel | None, val_years: float | None, val_gate: Gate | None,
               val_multiplier: float = 1.0) -> dict:
    """P(pass dev), P(pass val | reached), P(pass both) at true net Sharpe S (val Sharpe = S * val_multiplier)."""
    p_dev = float(dev_gate.pass_prob(S, dev_series, dev_years))
    if val_gate is None or val_series is None or not val_years:
        return {"p_dev": p_dev, "p_val": None, "p_joint": p_dev}
    Sv = S * val_multiplier
    if val_gate.fraction_of_dev is None:
        p_val = float(val_gate.pass_prob(Sv, val_series, val_years))
        return {"p_dev": p_dev, "p_val": p_val, "p_joint": p_dev * p_val}
    # effect-size validation: S_hat_val >= f * S_hat_dev (plus the gate's other legs)
    h_d = dev_gate.threshold(dev_series, dev_years)
    sd_d = float(dev_series.se(S, dev_years))
    sd_v = float(val_series.se(Sv, val_years))
    h_v0 = val_gate.threshold(val_series, val_years)
    x = np.linspace(h_d, max(h_d, S) + 12 * sd_d, 6001)
    f = _N.pdf((x - S) / sd_d) / sd_d
    hv = np.maximum(h_v0, val_gate.fraction_of_dev * x)
    g = _N.sf((hv - Sv) / sd_v)
    p_joint = float(np.trapezoid(f * g, x))
    return {"p_dev": p_dev, "p_val": (p_joint / p_dev) if p_dev > 0 else 0.0, "p_joint": p_joint}


def joint_curve(S_list, *args, **kw) -> list[dict]:
    return [dict(S=float(s), **joint_pass(float(s), *args, **kw)) for s in S_list]


def mde_joint(dev_series, dev_years, dev_gate, val_series, val_years, val_gate, power=DEFAULT_POWER,
              val_multiplier=1.0) -> float:
    return solve_mde(lambda S: joint_pass(S, dev_series, dev_years, dev_gate, val_series, val_years, val_gate,
                                          val_multiplier)["p_joint"], power)


def years_joint(S: float, dev_series, dev_gate, val_series, val_gate, dev_fraction: float = 0.5,
                power=DEFAULT_POWER, val_multiplier=1.0) -> float:
    """Total years (dev + val, split dev_fraction : 1 - dev_fraction) for joint power `power`.
    inf when unattainable (e.g. a fixed 0.75 Sharpe validation gate with S <= 0.75)."""
    if val_gate is None:
        return solve_years(lambda Y: dev_gate.pass_prob(S, dev_series, Y), power)
    return solve_years(lambda Y: joint_pass(S, dev_series, dev_fraction * Y, dev_gate, val_series,
                                            (1 - dev_fraction) * Y, val_gate, val_multiplier)["p_joint"], power)


def years_single_gate(S: float, series, gate: Gate, power=DEFAULT_POWER) -> float:
    return solve_years(lambda Y: gate.pass_prob(S, series, Y), power)


# --------------------------------------------------------------------------------------------- winner's curse
def truncation_corrected_estimate(S_hat_dev: float, dev_series: SeriesModel, dev_years: float,
                                  dev_gate: Gate) -> float | None:
    """Conditional median-unbiased estimate of S given that the dev gate was passed (the selection-adjusted
    estimator of Andrews, Kitagawa & McCloskey 2019 / Zoellner & Pfeiffer 2008 flavour): the S at which the
    observed S_hat_dev is the median of S_hat | S_hat >= h. None if S_hat_dev did not clear the gate."""
    h = dev_gate.threshold(dev_series, dev_years)
    if S_hat_dev <= h:
        return None

    def cond_sf(S):
        sd = float(dev_series.se(S, dev_years))
        return _N.sf((S_hat_dev - S) / sd) / max(_N.sf((h - S) / sd), 1e-300)

    f = lambda S: cond_sf(S) - 0.5
    lo, hi = -5.0, S_hat_dev + 5.0
    if f(lo) > 0:
        return lo
    return float(optimize.brentq(f, lo, hi, xtol=1e-6))


def normal_prior_posterior(S_hat_dev: float, dev_series: SeriesModel, dev_years: float,
                           prior_sd: float = 0.5, prior_mean: float = 0.0) -> float:
    """Posterior mean of S under a N(prior_mean, prior_sd^2) prior on true Sharpes (selection does not change a
    Bayesian posterior if the prior is right). prior_sd = 0.5 is an ASSUMPTION about this project's search space."""
    se2 = float(dev_series.se(S_hat_dev, dev_years)) ** 2
    w = prior_sd ** 2 / (prior_sd ** 2 + se2)
    return float(prior_mean + w * (S_hat_dev - prior_mean))


# --------------------------------------------------------------------------------------------- sleeve screen
def sleeve_screen_power(s_sleeve: float, *, k: int, m_real: int, rho: float, incl_sharpe: float,
                        dev_years: float, hold_years: float, sleeve_series: SeriesModel,
                        book_series: SeriesModel | None = None, hold_t: float = 2.0) -> dict:
    """multiasset-style screen: k candidate sleeves, m_real of them with true Sharpe s_sleeve, the rest null.
    Dev: include every sleeve with S_hat >= incl_sharpe (no null, no multiplicity correction).
    Hold-out: the equal-risk book of included sleeves must have HAC t >= hold_t over hold_years.
    Sleeves are unit-vol with pairwise correlation rho; a book of n sleeves, R of them real, has
    S_book = R s / sqrt(n (1 + (n-1) rho)). Exact sum over Binomial(R; m_real, p1) x Binomial(Z; k - m_real, p0)."""
    book_series = book_series or sleeve_series
    p1 = float(p_exceed(incl_sharpe, s_sleeve, sleeve_series.se(s_sleeve, dev_years)))
    p0 = float(p_exceed(incl_sharpe, 0.0, sleeve_series.se(0.0, dev_years)))
    h = hold_t * float(book_series.se_null(hold_years))
    R = np.arange(m_real + 1)
    Z = np.arange(k - m_real + 1)
    pr = stats.binom.pmf(R, m_real, p1)
    pz = stats.binom.pmf(Z, k - m_real, p0)
    total = 0.0
    exp_book_sr = 0.0
    p_any = 0.0
    for r, wr in zip(R, pr):
        for z, wz in zip(Z, pz):
            n = r + z
            if n == 0:
                continue
            Sb = r * s_sleeve / math.sqrt(n * (1 + (n - 1) * rho))
            ph = float(p_exceed(h, Sb, book_series.se(Sb, hold_years)))
            total += wr * wz * ph
            exp_book_sr += wr * wz * Sb
            p_any += wr * wz
    return {"p_include_real": p1, "p_include_null": p0, "expected_null_included": (k - m_real) * p0,
            "familywise_any_null_included": 1 - (1 - p0) ** (k - m_real),
            "p_any_included": p_any, "expected_book_sharpe_given_any": exp_book_sr / p_any if p_any else 0.0,
            "hold_threshold_sharpe": h, "p_joint": total}
