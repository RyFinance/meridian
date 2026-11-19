# Frozen candidates for the MSTR/BTC intraday option search (2026-10-16 23:0x ET)

Written after the dev grids finished (`dev_grid.parquet`, `spread_grid.parquet`,
`pct_grid.parquet`), BEFORE any 2024+ minute data is loaded. Validation data
(`data/lse/options_mstr/1m/chunk_001..`, 2024-01-01..2026-09-17) is pulled by
`pull_1m.py` and remains LOCKED for candidates until this file is registered in
`research/preregistrations.jsonl`. Registration note states candidate count = 2.

## Candidate C1 — IC-v1: BTC-agnostic 0DTE iron condor (credit spreads)

Exact spec (`research/mstr_btc_0dte/spreads.py`):
```python
Spread(short_steps=2, width=1, entry_min=5, tp=0.5, sl=None, min_btc=0.0, both=True)
```
Sell a 1-wide put spread `short_steps=2` strikes OTM and a 1-wide call spread 2 strikes
OTM. Enter at the first print at/after 09:35 (entry_min=5, first bar in [05, 09]).
Buy back at <= (1 - 0.5) x (credit + 2x$0.65x2) ... per `one_side()`; 0DTE settles on
closing parity spot; non-0DTE Monday legs buy back at the last print. Both fills:
`base` (close +/- half-spread max($0.03, 2.5%)) and `worst` (adverse bar extreme).
Commission $0.65/contract/side on both legs. Return = PnL / risk, risk = width - credit.

Dev stats (2020-11-16..2023-12-29, 273 prepared days, `dev_days.pkl`):
- n = 184 trades (two sides/day), win 92.9%
- mean +24.6% of risk per trade, t 9.55 (base); +20.9%, t 7.88 (worst fills)
- per dev year: 2021 +12.4%, 2022 +30.1%, 2023 +28.6%
- avg credit 26.3% of width (avg credit $1.14, avg risk $3.51); worst day -100.7% of risk
- neighborhood: whole width=1 sweep t 4.99..9.55 for short_steps 1..6 (tp 0.5),
  and tp=0.8 same sweep t 4.99..8.64. Not a single lucky cell.
- flip control (single-sided, opposite side vs BTC): weak (near-miss list shows no
  flip cell above t 2), so C1 is a STRUCTURE (0DTE IV) edge, not a BTC-direction edge.

## Candidate C2 — NNV-v1: naked premium short on the "safe" side (BTC-directed)

Exact spec (`research/mstr_btc_0dte/engine.py`):
```python
Rule(side='sell', strike_steps=4, entry_min=5, tp=None, sl=None, stop_min=390, min_btc=0.0)
```
Sell ONE contract 4 strikes OTM on the side BTC's overnight move points AWAY from
(BTC up -> sell put; BTC down -> sell call), nearest expiry (0DTE Fri, that Fri on Mon),
entry first print in [05, 09] minutes, hold to expiry (0DTE: intrinsic vs closing parity
spot) or last print. Fill/exit as in `engine.py`, both fill models same as C1.

Dev stats:
- n = 173 (one trade/day when the 4th-strike contract prints within +-8% of parity spot)
- mean +24.7% of premium per trade, t 2.03 (base); +23.4%, t 1.88 (worst fills)
- margin-basis (Reg-T proxy max(20% S - OTM, 10% S) + premium): +0.96% per trade, t 2.07
- per dev year (premium basis): 2021 +59.0%, 2022 +2.7%, 2023 +18.1%
- official-close re-settlement of the 95 expiry exits: mean +25.6%, t 2.24 (parity check OK:
  parity spot vs official close, mean err -27 bp, |err| p95 75 bp)
- flip control (same structure, opposite side): +10.2%, t 0.49, avg loss -2.53x premium,
  worst -30.5x premium. The directed side halves tail losses => BTC direction is informative.
- 5-day block bootstrap of base t (7 rng): 5th pct 1.13, median 3.29 -> not a clustering artifact.

## Documented near-misses (NOT candidates; listed for transparency)

- pct.py naked safe 6% OTM, entry 09:45, Mon+Fri: t 5.11 (worst 5.06), n = 142 ->
  fails the >= 150-trade dev gate. Everything else in `pct_grid.parquet` fails t or n.
- engine buy-side rules with t > 2.8: all n <= 24 -> rejected (tiny-n overfit).
- thousands of spread/spread+BTC rows pass raw gates; C1 is chosen as the ROUND,
  neighborhood-robust representative of the family; all other passing rows share its
  parameters' neighborhood and are not registered.

## Validation gates for these 2 registered candidates

Run once on 2024-01-01..2026-09-17 1m prints, same code path (`backtest_tp.load_1m
(window='validation')` -> engine/spreads), no re-tuning:
1. mean net return > 0 under BOTH fill models;
2. one-sided t under base fills >= 1.96 (Bonferroni a=0.05 two-sided-equivalent
   one-sided alpha 0.025 spread over exactly 2 candidates);
3. no single calendar year of 2024, 2025, or 2026 with mean per-trade return below
   -10% (IC: on risk; NNV: on premium), any fill model;
4. A pass leads to a forward paper test only. No live orders in any case.

Metric note: C1/C2 dev stats above use `ret` on risk / premium as their trade return;
validation compares like-for-like.
