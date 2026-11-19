# Execution simulation rules (registered 2026-10-17, before the simulation is run)

Real IBIT and ETHA 1-minute after-hours prints (LSE vault, 2026-04-28..2026-09-16), NYSE weekdays.
- **Entry.** Reference = last print at or before 16:59 ET. Post a buy limit at ref − $0.01 at 17:00. It fills if any 1-minute bar from 17:00 to 17:04 has a low ≤ the limit. If unfilled by 17:05, buy at the 17:05 bar's high plus $0.01 (marketable).
- **Exit.** Reference = last print at or before 17:59. Post a sell limit at ref + $0.01 at 18:00. It fills if any bar from 18:00 to 18:04 has a high ≥ the limit. Otherwise sell at the 18:05 bar's low minus $0.01.
- Commission $0.0035/share per side (IBKR Pro). $10k per ETF.
- **Reported.** Net bp per trade, win rate, and total P&L for IBIT, ETHA and combined. Also a "market" variant: buy at the 17:00 bar high + $0.01 and sell at the 18:00 bar low − $0.01.
