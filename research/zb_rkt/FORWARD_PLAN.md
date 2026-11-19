# Forward paper test: ZB overnight → RKT first hour (`zb_rkt_v1`)

Registered 2026-10-18 (Sunday), before the first decision on Monday 2026-10-19. This is a second leg next to `zb_itb_v1`, with the identical rule and signal. Paper only: scored on public data, no orders.

## What is known (found in round 5 among about 50 names, so selection-biased)
- yfinance 60m, 2024-05..2026-10, at 5 bp/side: dev (≤2025-06) +61 bp, t 4.8; check +32 bp, t 2.6; 570 trades.
- Correlation of trade P&L with ITB is 0.41. Volatility is about 2× ITB.
- A 2/3 ITB + 1/3 RKT mix had Sharpe 4.1 vs 3.45 for ITB alone (most of the gain is in dev).

## Rule (fixed)
The same as `research/zb_itb/FORWARD_PLAN.md`, with RKT as the instrument:
- d = sign(ZB=F 60m close at 09:00 ET / close at 16:00 ET on the previous session), recorded between 09:15 and 09:29:30 ET.
- Hold d × RKT from the 09:30 open to 10:30 (yfinance 60m 09:30 bar).

## Costs
5 bp per side base, 10 bp per side stress.

## Gate
- Final n = 250.
- PASS if the gross t ≥ 1.65 and the mean net at 5 bp/side > 0.
- KILL if the cumulative net at 5 bp/side ≤ −10%.
