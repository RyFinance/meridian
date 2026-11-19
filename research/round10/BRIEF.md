# Round 10: find another "slow open" edge (2026-10-19)

## What worked, and why (copy the method, not the market)
- **The verified edge:** when 30-year Treasury futures (ZB=F, 24h market) rise overnight (16:00 → 09:00 ET), homebuilders (ITB) open only about half-repriced and catch up over the first ~45 minutes. Entering at the 09:30 open (a market-on-open order) and exiting at 10:30 earns +22 bp/trade net, t 5.2, over 2024-05..2026-10.
  - It replicates in all 7 builder stocks and in RKT. It also works in 2020–23 with a proxy.
  - The signal strengthens with bond duration (ZT < ZF < ZN < ZB).
  - Placebos (SPY, REITs, banks) are about 0.
- **The mechanism:** information produced overnight in a DIFFERENT market, which the stock depends on economically, is under-priced by the stock's opening auction and diffuses over the first hour.
- **Already dead** (don't repeat these unless with a new angle):
  - BTC→MSTR/miners/crypto stocks;
  - oil→energy, airlines and cruise lines; gas→producers and utilities;
  - grains→ag stocks; metals→miners;
  - FX→ADRs and multinationals; country ETFs/ADRs vs their home index;
  - ES futures→SPY/QQQ/IWM;
  - rates→REITs, banks, insurers, bond ETFs, solar, fintech;
  - UK builders.

## Hard rules
1. **No look-ahead.** The signal must come only from data timestamped before the decision time (≤ 09:25 ET for an open entry). Verify bar labeling (yfinance 60m bars are START-labeled) and say how.
2. **Entry and exit:**
   - Entry at the official 09:30 open (yfinance daily Open, or the 60m 09:30 bar Open), or later.
   - **Never use the stock's own opening print as the signal AND the fill.** A rule that needs the stock's own gap must enter after the open (09:31+).
   - Exits at bar closes.
3. **Costs:** 2 bp/side for liquid ETFs and mega caps, 5 bp/side for other stocks, 10 bp/side for thin names.
4. **Split:** dev = first ~55% of the sample, check = the rest. yfinance 60m covers about 2024-05..2026-10.
   - Select on dev only; report check numbers for the top picks.
   - Count every variant. Report a flip (opposite-direction) control and an unrelated placebo (e.g. SPY with the same signal).
5. **Code:** Python is `cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python <script>`. Write only in your folder `research/round10/<agent>/`.
   - Cache downloads there. Use curl via subprocess for any HTTP that Python urllib can't do through the proxy.
   - No installs, no background jobs, no launchd, no orders.
6. **Deliverable:** `RESULTS.md` (≤ 60 lines), with:
   - the best rule stated precisely;
   - dev and check n, mean net bp, t and win rate;
   - controls;
   - correlation of its trade P&L with the ITB rule's (`research/zb_itb/verify/f3_trades_canonical.csv`; net = g_off − 0.0004; index = date);
   - a verdict: EDGE / WEAK / NONE.

   Final reply ≤ 250 words.
