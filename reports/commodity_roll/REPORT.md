# Commodity roll premium via same-commodity ETF pairs (A1): dev PASS → audit WEAKENED → validation FAIL

2026-09-23.
- **Plan:** `research/commodity_roll/PLAN.md`, registered 23:16:05 PDT (sha256 `d0783632…`).
- **Unlock:** `research/commodity_roll/VALIDATION_UNLOCK.md`, registered 23:38:11 PDT (sha256 `12b5dc3a…`).
- **Code:** `research/commodity_roll/{core,evaluate,validation_checks}.py` and `research/struct_common.py`; all hashes
  are in the ledger.
- **Tests:** `tests/test_commodity_roll.py` (4) and `tests/test_commodity_roll_validation_checks.py` (4); all pass.
- **Numbers:** `dev_results.json`, `validation_results.json`, `{dev,validation}_validation_checks.json`,
  `{dev,validation}_daily.csv`.
- **Audit:** [`reports/audit_commodity_roll/REPORT.md`](../audit_commodity_roll/REPORT.md).

**Final status: SPENT.** Validation failed by the rule fixed before it was opened. No re-specification: no other
pairs, hedges, sub-selections (e.g. natgas only), windows or costs.

## Rule

- **Pairs** (long deferred/optimized, short front month): crude USL/USO, natgas UNL/UNG, broad DBC/GSG.
- Each pair is dollar-neutral, reset to +1/−1 at each month's first-session close, drifting in between.
- The book is the equal-weight average of the live pairs.
- **Costs:** base 10 bp per side plus 1% borrow; stress 30 bp plus 4%.

## Development (2006-07-21 → 2016-12-30): PASS

| | Sharpe | Ann. | Gate |
|---|---:|---:|---|
| Base | **0.596** | 6.35% | ≥ 0.557 ✓ |
| Stress | 0.29 | 3.06% | > 0 ✓ |

- Bootstrap p: 0.0064 (< 0.025 ✓).
- P(pass | null): 0.006.
- Per-pair Sharpe: crude 0.47, natgas 0.26, broad 0.49.

## Independent audit (development only): WEAKENED

- **Reproduction:** exact; no data bug.
- **The director's front-basket hedge was biased.** The front funds' own returns contain the roll bleed (USO −14%/yr,
  UNG −24%/yr, GSG −8%/yr, with spot drift about 0). Against roll-free FRED spot proxies the alpha is +7.2%/yr,
  NW t 3.09.
- **Fragilities:**
  - tradable vol-matched "pure roll" t 1.6–1.8;
  - top 5% of months 50% of P&L;
  - borrow above 1.4%/yr breaks the gate;
  - most favourable block length.
- **Literature:** the Mou (2011) index-roll front-running is largely arbitraged after 2011.
- **Recommendation:** unlock only with stricter binding criteria V1–V6. They were adopted verbatim, plus V6 for the
  2020 episode the director already knew about.

## Validation (2017-01-03 → 2026-09-17): FAIL

| Criterion | Value | Threshold | Result |
|---|---:|---|---|
| Base Sharpe (registered) | **0.21** (2.5%/yr, max DD −26%) | ≥ 0.75 | ✗ |
| Stress mean (registered) | −0.83%/yr | > 0 | ✗ |
| Bootstrap p (registered) | 0.24 | < 0.025 | ✗ |
| V1 spot-hedged alpha | 6.6%/yr, t 1.87 | t ≥ 2.0 | ✗ |
| V2 vol-matched mean | +2.6%/yr (Sharpe 0.37) | > 0 | ✓ |
| V3 no-rebate mean | +0.007%/yr | > 0 | ✓ (barely) |
| V4 top-5% share / pairs positive | 224% / 3 of 3 | < 50% / ≥ 2 | ✗ |
| V5 p at 21 / 63-day blocks | 0.24 / 0.23 | < 0.025 | ✗ |
| V6 alpha ex Mar–Jun 2020 | 3.0%/yr, t 1.78 | t ≥ 1.65 | ✓ |

**Where the validation P&L came from:**
- **2020 is the whole result.** The book made +34.1% in 2020, in the oil and gas super-contango (Mar +15.0%,
  Apr +13.7%). Without 2020 the book's Sharpe is **−0.10** (−1.1%/yr).
- **2026 to date: −19.5%.** The crude pair lost 39.7%, with Jan −8.3% and Mar −12.7% book months, as a backwardated
  front leg rallied against the short.

**Per pair:**

| Pair | Sharpe | Spot-hedged alpha |
|---|---:|---|
| Crude | −0.09 | 2.5%/yr, t 0.49 |
| Natgas | 0.37 | 15.3%/yr, t 3.20 |
| Broad | −0.24 | 2.2%/yr, t 1.18 |

- **Beta:** −0.32 to the front basket and −0.17 to spot, the same Samuelson-effect short as in development.
- **Descriptive split** (USO moved to multi-month holdings in 2020):
  - pre-May-2020: spot alpha 10.9%/yr, t 1.46, over 39 months;
  - post: 4.0%/yr, t 1.82; tradable mean −2.4%/yr.

## Interpretation

- **As a tradable ETF book, the roll premium failed out of sample.** Apart from one super-contango episode it
  earned nothing, and its structural short-commodity exposure lost heavily when curves flipped to backwardation
  (2026).
- **The spot-hedged alpha stayed positive** (6.6%/yr, t 1.87), mostly in natural gas. That fits a real but
  non-tradable roll/storage return, which the ETF pair cannot harvest without holding the short-spot beta and
  paying for it.
- **Natgas-only observation.** Its strong validation alpha is a post-hoc sub-selection and is **not** a candidate.
  Acting on it would be re-specification after seeing the window.
- **Process worked as intended.** The audit's stricter criteria were frozen before unlocking. The dev pass, the
  plausible mechanism and a clean audit still did not survive a genuinely locked window. The project's record is
  now 0 of 11 dev passes validated: the null lab's 0 of 9, then tsy_month_end, then commodity_roll.
