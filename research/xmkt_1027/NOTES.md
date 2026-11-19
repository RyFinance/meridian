# Cross-market scan, 2026-10-27 (Alpaca SIP 15-min bars, 2016-01 → 2026-10, 58 ETFs)

Splits: discovery 2016-20 · validation 2021-23 · holdout 2024-26. Costs 2 bp/side (liquid) or 6 bp/side.

Scan (scan.py): 9,224 rules in four families. 14 passed discovery t>2.5 and validation t>2.
- A, intraday momentum into the close (SPY/QQQ/IWM/TLT/own → 15:30-16:00): nothing; best min-t 1.6.
- B, overnight holds, conditional or unconditional: nothing; best min-t 1.3.
- D, own gap with a 10:00 entry: nothing; best min-t 1.45.
- C, pre-market lead from one ETF to another: FCX→COPX (t 5-7), DIA/FAS/XLE→LABU fade, EEM/EDC/YINN→COPX, TMF→NAIL.

Stress test (validate.py): every new C rule is an open-print artifact. With entry moved to 09:45 or 10:00 they are about 0
or negative, and they are negative in the 2024-26 holdout even at the open (thin COPX/LABU opening prints are stale).
Only TMF/TLT pre-market → NAIL survives all three periods (bond_legs.py: NAIL is the only target with min-t > 1.5).

Exit and leverage on the one edge (TLT pre-market → NAIL, regime switch, 6 bp/side, 2017-26):
| exit | lev | CAGR 17-26 | CAGR 24-26 | Sharpe | max DD |
| 10:30 | 1.0 | 93% | 262% | 1.88 | −46% |
| 13:00 | 1.0 | 100% | 340% | 1.67 | −43% |
| 10:30 | 1.5 | 154% | 530% | 1.88 | −62% |
| 10:30 | 2.0 | 220% | 934% | 1.88 | −74% |

Execution finding: NAIL's edge sits in the opening auction and the first hour. Entries at 09:45 lose most of it,
so live partial MOO fills topped up at ~09:33 capture little. Full auction fills matter more than anything else here.
