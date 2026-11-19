# Round 9 / auctions: ZB auction-hour move -> ITB intraday and overnight

Verdict: **NONE**

## Data and what was actually used
- TreasuryDirect API: blocked. curl fails with an SSL "self signed certificate in certificate chain" error (sandbox/proxy TLS interception). Not bypassed with -k.
- Auction calendar: local `data/treasury/auctions_fiscaldata_raw.json` (dates, tenor, reopening, TIPS/FRN flags). No yields and no result times.
- Result times: `data/public_scout/treasury_auctions/notes_2024_sample.json` (2023-12..2024-12, Notes only, has highYield). Only 63 rows, so the tail proxy covers 2024 only. All other auctions assumed 13:00 ET (2 of 191 dates in the sample show 11:30).
- Prices: frozen caches in `research/zb_itb/verify/yf_cache/` (ZB_F_60m, ITB_60m, SPY_60m). ITB bars are :30-labeled.
- Window 2024-05-28..2026-10-16. Dev 2024-05-28..2025-06-30, check 2025-07-01..2026-10-16.
- Costs: 2 bp/side = 4 bp round trip, as in verify/f3_canonical.py.
- Auction-day count is 191 dates (170 with non-zero signal), not the 60-80 expected. Coupon auctions 2/3/5/7/10/20/30 incl. reopenings run about 2 per week.

## Rule
- Signal d = sign(log(Close / Open) of ZB 60m bar starting 13:00 ET). Known by 14:00.
- intra: d x log(ITB Close 15:30 bar / Open 14:30 bar) - 4 bp.
- over: d x log(ITB Close 09:30 bar next day / Open 14:30 bar) - 4 bp.
- Control: same rule on non-auction days. Flip: -net - 8 bp. Placebo: SPY, same rule.

## Results (net bp, t)
| group | leg | dev | check | all |
|---|---|---|---|---|
| AUCTION days (n 83/87/170) | intra | +0.9 (t 0.2) | -1.0 (t -0.2) | -0.1 (t 0.0) |
| AUCTION days | over | -33.3 (t -1.9) | +11.2 (t 0.6) | -10.5 (t -0.8) |
| CONTROL non-auction (n 166/188/354) | intra | -1.0 (t -0.3) | -4.0 (t -1.0) | -2.6 (t -1.0) |
| CONTROL non-auction | over | +3.8 (t 0.3) | -17.8 (t -1.5) | -7.7 (t -0.9) |
| FLIP auction (opposite dir) | intra | -8.9 (t -1.7) | -7.0 (t -1.6) | -7.9 (t -2.3) |
| FLIP auction | over | +25.3 (t 1.4) | -19.2 (t -1.1) | +2.5 (t 0.2) |
| SPY placebo, auction days | intra | -0.8 (t -0.2) | -0.4 (t -0.2) | -0.6 (t -0.3) |
| SPY placebo, auction days | over | -8.5 (t -1.0) | +3.7 (t 0.6) | -2.3 (t -0.4) |

- Auction minus control, intra: +2.5 bp, Welch t 0.57. Overnight: -2.8 bp, t -0.19.
- Strict 10y/30y subset (n 53): intra dev -16.8 bp (t -2.1), check +4.5 bp (t 0.5), all -5.2 bp (t -0.8).
- Tail proxy (2024 notes, n 33, highYield minus averageMedianYield): corr with ZB hour move -0.44. Sign(tail) x intra +8.1 bp, t 0.9. Descriptive only.
- Same-hour check: ITB 13:30 bar on ZB 13:00 bar on auction days, corr 0.39, beta 0.65. ITB reacts within the hour, so no obvious lag to trade.

## Reading
- Intraday, auction-hour direction does not predict the 14:30-15:30 ITB move. Auction days look like control days.
- The flip is significantly negative intraday (t -2.3), but the flip is the opposite sign of a near-zero effect, so it is a cost artefact, not a reversal to trade.
- Dev is marginal on the overnight leg and on the strict 10y/30y subset (|t| about 2 with many variants). The check period shows nothing. Treat as noise.
- Variants tried: 2 legs x 2 directions x 3 subsets, plus tail proxy and diagnostics, about 15 tests. |t| near 2 is noise.

## Caveats
- Result times are assumed 13:00 for about 90% of dates; a wrong time shifts the signal bar.
- Tail proxy has n 33 and is 2024-only.
- No yields in the local calendar, so no yield surprise.

Files: study.py, events.csv, summary.csv (same folder).
