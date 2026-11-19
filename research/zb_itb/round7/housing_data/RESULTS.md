# Round 7: housing data releases vs ITB (2024-05..2026-10-16)
Script run.py, raw output out.txt. Costs 2 bp/side ITB (4 bp round trip). Bars 60m start-labeled; 09:30 bar = 09:30-10:30 (contains a 10:00 release).

## Release dates: NOT purely from memory
I could not reliably recall every 2025-26 date (the Oct-Nov 2025 shutdown shifted Census releases). Dates come from the
economic_calendar.csv US rows, which carry actual values, so each row was really released. Rows with no actual were dropped,
as were later duplicates of the same period. The calendar's time column is inconsistent (UTC, with shifting offsets), so only
the DATE is used. I assume 08:30 ET (starts) and 10:00 ET (new/existing/pending, construction, NAHB) from the official
schedules, and 09:00 ET for Case-Shiller. Unchecked: from memory I believe housing starts for June 2025 was published
2025-07-17, while the calendar says 07-18. One-day errors would blur the results toward zero. Counts:
starts 23, new home 24, existing 27, pending 27, construction 25, NAHB 27, Case-Shiller 27. The 10:00 union is 127 days.
No day has both 08:30 and 10:00 releases.

## (a) 10:00 days: ITB post-release continuation (net of 4 bp; flip = trade the opposite direction)
Signal = sign of the 10:30 bar (10:30-11:30). Target = 11:30 -> 15:30 close. Dev/check split: dev <= 2025-06-30.
| set | n | mean net | t | flip net | t |
|---|---|---|---|---|---|
| ALL 10:00 | 127 | +10.6 | 1.31 | -18.6 | -2.31 |
| ALL, dev | 69 | +8.0 | 0.79 | | |
| ALL, check | 58 | +13.7 | 1.06 | | |
| new home | 24 | -23.7 | -1.60 | | |
| existing | 27 | +1.6 | 0.09 | | |
| pending | 27 | +43.1 | 2.26 | -51.1 | -2.67 |
| construction | 25 | +21.1 | 1.07 | | |
| NAHB | 26 | +9.0 | 0.61 | | |
| non-release days (control) | 544 | -0.5 | -0.12 | -7.5 | -2.02 |
| SPY on the same ALL days | 126 | +1.5 | 0.33 | | |
- First post-release hour vs the next hour (10:30 bar sign -> 11:30 bar): ALL +1.8 bp gross, t 0.5 (net -2.2). Pending is -15.4 net (t -2.2), the opposite sign to its own 11:30-close result. A real drift would not do that, so both are noise.
- The 09:30 bar sign (contains the release) -> 10:30 to close: ALL -2.7 net, t -0.27. Nothing there.
- Placebo permutation (127 random non-release days, same rule): real gross 14.6 bp vs placebo mean 3.6 bp, two-sided p = 0.058. The positive sign is consistent but gross is only ~15 bp for a 4 bp cost, and the result is weaker than the ZB rule.
- Variant count: about 7 sets x 3 targets = 21, plus a flip for each. The single t >= 2 (pending) is what 21 tries would produce by chance.

## (b) ZB-overnight rule by day type (net, MOO entry, 09:30-10:30)
| days | n | mean net | t |
|---|---|---|---|
| all | 580 | +21.5 | 5.07 |
| 08:30 starts | 22 | +10.7 | 0.59 (dev -9.6, check +39.9) |
| 10:00 releases | 122 | +29.9 | 3.12 (dev +24.8, check +35.5) |
| Case-Shiller 09:00 | 26 | +40.4 | 2.31 |
| non-release | 413 | +19.0 | 3.75 |
- 08:30 vs non-release: -8.4 bp, Welch t -0.44. 10:00 vs non-release: +10.9 bp, t 1.00. Neither difference is significant.
- By type: new home +73.8 (n 23, t 3.1), existing +44.1 (t 2.4), pending +3.8, construction +4.0, NAHB +11.3. This is n ~ 25 per cell with trade sd ~ 120 bp, so the standard error is ~25 bp and the spread is consistent with noise. Do not trade it.

## (c) First-hour volatility (09:30 bar, ITB)
| days | n | mean abs return | mean high-low range |
|---|---|---|---|
| 08:30 | 23 | 77.6 bp | 149 bp |
| 10:00 | 127 | 84.8 bp | 159 bp |
| Case-Shiller | 27 | 80.1 bp | 152 bp |
| non-release | 544 | 75.9 bp | 148 bp |
Only the 10:00 range difference is significant (Mann-Whitney p = 0.03; +7% over non-release), and it is small. The abs-return difference has p = 0.18. 08:30 and Case-Shiller are indistinguishable from normal.

## Skip or double on 10:00 days (sizing the ZB rule)
Base: total +12,474 bp, mean 21.5 bp. Skip: total 8,827 bp, mean 15.2 bp. Half: 10,650 bp. Double: 16,121 bp, mean 27.8 bp.
Skipping is worse, because the rule works as well on release days (30 bp vs 19 bp). Doubling only looks better in hindsight. It rests on a +10.9 bp difference with p = 0.32 and a cell that splits sharply by release type. Recommendation: keep size at 1x, no skip.

## Verdict: NONE (post-release drift); keep the ZB rule unchanged
- No tradable post-release drift in ITB at any of the 10:00 releases. The pooled sign is positive but not significant, and the SPY control is flat.
- The release-day interaction with the ZB rule is not significant. Keep the rule as is (neither skip nor double).
- Caveat: n ~ 25 per release type, dates from a scraped calendar, and about 700 days with common macro events (CPI, FOMC, jobs) uncontrolled. A tenth of the ZB rule's trades sit on 10:00 release days, and they are the better ones, so it should not be filtered.
