# Round 8: does the ZB->ITB first-hour lag extend to retail-heavy rate-sensitive names?
Signal/trade as BRIEF.md: d=sign(ZB 08:00 bar close / prior 15:00 bar close), trade d x name from official 09:30 open to 10:30 (60m bar close). Costs per side: 5 bp (most), 10 bp (COMP, ETD, LZB). Dev 2024-05-28..2025-06-30 (260d), check 2025-07-01..2026-10-16 (310d). Code: run.py, data: cache/, per-name csv: per_name.csv.
Variants tried: 1 rule x 28 names x 5 groups (no parameter search). Bonferroni one-sided at 28 names needs t >= ~2.9.
Data gaps: RDFN, EXPI, SNBR, NOVA, LC have no yfinance data; RMAX has only 189 bars; OPAD dropped (unadjusted reverse split in the 1d Open gives garbage). 28 names tested.
ITB reference (net 2bp/side): dev +16.6 bp t 2.9; check +27.2 bp t 4.3, win 59%.

## Per name (net bp/trade, t, win; flip = opposite direction net, check; corr = P&L corr with ITB, all days)
| sym | dev bp | dev t | chk bp | chk t | chk win | flip chk | corr ITB |
|---|---|---|---|---|---|---|---|
| OPEN | +60.3 | 2.84 | +12.1 | 0.47 | .53 | -32 | .21 |
| Z | +16.5 | 1.92 | +17.9 | 1.63 | .52 | -38 | .30 |
| ZG | +18.3 | 2.12 | +15.4 | 1.41 | .55 | -35 | .32 |
| COMP | +12.0 | 0.87 | +20.3 | 1.73 | .54 | -60 | .33 |
| RH | +19.9 | 1.33 | +15.4 | 1.17 | .52 | -35 | .46 |
| W | +25.6 | 1.53 | +29.6 | 2.11 | .54 | -50 | .36 |
| WSM | +8.4 | 0.88 | +14.5 | 1.75 | .55 | -35 | .53 |
| ETD | +0.7 | 0.10 | +2.8 | 0.42 | .50 | -43 | .51 |
| LZB | -7.7 | -1.09 | -17.0 | -2.36 | .43 | -23 | .53 |
| TAN | +0.2 | 0.03 | -6.5 | -0.91 | .46 | -14 | .10 |
| ENPH | +15.2 | 1.17 | -6.0 | -0.38 | .48 | -14 | .15 |
| RUN | +24.9 | 1.23 | +9.3 | 0.52 | .53 | -29 | .12 |
| SEDG | +43.1 | 1.82 | -25.0 | -1.17 | .49 | +5 | .09 |
| ARRY | -4.1 | -0.20 | -5.0 | -0.30 | .47 | -15 | .15 |
| FSLR | +5.4 | 0.42 | +0.5 | 0.04 | .48 | -20 | .03 |
| SOFI | +0.3 | 0.02 | -5.2 | -0.40 | .49 | -15 | .14 |
| UPST | +3.4 | 0.17 | +20.0 | 1.42 | .50 | -40 | .20 |
| AFRM | +1.8 | 0.10 | +8.4 | 0.59 | .50 | -28 | .16 |
| ALLY | +0.6 | 0.07 | -6.2 | -0.95 | .50 | -14 | .34 |
| COF | -7.9 | -1.02 | -4.9 | -0.73 | .47 | -15 | .31 |
| SYF | -12.5 | -1.42 | -7.4 | -1.08 | .46 | -13 | .35 |
| OMF | +1.3 | 0.16 | -0.7 | -0.11 | .50 | -19 | .39 |
| IWO | -0.1 | -0.02 | -6.6 | -1.60 | .45 | -13 | .31 |
| CVNA | -4.4 | -0.28 | -0.1 | -0.01 | .48 | -20 | .18 |
Only OPEN passes dev t>2.5 and Z/ZG pass dev t>2; all three fail Bonferroni (dev t < 2.9) and none has check t > 2 except W (dev t 1.5, not selected on dev). Flip control is negative everywhere after costs (as expected for a null: it only shows costs bite; the flip is not informative for weak names).

## Baskets (equal weight, net)
| group | names | dev bp (t) | chk bp (t) | chk flip | corr ITB | 2-leg ITB+grp chk Sharpe (ITB alone 3.86) |
|---|---|---|---|---|---|---|
| housing_tech | OPEN Z ZG COMP | +26.8 (2.55) | +16.4 (1.46) | -41 | .35 | 2.69 |
| housing_cons | RH W WSM ETD LZB | +9.4 (1.14) | +9.1 (1.21) | -37 | .62 | 2.57 |
| solar | TAN ENPH RUN SEDG ARRY FSLR | +14.1 (1.11) | -5.5 (-0.47) | -15 | .14 | 1.45 |
| fintech | SOFI UPST AFRM ALLY COF SYF OMF | -1.9 (-0.20) | +0.3 (0.04) | -20 | .31 | 2.24 |
| smallgrowth | IWO CVNA | -2.3 (-0.24) | -3.4 (-0.45) | -17 | .24 | 1.99 |
Best group by dev = housing_tech. 2-leg 50/50 ITB + housing_tech on check: mean 21.8 bp, Sharpe 2.69 vs ITB alone 27.2 bp, Sharpe 3.86. No group improves on ITB alone (every blend has lower mean and lower Sharpe; the groups are correlated 0.14-0.62 with ITB but have too little edge to diversify).

## Verdicts
- housing_tech (OPEN/Z/ZG/COMP): WEAK. Same sign in dev and check for all four names (+12 to +60 dev, +12 to +20 check), basket check t 1.46. Z/ZG/COMP check t 1.4-1.7 individually. Consistent with the housing-demand channel, but not significant after 28-name multiple testing. Needs forward data.
- housing_cons (RH, W, WSM, ETD, LZB): WEAK. RH/W/WSM positive in both halves (W check t 2.1), ETD and LZB null/negative; basket check t 1.2. Highest ITB correlation (.62), so it is largely the same housing factor, not new alpha.
- solar: NONE. Dev positives (SEDG +43, RUN +25) reverse or fade in check; basket check negative. FSLR, the utility-scale contrast, is ~0 as expected, but TAN is also ~0.
- fintech/consumer lenders: NONE. All seven names about 0 (UPST check +20 is noise).
- small-cap growth (IWO, CVNA): NONE. Negative on check.
Overall: the lag is not a generic retail-rate effect. Only names with a housing-demand link (homebuilders, RKT, and weakly housing platforms/home furnishings) show it; the weak ones are not tradeable on their own evidence. Hypothesis "retail ownership" not supported by lenders, solar, growth.
Caveats: 1d Open from unadjusted yfinance (split issue: OPAD dropped, check no other splits - none visible in gross means). yfinance official open for thin names may be a poor fill proxy; COMP 20bp/side is generous.
