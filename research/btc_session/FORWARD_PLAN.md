# Forward paper test: long BTC during CME's daily break (17:00–18:00 ET)

Strategy id `btc_cme_break_v1`, registered 2026-10-17. Frozen code: `research/btc_session/forward.py`. Its SHA-256 is in the registry spec.

## Evidence before registration
- **Where it came from.** Agent B scanned 24 ET hours on 2017-08..2022-12 BTC data (`research/mstr_btc_0dte/agent_b/`). The 17:00–18:00 ET hour stood out, with t 3.8 on hourly bars.
- **Exact rule on 1-minute data** (`postclose.py`, `cmebreak_17_18.parquet`), long 17:00→18:00 ET on NYSE weekdays:

| Period | Gross per trade | t | Hit rate |
|---|---|---|---|
| 2017-22 | +7.1 bp | 3.17 | 56.7% |
| 2023-26 | +5.0 bp | 2.87 | 56.0% |
| 2024-26 (spot-ETF era) | +7.0 bp | 3.68 | 56.1% |

- Positive in 8 of 10 calendar years and on every weekday. Bonferroni across 24 hours needs t ≈ 2.9; dev passes it.
- 2023-26 data had been looked at hour by hour before this rule was frozen, so it is not a clean hold-out. Only forward trades count.
- **Plausible mechanism.** CME bitcoin futures stop trading 17:00–18:00 ET every day, so futures-based hedgers and basis traders can't trade for that hour. Spot keeps trading.
- **Vehicle check.** IBIT after-hours 17:00–18:00 tracks BTC with corr 0.985 (82 days in 2026). It trades in about 40 of the 60 minutes, at about $25k per minute; the median 1-minute range is 2.7 bp.

## Rule (fixed)
Every Monday–Friday that is an NYSE session day:
- buy $10,000 of BTC at 17:00:00 ET and sell at 18:00:00 ET;
- the decision is recorded before 17:00 ET;
- no filters and no sizing changes.

## Scoring
- Gross per trade is ln(P18/P17) on Coinbase BTC-USD 1-minute closes at 17:00 and 18:00 ET.
- Net is reported at 2 bp (limit orders), 5 bp (taker fills in IBIT after hours) and 10 bp (retail spot) per round trip.
- LSE sim BTC/USD fills are logged as an execution check only and don't affect the score.

## Gate (set now)
- The final look is at 250 counted trades, about 1 year (October 2027).
- **Pass:** gross mean > 0 with one-sided t ≥ 1.65, AND net at 5 bp > 0.
- **Kill:** cumulative net at 5 bp ≤ −8% of notional.
- **Power:** at the historical +6 bp and 1-hour sd of ~55 bp, 250 trades give an expected gross t of about 1.7. A pass is roughly a coin flip even if the effect is real.

## Revision before the first decision (2026-10-17)
`forward.py` was hardened before any decision was recorded. The spec was re-registered, and only the latest spec counts. The rule and scoring are unchanged. The changes:
- auto-launch LSE Terminal;
- fall back to Coinbase prices for sizing;
- retry the sim close and skip it if no position is open.
