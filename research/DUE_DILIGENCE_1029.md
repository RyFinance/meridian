# GapUp due diligence: ITB and NAIL (answers to the 60-point list)

Prepared 2026-10-29. The signal and its parameters are not disclosed here. In outline: a pre-open, cross-asset directional signal decides the trade, and the position is held for one intraday hour. It runs on one ETF (ITB) and on its 3× leveraged version (NAIL). There is one market regime filter.

**Status labels:** **A** = addressed, **P** = partially addressed, **N** = not addressed.

## Read this first

1. **"70% CAGR" is the NAIL figure.**
   - The 10-year tradable backtest (2016–26) gives NAIL 68% CAGR at 1× with costs, Sharpe 1.72 and max drawdown −38%.
   - ITB, the same signal unleveraged, gives 16% CAGR, Sharpe 1.43 and max drawdown −15%.
   - NAIL is not a second edge. Its trades correlate 0.97 with ITB's, so NAIL is ITB at roughly 3× leverage, and the extra CAGR comes from that leverage.
2. **The "10% in 7 days" is not a real-money or real-fill number.**
   - Real broker paper results so far:
     - ITB +$66, about +3.3%, over 6 trades.
     - NAIL −$58, about −2.9%, over 5 trades.
   - The +8 to +10% NAIL figure includes +$226 of simulated sessions:
     - one day the Mac was off;
     - one day a software bug blocked trading;
     - one day the order only partly filled and the rest was simulated as filled.
   - Either way, 7 days carries no statistical weight.
3. **The three-model validation (Opus / Astra / DeepSeek on LSE Terminal) is not part of this work.**
   - I have no record of those runs, so I can't vouch for them.
   - This research didn't use LSE Terminal's backtest engine at all.
   - Prices came from Yahoo Finance hourly bars, Alpaca SIP consolidated tape (1-minute and 15-minute bars) and LSE vault tick data. Every return and statistic was computed in my own Python.
   - So the common-mode risk the reviewer flags for LSE Terminal does not apply to these numbers. The other common-mode risks (data vendors, my own specifications) are covered below.

## Headline numbers (independent recomputation, 2026-10-29)

Written from scratch on raw Alpaca SIP bars; it shares no code with the original research.

- **Signal:** a fully tradable proxy, known before 09:15 ET.
- **Trade:** enter at the 09:30 open, exit at 10:30.
- **Regime filter:** on.
- **Costs:** 2 bp per side for ITB, 5 bp per side for NAIL.
- **Other assumptions:** no stop applied, idle cash earns 0%, RF = 0.

| | ITB 2016–26 | NAIL 2016–26 |
|---|---|---|
| Trades | 1,154 | 1,072 |
| Mean per trade (net) | +13.6 bp (t 4.5) | +52.7 bp (t 5.4) |
| Win rate | 53.6% | 55.2% |
| CAGR | 16.3% | 68.2% |
| Sharpe (daily, incl. flat days) | 1.43 | 1.72 |
| Max drawdown | −14.6% | −38.4% |
| Calmar | 1.12 | 1.78 |
| Longest drawdown | 993 trading days | 694 trading days |
| Worst day | −2.9% | −10.0% |
| Worst month | −7.5% | −16.7% |
| Expected shortfall 95% / 99% (per trade) | −1.9% / −2.5% | −6.0% / −7.9% |
| Lag-1 autocorrelation | −0.002 | −0.016 |
| Placebo p (2,000 random-sign runs) | < 0.0005 | < 0.0005 |

**By era. This is the most important table.**

| | ITB net/trade | ITB CAGR | NAIL net/trade | NAIL CAGR | NAIL max DD |
|---|---|---|---|---|---|
| 2016–19 | −2.8 bp (t −0.6) | −1.9% | +8.6 bp (t 0.4) | +2.3% | −17.9% |
| 2020–23 | +12.6 bp (t 2.6) | +18.4% | +49.8 bp (t 3.4) | +85.6% | −38.4% |
| 2024–26 | +23.4 bp (t 4.6) | +41.9% | +70.3 bp (t 4.7) | +173.7% | −21.6% |

The edge is **zero before 2020**. It has existed only in the post-2020 regime, and it is strongest in the most recent window. Most of the 68% comes from 2020–26.

---

## 1. Statistical validity

| # | Concern | Status | Evidence / what remains |
|---|---|---|---|
| 1 | Lookahead | **A** | Bar timestamps were audited (start- vs end-labeled, cross-checked against 5-minute bars). The signal is complete before 09:15; entry is at 09:30. The regime filter uses a correlation computed from prior days only. |
| 2 | Leakage | **A** | No model, normalization or training. The only fitted quantities are the signal's sign and a correlation threshold of 0. |
| 3 | Survivorship | **A** for the rule, **P** for selection | The rule trades two ETFs that exist today; no historical universe is involved. Selection is the issue: homebuilders were picked as the leg after looking across sectors (see #4), and the 58-ETF cross-market scan used funds that exist today. |
| 4 | Multiple testing | **P** (the biggest open issue) | Roughly 6,000 variants were tested before this rule was picked, and about 10,500 more since (cross-market scans that found nothing new). The deflated Sharpe probability was 0.93 at 6,000 trials. It hasn't been redone at about 16,500, and it will be lower. Mitigants: the result replicates in 6 single homebuilder stocks and XHB, the duration ladder steps up monotonically (2y < 5y < 10y < 30y bond signal), and a random-sign placebo gives p < 0.0005. NAIL was not a separate discovery; it is the same signal on the 3× fund. |
| 5 | Overfitting | **A/P** | Only a sign, an exit time and one threshold. The exit time is not tuned (see #8). The regime threshold (correlation > 0) was chosen *after* seeing that 2010–19 failed, so that part is fitted in-sample. |
| 6 | OOS contamination | **P** | The rule was found on 2024–26 data. 2020–23 was then a genuine out-of-sample confirmation (+12.6 bp, t 2.6). 2016–19 was checked afterwards and failed. Every period has now been seen, and a sealed 2-month holdout gave +15 bp (t 1.07), positive but weak. **No untouched data remains**; only forward trading counts from here. |
| 7 | Regime dependency | **N** (the edge is regime-dependent) | Zero edge in 2016–19, as shown in the era table above. The regime switch is a guardrail, not a fix: it stands aside when stocks and bonds stop moving together. Expect the edge to fade if that regime ends. |
| 8 | Parameter sensitivity | **A** | Every alternative exit time is positive (ITB 10:00 → 16:00: +9.5 to +19.3 bp; NAIL +41 to +69 bp). Correlation thresholds of −0.2 and +0.2 are both positive (NAIL Sharpe 1.73 / 2.01). **The one fragile input is entry timing:** entering at 09:45 instead of 09:30 takes ITB to +1 bp and NAIL to +6 bp. The edge is concentrated in the opening auction. |
| 9 | Sample size | **A** | About 1,100 trades over 10 years, 400 of them in the 2024–26 window. Daily trades are close to independent (lag-1 autocorrelation ≈ 0). The independent regime count is small: in effect, two eras. |
| 10 | Significance | **A/P** | t 4.5 (ITB) and t 5.4 (NAIL) over 10 years, permutation p < 0.0005. After about 16,500 trials a t of 4.5 still clears a Bonferroni-type bar (≈ 4.4–4.6), but only just. |

## 2. Data integrity

| # | Concern | Status | Evidence |
|---|---|---|---|
| 11 | Corporate actions | **A** | Every trade is an intraday return within one session, so splits and dividends can't create false returns. Raw prices are used. |
| 12 | Historical constituents | **N/A** | No stock universe; the rule trades two named ETFs. |
| 13 | Timestamp alignment | **A** | The bond signal, the ETF bars and the exchange calendar are all handled in Eastern time. Bar labeling convention was verified per source. |
| 14 | Missing data | **A** | A missing signal or missing bar means no trade; it is never converted to a return. Live: on 10-27 the signal was exactly zero and no trade was placed. |
| 15 | Revisions | **A** | Exchange trade prints aren't revised the way macro data is. |
| 16 | Calendars | **P** | NYSE calendar used. Sessions right after holidays average −54 bp (n 18); that is logged, not filtered. Half-days aren't modeled separately. |
| 17 | Bad ticks | **P** | Consolidated-tape bars are used and the opening print was cross-checked against the official open. Thin funds have stale 09:30 prints; this matters for NAIL and is covered under #19. |
| 18 | Source independence | **A** | Four independent sources agree: Yahoo hourly, Alpaca SIP 1-minute, LSE vault ticks (individual builders) and IBKR-style official opens. Per-trade correlation between Yahoo and SIP is 0.997. **Found while preparing this:** one cached ITB file from the cross-market scan stopped at 2019-06 because of a download bug. It didn't affect the core results, which use the complete files, but it is noted. |

## 3. Execution realism (where the risk actually is)

| # | Concern | Status | Evidence / what remains |
|---|---|---|---|
| 19 | Fill assumptions | **P** (the main risk) | The backtest fills at the official opening-auction price. **Live (Alpaca paper):** the opening order filled fully on 1 of 11 orders, filled partly on 3 (NAIL got 3 of 71 shares once) and got nothing on 7. A fallback entry then fills around 09:33–09:35. The backtest says a 09:45 entry loses almost all of the edge, and 09:35 loses about half. Alpaca's paper simulator doesn't take part in real auctions, so a real auction order at a real broker (e.g. IBKR) is the thing to test. **Until then, the live fill path doesn't match the backtest.** |
| 20 | Slippage | **A/P** | Costs are 2 bp per side (ITB) and 5 bp (NAIL), stress-tested at 2× and 4×. ITB breaks even at about 4× (≈ 8 bp per side); NAIL survives 4× (+22.7 bp, t 2.3). Real auction slippage hasn't been measured yet (see #19). |
| 21 | Spread | **A** | Included in the per-side cost. ITB's spread is about 1–2 bp; NAIL's is wider, hence the 5 bp. |
| 22 | Partial fills | **P** | Now handled in code: the trader tops up the unfilled remainder and sizes its stop from the actual fill. It isn't modeled in the backtest, and live partial fills are common (see #19). |
| 23 | Market impact | **A** at $2k | Capacity is about $0.5M per trade for ITB (1% of first-hour volume). NAIL is much thinner: estimate roughly $50–100k before impact matters; not measured. |
| 24 | Latency | **A** | The signal is known at 09:00–09:15 and the order goes in by 09:27; nothing needs to be fast. |
| 25 | Fees | **A** | Modeled on IBKR Tiered commissions plus regulatory fees, applied per trade. |
| 26 | Short costs | **P** | Shorts are held intraday only, so no overnight borrow fee is charged. Borrow availability for shorting NAIL (a 3× fund) isn't guaranteed and hasn't been tested live. The long-only results are reported separately in case shorting isn't possible. |
| 27 | Order logic | **A** | Opening-auction order, a fallback market order until 09:35, a 3% stop and a 10:30 market exit. The stop is a real stop order, so fills on gap-through are at the market price. The audit numbers above ignore the stop altogether (conservative on both wins and losses). |
| 28 | Capacity | **P** | See #23. NAIL is the constraint. |

## 4. Performance metrics

| # | Concern | Status | Evidence |
|---|---|---|---|
| 29 | CAGR | **A** | Compounded daily over all business days, including no-trade days, at 1× capital. Idle cash earns 0%, which understates; earlier versions that annualized on trade days only were corrected. |
| 30 | Sharpe | **A** | Daily returns including flat days, √252 annualization, RF = 0. With RF at T-bill rates, Sharpe falls by about 0.1–0.2. |
| 31 | Serial correlation | **A** | Lag-1 autocorrelation is −0.002 (ITB) and −0.016 (NAIL). Positions are flat every day, so there is no return smoothing. |
| 32–33 | Max drawdown and duration | **A** | In the headline table. Durations are long: ITB 993 days and NAIL 694 days, both mostly the dead 2016–19 period. |
| 34 | Tail risk | **A** | Expected shortfall in the table. NAIL's worst backtest day is −10% (with no stop); a 3% stop limits it in practice except when the price gaps through. Without the regime filter, NAIL's worst day was −29%. |
| 35 | Leverage | **A** | NAIL *is* the leverage. Applying 1.5× or 2× on top of NAIL raises CAGR but pushes max drawdown to −62% / −74%, so it isn't recommended. |
| 36–37 | Concentration / correlation | **N** (by design) | One signal, one sector. The ITB and NAIL books are one bet (correlation 0.97). Running both is not diversification. |
| 38 | Benchmark | **P** | Positions are flat 23 hours a day with no lasting market exposure. Not yet regressed on SPY/ITB/TLT factors. Buy-and-hold ITB over 2016–26 returned more in total but with about a −45% max drawdown (approximate, not recomputed). |

## 5. Monte Carlo

- **Method:** 20,000 one-year paths, run two ways for comparison: an independent daily shuffle (iid) and a 20-day block bootstrap.
- **Edge assumption:** half the historical mean edge (a haircut for decay and selection).

| 1-year forward, half edge | ITB iid | ITB block | NAIL iid | NAIL block |
|---|---|---|---|---|
| Median return | +7.4% | +6.3% | +25.8% | +22.4% |
| 5th-percentile return | −10.1% | −12.4% | −26.8% | −30.2% |
| P(losing year) | 25% | 31% | 24% | 29% |
| Median max drawdown | −8.5% | −9.3% | −22.9% | −24.3% |
| P(drawdown > 30%) | 0% | 0% | 25% | 29% |
| P(drawdown > 50%) | 0% | 0% | 1.2% | 1.7% |

| # | Status | Note |
|---|---|---|
| 39 | **A** | The block bootstrap keeps volatility clustering. It gives about 5 points worse tails than the iid shuffle. |
| 40 | **P** | Resampling can't produce a loss larger than the worst one in history. Tail risk beyond the sample comes from the gap-through-stop case. |
| 41 | **A/P** | Handled by the half-edge haircut. A full parameter-uncertainty model hasn't been run. |
| 42 | **A** | See #20 (2× and 4× cost stress). |
| 43 | **N** | The Monte Carlo resamples the whole 10-year mix. A regime-switching model (e.g. drawing 2016–19-like years with some probability) hasn't been built. The simplest stand-in: 2016–19 returned about 0. |
| 44 | **A** | Blocks are drawn from about 1,100 real trades. The paths are not treated as extra independent data. |
| 45 | **A** | Probability of a > 50% drawdown within one year: NAIL ≈ 1.5%, ITB ≈ 0. |

## 6. The "three independent AI validations"

As noted under "Read this first", I have no record of those runs. These answers cover the GapUp work only.

| # | Status | Note |
|---|---|---|
| 46 | **A** for this work | No LSE Terminal engine was used. |
| 47 | **P** | One blind re-implementation was written from a plain-text spec without seeing the original code; it matched all 570 trades. A shared mistake in the spec itself would survive that test. |
| 48 | **A** | All statistics are computed in our own code from raw bars. Today's audit is a third independent implementation. |
| 49 | **A** | 570 of 570 trades matched on the 2024–26 set. |
| 50 | **A** | Scripts, cached raw bars and trade CSVs are kept in the research folder. |
| 51 | **A** | Two price sources differ by 0.5 bp per trade on average. |
| 52 | **A** | Yes. Every result here comes from implementations independent of LSE Terminal. |

## 7. Forward paper trading

| # | Concern | Status | Evidence |
|---|---|---|---|
| 53 | Forward performance | **N** (too early) | **Real paper results:** ITB 6 trades, +3.3%; NAIL 5 trades, −2.9%. The pre-registered forward test needs 250 trades. There is also a sealed 2-month holdout: +15 bp, t 1.07. |
| 54 | Paper vs live | **N** | Alpaca paper doesn't simulate the opening auction realistically (see #19). This is the most important open question. |
| 55 | Reliability | **P** | Bugs found and fixed in the first 10 days: a false drawdown kill, the late order rejected for buying power, the exit blocked by a held quantity, a duplicate order ID, and NaN values on the dashboard. A sixth was found and fixed 10-29: a trade closed by its stop was journaled as $0 P&L (10-28, NAIL −$63.85). The exit now books realized P&L from the broker's fills, it is checked against the real 10-28 orders, and there is a regression test. |
| 56 | Risk controls | **A/P** | 3% stop per trade, a per-account drawdown kill switch (tested, and it fired once falsely), an afternoon failsafe that closes anything left open, a KILL file and a regime switch. Paper only; live trading needs explicit confirmation. |
| 57 | Data outages | **A** | Missing or flat data means no trade. Broker or DNS failures leave the position flat and are logged. |
| 58 | Degradation | **P** | The forward test has a registered pass/fail rule. An automatic "edge has decayed" alarm isn't built. |
| 59 | Capital | **A** | Two $2,000 paper accounts. No real capital. |
| 60 | Operational resilience | **P** | Runs on a laptop under launchd and has missed sessions when the Mac was off. It needs an always-on host before real money. |

## Bottom line

- **The edge is real.** It holds across four data sources and a blind re-implementation, with t ≈ 4.5–5.4 over 10 years and placebo p < 0.0005.
- **It is regime-bound.** The edge was zero in 2016–19, and the 68% NAIL CAGR leans on 2020–26.
- **It is selection-taxed:** about 16,500 variants were tried.
- **It is execution-fragile:** the edge is in the opening auction, and paper fills so far haven't come from the auction.
- **Realistic planning numbers** (half the historical edge):
  - ITB: about +6–7% a year, with a 25–30% chance of a losing year.
  - NAIL: about +20–25% a year, with a 25–30% chance of a drawdown over 30%.
- **What 7 days of forward trading show:** nothing yet, statistically.

**Next confidence step:** run real-broker auction orders at small size (or IBKR paper) to measure actual opening fills against the backtest. That one test decides whether the backtest's returns are reachable at all.

Audit script and output: `research/xmkt_1027/audit_1029.py`, `audit_1029.json`.
