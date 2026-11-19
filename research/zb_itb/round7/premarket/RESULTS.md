# Round 7: pre-market entry for the ZB → homebuilder rule

Signal d = sign(ZB 08:00 / prior 15:00) from `verify/f3_canonical.build()`. Baseline = MOO at 09:30 open, exit at 10:30 close, 2 bp/side.
Script: `premarket.py` (log in `run_out.txt`, per-day rows in `per_day_<SYM>.csv`). Data: vault 1m (DHI, LEN, PHM, TOL, KBH, SPY), yfinance 5m prepost (`data/ITB_5m_pp.parquet`, `data/XHB_5m_pp.parquet`).

## Data checks
- Vault 1m timestamps are UTC. Verified: the 09:30 bar open equals the yfinance daily open (median gap 0 bp), and the largest-volume minute is 16:00 ET. Bars are start-labeled.
- Only volume > 0 bars count as prints. The 5m prepost bars are flat fill-ins when volume is 0.

## 1. Pre-market activity, 09:00–09:29 (median per day)
| Name | Days | Shares 09:00–09:29 | Shares 09:15–09:29 | Days with no print 09:15–09:29 |
|---|---|---|---|---|
| DHI | 545 | 511 | 302 | 14% |
| LEN | 545 | 494 | 316 | 17% |
| PHM | 544 | 114 | 50 | 29% |
| TOL | 532 | 180 | 85 | 25% |
| KBH | 510 | 0 | 0 | 97% (only 659 pre-open bars in the whole file) |
| ITB | 57 | 0 | 0 | yfinance: 0 volume in all 1,050 pre-open bars |
| XHB | 57 | 0 | 0 | same |

ITB cannot be measured pre-market. Its yfinance pre-market bars carry no volume, and only 25 of 66 bars in 09:00–09:29 change price, which looks like quote marks rather than trades. The vault has no ITB or XHB candles (404 "no candle data").

## 2. Gross edge of pre-market entry vs 09:30 open (bp per trade, positive = better)
| Entry | All | Dev (to 2025-06-30) | Check (from 2025-07-01) | t all | Day-level (494 days) |
|---|---|---|---|---|---|
| 09:15 | 13.2 | 16.3 | 9.9 | 9.5 | 13.1, t 6.3 |
| 09:16 | 12.8 | 15.8 | 9.6 | 9.2 | 12.7, t 6.1 |
| 09:20 | 12.1 | 13.8 | 10.3 | 8.8 | 12.1, t 5.9 |
| 09:25 | 11.7 | 13.3 | 9.9 | 8.6 | 11.7, t 5.9 |

The brief's +12 bp holds. The edge is smaller in the check period, and trade-level t-stats overstate significance because trades share a day across five names.
Break-even all-in pre-market entry cost per side: 13.7–15.2 bp on the pooled sample by entry time (dev about 18 bp, check about 12 bp at 09:15).

## 3. Limit rule (buy last print + 5 bp; fill on the first later print at or below the limit before 09:29; else MOO)
Net improvement vs MOO per trade, pooled builders, all sample:

| Order placed | Fill rate | 2 bp | 5 bp | 10 bp | 15 bp |
|---|---|---|---|---|---|
| 09:15 | 53% | +6.4 (t 7.4) | +4.8 | +2.2 | −0.5 |
| 09:20 | 49% | +5.8 | +4.3 | +1.8 | −0.6 |
| 09:25 | 43% | +4.3 | +3.0 | +0.9 | −1.2 |

Check period, 09:15 order: +3.9 bp at 2 bp (t 3.6), −0.3 at 10 bp. Dev period, 09:15: +9.2 at 2 bp.
Day-level (equal-weight builders), 09:15: +6.4 at 2 bp (t 5.2), +2.2 at 10 bp (t 1.8), −0.5 at 15 bp.

Per name at 09:15, 2 bp, all sample: DHI +8.9, LEN +9.1, PHM +8.2, TOL +5.3, KBH +0.1 (34 trade days with a pre-market print).

## 4. Controls (bp per trade, 09:15 entry, pre-market price vs open)
- Flip (−d): −13.2. Mirror image, as expected.
- Lagged signal (yesterday's d): −7.9. Not zero, so part of the pre-market-to-open move leans against yesterday's signal. Today's signal still beats this placebo by about 21 bp.
- SPY placebo: −1.4 (t −2). Only 84 usable days, because the vault SPY 1m file has no 09:00–09:29 bars in 2024–25.

## 5. Capacity
Median print volume over 09:15–09:29 is 302 shares for DHI, 316 LEN, 50 PHM, 85 TOL, and 0 KBH. At 10% participation that is about 30, 32, 5, 8 and 0 shares per day. These are the sizes that could fill at the modelled prices.

## Caveats
- The fill model counts any print at or below the limit as a fill. It has no quote, queue or size data, so it overstates fills at real order sizes.
- Pre-market prints are sparse: 14–29% of days have no print in the 09:15–09:29 window, and on those days the rule falls back to MOO.
- Many variants were tested (4 entries × 5 names, 3 order times × 5 cost levels). The day-level t-stats are the ones to read.

## Verdict
**Do not add a pre-market limit attempt to the live ITB trader.**
- ITB itself is untestable: no pre-market volume in yfinance and no vault candles.
- The builder-only gain is real but small: about +6 bp per trade at 2 bp costs on the full sample, falling to +4 bp in the check period, and roughly zero at 10 bp.
- Capacity is tens of shares per name per day. The trader's position size is far larger, so it could not use this fill.
- To revisit, first obtain ITB pre-market trade and quote data (prints, bid/ask, and volume) and re-run.
