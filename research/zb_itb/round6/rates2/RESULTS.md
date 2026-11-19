# Round 6 rates2: ZB/ZN-overnight -> 09:30 open..10:30 in untested rate-linked areas
Rule (same as ITB): d = sign(ZB (or ZN) 60m close @08:00 ET / close @15:00 prev session); trade sign*d from the official 09:30 open (1d Open) to the 09:30 60m bar close.
Pre-specified sign: bond/long-duration +, beneficiaries -. Dev 2024-05-28..2025-06-30, check 2025-07-01..2026-10-16. n ~570 days (SHY etc. identical).
Cost per ROUND TRIP in table: 1bp/side (LQD,HYG,TLT,IEF) = 2bp; 2bp/side otherwise = 4bp; LNC,CRBG,MAIN,IPO 5bp/side = 10bp (ARKG/ARKK/HOOD/XBI 2bp/side).
Variants: 32 names x 2 signals (ZB, ZN) = 64 (+ flip, SPY placebo). Bonferroni 5% over 64 needs |t| ~ 3.2 (two-sided). ITB reference: +22.4bp net, t 5.2.
Full table: results.csv (all/dev/check bp & t, flip, gross, SPY placebo t, corr with ITB trade P&L).

## Area 1 bond ETFs (net bp ZB signal; all-sample t; gross = net + cost)
| ETF | dev bp (t) | chk bp (t) | all bp (t) | gross bp | flip bp |
|---|---|---|---|---|---|
| LQD | -2.8 (-2.7) | -1.8 (-2.4) | -2.3 (-3.6) | -0.3 | -1.7 |
| VCIT | -3.6 (-3.3) | -3.7 (-5.8) | -3.6 (-6.1) | +0.4 | -4.4 |
| IGIB | -4.3 (-5.2) | -3.5 (-5.8) | -3.9 (-7.7) | +0.1 | -4.1 |
| HYG | +0.9 (1.1) | 0.0 (0.0) | +0.4 (0.8) | +2.4 | -4.4 |
| JNK | -0.3 (-0.4) | -1.0 (-1.6) | -0.7 (-1.3) | +3.3 | -7.3 |
| EMB | +0.1 (0.1) | -0.3 (-0.3) | -0.1 (-0.2) | +3.9 | -7.9 |
| MUB | -1.5 (-1.6) | -2.4 (-4.0) | -2.0 (-3.6) | +2.0 | -6.0 |
| PFF | -2.0 (-1.1) | +1.9 (1.4) | +0.1 (0.1) | +4.1 | -8.1 |
| MBB | -3.7 (-3.0) | -3.2 (-4.4) | -3.5 (-5.0) | +0.6 | -4.6 |
| TLT/IEF/SHY (ctrl) | -4.5/-2.8/-4.1 | -1.6/-1.5/-3.9 | -2.9/-2.1/-4.0 | -0.9/-0.1/0.05 | |
ZN signal gives the same picture (HYG +0.2 net t 0.3, PFF +0.1, others negative = cost).
Gross moves are 0 to +4 bp with t < 1.5 for HYG/JNK/EMB/PFF; investment-grade and Treasury ETFs have ZERO gross edge (the
"negative t" is just cost on a flat strategy). No NAV-lag continuation. SPY placebo t +0.2 (ZB) / -0.3 (ZN).
**Verdict area 1: NONE.** HY/EM/pref gross +2-4bp is below cost, unstable sign across dev/check (PFF), and untradeable at any cost >=2bp/side.

## Area 2 rate beneficiaries (expected sign NEGATIVE: bonds up -> stock down; table shows trade in that direction)
| Stock | dev bp (t) | chk bp (t) | all bp (t) | flip bp | corr ITB |
|---|---|---|---|---|---|
| MET | +2.3 (0.4) | +0.8 (0.1) | +1.5 (0.4) | -9.5 | -0.26 |
| PRU | +1.2 (0.2) | -6.3 (-1.2) | -2.8 (-0.8) | -5.2 | -0.31 |
| LNC | -5.9 (-0.7) | -5.8 (-0.8) | -5.8 (-1.0) | -14.2 | -0.22 |
| CRBG | -7.0 (-1.0) | -11.4 (-1.5) | -9.4 (-1.8) | -10.6 | -0.21 |
| SCHW | -0.2 (0.0) | +3.3 (0.6) | +1.7 (0.4) | -9.7 | -0.04 |
| IBKR | +7.2 (0.8) | -2.0 (-0.3) | +2.2 (0.4) | -10.2 | +0.02 |
| HOOD | -14.3 (-0.9) | -8.0 (-0.6) | -10.9 (-1.0) | +2.9 | -0.03 |
Nothing |t| > 1.8 in any sample, ZN agrees. (Gross for MET/SCHW/IBKR +5-6bp but t~0.4; noise on 100+bp daily vol.)
Insurer correlation to ITB P&L is negative (-0.2/-0.3) only mechanically (sign flip); their own P&L is zero, so no diversification.
**Verdict area 2: NONE.**

## Area 3 long-duration equities (expected sign +)
| Name | dev bp (t) | chk bp (t) | all bp (t) | flip bp | corr ITB |
|---|---|---|---|---|---|
| XBI | +17.8 (3.2) | -2.4 (-0.4) | +6.8 (1.6) | -14.8 | 0.09 |
| ARKG | +37.5 (3.7) | +6.2 (0.6) | +20.5 (2.8) | -28.5 | 0.14 |
| ARKK | +8.1 (0.9) | +0.9 (0.1) | +4.2 (0.8) | -12.2 | 0.11 |
| IPO | -2.1 (-0.4) | -4.2 (-0.7) | -3.2 (-0.8) | -16.8 | 0.06 |
| ARCC / MAIN | -3.0 (-0.7) / -2.5 (-0.5) | -2.9 (-0.7) / -11.3 (-2.0) | -2.9 / -7.3 | | 0.27 / 0.20 |
| VPU,IDU,NEE,DUK,SO,AWK,AEP | all |dev t|<=1.7 (AEP-ZN -2.2, wrong sign), check |t|<=1.2 | all |t|<=1.7 (AEP-ZN -2.35) | | 0.04-0.15 |
ZN: XBI dev +12.5 (2.2) / chk -0.7; ARKG dev +28.0 (2.8) / chk +11.9 (1.1) (all +19.2, t 2.6). SPY placebo t +0.2/-0.3.
Only ARKG and XBI show dev edge. Dev-selected: ARKG dev t 3.7 is at the Bonferroni line (3.2 over 64), but in check it falls to +6bp (t 0.6;
ZN +12bp, t 1.1), same sign but ~1/6 the size and insignificant, and ARKG/XBI daily vol (noise) means a 570-day
sample can show t 2.8 from selection alone. XBI check is negative. Utilities and BDCs: nothing (BDCs/MAIN negative).
Both are high-vol (ARKG 1h stdev ~178bp), so even the full-sample +20bp net is ~0.15 sd per trade.
**Verdict area 3: WEAK (ARKG only; XBI NONE).** ARKG is a forward-test candidate at most: all-sample +20.5bp net (t 2.8, not Bonferroni-significant
over 64), corr to ITB 0.14 (diversifying if real). Needs a fresh out-of-sample period before any use.

## Controls / caveats
Flip control = exact negative of the gross minus cost (shown as flip_bp); for ARKG/XBI flip is -28/-15bp (symmetrical, as expected for a real sign).
SPY placebo t ~0 (|t|<0.3 for the + sign; -2.8/-2.3 with the - sign is cost on a flat SPY). ZN and ZB give consistent results (signs agree on 89% of days), so they are not independent confirmation.
No hold-out beyond the check window exists: 730d of 60m data only. Files: dl.py (yfinance cache in ./cache), run.py, results.csv.
