# MSTR opening-auction lag: does BTC's 09:20-09:31 ET move lead MSTR's first 15 minutes?

Verdict: **NONE** under the brief's costs and worst fills. A first-minute lead exists, but it sits inside the first bar, which the required exits (09:35+) and worst fills cannot capture.

**Setup.** MSTR 1m regular hours (dev 2020-08..2023-12; LSE 2026-04-29..08-10), BTC 1m. Sealed holdout enforced. 613 trade days with full bars (dev 294 ≤ 2022-06-30, check 319). No MSTR data 2024-01..2026-04-28. Timestamps are bar-open (BTC open_t is 0.8 bp from close_{t-1}, versus 5.8 bp from its own close). Price "as of T" = close of bar T-1. MSTR O = 09:30 bar open. Costs 8 bp per side (3 + 5). Worst fills: buy at high, sell at low.

Signals: x1 = BTC 09:20→09:30, x2 = BTC 09:28→09:30, x3 = BTC 09:30→09:31.

## 1. Regressions (27 specs, bp on bp, OLS t)

| y (MSTR) | x | dev beta (t) | check beta (t) | read |
|---|---|---|---|---|
| O→09:31 close (first minute) | x1 | 0.37 (3.84) | 0.35 (3.19) | replicates |
| O→09:35 | x1 | 0.34 (1.68) | 0.67 (3.64) | grows in check |
| 09:31→09:32 | x3 | 0.61 (2.65) | -0.04 (-0.19) | does not replicate |
| 09:31→09:35 | x3 | 0.59 (1.48) | 0.51 (1.35) | weak |
| 09:31→09:35 | x1 | -0.03 (-0.20) | 0.31 (1.98) | weak |

x3 fits on the same bar (beta 1.8, t 7.1, check) are contemporaneous and not tradable.

## 2. Primary trades (60 variants, worst fills, 8 bp per side)

Grid: 5 signal/entry pairs (x1 or x2 at 09:30 or 09:31 open; x3 at 09:31) × exits 09:35, 09:40, 09:45 × thresholds 0, 10, 25, 50 bp. Long if signal > 0, short if < 0. Flip control on every row.

- Dev, n ≥ 30 (51 variants): **0 positive**, best -36 bp. Check, n ≥ 30 (36 variants): **0 positive**, best -37 bp.
- Flipped direction also negative in every row. Fills and costs dominate: penalty 82-115 bp per trade (section 4).

Dev top 3 (least-negative dev mean), then check:

| rule (signal \| entry \| exit \| thr) | dev n | win | dev bp (t) | avg W / L | dev per-yr bp | check n | check bp (t) | flip bp |
|---|---|---|---|---|---|---|---|---|
| x1 \| 09:30 open \| 09:45 \| 25 | 112 | .44 | -36 (-1.3) | +205 / -224 | 20 -36, 21 -16, 22 -89 | 59 | -109 (-3.3) | -114 |
| x1 \| 09:31 open \| 09:45 \| 25 | 112 | .43 | -39 (-1.5) | +191 / -211 | 20 -1, 21 -4, 22 -140 | 59 | -105 (-3.4) | -101 |
| x1 \| 09:30 open \| 09:45 \| 50 | 46 | .48 | -50 (-1.0) | +223 / -300 | 20 +35, 21 -7, 22 -211 | 12 | -183 (-2.7) | -95 |

Check per-year for rule 1: 2022 -213, 2023 -70, 2026 -2 bp.

## 3. Best dev rule, precisely (not tradable)

x1 = close(09:29)/close(09:19) - 1. If x1 ≥ +25 bp, buy at the 09:30 bar high (≤ -25 bp: sell at low). Exit at the 09:45 bar low (long) or high (short). Net of 8 bp per side. Dev -36 bp (n=112). Check -109 bp (n=59). Flip -114 bp.

## 4. Diagnostic (not one of the 60 primary rules)

Edge = (signal - flip)/2, penalty = -(signal + flip)/2, from primary trades. Check (n ≥ 30): edge positive in 31 of 36 rows, range -10 to +71 bp; penalty 82-115 bp. Dev: edge positive in 43 of 51.

Open-fill sensitivity (fill at bar open, 8 bp per side, same rules): dev top rule x1 \| 09:30 open \| 09:45 \| 25 = **+78 bp (n=112, t 2.7)**, check **-10 bp (n=59, t -0.3)**. Open-fill positives: dev 29 of 51, check 12 of 36. Heavy dev-to-check decay.

## 5. Caveats

- 60 primary rules plus 27 regressions. The open-fill grid is a diagnostic, not used for selection.
- Not tested: a 09:31 exit (the first-minute move from section 1). The brief's exits start at 09:35. At worst fills, the 09:30-09:31 bar range alone likely exceeds any edge.
- Of 888 trade days (827 dev files + 61 LSE days), 275 lacked full bars and were excluded.
- Check is not one contiguous period (2022-07..2023-12 plus 2026-04-29..08-10).

## Verdict

NONE. No positive variant under the brief's rules in either half. The first-minute lead (about 0.35 × BTC's 09:20→09:30 move, t 3.2-3.8, replicated) shows the auction does not fully price BTC's last 10 minutes. It is smaller than the worst-fill range plus the 16 bp round trip, so it is not tradable with these exits.

Files: auction/auction_study.py, run_log.txt, regressions.csv, variant_summary.csv, trades.csv, diag_*.csv.
