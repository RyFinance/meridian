# Round 5: build on the ZB → homebuilder first-hour edge (2026-10-18)

## The discovery (verified; read research/zb_itb/verify/VERIFICATION.md)
- **Signal:** d = sign(ZB=F 60m close at 09:00 ET / ZB=F 60m close at 16:00 ET on the previous session). Bars are START-labeled, so use the bars labeled 08:00 and 15:00.
- **Trade:** d × ITB from the 09:30 official open to 10:30 (close of the 09:30 60m bar).
- **Results:** 2024-05..2026-10, 570 trades, +22 bp net at 2 bp/side, t 5.2, Sharpe 3.3.
  - It replicates in XHB and in DHI, LEN, PHM, TOL, KBH and NVR. VNQ, IWM, XLU, KRE and SPY are about 0.
  - With a TLT-gap proxy, it exists since 2020 and not in 2010–19.
- **Mechanism:** the stock's opening auction prices only part of an overnight move in a 24h market the stock depends on. The rest diffuses over the first ~45 minutes. ZB itself does not continue after 09:00.

## Rules for this round
1. **Data:** yfinance only has 60m data for the last 730 days (2024-05..2026-10) and 5m for the last 60 days. Use the frozen helper `research/zb_itb/verify/f3_canonical.py` (`build(etf, zbfile)` reads `research/zb_itb/verify/yf_cache/<SYM>_60m.parquet` and `<SYM>_1d.parquet`). For other symbols, download yfinance 60m (period="730d") and 1d into YOUR OWN folder and copy the logic. Do not modify anything outside your folder.
2. **No look-ahead:** the signal must be computable before 09:30 (futures bars ending ≤ 09:00, or ≤ 09:25 with 5m data). Entry is at the 09:30 open (MOO). Exits at bar closes.
3. **Costs:** 2 bp/side for liquid ETFs and large caps, 5 bp/side for small/mid caps or ETFs under $20M/day, 10 bp/side for anything thin.
4. **Split:** dev = 2024-05-28..2025-06-30, check = 2025-07-01..2026-10-16. Select on dev only and report check numbers for your top picks.
   - Report how many variants you tried. Treat |t| ≈ 2 from many variants as noise.
   - Report the flip (opposite-direction) control and a placebo (SPY or another unrelated name).
5. **Python:** `cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python <script>`. Write only inside your folder `research/zb_itb/round5/<agent>/`. No installs, no background jobs, no launchd, no orders.
6. **Deliverable:** `RESULTS.md` (≤ 60 lines) with a table, the best rule stated precisely, dev/check numbers, controls and a verdict (EDGE / WEAK / NONE). Final reply ≤ 250 words.
