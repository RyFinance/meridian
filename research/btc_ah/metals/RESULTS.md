# Metals overnight gap → US equity/ETF (agent: metals)

**Question:** do GLD, SLV, GDX, GDXJ, NUGT, NEM, GOLD, AEM, KGC, PAAS, AG, HL, FCX, SCCO, COPX lag or overshoot the GC=F / SI=F / HG=F move from 16:00 to ~09:00 ET?

**Data:** yfinance 1h bars (730-day cap), 2024-05-24 to 2026-08-10. Equities with pre/post-market. Sealed at 2026-08-11 00:00 ET. Cache in `cache/`. LSE Terminal was not running (app launch blocked), so no longer hourly history. Daily futures were not used (timing trap).

**Timing (no look-ahead):** futures 16:00 open (prev day) to futures 09:00 open. Equity close = 15:30 bar close. Equity pre-market price at 09:00 = 08:00 bar close. Entry at 09:30 open (signals a,b,c) or 10:30 open (signal d). Rolling beta and sd are past-only (shift 1, 60-day window).

**Signals (follow = trade in sign direction):**
- a: futures 16:00→09:00 raw move
- b: residual = beta × futures move − equity pre-market move (+ = equity lagging)
- c: COMEX-window futures move 08:00→09:00
- d: futures 09:00→10:00 move (London-window proxy), entry 10:30

**Variants:** 4 signals × 2 thresholds (|s| > k·sd, k∈{0,1}) × 2 holds (FH = entry bar, 1 hour; OC = to 16:00) × 15 pairs = **240 variants**. Flip (fade) reported as the control for each. 16 GOLD variants have no dev history (ticker starts 2025-12), so they are check-only and excluded from ranking: 224 dev-eligible.

**Split:** dev = trades ≤ 2025-06-30 (~13 months), check = 2025-07-01 to 2026-08-10. Costs: 2 bp/side ETFs (GLD, SLV, GDX, GDXJ, NUGT, COPX), 3 bp stocks, 10 bp/side for names under $5 at some point (KGC, AG, HL).

**Dev screen:** max dev t among 224 follow variants = 1.95; zero variants above 1.96. 19 variants have dev t < −1.96 (follow loses). Checked for the six largest |dev t|: their flips also lose on check.

**Top 3 by dev t (follow), net bp per trade:**

| rule (eq, signal, k, hold) | dev n | dev mean | dev t | dev win | flip dev | check n | check mean | check t | check win | flip check |
|---|---|---|---|---|---|---|---|---|---|---|
| FCX, d_london, k0, OC | 229 | +20.7 | 1.95 | 0.53 | −32.7 | 267 | −14.2 | −1.36 | 0.46 | +2.2 |
| COPX, d_london, k0, OC | 229 | +14.9 | 1.87 | 0.54 | −22.9 | 267 | −15.6 | −1.90 | 0.42 | +7.6 |
| COPX, a_fut_on, k0, OC | 229 | +18.2 | 1.75 | 0.55 | −26.2 | 270 | +13.8 | +1.27 | 0.57 | −21.8 |

**Full-sample detail (top 3):**

| rule | n | win | net mean | t | avg win | avg loss | flip net (t) | 2024 / 2025 / 2026 net | worst-fill net (t) |
|---|---|---|---|---|---|---|---|---|---|
| FCX d_london k0 OC | 496 | 0.49 | +1.9 | 0.25 | +112 | −106 | −13.9 (−1.85) | −2.7 / +13.7 / −14.8 | −93 (−13.6) |
| COPX d_london k0 OC | 496 | 0.47 | −1.5 | −0.27 | +89 | −82 | −6.5 (−1.11) | +1.0 / +6.4 / −17.0 | −65 (−12.3) |
| COPX a_fut_on k0 OC | 499 | 0.56 | +15.8 | 2.09 | +120 | −117 | −23.8 (−3.15) | +16.0 / +9.8 / +26.0 | −95 (−14.3) |

**Family means across 15 pairs (net bp per trade, dev / check):** no family is positive on both. Median dev t ranges from −1.8 to +0.1. Typical: a OC k0 −3 / −8; b OC k1 0 / +12; c FH k1 −4 / +21 (dev-negative); d OC k0 −2 / −13. Across variants, corr(dev mean, check mean) = 0.42, so dev rank carries some information, but not enough to make a top-3 pick work.

**Flip control:** all three flips lose on dev (−23 to −33 bp). On check, the FCX and COPX d_london flips are slightly positive (+2.2, +7.6 bp), but their follow sides lose on check, so this is noise around zero, not drift. The COPX a_fut_on flip loses on check (−21.8). The one dev-selected fade candidate on the tail (KGC d_london FH) has follow and flip both negative on check (−21.5 and −18.5). Costs drive those results, since gross is about −3 bp. The 6 variants with the largest |dev t| all have negative check flips, so none shows drift.

**Verdict: NONE.** Dev has no variant above t 1.96. Top 3 check results are mixed (one positive, two negative). All three fail the worst-fill stress (bar high in, bar low out, roughly −65 to −95 bp per trade). COPX a_fut_on is the only pattern with a consistent sign (positive in every year and in both halves), but its full-sample t (2.09) does not survive selection over 240 variants. Watch-only; retest forward, not as a trading rule.

**Caveats**
- Hourly granularity: the futures "09:00" price is the 09:00 open, not 09:25. The COMEX open (08:20) sits inside the 08:00 bar, so it is not separately resolved.
- The brief's "London fix (10:30 ET)" is not the LBMA fix. LBMA fixes are 10:30 London (05:30 ET) and 15:00 London (10:00 ET). Signal d is a 09:00→10:00 proxy.
- Only about 2.2 years, so both halves are short and underpowered.
- GOLD has no dev history; NUGT (levered ETF) is costed at 2 bp.
- Disclosure: the first yfinance probe printed the last bar timestamp (2026-10-16) for four symbols, and the pull downloaded post-holdout bars into memory before the cut. Nothing after 2026-08-10 was saved or used.

**Files:** `pull.py`, `study.py` (variants, `variants_summary.csv`, `all_trades.parquet`), `report.py` (family, top-3, per-year, worst-fill).
