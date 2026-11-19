# Wider-expiry premium selling on MSTR and IBIT (registered 2026-10-17, before any result)

**Motivation.** Literature: option sellers earn a volatility risk premium, which is larger for bitcoin (Deribit studies), and the CBOE PUT index shows the same for monthly index puts. Our naked 0DTE MSTR selling failed on tail risk. This tests defined-risk, longer-dated versions.

**Family** (all entries at the daily close print, using option daily OHLCV from the LSE vault OPRA prints):
- Structures: put credit spread (bullish), call credit spread, iron condor, and cash-secured put (CSP).
- Short strike X% out of the money; long wing W% further out.
- DTE target D ∈ {7, 14, 30, 45}: the expiry closest to D calendar days, with ≥ 4 days left.
- X ∈ {5, 10, 15%}, W ∈ {5, 10%} (CSP has no wing).
- Exit: hold to expiry (settle on the official close), or take profit at 50% of credit on the first later daily close print where the spread can be bought back for ≤ 50%.
- Filter variants: none; or enter only when the short option's Black-Scholes IV exceeds 20-day realized vol ("rich premium").
- Cadence: one position at a time; open the next on the first close after the prior one ends.

**Fills.** Each leg at its close print ∓ half-spread max($0.05, 5% of price); commission $0.65/contract/leg each side; expiry settlement is free. Stress case: half-spread max($0.10, 10%).

**Return.** P&L ÷ capital at risk: width − credit for spreads, or strike − credit for CSP (cash-secured). Cash earns 0 (conservative).

**Windows.**
- MSTR development: 2020-08..2023-12 (unlimited variants).
- MSTR validation: 2024-01..2026-09-16.
- IBIT validation: 2024-11..2026-09-16 (never examined).
- Validation runs once, on at most 3 frozen rules written to `CANDIDATES.md` and registered first.

**Pass** (per rule; both MSTR-val and IBIT must hold):
- mean return per trade > 0 under base and stress costs;
- MSTR-val one-sided t ≥ 2.13 (Bonferroni 3);
- worst single trade ≥ −100% of capital at risk (by construction);
- max drawdown < 40% of capital at 1× sizing.
