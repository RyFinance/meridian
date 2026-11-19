# Index / ETF overnight-gap study (SPY, QQQ, IWM, TQQQ, SQQQ, SOXL, UVXY)

**Data.** LSE Terminal was not running (`open` is blocked in the sandbox), so yfinance only. Daily adjusted OHLC: SPY 1993-, QQQ 1999-, IWM 2000-, leveraged 2010-11-. VIX daily. 60m (ETFs ~2023-11+, ES/NQ futures 2024-05+). Everything cut at 2026-08-10 (sealed holdout untouched).
**Split.** Daily dev <= 2022-06-30, check 2022-07-01..2026-08-10. Futures dev <= 2025-06-30 (short sample).
**Entry** = day's open print (gap known at open). **Stop** resolved worst-case (stop before target inside a daily bar). **Costs** 2 bp/side (4 bp RT).
**Variants.** Index fade grid 288 (3 sym x 2 gap dir x 3 gap bins 0.25-1.5% x 4 targets x 4 stops). Leveraged fade grid 384. Regime cells 105. Futures regressions 24, futures rules 12. Total ~813 tested. Flip control computed for every fade (same |distance|, trade with the gap).

## Results (dev -> check, net bp per trade)
| Rule | Dev n / win / mean / t | Check n / win / mean / t | Flip dev / chk |
|---|---|---|---|
| (A) SPY, gap-down 1.0-1.5%: long open, exit prev close, no stop | 171 / 63% / +11.5 / 1.05 | 42 / 64% / +34.3 / 2.76 | -7.6 / -31.1 |
| (B) IWM, same | 181 / 58% / +9.8 / 1.03 | 68 / 53% / +13.4 / 1.11 | -16.2 / -38.0 |
| (C) SPY, same, stop 1.5% | 171 / 57% / +6.5 / 0.76 | 42 / 60% / +19.5 / 1.36 | -15.6 / -33.0 |

Full-sample (A): n 213, win 63.4%, mean +16.0 bp, t 1.76, avg win +94 bp, avg loss -119 bp, 73% of years positive.

**Classic gap fill (1).** Same-day fill probability (prior close inside day range): SPY 0.25-0.5% gap ~60% (up) / 66% (down); 0.5-1.0% ~47%; 1.0-1.5% 30-42%. QQQ and IWM higher at small gaps (up to 71%). In check, large-gap fill rates fell sharply (SPY up 1.0-1.5%: 31% dev -> 19% check). Fill-target fades with stops: 10 of 72 fill variants had dev mean > 0; 5 were positive in both halves.
**Gap size/direction and regime (2).** Only 8 of 105 continuation cells are net-positive in both dev and check, and dev/check sign agreement is 56% (near coin-flip). Reversal dominates only in calm-to-mid cells and is not stable. No regime edge survives.
**Overnight futures path (3).** ES and NQ moves before 09:00 ET explain the SPY/QQQ gap almost 1:1 (beta 0.93-1.19, combined R2 0.92-0.94). Late (08:00-09:00) moves carry into open-to-close only weakly (beta 0.38, t 2.2 for ES; 0.28, t 1.6 for NQ), and sign rules on late moves net -4 to +4 bp with |t| under 1.2. Asia (16:00-02:00) moves revert intraday (beta -0.30, t -4.3 ES; -0.24, t -3.6 NQ), but a fade rule nets only +1 to +2 bp (gross ~5 bp, dev/check, t under 0.6). Europe-to-first-hour gross +3.0 bp (t 1.9) is below the 4 bp round trip.
**Leveraged ETFs (4).** TQQQ/SQQQ gap = 3x / -3x QQQ gap (mean tracking error under 4 bp, MAD ~9-11 bp). SOXL vs SOXX: ratio ~3 but MAD 39 bp (not tight). UVXY vs VIX spot only (no VIX futures available). Best UVXY fill fades (gap-up 1-1.5%, short: dev +29.6, chk +47.3) compare with unconditional short UVXY drift of +15.5 bp/day net, so most of it is decay, not gap. Flip is negative in both halves.
**High win-rate small-target fades (5).** Small-target variants (0.10%/0.25%): index median dev win 68%, median dev mean -22 bp. 35 index variants have dev win >= 80%; only 2 of them have dev mean > 0. Leveraged: 48 variants with dev win >= 80%; only 6 have dev mean > 0. Win-rate-high, mean-negative is the typical outcome. Fail.

## Best rule (code-ready)
At 09:30 ET, if SPY (or IWM) gaps down by 1.0% to 1.5% versus the prior 16:00 close: buy at the open, sell at the prior close if reached, otherwise at the 16:00 close. No stop. Costs 4 bp RT.

## Verdict
- Rule (A) and (B): **WEAK**. Check mean is higher than dev mean, so no decay, but check n is 42-68 and check t 1.1-2.8. Across 288 index variants, a single t of 2.8 is consistent with chance once you correct for the search. The flip is negative in both halves, so this is not plain drift.
- Futures overnight path, leveraged ETFs, small-target fades, regime filters: **NONE**.
- Recommendation: the lead runs rule (A) once on the sealed holdout (2026-08-11 onward); no re-tuning.

## Caveats
- Daily stops use worst-case ordering; no 1m or 60m stop verification was done.
- Entry at the open print assumes an at-open fill; a real MOO fill may be worse.
- Overnight futures sample is 541 days; leveraged UVXY has no VIX futures series.
- Scripts and outputs: `daily_gaps.py`, `futures_overnight.py`, `summarize_gaps.py`; CSVs `fade_grid_*.csv`, `regime_continuation.csv`, `futures_rules.csv`, `unconditional_oc_baseline.csv`.
