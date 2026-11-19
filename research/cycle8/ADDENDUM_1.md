# Cycle 8 addendum 1 — engine clarifications (before any portfolio return)

Clarifies how FRAMEWORK §3–§5 are implemented. Written and hashed before the first portfolio return. Code:
`research/cycle8/engine/` (unit tests `tests/test_cycle8_engine.py`).

## 1. Simulator

- One step simulator (`core.simulate`) for both frequencies. Rebalance to target at the start of each month; trading
  costs are paid from the account (they reduce equity, then targets are re-set on the post-cost equity). The first
  month starts fully invested with no entry cost.
- **Historical run = daily steps.** Each month's daily sleeve returns are the sleeve's daily proxy returns, shifted
  by a constant daily log drift so they compound exactly to the monthly CAD sleeve return (FRAMEWORK §4.3). Where no
  daily proxy exists for a sleeve-month, the monthly return is spread geometrically. Overlay excess returns are
  spread additively (notional is fixed within the month, so the month's overlay P&L equals notional × monthly
  excess). Loan interest per day = monthly margin rate / trading days in the month. Month-end values give the
  monthly return series on which every §5.1 metric is computed; the daily max drawdown is also reported.
- **Bootstrap = monthly steps**, month-end margin checks only (FRAMEWORK §5.2).
- A negative loan balance (cash left after a forced sale) earns the CAD T-bill.

## 2. Margin requirement with overlays

FRAMEWORK §4.3 says equity/assets ≥ 30%. For unfunded overlays (P6) "assets" is defined as: requirement =
30% × funded assets + 10% × |overlay notional| (futures-style margin on the overlay). A call restores equity to
(35/30) × requirement after paying 1.0% on the amount sold. Items with L = 1.0 and no overlay never borrow and
cannot be called.

## 3. Overlays

- P6a overlay excess (monthly) = AQR TSMOM excess − 2.0%/12 (USD P&L; an unfunded overlay has no principal FX
  exposure, so no USD/CAD translation of notional). This is the FRAMEWORK's "TREND − US T-bill".
- P6b overlay excess = BOND (net of its 0.10% fee) − CAD T-bill.
- Rebalancing cost on overlay notional traded: 0.02% (futures; declared, the FRAMEWORK was silent).

## 4. Withholding tax by account

- L = 1.0 items (P1–P5, and P6 at 1.0x implemented with ETFs in a TFSA) carry the TFSA WHT drag of FRAMEWORK §4.4.
- L > 1 items are margin-account items: no WHT drag (recoverable), pre-tax.

## 5. Sleeve returns known in advance

- Month-t cash return = CAD T-bill yield at end of t−1 / 12; USD cash = Ken French RF for month t; margin rate =
  (BoC policy rate at end of t−1 + 1.5%) / 12. The same columns enter the joint bootstrap vector.
- P5 weights at month t use the 36 months ending t−1 of each sleeve's CAD monthly return (net of drags).

## 6. P7 and P8

- P7 has no loan and no margin calls. Its monthly CAD return series (from the daily simulation) enters the bootstrap
  as one more column of the joint vector. Rebalancing to 60/40 monthly costs 0.05% of traded notional + 0.10% FX.
- P8 = CAD T-bill as a funded sleeve.

## 7. Supplementary W_US1926 run

USD base, US-only sleeves: Ken French US market, US 10Y par bond, US T-bill (Ken French RF). Margin rate =
US T-bill yield + 1.5%. Daily margin monitoring with Ken French daily equity; bonds spread geometrically before daily
yields exist. Same fees; no WHT (not a Canadian account question). Not used by the answer rule.

## 8. Forward lens details

- Portfolio σ for forward geometric returns: historical CAD monthly covariance of sleeves on W_COMMON; P5 uses its
  average realised weights on W_COMMON; σ scales with L.
- Forward WHT drag on EQ_G at L = 1.0: 0.45 × 15% × current US dividend yield + 0.25 × 10% × 3.0% + 0.05 × 10% × 2.5%.
- Forward fee drags as FRAMEWORK §2; forward financing = (forward CAD cash + 1.5%) × (L − 1); forward overlay
  return = L × 0.5 × (E[sleeve] − forward cash) − drag.

## 9. Sharpe CI

`research/amendment4/ci.calibrated_ci(excess, level=0.95, q=12, seed=20260928)` on monthly CAD excess returns.

## 10. Data decisions (after acquisition, before any portfolio return)

Sources, splices and checks: `data/cycle8/meta/*.json`, `data/cycle8/notes/*.md`, `data/cycle8/cma/`.

| Item | Decision |
|---|---|
| Canada equity | Ken French Canada from **1977-01** (not 1975); 1971-01..1976-12 backfilled with US (FRAMEWORK rule). 2026-01..08 spliced from XIC.TO (USD) — accepted, declared. |
| Dev ex-NA | Ken French "Major Markets" (EAFE+Canada cap-weighted) with Canada backed out (rolling NNLS Canada share), 1975-01+; 1971–74 backfilled with US. Cap-weighted, so the equal-weight fallback is not used. 2026 spliced from MSCI EAFE gross. |
| EM | Ken French Emerging 1989-07+; before, its weight uses dev ex-NA. |
| US dividend yield | Shiller D/P ends 2024-06; forward-filled after (WHT drag only). |
| USD/CAD | Fed H.10 daily (= FRED DEXCAUS), month-end = last daily obs; 1971-01+. FRED itself was unreachable. |
| Canada 10Y | StatCan/BoC splice (over-10y avg 1936–50, 5–10y avg 1951–82-05, 10Y benchmark after); point-in-time. |
| Policy rate | Bank Rate to 1995-12 (≈0.22 pt above target; unadjusted), overnight target from 1996-01. |
| Gold | **World Bank monthly-average** price 1960–2000-07 (no free month-end series exists before 2000-08), then COMEX front-month month-end. Declared limitation: gold volatility and drawdowns before 2000-08 are understated and lagged by averaging. Daily gold proxy (margin paths) from 2000-08. |
| Trend | AQR TSMOM (gross) 1985-01..**2026-05**; the Century series is not free, so the trend sleeve starts 1985-01. Drag 2.0%/yr as declared. |
| Daily USD T-bill | Monthly Ken French RF spread geometrically over trading days (the daily KF RF is rounded to 1 bp/day). |
| Daily proxies (margin paths) | EQ_G: available components renormalised (US 1926+, Canada TSX price 1979-07+, dev ex-NA 1990-07+, EM 2001+) × daily USD/CAD (1971+); BOND: 0.6 CA10 (2001+) + 0.4 US10 (1962+), renormalised; GOLD: GC=F × USD/CAD (2000-08+); TREND, CASH: geometric. |
| Windows | W_MAIN 1971-01..2026-08 (2026-05 for trend-holding items). P5 first month 1988-01 (36-month burn-in from 1985-01). **W_COMMON = 1988-01..2026-05.** |

### 10.1 Forward-lens CMA mapping rules (fixed before any portfolio return)

1. Median across the five target sources that yielded data: FP Canada 2026, J.P. Morgan LTCMA 2026 (CAD matrix),
   Vanguard VCMM (2026-06-30 run), AQR 2026 CMA, BlackRock (Aug 2026). Research Affiliates is blocked (terms
   acceptance required). Horizon survey and GMO are reported but excluded from the median.
2. Where a source publishes CAD-denominated figures, use them (JPM CAD matrix; BlackRock's own CAD figures,
   i.e. its XEQT-weight CAD blend) instead of converting its USD figures.
3. Geometric figures without a source volatility are converted to arithmetic with + σ²/2 using the sleeve's
   historical CAD σ on W_COMMON (same σ used for portfolio geometric returns).
4. JPM's "macro hedge fund" is not a trend figure → TREND uses the fallback (forward USD cash + 2.0%, converted);
   no source publishes a trend/CTA figure, so TREND is the fallback for every source (flagged).
5. GOLD: only JPM publishes (5.73); the others use their forward CAD inflation (fallback).
6. Missing CAD cash / inflation are filled with the median of the sources that publish them (flagged).
7. FP Canada figures used without its 0.5% safety-margin add-back.
