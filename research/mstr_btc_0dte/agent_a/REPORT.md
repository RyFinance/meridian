# MSTR extended-hours vs BTC: lead-lag / fair-value-gap study (agent_a)

## Pre-registration (written before any test-half data was examined)
- DEV (explore): 2026-04-29 .. 2026-07-15 (ET trade dates; signal day = the day whose 09:30 open is the exit).
- TEST (one shot, <=2 rules chosen on DEV, frozen): 2026-07-16 .. 2026-09-16.
- Exit = official 09:30 open (yfinance Open). Costs: half-spread 15 bp (04:00-08:00), 6 bp (08:00-09:25), 2 bp at open auction;
  $0.005/share commission per side; $100k notional; stress = all half-spreads doubled.
- Entry = close of the first MSTR bar printed in the minute after the signal time (no print -> no trade).

## Frozen rules for the TEST half (chosen on DEV only, recorded before running test_rules.py)
gap_fv(T) = log(MSTR last print <=T / FV), FV = prior official close * exp(beta * BTC log-ret since prior 16:00),
beta = 40-day rolling OLS of (16:00->09:30 MSTR gap) on BTC, prior days only.
- R1 (hypothesis direction, best DEV fade cell): at 08:00, if |gap_fv| > 50 bp, FADE the gap (MSTR rich -> short), exit official open.
- R2 (DEV-observed continuation, CONTRARY to the lag hypothesis): at 08:00, if |gap_fv| > 100 bp, FOLLOW the gap, exit official open.
Both are expected to be weak: R1 dev t=0.38, R2 dev t~2 on n=13 picked from a 40-cell grid (multiple-testing).

## Data (what is actually there)
- Vault MSTR 1m ext-hours history starts 2026-04-28 (probes of 2026-01-15 and 2026-04-15 return RTH-only 390 bars). Filled 14 days
  missing from mstr_stock_1m_lse.parquet via `pull_missing.py` -> `stock_1m/`. 88 sessions with pre-market bars (44 DEV, 44 TEST);
  9 DEV days are RTH-only in the vault and are excluded.
- Bars exist in 89-99% of extended-hours minutes (MSTR prints almost every minute pre-market), but **ext-hours volume is reported as 0 on
  ~97% of bars before 2026-07-17** (vault feed change); from 2026-07-20 volume is populated. So fillable size is only measurable on TEST.
- TEST ext-hours liquidity (median per minute, when reported): 04:00-08:00 650 sh (~$71k); 08:00-09:30 1,595 sh (~$177k);
  16:00-20:00 375 sh (~$42k); RTH 27,889 sh (~$3.0M). 8-15% of ext bars are flat-OHLC single prints.
- Odd vendor quirk: the opening-cross volume is often booked on the 09:29 bar. Exit uses yfinance official Open instead.
- Returns are computed only between minutes that both have a printed bar (no forward-filled MSTR prices); BTC = Binance BTCUSDT perp 1m.

## 1. Extended-hours lead-lag (corr of BTC past k-min vs MSTR next k-min; non-overlapping windows) — DEV / TEST
| segment | k=1 | k=5 | k=15 | k=30 | contemporaneous k=5 |
|---|---|---|---|---|---|
| after-hours 16-20 | 0.137 / 0.063 | 0.035 / 0.063 | 0.032 / 0.261 | 0.168 / 0.084 | 0.53 / 0.68 |
| pre 04-08 | 0.072 / 0.081 | 0.046 / 0.044 | 0.005 / 0.045 | 0.013 / -0.064 | 0.63 / 0.78 |
| pre 08-09:29 | 0.075 / 0.075 | 0.059 / 0.058 | 0.026 / -0.043 | -0.032 / -0.227 | 0.75 / 0.82 |
| RTH (baseline) | 0.026 / 0.031 | 0.029 / 0.025 | -0.018 / 0.008 | -0.066 / -0.085 | 0.70 / 0.72 |
- There IS a statistically significant **1-minute** lag in extended hours (t 5-13, 2-5x the RTH value), fading to ~0 by 5-15 min
  (AH k=15 test 0.26 is n=483, not seen in DEV). Much of k=1 is non-synchronous printing (Epps) plus bid-ask bounce
  (MSTR own 1m autocorr -0.06..-0.16).
- Size (DEV, `micro_dev.py`): following the 1-min divergence 1.2*BTC_1m - MSTR_1m earns **0.5-6 bp gross** in the top decile and
  4-13 bp in the top 1% (35-40 bp divergences), measured close-to-close (i.e. before paying any spread, and flattered by bounce).
  Round trip is 30 bp (04-08) / 12 bp (08-09:25). **Not tradable.**
- Overnight closed gap (20:00 -> first print after 04:00): MSTR's first pre-market print already reflects BTC's overnight move
  (corr 0.85 DEV / 0.96 TEST, slope 1.17 / 1.39). The residual does not predict the later pre-market move consistently
  (corr to 04:30..09:29: DEV -0.12..+0.01; TEST -0.12..+0.33, sign unstable).

## 2. Pre-market fair-value gap
- BTC-implied FV gap (beta 1.13-1.50, prior-days only): sd 130-180 bp (DEV), 76-106 bp (TEST). Its slope on the move to the open is
  **positive** in both halves (DEV 08:00: corr +0.24, slope +0.31, t 1.6; TEST 08:00: corr +0.26, slope +0.41). Lag hypothesis
  requires a negative slope (-1 = full catch-up). The gap is MSTR-specific information (news, premium/mNAV moves), which continues
  modestly into the open, not stale pricing. To 10:00 the relation is ~0.
- MSTRUSDT perp gap (basis-adjusted at prior 16:00): sd only 6-11 bp, |gap| median 4-8 bp. Pre-market MSTR and the perp agree to
  within a few bp; essentially no day exceeds 25 bp (1-2 per time slot). No predictive slope (t |<1.4|). Nothing to arbitrage
  after a 6-15 bp half-spread.

## 3-4. Trade rules (entry = next 1m print after T, exit official open; $100k; base costs, stress = 2x half-spreads)
DEV grid (40 cells, `fvgap_dev_grid.csv`): fading the FV gap loses in 15 of 20 cells; every 09:00/09:20/09:25 cell is negative
(-19 to -54 bp net). Perp-gap rules have 0-2 trades.

One-shot TEST of the frozen rules:
| rule | period | n | mean gross bp | mean net bp | stress net bp | win | t(net) | median fillable at 10% of minute vol | mean filled of $100k |
|---|---|---|---|---|---|---|---|---|---|
| R1 fade 08:00 \|gap\|>50 | DEV | 29 | +20.4 | +11.6 | +3.6 | 45% | 0.38 | n/a (vol=0) | n/a |
| R1 fade 08:00 \|gap\|>50 | TEST | 24 | -54.7 | **-63.5** | -71.5 | 29% | **-2.59** | $14.9k | $24.4k |
| R2 follow 08:00 \|gap\|>100 | DEV | 13 | +70.3 | +61.4 | +53.4 | 77% | 1.58 | n/a | n/a |
| R2 follow 08:00 \|gap\|>100 | TEST | 6 | +22.8 | +13.9 | +5.9 | 50% | 0.28 | $39.1k | $52.3k |
(Commission at $0.005/sh ~ 0.8-1 bp round trip at $95-140/share.)

## Conclusion
- **No tradable extended-hours BTC->MSTR edge.** The only lag is ~1 minute and worth a few bp gross vs 12-30 bp round-trip spreads.
- The BTC-implied pre-market "mispricing" does not mean-revert to the open; if anything it continues (slope +0.3..+0.4 both halves),
  i.e. it is MSTR-specific information. The hypothesis-direction fade rule failed out of sample (-63.5 bp/trade, t -2.6).
- The continuation rule (R2) was positive but tiny-sample and insignificant out of sample (n=6, +13.9 bp net, t 0.28). Continuation
  would need a fresh pre-registered forward test with more data; not recommended on this evidence.
- Capacity is also small: at 10% of printed minute volume, the median fillable 08:00 entry was ~$15-39k, well short of $100k.

## Caveats
- Short sample: 44+44 pre-market sessions; dev volume missing (fills unmeasurable in DEV). Bar closes != quotes: real bid/ask may be
  wider or narrower than the assumed half-spreads; no L1 quote data was available.
- Binance BTCUSDT perp used as BTC; minute-boundary alignment of 1m bars means k=1 numbers carry non-synchronous-trading bias.
- After the test, lead-lag/gap tables on TEST were computed descriptively only; no rule was altered.

## Files
pull_missing.py, common.py, leadlag.py (+leadlag_*.csv/log, quality_*.csv, overnight_gap_*.csv), micro_dev.py (+log),
fvgap.py (fv_panel.parquet, fvgap_dev_regress.csv, fvgap_dev_grid.csv, log), test_rules.py (rule_results.csv, rule_trades.csv, log).
