# Asia semis -> US semis at the open (round 10)  VERDICT: NONE

## Setup
- Signal: Asia-session return D (prev Asia close -> close on D) for 000660.KS, 005930.KS, 2330.TW, 8035.T, 6857.T, 6920.T, plus
  COMP = equal-weight mean of the 6 (needs >=4 live). Raw, and residual = Asia ret - beta x ^SOX ret of the last US session before D
  (beta = rolling 250-pair OLS using only pairs strictly before D). Rules: sign, or z>=1 / z<=-1 (z = ret / past 60d std, shifted 1 day).
- Timing: Asia closes are 01:30-02:30 ET (KRX 15:30 KST, TSE 15:30 JST, TWSE 13:30 CST) vs the US open at 09:30 ET on the same
  calendar date, so signal is known >=7h before entry. yfinance US 60m bars are START-labeled: the 09:30 bar Open is the entry fill,
  the 09:30 bar Close = 10:30 exit, the 10:30 bar Close = 11:30 exit, the 15:30 bar Close = close exit. Asia holiday = no bar = no trade.
  Mon: the Asia return spans Fri's US session; the residual strips that (prior-US-session SOX = Fri).
- Entry never uses the US stock's own gap. Costs 2 bp/side (MU, NVDA, AMD, AVGO, AMAT, LRCX, KLAC, ETFs), 5 bp (TER, MRVL).
- Sample 2023-11-17..2026-10-16 (727 days). Dev = first 55% (to 2025-06-24), check = 2025-06-25 on.
- Variants: 7 signals x 13 US names (incl. SPY, XLP controls) x raw/res x sign/z1 x 3 exits = 1092 (924 non-control; 168 on
  the "natural" pairs: SKH/Samsung->MU, TEL/Lasertec->AMAT/LRCX/KLAC, Advantest->TER/KLAC, TSMC->NVDA/AMD/SMH, COMP->SMH). Flip grid: 924 more.

## Result: no edge
- Mean dev t over all 924 non-control variants is -0.77 (9% of them < -2): the average rule LOSES. Max dev t = 2.0 (3 variants > 1.65);
  none of the 168 natural pairs exceeds dev t 1.28. With ~900 tries, a max t of 2 is what noise produces.
- Top picks (net bp/trade; dev | check):
  - 8035.T -> LRCX, raw z1, 09:30->10:30 (best natural): dev n92 +18.8bp t1.28 win57% | check n87 +4.7 t0.21 win54%.
  - 000660.KS -> LRCX, resid z1, ->close (best overall): dev n112 +44.7 t2.00 win61% | check n98 +11.8 t0.38 win54%.
  - 000660.KS -> MU, raw sign, ->10:30: dev n360 +10.8 t1.18 | check n305 -16.5 t-1.18 (sign reverses).
  - 000660.KS -> MU, resid z1, ->close: dev n112 +26.0 t1.08 | check n98 +20.9 t0.54.
  - COMP -> SMH, raw sign, ->10:30: dev n365 -5.6 t-1.03 | check n299 -3.0 t-0.46. COMP -> MU: dev -0.6 t-0.06 | check +4.8 t0.34.
  - No variant has dev t>1.65 AND check t>1.65 (0 of 3 survive; 0 for natural).
- Why: the Asia signal is already in the US open. corr(COMP z, US open-vs-prev-close gap) = 0.36 MU / 0.43 SMH / 0.30 AMAT, but
  corr with the 09:30->10:30 return is -0.04 / -0.07 / +0.03. Regressing the gap on z gives ~120 bp per z (MU); post-open drift is
  ~-9 bp per z (slight reversal, not catch-up). The 09:30 auction is NOT under-pricing it, unlike ZB->ITB.
- Long history sanity (daily Open->Close, sign rule, 2010-2026, GROSS bp, n~3,950): 8035->LRCX +8.1 (t2.5), 8035->KLAC +5.8 (t1.9),
  000660->MU +7.8 (t2.0), 005930->MU -1.8, 2330->NVDA -2.3, COMP->SMH +1.3, COMP->SPY +0.4. Small and positive only for Tokyo
  Electron/SK Hynix, and below or equal to the 4 bp round-trip cost plus a t that does not survive the multiplicity above.

## Controls
- Same signals on SPY and XLP (non-semi): mean dev t -1.70 / -1.61, check t -2.15 / -1.73 (net -6 to -9 bp: pure cost + mild
  reversal). COMP raw sign -> SPY ->10:30: dev -3.4bp t-1.77, check -3.6 t-1.97. Placebos are NOT ~0 but negative, so even the
  semis' lack of edge is not far from the placebo.
- Flip (opposite direction): max dev t 2.66 (6920.T->NVDA resid z1) but check -9.5 t-0.67; 16 flip variants with dev t>2,
  0 with check t>2 (4 with check t>0). Flips on the top picks above: dev -18..-53bp, check mostly negative (000660->MU raw sign
  flip: dev -18.8 t-2.06, check +8.5 t+0.61). No consistent reversal edge either.

## Correlation with the ZB->ITB rule (f3_trades_canonical.csv, net = g_off - 0.0004)
- 8035->LRCX z1 10:30: +0.06 (n=145 overlap days); 000660->LRCX resid close: -0.09; 000660->MU raw 10:30: -0.04;
  000660->MU resid close: -0.14; COMP->SMH: +0.06. Uncorrelated (but there's nothing here to diversify with).

## Caveats
- TSM ADR: TSMC (2330.TW) is also traded in the US as TSM, which trades the Taiwan move during the prior-day US session, in
  04:00-09:30 ET pre-market, and at the open. NVDA/AMD/AVGO/SMH also have pre-market prints (not in yfinance 60m) that arbitrage
  Asia headlines before 09:30. So the TSMC channel is the least likely to be slow, and the gap regression shows the open absorbs
  the news. The TSM ADR itself was not used as a signal (its US-session move is not an overnight, different-market signal).
- yfinance 60m 09:30 Open may be the first regular print rather than the official opening auction price; the effect would only blur.
- 60m history is only ~3 years (727 days); dev/check have ~90-110 trades for z1 rules, so t ~1-2 are weakly powered. The long daily
  check above is the higher-powered cross-check and also shows nothing net of cost.
- Variants used here share the same ~700 US days and highly correlated names, so the effective number of independent tests is lower
  than 924, but the mean-t shift (-0.77) is the more telling evidence.

Files: dl.py (download), build.py (signal/US panel), test.py (grid), diag.py, fin.py; cache/, panel.pkl, grid.pkl.
