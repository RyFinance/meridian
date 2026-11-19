# ZB overnight → ITB first hour: verification (2026-10-18)

Rule: d = sign(ZB=F close at 09:00 ET / close at 16:00 ET on the previous session). Hold d × ITB from the 09:30 open to 10:30.

## 1. Are the backtest numbers computed correctly? YES
- **Blind re-implementation:** a separate agent coded the rule from a written spec without seeing this code. It matches all 570 trades exactly (directions, returns, every stat). `blind/`
- **Bar timing:** ZB and ITB hourly bars are start-labeled (the 08:00 ZB bar is 08:00–09:00, confirmed against 5m bars). The signal ends at 09:00, so there is no look-ahead. `audit_timing.py`
- **Fill price:** using ITB's official daily open, which is what an MOO auction order gets, gives +22.4 bp, slightly better than +21.7 bp with the hourly-bar open. `f3_canonical.py`
- **Second data source:** LSE vault tick-built bars for DHI, LEN, PHM and TOL reproduce the result (+20.5 to +22.6 bp, t 3.8–4.0). `cross_source.py`
- **Contract rolls:** no artifacts. ZB's overnight sign matches TLT's opening gap on 91% of days.

## 2. Is it robust on 2024-05..2026-10 (570 trades)? YES
- **Costs:** at 2 bp/side, +22 bp (t 5.2); at 5 bp/side, +16 bp (t 3.8). Breakeven is about 13 bp/side.
- **Exit time:** exiting at 10:30, 11:30, 12:30 or 16:00 all give +22 to +25 bp. No reversal.
- **Every slice is positive:**
  - all signal-size quintiles;
  - the long side (+22 bp) and the short side (+23 bp);
  - all five weekdays;
  - every half-year (the weakest is 2025H1, +12 bp);
  - 25 of 30 months.
- **Not driven by a few days:** without the 10 best days, t is still 4.2. The median trade is +17 bp.
- **Permutation test:** p < 0.0001. The 95% block-bootstrap CI for Sharpe is 2.2–4.8.
- **Mechanism:**
  - ZB itself does not continue after 09:00 (−1 bp). Homebuilders lag the overnight rate move and catch up in the first hour.
  - Most of the signal comes from the 16:00→08:00 move (t 3.8), not only the 08:30 data releases.
- **Specificity:** it replicates in XHB and in all six builders (t 3.2–3.6). REITs, IWM, XLU, KRE and SPY are about 0. Using ZN as the signal also works (t 3.3).
- **Late entry:** entering 5 minutes late (09:35) on builders still earns +12 to +16 bp. The edge is not all in the opening print.

## 3. Does it hold over longer history? ONLY SINCE 2020 (the key caveat)
There is no pre-2024 intraday ZB data available, so this uses a proxy: the sign of TLT's opening gap, traded on the six builders.

| Period | Enter 09:30 (reference) | Enter 09:35 (tradable) |
|---|---|---|
| 2010–14 | −3.8 bp (t −1.0) | −3.5 bp |
| 2015–19 | −1.1 bp (t −0.4) | −5.1 bp |
| 2020–23 | **+14.2 bp (t 3.2)** | +4.7 bp |
| 2024–26 | **+14.5 bp (t 3.3)** | +6.7 bp |

2020–23 is independent confirmation, since the rule was found on 2024+ data. 2010–19 shows nothing. The edge belongs to the post-2020, rates-driven housing market, and it could fade if that regime ends.

## 4. Realistic account results (2024–26, 1× capital)
| Account | Yearly | Max DD |
|---|---|---|
| Margin ≥ $25k, long/short, $0 commission, 1/2 bp slippage | +72% | −12% |
| Same, stressed 3/5 bp slippage | +52% | −13% |
| Margin < $25k (pattern-day-trader rule: 3 trades per 5 days) | +52% | −7% |
| Cash account, long-only | +24–29% | −6% |
| $250 at a $1-minimum-commission broker | −37% | −67% |

## 5. What to expect live
- The backtest Sharpe of 3+ comes from a short, favorable window, and the effect is regime-dependent.
- Plan on roughly half the backtest edge, about +10–12 bp/trade net: roughly +25–35%/yr long/short, or +10–15%/yr long-only.
- Accept the risk that it stops working.
- The forward test `zb_itb_v1` (registry seq 9) is the arbiter.

## 6. Execution timing (vault 1m, six-builder basket, 546 days)
- Cumulative signed return from the 09:30 open: +5.5 bp at 09:30, +8.8 bp at 09:35, +17.2 bp at 09:45, +25.0 bp at 10:29.
- Net at 3 bp/side, entering late and exiting at 10:30:
  - 09:31: +11.8 bp (t 2.6)
  - 09:35: +10.2 bp (t 2.5)
  - 09:40: +5.7 bp
  - 09:45 or later: about 0
- **Live implication:** enter with a market-on-open (MOO) order submitted before about 09:25. A late fallback entry is acceptable only before about 09:36. Skip the day if not filled by then. (`intraday_path.py`)

## 7. Overnight additions (2026-10-18, rounds 5–6)
- **Duration ladder (signal → ITB, net/trade):** ZT +10 (t 2.3), ZF +13.5 (t 3.1), ZN +14.7 (t 3.3), ZB +22.4 (t 5.2), UB +24.4 (t 5.7). The step-up with duration is what the mortgage-rate mechanism predicts.
- **Deflated Sharpe probability:** 0.99 at 288 trials, 0.93 at 6,000 (about this session), 0.88 at 20,000.
- **RKT (Rocket):**
  - At 5 bp/side: dev +61 bp (t 4.8), check +32 bp (t 2.6).
  - TLT-proxy 2020–23: +21 bp (t 2.8), independent of selection.
  - A 2/3 ITB + 1/3 RKT mix: Sharpe 4.1 vs 3.45, max drawdown −8.6% vs −12%.
  - Forward test `zb_rkt_v1` (seq 10).
- **No improvement from:** |m| sizing, ZN composites, NAIL (just 2.9× leverage), later exits, the unpriced-gap logic, an SPY hedge (Sharpe 2.96), or options (spreads take the edge; only 9% of legs had prints).
- **No lag elsewhere:** oil→airlines/cruise/truckers, gas→producers/utilities, grains→ag stocks, FX→ADRs/multinationals/EM, rates→bond ETFs/insurers/brokers/REITs/banks. No intraday hour-to-hour lag either: the edge is the overnight→open handoff only.
- **When it pays:**
  - Broad: non-release days +20 bp (t 4.1); jobs/FOMC days +44–53 bp; every regime tercile positive.
  - Post-holiday sessions −54 bp (n 18), logged and not filtered.
  - Capacity is about $0.5M per trade (1% of first-hour ITB volume).
- **Pre-market entry (09:15, builders, vault 1m):** +12 bp more gross than the open, but liquidity is very thin (~100 shares per 15 min). It breaks even with MOO at ~15 bp entry cost. Candidate for a small paper experiment only.

## 8. Regime switch (2026-10-19)
The edge needs homebuilders to trade WITH bonds. Use the past-only 60-day correlation of daily ITB vs TLT returns.
- **Median correlation:** −0.35 (2010–14), −0.16 (2015–19), +0.12 (2020–23), +0.41 (2024–26). It is +0.66 now.
- **TLT-proxy history**, trading only when corr > 0, net per trade:
  - 2010–14: +32.6 bp (t 3.4)
  - 2015–19: −7.4 bp
  - 2020–23: +13.6 bp
  - 2024–26: +14.5 bp
  - All years: +12.9 bp (t 4.7), vs +4.3 bp (t 2.3) with no switch.
- **Live rule 2024–26:** the switch would have skipped 0 trades.
- **Interpretation:** before 2020, bonds rallied on risk-off days (bad for builders). Since 2022 the stock–bond correlation is positive.
- **Use:** a live safety switch (skip when corr ≤ 0), not a return booster.

## 9. Independent price source + 10-year tradable test (2026-10-19, Alpaca SIP 1-minute bars, all US exchanges)
- **2024–26, live ZB signal, SIP prices:**
  - ITB +22.0 bp (t 5.0), win 58.3%, Sharpe 3.37, max DD −13% (yfinance: +21.5 bp). Per-trade correlation 0.997.
  - NAIL +71.1 bp (t 5.3), Sharpe 3.63, max DD −28%.
  - **Confirmed.**
- **2016–26, fully tradable proxy signal:** sign of TLT's last pre-market trade at 09:25 vs the previous 15:59 close. It agrees with ZB 91% of the time.
  - **ITB:**
    - 2016–19: +0.1 bp
    - 2020–23: +7.4 bp (t 1.9)
    - 2024–26: +19.9 bp (t 5.1)
    - All 10 years: +7.9 bp (t 4.0), Sharpe 1.24, max DD −34%. With the regime switch: +11.3 bp (t 4.5), Sharpe 1.78, max DD −19%.
  - **NAIL:**
    - All 10 years: +46.9 bp, Sharpe 2.06, but **max DD −73% (2020–23)**.
    - With the regime switch: +57.3 bp (t 6.1), Sharpe 2.77, max DD −29%.
- **Reading:**
  - The 2024–26 strength is real (two price sources), but it is the best regime in 10 years. 2020–23 ran at about a third of it, and 2016–19 at zero.
  - NAIL without the regime switch can lose ~3/4 of the account in a bad regime. The switch roughly halves NAIL's and ITB's worst drawdowns.
