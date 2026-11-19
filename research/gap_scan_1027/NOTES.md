# Gap scan 2026-10-27 (00:40–00:45 PT, CAGR focus)

Data: yfinance 60m, ~2024-11 → 2026-10 (same window the ZB→ITB edge was found in, so not an independent test).
Rule: d = sign(futures 08:00 ET bar close / prev 15:00 ET bar close); trade target from the 09:30 open to the
10:30 / 11:30 / 13:30 / 16:00 bar close; 5 bp/side. Direction picked on the first half, scored on the second.

- 11 overnight signals (ZB, ZN, CL, GC, ES, NQ, RTY, HG, NG, 6J, BTC) × 30 leveraged/high-beta targets × 4 holds = 1,320.
  Only rates → housing/mortgage survives (NAIL, RKT, UWMC). Oil, gold, equity index, copper, natgas, yen and BTC: nothing.
- Own-gap follow/fade (entry at 10:30 to avoid the same-print trap), 60 combos: none pass.
- Best by CAGR: ZB → NAIL held to the close: 448% CAGR, Sharpe 2.45, max DD −50%.
  Hold to 13:30: 418%, Sharpe 2.67, −45%. Live today (10:30 exit): 314%, Sharpe 2.95, −39%.
  Skip the smallest 25% of ZB moves: close-hold 382%, Sharpe 2.88, −42% (best CAGR/Sharpe balance).
- The regime switch never turned off in this window, so it changes nothing here.
- Scan picked from 1,320 tries: expect live to be well below backtest. Forward-test before changing the live exit.
