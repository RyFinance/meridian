# Forward paper test: ZB overnight → ITB first hour (`zb_itb_v1`)

Registered 2026-10-17 (Saturday), before the first decision on Monday 2026-10-19. Paper only: decisions are recorded in `reports/forward/registry.jsonl` and scored on public market data. No orders are placed anywhere.

## What is known (no hidden hold-out left)
- Found by the round-4 fx_rates agent (288 variants), then verified independently (`research/btc_ah/lead_verify/zb_itb.py`).
- yfinance 60m data, 2024-08..2025-06: +15.7 bp, t 2.8.
- 2025-07..2026-08-10: +27.4 bp, t 3.9, n 267.
- Replicates in XHB, LEN, DHI, PHM, TOL, KBH and NVR. Placebos XLU, KRE and SPY are about 0.
- Sealed holdout 2026-08-11..10-16: +15.3 bp, t 1.07, n 46. Positive, not significant.
- Only about 2 years of hourly history exist, so the prior is moderate. The forward record is the evidence that counts.

## Rule (fixed)
On every NYSE session:
1. P0 = the close of the ZB=F 60m bar that ends at 16:00 ET on the previous NYSE session (yfinance). P1 = the close of the ZB=F 60m bar that ends at 09:00 ET today.
2. d = sign(ln(P1 / P0)). If d = 0 or either price is missing, there is no trade.
3. Record the decision between 09:15:00 and 09:29:30 ET (yfinance futures data is about 10 min delayed, so the 08:00–09:00 bar is final by then). A decision recorded at or after 09:30:00 is excluded.
4. Position: d × ITB, entered at the official 09:30 open and exited at 10:30 ET. Score = d·ln(close of the ITB 09:30 60m bar / its open), from yfinance 60m.
   - The long-only variant (d = +1 days only) is reported alongside the primary.

## Costs
2 bp per side (4 bp round trip) base, and 5 bp per side stress.

## Gate
- Final n = 250 scored trades.
- PASS if the gross t ≥ 1.65 and the mean net at 2 bp/side > 0.
- KILL early if the cumulative net at 2 bp/side ≤ −8%.
- No re-tuning; any change means a new strategy id.
