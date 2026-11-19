# eu_peers: European stock move 03:00-09:00 ET -> US economic peer, 09:30 open entry (2026-10-19)

VERDICT: **WEAK** for three clusters (luxury, autos, chemicals), only on big stock-specific move days. **NONE** for every other cluster.
No variant reaches dev t>2 on a rule I would call robust, and the whole result rests on ~300 trades over 2.9 years.

## Data and timing (no look-ahead)
- yfinance 60m, 2023-11-17..2026-10-16 (~2.9 yr), longer than the brief's 2024-05. Dev = 2023-11-17..2025-06-25, check = 2025-06-26..2026-10-16.
- Bars are START-labeled. Checked in ET: Paris/Amsterdam/Frankfurt/Milan/Zurich/Copenhagen first bar 03:00, London 03:00, last bar 11:00-11:30 (ends 11:30 ET). A bar starting <=08:00 ET ends <=09:00 ET, so P(09:00) is the Close of the last bar starting <=08:00 ET.
- US entry = 60m 09:30 bar Open. Exit = 09:30 bar Close (10:30), 10:30 bar Close (11:30) or the last bar Close. The signal uses only European bars, so the peer's own gap is never used as the signal.
- Signals (A, B, C), all computed from bars ending <=09:00 ET:
  - A = last 60m bar close of the previous European session -> 09:00 ET.
  - B = European open (03:00 bar Open) -> 09:00 ET, which excludes the overnight gap.
  - C = previous OFFICIAL daily close -> 09:00 ET. The last 60m bar excludes the closing auction (median gap to the official close 17 bp), so C is cleaner than A.
- Residual = stock return minus beta x Euro Stoxx 50 return on the same window. Beta is a rolling 60-day regression, shifted 1 day (past only).
- Costs: 2 bp/side for mega caps, 5 bp for LRCX/KLAC/TPR/RL/CL/GIS/KHC/DOW/LYB/FCX/EL, 10 bp for CPRI. Cluster trades = the equal-weighted US peer basket, signed by the sign of the mean European residual of the cluster's names. SHEL.L is a control.
- Variants counted: 234 (cluster x A/B x filter x exit) + 468 (cluster x A/B/C x exit x threshold 0-2%) + 45 (family) + 36 pairs x 3 signals x 2 periods of regressions, roughly 850 looks. Treat t of 2-3 with caution.

## 1. Is the US peer already repriced at the open? (regression of peer return on the European residual, C signal, full sample, bp per 1% residual)
| cluster | gap (prev close->09:30 open) | open->10:30 | open->close |
|---|---|---|---|
| semis | 64 (t 13) | 3 (t 0.9) | 8 (1.4) |
| mining, energy ctrl, software, food, pharma | 14-69 (t 7-18) | 0-5 (t<1.2) | ~0 |
| aero, industrial, household, obesity | 1-8 | ~0 | ~0 |
| **luxury** | 17 (t 4.5) | **11 (t 3.5)** | 16 (t 3.2) |
| **autos** | 17 (t 5.5) | **12 (t 3.6)** | 13 (t 2.8) |
| **chem** | 24 (t 6.9) | **12 (t 3.2)** | 14 (t 2.5) |
Most clusters are fully priced at the open (semis, mining, energy, software, pharma, food). Only luxury, autos and chem show about 40% post-open continuation. The pair-level dev regressions pointed to the same three (dev t 2-4 for EL, CPRI, DOW, LYB, GM, F), so the family was selected on dev.

## 2. Tradeable form (sign of the cluster residual, only when |composite residual| > threshold). Net of costs.
Plain sign trading on all days is about 0 or negative in every cluster (e.g. semis A 10:30: dev -8 bp t -1.4). Thresholds are needed.

Best/representative rule (family = luxury + autos + chem, equal-weighted per day): **signal C, trade when |mean European residual of the cluster| > 1.5%, long (short) the US peer basket (luxury: TPR RL CPRI EL; autos: GM F; chem: DOW LYB) if European residual > 0 (< 0), 09:30 open -> 10:30.**
- dev: n 145, +12.8 bp net, t 1.36, win 57%. check: n 159, +29.1 bp, t 2.88, win 61%. All: n 304, +21.3 bp, t 3.08.
- The SPY-hedged version (peer basket minus SPY, +4 bp cost): dev +12.2 bp t 1.40, check +25.9 bp t 2.55.
- Dose-response: tau 2% (C, 10:30): dev n 89 +11.9 bp t 0.83, check n 99 +43.3 bp t 3.39. Exit at the close at tau 2%: dev +26.8 bp t 1.39, check +50.5 bp t 2.49. A at tau 3%, close: dev n 29 +77.9 bp t 1.95, check n 43 +60.5 bp t 1.89 (this is the only dev-t-best pick).
- 45 family variants: 0 reach dev t>2; the check t reaches 2-3.4 in 20+ of them. Dev is weak and check is strong, which suggests a non-stationary or noisy effect.
- By stock, tau 1.5%, C, 10:30: all positive in both halves. CPRI +43 bp (all t 2.05), EL +31 (t 2.2), F +23 (t 1.9), DOW +23 (t 1.7), LYB +21, GM +13, RL +16, TPR +11 (t<1.1).

## 3. Controls (family, C, tau 1.5%, 10:30, same days and signs; net)
- Flip: dev -29.9 bp t -3.2, check -46.5 bp t -4.6.
- SPY placebo: dev -6.9 bp, check -4.1 bp (SPY drifts slightly against the signal; t -2.7 all).
- Random six (JPM WMT COST NFLX ADBE UNH): dev -9.8 bp, check -7.4 bp.
- Cross-cluster swap (luxury signal -> GM/F, autos -> CPRI/EL, chem -> TPR/RL): dev -10 bp, check -14 bp.
- Controls are flat to negative, so the effect is not a market or sign artefact. The negative drift in the placebos means the raw numbers slightly understate the hedged edge.

## 4. Other clusters (best dev pick, net; check): no edge
- semis B r2 10:30: dev n 26 +61 bp t 2.3, check n 30 -2 bp t -0.1. Opens at about 64 bp per 1%, fully priced.
- obesity (NOVO->LLY) B close: dev +16 bp t 1.8, check +1 bp t 0.1.
- aero, software, industrial, mining: none (|t|<1.4 dev, check mixed or negative).
- household/food: gap beta high (food 20 bp/1%), no continuation.
- pharma (AZN->MRK, PFE) B tau 1% 11:30: dev +16 bp t 1.4, check +34 bp t 3.1, but the dev slope was negative at 10:30 for some signals (A: t -0.9 for MRK). Not credible after selection; watch only.
- energy control (SHEL->XOM, CVX): gap beta 46 bp (t 18), continuation ~0 or negative. This is the expected "priced" control.
- Pooled all-cluster generic rule (tau 1%, A/B/C, 10:30): about +2 to +4 bp net and not significant (gross +9 bp t 3.3 dev / 2.3 check, so costs consume it).
## 5. Correlation with the ITB rule
Daily trade P&L correlation with ZB->ITB (f3_trades_canonical g_off - 4 bp): +0.04 (tau 1.5%, n 267 overlapping days); other variants -0.09 to +0.09. Essentially orthogonal, so the book would diversify.
## Caveats
- ~100 trades/yr in a basket costing 4-20 bp round trip, with 1.4-2.9 t-stats split across dev/check. The edge is concentrated in a few mid-cap US names (CPRI, EL, F), which have wider spreads than assumed in thin pre-news open auctions.
- Forward-test only; do not re-mine 2023-26. A pre-registered forward test: luxury/autos/chem, signal C, tau 1.5%, 10:30 exit, long/short basket.
- Scripts: build.py (panels), an.py, an2.py, an3.py, an4.py, an5.py, an6.py; caches in cache/. NB: my first download run wrote cache files into quant_v7/cache (cwd bug, shared with another agent); files are harmless duplicates.
