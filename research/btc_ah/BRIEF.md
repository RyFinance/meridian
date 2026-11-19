# BTC after-hours → tradable rule hunt (2026-10-17)

Goal: a rule, keyed on BTC's move while US equities are closed, that makes money **net of costs** in stocks, ETFs, options, or BTC itself. A high win rate is nice, but the mean net return and its t-stat are what decide it.

## HARD RULES (any violation voids your result)
1. **SEALED HOLDOUT: never load, compute on, or look at any price dated after 2026-08-10.** Filter every dataset to `<= 2026-08-10` right after loading. That window is the final test, run once by the lead.
2. **No look-ahead.** A decision at time T may use only data with timestamps strictly before T. Enter at the next bar's price, not the bar used to decide. Use `bar.high` for buys and `bar.low` for sells when testing "worst fills".
3. **Costs are always on.**
   - Shares in regular hours: 3 bp per side. Pre-market/after-hours: **15 bp per side** (wide spreads).
   - Options: half-spread max($0.03, 2.5% of price) + $0.65/contract per side.
   - BTC spot: 5 bp per side.
4. Report every rule you tried, including the count. Report: n, win rate, mean net per trade, t-stat, average win and average loss, per-year mean, and the **flipped-direction control**. A rule whose flip also makes money is drift, not signal.
5. Split each dataset into a dev half and a check half by time (e.g. dev ≤ 2022-06, check 2022-07..2026-08-10). Pick parameters on dev only and report check results for the top 3 dev rules. Large dev-to-check decay = overfit.
6. Python: `cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python your_script.py`. Write ONLY inside your own folder `research/btc_ah/<your_agent_name>/`. Do not modify anything else. Do not install packages. Do not start background jobs or launchd.

## Data (read-only)
- BTC 1-minute, UTC, 2017-08..2026-08-11: `/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet` (columns timestamp, open, high, low, close, volume).
- MSTR stock 1-minute **including extended hours** (04:00–20:00 ET), as-traded prices (10:1 split 2024-08-08), UTC naive timestamps:
  - `research/mstr_btc_0dte/stock_1m_dev/YYYY-MM-DD.parquet`: 827 days, 2020-08-12..2023-12-29.
  - `research/mstr_btc_0dte/mstr_stock_1m_lse.parquet`: 2026-04-29..2026-09-16 (**filter to ≤ 2026-08-10**).
- MSTR daily OHLC (yfinance, split-adjusted): `research/mstr_btc_0dte/mstr_daily_yf.parquet`. Daily panel with BTC off-hours moves: `research/mstr_btc_0dte/daily_panel.parquet`.
- MSTR option daily per-contract prints 2020–2026: `data/lse/options_mstr/MSTR.parquet`. IBIT options: `data/lse/options_ibit/IBIT.parquet`.
- Other tickers: yfinance is installed in the venv (daily history is fine; 60m covers about 730 days; 1m covers 7 days). Cache downloads in your folder.

## What is already known (don't redo)
- MSTR's **09:30 official open** already prices BTC's 16:00→09:30 move about 1:1 (gap beta ≈ 1.0).
- After 09:30, BTC's direction barely predicts MSTR open→close (corr ≈ 0). Monday shares open→close: +21 bp net, t 0.67.
- Buying options at the open in BTC's direction: net −1.5% per trade. Take-profit-ASAP: 72% win, but avg win +13% vs avg loss −46%. A trailing-stop grid (486 variants): all negative.
- Short premium (0DTE, 2–14 DTE spreads, condors): wins 72–100% in 2020–23, failed 2024–26 on tail Fridays.
- No BTC→MSTR minute lead-lag in **regular hours** (MSTR reprices within the same minute).
- Not tested: extended hours (pre-market and after-hours), other tickers' extended hours, intraday share management.

## Deliverable
`research/btc_ah/<agent>/RESULTS.md`, under 60 lines: what you tested (number of variants), a results table, the best rule written precisely enough to code, its dev and check numbers, the flip control, and an honest verdict (EDGE / WEAK / NONE). Keep your final reply under 300 words with the key numbers.

## ADDENDUM (round 4): other overnight-gap markets
The same idea applies to other markets: a market that trades while US equities are closed (futures and foreign markets) moves, and then the US-listed equity or ETF opens.
- yfinance futures symbols: CL=F, BZ=F, NG=F, GC=F, SI=F, HG=F, ES=F, NQ=F, RTY=F, ZN=F, 6E=F, 6J=F. Daily history goes back decades; 60m/1h covers about 730 days.
- **Timing trap:** a futures daily bar does NOT close at 16:00 ET (CL settles at 14:30, the ES day bar runs 18:00→17:00). For a precise "16:00 → 09:25 ET" move, use hourly or 1m bars. If you use daily bars, define the signal only from times you can prove precede the equity open.
- Optional longer intraday history: the LSE Terminal is running. `from research.lse_mcp_client import Terminal, content_text`, then `t.call("get_history", {"symbol":..., "timeframe":"1h", "start":"YYYY-MM-DD", "end":"YYYY-MM-DD", "limit":1000})` returns CSV text. Use `search_instruments` to find symbols. See research/mstr_btc_0dte/pull_stock_1m_dev.py for the pattern and its quirk: [day, day+1) ranges. Be gentle: sleep 0.5–1 s per call.
- Costs: liquid ETFs (SPY, QQQ, GLD, USO, EWJ...) 2 bp per side; single stocks and ADRs 3 bp; anything under $5 or thin, 10 bp.
- The sealed-holdout rule applies to every market: nothing after 2026-08-10.
