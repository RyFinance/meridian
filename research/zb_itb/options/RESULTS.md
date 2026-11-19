# Options version of ZB → homebuilders (real OPRA 1m prints, LSE vault), 2024-05..2026-09

On each signal day, for DHI, LEN, PHM, TOL and KBH: buy a call (bonds up) or a put (bonds down). Entry is the first print in 09:30–09:34; exit is the last print in 10:25–10:35, with a fallback to 10:35–10:45. Three expiry buckets × three strikes. `backtest.py`

- **Liquidity is the binding problem:** only 1,484 of 15,926 attempted legs (9%) had prints at both entry and exit, and 451 of those used the late-exit fallback. Builder options are too thin to execute reliably on this schedule.
- **Results on premium:**
  - Gross +9.3%; after half-spread max($0.03, 3%) + $0.65/contract, −0.3% (t −0.1).
  - Stress costs (6% half-spread): −7.4%. Worst fills: −1.4%. Win rate 41%.
- **Cells:** 8 of 9 are negative or flat at base cost. 0–3 DTE one-strike-OTM shows +13.7% (t 1.37, n 215) but only +2.5% at stress costs; as one cell of 9 it isn't significant.
- **Verdict: NONE.** The bid-ask spread takes the edge, and the thin prints make execution unreliable. The stock/ETF version (ITB) stays the way to trade it. For leverage, intraday margin on ITB is cheaper than options.
