# Frozen candidates (registered before any validation result)
Selected on MSTR dev 2020-08..2023-12 (288 rules; only put credit spreads were near positive; dev t ≤ 1.0, so evidence is weak):
- **P1** `Rule("pcs", 7, 0.03, 0.10, None, True)`: 7-DTE put spread, short 3% OTM, wing 10%, only when IV > RV20, hold to expiry. Dev: n 108, +4.3%/trade, t 1.00; stress +1.9%.
- **P2** `Rule("pcs", 14, 0.03, 0.10, 0.5, True)`: 14-DTE, same strikes, 50% take-profit, IV filter. Dev: stress +3.0%, t 0.63.
- **P3** `Rule("pcs", 7, 0.10, 0.10, None, False)`: 7-DTE, short 10% OTM, wing 10%, always on. Dev: n 130, win 91%, +1.4%/trade; stress +0.1%.

Validation runs once: MSTR 2024-01..2026-09-16, and IBIT 2024-11..2026-09-16. Pass rules are as in PROTOCOL.md.
