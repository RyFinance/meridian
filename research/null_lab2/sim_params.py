"""Per-family simulation parameters: periods/year, representative vol, AR(1) phi, and the
null-world knobs (cost-drag Sharpe, shift/permutation null offset, residual beta-leak).

These are calibration inputs, not measurements of the real family -- the hard constraint bars
loading any real price or return series for this workstream. Defaults are chosen to be consistent
with (1) the figures visible in each family's own reports/*/dev_results.json (annualised vol,
active mean, reported null mean/sd where given) and (2) the calibration ranges `reports/null_lab/
REPORT.md` already established for this same project (kappa ~0.85-1.4; cost drag pulls null
Sharpes to about -0.3). Every override below cites the number it is matched to.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SimParams:
    periods_per_year: float
    annual_vol: float          # representative annualised vol of the tested (active or absolute) series
    phi: float                 # AR(1) autocorrelation, period-to-period
    null_offset_a: float = -0.30   # true annualised Sharpe under null world (a): zero gross + cost drag
    null_offset_b: float = 0.0     # true annualised Sharpe under null world (b): zero net
    shift_perm_offset: float = -0.30  # reference-distribution offset (Sharpe units) for shift/permutation
                                       # nulls; -0.30 is the null_lab project-wide cost-drag default
    beta_leak: float = 0.05    # residual/uncancelled exposure (Sharpe units) used in world (c) for
                                # "absolute" (non-active) gates and as a small residual for active gates
    stress_drag: float = 0.008  # extra annualised mean drag applied for the stress-cost leg


# Default by periods_per_year bucket, keyed off the plan text ("weekly returns, sqrt(52)", etc).
PERIODS = {
    "weekly": 52.0,
    "daily": 252.0,
    "monthly": 12.0,
    "cycle": 12.03,
}

_DEFAULT_DAILY_ACTIVE = SimParams(periods_per_year=252.0, annual_vol=0.05, phi=0.05)
_DEFAULT_DAILY_ABSOLUTE = SimParams(periods_per_year=252.0, annual_vol=0.12, phi=0.05, beta_leak=0.225)
_DEFAULT_WEEKLY = SimParams(periods_per_year=52.0, annual_vol=0.08, phi=0.10)
_DEFAULT_MONTHLY = SimParams(periods_per_year=12.0, annual_vol=0.08, phi=0.15)

# Family-specific overrides (family key must match families.GateRow.family exactly).
OVERRIDES: dict[str, SimParams] = {
    # --- pre-amendment, weekly-return families ---
    "options_signals(H1-H4)": SimParams(52.0, 0.10, 0.05),
    "cot(C1-C3)": SimParams(52.0, 0.07, 0.10),
    "fx_carry_vol(F2,F3 vs F1)": SimParams(52.0, 0.05, 0.10),

    # --- pre-amendment, monthly-return families ---
    "iv_changes(V1-V3)": SimParams(12.0, 0.06, 0.10),
    "fundamentals(F1-F3)": SimParams(12.0, 0.05, 0.20),
    "survivor_hybrid(H1-H4)": SimParams(12.0, 0.10, 0.15, beta_leak=0.10),

    # --- pre-amendment, daily, active-vs-control books ---
    "insider(N1-N4)": SimParams(252.0, 0.11, 0.05),
    "pead_streak(S1-S2)": SimParams(252.0, 0.09, 0.05),
    "pead_2004_2014": SimParams(252.0, 0.10, 0.05),
    "pead_portfolio(B1-B5)": SimParams(252.0, 0.09, 0.05),

    # --- pre-amendment, daily, absolute-Sharpe (unhedged / long-tilted) books ---
    "putwrite(P1-P3)": SimParams(252.0, 0.06, 0.10, beta_leak=0.20),
    "intraday(I1-I4)": SimParams(252.0, 0.12, 0.05, beta_leak=0.05),
    "rebalancing(R1-R3)": SimParams(252.0, 0.10, 0.05, beta_leak=0.30),
    "letf_rebalancing(L1-L2)": SimParams(252.0, 0.13, 0.05, beta_leak=0.20),
    "auction_cycle(A1-A3)": SimParams(252.0, 0.05, 0.05, beta_leak=0.10),
    "etf_hybrids(E1-E5)": SimParams(252.0, 0.13, 0.05, beta_leak=0.45),
    "macro_surprise(M1,M2)": SimParams(252.0, 0.09, 0.05, beta_leak=0.10),

    # --- multi-asset (sleeve inclusion is a best-of-17 absolute-Sharpe screen; long-tilted) ---
    "multiasset(17-sleeve inclusion + 5-sleeve holdout)": SimParams(252.0, 0.10, 0.10, beta_leak=0.15),
    "multiasset/crypto(2 candidates)": SimParams(252.0, 0.55, 0.10, beta_leak=0.18),

    # --- post-amendment, active-vs-control books (bootstrap null) ---
    "japan_us_flow(J1)": SimParams(252.0, 0.055, 0.02, shift_perm_offset=-0.20),
    "credit_lead": SimParams(252.0, 0.035, 0.05, beta_leak=0.30),
    "index_option_breadth": SimParams(252.0, 0.045, 0.05, beta_leak=0.10),
    "structural_frontier(A: Treasury term premium)": SimParams(252.0, 0.030, 0.10),
    "structural_frontier(B: HY credit carry)": SimParams(252.0, 0.06, 0.10),
    "structural_frontier(C: TLT put insurance)": SimParams(12.03, 0.05, 0.10),
    "vrp_putwrite(PW)": SimParams(12.03, 0.04, 0.15),
    "commodity_roll": SimParams(252.0, 0.06, 0.10),
    "mbs_convexity": SimParams(252.0, 0.013, 0.10),

    # --- post-amendment, shift-null books ---
    "credit_gate(G)": SimParams(252.0, 0.045, 0.05, shift_perm_offset=-0.15),
    "etf_basis(B)": SimParams(252.0, 0.014, 0.15, shift_perm_offset=-0.20),
    "tsy_month_end(M)": SimParams(252.0, 0.028, 0.15, shift_perm_offset=-0.05),
    "sector_month_end": SimParams(252.0, 0.010, 0.20, shift_perm_offset=-0.965),  # matches its own
                                                                                    # reported shift-null
                                                                                    # mean_sd=[-0.965,0.31]

    # --- post-amendment, permutation-null books ---
    "policy_trend(P1)": SimParams(12.0, 0.075, 0.15, shift_perm_offset=-0.10),
    "fx_news(F1,F2)": SimParams(252.0, 0.06, 0.02, shift_perm_offset=-4.0),  # matches its own reported
                                                                               # perm_sharpe_mean_sd
                                                                               # approx [-4.08, 0.42]
    "fx_hedge_rebal": SimParams(252.0, 0.02, 0.10, shift_perm_offset=-0.27),  # matches its own reported
                                                                                # perm_mean_sd approx -0.27
}


def get(family: str, dev_kind: str, dev_null: str, periods_per_year_hint: float | None = None) -> SimParams:
    if family in OVERRIDES:
        return OVERRIDES[family]
    if periods_per_year_hint == 52.0:
        return _DEFAULT_WEEKLY
    if periods_per_year_hint == 12.0:
        return _DEFAULT_MONTHLY
    if "active" in dev_kind:
        return _DEFAULT_DAILY_ACTIVE
    return _DEFAULT_DAILY_ABSOLUTE
