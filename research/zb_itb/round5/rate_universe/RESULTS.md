# Round 5 / rate_universe: who else lags overnight Treasury moves? (2026-10-18)
Rule: d=sign(ZB or ZN 60m close 08:00 bar / 15:00 bar prev day); trade d x stock, official open (1d Open) -> 10:30 (60m 09:30 bar Close).
Costs RT: 4bp (ETFs, large caps, AGNC/NLY/FNF/builders-large), 10bp (small/mid), 20bp (NAIL, REZ). dev 2024-05-28..2025-06-30 (n=260), check 2025-07-01..2026-10-16 (n=310).
Not available on yfinance (skipped): COOP, TMHC, TPH, AZEK, EQR/AVB (only ~150 bars). IWM not re-run. 49 names x 3 signals (ZB, ZN, ZB&ZN agree) + 15 baskets = ~190 cells tried. Files: all_results.csv, clusters.csv, an.py, cl.py.

## Single names, ZB signal, net bp/trade (t) [flip = opposite direction, net bp]
| sym | dev | check | win dev/chk | flip dev/chk |
|---|---|---|---|---|
| RKT | 60.8 (4.8) | 32.3 (2.6) | .60/.58 | -81/-52 |
| UWMC | 45.5 (4.3) | 20.3 (1.5) | .59/.51 | -66/-40 |
| FNF | 16.9 (3.1) | 9.9 (1.6) | .57/.54 | -25/-18 |
| ITB (ref) | 16.6 (2.9) | 27.2 (4.3) | .58/.59 | -25/-35 |
| NAIL | 39.3 (2.4) | 65.6 (3.5) | .55/.57 | -79/-106 |
| AGNC | 13.3 (2.3) | 8.5 (1.9) | .55/.55 | -21/-17 |
| LOW | 11.2 (2.1) | 12.3 (2.1) | .51/.55 | -19/-20 |
| CCS | 17.7 (2.0) | 14.4 (1.6) | .55/.51 | -38/-34 |
| XHB (ref) | 10.7 (2.0) | 22.1 (3.9) | .54/.57 | -19/-30 |
| PFSI | 13.3 (1.8) | 13.9 (1.7) | .53/.53 | -33/-34 |
| PHM/LEN/DHI | 12/11/11 (1.5-1.8) | 24/24/25 (3.0-3.1) | | |
| DFH, LGIH | 18, 16 (1.3-1.5) | 43, 32 (3.4, 2.6) | | |
| NLY, FAF, MHO, HD | 7-11 (1.4-1.9) | 5-12 (1.2-1.7) | | |
| POOL, SHW, MHK, MTH, OC, TOL, BLDR | ~0-10 (<1) | 16-29 (2.3-3.9) | | check only, NOT selected on dev |
| SPY (placebo) | -1.9 (-0.75) | -1.4 (-0.74) | .48/.48 | -6/-7 |
| RDN MTG ESNT TREX FBIN WHR MAS O PLD XLRE ELS SUI INVH AMH | all |t|<1 on dev, no sign of edge | | |
| MAA UDR CPT ESS REZ TLT | negative (t -1.3 to -3.3 both periods): TLT/apartment REITs mean-revert slightly (gross ~-2 to -3bp), not tradable inverse after costs | | |
ZN signal is the same ranking, weaker everywhere (RKT 60/20, ITB 13/16, UWMC 49/5). Full table in all_results.csv.

## Multiple testing
Bonferroni over 49 names (|t|>~3.3 on dev): only RKT and UWMC pass (t 4.3-4.8; AGR signal 5.1). ITB/FNF (2.9-3.1) are marginal. By check, RKT holds (2.6), UWMC does not (1.5). Everything with dev t 1.5-2.3 (LOW, CCS, AGNC, NAIL) is noise-level on dev alone; their check-period t is positive only because the whole housing complex rallied/continued in the check window (shared factor, not independent confirmation).
Check-period t-stats of 2.5-3.9 in names that were ~0 on dev (POOL, SHW, MHK, MTH, TOL) are not evidence: not selected on dev, and the 2025-26 sample is clearly regime-specific. Per-name results are highly correlated.

## Clusters (equal weight, net, ZB signal) dev / check bp (t) ; Sharpe check
| cluster | dev | check | Sharpe chk | vs ITB on check (paired t) |
|---|---|---|---|---|
| ITB | 16.6 (2.9) | 27.2 (4.3) | 3.9 | ref |
| XHB | 10.7 (2.0) | 22.1 (3.9) | 3.5 | -5.2 (-2.6) |
| mortgage originators RKT UWMC PFSI | 39.9 (4.6) | 22.2 (2.3) | 2.1 | -5.1 (-0.6) |
| builders, all 11 | 11.2 (1.6) | 21.7 (2.8) | 2.5 | -5.5 (-2.2) |
| builders 5 small | 13.6 (1.6) | 23.7 (2.6) | 2.4 | -3.5 (-0.9) |
| builders 6 large | 9.2 (1.5) | 20.1 (2.8) | 2.6 | -7.2 (-3.2) |
| builders+mortgage orig (14) | 17.3 (2.6) | 21.8 (3.0) | 2.7 | -5.4 (-2.0) |
| builders+products+mortgage (25) | 11.2 (2.0) | 19.4 (2.9) | 2.7 | -7.8 (-4.0) |
| building products (11) | 3.3 (0.7) | 16.3 (2.5) | 2.3 | -10.9 (-3.9) |
| HD+LOW | 9.2 (1.9) | 10.9 (2.0) | 1.8 | -16 (-4.3) |
| mREITs AGNC+NLY | 11.3 (2.1) | 7.0 (1.7) | 1.5 | -20 (-3.4) |
| title/MI FNF FAF MTG RDN ESNT | 2.1 (0.4) | 3.3 (0.7) | 0.6 | -24 (-4.0) |
| apartment/SFR REITs (8) | -5.1 (-1.3) | -4.5 (-1.3) | | -32 (-5.4) |
Flip control on every cluster is strongly negative (-15 to -43 bp). Placebo SPY ~0.
SPY-hedged (beta 1, +4bp): ITB 10.5/20.6 (t 1.9/3.3), builders 5.1/15.1, mortgage orig 33.8/15.6 -> a good part of the edge is market beta in the first hour; ITB itself is least diluted.

## Sign agreement ZB & ZN
Agreeing days (88% of days) are not better per trade for ITB in check (25.2 vs 27.2 all; disagree days +45bp, n=31, t 2.6, dev +10.6). ZN-only signal is weaker than ZB for every name. Only for mortgage originators does agreement lift dev (48 vs 40 bp, 5.2 vs 4.6 t) but check 21.5 vs 22.2: no help. Verdict: ZB alone; agreement filter does not help (n=30 disagree days is too few to say it hurts).

## Verdicts
- Mortgage originators (RKT, UWMC, PFSI): WEAK-to-EDGE on dev (largest gross, ~60bp), decays ~half in check (UWMC t 1.5). Costs assumed 10bp RT are optimistic given wide opens; borrow/liquidity at MOO unverified. Candidate for forward test, no better than ITB after cost risk.
- Builders (small/large/all): EDGE-consistent with ITB (same sign, check t 2.6-2.8) but dev t only 1.5-1.6 per basket; no basket beats ITB on check (all negative vs ITB). ITB is the efficient expression.
- Building products / HD, LOW: WEAK (dev ~0-9bp, check positive; weaker beta-driven version of the same thing). LOW alone dev t 2.1.
- NAIL (3x homebuilders): high bp (39/66) but 20bp cost assumed, ETF decay/illiquid; same signal as ITB levered, not independent. WEAK/redundant.
- mREITs: WEAK (t 2.1/1.7, 7-11bp). Title/MI: NONE. Apartment/SFR REITs, VNQ-like (XLRE, O, PLD): NONE. ARKK, small-cap growth (IJT, VBK), SPY: NONE.
- Overall: signal is specific to rate-sensitive housing (builders + mortgage originators); no new cluster beats ITB. Do not trade baskets; ITB (and possibly RKT in forward test) only.
