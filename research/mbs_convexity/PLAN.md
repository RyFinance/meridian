# MBS negative-convexity premium (MBB vs rate-hedged Treasuries): pre-registration

Status: DRAFT until registered. Written 2026-09-23 before any MBB return was computed.

## Novelty and mechanism

- No project trial has used agency MBS. The duration premium (IEF−SHY) and HY carry were tested by
  `structural_frontier`; this is a different risk.
- **Mechanism.** MBS holders are short the borrower's prepayment option, i.e. negative convexity.
  They must dynamically hedge duration, and are paid a spread above duration-matched Treasuries
  for bearing prepayment and convexity risk (Boyarchenko, Fuster & Lucca, *RFS* 2019).
- **Who pays:** homeowners holding the refinancing option, through mortgage rates.
- **Why it persists:** hedging costs and balance-sheet limits of MBS investors.
- **Direction (fixed):** long MBB, short a rate-matched Treasury mix. Never reversed.

## Rules

- **Prices:** yfinance adjusted closes for MBB, IEF and SHY.
- **Hedge (point in time).**
  - At each month's first session close t, regress MBB daily returns on IEF and SHY daily returns
    over the prior 252 sessions ending at t−1. Use no-intercept OLS, with coefficients clipped to
    [0, 2].
  - The hedge is h_IEF·IEF + h_SHY·SHY, held for the month.
- **Book:** long 1.0 MBB, short the hedge. Excess return = r_MBB − (h_IEF r_IEF + h_SHY r_SHY) −
  (1 − h_IEF − h_SHY) × rf.
- **Costs:** base 3 bp per side on MBB trades and 2 bp on the hedge legs; stress ×3. Borrow on the
  short Treasury ETFs: base 0.3%, stress 1.0% per year.

## Control and null

- **Controls:**
  - the hedge itself is the duration control;
  - a static-hedge diagnostic using full-development-window betas (look-ahead, descriptive only).
  Also reported: beta to SPY excess, beta to HYG excess (credit), year-by-year results, and the
  2008 and 2013 contributions.
- **Null:** a mean-centred block bootstrap of daily book returns (21-day blocks, 5,000 draws, seed
  20260923).

## Windows

- **Development:** MBB 2007-03-16 + 252 sessions warm-up → 2016-12-30.
- **Validation (locked):** 2017-01-03 → 2026-09-17.

## Gates

- **Development:** net base Sharpe ≥ 1.8/√T (T ≈ 8.8 years, so about 0.61), stress mean > 0, and
  bootstrap p < 0.025 (two Workstream A tests).
- **Validation:** net Sharpe ≥ 0.75, stress mean > 0, p < 0.025.

## Limits

- MBB is a pass-through ETF, not TBA dollar rolls.
- The hedge is regression-based, so its duration drifts within the month.
- The 2008 crisis is in development.
