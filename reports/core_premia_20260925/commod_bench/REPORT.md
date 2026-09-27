## Summary

*Written by the commodities/benchmarks agent (2026-09-26). Saved by the director session.*

Built the commodities/benchmarks data layer for Core Premia at `/Users/rytty/CCP/quant_v7`, respecting the instrument-level-only rule (no signals, sorts, or strategy returns).

**Code** (`research/core_premia_data/commod_bench/`): `commodity_etf_universe.py`, `eia_trend_audit.py`, `benchmarks_snapshot.py`
**Data**: `data/core_premia/commod_bench/{etf,eia_audit,benchmarks}/`
**Reports**: `reports/core_premia_20260925/commod_bench/{completeness.json, commodity_universe.csv, eia_trend_audit.json, benchmarks_manifest.json}`

### 1. Commodity ETF/ETN universe (24/28 tickers retrieved via yfinance, since 2006 where listed)

| Tier | Tickers |
|---|---|
| Clean, long history, physically/futures backed | GLD (2004), SLV (2006), USO (2006), DBC (2006), GSG (2006), UNG (2007), DBO/DBE/DBB/DBA (2007) |
| Usable, shorter/leveraged | UGA, BNO, USL, PALL, PPLT, SIVR, UCO, SCO, CPER, CORN, WEAT, SOYB, UNL |
| Delisted, unavailable free (2023 iPath ETN wind-down) | UHN (404 on yfinance — likely a mislabeled/retired symbol, distinct from UNL), JJC, SGG, COW |
| Delisted but 1 stale row only, effectively unusable | JO (iPath coffee ETN) — 1 row, 2023-06-08 |

Structural breaks recorded: **USO's April 2020 negative-WTI event** (reverse split + prospectus amendment moving from fixed front-month to a multi-contract-month basket) and **UNG's repeated reverse splits** from chronic contango decay. Roll methodology, expense ratio and inception/closure recorded per ticker in `commodity_universe.csv`.

### 2. EIA energy contracts — audit verdict: **clean for trend use, with scope limits**

- Read price values under the owner's audit exception (no return/spread/level statistic beyond this authorized diagnostic).
- **Roll handling**: EIA's "Contract 1" label auto-rolls at each contract's calendar expiry (published EIA rule), so the daily C1 series is already a paper-rolled, zero-slippage front-month return with no look-ahead.
- **Continuity**: zero duplicate dates for crude oil and natural gas C1; the one nonpositive crude print is the confirmed genuine **2020-04-20 negative-WTI settlement** (−$37.63), not a data defect.
- **Coverage gap**: heating oil, gasoline (conventional), and propane C2–C4 have 65–85% fill pre-2006 and don't exist before ~1994 — **not clean**, excluded from the "clean" verdict.
- **Discontinuation**: entire EIA table stops 2024-04-05 (hard ceiling).
- **Heating-oil → ULSD spec change** (~2013) is invisible in EIA's own metadata — flagged as a trap for any post-2013 heating-oil use, though moot for the pre-2024 window generally.
- **Publication lag**: could not be measured from the static archive (no per-row publish timestamp); would require Wayback Machine cross-referencing (out of scope here).
- **Synthetic construction error vs USO/UNG, 2006–2016 overlap** (construction difference, not a strategy): crude oil vs USO annualized tracking error ≈16.9%, correlation captured in JSON; natural gas vs UNG annualized TE ≈21.4%. Large TE is expected — EIA's C1 is a cost-free/slippage-free idealized roll, while USO/UNG embed real trading, fees and (for USO) the 2020 structural change.

**Verdict: clean for crude oil (RCLC) and natural gas (RNGC) contract-1 and contract-4 series through 2024-04-05, for a narrow ~3–4 month front-curve slope only — NOT clean for heating oil/gasoline/propane, and NOT a substitute for a 12-month strip (USL/UNL) replication.**

### 3. Commodity and equity carry — plain assessment

- **Commodity carry**: needs a full curve; EIA gives only an energy-only (crude + natgas) C1–C4 slope through 2024-04-05 — feasible only as a narrow, disclosed-limitation energy-curve carry proxy, not a broad commodity carry factor.
- **Equity carry**: needs dividend futures or implied dividends from options — **not feasible from free data** available to this task.

### 4. Benchmarks — all 4 families snapshotted (8 files, keyless, no strategy computed)

| Source | File | Coverage |
|---|---|---|
| AQR TSMOM Factors (Monthly) | `aqr_tsmom_factors_monthly.xlsx` | 1985-01 to 2026-05; cols: TSMOM, TSMOM^CM/EQ/FI/FX |
| AQR Century of Factor Premia (Monthly) | `aqr_century_factor_premia_monthly.xlsx` | 1926-07 to 2026-02; 44 style/asset-class columns |
| AQR Value and Momentum Everywhere (Monthly) | `aqr_value_momentum_everywhere_monthly.xlsx` | 1972-01 to 2026-07; VAL/MOM factors + regional/asset-class long-short series |
| Ken French: US 3F, US 5F(2x3), Developed 3F, Developed-ex-US 3F, Global-ex-US 3F | 5 zips | US 3F back to 1926-07 (RF/T-bill included); regional files from 1990-07; all through mid-2026 |

Each file's URL, retrieval UTC, sha256, byte size, terms-of-use text/URL, and column/date coverage is in `benchmarks_manifest.json`.

### Constraints honored
No paid data, accounts, keys, or CAPTCHA bypass; no trades; no commits/pushes (working tree only has new files under the assigned output paths, verified via `git status`); `bot/`, `reports/forward/`, cron/launchd untouched; Sol's files not edited.