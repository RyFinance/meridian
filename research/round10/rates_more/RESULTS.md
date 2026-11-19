# rates_more: do sister equities respond to the ZB-overnight signal? (round10, 2026-10-19)

**Verdict: NONE for EDGE.** No group clears the bar. Best candidate: RV/boat/HVAC basket, WEAK. No single name survives correction in the positive direction.

## Best rule (core, pre-registered, no selection)
- Signal: d = sign(ln(ZB 60m close, 08:00 ET bar on D / close, 15:00 ET bar on prev equity day)). Bars are START-labeled, so the 08:00 bar closes at 09:00: no look-ahead.
- Each day with d≠0: long the names if d>0, short if d<0. Enter at the official daily Open. Exit at the 60m 09:30-bar close (10:30).
- Round-trip cost = 2 x per-side: ETFs 2 bp; names 5 bp/side; names with median USD ADV < $20m 10 bp/side.
- Best basket (equal weight, names trading that day): THO WGO LCII BC MBUU MCFT POOL LII CARR WSO.

## Checks
- ITB rule reproduced vs f3_trades_canonical.csv: 569 trades, max diff 1e-16.
- Labels: 60m first bar = 09:30 on 99.9% of days; last bar = 15:30 on 98.8%. ZB 08:00 close = 5m 08:55 close (median 0.000 bp, n=49). 60m 09:30 Open = daily Open (median 0.00 bp).
- Sample: 571 ZB trade days, 2024-05-29..2026-10-16. Dev/check cut 2025-09-19 (dev n=314, check n=257).
- Data gaps: PCH has no yfinance data (merged into RYN). FN.TO, DREAM.TO and HCG.TO return no data. FLG starts 2024-10-28 (NYCB renamed). So no Canadian builder could be tested; only the three TSX lenders had data.

## Group baskets (equal weight, tier costs, net bp)
| Group | Names | Dev n | Dev net | Dev t | Chk n | Chk net | Chk t | Chk win | Flip chk | Corr w/ ITB | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Auto | 8 | 314 | +1.8 | 0.3 | 257 | -3.1 | -0.5 | .51 | -16.9 | 0.51 | NONE |
| RV/boat/HVAC | 10 | 314 | +5.0 | 1.0 | 257 | +7.6 | 1.1 | .52 | -31.6 | 0.74 | WEAK |
| Mortgage svcs | 5 | 314 | +17.5 | 2.7 | 257 | +0.4 | 0.1 | .53 | -28.4 | 0.37 | WEAK (literal; effectively NONE) |
| Timber | 5 | 314 | +2.4 | 0.5 | 257 | +7.1 | 1.0 | .49 | -27.1 | 0.76 | WEAK |
| Housing banks | 4 | 314 | -8.2 | -1.3 | 257 | -4.1 | -0.7 | .51 | -20.9 | 0.46 | NONE |
| Canada (EQB, MKP, FC) | 3 | 307 | -16.0 | -4.9 | 252 | -8.2 | -2.4 | .41 | -31.8 | 0.25 | NONE |
| Placebo SPY | 1 | 314 | -3.0 | -1.3 | 255 | +0.3 | 0.2 | .51 | -8.3 | 0.21 | n/a |
| Reference ITB | 1 | 314 | +19.2 | 3.6 | 256 | +23.8 | 3.3 | .59 | -31.8 | 1.00 | n/a |

Verdict rule (fixed before running): EDGE = basket net > 0 in dev and check, check t >= 2.7 (Bonferroni 0.05/7 groups), and at least half the names positive in check. WEAK = basket net > 0 in both halves, not EDGE. Mortgage services meets WEAK only because check is +0.4 bp.

## Gross (before costs), check half
RV +19.6 (t 2.9); timber +17.1 (2.4); mortgage +14.4 (2.5); Canada +11.8 (3.4); banks +8.4 (1.4); auto +6.9 (1.1); SPY +4.3 (2.1); ITB +27.8 (3.8). Excess over SPY gross: RV +15, timber +13, mortgage +10, Canada +7, banks +4, auto +3, ITB +24.
Canada is gross-positive in both halves, but its thin names (ADV $0.4-6m) pay 20 bp round trip.

## Name level and multiplicity (35 names, check, two-sided)
- Net positive: 20/35 on check, 21/35 on dev. Gross same-direction positive: 34/35 on check.
- Raw p<0.05: POOL +17.3 bp (t 2.1), TFSL -13.5 (-2.5), PAG -16.8 (-2.4), FC.TO -10.4 (-3.4). Bonferroni (0.05/35) and BH q<0.05: only FC.TO, and in the negative direction. No positive name survives.
- Flip (opposite direction) is net negative on check for 35/35 names.
- Dev-selected best of 6 variants (direction x exit 10:30/11:30/16:00): check t >= 2 in 1 name (LPX +2.2) and <= -2 in 4. That is chance-level for 35 names. Dev chose the 16:00 exit for 17 names; that is a hypothesis for a new test, not a finding.
- Per-name corr with ITB P&L ranges from 0.13 (PRCH) to 0.74 (UFPI). Timber and RV names are mostly the same housing bet as ITB.

## Caveats
- Costs decide the outcome. Most names pay 5 bp/side, against 2 bp for the ITB ETF.
- Market-wide component: SPY gross check is +4.3 bp (t 2.1), so the gross effect is not fully housing-specific.
- PRCH dev +66 bp comes from three ~50% event days (Oct 2024, Feb 2025, May 2025); its check is 0.
- ADV uses yfinance volume. TSX volume may be undercounted, so Canadian cost tiers could be too low.
- The ZB series is read from the existing ITB cache (zb_itb/verify/yf_cache), not re-pulled.

## Files (research/round10/rates_more/)
analysis.py (full test), summary_extra.py (basket win/flip), dl.py (download), results_by_name.csv, results_baskets.csv, cache/.
