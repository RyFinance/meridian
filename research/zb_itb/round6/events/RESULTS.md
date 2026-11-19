# Round 6 events: when does ZB -> ITB pay?

Frozen helper build('ITB'), net = g_off - 4 bp (official-open entry, 10:30 exit, 2 bp/side), n=570 trades, mean 22.4 bp, t 5.2. Diagnostic only; all splits are post-hoc and many cells are small. t ~ 2 in a thin cell is not evidence.

## 1. Macro days

Release dates are hard-coded FROM MEMORY of the official schedules (BLS, BEA, FOMC). Spot-check against polymarket_arb economic_calendar.csv (US rows):

- CPI: memory 29, calendar 30, in both 28; memory-only ['2025-12-18']; calendar-only ['2025-11-13', '2026-02-11']
- NFP: memory 28, calendar 31, in both 28; memory-only []; calendar-only ['2024-05-03', '2024-08-21', '2025-09-09']
- PCE: memory 29, calendar 30, in both 29; memory-only []; calendar-only ['2026-02-26']
- FOMC: memory 20, calendar 21, in both 20; memory-only []; calendar-only ['2024-05-01']

Categories overlap (e.g. PCE and FOMC can coincide); 'Other' excludes all five. Net = g_off - 4 bp (2 bp/side), official open entry, 10:30 exit.

| group                           |   n |   mean_net_bp |    t |   win_% |
|:--------------------------------|----:|--------------:|-----:|--------:|
| ALL                             | 570 |          22.4 |  5.2 |    58.8 |
| CPI day                         |  26 |          17.7 |  0.8 |    53.8 |
| NFP day                         |  23 |          53.3 |  2.3 |    60.9 |
| PCE day                         |  28 |          33.9 |  2.1 |    64.3 |
| FOMC decision day               |  19 |          43.8 |  2.4 |    68.4 |
| Day after FOMC                  |  19 |          39.4 |  1.6 |    63.2 |
| Any of the above                | 111 |          33.2 |  3.5 |    60.4 |
| Other days (none of the above)  | 459 |          19.8 |  4.1 |    58.4 |
| Monday (weekend gap)            | 109 |          16.8 |  1.7 |    58.7 |
| Non-Monday                      | 461 |          23.7 |  4.9 |    58.8 |
| First day after weekday holiday |  18 |         -54.1 | -2.7 |    27.8 |
| Mon excl. holiday               | 105 |          19.4 |  2   |    59   |


## 1b. By weekday

| group   |   n |   mean_net_bp |   t |   win_% |
|:--------|----:|--------------:|----:|--------:|
| Mon     | 109 |          16.8 | 1.7 |    58.7 |
| Tue     | 118 |          27.1 | 2.9 |    59.3 |
| Wed     | 117 |          25   | 2.5 |    59.8 |
| Thu     | 114 |          13.2 | 1.4 |    57.9 |
| Fri     | 112 |          29.5 | 3   |    58   |


## 2a. ZB trailing 20d realized vol (terciles, features use data through D-1; cutoffs full-sample)

| group                        |   n |   mean_net_bp |   t |   win_% |
|:-----------------------------|----:|--------------:|----:|--------:|
| ZB 20d vol ann% low (<=8.10) | 190 |          31.3 | 3.9 |    63.2 |
| ZB 20d vol ann% mid          | 190 |          19.7 | 2.6 |    55.8 |
| ZB 20d vol ann% high (>9.73) | 190 |          16.2 | 2.3 |    57.4 |


## 2b. 10Y yield level (^TNX close D-1, terciles) and 20d trend

| group                           |   n |   mean_net_bp |   t |   win_% |
|:--------------------------------|----:|--------------:|----:|--------:|
| 10Y level % low (<=4.21)        | 190 |          18.9 | 2.5 |    58.4 |
| 10Y level % mid                 | 190 |          20.1 | 2.7 |    57.4 |
| 10Y level % high (>4.41)        | 190 |          28.1 | 3.8 |    60.5 |
| 10Y rising over 20d             | 302 |          21.3 | 3.7 |    58.6 |
| 10Y falling over 20d            | 268 |          23.6 | 3.6 |    59   |
| 10Y 20d chg (pts) low (<=-0.07) | 190 |          29   | 3.7 |    61.1 |
| 10Y 20d chg (pts) mid           | 190 |          12.9 | 1.7 |    54.7 |
| 10Y 20d chg (pts) high (>0.09)  | 190 |          25.2 | 3.5 |    60.5 |


## 2c. ITB trailing 20d return (close D-1 vs close D-21, terciles)

| group                     |   n |   mean_net_bp |   t |   win_% |
|:--------------------------|----:|--------------:|----:|--------:|
| ITB 20d ret low (<=-0.04) | 190 |          20.1 | 3   |    58.4 |
| ITB 20d ret mid           | 190 |          24.3 | 3.4 |    60.5 |
| ITB 20d ret high (>0.03)  | 190 |          22.7 | 2.7 |    57.4 |


## 2d. Signal direction vs 10Y trend (long ITB = ZB up = yields down)

| group              |   n |   mean_net_bp |   t |   win_% |
|:-------------------|----:|--------------:|----:|--------:|
| long, 10Y falling  | 123 |          23.3 | 2.1 |    52.8 |
| long, 10Y rising   | 141 |          21.1 | 2.2 |    53.9 |
| short, 10Y falling | 145 |          23.8 | 3   |    64.1 |
| short, 10Y rising  | 161 |          21.6 | 3.2 |    62.7 |


## 3. Signal size z = |m| / trailing 60d stdev of m (past-only)

| group        |   n |   mean_net_bp |   t |   win_% |
|:-------------|----:|--------------:|----:|--------:|
| |z| 0-0.25   |  90 |          14.1 | 1.6 |    56.7 |
| |z| 0.25-0.5 | 104 |          27.7 | 3.3 |    66.3 |
| |z| 0.5-0.75 | 106 |          25.5 | 2.3 |    59.4 |
| |z| 0.75-1   |  81 |          17   | 1.5 |    56.8 |
| |z| 1-1.5    |  98 |          12.3 | 1.1 |    56.1 |
| |z| 1.5-2    |  36 |          44.7 | 2.1 |    63.9 |
| |z| 2-inf    |  27 |          67.8 | 2.4 |    59.3 |
| |z| < 0.5    | 194 |          21.4 | 3.6 |    61.9 |
| |z| >= 0.5   | 348 |          25.1 | 4.1 |    58.3 |
| |z| < 1      | 381 |          21.6 | 4.4 |    60.1 |
| |z| >= 1     | 161 |          28.8 | 3   |    58.4 |

Gross (before the 4 bp cost; the column header says mean_net_bp but values are GROSS), same bins:

| group        |   n |   mean_net_bp |   t |   win_% |
|:-------------|----:|--------------:|----:|--------:|
| |z| 0-0.25   |  90 |          18.1 | 2.1 |    60   |
| |z| 0.25-0.5 | 104 |          31.7 | 3.8 |    67.3 |
| |z| 0.5-0.75 | 106 |          29.5 | 2.7 |    62.3 |
| |z| 0.75-1   |  81 |          21   | 1.9 |    58   |
| |z| 1-1.5    |  98 |          16.3 | 1.5 |    57.1 |
| |z| 1.5-2    |  36 |          48.7 | 2.2 |    63.9 |
| |z| 2-inf    |  27 |          71.8 | 2.5 |    63   |

Correlation of |z| with signed gross return: 0.066; with raw ITB first-hour |return|: 0.168


## 3b. |z| quintiles

| group   |   n |   mean_net_bp |   t |   win_% |
|:--------|----:|--------------:|----:|--------:|
| Q1      | 109 |          17.9 | 2.2 |    59.6 |
| Q2      | 108 |          23.6 | 2.7 |    62   |
| Q3      | 108 |          22.7 | 2.2 |    57.4 |
| Q4      | 108 |          21.4 | 2.3 |    62   |
| Q5      | 109 |          33.2 | 2.6 |    56.9 |


## 4. Overnight path (ZB 60m, segments 16:00-20:00, 20:00-02:00, 02:00-08:00, 08:00-09:00 ET; n=544)

Multivariate OLS of ITB raw first-hour return (09:30 official open -> 10:30 close, bp) on the four ZB segment returns (bp). HAC(5) t.

| segment   |   seg stdev bp |   beta (ITB bp per ZB bp) |   t (HAC) |   std beta (ITB bp per 1sd) |   std t |
|:----------|---------------:|--------------------------:|----------:|----------------------------:|--------:|
| 16-20     |          20.12 |                      0.5  |      1.75 |                       10.07 |    1.75 |
| 20-02     |          18.83 |                      0.38 |      1.63 |                        7.11 |    1.63 |
| 02-08     |          26.94 |                      0.59 |      3.2  |                       15.85 |    3.2  |
| 08-09     |          27.56 |                      0.75 |      4.52 |                       20.54 |    4.52 |

All four segments summed (= m): beta 0.585, t 5.33, R2 6.8%. Multivariate R2 7.1%.

Univariate (each segment alone) and what the sign rule earns if only that segment is used:

| segment   |   beta |    t |   R2 % |   sign-rule net bp |   sign-rule t |   sign agrees w/ full m % |
|:----------|-------:|-----:|-------:|-------------------:|--------------:|--------------------------:|
| 16-20     |   0.52 | 1.64 |   0.95 |               6.02 |          1.39 |                     56.07 |
| 20-02     |   0.4  | 1.64 |   0.49 |              -0.37 |         -0.09 |                     57.72 |
| 02-08     |   0.6  | 3.34 |   2.27 |              10.26 |          2.3  |                     75.18 |
| 08-09     |   0.71 | 4.34 |   3.38 |               6.87 |          1.56 |                     58.64 |


## 4b. Sum-of-segments sanity

max |s1+s2+s3+s4 - m| (bp) = 0.00; segments computed with 'last bar at or before' on calendar evening before D (handles Sunday-open / holidays), missing >3h => dropped.


## 4c. Overnight (16:00-08:00) vs last hour (08:00-09:00) direction

| group                                    |   n |   mean_net_bp |   t |   win_% |
|:-----------------------------------------|----:|--------------:|----:|--------:|
| last hour same sign as earlier overnight | 234 |          34.4 | 4.8 |    62   |
| last hour opposes earlier overnight      | 310 |          17.5 | 3.2 |    57.7 |


## 5. Capacity

ITB 09:30-10:30 60m bar: Volume x (open+close)/2, trade days n=570.

| stat | $ first-hour volume | 1% of it |
|---|---|---|
| mean | 60.4M | $604k |
| median | 51.4M | $514k |
| 10th pct | 24.2M | $242k |
| min | 4.6M | $46k |
| last 180d mean | 58.5M | $585k |

Mean by year: 2024: 52.0M, 2025: 61.8M, 2026: 64.9M.
Caveat: 09:30 bar volume includes the opening auction. The volume the strategy adds is MOO (auction) + continuous trading in the same hour; a 1% participation rule on the whole hour is a rough guide. Edge diffuses in 45 min, so own impact scales with size; the 5 bp/side breakeven check (+16 bp) in VERIFICATION gives some room. The signed day-by-day edge vs first-hour dollar volume tercile:

| group     |   n |   mean_net_bp |   t |   win_% |
|:----------|----:|--------------:|----:|--------:|
| $vol low  | 190 |           5.2 | 1   |    54.2 |
| $vol mid  | 190 |          13.6 | 2.2 |    57.4 |
| $vol high | 190 |          48.4 | 4.9 |    64.7 |

## Plain-English summary

**Where the edge comes from.** It is broad, not event-driven. Mean net 22 bp over 570 trades. Excluding the 18 first-days-after-holidays it is +24.9 bp (t 5.7). On the 459 days with no CPI, NFP, PCE or FOMC nearby it is still +19.8 bp (t 4.1). Macro days pay more (NFP +53, PCE +34, FOMC day +44, day after FOMC +39 bp; "any" +33 bp, t 3.5) but each cell has only 19-28 trades (t 1.6-2.4), so this is suggestive, not established. CPI days are +18 bp (n 26, t 0.8): no more than average. Weekdays are all positive (Thu weakest, +13 bp); Mondays are +17 bp (t 1.7), a bit below the non-Monday +24 bp, not a distinct regime.

**When it does not work: after holidays.** The first session after a weekday market holiday (including the Jan-2025 mourning closure) lost -54 bp net on average (n 18, t -2.7, 5 wins of 18). It is a post-hoc cut among about 12 groupings, so the multiple-comparison discount is real, but the mechanism is plausible: on holiday the Globex session is shortened and the 15:00 anchor / 08:00 end bar span a thin or irregular overnight. Four of the 18 trades lost 110-230 bp each (2024-09-03, 2026-02-17, 2026-07-06, 2026-09-08), so the mean is driven by a few large losses; the other 14 average about -20 bp. This is the single largest live risk found. Not enough to call a filter (n 18), but worth logging in the forward test.

**Regime.** Positive in every tercile. The edge is strongest when ZB volatility is low (+31 bp, t 3.9 vs +16 bp at high vol, t 2.3), the opposite of what a macro-shock story would predict; the difference between terciles is not significant. 10Y level, 10Y trend and ITB's own trailing 20-day return make no real difference (all +19 to +28 bp; the middle tercile of 10Y 20-day change is weakest at +13 bp, t 1.7, likely noise). Long and short signals earn the same whether yields have been rising or falling; win rate is about 53% on longs and 63% on shorts, with similar mean net (shorts win more often but with smaller average winners).

**Signal size.** No floor below which trades are noise. Lowest |z| bin (0-0.25) is +14 bp (t 1.6, gross +18 bp), below average but positive. Highest |z| (>1.5, n 63) pays most (+45 and +68 bp, t about 2.1-2.4), but 1.0-1.5 is the weakest bin (+12 bp), so it is not monotone. Correlation of |z| with signed gross return is only 0.07. Filtering on size would give up trades that still pay 2-4x the cost. No recommendation.

**Overnight path.** All four segments are positively related to the ITB first hour; no single segment is the whole story. In the joint regression the last hour (08:00-09:00, includes 08:30 data) has the largest, most significant coefficient (std beta 20.5 bp per 1 sd, t 4.5), then 02:00-08:00 (15.9 bp, t 3.2), with 16:00-20:00 (10.1 bp, t 1.8) and 20:00-02:00 (7.1 bp, t 1.6) weaker individually. The coefficients are similar in size per bp of ZB move (0.4-0.75), consistent with homebuilders pricing the whole overnight move with a uniform partial lag and 02:00-08:00 and the last hour being the largest in variance. 02:00-08:00 (Europe) alone gives the best sign-rule (+10 bp, t 2.3, and agrees with the full signal 75% of days); no segment alone beats the full 16:00->09:00 signal. Where the final hour confirms the earlier overnight move the trade earns +34 bp (n 234); where it reverses it, +17.5 bp (n 310): both positive. Total R2 is only 7%: the edge is a small tilt on a noisy outcome (win rate 59%).

**Capacity.** ITB's 09:30-10:30 bar trades about $60M on average (median $51M, 10th percentile $24M, min $4.6M), rising year over year (2024 $52M, 2026 $65M). 1% participation is about $0.5-0.6M per trade, $0.24M on a thin day. Edge by first-hour dollar volume tercile: low +5 bp, mid +14 bp, high +48 bp (t 4.9). Caution: volume is measured on the same day as the move, so this is contemporaneous (big move days have high volume), not a tradable filter. It does say the edge lives on active days, and thin days earn little after cost. Practical size limit is probably a few hundred thousand dollars, set by the 1%-of-volume participation rule rather than by the edge.

## Main live risks (diagnostic)
1. Post-holiday sessions (n 18, -54 bp). Largest tail losses seen (-110 to -230 bp per trade). Log them; do not drop the rule on this alone.
2. Thin-volume days: edge is near zero (+5 bp, t 1.0) in the lowest-volume third of days; wider spreads on those days would erase it.
3. Dependence on a few big-|z| days: |z|>1.5 trades pay +45-68 bp vs about +20 bp for the rest. If big overnight moves become rarer the average falls toward +20 bp or lower.
4. Year drift: first period (to mid-2025) +16.6 bp, second (since 2025-07) +27.2 bp, so no sign of decay in this sample, but the regime caveat in VERIFICATION still applies (no edge before 2020).
5. Macro-day concentration is not the explanation: removing all CPI/NFP/PCE/FOMC days leaves +19.8 bp, t 4.1.

## Method notes
- Frozen helper `build('ITB')`, net = g_off - 0.0004. Raw-return regression uses the official-open entry. Code: `events.py`; per-trade table: `event_table.csv`.
- Release dates are typed from memory. Calendar mismatches: calendar has CPI 2025-11-13 (October 2025 CPI was cancelled; November CPI came out 2025-12-18, which the calendar lists only under Core Inflation) and 2026-02-11 (I used 2026-02-13 for CPI and 2026-02-11 for NFP; the calendar lists both on 02-11, which looks like a mislabel or a delay I cannot confirm); extra NFP entries (2024-05-03, 2024-08-21 benchmark revision, 2025-09-09 benchmark revision) and one extra PCE (2026-02-26) and FOMC (2024-05-01, outside the sample for trades) are non-matching. The 2025 shutdown-delayed releases (NFP 2025-11-20 and 2025-12-16, PCE 2025-12-05 and 2026-01-22) agree with the calendar. 2026 dates beyond mid-October 2026 were scheduled, not observed, and do not affect trades (data ends 2026-10-16).
- Tercile cutoffs are full-sample (feature values are past-only). Holiday dates are inferred from missing weekday sessions in ITB's 60m data.
- About 12 groupings and 50+ cells were tested post-hoc; treat |t| near 2 as noise.
