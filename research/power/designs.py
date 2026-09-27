"""research.power.designs -- map each research design to (a) the calendar-time series whose Sharpe the project's
gates test and (b) its effective sample size, so power / MDE / years can be computed on a common footing.

Every function takes its correlation / autocorrelation parameters as REQUIRED keyword arguments. For designs whose
units share shocks (events on the same dates or overlapping windows, cross-sections, panels, multi-asset carry), a
zero correlation is refused with CorrelationAssumptionError unless `assume_independent` carries a written
justification, in which case a loud IndependenceWarning is emitted and the justification is recorded.

Key identity used throughout: breadth changes the Sharpe that a given per-bet edge buys; it does NOT change the
power at a given net Sharpe of the tested series. Power at a given Sharpe depends only on years, the
autocorrelation (kappa) and the gate. So each design reports both (i) power/MDE in Sharpe units and (ii) the
natural-unit edge (bp per event, IC, per-market Sharpe) that corresponds to a given Sharpe.

References: Grinold (1989) and Grinold & Kahn (2000) fundamental law; Buckle (2004), Clarke, de Silva & Thorley
(2002, 2006) and Qian, Hua & Sorensen (2007) for breadth with correlated bets; Kish (1965) and Moulton (1986, 1990)
for the cluster design effect; Fama (1998), Mitchell & Stafford (2000) and Jaffe (1974) / Mandelker (1974) for
calendar-time portfolios; Hansen & Hodrick (1980) for overlapping horizons; Lo (2002), Mertens (2002), Opdyke (2007)
for the Sharpe SE.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from numpy.polynomial.hermite_e import hermegauss
from scipy import optimize, stats

from research.power.core import (Autocorr, CorrelationAssumptionError, SeriesModel, block_mean_corr,
                                 breadth_eff, require_explicit_corr, z_upper)

_N = stats.norm
_GH_X, _GH_W = hermegauss(121)
_GH_W = _GH_W / _GH_W.sum()


@dataclass
class Design:
    kind: str
    name: str
    series: SeriesModel
    raw_per_year: float
    raw_unit: str
    deff_cross: float
    n_units: float
    n_eff_units: float | None
    natural_unit: str
    natural_slope: float              # natural-unit mean per +1.0 of annualised NET Sharpe
    natural_offset: float = 0.0       # natural-unit mean at net Sharpe 0 (e.g. costs to overcome)
    implied: dict = field(default_factory=dict)
    breadth_curve: list = field(default_factory=list)
    rho_sensitivity: list = field(default_factory=list)
    naive: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    inputs: dict = field(default_factory=dict)

    def n_raw(self, years: float) -> float:
        return self.raw_per_year * years

    def n_eff(self, years: float) -> float:
        return self.n_raw(years) / (self.deff_cross * self.series.D1)

    def natural_from_sharpe(self, S: float) -> float:
        return self.natural_slope * S + self.natural_offset

    def sharpe_from_natural(self, x: float) -> float:
        return (x - self.natural_offset) / self.natural_slope

    def se_natural(self, years: float) -> float:
        """SE of the natural-unit mean estimate over `years` (true effect zero)."""
        return float(self.natural_slope * self.series.se(0.0, years))


def _naive(deff_total: float, alpha: float = 0.05) -> dict:
    """What an analysis that assumes independence would report: its SE is too small by sqrt(deff) and its
    nominal-alpha one-sided test rejects a true null with probability sf(z_alpha / sqrt(deff))."""
    return {"deff_ignored": float(deff_total), "naive_se_ratio": float(1 / math.sqrt(deff_total)),
            "naive_false_positive_at_nominal_0.05": float(_N.sf(z_upper(alpha) / math.sqrt(deff_total)))}


# ============================================================================================== 1-2. time series
def timeseries(*, periods_per_year: float, autocorr, skew: float = 0.0, exkurt: float = 0.0,
               mean_ann: float | None = None, vol_ann: float | None = None, null_block: int | None = None,
               null_D: float | None = None, name: str = "timeseries") -> Design:
    """A single strategy return series (daily, weekly, monthly). `autocorr` is required (0.0 is allowed here, a
    single series is one unit; the report still shows the Newey-West check)."""
    ac = Autocorr.from_spec(autocorr)
    ser = SeriesModel(periods_per_year, ac, skew, exkurt, null_block, null_D)
    implied = {}
    if mean_ann is not None and vol_ann:
        implied["sharpe_net"] = mean_ann / vol_ann
    rows = []
    for phi in (0.0, 0.05, 0.1, 0.2, 0.3, 0.5):
        a2 = Autocorr("ar1", phi=phi)
        rows.append({"phi": phi, "D1": a2.D1(), "kappa0": math.sqrt(a2.D1()),
                     "n_eff_per_year": periods_per_year / a2.D1()})
    curve = [{"years": y, "n_raw": periods_per_year * y, "n_eff": periods_per_year * y / ser.D1}
             for y in (1, 2, 5, 10, 15, 20, 30)]
    notes = []
    if ac.is_zero:
        notes.append("autocorrelation set to 0 explicitly: OK for one series only if its residual ACF is flat; "
                     "check with the Newey-West ratio reported below.")
    return Design("timeseries", name, ser, periods_per_year, "periods", 1.0, 1.0, 1.0,
                  "annualised mean return" if vol_ann else "annualised Sharpe",
                  vol_ann if vol_ann else 1.0, 0.0, implied, curve, rows, _naive(ser.D1), notes,
                  dict(periods_per_year=periods_per_year, autocorr=ac.to_dict(), skew=skew, exkurt=exkurt,
                       mean_ann=mean_ann, vol_ann=vol_ann, null_block=null_block, null_D=null_D))


def daily_strategy(**kw) -> Design:
    return timeseries(periods_per_year=252.0, **kw)


def monthly_strategy(**kw) -> Design:
    return timeseries(periods_per_year=12.0, **kw)


# ============================================================================================== 3. event studies
def concurrency_profile(events_per_year: float, hold_days: int, spec: dict, days_per_year: int = 252) -> dict:
    """Size-weighted mean number of concurrently held events, m_w = E[A^2]/E[A] over position-days.

    Models:
      seasonal_poisson {season_fraction f, n_seasons}: arrivals Poisson on in-season days (f of the year in
          n_seasons equal contiguous blocks), each event held hold_days. m_t = lambda * #in-season days in the
          window ending t; Poisson => E[A_t^2] = m_t + m_t^2, so m_w = 1 + sum m_t^2 / sum m_t (exact).
      uniform_poisson: seasonal_poisson with f = 1.
      clusters {mean_size m, cv}: events arrive in same-date clusters whose windows do not overlap other clusters;
          m_w = (1 + cv^2) m (Kish).
      cluster_sizes {sizes: [...]}: explicit sizes; m_w = sum m^2 / sum m.
    """
    model = spec.get("model")
    if model in ("seasonal_poisson", "uniform_poisson"):
        f = 1.0 if model == "uniform_poisson" else float(spec["season_fraction"])
        ns = int(spec.get("n_seasons", 4))
        ind = np.zeros(days_per_year)
        L = max(1, int(round(f * days_per_year / ns)))
        for j in range(ns):
            s0 = int(round(j * days_per_year / ns))
            ind[(s0 + np.arange(L)) % days_per_year] = 1.0
        lam = events_per_year / ind.sum()
        h = int(hold_days)
        # m_t = lam * sum_{u=t-h+1..t} ind[u], circular
        c = np.concatenate([ind[-(h - 1):], ind]) if h > 1 else ind
        cs = np.concatenate([[0.0], np.cumsum(c)])
        win = cs[h:] - cs[:-h] if h > 1 else ind
        m = lam * win
        m_w = 1.0 + float(np.sum(m ** 2) / np.sum(m))
        return {"model": model, "m_w": m_w, "mean_active_when_active": float(m[m > 0].mean()),
                "lambda_per_season_day": float(lam), "season_days": float(ind.sum()),
                "active_day_fraction": float((m > 0).mean())}
    if model == "clusters":
        m = float(spec["mean_size"])
        cv = float(spec.get("cv", 0.0))
        return {"model": model, "m_w": (1 + cv ** 2) * m, "mean_size": m, "cv": cv}
    if model == "cluster_sizes":
        s = np.asarray(spec["sizes"], float)
        return {"model": model, "m_w": float(np.sum(s ** 2) / np.sum(s)), "mean_size": float(s.mean())}
    raise ValueError(f"unknown concurrency model {model!r}")


def event_study(*, events_per_year: float, car_sd: float, hold_days: int, icc: float, concurrency: dict,
                portfolio_autocorr, mean_car: float | None = None, cost_per_event: float = 0.0,
                days_per_year: int = 252, skew: float = 0.0, exkurt: float = 0.0, null_block: int | None = None,
                null_D: float | None = None, assume_independent: str | None = None,
                name: str = "event_study") -> Design:
    """N events per year, per-event abnormal return (CAR over hold_days) sd `car_sd`, correlated through shared
    dates: `icc` is the correlation of two events' daily abnormal returns on the same day (= the CAR correlation
    of two same-date events; events whose windows overlap by d of h days have CAR correlation icc * d / h).

    Design effect (Kish/Moulton with concurrency): deff = 1 + icc * (m_w - 1), m_w the size-weighted mean number of
    concurrently held events.  N_eff = N / deff.

    Calendar-time portfolio equivalence (fixed dollar per event, Fama 1998 / Mitchell-Stafford 2000): the sum of
    all CARs equals the sum over days of the calendar-time portfolio P&L, so the pooled event-level t with
    cluster-robust SE and the calendar-time portfolio t coincide:
        S_calendar = (mean_car - cost) / car_sd * sqrt(events_per_year / deff).
    """
    cp = concurrency_profile(events_per_year, hold_days, concurrency, days_per_year)
    m_w = cp["m_w"]
    rho = require_explicit_corr(icc, "icc", units_share_shocks=m_w > 1.0 + 1e-9,
                                assume_independent=assume_independent, context="event study")
    deff = 1.0 + rho * (m_w - 1.0)
    ac = Autocorr.from_spec(portfolio_autocorr)
    ser = SeriesModel(float(days_per_year), ac, skew, exkurt, null_block, null_D)
    slope = car_sd * math.sqrt(deff / events_per_year)
    implied = {"events_per_year": events_per_year, "deff": deff, "m_w": m_w,
               "n_eff_per_year": events_per_year / deff, "per_event_ir_per_unit_sharpe": slope / car_sd}
    if mean_car is not None:
        implied["sharpe_gross"] = mean_car / car_sd * math.sqrt(events_per_year / deff)
        implied["sharpe_net"] = (mean_car - cost_per_event) / car_sd * math.sqrt(events_per_year / deff)
    curve = []
    for mult in (0.125, 0.25, 0.5, 1, 2, 4, 8):
        n = events_per_year * mult
        c2 = concurrency_profile(n, hold_days, concurrency, days_per_year) if concurrency.get("model") in (
            "seasonal_poisson", "uniform_poisson") else cp
        d2 = 1 + rho * (c2["m_w"] - 1)
        curve.append({"events_per_year": n, "m_w": c2["m_w"], "deff": d2, "n_eff_per_year": n / d2})
    rows = []
    for r in (0.0, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.4):
        d2 = 1 + r * (m_w - 1)
        row = {"icc": r, "deff": d2, "n_eff_per_year": events_per_year / d2,
               "natural_slope": car_sd * math.sqrt(d2 / events_per_year)}
        if mean_car is not None:
            row["sharpe_net"] = (mean_car - cost_per_event) / car_sd * math.sqrt(events_per_year / d2)
        rows.append(row)
    notes = [f"calendar-time equivalence: per-event IR x sqrt(N_eff/yr); m_w={m_w:.2f}, deff={deff:.2f}"]
    if m_w <= 1.0 + 1e-9:
        notes.append("m_w = 1 (no concurrent events): icc cannot matter; deff = 1.")
    return Design("event_study", name, ser, events_per_year, "events", deff, m_w, events_per_year / deff,
                  "mean net CAR per event (return units)", slope, cost_per_event, implied, curve, rows,
                  _naive(deff * ser.D1), notes,
                  dict(events_per_year=events_per_year, car_sd=car_sd, hold_days=hold_days, icc=icc,
                       concurrency=concurrency, concurrency_profile=cp, portfolio_autocorr=ac.to_dict(),
                       mean_car=mean_car, cost_per_event=cost_per_event, days_per_year=days_per_year,
                       skew=skew, exkurt=exkurt, assume_independent=assume_independent))


# ============================================================================================== 4. cross-sectional IC
def cross_sectional_ic(*, n_assets: int, periods_per_year: float, ic: float, ic_autocorr, rho_resid: float,
                       rho_signal: float = 1.0, ic_sd_true: float = 0.0, assume_independent: str | None = None,
                       name: str = "cross_sectional_ic") -> Design:
    """Per-period cross-sectional IC with N assets.

    Correlation that matters for breadth is between the BETS (signal x residual return), not between raw assets:
    a common mode that the signal does not load on cancels in a cross-sectionally demeaned IC. In a one-factor
    model with heterogeneous (e.g. sector/style) loadings, where the residual returns load on the factor with
    R^2 = rho_resid and the signal with R^2 = rho_signal, the bet correlation is rho_bet = rho_resid * rho_signal
    and (Grinold-Kahn breadth with correlated bets)
        Var(IC_hat_t) = (1 + (N - 1) rho_bet) / N  (+ ic_sd_true^2),  N_eff = N / (1 + (N - 1) rho_bet).
    rho_signal = 1 is the brief's literal N/(1+(N-1) rho_bar) with rho_bar = rho_resid (a pure factor bet).
    IC autocorrelation from overlapping forecast horizons enters through `ic_autocorr` (e.g. overlap H).
    The IC-weighted (linear, transfer coefficient 1) book has per-period IR = IC / sd(IC_hat).
    """
    rr = require_explicit_corr(rho_resid, "rho_resid", units_share_shocks=n_assets > 1,
                               assume_independent=assume_independent, context="cross-sectional ranking")
    if rho_signal is None:
        raise TypeError("rho_signal must be given explicitly")
    rb = rr * float(rho_signal)
    var_ic = (1 + (n_assets - 1) * rb) / n_assets + ic_sd_true ** 2
    sd_ic = math.sqrt(var_ic)
    ac = Autocorr.from_spec(ic_autocorr)
    ser = SeriesModel(periods_per_year, ac)
    n_eff = float(breadth_eff(n_assets, rb))
    slope = sd_ic / math.sqrt(periods_per_year)
    implied = {"rho_bet": rb, "sd_ic_per_period": sd_ic, "ir_per_period": ic / sd_ic,
               "sharpe_gross_linear_book": ic / sd_ic * math.sqrt(periods_per_year), "n_eff": n_eff,
               "n_eff_ceiling_1_over_rho": (1 / rb) if rb > 0 else float("inf"),
               "fundamental_law_uncorrelated_sharpe": ic * math.sqrt(n_assets * periods_per_year)}
    curve = [{"n_assets": n, "n_eff": float(breadth_eff(n, rb)),
              "sharpe_gross_linear_book": ic / math.sqrt((1 + (n - 1) * rb) / n + ic_sd_true ** 2)
              * math.sqrt(periods_per_year)}
             for n in (10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 8000)]
    rows = []
    for r in (0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5):
        b = r * rho_signal
        v = (1 + (n_assets - 1) * b) / n_assets + ic_sd_true ** 2
        rows.append({"rho_resid": r, "rho_bet": b, "n_eff": float(breadth_eff(n_assets, b)),
                     "sharpe_gross_linear_book": ic / math.sqrt(v) * math.sqrt(periods_per_year),
                     "natural_slope": math.sqrt(v / periods_per_year)})
    deff = n_assets / n_eff
    return Design("cross_sectional_ic", name, ser, n_assets * periods_per_year, "asset-periods", deff, n_assets,
                  n_eff, "mean IC per period", slope, 0.0, implied, curve, rows, _naive(deff * ser.D1),
                  [f"rho_bet = rho_resid x rho_signal = {rb:.4f}"],
                  dict(n_assets=n_assets, periods_per_year=periods_per_year, ic=ic, ic_autocorr=ac.to_dict(),
                       rho_resid=rho_resid, rho_signal=rho_signal, ic_sd_true=ic_sd_true,
                       assume_independent=assume_independent))


# ============================================================================================== 5. long-short
def _quantile_tilt_moments(q: float, rho_signal: float) -> dict:
    """Large-N quantile-book moments in the one-factor tilt model with Rademacher loadings b_i = +/-1:
    s_i = a b_i S + c xi_i (a = sqrt(rho_signal), c = sqrt(1 - rho_signal)), S ~ N(0,1) per period.
    Returns E[ds] (mean top-minus-bottom signal), Var(ds_inf(S)), E[B_inf^2], E[B_top^2] where
    B = (1/Nq)(sum_top b - sum_bottom b) is the book's loading on the factor. Gauss-Hermite over S."""
    a = math.sqrt(min(max(rho_signal, 0.0), 0.995))
    c = math.sqrt(1 - a * a)
    ds, B, Bt = [], [], []
    for S in _GH_X:
        m = a * S
        g = lambda z: 0.5 * (_N.sf((z - m) / c) + _N.sf((z + m) / c)) - q
        z = optimize.brentq(g, -12 - abs(m), 12 + abs(m), xtol=1e-10)
        pp = 0.5 * _N.sf((z - m) / c)
        pm = 0.5 * _N.sf((z + m) / c)
        bt = (pp - pm) / q
        top_mean = 0.5 * (m * _N.sf((z - m) / c) + c * _N.pdf((z - m) / c)
                          - m * _N.sf((z + m) / c) + c * _N.pdf((z + m) / c)) / q
        ds.append(2 * top_mean)
        B.append(2 * bt)
        Bt.append(bt)
    ds, B, Bt = map(np.asarray, (ds, B, Bt))
    E_ds = float(np.sum(_GH_W * ds))
    return {"E_ds": E_ds, "Var_ds": float(np.sum(_GH_W * (ds - E_ds) ** 2)),
            "E_B2": float(np.sum(_GH_W * B ** 2)), "E_Bt2": float(np.sum(_GH_W * Bt ** 2))}


def quantile_turnover(q: float, signal_autocorr: float) -> float:
    """One-way fraction of each quantile leg replaced per rebalance for a Gaussian signal with period-to-period
    correlation rho: tau = 1 - P(s_t > z, s_{t-1} > z) / q (bivariate-normal orthant)."""
    z = _N.isf(q)
    if signal_autocorr >= 0.999999:
        return 0.0
    both = stats.multivariate_normal(mean=[0, 0], cov=[[1, signal_autocorr], [signal_autocorr, 1]]).cdf([-z, -z])
    return float(max(0.0, 1 - both / q))


def long_short_core(n_assets, ic, cs_dispersion, quantile, rho_resid, rho_signal, signal_autocorr,
                    cost_bps_one_way, periods_per_year, borrow_bps_annual=0.0, correlation_mode="factor_tilt",
                    turnover_override=None) -> dict:
    N, q, sig = float(n_assets), float(quantile), float(cs_dispersion)
    nq = N * q
    if correlation_mode == "factor_tilt":
        mom = _quantile_tilt_moments(q, rho_signal)
        E_B2 = mom["E_B2"] + 2 * (1 - mom["E_Bt2"]) / nq
        V = (1 - ic ** 2) * (rho_resid * E_B2 + (1 - rho_resid) * 2 / nq) + ic ** 2 * mom["Var_ds"]
        E_ds = mom["E_ds"]
    elif correlation_mode == "equicorrelated_bets":
        rb = rho_resid * rho_signal
        V = (1 - ic ** 2) * (2 / nq) * (1 + (2 * nq - 1) * rb)
        E_ds = 2 * _N.pdf(_N.isf(q)) / q
        mom = {"E_ds": E_ds}
    else:
        raise ValueError("correlation_mode must be 'factor_tilt' or 'equicorrelated_bets'")
    tau = quantile_turnover(q, signal_autocorr) if turnover_override is None else float(turnover_override)
    cost = 4 * tau * cost_bps_one_way / 1e4 + borrow_bps_annual / 1e4 / periods_per_year
    mu = sig * ic * E_ds
    sd = sig * math.sqrt(V)
    sr_g = mu / sd * math.sqrt(periods_per_year)
    sr_n = (mu - cost) / sd * math.sqrt(periods_per_year)
    return {"spread_mean_gross": mu, "spread_sd": sd, "cost_per_period": cost, "turnover_one_way_per_leg": tau,
            "spread_mean_net": mu - cost, "sharpe_gross": sr_g, "sharpe_net": sr_n, "V_over_sigma2": V,
            "E_signal_spread": E_ds, "position_efficiency": (2 / nq) * (1 - ic ** 2) / V,
            "n_eff_positions": 2 * nq * (2 / nq) * (1 - ic ** 2) / V,
            "cost_drag_sharpe": cost / sd * math.sqrt(periods_per_year)}


def long_short(*, n_assets: int, periods_per_year: float, ic: float, cs_dispersion: float, quantile: float,
               rho_resid: float, rho_signal: float, signal_autocorr: float, cost_bps_one_way: float,
               spread_autocorr, borrow_bps_annual: float = 0.0, skew: float = 0.0, exkurt: float = 0.0,
               correlation_mode: str = "factor_tilt", turnover_override: float | None = None,
               null_block: int | None = None, assume_independent: str | None = None,
               name: str = "long_short") -> Design:
    """Quantile long-short book (top q long, bottom q short, equal weight, $1 per leg) from IC, cross-sectional
    residual dispersion sigma_cs (per period) and quantile q.

    Mean spread per period  = sigma_cs * IC * E[s_top - s_bottom]  (= sigma_cs IC 2 phi(z_q)/q without tilt)
    Var(spread)/sigma_cs^2  = (1 - IC^2) [rho_resid E[B^2] + (1 - rho_resid) 2/(Nq)] + IC^2 Var(ds)
      with B the book's loading on the heterogeneous factor the signal is tilted towards (factor_tilt mode,
      exact large-N quadrature + finite-N sampling term), or, in 'equicorrelated_bets' mode, the brief's
      literal (2/(Nq)) (1 + (2Nq - 1) rho_bar) with rho_bar = rho_resid x rho_signal.
    Turnover: tau = 1 - P(stay in quantile) from the bivariate-normal orthant at signal autocorrelation rho_s;
      traded notional per rebalance = 4 tau (two legs, sell + buy); cost = 4 tau c + borrow / q.
    NET Sharpe = (mean - cost)/sd * sqrt(q) is what gets powered.
    """
    rr = require_explicit_corr(rho_resid, "rho_resid", units_share_shocks=n_assets > 1,
                               assume_independent=assume_independent, context="long-short cross-section")
    if rho_signal is None or signal_autocorr is None:
        raise TypeError("rho_signal and signal_autocorr must be given explicitly")
    core = long_short_core(n_assets, ic, cs_dispersion, quantile, rr, rho_signal, signal_autocorr,
                           cost_bps_one_way, periods_per_year, borrow_bps_annual, correlation_mode,
                           turnover_override)
    ac = Autocorr.from_spec(spread_autocorr)
    ser = SeriesModel(periods_per_year, ac, skew, exkurt, null_block)
    k_ds = core["E_signal_spread"]
    slope = core["spread_sd"] / math.sqrt(periods_per_year) / (cs_dispersion * k_ds)
    offset = core["cost_per_period"] / (cs_dispersion * k_ds)
    rb = rr * rho_signal
    n_eff_lin = float(breadth_eff(n_assets, rb))
    implied = dict(core)
    implied.update({"rho_bet_linear": rb, "n_eff_linear": n_eff_lin,
                    "sharpe_gross_linear_book_TC1": ic * math.sqrt(n_eff_lin * periods_per_year),
                    "ic_breakeven_costs": offset})
    curve = []
    for n in (50, 100, 200, 500, 1000, 2000, 5000):
        c2 = long_short_core(n, ic, cs_dispersion, quantile, rr, rho_signal, signal_autocorr, cost_bps_one_way,
                             periods_per_year, borrow_bps_annual, correlation_mode, turnover_override)
        curve.append({"n_assets": n, "n_eff_linear": float(breadth_eff(n, rb)),
                      "n_eff_positions": c2["n_eff_positions"], "sharpe_gross": c2["sharpe_gross"],
                      "sharpe_net": c2["sharpe_net"]})
    rows = []
    for r in (0.0, 0.05, 0.1, 0.2, 0.3, 0.5):
        c2 = long_short_core(n_assets, ic, cs_dispersion, quantile, r, rho_signal, signal_autocorr,
                             cost_bps_one_way, periods_per_year, borrow_bps_annual, correlation_mode,
                             turnover_override)
        rows.append({"rho_resid": r, "rho_bet_linear": r * rho_signal, "spread_sd": c2["spread_sd"],
                     "sharpe_gross": c2["sharpe_gross"], "sharpe_net": c2["sharpe_net"],
                     "natural_slope": c2["spread_sd"] / math.sqrt(periods_per_year) / (cs_dispersion * k_ds)})
    deff = n_assets / n_eff_lin
    return Design("long_short", name, ser, n_assets * periods_per_year, "asset-periods", deff, n_assets, n_eff_lin,
                  "mean IC per period (net of costs via offset)", slope, offset, implied, curve, rows,
                  _naive(deff * ser.D1), [f"mode={correlation_mode}; rho_bet_linear={rb:.4f}"],
                  dict(n_assets=n_assets, periods_per_year=periods_per_year, ic=ic, cs_dispersion=cs_dispersion,
                       quantile=quantile, rho_resid=rho_resid, rho_signal=rho_signal,
                       signal_autocorr=signal_autocorr, cost_bps_one_way=cost_bps_one_way,
                       spread_autocorr=ac.to_dict(), borrow_bps_annual=borrow_bps_annual, skew=skew,
                       exkurt=exkurt, correlation_mode=correlation_mode, turnover_override=turnover_override,
                       assume_independent=assume_independent))


# ============================================================================================== 6. carry
def crash_moments(p_crash: float, jump_mean: float, jump_sd: float = 0.0) -> dict:
    """Skew / excess kurtosis of X = Z + I*J, Z ~ N(0,1), I ~ Bernoulli(p), J ~ N(jump_mean, jump_sd^2)
    (jump in units of the diffusion sd). Exact cumulants."""
    p, m, s = p_crash, jump_mean, jump_sd
    m1 = p * m
    m2 = p * (m * m + s * s)
    m3 = p * (m ** 3 + 3 * m * s * s)
    m4 = p * (m ** 4 + 6 * m * m * s * s + 3 * s ** 4)
    k2 = m2 - m1 ** 2
    k3 = m3 - 3 * m2 * m1 + 2 * m1 ** 3
    k4 = m4 - 4 * m3 * m1 - 3 * m2 ** 2 + 12 * m2 * m1 ** 2 - 6 * m1 ** 4
    K2 = 1 + k2
    return {"var": K2, "skew": k3 / K2 ** 1.5, "exkurt": k4 / K2 ** 2}


def one_factor_portfolio_moments(n_assets: int, rho: float, factor_skew: float, factor_exkurt: float,
                                 idio_skew: float = 0.0, idio_exkurt: float = 0.0) -> dict:
    """Equal-weight portfolio of K unit-variance assets x_i = sqrt(rho) F + sqrt(1-rho) e_i: cumulants add, so
    skew = [rho^1.5 g3F + (1-rho)^1.5 g3e / K^2] / v^1.5, exkurt = [rho^2 g4F + (1-rho)^2 g4e / K^3] / v^2,
    v = rho + (1 - rho)/K.  Crash risk that is common (in F) does not diversify away."""
    K = float(n_assets)
    v = rho + (1 - rho) / K
    k3 = rho ** 1.5 * factor_skew + (1 - rho) ** 1.5 * idio_skew / K ** 2
    k4 = rho ** 2 * factor_exkurt + (1 - rho) ** 2 * idio_exkurt / K ** 3
    return {"skew": k3 / v ** 1.5, "exkurt": k4 / v ** 2, "var": v}


def scale_mixture_moments(skew: float, exkurt: float, scale_cv: float) -> dict:
    """Time-varying position size w_t (lognormal, independent of the shock, E[w^2] = 1) multiplying a return with
    the given skew/exkurt: skew *= exp(1.5 s2), raw kurtosis *= exp(4 s2), s2 = ln(1 + cv^2)."""
    s2 = math.log(1 + scale_cv ** 2)
    return {"skew": skew * math.exp(1.5 * s2), "exkurt": (exkurt + 3) * math.exp(4 * s2) - 3}


def _rho_from(rho, blocks):
    if blocks:
        return block_mean_corr(blocks["sizes"], blocks["rho_within"], blocks["rho_between"])
    return rho


def carry(*, n_assets: int, periods_per_year: float, rho: float | None, autocorr, skew: float, exkurt: float,
          blocks: dict | None = None, sharpe_per_asset: float | None = None, signal_scale_cv: float = 0.0,
          null_block: int | None = None, assume_independent: str | None = None, name: str = "carry") -> Design:
    """K-asset carry book with crash / skew risk. `skew` and `exkurt` are REQUIRED (the portfolio's per-period
    moments; use crash_moments / one_factor_portfolio_moments to build them). They widen the Sharpe SE by the
    Mertens/Opdyke terms. A time-varying carry signal (position scale cv) further fattens tails (scale mixture).
    Diversification: an equal-weight book of K equal-Sharpe assets with mean pairwise correlation rho_bar has
    S_book = s_asset * sqrt(N_eff), N_eff = K / (1 + (K - 1) rho_bar)."""
    if skew is None or exkurt is None:
        raise TypeError("carry: skew and exkurt must be given explicitly (crash risk is the point)")
    rb = require_explicit_corr(_rho_from(rho, blocks), "rho", units_share_shocks=n_assets > 1,
                               assume_independent=assume_independent, context="carry panel")
    if signal_scale_cv:
        mm = scale_mixture_moments(skew, exkurt, signal_scale_cv)
        skew, exkurt = mm["skew"], mm["exkurt"]
    ac = Autocorr.from_spec(autocorr)
    ser = SeriesModel(periods_per_year, ac, skew, exkurt, null_block)
    n_eff = float(breadth_eff(n_assets, rb))
    implied = {"rho_bar": rb, "n_eff": n_eff, "skew_used": skew, "exkurt_used": exkurt,
               "kappa0": math.sqrt(float(ser.kappa2(0.0))),
               "kappa_at_0.7": math.sqrt(float(ser.kappa2(0.7))),
               "kappa_at_0.7_if_gaussian": math.sqrt(float(SeriesModel(periods_per_year, ac).kappa2(0.7)))}
    if sharpe_per_asset is not None:
        implied["sharpe_net"] = sharpe_per_asset * math.sqrt(n_eff)
    curve = [{"n_assets": k, "n_eff": float(breadth_eff(k, rb))} for k in (1, 2, 4, 8, 16, 32, 64, 128)]
    rows = [{"rho": r, "n_eff": float(breadth_eff(n_assets, r)), "natural_slope": 1 / math.sqrt(breadth_eff(n_assets, r)),
             **({"sharpe_net": sharpe_per_asset * math.sqrt(breadth_eff(n_assets, r))} if sharpe_per_asset else {})}
            for r in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8)]
    deff = n_assets / n_eff
    return Design("carry", name, ser, n_assets * periods_per_year, "asset-periods", deff, n_assets, n_eff,
                  "per-asset net Sharpe", 1 / math.sqrt(n_eff), 0.0, implied, curve, rows,
                  _naive(deff * ser.D1), [], dict(n_assets=n_assets, periods_per_year=periods_per_year, rho=rho,
                                                  blocks=blocks, autocorr=ac.to_dict(), skew=skew, exkurt=exkurt,
                                                  sharpe_per_asset=sharpe_per_asset,
                                                  signal_scale_cv=signal_scale_cv,
                                                  assume_independent=assume_independent))


# ============================================================================================== 7. panels
def panel(*, n_markets: int, periods_per_year: float, rho: float | None, autocorr, blocks: dict | None = None,
          skew: float = 0.0, exkurt: float = 0.0, sharpe_per_market: float | None = None,
          null_block: int | None = None, null_D: float | None = None, assume_independent: str | None = None,
          name: str = "panel") -> Design:
    """K markets x T periods, equal-weight pooled strategy. Average pairwise correlation rho (or blocks
    {sizes, rho_within, rho_between} for regions / sectors). The pooled estimate is the calendar-time EW
    portfolio (equivalently a pooled regression with time-clustered SEs):
        N_eff = K / (1 + (K - 1) rho_bar),  S_book = s_market * sqrt(N_eff).
    A pooled OLS that treats the K*T cells as independent understates the SE by sqrt((1 + (K-1) rho_bar) D)."""
    rb = require_explicit_corr(_rho_from(rho, blocks), "rho", units_share_shocks=n_markets > 1,
                               assume_independent=assume_independent, context="multi-asset panel")
    ac = Autocorr.from_spec(autocorr)
    ser = SeriesModel(periods_per_year, ac, skew, exkurt, null_block, null_D)
    n_eff = float(breadth_eff(n_markets, rb))
    implied = {"rho_bar": rb, "n_eff": n_eff}
    if sharpe_per_market is not None:
        implied["sharpe_net"] = sharpe_per_market * math.sqrt(n_eff)
    curve = [{"n_markets": k, "n_eff": float(breadth_eff(k, rb))} for k in (1, 2, 5, 10, 20, 30, 50, 100, 200)]
    rows = [{"rho": r, "n_eff": float(breadth_eff(n_markets, r)), "natural_slope": 1 / math.sqrt(breadth_eff(n_markets, r)),
             **({"sharpe_net": sharpe_per_market * math.sqrt(breadth_eff(n_markets, r))} if sharpe_per_market else {})}
            for r in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)]
    deff = n_markets / n_eff
    return Design("panel", name, ser, n_markets * periods_per_year, "market-periods", deff, n_markets, n_eff,
                  "per-market net Sharpe", 1 / math.sqrt(n_eff), 0.0, implied, curve, rows,
                  _naive(deff * ser.D1), [],
                  dict(n_markets=n_markets, periods_per_year=periods_per_year, rho=rho, blocks=blocks,
                       autocorr=ac.to_dict(), skew=skew, exkurt=exkurt, sharpe_per_market=sharpe_per_market,
                       assume_independent=assume_independent))


BUILDERS = {"timeseries": timeseries, "event_study": event_study, "cross_sectional_ic": cross_sectional_ic,
            "long_short": long_short, "carry": carry, "panel": panel}


def build(kind: str, params: dict, name: str | None = None) -> Design:
    if kind not in BUILDERS:
        raise ValueError(f"unknown design {kind!r}; choose from {sorted(BUILDERS)}")
    p = dict(params)
    if name:
        p["name"] = name
    return BUILDERS[kind](**p)
