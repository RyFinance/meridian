# Wider-expiry (2–14 DTE) defined-risk premium selling on MSTR and IBIT: FAILED (2026-10-17)

**Dev (MSTR 2020-08..2023-12, 288 rules).**
- Only put credit spreads were near positive: best t 1.0, and stress costs about +0–3%/trade.
- Call spreads (−8.5%) and iron condors (−7.8%) lost.
- The small put-spread gains reflect MSTR's 2020–23 uptrend, not a premium edge.

**Validation, run once on 3 frozen put-spread rules (CANDIDATES.md).**

| rule | MSTR 2024–26 base / stress | IBIT 2024–26 base / stress |
|---|---|---|
| P1: 7d, 3% OTM, IV filter | −2.0% / −4.1% per trade | −2.0% / −2.9% (max drawdown −98%) |
| P2: 14d, 50% take-profit, IV filter | +11.3% (t 0.81) / −6.9% | −3.4% / −4.0% |
| P3: 7d, 10% OTM, always on | −1.5% / −2.4% | −1.3% / +4.2% (stress n = 9 only) |

All three fail. Win rates are 72–92%, but full-width losses (−75% to −100% of risk) erase the gains, the same pattern as 0DTE.
