# Cycle 8 framework — highest expected return under a drawdown limit, Canadian retail

Written 2026-09-27/28 (UTC) **before any portfolio, sleeve or ETF return was computed** in this cycle. Frozen by the
SHA-256 in `research/cycle8_prereg_ledger.md`. Changes after hashing go only in numbered addenda, each hashed before
the returns it governs. Data-only addenda (sources found/blocked, splices) are allowed before the first portfolio
return; nothing in §2–§8 may change after the first portfolio return.

## 0. Framing

Portfolio construction from known risk premia, **not alpha research**. No claim of edge is made or tested. The
question: for a Canadian retail investor, which pre-declared portfolio gives the highest expected long-run return
while (a) its Sharpe is at least the plain 60/40's and (b) its drawdown risk is within a stated tolerance
(25%, 35%, 50%)? Research only; not a recommendation to trade.

## 1. Base conventions

- **Currency:** CAD. Every return is a CAD total return. USD assets convert at month-end USD/CAD (daily where daily
  paths are used). Unhedged unless stated.
- **Cash / risk-free:** Canadian 3-month T-bill (Bank of Canada / FRED). Sharpe = mean monthly (return − CAD T-bill)
  / sd × √12.
- **Inflation:** Canada CPI (all items), for real CAGR.
- **Frequency:** monthly engine, month-end rebalancing to target weights. Daily paths are used only for (i) the
  daily-reset leveraged ETF simulation (P7) and (ii) margin-call monitoring (§4.3).
- **Windows (fixed):**
  - `W_MAIN` 1971-01 → last common month (CAD base; USD/CAD floats from 1970-06; FRED EXCAUS starts 1971-01).
  - Each portfolio is scored on its **own window** = W_MAIN intersected with the availability of all its sleeves
    (after any declared backfill in §2). Its Sharpe hurdle is P3 1.0x **on the same window**.
  - `W_COMMON` = the latest start among P1–P6 → end: every portfolio on identical months (reported alongside).
  - `W_US1926` (supplementary, USD, US-only sleeves): 1926-07 → end, P1–P3 with US equity / US 10Y / US T-bill,
    to show 1929–32 and 1937 leverage outcomes. Not used by the answer rule.

## 2. Sleeves (fixed)

| Sleeve | Definition | Source priority (first available wins; splices declared in the data addendum) | Fee drag (%/yr) |
|---|---|---|---|
| `EQ_G` global equity, unhedged | Fixed XEQT-like mix, monthly rebalanced: 45% US, 25% Canada, 25% developed ex-North-America, 5% EM | US: Ken French market (Mkt-RF + RF), 1926+. Canada: Ken French international country "Canada" (USD, total return, 1975+); before that, US. Dev ex-NA: a published cap-weighted aggregate (Ken French/MSCI, total return) if available, else equal-weighted mean of available developed ex-NA Ken French country returns; before availability, US. EM: Ken French emerging / MSCI EM, total return; before availability its weight goes to dev ex-NA. All USD, converted to CAD. | 0.20 |
| `EQ_GH` global equity, CAD-hedged | EQ_G with the USD/CAD leg hedged: r_H = r_USD + (rf_CAD − rf_USD) − 0.10%/yr hedge cost (non-USD currencies vs USD stay unhedged; declared approximation) | as EQ_G | 0.20 |
| `BOND` | 60% Canada 10Y constant-maturity + 40% US 10Y constant-maturity hedged to CAD (r + rf_CAD − rf_USD) | Par-bond repricing from month-end yields: coupon = y_{t−1}, remaining maturity 10 − 1/12, priced at y_t (duration and convexity exact). Canada 10Y: FRED IRLTLT01CAM156N / BoC. US 10Y: FRED GS10 (1953+), Shiller long rate before. Validated vs XBB/ZAG (Canada) and IEF (US) on overlap. | 0.10 |
| `GOLD` | Spot gold USD → CAD | Monthly LBMA/Bundesbank gold (datahub `gold-prices`), daily LBMA where available; validated vs GLD. | 0.25 |
| `TREND` | Funded managed futures: US T-bill + TSMOM excess return − 2.0%/yr drag (1.0% ETF fee + 1.0% trading/replication shortfall), USD → CAD | AQR "Time Series Momentum: Factors, Monthly" (TSMOM, 1985+). Before 1985, AQR "A Century of Evidence on Trend-Following" **net-of-fee** excess series if obtainable (its 2/20 fee replaces the 2.0% drag); else the sleeve starts 1985-01. Validated vs DBMF, KMLM (and CTA if available) since inception. | in drag |
| `CASH` | CAD 3-month T-bill | BoC / FRED | 0 |

Fee drags are deducted monthly (drag/12). They apply to every portfolio holding the sleeve, levered or not.

## 3. Fixed menu (weights at 1.0x; leverage multiplies every risky weight)

| ID | Portfolio | 1.0x weights | Leverage levels |
|---|---|---|---|
| P1u | 100% global equity, unhedged | EQ_G 100 | 1.0, 1.25, 1.5, 2.0 |
| P1h | 100% global equity, CAD-hedged | EQ_GH 100 | 1.0, 1.25, 1.5, 2.0 |
| P2 | 80/20 | EQ_G 80, BOND 20 | 1.0, 1.25, 1.5, 2.0 |
| P3 | 60/40 (the benchmark) | EQ_G 60, BOND 40 | 1.0, 1.25, 1.5, 2.0 |
| P4 | 60/40 + 10 gold + 10 trend | EQ_G 48, BOND 32, GOLD 10, TREND 10 | 1.0, 1.25, 1.5, 2.0 |
| P5 | Risk parity (static inverse-vol) | EQ_G, BOND, GOLD, TREND ∝ 1/σ_i, σ_i = trailing 36-month sd of monthly CAD returns known at month-end t−1; weights sum to 1; monthly | 1.0, 1.25, 1.5, 2.0 |
| P6a | Stacked: equity + trend overlay | EQ_G 100 + 0.5 × (TREND − US T-bill) unfunded overlay (gross 1.5) | 1.0, 1.25, 1.5, 2.0 (gross 1.5 → 3.0) |
| P6b | Stacked: equity + bond overlay (NTSX-style) | EQ_G 100 + 0.5 × (BOND − CAD T-bill) unfunded overlay (gross 1.5) | 1.0, 1.25, 1.5, 2.0 |
| P7-2x | Leveraged 60/40 via daily-reset ETFs (**cautionary benchmark only**) | 60% simulated SSO (2x daily US equity) + 40% simulated UBT (2x daily US 20Y Treasury) | fixed, no dial |
| P7-3x | same, 3x (**cautionary only**) | 60% simulated UPRO + 40% simulated TMF | fixed, no dial |
| P8 | Cash (reference) | CASH 100 | 1.0 only |

No other portfolio, weight or leverage level will be computed for the ranking or the answer. P7 and P8 are excluded
from the answer.

## 4. Leverage and account realism

### 4.1 Margin financing (P1–P6 at L > 1, and the overlay notional of P6 at every L)

- At leverage L the funded risky weights are L × (1.0x weights); the margin loan is (L − 1) × NAV. For P6 the
  overlay is unfunded and futures-like: it adds 0.5 × L × (sleeve − T-bill) with no loan (its financing is inside the
  excess return); the margin loan is still (L − 1) × NAV on the funded equity.
- **Margin rate (CAD):** Bank of Canada policy rate (overnight target; Bank Rate before the overnight target existed)
  + **1.5%/yr** (discount-broker spread, IBKR-Canada-like). Sensitivity (reported, not used by the answer):
  + 3.0%/yr (bank-broker prime-based).
- Rebalanced monthly back to target L.

### 4.2 Daily-reset leveraged ETFs (P7)

Daily ETF return = k × r_index,d − (k − 1) × (US T-bill_d + s) − ER/252, compounded daily; k ∈ {2, 3}.
- Equity index: Ken French daily US market total return (CRSP VW; declared proxy for the S&P 500). s = 0.50%/yr.
  ER: SSO 0.89%, UPRO 0.91%.
- Treasury index: 20Y constant-maturity par bond from daily yields (FRED DGS20; DGS30 in DGS20's gap; declared splice).
  s = 0.25%/yr. ER: UBT 0.95%, TMF 1.06%.
- USD → CAD at daily USD/CAD; the two ETFs rebalanced to 60/40 monthly. Validated vs actual SSO/UPRO/TMF (and UBT)
  since inception.

### 4.3 Margin calls (P1–P6 at L > 1)

- Maintenance: equity / assets ≥ **30%** (CIRO-style reduced margin for broad-index ETFs; declared).
- Monitoring **daily**. Each sleeve's daily path is its own daily proxy (US equity: Ken French daily; Canada: TSX
  composite daily price; dev ex-NA / EM: the best free daily index/ETF; bonds: daily yields; gold: daily LBMA/GLD;
  USD/CAD daily). Each daily path is rescaled by a constant daily log drift so it compounds exactly to the sleeve's
  monthly return. Sleeves or months without a daily proxy use geometric interpolation (declared: this understates
  intramonth drawdowns for those sleeves).
- On a breach the broker sells at that day's close enough assets to restore equity/assets = 35% (maintenance + 5-point
  buffer), paying **1.0%** on the amount sold. The investor re-levers to target L at the next month-end.
  If equity ≤ 0 the portfolio is ruined (wealth 0 thereafter). Each breach day is one forced-liquidation event.
- The bootstrap (§5.2) runs monthly and checks margin on month-end values only (declared understatement).

### 4.4 Costs, taxes and accounts

- Rebalancing: 0.05% of traded notional for equity/bond ETFs, 0.10% for gold and trend.
- CAD/USD conversion: 0.10% on the USD-listed notional traded (trend, P7, and USD-listed capital-efficient ETFs).
- **Withholding tax (primary account = TFSA holding CAD-listed one-ticket ETFs):** US sleeve 15% × US dividend yield
  (Shiller D/P, time-varying); dev ex-NA sleeve 10% × 3.0%; EM 10% × 2.5%; Canada 0. Taxable margin accounts: WHT
  recoverable via foreign tax credit → no WHT drag, but income tax is not modelled (**pre-tax**, declared).
- **Account feasibility:** TFSA/RRSP cannot borrow. L > 1 is TFSA/RRSP-feasible only via ETFs with built-in
  leverage (e.g. NTSX, RSSB, RSST, GDE, SSO/UPRO/TMF). The report states for each
  menu item × L whether a TFSA/RRSP implementation exists and which tickers approximate it (exact or approximate,
  with the approximation named).

## 5. Evaluation (every menu item × L)

### 5.1 Historical metrics (own window and W_COMMON)

CAGR nominal and real (CAD), annualised volatility, Sharpe with a **95% calibrated CI**
(`research/amendment4/ci.py:calibrated_ci`, q = 12, level 0.95), maximum drawdown (month-end, and daily where the
daily path exists), longest time underwater (months, peak to recovery or to the end), worst 12-month return, ulcer
index (√mean(DD²) of monthly drawdowns in %), forced-liquidation count, ruin flag.

**Named crises (fixed windows; cumulative return and in-window max drawdown):** 1973-01..1974-12 (oil/inflation
bear), 1979-10..1981-09 (Volcker rates shock), 1987-08..1987-12 (crash), 2000-09..2002-09 (dot-com),
2007-11..2009-02 (GFC), 2020-02..2020-03 (COVID), 2022-01..2022-10 (stocks and bonds fell together).
W_US1926 adds 1929-09..1932-06 and 1937-03..1938-03.

### 5.2 Drawdown probability (block bootstrap)

Stationary block bootstrap (Politis–Romano) of the **joint monthly vector** of all sleeve returns, CAD T-bill,
margin rate, USD T-bill (so cross-asset crisis clustering is kept), from each portfolio's own window. Mean block
length **24 months** (primary; keeps multi-year crises intact); 12 months reported as sensitivity.
**Horizon 20 years** (240 months) primary; 10 and 30 years reported. 10,000 paths, seed 20260928. The portfolio
rule (incl. P5 trailing vol with a 36-month burn-in drawn from the same path, and month-end margin checks) runs on
each path. Output: P(max DD > 25%), P(> 35%), P(> 50%), P(ruin).

### 5.3 Kelly check

For each portfolio's 1.0x monthly return r, the growth-optimal leverage L* = (mean(r) − mean(margin rate)/12) /
var(r) (margin-financed leverage). Parameter uncertainty: the same stationary bootstrap (24-month blocks, 5,000
draws) gives a distribution of L*. Report median L*, its 5th percentile, and **half-Kelly = 0.5 × median L***. Any
L above half-Kelly is flagged **imprudent**; also report 0.5 × 5th-percentile L* as the uncertainty-robust bound.

### 5.4 Two lenses for expected return

- **(a) Historical:** realised CAGR on the own window (and W_COMMON).
- **(b) Forward:** published long-term capital market assumptions (CMAs) opened from free sources (target set:
  Vanguard, Research Affiliates, AQR, BlackRock, J.P. Morgan LTCMA, FP Canada Projection Assumption Guidelines;
  every figure cited with URL, edition and horizon). Per sleeve, the forward expected **arithmetic** CAD return =
  median across the sources covering it; range = min–max. Mapping rules: global equity = the source's global/ACWI
  figure (else the XEQT-weight blend of its US/Canada/EAFE/EM); bonds = Canadian aggregate/universe figure (else
  Canadian government) blended 60/40 with the US aggregate hedged (USD figure + forward CAD − USD cash);
  gold = source figure if published, else forward CAD inflation; trend = source figure if published, else forward
  USD cash + 2.0% (a declared, conservative premium; minus the 2.0% drag = cash) — the report shows both;
  cash = forward CAD cash. USD figures convert to CAD by adding (forward CAD cash − forward USD cash).
  Portfolio forward arithmetic mean = Σ w_i·E[r_i] − fees − L-scaled financing at (forward CAD cash + 1.5%);
  forward **geometric** = arithmetic − σ²/2 with σ from the historical covariance on W_COMMON. Ranking uses forward
  geometric (median CMA); the range uses the min and max source.
- Rank all items under (a) and (b); report every ranking flip. State the historical haircut per sleeve explicitly
  (historical realised − forward median).

## 6. Answer rule (fixed)

For each tolerance T ∈ {25%, 35%, 50%}: among P1u–P6b × {1.0, 1.25, 1.5, 2.0}, an item is **eligible** iff
1. bootstrap P(max DD > T over 20 years) < 10% (primary settings), **and**
2. its historical Sharpe point estimate ≥ P3 1.0x Sharpe on the same window.

The answer is the eligible item with the highest forward-lens geometric expected return (median CMA). Report its
forward range, historical CAGR, worst historical crisis path, forced-liquidation count, Kelly flag, TFSA feasibility
and the cheapest real-world implementation (tickers, fees, account). If no item at L > 1 is eligible for a
tolerance, say so explicitly. If nothing is eligible, say so. Ties go to the lower leverage.

## 7. Live-era check (descriptive; not used by the answer)

Actual ETFs since inception, in CAD, total return (adjusted close): XEQT, VEQT, XGRO, VGRO, VBAL, XBAL, ZAG, XBB,
VAB, ZGLD/CGL.C/GLD, DBMF, KMLM, CTA, NTSX, RSSB, RSST, GDE, SSO, UPRO, TMF, UBT, SPY, VT, TLT, IEF. CAGR, vol,
Sharpe, max DD, and tracking (correlation, annualised return gap) versus the simulated sleeve / portfolio on the
overlap.

## 8. Data, snapshots, rules

- Every input file is recorded with source URL, retrieval UTC, first/last date and row count, and frozen with
  `python -m research.data_snapshot` (dataset `cycle8_v1`) before the first portfolio return. Blocked or paywalled
  sources are listed for the owner; the sandbox, network and permissions are never changed.
- No crypto, no paid data, no forward-registry writes, no commits/pushes/deletions, no edits to old reports, no
  orders, broker, credential, cron, launchd or sandbox changes.
- Nothing here is a recommendation to trade.
