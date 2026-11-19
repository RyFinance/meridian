# Round 5: FX second-order → US equities (fx_second_order)

**Rule:** d = sign of FX 60m return from 16:00 (prev. session) to 09:00 ET. Bars are start-labeled (checked: every FX 60m bar matches its 5m OHLC). Trade d × target, entry at the 09:30 official open, exit at the 09:30 bar close (10:30). Gross = log(exit/entry). Net = gross − 2 × cost/side.
**Window:** 2024-05-28..2026-10-16. Dev 2024-05-28..2025-06-30, check 2025-07-01..2026-10-16. Priors fixed before the run.
**Costs:** 2 bp/side if median dollar volume ≥ $20M/day, else 5 bp/side.

## Primary (a priori signal and sign, 22 targets)
Strength signals: DXY (USD), 6E (EUR), 6J (JPY), JPY=X (sign flipped, so + = yen strong), 6A (AUD). Priors: yen-exporter and USD-linked names use −1 on USD or yen strength; AUD names use +1.

| Target | Signal, sign | Gross dev bp (t) | Gross check bp (t) | Net check bp (t) |
|---|---|---|---|---|
| TM | JPY −1 | 1.9 (0.5) | −0.9 (−0.3) | −4.9 (−1.8) |
| HMC | JPY −1 | 3.1 (0.7) | −0.8 (−0.2) | −4.8 (−1.3) |
| SONY | JPY −1 | 2.2 (0.5) | −2.2 (−0.6) | −6.2 (−1.6) |
| MUFG | JPY −1 | −1.0 (−0.2) | 4.5 (1.3) | 0.5 (0.1) |
| SMFG (5bp) | JPY −1 | −4.7 (−1.0) | 2.2 (0.6) | −7.8 (−2.1) |
| EWJ | JPY −1 | −0.6 (−0.3) | −0.1 (−0.1) | −4.1 (−1.9) |
| GDX | USD −1 | 12.9 (1.9) | 15.3 (1.9) | 11.3 (1.4) |
| NEM | USD −1 | 8.1 (1.1) | 14.4 (1.6) | 10.4 (1.2) |
| AEM | USD −1 | 6.3 (0.9) | 16.2 (1.9) | 12.2 (1.4) |
| KO | USD −1 | 2.8 (0.7) | 4.2 (1.1) | 0.2 (0.0) |
| PG | USD −1 | −3.8 (−0.9) | 3.1 (0.7) | −0.9 (−0.2) |
| MCD | USD −1 | 3.8 (0.8) | 3.5 (0.8) | −0.5 (−0.1) |
| AAPL | USD −1 | 10.4 (1.7) | 4.4 (0.8) | 0.4 (0.1) |
| MSFT | USD −1 | 4.3 (0.9) | 2.8 (0.5) | −1.2 (−0.2) |
| CAT | USD −1 | 0.8 (0.1) | −3.7 (−0.5) | −7.7 (−1.0) |
| DE | USD −1 | 9.7 (1.7) | 2.0 (0.3) | −2.0 (−0.3) |
| EEM | USD −1 | 1.8 (0.8) | 0.0 (0.0) | −4.0 (−1.4) |
| EWZ | USD −1 | 3.0 (0.8) | −4.2 (−1.0) | −8.2 (−2.0) |
| EWW | USD −1 | 12.5 (2.4) | 10.7 (2.4) | 6.7 (1.5) |
| BHP | AUD +1 | 4.3 (1.1) | −1.5 (−0.3) | −5.5 (−1.2) |
| RIO | AUD +1 | 2.3 (0.7) | −2.9 (−0.8) | −6.9 (−1.8) |
| EWA | AUD +1 | 2.0 (0.8) | −1.8 (−0.8) | −5.8 (−2.7) |

DXJ (yen-hedged, no prior) and SPY (placebo) are in the scan only.

## Controls
- **Flip:** the gross flip is the exact negative of the primary. Net flip, pooled over the 22 primaries: dev −8.0 bp (t −4.5), check −7.2 bp (t −4.0). This is cost-dominated, not an edge in the other direction.
- **SPY placebo** (10 variants, USD/EUR/JPY/JPY=X/AUD × 2 signs): gross |t| ≤ 1.7 dev, ≤ 0.8 check. Nothing. EUR +1 alone reached dev t 2.2, check t 0.2.
- **Pooled primary** (equal-weight, 22 names): gross dev +3.7 bp (t 2.1), check +2.9 bp (t 1.6). Net dev −0.5 bp (t −0.3), check −1.4 bp (t −0.8). Thirteen of the 22 are USD-linked, so this is mostly one USD factor, not 22 tests.
- **Cost stress** (5 bp/side, all names): the primary check net is > 0 for only 4 of 22; median −7.9 bp.

## Variants and multiplicity
- 240 variants = 24 targets × 5 signals × 2 directions (120 unique tests; the flips are mirrors).
- Dev gross |t| ≥ 2: 5 of 120 (about 6 expected under null). Those 5: AAPL EUR (2.5), EWW DXY −1 (2.4), EWW EUR (2.3), SPY EUR (2.2), DXJ EUR (2.1). On check, only the EWW pair holds (t 2.4 and 2.1), and they are one name, one factor.
- Top net-dev exploratory pick (AAPL EUR): check net +5.7 bp (t 1.1). Not a survivor.

## Sign conventions
- USD → gold miners and multinationals: a weaker USD helped in dev and check for GDX, NEM and AEM (gross, all positive). The sign is right; the magnitude is small.
- Yen → exporters (TM, HMC, SONY): dev gross positive, check gross negative. No consistent sign.

## Best rule and verdict
- **Best rule (dev-selected by gross t, and a priori):** EWW. Position = −sign(DXY move 16:00→09:00 ET); enter at 09:30 open, exit at 10:30. Dev net +8.5 bp (t 1.7); check net +6.7 bp (t 1.5) at 2 bp/side. Breakeven is about 5 bp/side (check +0.7 bp at 5 bp/side).
- **Verdict: WEAK.** A gross USD-factor tilt of about +3 bp per trade is positive in both halves. It is below 2 bp/side costs after netting. 0 of 22 primaries have check net t ≥ 2. EWW is the only nominal survivor, and it dies at 5 bp/side. Not comparable to the ZB rule (+22 bp net).

## Limits
- FX 60m exists only from 2024-05-26 (yfinance 730d). No pre-2024 intraday test, so the ZB regime check (2020 onward) cannot be run here.
- ^TNX 60m covers 07:20–13:20 CT only, so no 16:00→09:00 signal. Skipped.
- Cost tiers use median dollar volume; no liquidity audit beyond that.
