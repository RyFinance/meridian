# FINRA daily short-sale volume (Reg SHO) - results
**VERDICT: NONE (tradable).** A small gross cross-sectional signal exists (low SVR outperforms next day) but it does not clear
Bonferroni and costs more than eat it. Time-series (H2) and market-level (H3) are noise.
## Data / setup
- FINRA CNMSshvol files 2022-01-03..2026-10-16: 1202 trading days, all present (48 holiday 403s). Cached in raw/ (curl, 0.3 s spacing).
- Universe: 501 names from data/expanded_universe_all_tickers.txt (today's S&P 500; BRK-B, BF-B dropped for symbol mismatch).
  **Survivorship bias**: current constituents only; low-SVR names skew to today's winners, which inflates long-horizon (h20) numbers.
- yfinance adjusted OHLC (px.pkl). SVR = ShortVol/TotalVol; z20 = (SVR - mean20)/sd20 using the prior 20 days (excludes today).
- Day-t signal -> entry at day t+1 open, exit at open t+1+h. dev = 2022-2024, check = 2025..2026-10-16.
- Costs 5 bp/side/stock = 20 bp per long-short cohort round trip (naive, no netting). Decile = 10% of names (~50/leg).
- t-stats: Newey-West (lag h) on daily cohort series, plus non-overlapping (every h-th day) t. Scripts: load.py, analyze.py, log analyze.log.
## Multiple testing
Variants tried: H1 6 (raw|z20 x h1/5/20) + H2 10 (z>2, z<-2 x h1..5) + H3 2 (vw, ew) = **18**. Nothing else was run.
Bonferroni 0.05/18 -> need |t| >= ~3.0. Pass rule: dev net t >= 3 AND check same sign, net > 0.
## H1: decile spread (long lowest SVR, short highest), bp per cohort
| variant | dev gross (NW t / non-ov t) | dev net | chk gross (NW t / non-ov t) | chk net | turnover/day |
|---|---|---|---|---|---|
| raw h1 | 4.2 (2.66 / 2.60) | -15.8 | 9.5 (2.84 / 2.88) | -10.5 | 60% / 52% |
| raw h5 | 10.6 (1.98 / 0.79) | -9.4 | 17.9 (1.62 / 2.07) | -2.1 | 60% / 52% |
| raw h20 | 35.9 (2.10 / 0.87) | +15.9 (t 0.93) | 55.4 (1.69 / 1.61) | +35.4 (t 1.08) | 60% / 52% |
| z20 h1 | 2.4 (1.48 / 1.53) | -17.6 | 8.2 (2.54 / 2.53) | -11.8 | 75% / 72% |
| z20 h5 | 5.3 (1.26 / 2.07) | -14.7 | 2.1 (0.24 / 0.39) | -17.9 | 75% / 72% |
| z20 h20 | 7.4 (0.70 / 1.27) | -12.6 | -3.2 (-0.18 / 0.02) | -23.2 | 75% / 72% |
- Best candidate raw h1: gross t 2.7/2.8 (consistent sign) but < 3.0 Bonferroni. Even with turnover-netted costs (20bp x turnover)
  net is -7.8 bp (dev) / -0.9 bp (check) per day. Break-even cost ~1.7 bp/side (dev), ~4.6 bp/side (check) vs 5 assumed.
- raw h20 is the only net-positive row, but t ~1 (dev 0.93, check 1.08), non-overlapping n = 36 / 21 cohorts, and it is the
  variant most exposed to survivorship (persistent low-SVR stocks = today's S&P winners). Not credible.
- Deciles loosely monotone (raw h1 dev D0..D9: 8.3 6.0 5.3 4.4 3.8 2.9 3.4 3.6 4.2 4.1 bp); spread is mostly D0 outperforming.
- **Flip control** (long highest, short lowest): net -24 / -30 bp (raw h1), -56 / -75 bp (raw h20): flipped loses in every row as expected
  from the sign, so the direction is consistent with the literature, but the control only confirms sign, not tradability.
### Per-year gross annualised LS % (before costs)
| variant | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|
| raw h1 | 18.2 | 5.3 | 8.2 | 31.1 | 14.9 |
| raw h5 | 8.2 | 2.8 | 5.0 | 16.2 | -0.2 |
| raw h20 | 6.4 | 1.7 | 5.5 | 10.6 | 1.9 |
| z20 h1 | 7.5 | 3.7 | 7.1 | 28.0 | 11.2 |
| z20 h5 | 4.3 | -0.6 | 4.5 | 8.1 | -8.1 |
| z20 h20 | -1.0 | -0.9 | 4.5 | 1.2 | -2.6 |
## H2: per-stock abnormal SVR (z20 beyond +/-2), abnormal return vs equal-weight universe, bp (date-clustered HAC t)
| event | h1 dev / chk | h3 dev / chk | h5 dev / chk |
|---|---|---|---|
| z>2 (N 13.2k / 7.9k) | -3.3 (-1.84) / -2.1 (-0.76) | -6.8 (-2.15) / -7.0 (-1.43) | -6.2 (-1.61) / +0.9 (0.12) |
| z<-2 (N 15.6k / 10.7k) | +2.7 (1.70) / +6.2 (2.19) | +4.0 (1.34) / +9.6 (1.99) | +3.9 (0.95) / +9.3 (1.42) |
Signs are directionally literature-consistent (high SVR -> underperform) but max |t| = 2.4 (dev), nothing near 3.0, the dev/check
profile drifts, and gross effects of 3-10 bp are below the 10 bp round-trip cost on every cell (net negative in both directions).
## H3: market-level aggregate SVR (z20) -> next-day SPY return (open t+1 to open t+2)
| agg | dev slope bp/1z (t) | check slope (t) | corr dev / chk |
|---|---|---|---|
| volume-weighted | -1.75 (-0.52) | -1.26 (-0.27) | -0.02 / -0.01 |
| equal-weight | -3.39 (-1.07) | +1.93 (0.45) | -0.04 / +0.02 |
No predictability (sign flips). Note the contemporaneous corr with same-day SPY return is -0.24/-0.35 (dev): SVR mostly reflects
same-day returns (short volume rises on up days), which is not tradable with a post-close publication.
## Honest conclusion
- 0 of 18 variants pass the Bonferroni + net + check gate. Strongest gross finding (raw h1 decile spread, t ~2.7-2.8 in both
  periods) has ~4-10 bp gross per day against 12 bp of netted costs at 5 bp/side: **NONE** as a standalone retail-cost strategy.
- A weak informational effect likely exists (low-SVR > high-SVR, positive all years gross), only usable as a tilt/overlay on trades
  already being made at near-zero marginal cost, or at institutional costs (< ~2-4 bp/side). Not worth pursuing standalone.
- Caveats: survivorship (current S&P 500), yfinance adjusted opens, no borrow costs on shorts, no netting of overlapping h5/h20 cohorts.
