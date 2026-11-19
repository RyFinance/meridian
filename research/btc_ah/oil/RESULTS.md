# Oil overnight move -> US energy names at the open (agent: oil)

**Verdict: NONE.** Energy equities/ETFs do not lag or overshoot the overnight oil move in a way that pays after costs. ETFs gap ~1:1 (USO 0.97, BNO 0.94); stocks gap only 0.36-0.73 of the oil move, but the residual does not continue or revert tradeably.

## Tested
- Intraday (1h, 2024-05-28..2026-08-10, 523 sessions): 20 instruments (oil map fixed a priori: CL for USO/UCO/SCO/XLE/XOP/OIH/XOM/CVX/OXY/COP/DVN/FANG/APA/FRO/DHT/STNG/TNK, BZ for BNO, NG for UNG/BOIL). Rules: X_FH (follow sign of oil move, 09:30 open -> 10:30 close), X_OC (09:30 open -> 16:00), E_RES (residual of open gap vs oil-implied, decided 10:30, 10:30 open -> 16:00). Each at k in {0,0.5,1,2} sigma. **240 follow variants**, each with its flip as control.
- Daily (2000-08..2026-08-10): same 20 names, D_OD (open->close) and D_GAP (close->open), k in {0,0.5,1,2}. **160 variants**, flips as control. No daily residual rule (gap known only at the open).
- Event subsets: weekend, weekend |oil|>3%, OPEC+ Mondays. Total **400 follow variants** plus flips.

## Timing and data
- Off-hours move: oil close of bar 15:00 (16:00 ET) -> bar 08:00 (09:00 ET), the last hourly close before 09:25.
- Entries: 09:30 open (X rules); residual rule decides on the 09:30 bar close and enters 10:30 open.
- Costs: ETFs 2 bp/side, stocks 3 bp/side. The $5 rule (10 bp) was not applied; no price check was done.
- Deviation: intraday history starts 2024-05, so dev/check = 2024-05..2025-06-30 / 2025-07..2026-08-10. LSE Terminal was not running and the sandbox blocks launching it.
- Daily: CL/BZ/NG daily close is assumed to be the 14:30 ET settle (before the 16:00 USO close). Signal = oil move through prior session P. Dev <=2022-06-30, check 2022-07..2026-08-10.

## Pooled results (all 20 names, net bp per trade, follow / flip)
| test | dev n | dev net / t | check n | check net / t |
|---|---|---|---|---|
| Intraday X_FH k0 | 5025 | -4.9 / -2.75 (flip -5.3 / -3.00) | 5281 | -1.4 / -0.83 (flip -8.8 / -5.21) |
| Intraday X_OC k0 | 5025 | -10.4 / -3.46 (flip +0.2 / 0.06) | 5281 | +0.1 / 0.03 (flip -10.3 / -3.87) |
| Intraday E_RES k0 | 5069 | -2.7 / -1.15 (flip -7.5 / -3.15) | 5317 | -8.5 / -4.00 (flip -1.7 / -0.79) |
| Intraday X_FH k1 | 1070 | +14.2 / 3.02 (flip -24.4 / -5.18) | 1795 | -2.0 / -0.68 (flip -8.3 / -2.82) |
| Daily D_GAP k0 | 86657 | -4.7 / -7.63 (flip -5.7 / -9.19) | 20546 | -6.5 / -4.54 (flip -3.7 / -2.60) |
| Daily D_OD k0 | 86657 | -9.1 / -11.5 (flip -1.3 / -1.59) | 20546 | -7.9 / -5.33 (flip -2.3 / -1.52) |

## Top 3 by dev t (intraday; n_dev >= 60)
| rule | name | dev n / net / t | check n / net / t | flip dev / check (net, t) |
|---|---|---|---|---|
| E_RES k1.0 | FRO | 66 / +57.5 / 2.95 | 66 / -7.9 / -0.41 | -69.5 / -3.56 ; -4.1 / -0.21 |
| X_FH k0.5 | FANG | 125 / +25.1 / 2.08 | 172 / +1.9 / 0.17 | -37.1 / -3.08 ; -13.9 / -1.30 |
| X_FH k0.5 | OXY | 125 / +22.5 / 1.87 | 172 / +7.9 / 0.77 | -34.5 / -2.87 ; -19.9 / -1.94 |

Per-year net bp (n): FRO E_RES follow 2024 +64 (27), 2025 +53 (39) | check 2025 +4 (27), 2026 -16 (39). FANG follow 2024 +16 (64), 2025 +35 (61) | check 2025 +27 (62), 2026 -12 (110). OXY follow 2024 -3 (64), 2025 +49 (61) | check 2025 +25 (62), 2026 -2 (110). Flips are negative in most years. Decay is large for FRO (+57 to -8). FANG and OXY fall to about zero in check.

## Top 3 by dev t (daily long history; n_dev >= 60)
| rule | name | dev n / net / t | check n / net / t | flip dev / check (net, t) |
|---|---|---|---|---|
| D_GAP k1.0 | BOIL | 647 / +30.1 / 1.61 | 464 / -4.3 / -0.16 | -38.1 / -2.04 ; -3.7 / -0.14 |
| D_GAP k1.0 | UNG | 939 / +9.1 / 1.21 | 462 / -10.2 / -0.67 | -17.1 / -2.29 ; +2.2 / 0.14 |
| D_GAP k2.0 | BNO | 153 / +34.2 / 1.21 | 66 / +40.4 / 0.95 | -42.2 / -1.50 ; -48.4 / -1.14 |

Dev t>2: intraday 2 of 127 (n>=60), daily 0 of 160. Post-hoc: shipping names (DHT, STNG, TNK) are negative under daily follow in both dev and check (D_GAP k0 STNG -7.3 dev, -14.7 check). Gross reversal is about 4 bp, below the 6 bp cost, so the flip still loses net.

## Special events (intraday X_OC k0, follow)
- Weekend Fri->Mon, all: n 1896, net -5.5 bp, t -1.21.
- Weekend |oil|>3%: 43 distinct dates (CL/BZ/NG). Date-level mean net +7.0 bp, t 0.22 (trade-level -30 bp, t -2.2, is clustered across names). Flip trade-level +20 bp, t 1.48. No reliable edge.
- OPEC+ Mondays: 10 dates from memory, NOT verified; n 139 trades, net -21.7 bp, t -0.94. Too few to test.

## Per-year (pooled intraday, net bp, follow)
- Intraday X_OC k0: 2024 -2.7 (2756), 2025 -6.9 (4666), 2026 -4.3 (2884).
- Intraday E_RES k0: 2024 -3.0, 2025 -7.9, 2026 -4.6.

## Verdict
NONE. No rule keeps a stable dev-to-check sign with t > 2; top-3 check results are indistinguishable from zero. Flips are not profitable either, so follow-side means are cost-driven. The open-gap lag is real but does not carry forward in time.
## Holdout disclosure
The hourly pull (period="730d", no end date) held post-cutoff rows in memory until fetch.py filtered them at once. Nothing after the cutoff was saved or analyzed. An early probe printed only one index max date (2026-10-16), no prices.

Code and outputs: research/btc_ah/oil/ (fetch.py, analyze*.py, report*.py, select_intraday.py, cache/, results_*.csv).
