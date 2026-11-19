# Round 6 "ag": CBOT grain overnight move -> US ag/food equities, 09:30 entry

**Verdict: NONE.** Gross directional effects are small and unstable; net of the brief's costs nothing survives check.

## Setup (as run: `analysis.py`, data frozen by `fetch.py` into `data/`)
- Signal: m = log(grain close of bar labeled 08:00 ET / close of bar labeled 14:00 ET on the prior equity session).
  Bars are start-labeled. 08:00 bar ends 09:00 and only holds trades before the 08:45 halt. Grains have no 15:00 bar (day session ends 14:20 ET), so 14:00 is the last bar ending at or before 16:00. 580 valid days, no zero moves.
- Signal variants: COMB (mean of ZC, ZS, ZW log moves), ZC, ZS, ZW.
- Entry: MOO (daily open) or 60m 09:30 bar open. Exit: 10:30 bar close, 11:30 bar close, or daily close. Net = gross - 2 x side cost (round trip).
- Groups: LONG_STK (ADM BG ANDE CTVA FMC MOS CF NTR DE AGCO CNH, sign +1), LONG_ETF (MOO CORN SOYB WEAT, sign +1), PROC (GIS CAG TSN PPC HRL, sign -1). Position = sign x sign(m).
- Missing data: LNDC and K return no yfinance data, so they are excluded (20 names used).
- Costs: ADV < $5M = 10 bp/side (MOO, CORN, SOYB, WEAT); $5-200M = 5 bp (ANDE, ETFs $5-20M and mid caps); >= $200M = 2 bp (DE, GIS).
- Dev = 2024-05-28..2025-06-30. Check = 2025-07-01..2026-10-16. Basket = equal-weight mean of names trading that day. t is on daily basket returns.

## Dev-selected rule per group (best basket t, net), checked out of sample
| Group | Dev rule (signal / entry / exit) | Dev net bp (n days, t) | Check net bp (n days, t) | Check gross bp (t) | Flip check net bp (t) |
|---|---|---|---|---|---|
| LONG_STK | ZS / 09:30 bar / close | +15.0 (262, 1.93) | -9.1 (308, -1.26) | +0.4 (0.06) | -9.9 (-1.38) |
| LONG_ETF | ZS / 09:30 bar / close | -10.9 (262, -2.72) | -18.0 (308, -5.14) | +2.1 (0.59) | -22.1 (-6.31) |
| PROC | COMB / 09:30 bar / close | -2.9 (265, -0.44) | -0.5 (315, -0.07) | +8.4 (1.30) | -17.2 (-2.67) |

Dev gross for LONG_STK under the same rule was +24.4 bp (t 3.15). It dropped to +0.4 bp (t 0.06) out of sample.
Exit variants for LONG_STK, check net: 10:30 -9.3 (t -1.89), 11:30 -5.6 (t -0.95), close -9.1 (t -1.26).

## Controls
- **Flip** (opposite sign): LONG_STK dev net -33.9 (t -4.37), check net -9.9. Both signs are net negative in check, so the gap is cost (about 10 bp round trip) on top of a near-zero gross move, not a clean reversal.
- **SPY placebo** (same grain signal, sign +1, MOO entry): net -4.4 dev / -4.0 check at 10:30 and -2.2 / -2.5 at 11:30 (4 bp round-trip cost), so gross is about 0 to 2 bp. Close exits are mixed (+6.9 dev, -2.3 check). Nothing in the SPY table is significant.
- **Gap vs drift**: correlation of COMB with the 09:30 gap is 0.2-0.26 for NTR, CF, MOS (the open already prices most of it). Correlation with the 09:30->10:30 move is 0.03-0.14 and unstable across splits (CNH: dev +0.09, check -0.16).

## Variant counting (multiplicity)
- Group-level: 3 groups x 4 signals x 2 entries x 3 exits = 72 rules, each on dev and check.
- Per-name: 20 names x 24 rules = 480 rules. 12 had dev t > 2 (one-sided null expects about 11). Check |t| > 2 rules: 138 of 480, and every one is negative (cost-driven). No name has a positive check t above 2.
- SPY placebo: 24 rules.
- Total distinct tests: 576 plus placebo.

## Top per-name dev picks, check numbers (net)
| Name | Dev rule | Dev bp (t) | Check bp (t) |
|---|---|---|---|
| DE (2 bp) | ZS / 09:30 / close | +24.5 (2.61) | -17.9 (-1.99) |
| CTVA | ZS / 09:30 / close | +20.8 (2.53) | +0.1 (0.01) |
| CNH | ZS / MOO / 11:30 | +17.6 (2.05) | -31.5 (-2.90) |
| ADM | ZS / 09:30 / close | +18.0 (1.87) | +2.3 (0.23) |
| CF | ZC / 09:30 / close | +17.9 (1.63) | +8.8 (0.73) |

## Verdict and reasoning
- NONE. The three long-exposure groups show a positive gross effect only in dev, and in check the gross edge is about 0 to 2 bp. Net of costs, the check numbers are negative for both long groups.
- PROC shows a gross effect in the expected direction in both splits (about +6 to +8 bp gross, t about 1.3, not significant), but net is negative at 5-10 bp per side. It would need costs near 2 bp per side to be tradable.
- Caveats: LNDC and K are missing from yfinance. Tests are on 2 years of 60m data only. Costs are by brief tier, not measured spreads.
