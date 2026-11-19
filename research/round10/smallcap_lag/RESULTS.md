# smallcap_lag: do small caps open under-repriced vs the overnight ES move? (round10, 2026-10-19)

**Verdict: NONE.** Small caps price the ES overnight move fully at the open (open-gap slope on m is 0.8-1.2). Open->10:30 drift on m is zero in every liquidity tercile, and no tercile shows a larger lag. Gross is about 0 for the entry rule and for the "unpriced" variant, so costs make every net result negative.

## Rule (pre-set from the brief, no selection)
- m = ln(ES=F close of the 60m bar starting 08:00 ET on D / close of the bar starting 15:00 ET on the prior session), i.e. 16:00 -> 09:00. NQ=F and RTY=F built the same way.
- **A (entry rule):** direction = sign(m); buy/sell at the official daily Open (MOO), exit at the 10:30 close (close of the 60m 09:30 bar). Stock's own gap is not used.
- **B (unpriced):** beta_i = past-only 120-day OLS slope (min 60 obs, shifted 1 day) of the stock's dividend-adjusted open gap on m. At 10:30 (open of the 10:30 bar) trade sign(beta_i*m - gap_i); exit at the daily close. B2 = same but with the total move prev close -> 10:30 instead of the gap.
- Equal-weight daily basket across names; costs 5 bp/side (10 bp/side for the least liquid tercile, 2 bp/side for ETFs and mega caps, 5 for IWC).
- Split: 577 signal days 2024-05-29..2026-10-16. dev = first 55% (n=317, to 2025-09-22); check = rest (n=260). B has fewer dev days (257) because beta needs 60 days of history.

## Checks
- Labels: START-labeled futures bars. ES/NQ/RTY have 585-600 bars per label hour except hour 17 (3-7 bars, the CME 17:00 break); bar 16:00 exists. SPY's 09:30-10:30 return correlates 0.68 / 0.52 with ES bars labeled 09 / 10 and about 0 (0.06 / -0.04) with those labeled 08 / 11. So the 08:00 bar closes at 09:00, no look-ahead.
- Official Open vs 60m 09:30 Open: median diff 0 bp. Entry A uses the daily Open only; B enters at 10:30, after its gap is known.
- Caught and fixed a daily-date shift bug (UTC->NY on naive dates) that had produced fake +220 bp results; RGR dropped (60m prices 2.67x the daily series); ALKS dropped (pharma).
- Universe: 122 names hand-picked across sectors, no biotech, with yfinance current market cap $0.3-3B and dev-period median $ADV > $5M. Terciles by dev ADV: L $5.1-10.2M (41), M $10.3-16.4M (40), H $17.1-98M (41). Current-day cap and survivor-only selection is a caveat, but it cannot create a lag that is absent in gross.

## Results, ES signal, net bp/trade/day-basket (gross in brackets)
| Basket | Rule | Dev n | Dev net | Dev t | Chk n | Chk net | Chk t | Chk win |
|---|---|---|---|---|---|---|---|---|
| small ALL | A | 317 | -16.1 (-2.8) | -4.0 | 260 | -14.8 (-1.4) | -3.4 | .40 |
| small L (least liquid) | A | 317 | -23.3 (-3.3) | -5.4 | 260 | -23.9 (-3.9) | -5.5 | .35 |
| small M | A | 317 | -13.7 (-3.7) | -3.6 | 260 | -11.5 (-1.5) | -2.6 | .41 |
| small H | A | 317 | -11.3 (-1.3) | -2.5 | 260 | -9.0 (+1.1) | -1.8 | .45 |
| small ALL | B | 257 | -11.8 (+1.6) | -4.1 | 260 | -12.4 (+0.9) | -5.7 | .30 |
| small L | B | 257 | -18.9 (+1.1) | -5.4 | 260 | -19.0 (+1.1) | -7.4 | .27 |
| small ALL | B2 | 257 | -14.0 (-0.6) | -3.8 | 260 | -7.8 (+5.6) | -3.2 | .36 |

- Gross t of every A/B cell is |t| < 1.4 on dev; the largest gross check value is B2 +5.6 bp (t 2.3), which is not present in dev (-0.6) and is 2x below the cost. 
- NQ and RTY signals: the same pattern (A small ALL gross dev/check: NQ -3.2/-2.4, RTY -0.3/+3.0; L tercile RTY +0.1 on check). The best dev-gross cell, NQ rule B H-tercile (+6.2 dev, t 1.4), is +1.6 gross on check (t 0.5) and -9.4 net. NQ/RTY B small ALL gross is +2 to +5 bp, still below the 10 bp round trip.
- Mechanism test (daily basket, slope on m): open gap L/M/H = 1.23/1.18/1.22 dev and 1.01/0.92/0.79 check (t 11-20), so the open already prices m (slightly over-prices it). Open->10:30 slope L/M/H = +0.03/-0.01/+0.09 dev and -0.09/0.00/0.00 check (all |t| < 1.1). 10:30->close slope is -0.13 to -0.19 (t -1.2 to -1.7, mild reversal). No lag, and no gradient with illiquidity.
- |m| conditioning (top third by |m|, threshold from dev): A gross -0.4 dev / -3.5 check (L tercile -0.2 / -6.9).
- Names: 30% of names have positive A gross in dev and 45% in check; cross-name corr(dev, check) 0.20; 3 of 122 have |t| > 2 on check, which is chance.

## Controls (A rule, check half; gross/net bp)
- Flip (opposite sign), small ALL: gross +1.4 / net -11.9 (t -2.8); L tercile flip net -16.1 (t -3.7). Both directions lose to costs.
- Large caps (28 names: AAPL MSFT JPM etc., 2 bp/side): gross -2.3, net -6.3 (t -3.2). SPY -1.3 / -5.3 (t -2.6). QQQ -1.9 / -5.9. IWM -5.7 / -9.7 (t -2.6). IJR -4.0 / -8.0. IWC (micro-cap) -7.4 / -17.4 (t -3.3); SLY has no yfinance data.
- Rule B placebo: SPY check gross +2.6 / net -1.4 (t -0.4); large caps +1.9 / -2.1; IWC -3.9 / -13.9. Small caps behave like the controls, i.e. 0 gross.

## Correlation with ITB rule P&L (f3_trades_canonical.csv, net = g_off - 0.0004, matched days)
- A basket net vs ITB: 0.11 (n=577). B basket vs ITB: 0.05 (n=517). Both are irrelevant because neither rule earns anything.

## Variants counted
About 60 cells: 3 signals x 4 groups x 3 rules (36), 10 control baskets x 2 rules (20) plus flips (4), plus 4 |m| cells. Nothing survives even uncorrected, so no correction was needed.

## Files
`univ.py` tickers, `dl.py` downloads, `build.py` panel/signal, `core.py` rules, `an1.py` grid, `an2.py` controls, `an3.py` mechanism/ITB, `label_check.py` bar labels.
