# Working method: long BTC during CME's daily break, 17:00–18:00 ET weekdays (2026-10-17)

## The edge
Buy BTC exposure at 17:00 ET and sell at 18:00 ET on every NYSE weekday. That hour is CME's daily bitcoin-futures maintenance break.

| period | trades | gross/trade | t | win | net @2 bp RT | net @5 bp RT |
|---|---|---|---|---|---|---|
| 2017-08..2022-12 | 1276 | +7.1 bp | 3.17 | 56.7% | +12%/yr, Sharpe 0.98 | +5%/yr |
| 2023-01..2026-08 | 861 | +5.0 bp | 2.87 | 56.0% | +7%/yr, Sharpe 0.91 | 0%/yr |
| 2024-01..2026-08 (spot-ETF era) | 611 | +7.0 bp | 3.68 | 56.1% | +12%/yr, Sharpe 1.63 | +5%/yr |

- Positive in 8 of 10 calendar years and on every weekday (Mon +4 to Fri +9 bp).
- Neighbouring windows fade: 17:30–18:00 is positive, 18:00–19:00 is ~0 after 2023, and 16:00–17:00 is ~0. The effect sits inside the CME break.
- The %/yr figures are on notional held 1 hour per day; leverage scales return and risk equally.

## How to trade it (US-accessible)
- **IBIT in the after-hours session** (most US brokers run it until 20:00 ET):
  - tracks BTC with corr 0.985 at 17:00–18:00 (82 days in 2026);
  - trades in about 40 of the 60 minutes, about $25k/min;
  - quoted spread about 2 cents on about $46, i.e. about 4 bp for a full round trip at market;
  - limit orders at the touch bring it toward 2 bp.
- **CME futures are closed** in this window, so they can't be used.
- Retail spot exchanges (≥20 bp) kill the edge.

## Honest limits
- The edge is thin, about 5–7 bp gross per trade, and it only pays with execution costs ≤ ~4 bp round trip.
- Capacity is roughly $25–50k per trade in IBIT after hours.
- The hour was found in a 24-hour scan of 2017–22, and 2023–26 was viewed hour by hour before the rule was frozen. Only forward trades are clean evidence.

## Live verification
- Forward paper test `btc_cme_break_v1` is registered (registry seq 6, `FORWARD_PLAN.md`).
- launchd runs it at 13:50 PT on weekdays and buys/sells $10k BTC/USD on LSE sim account 1717158.
- It is scored on Coinbase 1-minute closes; the gate is set at 250 trades.

## Everything else tested today (all null)
These are listed in `research/mstr_btc_0dte/REPORT.md` and `agent_a/b/c`:
- MSTR 0DTE buying and premium selling
- credit spreads
- BTC→MSTR minute lead-lag
- tokenized MSTR
- MSTR extended-hours lag
- BTC off-hours momentum and after-hours entry
- slower BTC proxies
- MSTR–BTC premium mean reversion and momentum
- 8-K purchase days
- intraday momentum
- leveraged-ETF close flows

## Independent check on Coinbase BTC-USD, the forward scoring venue (2026-10-17, `coinbase_check.py`)

| period | trades | mean | t | hit rate |
|---|---|---|---|---|
| 2019–22 | 1006 | +9.5 bp | 4.28 | 56.7% |
| 2023–26-10 | 951 | +5.5 bp | 3.44 | 55.6% |
| 2024–26 | 701 | +7.2 bp | 4.04 | 55.2% |
| **2026 YTD** | 199 | **+1.4 bp** | 0.48 | 49.7% |

- Every year 2019–2026 was positive, but 2026 is the weakest year so far. Treat that as a warning sign: the edge may be decaying as it becomes known; an ETF built on BTC's overnight returns (NGHT) launched in April 2026.
- The playbook and the forward test (spec seq 7, hardened code) are final. The full run flow was tested end to end on the LSE sim against a temporary registry.

## 2026-10-17 follow-ups
- **ETH out-of-sample mechanism test (pre-registered, one shot) PASSED.** ETH 17:00–18:00 ET weekdays:
  - 2019–26: +8.0 bp, t 3.53.
  - 2023–26: +10.3 bp, t 3.64.
  - Placebo hours: 16:00–17:00 +1.2 bp (t 0.5); 18:00–19:00 +3.1 bp (t 1.5).
  - So the CME-break effect shows up on a second asset that had never been examined.
- **Combined BTC+ETH (equal weight):**
  - 2023–26: +6.9 bp, t 3.88.
  - 2025–26: +6.3 bp, t 2.55, with 15 of 22 months positive.
  - ROI at 4 bp per round trip, by year: 2019 +15%, 2020 +29%, 2021 +18%, 2022 −11%, 2023 −8%, 2024 +26%, 2025 +14%, 2026 YTD −3%.
  - 2026 is +2.5 bp gross, so whether it nets a profit depends on execution cost.
- **Adaptive hour-chasing (pre-registered) FAILED.** −6% to +4% per year in 2025–26; hour patterns other than the CME break are noise.
- **Cash-and-carry check.** Long spot / short CME futures paid T-bills +2–7% a year in 2023–25 (BITO-implied; actual CME BTC=F basis 6–15%). The 2026 basis is about 4–5%, and only 1–3% in October 2026. That is now below T-bills, so it is not worth doing currently.
- **Forward tests running:** `btc_cme_break_v1` (registry seq 7) and `eth_cme_break_v1` (seq 8), with launchd on weekdays. The combined scoreboard is `reports/forward/cme_break_combined.json`.

## Real execution test on 2026 after-hours prints (EXEC_PREREG.md, rules fixed in advance)

| ETF | days | price move | limit-rule net | market-order net | implied cost |
|---|---|---|---|---|---|
| IBIT | 82 | +4.8 bp | **−1.75 bp** (t −0.37), win 40% | −5.4 bp | ~6.5 bp |
| ETHA | 71 | +10.1 bp | **+0.1 bp** (t 0.01), win 38% | +2.6 bp | ~10 bp |

**Verdict for 2026:** the edge still shows up in prices, but real ETF after-hours execution costs about as much as it earns. Net is about breakeven, so it is **not actively profitable after costs right now**. It would pay only with execution at or below ~2–3 bp, for example a market-maker or exchange-fee tier that retail can't get.
