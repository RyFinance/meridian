# Commodity term-structure / roll premium via same-commodity ETF pairs: pre-registration

Status: DRAFT until its hash is in `research/preregistrations.jsonl`. Written 2026-09-23 before any
return of these pairs was computed.

## Novelty and mechanism

- The project has never traded commodity term structure. The COT studies used positioning; the
  multi-asset book used trend and cross-sectional momentum on price.
- Contract-level curves are unavailable (checked on yfinance and LSE; `data/scout_A/`).
- Instead, ETF pairs that hold the **same commodity at different curve points** isolate the
  roll/term-structure return:
  - front-month funds roll the nearest contract on a published schedule and pay the contango
    storage/roll cost;
  - 12-month-strip or optimum-yield funds hold deferred contracts, which carry lower roll cost
    and are less exposed to scheduled index-roll pressure.
- **Who pays:** front-month ETF and index investors, whose predictable, price-insensitive rolls
  are front-run (Mou 2011), and who pay storage-driven contango (Gorton–Rouwenhorst; Erb–Harvey).
- **Direction (fixed):** long the deferred/optimized fund and short the front-month fund, equal
  dollar. The reverse is never tested.

## Universe (fixed; same-commodity pairs plus one broad pair)

| Pair | Long (deferred / optimized) | Short (front month) | First common date |
|---|---|---|---|
| Crude | USL (12-month WTI strip) | USO | 2007-12-06 |
| Natural gas | UNL (12-month NG strip) | UNG | 2010-01-04 |
| Broad | DBC (optimum yield, diversified) | GSG (S&P GSCI front) | 2006-07-21 |

DBC and GSG differ in composition. That adds noise, not a directional bias, and is disclosed.

## Rules

- **Prices:** yfinance adjusted closes (split-adjusted; USO and UNG reverse splits handled by
  adjustment). Use each pair from its first common date.
- **Book:** each pair is +1 long / −1 short at the start of each calendar month, rebalanced at
  the first session's close; weights drift in between. The book is the equal-weight average of the
  available pairs.
  - The pair return is r_long − r_short. The dollar-neutral financing cancels; the short rebate is
    assumed to equal cash.
- **Costs:**
  - trading: base 10 bp, stress 30 bp per side on traded notional (both legs; monthly rebalance);
  - borrow on the short leg: base 1.0%, stress 4.0% per year.

## Control and null

- The spread is market-neutral by construction. The control is zero, and the report also includes:
  - the beta of the book to the front-month basket (equal-weight USO/UNG/GSG);
  - the beta to SPY excess;
  - year-by-year and per-pair contributions.
- **Null:** a mean-centred block bootstrap of daily book returns (21-day blocks, 5,000 draws,
  seed 20260923), giving a one-sided p. P(pass | null) is reported.

## Windows

- **Development:** 2006-07-21 → 2016-12-30.
- **Validation (locked):** 2017-01-03 → 2026-09-17. It needs `VALIDATION_UNLOCK.md` registered, and
  runs once if selected.

## Gates

- Workstream A registers two tests this session (A1 and A2), so the bootstrap threshold is
  0.05/2 = 0.025.
- **Development.** Net base Sharpe ≥ 1.8/√T (T ≈ 10.4 years, so about 0.56), stress mean > 0, and
  bootstrap p < 0.025.
- **Validation:** net Sharpe ≥ 0.75, stress mean > 0, p < 0.025.

## Limits

- Term structure is regime-dependent: contango dominated 2009–2016; backwardation came in 2018 and
  2021–22, which is in validation.
- USL and UNL are thin funds with wider spreads, covered by the stress costs.
- A front-month short pays borrow.
