# Round 9 COT: Treasury speculator positioning -> ITB weekly (2026-10-18)

**Verdict: NONE.** No COT rule has a stable sign across dev (2016) and check (2017 to 2026-09). The one dev-selected rule reverses in check.

## Data and setup
- COT: `data/lse/cot/cot.parquet`, legacy format (noncommercial = speculators). ZB and ZN present. **UB is not in the file.** ZT and ZF are present but were not tested.
- Speculator net = noncomm_long - noncomm_short. Level z and change z use the prior 52 reports (no look-ahead). Change z = Δnet standardized the same way.
- Trade: Monday open after the release Friday, Friday close (anchor = release_date, fallback date+3). Entry at ITB adjusted open, exit at adjusted close. Costs 4 bp round trip per traded week.
- Dev = entries ≤ 2016-12-31 (50 weeks, about 29 traded). Check = entries 2017-01-01 onward (507 weeks).
- Weekly, one trade per week, so t-stats use weekly nets with no overlap.
- **COT ends with the 2026-09-08 report.** Sep 21 to Oct 16 has no COT data, so the check window stops at 2026-09-18.

## Results (net bp per traded week, t on weekly nets)
`mom`/`cont` = long ITB when z ≥ k, short when z ≤ -k. `contra`/`rev` = mirror. The flip column is the mirror, so it equals the contra/rev row.

| Rule | dev n | dev bp | dev t | chk n | chk bp | chk t | SPY placebo chk bp (t) | bond-call hit chk |
|---|---|---|---|---|---|---|---|---|
| LVL ZB ≥1.0 mom | 29 | +60 | 1.26 | 269 | -50 | -2.06 | -24 (-1.89) | 0.54 |
| LVL ZB ≥1.0 contra | 29 | -68 | -1.43 | 269 | +42 | +1.73 | +16 (1.26) | 0.46 |
| CHG ZB ≥1.0 cont | 19 | +46 | 0.65 | 158 | -45 | -1.27 | -37 (-2.15) | 0.47 |
| CHG ZB ≥1.0 rev | 19 | -54 | -0.76 | 158 | +37 | +1.05 | +29 (1.69) | 0.53 |
| LVL ZB ≥1.5 mom | 25 | +58 | 1.07 | 156 | -53 | -1.69 | -14 (-0.82) | 0.54 |
| LVL ZB ≥1.5 contra | 25 | -66 | -1.21 | 156 | +45 | +1.44 | +6 (0.34) | 0.46 |
| CHG ZB ≥1.5 cont | 9 | -60 | -0.48 | 74 | -64 | -1.12 | -40 (-1.50) | 0.51 |
| CHG ZB ≥1.5 rev | 9 | +52 | 0.42 | 74 | +56 | 0.98 | +32 (1.20) | 0.49 |
| LVL ZN ≥1.0 mom | 33 | -50 | -1.01 | 249 | +11 | 0.44 | +12 (1.01) | 0.53 |
| LVL ZN ≥1.0 contra | 33 | +42 | 0.84 | 249 | -19 | -0.77 | -20 (-1.66) | 0.45 |
| CHG ZN ≥1.0 cont | 20 | -26 | -0.42 | 152 | -72 | -2.00 | -14 (-0.75) | 0.48 |
| CHG ZN ≥1.0 rev | 20 | +18 | 0.29 | 152 | +64 | +1.78 | +6 (0.31) | 0.50 |
| LVL ZN ≥1.5 mom | 19 | +23 | 0.35 | 150 | +7 | 0.22 | +2 (0.11) | 0.51 |
| LVL ZN ≥1.5 contra | 19 | -31 | -0.46 | 150 | -15 | -0.46 | -10 (-0.57) | 0.48 |
| CHG ZN ≥1.5 cont | 11 | -105 | -1.15 | 72 | -74 | -1.23 | -12 (-0.42) | 0.46 |
| CHG ZN ≥1.5 rev | 11 | +97 | 1.06 | 72 | +66 | 1.10 | +4 (0.14) | 0.50 |

- **Benchmark:** ITB Mon-open to Fri-close, all weeks, no costs. ZB-weeks dev +33 bp (t 0.91), check +31 bp (t 1.78). The long drift is large, so a rule that is short ITB for some weeks has a structural handicap.
- **Bond-call hit** = share of traded weeks where ZB or ZN moved in the direction the rule implied. It sits at 0.45 to 0.54, so positioning barely calls the bond direction.

## Controls and extra checks
- **Count:** 16 tested variants on check (8 signals × 2 signs), plus 8 roll-clean variants and 8 bucket-spread diagnostics. Max |check t| is 2.06 across 16 variants. Under a Bonferroni-style correction this is noise.
- **Sign flip:** ZB level ≥1.0 is +60 bp in dev and -50 bp in check. The sign reverses.
- **Bucket spread**, z ≥ 1 minus z ≤ -1 (ITB, check): ZB level -82 bp (Welch t -1.72); ZB change -80 bp (t -1.13); ZN level +38 bp (t 0.74); ZN change -134 bp (t -1.83). Dev has 5 to 24 weeks per bucket, too few to trust.
- **Per-year, ZB level ≥1 mom:** 5 of 11 years positive. 2020 is -285 bp per traded week, 2025 is -139 bp.
- **Roll-clean** (drop weeks with |ΔOI| > 5%, which removes quarterly roll artefacts): every change-rule check t is within ±1.5, and the dev sign flips again.
- **SPY placebo:** same rules on SPY. The ZB level mom rule shows t -1.89 on SPY, close to its ITB t. That points to a broad risk-timing effect, not a homebuilder-specific one.

## Caveats
- Dev is one year (2016). The 52-week z needs history starting 2015, so dev cannot be longer.
- Legacy COT, not disaggregated. No UB. Quarterly roll weeks inflate change signals (61 ZB and 57 ZN weeks flagged).
- ZB=F and ZN=F are continuous futures, so bond-call hit uses roll-affected returns. It is diagnostic only.
- The data gap from Sep 21 to Oct 16 is not covered by the local file, and I did not fetch CFTC directly.

Script: `cot_itb.py` (16 rules, dev/check, flip, placebo). `sens.py` (bucket spread, roll-clean, per-year). `fetch_zn.py` (ZN=F daily to this folder).
