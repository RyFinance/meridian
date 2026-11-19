# FX / Treasury overnight move → ETF and rate-sensitive stock rules (agent fx_rates)

**Verdict: WEAK.** One dev-selected candidate survives the check split. Nothing else does. Not EDGE until the lead runs the sealed test.

## Data and limits
- yfinance hourly bars, 730-day cap: futures from 2024-05-24, ETFs (incl. pre/post-market) from 2023-11. Sealed rows (after 2026-08-10) were dropped at load. Only timestamps were printed, never prices.
- Signal: futures 16:00→09:00 ET (close of 15:00 bar to close of 08:00 bar). The brief's 09:25 is not available on hourly bars, so 09:00 is used.
- Dev: session < 2025-06-01 (~246 sessions). Check: 2025-06-01..2026-08-10 (~286). Only ~2.2 years of data, so the split is short.
- Costs: 2 bp per side for ETFs (regular hours). Worst-fill stress: buy at bar high, sell at bar low, applied literally, so H1 double-counts one bar.
- Refunding dates: 2026 statements (Feb 4, May 6, Aug 5) confirmed by search. 2024-25 dates follow the Treasury Wed-before-auctions pattern and are approximate.

## Rules tried (count)
- **A' residual gap, valid (144):** 12 pairs × follow/fade × H1/OC × k∈{0,0.5,1}. Residual R = ETF overnight gap − β·futures move, β expanding OLS on prior sessions. Decision at the 09:30 bar close, entry at 10:30 open. H1 = 10:30 close, OC = 16:00.
- **C raw futures sign, valid (144):** same grid, but trade sign(futures move) on z, entry 09:30 open, H1 = 09:30 bar close.
- **Discarded, invalid data (192):** pre-market residual rules (144 in analyze.py, 48 in premkt_fade.py). Every yfinance pre-market bar has zero volume, so the 09:00 ETF price is stale. Results not used.
- **Event-day cells (12, descriptive):** ZN/ZB→IEF/TLT/TMF/TBT on statement days (n=9) and auction days (n=24).
- Valid total: 288 variants. Dev t>2 (n≥50): 2 in A', 4 in C. Max dev t: 2.60 (A'), 2.53 (C). Bonferroni t for 144 is about 3.5.

## Diagnostics: lag or overshoot at the open (dev / check β, overnight ETF gap on futures move)
| ETF | β dev | β check | Read |
|---|---|---|---|
| FXE | 0.95 | 0.93 | full pass-through, no lag |
| FXY | 0.93 | 0.95 | full pass-through |
| UUP (−6E) | −0.82 | −0.94 | full pass-through |
| FXB | 0.99 | 0.96 | full pass-through |
| IEF / TLT | 1.09 / 1.23 | 1.11 / 1.13 | full pass-through |
| TMF / TBT | 3.73 / −2.49 | 3.37 / −2.26 | leverage only |
| XLU | 0.32 | 0.34 | lags |
| XHB / ITB | 0.17 / 0.30 | 1.17 / 1.14 | lag in dev, caught up by check |
| KRE | −0.43 | 0.46 | unstable |

## Top 3 (dev-selected per family, check reported)
| Rule (family) | Dev n | Dev mean net | Dev t | Dev flip t | Chk n | Chk win | Chk mean net | Chk t | Chk flip t |
|---|---|---|---|---|---|---|---|---|---|
| A' ZB→XLU fade OC k1 | 55 | +0.25% | 2.60 | −3.43 | 75 | 57% | +0.14% | 1.89 | −2.96 |
| A' ZB→XHB fade OC k0 | 166 | +0.21% | 2.12 | −2.91 | 286 | 45% | −0.14% | −2.25 | +0.95 |
| A' ZB→XHB fade OC k0.5 | 84 | +0.32% | 1.96 | −2.46 | 132 | 45% | −0.12% | −1.21 | +0.40 |
| C ZB→ITB follow H1 k0.5 | 103 | +0.25% | 2.53 | −3.34 | 134 | 57% | +0.32% | 3.00 | −3.75 |
| C ZB→ITB follow H1 k0 | 164 | +0.17% | 2.46 | −3.61 | 282 | 59% | +0.28% | 4.18 | −5.36 |
| C ZB→ITB follow H1 k1 | 53 | +0.36% | 2.24 | −2.74 | 44 | 57% | +0.31% | 1.58 | −1.98 |

The family C top 3 are three thresholds on one pair (ITB), so they are not three independent rules.

## Best rule, precisely
C ZB→ITB, k0: at 09:00 ET compute r = ln(ZB 08:00-bar close / ZB 15:00-bar close on the prior session). If r > 0, buy ITB at the 09:30 open. If r < 0, short ITB. Exit at the 09:30-bar close (10:30). Cost 2 bp per side.
- Check: n=282, win 58.5%, mean +0.28% net, t 4.18, avg win +1.00%, avg loss −0.73%.
- Per year (dev-to-check, k0): 2024 +0.32% (n63), 2025 +0.19% (n243), 2026 +0.30% (n140).
- Flip (fade): check −0.36%, t −5.36. Per year −0.40% / −0.27% / −0.38%. Not drift.
- Dev-to-check decay: none (dev +0.17% to check +0.28%).

## Caveats (why not EDGE)
- Worst-fill stress fails (mean −1.6% per trade, t −34 for k0.5). The H1 stress double-counts the same bar, so it is not informative.
- The open pass-through changed regime: ITB β 0.36 in dev, 1.14 in check. The first-hour continuation may be the morning macro flow (08:30 releases), not a pure lag.
- A' residual family: XHB and XLU show dev reversal that decayed or flipped in check.
- Event days (refunding statements n=9, auctions n=24): no significant follow-OC edge (all |t| ≤ 1.5). Non-event days, full sample only (not in grid, unvalidated): ZN→IEF −4.9 bp (t −4.6), ZB→TLT −7.3 bp (t −3.2). Treat as a lead for a pre-registered test, not a finding.
- XHB and ITB are one homebuilder factor, so there is one test, not two.

## Files (research/btc_ah/fx_rates/)
pull.py, analyze.py (invalid pre-market grid, kept for audit), premkt_fade.py (invalid), clean_grid.py (valid, 288 variants), events.py, report_extra.py, check_tbt.py and vol_check.py (data checks), diagnostics_clean.csv, clean_grid.pkl, event_days.csv, cache/.
