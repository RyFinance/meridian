# Miners deep dive: residual open-gap fade, when does it work, does it survive 2026?

**Verdict: NONE.** The dev-period edge (2020-08..2023-12) does not survive the check window (2024-01..2026-08-10). The one tradable long-only subset is WEAK and unconfirmed. Not an EDGE.

**Holdout:** every read uses a pyarrow filter (`< 2026-08-11`). The BTC 1m read stops at 2026-08-10 23:59 UTC. Downloads in `cache/` were capped at the cut. Earlier agents' `tickers/` files were loaded in full before filtering (see tickers/RESULTS.md); this pipeline does not reuse that step.

## Scope and data limits
- Universe, daily (2017-2026): MARA, RIOT, CLSK, HUT, CIFR, WULF, IREN, BTBT, BTDR, APLD, GLXY, HIVE, CORZ. BITF is not on yfinance (dropped). CORZ/HIVE have no 60m. APLD/BTDR 60m came back empty, so the intraday universe is 8 long-history names plus GLXY.
- 60m (yfinance, ~730 days, 2024-08..2026-08-10): no dev-period intraday data. The LSE terminal is up (`terminal_status` OK), but the Python bridge fails here because the sandbox blocks the app launch (`open -b` error), and pulling 30m history through the MCP tool is too large for context. So intraday exits are check-only, and 12:00 is replaced by 12:30 (the 60m grid has no 12:00 bar).
- **Timing flaw in the prior residual fade (lead_verify/resfade.py):** the signal uses the 09:30 open, which is also the fill. That is look-ahead. I label these ideal (`I_*`, `D_close`). Tradable variants (`V_*`) decide on the 09:30 bar and enter at the 10:30 open.
- Signal: residual = gap − β·BTC_off (β from past 250 sessions). z = residual / past-250 residual std. Exclude |gap| > 15%.
- Regime: BTC 16:00 close vs its 50-day mean (known at prior close); 20-day vol vs its past-250 median.
- Costs: 3 bp/side, 10 bp/side when raw open < $5.

## Variants tested: 324
- Daily close, ideal entry: 54 (2 directions × |z| ≥ 0/1/2 × BTC above/below/all MA50 × vol hi/lo/all).
- 60m, 5 entry/exit pairs × the same 54: I_1030, I_1230, I_close, V_1230, V_close.
- Dev-selection on daily variants; intraday within-window dev 2024-08..2025-06, check 2025-07..2026-08.

## Top 3 by dev t (daily close, ideal; check = 2024-01..2026-08-10)

| Rule | Dev n, mean bp, t, flip | Check n, mean bp, t, flip | 2026 YTD n, mean bp, t |
|---|---|---|---|
| up_short \|z≥1\|BTC all\|vol lo | 391, +173, 4.52, −199 | 388, −50, −0.72, +31 | 122, −73, −0.64 |
| down_buy \|z≥1\|BTC below\|vol all | 284, +269, 3.79, −293 | 384, +2, +0.17, −20 | 96, +69, −0.54 |
| up_short \|z≥1\|BTC all\|vol all | 718, +76, 3.39, −100 | 821, +48, +0.64, −68 | 227, −54, −0.21 |

Only the second rule is long-only, and it is the one that matters for retail. Its dev edge is gone on check.

## Per-year, daily close (mean bp per trade, n, day-t)

| Year | up_short \|z≥1\|all\|lo | down_buy \|z≥1\|below\|all | down_buy \|z≥0\|all\|all (base) |
|---|---|---|---|
| 2020 | +230, 79, 3.3 | +357, 58, 2.8 | +125, 625, 3.6 |
| 2021 | +449, 37, 3.3 | +397, 36, 2.1 | −4, 806, 1.1 |
| 2022 | +176, 121, 2.5 | +178, 174, 0.9 | −7, 1056, −0.3 |
| 2023 | +101, 219, 1.7 | +329, 49, 1.9 | +83, 1239, 1.4 |
| 2024 | −143, 90, −0.5 | −52, 83, 0.3 | −17, 1109, 0.1 |
| 2025 | +14, 176, −0.2 | −8, 205, 0.4 | +53, 1419, 0.8 |
| 2026 YTD | −73, 122, −0.6 | +69, 96, −0.5 | −13, 915, 0.6 |

The base (all down-gap buys, no conditioning) is flat in every year except 2020 and 2023. Its signs flip year to year, which is what noise looks like.

## Tradable intraday long-only (decision on 09:30 bar, enter 10:30 open, exit 16:00)
- Best of the 54 by check (`down_buy |z≥0| BTC above MA50 | vol lo`): within-window dev +12 bp (n 196, t 0.6), check +53 bp (n 276, t 1.8), 2026 +51 bp (n 139, t 1.6).
- Post-hoc: chosen after seeing check. Median trade −6 bp, mean carried by the top 5% of trades (more than 100% of total P&L). Worst-fill stress (buy at 10:30 bar high, sell at 15:30 bar low): mean −117 bp.
- Whole family of 54 at V_close: 15 positive on check; median −38 bp. Not distinguishable from chance.

## Is the 2026 failure regime change or noise?
- **Dev winner (up-gap fade):** positive in 2020-2023 (+101 to +449 bp), then 2024 −143, 2025 +14, 2026 −73. The break is at 2024 (AI/HPC era), not 2026 alone, which fits a regime change. But the 2024-26 samples are small and each has |t| under 0.7, so the data says "no edge", not "reversed".
- **Long-only down-gap buy:** no era pattern. The one positive year (2026 trade-weighted +69 bp) has a day-weighted t of −0.5, so it is outlier-driven. Noise.

## Caveats
- Intraday variants have no dev sample before 2024-08. The within-window split is a second-best substitute.
- BITF missing; HIVE/CORZ and BTDR/APLD have too little history for stable dev stats.
- Few trades per variant on the tightest filters (z≥2: 4 to 30 per year); t-stats there are unreliable.
- Bonferroni over 324 variants: t ≈ 3.8. Only the dev values clear it; none clear it on check.

## Files
- `run.py` (build and trades), `analyze*.py` (tables), `variants_stats.csv` (every variant × exit × sample), `trades.parquet`.
- `fetch.py`, `fetch60b.py`: yfinance pulls for BTDR, APLD, CORZ, GLXY, HIVE (cache/).
