# Cycle 8 — highest expected return under a drawdown limit (Canadian retail)

> **Framing.** This is portfolio construction from known risk premia, **not alpha research**. No edge is claimed or
> tested. Question: for a Canadian retail investor, which pre-declared portfolio has the highest expected long-run
> return while (a) its Sharpe is ≥ a plain 60/40's and (b) its drawdown risk stays inside a stated tolerance —
> answered at 25%, 35% and 50% so the owner chooses. Research only; **nothing here is a recommendation to trade.**

Run 2026-09-28. Everything is CAD, total return, net of declared fees/costs, pre-income-tax.

## 1. Bottom line

| Tolerance | Preregistered-rule answer | Forward geo. return, median [source range] | Hist. CAGR (window) | Max DD month-end / daily | P(DD > tol, 20 y) | Audit verdict | Robust fallback |
|---|---|---|---|---|---|---|---|
| **25%** | **P4 @ 1.5x** — 60/40 + 10 gold + 10 trend, levered 1.5x (72 eq / 48 bond / 15 gold / 15 trend) | **4.9%** [4.2–5.5] | 11.6% (1985–2026) | 18% / 24% | 3.6% | **SURVIVES** | P4 @ 1.25x (4.8%) if trend's post-2012 premium is the true one |
| **35%** | **P6a @ 1.0x** — 100% global equity + 50% trend overlay | **5.6%** [4.7–6.7] | 16.2% (1985–2026) | 32% / **38%** | 5.7% | **WEAKENED** | **P3 60/40 @ 1.0x (5.2%)** — the answer if trend's premium is haircut ≥ 4–5%/yr |
| **50%** | **P6a @ 1.5x** — 150% equity + 75% trend overlay | **6.0%** [4.6–7.5] | 21.4% (1985–2026) | 47% / **54%** | 8.1% (12-mo blocks 10.2%, 30 y 12.2%) | **FAILS robustness** | P6a @ 1.25x (6.0%, P = 1.9%) holds to a ~6%/yr trend haircut; full haircut → P3 @ 1.0x |

- **Leverage above 1x is eligible at every tolerance** (25%: P4 @ 1.25/1.5, P5 @ 1.25–2.0; 35%: also P4 @ 2.0;
  50%: also P6a @ 1.25/1.5). But every eligible levered item holds **trend**, and trend's historical record is
  AQR's gross TSMOM backtest, which earned **16.1%/yr excess before its 2012 publication and 5.1% after** (gross).
  Without trend, **no levered item is eligible at any tolerance** (all fail the Sharpe hurdle: leverage financed at
  policy + 1.5% lowers Sharpe below 60/40's 0.46).
- **Forward lens is sobering:** no menu item exceeds 7.2% geometric (median CMA); the best is P6b @ 2.0x at 7.2%
  with P(DD > 50%) = 87%. The forward median trend premium is zero after the 2.0% drag, so the trend overlay adds
  **no expected return**, only (historical) drawdown protection.
- **Both P6a answers already breached their tolerance on the daily historical path** (38% vs 35%; 54% vs 50%) —
  the rule scores month-end bootstrap paths; the daily breach is disclosed here, not used to override the rule.
- **The 25% answer's forward return (4.9%) is below plain 60/40's (5.2%)** — the price of a 25% tolerance is lower
  expected return, not higher, because 60/40 itself breaches 25% with P = 27%.

## 2. Preregistration (ledger `research/cycle8_prereg_ledger.md`)

| UTC | Item | SHA-256 |
|---|---|---|
| 2026-09-28T06:41:37Z | `research/cycle8/FRAMEWORK.md` (menu, data, costs, leverage/margin, metrics, answer rule) | `933ec68b5e43…1aa1f` |
| 2026-09-28T07:09:39Z | `research/cycle8/ADDENDUM_1.md` (engine clarifications, data decisions, CMA mapping rules) | `e4b4d089f372…dbda5ce` |
| 2026-09-28T07:09:39Z | engine + runner code (`research/cycle8/engine/*.py`, `run.py`) | `1118dda9ebee…1f7093a` |
| 2026-09-28T07:09:39Z | data snapshot `cycle8_v1` (registered experiment `cycle8_main`) | `207cc70443c4…ab197c21` |
| 2026-09-28T07:10:56Z | `research/cycle8/forward.py` (forward lens + answer rule; hashed after the main run finished, before its outputs were viewed) | `14eab80d84b3…e860053` |

Menu, leverage levels (1.0/1.25/1.5/2.0) and the answer rule were fixed before any return. One run; no reruns.
Engine tests: 9 engine + 5 bond-pricer unit tests pass; smoke-tested on randomised data only before the freeze.

## 3. Data

| Sleeve / input | Source (free) | Span used | Checks vs real products |
|---|---|---|---|
| US equity | Ken French market (Mkt-RF+RF), monthly + daily | 1926-07+ | vs MSCI USA GR corr 0.996, +0.29%/yr |
| Canada equity | Ken French Canada (USD) → XIC splice 2026 | 1977-01+ (US backfill 1971–76) | vs XIC corr 0.995 |
| Dev ex-N. America | Ken French "Major Markets" with Canada backed out; MSCI EAFE splice 2026 | 1975-01+ (US backfill 1971–74) | vs MSCI EAFE GR corr 0.997, +0.10%/yr |
| EM equity | Ken French Emerging | 1989-07+ (dev ex-NA before) | vs MSCI EM GR corr 0.995 |
| USD/CAD | Fed H.10 daily (= FRED DEXCAUS), month-end | 1971-01+ | vs BoC 2017+ diff −0.0001 |
| Canada CPI / US CPI | StatCan 18-10-0004 / BLS API | 1914+ | — |
| Bonds | Par-bond repricing of 10Y yields: Canada (StatCan/BoC splice), US (Shiller → GS10 → DGS10) | CA 1936+, US 1871+ | US10 vs IEF corr 0.99; CA10 vs XBB corr 0.87 (duration/credit mismatch); 2022: sim −13.2% vs XBB −11.7% |
| 20Y Treasury (P7) | DGS20 daily (DGS30 in gap) | 1962+ | vs TLT corr 0.95, gap −0.01%/yr |
| CAD T-bill, policy rate | StatCan/BoC (Bank Rate → overnight target 1996) | 1934+ | — |
| Gold | World Bank monthly **average** → COMEX month-end from 2000-08 | 1960+ | vs GLD corr 0.99, gap ≈ fee |
| Trend | AQR TSMOM factor (gross) − 2.0%/yr drag + T-bill | 1985-01..2026-05 | sleeve vs AQMIX (2010+) −0.5%/yr, corr 0.85; vs DBMF −5.5, KMLM +2.0, CTA −4.2 %/yr |
| Retail ETFs | Yahoo adjusted close (58 tickers) | inception+ | §8 |
| Forward CMAs | FP Canada PAG 2026, J.P. Morgan LTCMA 2026 (CAD), Vanguard VCMM (2026-06), AQR 2026, BlackRock (Aug 2026) | — | `data/cycle8/cma/` with URLs and raw copies |

Crises covered: 1973–74, 1979–81, 1987, 2000–02, 2008, 2020, 2022 (CAD windows); 1929–32 and 1937–38 in the USD
supplement. Trend-holding items (P4, P5, P6a) start 1985 (P5 1988) — they **miss 1973–74 and 1979–81**.

**Blocked / unavailable (owner list):** Research Affiliates AAI (needs terms acceptance); AQR "Century of Evidence"
trend series (not published as data); LBMA/Bundesbank/WGC gold fixes (404 / registration) — no free month-end gold
before 2000-08; datahub daily gold (404); Stooq (bot check); MSCI API before 2000; Vanguard Canada return ranges
(503); BLS flat files (403, API used); SG CTA / BarclayHedge (paid); no free daily EAFE/EM before 2001 or daily
Canada 10Y before 2001; FRED intermittently unreachable (Fed H.10 used); LSE Terminal not running (not used).

## 4. Every portfolio × leverage — historical (CAD, own window)

Sharpe is over CAD T-bill with the A4 calibrated 95% CI. "P3 hurdle" = 60/40 1.0x Sharpe on the same window.
Max DD month-end / daily (daily path reconstructed per ADDENDUM_1 §1).

| Item | Window | CAGR | Real CAGR | Vol | Sharpe [95% CI] | P3 hurdle | MaxDD m-end / daily | Underwater (mo) | Worst 12m | Ulcer | Margin calls |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P1u@1.0 | 1971-02..2026-08 | 10.6 | 6.5 | 13.0 | 0.44 [0.12, 0.73] | 0.46 | 48 / 50 | 73 | -42.7 | 12.0 | 0 |
| P1u@1.25 | 1971-02..2026-08 | 11.6 | 7.4 | 16.3 | 0.43 [0.11, 0.72] | 0.46 | 57 / 59 | 75 | -51.5 | 16.1 | 0 |
| P1u@1.5 | 1971-02..2026-08 | 12.1 | 7.9 | 19.5 | 0.41 [0.10, 0.70] | 0.46 | 65 / 67 | 152 | -59.4 | 20.7 | 0 |
| P1u@2.0 | 1971-02..2026-08 | 12.7 | 8.5 | 26.0 | 0.39 [0.08, 0.67] | 0.46 | 78 / 79 | 164 | -71.8 | 31.3 | 0 |
| P1h@1.0 | 1971-02..2026-08 | 10.9 | 6.7 | 14.5 | 0.42 [0.17, 0.65] | 0.46 | 50 / 54 | 62 | -43.8 | 12.3 | 0 |
| P1h@1.25 | 1971-02..2026-08 | 11.8 | 7.6 | 18.2 | 0.42 [0.17, 0.65] | 0.46 | 59 / 63 | 64 | -52.4 | 16.1 | 0 |
| P1h@1.5 | 1971-02..2026-08 | 12.2 | 8.0 | 21.8 | 0.40 [0.15, 0.63] | 0.46 | 67 / 71 | 69 | -60.1 | 20.3 | 0 |
| P1h@2.0 | 1971-02..2026-08 | 12.5 | 8.3 | 29.2 | 0.37 [0.13, 0.61] | 0.46 | 81 / 84 | 79 | -74.5 | 29.1 | 1 |
| P2@1.0 | 1971-02..2026-08 | 10.0 | 5.9 | 10.8 | 0.45 [0.14, 0.74] | 0.46 | 40 / 42 | 63 | -35.9 | 8.6 | 0 |
| P2@1.25 | 1971-02..2026-08 | 10.8 | 6.7 | 13.4 | 0.44 [0.13, 0.72] | 0.46 | 49 / 51 | 66 | -44.2 | 11.7 | 0 |
| P2@1.5 | 1971-02..2026-08 | 11.3 | 7.1 | 16.1 | 0.42 [0.11, 0.70] | 0.46 | 58 / 59 | 74 | -51.6 | 15.2 | 0 |
| P2@2.0 | 1971-02..2026-08 | 12.0 | 7.8 | 21.5 | 0.39 [0.08, 0.67] | 0.46 | 70 / 72 | 76 | -64.0 | 22.6 | 0 |
| P3@1.0 | 1971-02..2026-08 | 9.3 | 5.2 | 8.8 | 0.46 [0.17, 0.75] | 0.46 | 32 / 34 | 44 | -28.6 | 5.7 | 0 |
| P3@1.25 | 1971-02..2026-08 | 9.9 | 5.8 | 11.0 | 0.44 [0.15, 0.73] | 0.46 | 41 / 42 | 52 | -35.9 | 8.0 | 0 |
| P3@1.5 | 1971-02..2026-08 | 10.3 | 6.2 | 13.2 | 0.41 [0.12, 0.70] | 0.46 | 48 / 50 | 58 | -42.7 | 10.6 | 0 |
| P3@2.0 | 1971-02..2026-08 | 10.9 | 6.8 | 17.6 | 0.38 [0.09, 0.66] | 0.46 | 61 / 63 | 67 | -54.5 | 16.0 | 0 |
| P4@1.0 | 1985-01..2026-05 | 9.6 | 7.0 | 6.8 | 0.81 [0.42, 1.17] | 0.64 | 11 / 16 | 37 | -7.6 | 2.6 | 0 |
| P4@1.25 | 1985-01..2026-05 | 10.7 | 8.0 | 8.4 | 0.78 [0.39, 1.14] | 0.64 | 15 / 20 | 39 | -10.3 | 3.9 | 0 |
| P4@1.5 | 1985-01..2026-05 | 11.6 | 8.9 | 10.1 | 0.75 [0.36, 1.11] | 0.64 | 18 / 23 | 40 | -14.0 | 5.3 | 0 |
| P4@2.0 | 1985-01..2026-05 | 13.3 | 10.6 | 13.5 | 0.70 [0.32, 1.06] | 0.64 | 26 / 32 | 51 | -21.6 | 8.6 | 0 |
| P5@1.0 | 1988-01..2026-05 | 8.5 | 6.0 | 5.9 | 0.80 [0.57, 1.02] | 0.61 | 9 / 11 | 39 | -4.5 | 2.1 | 0 |
| P5@1.25 | 1988-01..2026-05 | 9.3 | 6.8 | 7.3 | 0.75 [0.53, 0.98] | 0.61 | 11 / 15 | 42 | -6.0 | 3.0 | 0 |
| P5@1.5 | 1988-01..2026-05 | 10.0 | 7.5 | 8.8 | 0.72 [0.49, 0.94] | 0.61 | 14 / 18 | 43 | -7.6 | 3.9 | 0 |
| P5@2.0 | 1988-01..2026-05 | 11.4 | 8.8 | 11.7 | 0.67 [0.44, 0.89] | 0.61 | 20 / 24 | 45 | -10.8 | 5.9 | 0 |
| P6a@1.0 | 1985-01..2026-05 | 16.2 | 13.4 | 13.6 | 0.89 [0.48, 1.28] | 0.64 | 32 / 38 | 41 | -25.1 | 7.8 | 0 |
| P6a@1.25 | 1985-01..2026-05 | 19.0 | 16.1 | 16.9 | 0.88 [0.47, 1.27] | 0.64 | 40 / 46 | 43 | -31.3 | 10.4 | 0 |
| P6a@1.5 | 1985-01..2026-05 | 21.4 | 18.4 | 20.3 | 0.87 [0.45, 1.25] | 0.64 | 47 / 54 | 44 | -37.3 | 13.1 | 0 |
| P6a@2.0 | 1985-01..2026-05 | 25.7 | 22.6 | 27.1 | 0.84 [0.43, 1.23] | 0.64 | 59 / 66 | 68 | -48.2 | 19.0 | 1 |
| P6b@1.0 | 1971-02..2026-08 | 11.3 | 7.2 | 14.1 | 0.46 [0.16, 0.76] | 0.46 | 51 / 53 | 58 | -45.4 | 11.5 | 0 |
| P6b@1.25 | 1971-02..2026-08 | 12.4 | 8.2 | 17.6 | 0.45 [0.15, 0.75] | 0.46 | 61 / 62 | 65 | -54.4 | 15.4 | 0 |
| P6b@1.5 | 1971-02..2026-08 | 13.0 | 8.8 | 21.2 | 0.44 [0.14, 0.73] | 0.46 | 69 / 70 | 73 | -62.3 | 19.7 | 0 |
| P6b@2.0 | 1971-02..2026-08 | 13.7 | 9.4 | 28.3 | 0.41 [0.11, 0.70] | 0.46 | 81 / 82 | 89 | -74.6 | 28.8 | 1 |
| P8@1.0 | 1971-02..2026-08 | 5.4 | 1.5 | 1.2 | 0.05 [-0.30, 0.37] | 0.46 | 0 / 0 | 0 | 0.1 | 0.0 | 0 |
| P7-2x@1.0 | 1971-02..2026-08 | 13.2 | 8.9 | 20.3 | 0.45 [0.09, 0.77] | 0.46 | 61 / 63 | 135 | -54.9 | 17.4 | 0 |
| P7-3x@1.0 | 1971-02..2026-08 | 15.5 | 11.2 | 30.9 | 0.45 [0.12, 0.75] | 0.46 | 78 / 79 | 148 | -70.9 | 28.3 | 0 |

## 5. Drawdown probability, Kelly and forward lens

Stationary block bootstrap of the joint monthly sleeve/rate vector, 24-month mean blocks, 10,000 paths, 20-year
horizon unless stated. Kelly L* = growth-optimal margin leverage of the 1.0x item (bootstrap median [5th pct]);
"Imprudent" = L above half-Kelly. Forward geo = median-CMA geometric expected return (%/yr, CAD, after fees,
financing, WHT); range = min–max across the five sources. Ranks over all 35 rows.

| Item | P(DD>25%) | P(DD>35%) | P(DD>50%) | P(>35%) 12m blk | P(>35%) 10y / 30y | Kelly L* med [p05] | Half-Kelly | Imprudent | Fwd geo (median) | Fwd range | Hist rank | Fwd rank | Eligible 25/35/50 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P1u@1.0 | 75.3 | 56.4 | 7.3 | 46.5 | 32 / 72 | 2.4 [0.5] | 1.20 | no | 5.74 | 4.8–6.8 | 26 | 17 | ·/·/· |
| P1u@1.25 | 92.7 | 70.6 | 33.4 | 67.4 | 45 / 85 | 2.4 [0.5] | 1.20 | YES | 6.10 | 5.0–7.4 | 18 | 8 | ·/·/· |
| P1u@1.5 | 98.7 | 89.5 | 59.1 | 86.1 | 66 / 97 | 2.4 [0.5] | 1.20 | YES | 6.20 | 4.8–7.7 | 14 | 6 | ·/·/· |
| P1u@2.0 | 99.9 | 97.7 | 83.2 | 96.8 | 84 / 100 | 2.4 [0.5] | 1.20 | YES | 6.13 | 4.3–8.3 | 10 | 7 | ·/·/· |
| P1h@1.0 | 76.3 | 60.9 | 23.9 | 53.8 | 36 / 76 | 2.1 [0.6] | 1.07 | no | 5.37 | 4.5–6.4 | 23 | 24 | ·/·/· |
| P1h@1.25 | 97.2 | 72.5 | 54.9 | 70.8 | 47 / 86 | 2.1 [0.6] | 1.07 | YES | 5.56 | 4.4–6.8 | 16 | 20 | ·/·/· |
| P1h@1.5 | 99.6 | 90.6 | 63.1 | 88.7 | 68 / 97 | 2.1 [0.6] | 1.07 | YES | 5.44 | 4.1–7.0 | 13 | 23 | ·/·/· |
| P1h@2.0 | 100.0 | 99.6 | 82.7 | 99.2 | 93 / 100 | 2.1 [0.6] | 1.07 | YES | 4.85 | 3.0–7.1 | 11 | 28 | ·/·/· |
| P2@1.0 | 61.8 | 26.9 | 1.2 | 21.7 | 14 / 39 | 2.8 [0.5] | 1.38 | no | 5.53 | 4.8–6.3 | 28 | 21 | ·/·/· |
| P2@1.25 | 74.3 | 57.0 | 7.5 | 47.6 | 33 / 73 | 2.8 [0.5] | 1.38 | no | 5.87 | 5.0–6.9 | 24 | 13 | ·/·/· |
| P2@1.5 | 96.3 | 67.4 | 30.0 | 63.9 | 41 / 82 | 2.8 [0.5] | 1.38 | YES | 6.00 | 4.9–7.2 | 21 | 10 | ·/·/· |
| P2@2.0 | 98.5 | 93.6 | 64.0 | 91.2 | 74 / 98 | 2.8 [0.5] | 1.38 | YES | 6.10 | 4.7–7.7 | 15 | 9 | ·/·/· |
| P3@1.0 | 27.1 | 2.4 | 0.1 | 2.8 | 1 / 4 | 3.0 [0.3] | 1.52 | no | 5.25 | 4.7–5.8 | 32 | 25 | ·/Y/Y |
| P3@1.25 | 58.1 | 24.9 | 0.9 | 19.4 | 13 / 36 | 3.0 [0.3] | 1.52 | no | 5.52 | 4.9–6.2 | 30 | 22 | ·/·/· |
| P3@1.5 | 77.7 | 35.9 | 5.1 | 34.6 | 19 / 50 | 3.0 [0.3] | 1.52 | no | 5.65 | 4.9–6.5 | 27 | 18 | ·/·/· |
| P3@2.0 | 97.0 | 71.1 | 32.0 | 68.9 | 44 / 85 | 3.0 [0.3] | 1.52 | YES | 5.80 | 4.8–6.9 | 22 | 15 | ·/·/· |
| P4@1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 / 0 | 8.4 [4.0] | 4.22 | no | 4.70 | 4.3–5.2 | 31 | 30 | Y/Y/Y |
| P4@1.25 | 0.3 | 0.0 | 0.0 | 0.0 | 0 / 0 | 8.4 [4.0] | 4.22 | no | 4.84 | 4.3–5.4 | 25 | 29 | Y/Y/Y |
| P4@1.5 | 3.6 | 0.1 | 0.0 | 0.2 | 0 / 0 | 8.4 [4.0] | 4.22 | no | 4.88 | 4.2–5.5 | 17 | 26 | Y/Y/Y |
| P4@2.0 | 42.9 | 4.8 | 0.1 | 6.5 | 2 / 8 | 8.4 [4.0] | 4.22 | no | 4.86 | 4.0–5.7 | 7 | 27 | ·/Y/Y |
| P5@1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 / 0 | 9.1 [5.4] | 4.53 | no | 3.81 | 3.5–4.5 | 34 | 31 | Y/Y/Y |
| P5@1.25 | 0.0 | 0.0 | 0.0 | 0.0 | 0 / 0 | 9.1 [5.4] | 4.53 | no | 3.68 | 3.4–4.6 | 33 | 32 | Y/Y/Y |
| P5@1.5 | 0.1 | 0.0 | 0.0 | 0.0 | 0 / 0 | 9.1 [5.4] | 4.53 | no | 3.49 | 3.2–4.6 | 29 | 33 | Y/Y/Y |
| P5@2.0 | 5.5 | 0.2 | 0.0 | 0.4 | 0 / 0 | 9.1 [5.4] | 4.53 | no | 3.03 | 2.7–4.5 | 19 | 34 | Y/Y/Y |
| P6a@1.0 | 66.6 | 5.7 | 0.1 | 7.5 | 3 / 9 | 5.7 [3.6] | 2.85 | no | 5.65 | 4.7–6.7 | 4 | 19 | ·/Y/Y |
| P6a@1.25 | 79.0 | 38.9 | 1.9 | 36.4 | 20 / 52 | 5.7 [3.6] | 2.85 | no | 5.96 | 4.8–7.2 | 3 | 12 | ·/·/Y |
| P6a@1.5 | 89.3 | 73.9 | 8.1 | 67.7 | 47 / 87 | 5.7 [3.6] | 2.85 | no | 5.99 | 4.6–7.5 | 2 | 11 | ·/·/Y |
| P6a@2.0 | 97.0 | 82.9 | 66.5 | 82.0 | 58 / 93 | 5.7 [3.6] | 2.85 | no | 5.75 | 3.9–8.0 | 1 | 16 | ·/·/· |
| P6b@1.0 | 81.7 | 54.8 | 17.4 | 45.9 | 30 / 70 | 2.4 [0.7] | 1.21 | no | 6.36 | 5.5–7.3 | 20 | 4 | ·/·/· |
| P6b@1.25 | 97.1 | 69.9 | 30.9 | 67.5 | 44 / 84 | 2.4 [0.7] | 1.21 | YES | 6.85 | 5.7–8.0 | 12 | 3 | ·/·/· |
| P6b@1.5 | 98.5 | 95.2 | 58.1 | 91.2 | 77 / 99 | 2.4 [0.7] | 1.21 | YES | 7.06 | 5.7–8.5 | 9 | 2 | ·/·/· |
| P6b@2.0 | 99.9 | 98.2 | 87.1 | 97.7 | 86 / 100 | 2.4 [0.7] | 1.21 | YES | 7.19 | 5.4–9.0 | 6 | 1 | ·/·/· |
| P8@1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 / 0 | n/a | n/a | — | 2.80 | 2.4–2.8 | 35 | 35 | ·/·/· |
| P7-2x@1.0 | 96.7 | 80.2 | 35.2 | 76.5 | 54 / 92 | 1.8 [0.6] | 0.90 | YES | 5.86 | — | 8 | 14 | ·/·/· |
| P7-3x@1.0 | 99.9 | 98.7 | 83.4 | 98.3 | 89 / 100 | 1.3 [0.5] | 0.64 | YES | 6.26 | — | 5 | 5 | ·/·/· |

**Sensitivities** (W_COMMON = 1988-01..2026-05, identical months for all items; margin at policy + 3.0%):

| Item | Common CAGR | Common Sharpe | Common MaxDD | Margin +3.0%: CAGR | Sharpe | P(DD>35%) | P(DD>50%) |
|---|---|---|---|---|---|---|---|
| P1u@1.0 | 9.7 | 0.54 | 41.0 | — | — | — | — |
| P1u@1.25 | 10.9 | 0.53 | 49.7 | 11.1 | 0.41 | 71.1 | 39.5 |
| P1u@1.5 | 11.7 | 0.51 | 57.9 | 11.2 | 0.37 | 90.4 | 59.9 |
| P1u@2.0 | 13.0 | 0.48 | 74.4 | 11.0 | 0.33 | 98.0 | 84.9 |
| P1h@1.0 | 10.0 | 0.50 | 50.4 | — | — | — | — |
| P1h@1.25 | 11.2 | 0.49 | 59.5 | 11.4 | 0.40 | 73.3 | 55.1 |
| P1h@1.5 | 11.9 | 0.48 | 67.3 | 11.4 | 0.36 | 91.3 | 63.9 |
| P1h@2.0 | 12.8 | 0.45 | 80.6 | 10.8 | 0.32 | 99.7 | 83.7 |
| P2@1.0 | 9.1 | 0.57 | 31.4 | — | — | — | — |
| P2@1.25 | 10.1 | 0.56 | 39.0 | 10.4 | 0.41 | 58.0 | 8.3 |
| P2@1.5 | 10.9 | 0.53 | 46.1 | 10.5 | 0.37 | 68.5 | 31.6 |
| P2@2.0 | 12.2 | 0.51 | 58.9 | 10.3 | 0.32 | 96.4 | 66.6 |
| P3@1.0 | 8.4 | 0.61 | 20.9 | — | — | — | — |
| P3@1.25 | 9.2 | 0.58 | 26.9 | 9.5 | 0.40 | 25.3 | 1.0 |
| P3@1.5 | 9.9 | 0.56 | 32.8 | 9.5 | 0.35 | 38.1 | 6.2 |
| P3@2.0 | 11.1 | 0.52 | 43.8 | 9.3 | 0.29 | 79.1 | 35.0 |
| P4@1.0 | 8.8 | 0.78 | 10.9 | — | — | — | — |
| P4@1.25 | 9.7 | 0.74 | 13.6 | 10.3 | 0.73 | 0.0 | 0.0 |
| P4@1.5 | 10.5 | 0.71 | 17.4 | 10.8 | 0.67 | 0.2 | 0.0 |
| P4@2.0 | 12.1 | 0.67 | 26.2 | 11.7 | 0.59 | 8.7 | 0.3 |
| P5@1.0 | 8.5 | 0.80 | 8.7 | — | — | — | — |
| P5@1.25 | 9.3 | 0.75 | 11.5 | 8.8 | 0.70 | 0.0 | 0.0 |
| P5@1.5 | 10.0 | 0.72 | 14.3 | 9.2 | 0.63 | 0.0 | 0.0 |
| P5@2.0 | 11.4 | 0.67 | 19.8 | 9.7 | 0.54 | 0.7 | 0.0 |
| P6a@1.0 | 14.9 | 0.88 | 32.0 | — | — | — | — |
| P6a@1.25 | 17.4 | 0.87 | 39.7 | 18.5 | 0.86 | 39.7 | 2.2 |
| P6a@1.5 | 19.6 | 0.85 | 47.0 | 20.5 | 0.83 | 74.3 | 9.0 |
| P6a@2.0 | 23.7 | 0.83 | 59.5 | 23.8 | 0.79 | 84.0 | 72.4 |
| P6b@1.0 | 10.9 | 0.60 | 36.5 | — | — | — | — |
| P6b@1.25 | 12.3 | 0.59 | 44.9 | 12.0 | 0.43 | 70.5 | 31.6 |
| P6b@1.5 | 13.4 | 0.57 | 52.7 | 12.2 | 0.40 | 95.3 | 59.8 |
| P6b@2.0 | 15.2 | 0.55 | 65.6 | 12.0 | 0.36 | 98.4 | 88.7 |
| P8@1.0 | 3.7 | -0.13 | 0.0 | — | — | — | — |
| P7-2x@1.0 | 14.0 | 0.62 | 49.2 | — | — | — | — |
| P7-3x@1.0 | 17.6 | 0.60 | 72.7 | — | — | — | — |

## 6. Crisis table (cumulative return % / in-window max DD %)

| Item | 1973-74 oil/inflation | 1979-81 Volcker | 1987 crash | 2000-02 dot-com | 2007-09 GFC | 2020 COVID | 2022 stocks+bonds |
|---|---|---|---|---|---|---|---|
| P1u@1.0 | -43 / 48 | 17 / 14 | -18 / 25 | -39 / 39 | -39 / 39 | -17 / 17 | -14 / 19 |
| P1u@1.25 | -53 / 57 | 13 / 19 | -24 / 31 | -47 / 47 | -47 / 47 | -21 / 21 | -18 / 23 |
| P1u@1.5 | -61 / 65 | 7 / 25 | -29 / 37 | -55 / 55 | -54 / 54 | -25 / 25 | -22 / 28 |
| P1u@2.0 | -75 / 78 | -5 / 36 | -40 / 49 | -68 / 68 | -66 / 66 | -33 / 33 | -29 / 36 |
| P1h@1.0 | -43 / 48 | 18 / 13 | -16 / 24 | -42 / 42 | -50 / 50 | -21 / 21 | -18 / 23 |
| P1h@1.25 | -53 / 58 | 13 / 18 | -21 / 30 | -51 / 51 | -59 / 59 | -26 / 26 | -23 / 28 |
| P1h@1.5 | -62 / 66 | 7 / 23 | -27 / 36 | -59 / 59 | -67 / 67 | -31 / 31 | -27 / 34 |
| P1h@2.0 | -75 / 78 | -5 / 34 | -37 / 47 | -72 / 72 | -81 / 81 | -40 / 40 | -36 / 43 |
| P2@1.0 | -34 / 40 | 12 / 12 | -14 / 20 | -29 / 29 | -30 / 30 | -12 / 12 | -14 / 18 |
| P2@1.25 | -44 / 49 | 6 / 17 | -18 / 25 | -37 / 37 | -37 / 37 | -16 / 16 | -18 / 22 |
| P2@1.5 | -52 / 58 | -0 / 23 | -22 / 30 | -44 / 44 | -44 / 44 | -19 / 19 | -22 / 27 |
| P2@2.0 | -66 / 70 | -13 / 34 | -31 / 39 | -56 / 56 | -55 / 55 | -25 / 25 | -29 / 35 |
| P3@1.0 | -25 / 32 | 6 / 11 | -9 / 14 | -18 / 18 | -20 / 21 | -8 / 8 | -14 / 17 |
| P3@1.25 | -34 / 41 | -1 / 16 | -12 / 18 | -24 / 24 | -26 / 26 | -10 / 10 | -18 / 21 |
| P3@1.5 | -42 / 48 | -8 / 22 | -16 / 22 | -30 / 30 | -31 / 32 | -12 / 12 | -22 / 25 |
| P3@2.0 | -55 / 61 | -21 / 32 | -22 / 29 | -40 / 40 | -41 / 42 | -16 / 16 | -29 / 33 |
| P4@1.0 | n/a | n/a | -7 / 11 | -7 / 8 | -6 / 10 | -4 / 4 | -9 / 11 |
| P4@1.25 | n/a | n/a | -10 / 15 | -12 / 12 | -9 / 13 | -5 / 5 | -11 / 14 |
| P4@1.5 | n/a | n/a | -12 / 18 | -16 / 16 | -12 / 15 | -6 / 6 | -14 / 16 |
| P4@2.0 | n/a | n/a | -18 / 24 | -23 / 23 | -18 / 21 | -8 / 8 | -19 / 22 |
| P5@1.0 | n/a | n/a | n/a | 18 / 2 | 16 / 3 | 3 / 0 | -5 / 6 |
| P5@1.25 | n/a | n/a | n/a | 20 / 3 | 18 / 5 | 3 / 0 | -7 / 8 |
| P5@1.5 | n/a | n/a | n/a | 22 / 4 | 21 / 6 | 4 / 1 | -9 / 9 |
| P5@2.0 | n/a | n/a | n/a | 25 / 6 | 25 / 9 | 5 / 1 | -12 / 13 |
| P6a@1.0 | n/a | n/a | -19 / 27 | -24 / 24 | -30 / 30 | -12 / 12 | -1 / 11 |
| P6a@1.25 | n/a | n/a | -26 / 34 | -31 / 31 | -37 / 37 | -15 / 15 | -2 / 14 |
| P6a@1.5 | n/a | n/a | -32 / 41 | -38 / 38 | -44 / 44 | -18 / 18 | -3 / 17 |
| P6a@2.0 | n/a | n/a | -46 / 55 | -50 / 50 | -56 / 56 | -24 / 24 | -6 / 22 |
| P6b@1.0 | -44 / 51 | -4 / 22 | -18 / 24 | -34 / 34 | -35 / 35 | -14 / 14 | -22 / 25 |
| P6b@1.25 | -54 / 61 | -13 / 30 | -23 / 30 | -42 / 42 | -42 / 43 | -18 / 18 | -27 / 31 |
| P6b@1.5 | -63 / 69 | -22 / 37 | -28 / 36 | -50 / 50 | -50 / 50 | -21 / 21 | -32 / 37 |
| P6b@2.0 | -76 / 81 | -39 / 50 | -41 / 49 | -62 / 62 | -62 / 62 | -28 / 28 | -42 / 47 |
| P8@1.0 | 14 / 0 | 34 / 0 | 4 / 0 | 8 / 0 | 3 / 0 | 0 / 0 | 1 / 0 |
| P7-2x@1.0 | -55 / 61 | -18 / 32 | -26 / 34 | -41 / 41 | -40 / 42 | -13 / 13 | -40 / 43 |
| P7-3x@1.0 | -72 / 77 | -38 / 49 | -37 / 46 | -60 / 60 | -65 / 66 | -25 / 25 | -57 / 60 |

Traceback (most recent call last):
  File "<stdin>", line 29, in <module>
AttributeError: 'function' object has no attribute 'map'

## 7. Expected return: historical vs forward

**Historical haircut by sleeve** (arithmetic %/yr, net of fees; forward = median CMA):

| Sleeve | From | Hist. return | Forward | Haircut | Hist. excess over cash | Fwd excess | Excess haircut |
|---|---|---|---|---|---|---|---|
| EQ_G (TFSA) | 1971-02 | 11.0 | 6.6 | 4.4 | 5.7 | 3.8 | 1.9 |
| BOND | 1971-02 | 6.9 | 4.2 | 2.7 | 1.6 | 1.4 | 0.2 |
| GOLD | 1971-02 | 10.5 | 1.9 | 8.6 | 5.2 | −0.9 | 6.1 |
| TREND | 1985-01 | 13.9 | 2.8 | 11.1 | 9.8 | 0.0 | 9.8 |
| CASH | 1971-02 | 5.3 | 2.8 | 2.5 | 0.0 | 0.0 | 0.0 |

- **Ranking flips.** Historical top 6: P6a @ 2.0/1.5/1.25/1.0, P6b @ 2.0, P4 @ 2.0 (trend-stacked wins). Forward
  top 6: P6b @ 2.0/1.5/1.25/1.0, P1u @ 1.5/2.0 (bond-stacked equity wins). Spearman between the two rankings over
  the 32 answer rows: 0.52. The flip is almost entirely trend: +9.8%/yr historical excess vs 0 forward.
- **Why the history is optimistic:** trend's history is a pre-publication gross backtest (16.1% vs 5.1% gross
  excess before/after 2012); gold's 1971–2026 record includes the end of Bretton Woods and 2024–26; bonds ran a
  40-year yield decline from 1981; equity includes the US-led 2009–2026 run. Cash itself fell from 5.3% to 2.8%.
- **Forward lens caveat:** portfolio σ uses W_COMMON history; trend and gold forward values are fallbacks (only JPM
  publishes gold; no source publishes trend); BlackRock is the high equity source (7.9%), Vanguard the low (5.9%).

## 8. Three-tolerance answer — detail

| | 25% → P4 @ 1.5x | 35% → P6a @ 1.0x | 50% → P6a @ 1.5x |
|---|---|---|---|
| Exposures (% of NAV) | 72 global eq, 48 bonds, 15 gold, 15 trend (gross 150) | 100 global eq + 50 trend overlay (gross 150) | 150 global eq + 75 trend overlay (gross 225) |
| Forward geometric, median [range] | 4.9 [4.2–5.5] | 5.6 [4.7–6.7] | 6.0 [4.6–7.5] |
| Forward arithmetic / σ | 5.3 / 9.7% | 6.4 / 12.6% | 7.8 / 18.9% |
| Historical CAGR / real / Sharpe | 11.6 / 8.9 / 0.75 (hurdle 0.64) | 16.2 / 13.4 / 0.89 (0.64) | 21.4 / 18.4 / 0.87 (0.64) |
| P(DD > tol) 20 y / 12-mo blocks / 30 y | 3.6 / 5.5 / 5.7% | 5.7 / 7.6 / 8.7% | 8.1 / **10.2 / 12.2%** |
| Max DD month-end / daily | 18 / 24% | 32 / **38%** | 47 / **54%** |
| Worst historical crisis | 2000–02: −16%; 1987: −12% (daily DD 24%) | 2008 GFC: −30%; 1987: −19% (−27% DD) | 2008 GFC: −44%; 1987: −32% (−41% DD) |
| Longest underwater | 40 months | 41 months | 44 months |
| Margin calls (daily, 30% maint.) | 0 | 0 | 0 |
| Kelly (half-Kelly) | 4.2 → 1.5x prudent | 2.9 → prudent | 2.9 → prudent |
| Trend haircut that flips it | Sharpe misses by 0.004 only at the full 7.2%/yr haircut | 4–5%/yr | 1.5–2%/yr |
| TFSA-feasible? | **Approximately** (US-listed capital-efficient ETFs, US-equity tilt) | **Yes, approximately** | **Only with daily-reset 3x ETFs** |
| Cheapest implementation (approx.) | TFSA: 21.7% RSSB + 15% RSST + 16.7% GDE + 26.3% ZAG + 20.3% XEQT (ER ≈ 0.33% + embedded financing). Margin acct: XEQT 72 / ZAG 48 / ZGLD 15 / DBMF 15 on 50% loan at policy + 1.5% | TFSA: 50% XEQT + 50% RSST (ER ≈ 0.60%; equity 50 global + 50 US). Margin route (XEQT + DBMF on margin) costs ~0.75%/yr more | Margin acct: 75% XEQT + 75% RSST on a 50% loan (ER ≈ 0.89% + loan). TFSA: 75% RSST + 25% UPRO (US-only, 3x daily reset) |
| Audit verdict | **SURVIVES** | **WEAKENED** | **FAILS robustness** |

ETF ERs are Yahoo-reported (verify before use); US-listed ETFs in a TFSA lose 15% US withholding on dividends and
need CAD→USD conversion (Norbert's gambit). RSST's trend leg is ReSolve's strategy, not AQR's; RSST has 34 months
of history. Live check of "equity + 50% trend" with real ETFs (audit): XEQT + 0.5×(DBMF − T-bill) 2019-10..2026-05
CAGR 17.9% vs simulated 15.3%, max DD 18.0% vs 12.3%; with KMLM 16.4% vs 16.9%.

**Is anything eligible at > 1x?** Yes at all three tolerances — but only items holding trend. Take trend away (or
haircut it to its post-2012 level) and the answers become: 25% → P4 @ 1.25x (still trend-holding); 35% → P3 60/40 @ 1.0x; 50% → P3 60/40 @ 1.0x. **No leveraged stock/bond-only portfolio beats 60/40's
Sharpe once financing is at retail margin rates.**

## 9. What would 12%/yr require?

Historically, 12%+ CAGR in CAD came from P1u @ 1.5–2x, P6b @ 1.25–2x, P4 @ 2x and P6a at any leverage — with month-end
drawdowns of 26–81% and bootstrap odds of a >35% drawdown within 20 years of 70–100% for everything except the
trend-holding items. Forward, **nothing on the menu gets there**: the median CMA puts global equity at ~6.8%
arithmetic and cash at 2.8%, so each extra 1x of equity bought with margin at policy + 1.5% adds only ~2.3%
arithmetic while volatility drag grows with the square of leverage — levered global equity peaks at about 6.2%
geometric near 1.5x and falls beyond it. The best forward item is P6b @ 2.0x at 7.2% (range 5.4–9.0%) with an 87%
chance of a >50% drawdown in 20 years. **Plainly: a 12%/yr expectation needs either the 1985–2011 trend record or
the 1982–2021 US equity/bond bull market to repeat, plus ~2x leverage — and the cost is a likely 60–80% drawdown
(US 1929–32: a 2x 60/40 lost 90%, 2x equity 99%) and years underwater.** On today's published assumptions, 12% is
not a risk-premium outcome; it would be a bet on history repeating.

## 10. Live-era check (actual ETFs, CAD, since inception)

| Item | Ccy | Yahoo ER % | From | CAGR CAD | Vol | Sharpe | MaxDD | Sim comparator | Gap ETF−sim | Corr |
|---|---|---|---|---|---|---|---|---|---|---|
| XEQT.TO | CAD | 0.2 | 2019-10 | 14.5 | 12.8 | 0.94 | 17.6 | P1u@1.0 | -0.1 | 1.00 |
| VEQT.TO | CAD | 0.22 | 2019-04 | 13.9 | 12.6 | 0.92 | 17.9 | P1u@1.0 | -0.1 | 0.99 |
| ZEQT.TO | CAD | 0.2 | 2022-04 | 15.3 | 11.6 | 1.0 | 13.8 | P1u@1.0 | -0.1 | 0.99 |
| XGRO.TO | CAD | 0.2 | 2018-09 | 10.7 | 10.9 | 0.79 | 16.4 | P2@1.0 | 0.3 | 0.99 |
| VGRO.TO | CAD | 0.22 | 2018-04 | 10.6 | 10.6 | 0.8 | 16.1 | P2@1.0 | 0.0 | 0.99 |
| VBAL.TO | CAD | 0.22 | 2018-04 | 8.2 | 8.8 | 0.7 | 15.0 | P3@1.0 | 0.2 | 0.98 |
| XBAL.TO | CAD | 0.19 | 2018-09 | 8.8 | 9.0 | 0.73 | 15.2 | P3@1.0 | 0.8 | 0.98 |
| ZAG.TO | CAD | 0.09 | 2010-03 | 2.7 | 4.8 | 0.26 | 16.1 | BOND | 0.7 | 0.86 |
| XBB.TO | CAD | 0.1 | 2001-01 | 3.7 | 4.7 | 0.37 | 15.6 | BOND | 0.3 | 0.86 |
| VAB.TO | CAD | 0.09 | 2012-03 | 2.1 | 5.1 | 0.12 | 16.0 | BOND | 1.2 | 0.86 |
| CGL-C.TO | CAD | 0.55 | 2012-03 | 8.8 | 15.4 | 0.52 | 27.6 | GOLD | -0.4 | 0.99 |
| ZGLD.TO | CAD | 0.22 | 2024-05 | 32.8 | 18.8 | 1.46 | 21.1 | GOLD | -0.3 | 0.97 |
| GLD | USD | 0.4 | 2005-01 | 11.6 | 16.5 | 0.64 | 29.0 | GOLD | -0.2 | 0.99 |
| DBMF | USD | 0.85 | 2019-07 | 10.0 | 13.3 | 0.6 | 19.3 | TREND | 5.5 | 0.72 |
| KMLM | USD | 0.9 | 2021-02 | 7.4 | 15.0 | 0.36 | 26.0 | TREND | -2.0 | 0.73 |
| CTA | USD | 0.75 | 2022-05 | 9.9 | 18.2 | 0.42 | 18.0 | TREND | 4.2 | 0.62 |
| AQMIX | USD | 3.09 | 2010-03 | 6.4 | 13.2 | 0.42 | 28.4 | TREND | 0.5 | 0.85 |
| NTSX | USD | 0.2 | 2018-10 | 13.6 | 13.4 | 0.86 | 25.1 | P6b@1.0 | 1.5 | 0.94 |
| RSSB | USD | 0.39 | 2024-02 | 19.7 | 12.2 | 1.29 | 7.4 | P6b@1.0 | -2.1 | 0.98 |
| RSST | USD | 0.99 | 2023-11 | 23.4 | 17.2 | 1.12 | 20.8 | — | — | — |
| GDE | USD | 0.2 | 2022-05 | 34.0 | 19.4 | 1.45 | 15.9 | — | — | — |
| RGBM.TO | CAD | 1.22 | 2025-04 | 14.2 | 10.5 | 1.09 | 4.4 | — | — | — |
| SSO | USD | 0.87 | 2006-08 | 16.9 | 27.0 | 0.66 | 77.8 | — | — | — |
| UPRO | USD | 0.89 | 2009-08 | 33.5 | 40.6 | 0.89 | 59.9 | — | — | — |
| UBT | USD | 0.95 | 2010-03 | 1.9 | 30.0 | 0.16 | 76.3 | — | — | — |
| TMF | USD | 0.9 | 2009-06 | -3.3 | 43.2 | 0.09 | 91.8 | — | — | — |
| SPY | USD | 0.09 | 1993-03 | 11.2 | 12.6 | 0.7 | 51.5 | — | — | — |
| VT | USD | 0.06 | 2008-08 | 11.0 | 12.2 | 0.8 | 32.4 | P1u@1.0 | 0.2 | 0.98 |
| TLT | USD | 0.15 | 2002-09 | 2.8 | 16.9 | 0.13 | 46.4 | — | — | — |
| IEF | USD | 0.15 | 2002-09 | 2.9 | 11.2 | 0.14 | 26.7 | — | — | — |
| USSL.TO | CAD | 1.28 | 2024-07 | 22.4 | 17.5 | 1.09 | 16.1 | — | — | — |

Daily-reset LETF simulation vs actual (USD, monthly):

| Item | Window | Actual CAGR USD | Simulated | Corr | TE |
|---|---|---|---|---|---|
| SSO | 2006-08..2026-08 | 15.7 | 16.2 | 0.995 | 3.2 |
| UBT | 2010-03..2026-08 | 0.2 | 0.2 | 0.987 | 5.8 |
| UPRO | 2009-08..2026-08 | 31.6 | 31.5 | 0.995 | 5.0 |
| TMF | 2009-06..2026-08 | -4.7 | -2.3 | 0.985 | 8.8 |

The TMF simulation is 2.3%/yr kinder than the real fund (financing/borrow costs above the declared T-bill + 0.25%),
so P7-3x is, if anything, flattered. P7 (cautionary benchmark) lost 61% (2x) and 78% (3x) peak-to-trough, and fell 40% / 57% in Jan–Oct 2022 alone.

## 11. Supplement: US-only 1926+ (USD; not used by the answer)

| Item | CAGR | Real | Sharpe | MaxDD | 1929-32 cum / DD | Underwater (mo) | Calls | Ruined |
|---|---|---|---|---|---|---|---|---|
| US_P1u@1.0 | 10.2 | 7.0 | 0.44 | 83.8 | -84 / 84 | 185 | 0 | False |
| US_P1u@1.25 | 10.9 | 7.7 | 0.43 | 90.8 | -91 / 91 | 194 | 0 | False |
| US_P1u@1.5 | 11.4 | 8.2 | 0.42 | 95.0 | -95 / 95 | 248 | 0 | False |
| US_P1u@2.0 | 11.5 | 8.2 | 0.4 | 98.9 | -99 / 99 | 297 | 3 | False |
| US_P2@1.0 | 9.3 | 6.2 | 0.46 | 75.3 | -75 / 75 | 164 | 0 | False |
| US_P2@1.25 | 10.1 | 6.9 | 0.44 | 83.8 | -84 / 84 | 183 | 0 | False |
| US_P2@1.5 | 10.7 | 7.5 | 0.42 | 89.7 | -90 / 90 | 192 | 0 | False |
| US_P2@2.0 | 11.4 | 8.2 | 0.41 | 96.1 | -96 / 96 | 252 | 0 | False |
| US_P3@1.0 | 8.4 | 5.2 | 0.48 | 63.1 | -63 / 63 | 84 | 0 | False |
| US_P3@1.25 | 9.0 | 5.9 | 0.45 | 72.7 | -73 / 73 | 88 | 0 | False |
| US_P3@1.5 | 9.6 | 6.4 | 0.43 | 80.1 | -80 / 80 | 165 | 0 | False |
| US_P3@2.0 | 10.5 | 7.3 | 0.41 | 89.8 | -90 / 90 | 188 | 0 | False |

Monthly re-levering survived the Depression at 2x (3 forced liquidations, not ruined) but with a 99% drawdown.

## 12. Limitations

- Trend history = AQR gross backtest; the result at 35%/50% depends on it (audit §3). No free pre-1985 trend data.
- Gold before 2000-08 uses monthly averages (vol and drawdowns understated). Trend daily paths are interpolated, so
  intramonth drawdowns of trend-holding items are understated.
- Bootstrap checks margin at month-end only; the historical run is daily. Income tax not modelled; WHT only.
- Canada bonds modelled as 10Y government (ETFs hold credit, ~7y duration): 2008 sim +15.5% vs XBB +6.2%.
- CMAs: 5 sources, one (RA) blocked; trend/gold forward values are declared fallbacks.
- The audit found no bugs (re-implementation within 0.015%/yr); two cosmetic issues (P7 forward ERs hardcoded; X_TREND
  ignores FX on overlay P&L, ~8 bp/yr). Files: `reports/cycle8_max_return/audit/`.

## 13. Files

`research/cycle8/` (FRAMEWORK, ADDENDUM_1, engine, run.py, forward.py, live.py, freeze.py, data_*),
`reports/cycle8_max_return/out/` (final_table.csv, answer.csv, crisis_table.csv, live_era.csv, letf_validation.csv,
us1926_*.csv, forward_sleeves.csv, item_returns_monthly.parquet), `reports/cycle8_max_return/audit/`,
`data/cycle8/` (local only; snapshot `cycle8_v1`). No commits, no orders, no forward-registry writes.
