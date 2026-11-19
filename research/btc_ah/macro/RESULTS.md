# BTC macro-release spillover (agent: macro)

Question: do BTC's reactions on US macro mornings (CPI, NFP 08:30 ET) or FOMC (14:00 ET) carry into MSTR / COIN / MARA / RIOT / CLSK or BTC itself?
Code: `run.py` (grid), `pull_yf.py` (yfinance 60m cache). All output in this folder. Nothing after 2026-08-10 loaded.

## Setup
- Morning move: BTC open 08:30 -> open 09:25 ET. Entry at 09:30 open. Exits 10:00, 10:30, 12:00, close (16:00 bar).
- FOMC move: BTC open 14:00 -> open 14:30 ET. Entry 14:30 open. Exits same-day 16:00 close, or next weekday 16:00 close.
- Direction: "with" = sign(BTC move), "against" = opposite. Threshold |BTC move| >= 0 / 20 / 50 bp.
- Costs: stocks 3 bp/side (6 bp RT), BTC 5 bp/side (10 bp RT). Net return = gross - RT.
- Non-event control: same rule on weekdays with no CPI, NFP or FOMC.
- Dev = entry on or before 2022-06-30; check = after. Dev is 1m (BTC 2020-08..2022-06, MSTR 2020-08..2022-06). Check is 1m (BTC 2022-07..2026-08-10, MSTR 2022-07..2023-12) plus 60m yfinance (2023-11-17..2026-08-10, MSTR/COIN/MARA/RIOT/CLSK). The 60m names have no dev data. 60m bars give 10:30 and close exits only.
- Calendar: `economic_calendar.csv` covers US CPI/NFP/PCE/retail only from late 2025 and FOMC for all years. CPI and NFP 2020-2025 were hardcoded from BLS schedules in my memory (2026 taken from calendar). FOMC dates were hardcoded (emergency 2020-03-15 excluded). PPI, retail sales, GDP and PCE were NOT tested, since the calendar lacks their history and the brief scope is CPI/NFP.
- Counts: CPI 79, NFP 79, FOMC 52 event dates.

## Variants: 408 specs
Morning 324 = (BTC, MSTR1m: 3 event sets x 3 thresholds x 4 exits x 2 dirs = 72 each) + (5 x 60m tickers: 3x3x2x2 = 36 each = 180). FOMC 84 = (BTC, MSTR1m: 12 each) + (5 x 60m: 12 each). Dev selection uses only 1m names (BTC, MSTR).

## Top 3 dev rules (morning, BTC-self, selected on dev t)
| rule | dev n | dev mean bp | dev t | check n | check mean bp | check t | check flip bp | non-event ctrl bp |
|---|---|---|---|---|---|---|---|---|
| BTC CPI, against, th 0, exit 10:30 | 22 | +68.5 | 2.56 | 47 | +2.3 | 0.16 | -22.3 | -10.4 (n 903) |
| BTC CPI, against, th 20, exit 10:30 | 18 | +73.1 | 2.35 | 36 | +3.3 | 0.19 | -23.3 | -9.7 |
| BTC CPI, against, th 0, exit 10:00 | 22 | +57.9 | 2.31 | 47 | +1.3 | 0.10 | -21.3 | -7.8 |

Verdict on these: decay to zero. Overfit.

## Other results (check split unless noted)
| rule | n | win | mean bp | t | flip bp | ctrl bp |
|---|---|---|---|---|---|---|
| MSTR1m CPI+NFP against, th 50, exit 12:00 | 16 | 81% | +264 | 3.25 | -276 | +0.2 |
| MSTR1m CPI+NFP against, th 0, exit close | 35 | 57% | +150 | 2.14 | -162 | -0.5 |
| MSTR 60m CPI+NFP against, th 0, exit 10:30 (2023-11..2026) | 57 | 53% | +7 | 0.20 | -19 | -14 |
| CLSK 60m CPI against, th 0, exit 10:30 | 30 | 57% | +158 | 2.39 | -170 | +3 |
| COIN 60m CPI against, th 50, exit close | 18 | 61% | +201 | 1.92 | -213 | -51 |
| BTC FOMC with, th 0, exit next-day close (dev) | 15 | 60% | +112 | 1.00 | -132 | +24 |
| BTC FOMC with, th 0, exit next-day close (check) | 31 | 61% | +97 | 2.00 | -117 | +4 |
| BTC FOMC with, th 0, exit same-day close (check) | 31 | 58% | +33 | 1.10 | -53 | -11 |
| MSTR 60m FOMC with, th 0, exit next-day close (check) | 19 | 79% | +352 | 3.22 | -364 | +6 |
| MSTR 1m FOMC with, th 0, exit next-day close (dev) | 13 | 23% | -175 | -1.14 | +65 | |
| MSTR 1m FOMC with, th 0, exit next-day close (check) | 12 | 67% | +45 | 0.20 | +15 | |

Read-across: MSTR's FOMC overnight sign flips between 1m dev (-175) and 60m check (+352). Not stable. BTC-only FOMC continuation keeps its sign and size from dev to check.

## Decay and flips
- Morning: dev-selected BTC fade decays to ~0 on check. Flipped-direction control is negative on every top rule (the "with" trade loses), so this is not drift.
- Stock morning fades look good on the 2022-23 1m MSTR check window but not on the 60m MSTR 2023-2026 window (t 0.2). Miner fades (CLSK, COIN, MARA) are positive on 60m check with t about 2, but were not in dev and are not corrected for ~400 variants.
- Year splits are mixed in sign across regimes (e.g. MSTR 60m CPI+NFP: 2023 +139, 2024 -26, 2025 +51, 2026 -35 bp).
- Multiple testing: 408 specs at |t|>=2 gives roughly 20 chance hits. Only FOMC-BTC continuation (dev and check same sign) and nothing in stocks survives that filter.

## Best rule as code (candidate, not yet verified)
On a FOMC day, at 14:30 ET open BTC if BTC rose from the 14:00 open to the 14:30 open (short if it fell). Exit at the 15:59 ET close of the next weekday. Cost 10 bp RT. Check: n 31, mean +97 bp net, t 2.0, win 61%, flip -117 bp, non-event control +4 bp.

## Verdict
- Morning CPI/NFP: NONE. Dev edge does not survive check. Stock-level 1m check hits are not repeated in 60m data for MSTR.
- FOMC: WEAK. BTC overnight continuation is consistent in sign across halves (n 46 total, t about 2) but small sample (2023 is flat at +2 bp, the other four check years are positive). Stock versions inconsistent (MSTR 1m dev vs 60m check). Not EDGE.
- Caveats: CPI/NFP dates hardcoded from memory for 2020-2025; PPI/retail/GDP/PCE untested; no options; 60m names have no dev data; yfinance 60m is adjusted only for splits and dividends.
