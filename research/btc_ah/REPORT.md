# Overnight-gap rule hunt, 2026-10-17: 23 haiku agents and lead verification

Brief: `BRIEF.md`. Sealed holdout: 2026-08-11..2026-10-16, run once per frozen rule (`FROZEN.md`). Every agent folder has a RESULTS.md.

## Bottom line
- **No BTC after-hours rule survives** realistic costs and tradable fills. About 6,000 variants were tested across MSTR (shares, options, pre-market and after-hours), miners, ETH names, Asian BTC stocks, BTC/ETH/SOL themselves, ML, straddles, macro and FOMC, the open auction, and pairs.
- **One non-BTC lead survives** (F3): the overnight 30-year Treasury futures move predicts homebuilders' first hour.
  - Dev and check: t 2.8 and 3.9. It replicates in 7 homebuilder names; placebos are about 0.
  - Sealed holdout: ITB +15.3 bp per trade, n 46, t 1.07, win 57%, positive in all 5 replication names. **Direction confirmed, significance not reached** (the bar was t > 1.65).

## Scorecard
| Area | Verdict | Key reason |
|---|---|---|
| MSTR pre-market and after-hours vs BTC | NONE | Only 61 days of extended-hours data; 15 bp/side costs eat everything |
| MSTR share management (stops, trails, targets) | NONE | Earlier +37 bp was a simulator bug: exits before entry |
| MSTR options (daily, straddles, earlier 0DTE work) | NONE | Negative in all cells after spreads |
| Miners residual-gap fade | NONE | +26 → +10 → −36 bp (2026); the open-print fill is not tradable |
| Boyaa 0434.HK BTC-residual dip buy | NOT TRADABLE | +65 bp at the open print, −25 bp entering at 10:30 HKT |
| BTC-linked tickers, ETH names, Asia, pairs | NONE/WEAK | Decay, trust-era artifacts (ETHE), small samples |
| BTC/ETH/SOL off-hours sessions, FOMC | NONE/WEAK | FOMC effect absent in 2017–22; SOL weekend weak |
| ML walk-forward (27 features) | NONE | Within shuffled-label noise |
| Open auction (BTC last 10 min → MSTR first minute) | NONE | A real lead (beta 0.35, t 3) but fills cost 80–115 bp |
| Oil, metals, country ETFs/ADRs | NONE | Opens price the overnight move ~1:1 |
| Index gaps (SPY gap-down fill) | WEAK | Check t 2.8, n 42, out of 288 variants |
| **ZB → homebuilders (F3)** | **WEAK+, forward-test** | See above |

## Recurring traps found
1. **Open-print fills.** Any rule whose signal uses the opening price cannot also fill at that price. Most gap fades die when the entry moves even one bar later.
2. **High win rate ≠ edge.** Small targets with wide stops win 70–100% of the time and lose money overall.
3. **Dev windows flatter results.** Most dev t > 3 results went to about 0 in the check window.

## F3 rule (frozen)
If ZB=F's 60m close at 09:00 ET is above its 16:00 ET close from the previous session, buy ITB at the 09:30 open and sell at 10:30. If it is below, short ITB (or skip, for long-only). Cost 2 bp per side.
- Code: `lead_verify/zb_itb.py`.
- Holdout: `_sealed/holdout_F3.py` → `_sealed/holdout_F3_result.txt`.
- Next step: a forward paper test. Longer history needs hourly Treasury futures before 2024-08, which neither yfinance nor the LSE vault has.
