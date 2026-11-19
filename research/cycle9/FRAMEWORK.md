# Cycle 9 framework — live trend evidence (item 1) and cycle 8b (item 2)

Written 2026-09-28 (UTC) **before any cycle-9 data were acquired or any cycle-9 return computed.** Frozen by the
SHA-256 in `research/cycle9_prereg_ledger.md`. Changes only via hashed addenda before the returns they govern.
Cycle 8's registered answers stand; nothing here overwrites them. Research only; not a recommendation to trade.

**Prior knowledge (disclosed).** Cycle 8's data pass already compared the AQR TSMOM sleeve with AQMIX, ASFYX,
PQTIX, WTMF, FMF, DBMF, KMLM and CTA (`data/cycle8/notes/trend_checks.md`): e.g. AQMIX 2010–2026 ≈ 4.5%/yr USD,
DBMF 2019–2026 ≈ 9.3%/yr. The cycle-8 audit also computed post-2012 AQR TSMOM statistics. The rules below were
written knowing those numbers; they are mechanical and do not depend on any fund's performance.

## Part A — Live trend evidence (item 1)

### A1. Search modalities (all free; each hit recorded, included or not)

1. US-registered open-end mutual funds and ETFs in the managed-futures / systematic-trend category (sponsor sites,
   SEC EDGAR, exchange/Yahoo/LSE prices), **including liquidated and merged funds**.
2. SEC-registered public commodity pools ("public futures funds") that file 10-K/10-Q/8-K/424B on EDGAR, with
   monthly NAV per unit or CFTC performance capsules (monthly rates of return), **including dissolved pools**.
3. Canadian-listed funds/ETFs with a trend mandate (and TFSA-holdability of every candidate).
4. Free, published CTA/trend indices (e.g. SG CTA, SG Trend, BTOP50, Barclay CTA). **Reported separately; never
   pooled with funds** (indices are not a single investable net-of-fee record and may carry selection/backfill bias).

### A2. Fund-inclusion rule (mechanical; applied to mandate text and dates only — never to performance)

A vehicle is **included** iff all hold:
- **I1 Live and public:** a registered fund/ETF or SEC-registered public commodity pool open to public investors,
  with a net-of-all-fees NAV or return history from a free primary or exchange source (sponsor document, SEC filing,
  exchange price adjusted for distributions).
- **I2 Diversified systematic trend:** the principal strategy stated in the prospectus/10-K is systematic
  (rules-based/quantitative) trend-following or managed futures trading futures/forwards in **≥ 3** of
  {equity indices, interest rates/bonds, currencies, commodities}. Multi-advisor pools qualify only if the filing
  states that the advisors are systematic/technical trend followers (≥ 2/3 of allocated assets at the start of the
  record). Replication/index ETFs of diversified trend (e.g. DBMF, KMLM, CTA) qualify.
- **I3 Exclusions:** discretionary macro; single-sector or single-asset-class programs; multi-strategy or
  style-premia funds where trend is not the stated principal strategy; leveraged/inverse, option-writing, long-only
  commodity, and funds of hedge funds with non-trend managers.
- **I4 History:** ≥ 36 consecutive monthly net returns.
- **I5 Survivorship:** liquidated, merged or dissolved vehicles are included for every month they reported; the
  final month uses the last reported NAV (liquidation at that NAV).
- **I6 One record per program:** one share class per fund (the class with the longest history; ties → lowest fee);
  a feeder and its master, or two vehicles of the same sponsor running the same program, count once (longer record).
- Ambiguous mandate text is resolved by two independent classifications from the text alone; disagreement →
  excluded and listed.

### A3. Returns

Monthly net total return in the fund's currency (USD for all US vehicles), from NAV per unit (or published monthly
rate of return; or distribution-adjusted close). Excess return = net return − US T-bill (Ken French RF) for USD
funds; CAD funds − CAD T-bill. No fee is deducted (records are already net).

### A4. Estimators

- **E1 equal-weight pooled series:** each month, the equal-weight mean of the excess returns of all included funds
  live that month; defined only for months with **≥ 3** funds live ("live era").
- **E2 inverse-variance pooled estimate:** per fund i, mean excess μ_i over its full history and its HAC variance
  v_i (Newey–West, bandwidth `research/amendment4/calib.stat_lags`); μ_IV = Σ(μ_i/v_i)/Σ(1/v_i). Same for the
  annualised Sharpe with a delta-method HAC variance.
- **Uncertainty for E1 and E2:** stationary block bootstrap over calendar months (mean block 12, 5,000 draws,
  seed 20260929) resampling all funds jointly, so cross-fund correlation is kept. E1 also gets the A4 calibrated
  95% CI on its Sharpe.
- Per-fund table: inception, end, months, fee (ER / management + incentive), net CAGR, excess over cash, vol,
  Sharpe, max DD, correlations with SPY and IEF (monthly; before SPY/IEF exist, Ken French market and the US 10Y par
  bond from the cycle-8 snapshot).

### A5. Windows

- **W1:** each fund's full live history; E1 over the whole live era.
- **W2 common window:** the balanced panel of all included funds with ≥ 120 months, over [latest start, earliest
  end] of that subset (if it spans < 36 months, the 5 longest records instead).
- **Episodes:** calendar 2008, 2018, 2020 (and 2020-02..03), 2022, 2023–2025.
- **Comparison:** AQR TSMOM gross excess, and gross − 2.0%/yr (cycle 8's drag), on exactly the same months as each
  window (AQR data end 2026-05).

## Part B — Cycle 8b (item 2): one registered rerun, new experiment

Frozen and reused unchanged: cycle-8 FRAMEWORK and ADDENDUM_1, engine code (hash `1118dda9…`), `forward.py` rules,
CMA mapping, snapshot `cycle8_v1` for every non-trend input, menu, leverage levels, costs, windows (trend-holding
items 1985-01..2026-05), seeds. **Exactly these changes:**

- **C1 Trend sleeve input.** USD excess (already net of fees) X_t, no extra drag (`TREND_DRAG = 0`):
  - live era (E1 defined): X_t = k · E1_t, where k = (median full-history vol of the included funds) / (vol of E1
    over the live era) — a single constant so the sleeve carries a typical single fund's risk;
  - before the live era (and from 1985-01): X_t = k_pre · (TSMOM_t − m_pre) + ρ · m_pre, where m_pre = mean of AQR
    TSMOM gross over the pre-live months, ρ = mean(k·E1) / mean(TSMOM) over the live era (live/backtest ratio of
    mean excess on identical months), and k_pre = vol(k·E1) / vol(TSMOM) over the live era (so pre-live volatility
    and correlation structure are AQR's, the level is live-like, and the mean is scaled by the live/backtest ratio).
  - Sensitivity (reported, not used by the answer): (s1) unscaled E1 (k = 1); (s2) full haircut: pre-live mean
    = live mean (ρ·m_pre replaced by mean(k·E1)).
- **C2 Daily drawdown evaluation.** Historical: the daily max drawdown of the reconstructed daily path (cycle-8
  method). Bootstrap: stationary block bootstrap over months (mean block 24, 10,000 paths, 20-year horizon, seed
  20260928) where each drawn month carries its full reconstructed **daily** sleeve path; the portfolio is simulated
  at daily steps with the cycle-8 engine (daily margin monitoring, month-start rebalancing). Output P(max daily DD
  > T). 12-month blocks and 10/30-year horizons as sensitivities.
- **C3 Daily trend proxy.** Within-month daily path of the trend sleeve = equal-weight daily NAV returns of the
  included funds that have daily data that month, rescaled to the monthly total (cycle-8 rule); geometric where none.
- **C4 Answer rule.** For T ∈ {25, 35, 50}%: eligible iff P(max daily DD > T, 20 y) < 10% and historical Sharpe ≥
  P3 1.0x Sharpe on the same window; answer = highest forward-lens geometric return (median CMA), ties → lower L.
  The answer is **flagged** if its historical daily max DD > T; the highest-forward eligible item **without** a flag
  is also reported (secondary).
- One run, registered as experiment `cycle8b_main` on a new snapshot `cycle9_v1` (live-trend inputs) plus
  `cycle8_v1`. Results are compared with cycle 8 side by side; cycle 8 is not edited.
