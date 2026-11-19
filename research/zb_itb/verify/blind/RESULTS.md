# ZB overnight -> ITB first-hour: blind re-implementation

Inputs: `ZB_F_60m.parquet` and `ITB_60m.parquet` only. Script: `backtest.py` (labels verified by `label_check.py`).

## Conventions used

- Both parquet indexes are tz-aware `America/New_York` (checked; `tz_convert` is a no-op). All time matching is wall-clock ET via tz-aware Timestamps, so DST is handled by pandas, not by hand.
- **Bar timestamps mark the START of each bar** (both ZB and ITB). Evidence in the 'Label convention' section. So the 'ZB bar that ENDS at 16:00 ET' is the bar labelled 15:00, and the 'bar that ENDS at 09:00 ET' is the bar labelled 08:00.
- prev = previous date (in the sorted list of dates that have an ITB 09:30 bar). D ranges over all dates that have an ITB 09:30 bar from the first D where P0, P1, entry and exit all exist (2024-05-29). ITB days before that (131, all before the ZB file starts) are not counted.
- d = sign(ln(P1/P0)); d=0 only if P1==P0 exactly (no trade, no cost). net = gross - 0.0004 on each trade. sd uses ddof=1.
- Annualised return = end_equity^(1/years)-1 with end_equity=exp(sum(net)) and years = (last date - first date of the window in calendar days)/365.25 (window = first/last ITB trading day D in the window, whether or not that day trades). Max drawdown includes the starting equity of 1.0 as the first peak.
- Sharpe = mean/sd*sqrt(252). Primary Sharpe uses the per-trade net series (one trade per day, no-signal days omitted). The zero-filled daily-series Sharpe is shown alongside. For long-only, non-long days earn 0 in the daily series.

## Long/short strategy (d = +1 long ITB, d = -1 short ITB)

### Long/short

| metric | FULL | <=2026-08-10 | 2026-08-11..2026-10-16 |
|---|---|---|---|
| n trades | 570 | 524 | 46 |
|   of which long (d=+1) | 264 | 246 | 18 |
|   of which short (d=-1) | 306 | 278 | 28 |
| no-signal days (missing P0/P1 bar) | 14 | 14 | 0 |
| flat days (P1==P0, d=0, no trade) | 12 | 10 | 2 |
| ITB trading days D in window | 596 | 548 | 48 |
| mean gross (bp/trade) | 25.711 | 26.277 | 19.262 |
| mean net (bp/trade) | 21.711 | 22.277 | 15.262 |
| sd net (bp/trade, ddof=1) | 103.18 | 103.77 | 97.07 |
| t-stat net (mean/sd*sqrt(n)) | 5.024 | 4.914 | 1.066 |
| win rate net (net>0, per trade) | 0.5807 | 0.5821 | 0.5652 |
| end equity exp(sum net), start=1 | 3.4470 | 3.2133 | 1.0727 |
| years (calendar days/365.25) | 2.3819 | 2.1985 | 0.1807 |
| annualised compounded return (net) | 68.1253% | 70.0556% | 47.4795% |
| max drawdown of compounded net equity | -12.3384% | -12.3384% | -3.6404% |
| Sharpe net, ann. sqrt(252), per-trade series | 3.340 | 3.408 | 2.496 |
| Sharpe net, ann. sqrt(252), daily series (0 on non-trade days) | 3.264 | 3.329 | 2.443 |
| mean net (bp/day, zero-filled) | 20.764 | 21.301 | 14.626 |
| mean gross (bp/day, zero-filled) | 24.589 | 25.126 | 18.459 |
| t-stat net on zero-filled daily series | 5.019 | 4.909 | 1.066 |

Alternative annualisation (years = (last-first+1 days)/365.25): FULL: 68.0251%; <=2026-08-10: 69.9434%; 2026-08-11..2026-10-16: 46.6267%

max drawdown excluding the initial 1.0 as a peak: FULL: -12.3384%; <=2026-08-10: -12.3384%; 2026-08-11..2026-10-16: -3.6404%

## Long-only version (only d = +1 trades; every other day earns 0)

### Long-only

| metric | FULL | <=2026-08-10 | 2026-08-11..2026-10-16 |
|---|---|---|---|
| n trades | 264 | 246 | 18 |
|   of which long (d=+1) | 264 | 246 | 18 |
|   of which short (d=-1) | 0 | 0 | 0 |
| no-signal days (missing P0/P1 bar) | 14 | 14 | 0 |
| flat days (P1==P0, d=0, no trade) | 12 | 10 | 2 |
| ITB trading days D in window | 596 | 548 | 48 |
| mean gross (bp/trade) | 25.604 | 28.513 | -14.156 |
| mean net (bp/trade) | 21.604 | 24.513 | -18.156 |
| sd net (bp/trade, ddof=1) | 115.76 | 114.93 | 123.00 |
| t-stat net (mean/sd*sqrt(n)) | 3.032 | 3.345 | -0.626 |
| win rate net (net>0, per trade) | 0.5341 | 0.5447 | 0.3889 |
| end equity exp(sum net), start=1 | 1.7689 | 1.8276 | 0.9678 |
| years (calendar days/365.25) | 2.3819 | 2.1985 | 0.1807 |
| annualised compounded return (net) | 27.0545% | 31.5595% | -16.5447% |
| max drawdown of compounded net equity | -6.6400% | -6.1724% | -6.6400% |
| Sharpe net, ann. sqrt(252), per-trade series | 2.963 | 3.386 | -2.343 |
| Sharpe net, ann. sqrt(252), daily series (0 on non-trade days) | 1.955 | 2.243 | -1.451 |
| mean net (bp/day, zero-filled) | 9.570 | 11.004 | -6.809 |
| mean gross (bp/day, zero-filled) | 11.341 | 12.800 | -5.309 |
| t-stat net on zero-filled daily series | 3.006 | 3.308 | -0.633 |

Alternative annualisation (years = (last-first+1 days)/365.25): FULL: 27.0195%; <=2026-08-10: 31.5147%; 2026-08-11..2026-10-16: -16.3191%

max drawdown excluding the initial 1.0 as a peak: FULL: -6.6400%; <=2026-08-10: -6.1724%; 2026-08-11..2026-10-16: -6.6400%

## Calendar-year breakdown (long/short trades)

|   year |   n |   mean_gross_bp |   mean_net_bp |
|-------:|----:|----------------:|--------------:|
|   2024 | 139 |          23.463 |        19.463 |
|   2025 | 243 |          22.569 |        18.569 |
|   2026 | 188 |          31.433 |        27.433 |

## No-signal days (no trade because a required ZB bar does not exist exactly)

Total from 2024-05-29 on: 14 (list also in `no_signal_days.csv`).

| date D | prev | reason |
|---|---|---|
| 2024-07-03 | 2024-07-02 | P1 bar (ZB ending 09:00 ET on D) missing |
| 2024-07-05 | 2024-07-03 | P0 bar (ZB ending 16:00 ET on prev=2024-07-03) missing |
| 2024-11-29 | 2024-11-27 | P1 bar (ZB ending 09:00 ET on D) missing |
| 2024-12-02 | 2024-11-29 | P0 bar (ZB ending 16:00 ET on prev=2024-11-29) missing |
| 2024-12-24 | 2024-12-23 | P1 bar (ZB ending 09:00 ET on D) missing |
| 2024-12-26 | 2024-12-24 | P0 bar (ZB ending 16:00 ET on prev=2024-12-24) missing |
| 2025-07-03 | 2025-07-02 | P1 bar (ZB ending 09:00 ET on D) missing |
| 2025-07-07 | 2025-07-03 | P0 bar (ZB ending 16:00 ET on prev=2025-07-03) missing |
| 2025-11-28 | 2025-11-26 | P1 bar (ZB ending 09:00 ET on D) missing |
| 2025-12-01 | 2025-11-28 | P0 bar (ZB ending 16:00 ET on prev=2025-11-28) missing |
| 2025-12-24 | 2025-12-23 | P1 bar (ZB ending 09:00 ET on D) missing |
| 2025-12-26 | 2025-12-24 | P0 bar (ZB ending 16:00 ET on prev=2025-12-24) missing |
| 2026-02-03 | 2026-01-30 | P0 bar (ZB ending 16:00 ET on prev=2026-01-30) missing |
| 2026-07-15 | 2026-07-10 | P0 bar (ZB ending 16:00 ET on prev=2026-07-10) missing |

Flat days (P1==P0 exactly, d=0, no trade): 12 -> 2024-06-25, 2024-07-12, 2024-07-30, 2024-08-14, 2024-11-14, 2025-05-06, 2026-01-09, 2026-01-15, 2026-06-01, 2026-08-05, 2026-08-21, 2026-09-04

Zero-volume bars used as P0: 1 ['2025-02-27']; as P1: 3 ['2024-08-29', '2024-11-27', '2025-03-07'] (kept: the bar exists and has a price).

## Sensitivity: if the labels were (wrongly) read as bar END
P0 := bar labelled 16:00, P1 := bar labelled 09:00. Full sample: n=572, mean gross 21.514 bp, mean net 17.514 bp, t=3.997, win 0.5507, ann 52.29%. (Shown only so a mismatch against another implementation can be diagnosed; it is NOT the answer.)

## Label convention evidence

### ZB label structure

- index tz = `America/New_York`, unique = True, monotonic = True, bars = 13571, first = 2024-05-26 18:00:00-04:00, last = 2026-10-16 16:00:00-04:00.
- Sunday labels: 18:00, 19:00, 20:00, 21:00, 22:00, 23:00  (Globex re-opens Sunday 18:00 ET).
- Mon-Thu label hours present: 00:00..23:00 with a hole only at 17:00 (maintenance hour 17:00-18:00 ET): 17:00 label count = 1 (one stray zero-volume flat bar), 18:00 label count = 577.
- Friday label hours: 00:00..16:00 (last label 16:00, nothing after; Globex closes Friday 17:00 ET).
- If labels were bar END times, Sunday's first label would be 19:00 and every session's last label would be 17:00. The data show the opposite (first Sunday label 18:00, last weekday label 16:00, 17:00 absent). => **labels = bar START** (each bar covers label .. label+1h).
- ITB: labels 09:30,10:30,...,15:30 (15:30 is the half-hour stub to 16:00); the 09:30 label exists, an END-labelled series would start at 10:30. => START as well.

Event check (mean High-Low on event days / mean on other days, by bar label):

| label | 12:00 | 13:00 | 14:00 | 15:00 | 16:00 |
|---|---|---|---|---|---|
| FOMC statement 14:00 ET (19 days) | 0.78 | 0.79 | 3.21 | 1.93 | 1.44 |

| label | 06:00 | 07:00 | 08:00 | 09:00 | 10:00 |
|---|---|---|---|---|---|
| Jobs report 08:30 ET (23 days) | 0.94 | 0.86 | 2.86 | 1.33 | 1.35 |

The 14:00 ET FOMC release produces its range spike in the bar labelled 14:00 (not 15:00), and the 08:30 ET releases in the bar labelled 08:00 (not 09:00): consistent only with START labels.

Self-check: P0/P1 re-derived purely by label (15:00 / 08:00) match the end-time lookup for every day: P0 True, P1 True.

## Data oddities

### ZB (ZB=F 60m) oddities

Dates with a non-standard hour set: 25 of 709 (standard = Sun 18-23h; Mon-Thu 00-16h + 18-23h; Fri 00-16h).

| date | what |
|---|---|
| 2024-07-03 Wed | HALF-DAY: only 4 bars labelled 09:30/10:30/11:30/12:30 (:30 grid); all other hours absent |
| 2024-11-29 Fri | HALF-DAY: only 4 bars labelled 09:30/10:30/11:30/12:30 (:30 grid); all other hours absent |
| 2024-12-24 Tue | HALF-DAY: only 4 bars labelled 09:30/10:30/11:30/12:30 (:30 grid); all other hours absent |
| 2024-12-31 Tue | missing 18:00..23:00 (6 bars) |
| 2025-01-09 Thu | missing 14:00,15:00,16:00 |
| 2025-03-10 Mon | extra 17:00 |
| 2025-04-17 Thu | missing 18:00..23:00 (6 bars) |
| 2025-05-26 Mon | missing 13:00..16:00 (4 bars) |
| 2025-06-19 Thu | missing 13:00..16:00 (4 bars) |
| 2025-07-03 Thu | HALF-DAY: only 4 bars labelled 09:30/10:30/11:30/12:30 (:30 grid); all other hours absent |
| 2025-07-04 Fri | missing 13:00..16:00 (4 bars) |
| 2025-09-15 Mon | missing 18:00,19:00 |
| 2025-10-06 Mon | missing 18:00..23:00 (6 bars) |
| 2025-10-07 Tue | missing 00:00..03:00 (4 bars) |
| 2025-11-28 Fri | HALF-DAY: only 4 bars labelled 09:30/10:30/11:30/12:30 (:30 grid); all other hours absent |
| 2025-12-24 Wed | HALF-DAY: only 4 bars labelled 09:30/10:30/11:30/12:30 (:30 grid); all other hours absent |
| 2025-12-31 Wed | missing 18:00..23:00 (6 bars) |
| 2026-01-18 Sun | missing 18:00..22:00 (5 bars) |
| 2026-01-30 Fri | missing 11:00..16:00 (6 bars) |
| 2026-02-02 Mon | missing 00:00..12:00 (13 bars) |
| 2026-04-19 Sun | missing 23:00 |
| 2026-04-20 Mon | missing 00:00..04:00 (5 bars) |
| 2026-05-14 Thu | missing 18:00,19:00,20:00 |
| 2026-07-10 Fri | missing 12:00..16:00 (5 bars) |
| 2026-07-15 Wed | missing 00:00..12:00 (7 bars) |

- Zero-volume bars: 519 of 13571; 238 at label 16:00 (of 590), 237 at label 18:00, the rest 44 scattered. These carry normal-looking OHLC (not flat); likely a volume-reporting quirk. The bars actually used (labels 15:00 and 08:00) are almost never zero-volume (see list in results).
- No duplicated timestamps; no NaNs; Close == Adj Close everywhere; last ZB bar is 2026-10-16 16:00 (volume 0).
- A single stray flat zero-volume bar labelled 17:00 on 2025-03-10 (the Monday after the US spring-forward); harmless.
- Half-days (NYSE 1pm closes): the ZB file contains ONLY the four :30-grid bars for 2024-07-03, 2024-11-29, 2024-12-24, 2025-07-03, 2025-11-28, 2025-12-24. Hence on those D the 09:00 bar is missing (no trade) and on the next ITB day the 16:00 bar of prev is missing (no trade).

### ITB (60m) oddities

Days whose bar set is not the standard 7 bars (09:30..15:30):

- 2023-11-24: 09:30,10:30,11:30 (NYSE half-day: 12:30-13:00 stub bar absent)
- 2024-07-03: 09:30,10:30,11:30 (NYSE half-day: 12:30-13:00 stub bar absent)
- 2024-11-29: 09:30,10:30,11:30 (NYSE half-day: 12:30-13:00 stub bar absent)
- 2024-12-24: 09:30,10:30,11:30 (NYSE half-day: 12:30-13:00 stub bar absent)
- 2025-07-03: 09:30,10:30,11:30 (NYSE half-day: 12:30-13:00 stub bar absent)
- 2025-11-28: 09:30,10:30,11:30 (NYSE half-day: 12:30-13:00 stub bar absent)
- 2025-12-24: 09:30,10:30,11:30 (NYSE half-day: 12:30-13:00 stub bar absent)
- 2026-01-30: 09:30
- 2026-02-02: 13:30,14:30,15:30
- 2026-07-10: 09:30,10:30,11:30,12:30

Non-holiday weekdays with no ITB bars at all (data gap): 2026-07-13, 2026-07-14.
Weekdays that have ITB bars although listed as NYSE holidays: none.
Days with ITB bars but no 09:30 bar (so not a trade day D): 2026-02-02.
Zero-volume ITB bars: 10; two of them are 09:30 bars (2023-12-13, 2024-05-16) but both predate the first trade day. No NaNs, no duplicates.
ITB 09:30 bars in file: 727; NYSE weekdays in range that are not holidays: 730.

Days D where `prev` (previous day with an ITB 09:30 bar) is NOT the preceding NYSE trading day because of ITB gaps: D=2026-02-03 prev=2026-01-30 (NYSE prior day 2026-02-02); D=2026-07-15 prev=2026-07-10 (NYSE prior day 2026-07-14).

### DST handling

Unique UTC offsets in the ZB index: -0400, -0500; same for ITB when loaded. US transitions inside the sample: 2024-11-03 (fall back), 2025-03-09 (spring fwd), 2025-11-02 (fall back), 2026-03-08 (spring fwd) - all fall on Sundays, i.e. inside the Globex weekend close (re-open 18:00 ET), so no bar is duplicated/skipped by the 02:00 transition itself.
Label-hour vs UTC check: bars labelled 18:00 ET sit at 22:00 UTC in EDT and 23:00 UTC in EST (and 08:00 ET at 12:00/13:00 UTC), i.e. the stored labels follow wall-clock ET in both regimes.

Trades on the first session after each transition (P0 label of prev, P1 label of D, with offsets):

| D | prev | P0 bar label (ends 16:00 ET) | P1 bar label (ends 09:00 ET) | P0 | P1 | d |
|---|---|---|---|---|---|---|
| 2024-11-04 | 2024-11-01 | 2024-11-01 15:00:00-04:00 (present) | 2024-11-04 08:00:00-05:00 (present) | 116.65625 | 118.0 | 1.0 |
| 2025-03-10 | 2025-03-07 | 2025-03-07 15:00:00-05:00 (present) | 2025-03-10 08:00:00-04:00 (present) | 116.6875 | 117.53125 | 1.0 |
| 2025-11-03 | 2025-10-31 | 2025-10-31 15:00:00-04:00 (present) | 2025-11-03 08:00:00-05:00 (present) | 117.4375 | 117.09375 | -1.0 |
| 2026-03-09 | 2026-03-06 | 2026-03-06 15:00:00-05:00 (present) | 2026-03-09 08:00:00-04:00 (present) | 116.0 | 115.5625 | -1.0 |

Note on 2026-02-03 and 2026-07-15: `prev` skips ITB-missing days (2026-02-02 has no 09:30 bar; 2026-07-13/14 absent), so P0 is taken on 2026-01-30 / 2026-07-10 where ZB has no 15:00 bar -> no trade. Reading `prev` as the prior NYSE day instead would add at most these two trades.