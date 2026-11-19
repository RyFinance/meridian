# Playbook: the CME-break hour (BTC + ETH, 17:00 → 18:00 ET, weekdays)

## The trade
On every NYSE trading day, Monday to Friday:
- be long bitcoin from 17:00 ET (2:00 pm PT) to 18:00 ET (3:00 pm PT);
- flat the rest of the day.

17:00–18:00 ET is CME's daily bitcoin-futures shutdown. Spot BTC has risen in that hour on average:

| period | avg/trade | t | win rate |
|---|---|---|---|
| 2017–22 | +7.1 bp | 3.2 | 57% |
| 2023–26 | +5.0 bp | 2.9 | 56% |
| 2024–26 | +7.0 bp | 3.7 | 56% |
| 2026 YTD (Coinbase) | +1.4 bp | 0.5 | 50% |

**Warning:** 2026 is the weakest year (still positive). The edge may be fading. Let the forward test confirm it before committing real size.

## ETH confirms it (pre-registered, never-examined asset)
ETH in the same hour:
- 2019–26: +8.0 bp, t 3.5.
- 2023–26: +10.3 bp.

Combined BTC+ETH (equal weight):
- 2023–26: +6.9 bp, t 3.9.
- 2025–26: +6.3 bp, t 2.6.

Split the size between **IBIT and ETHA** (iShares ether ETF; ~2-cent spread, about 3.7 bp). Both trade after hours.

## How to execute it (US account): IBIT (+ ETHA) in the after-hours session
1. **16:58 ET.** Check IBIT's after-hours bid/ask. Skip the day if the spread is above 2 cents (~4 bp).
2. **17:00 ET.** Buy IBIT with a **limit order at the bid**, or at most the mid; don't cross the spread. If it hasn't filled by 17:03, raise it to the ask once. If it still hasn't filled by 17:05, skip the day.
3. **18:00 ET.** Sell with a **limit order at the ask**, or the mid. If it hasn't filled by 18:03, sell at the bid. Never carry the position past 18:10.
4. Size it to at most about $25k per trade (after-hours liquidity is about $25k/min), or less.
5. Use a broker that allows extended-hours limit orders and charges ≤ $0.005/share (IBKR Pro, Schwab, Fidelity, Robinhood).

## Costs decide everything

| round-trip cost | expected net/trade | ~annual on traded notional |
|---|---|---|
| 2 bp (limit fills) | +3 to +5 bp | +7 to +12% |
| 4 bp | +1 to +3 bp | +2 to +7% |
| 5 bp (market orders) | ~0 to +2 bp | ~0 to +5% |
| ≥ 8 bp | negative | negative |

## Risk
- One hour of BTC exposure has an sd of 0.51% (2023–26) to 0.70% (all years), so $25k carries about $130–175 of daily P&L noise.
- The worst hour was −6.5% (−5.5% in 2023–26). 29 of 2,137 hours fell more than 2%.
- 32% of months lost money; the worst month was −11.5% of notional.
- The edge is a 56/44 coin. Judge it only over 100+ trades.

## What is running automatically
- `com.rytty.quant_v7.btc_cme_break_run` (13:50 PT on weekdays): records the decision before 17:00 ET, buys $10k BTC/USD on LSE sim account 1717158 at 17:00:05, and sells at 18:00:05.
- `com.rytty.quant_v7.btc_cme_break_evaluate` (15:15 PT): scores every trade on Coinbase BTC-USD 1-minute closes and writes `reports/forward/btc_cme_break_eval.json`.
- **Gate:** 250 trades (~Oct 2027). It passes if gross t ≥ 1.65 and net at 5 bp > 0. It is killed if cumulative net at 5 bp ≤ −8%.

## Daily check (30 seconds)

```bash
tail -3 ~/Library/Logs/quant_v7/btc_cme_break_run.log
```

```bash
cat /Users/rytty/CCP/quant_v7/reports/forward/btc_cme_break_eval.json | head -20
```

## Requirements
- The Mac must be awake at 13:50 PT on weekdays. LSE Terminal should be open; the job tries to launch it if it isn't. Scoring works even if the sim is down.
- Don't edit `research/btc_session/forward.py` or `research/forward/evaluate.py`. Both are fingerprinted in registered specs.
