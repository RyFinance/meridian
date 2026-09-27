# commodity_roll: validation unlock, with stricter binding criteria

Status: DRAFT until its hash is in `research/preregistrations.jsonl`. Written 2026-09-23. No return of the six ETFs
after 2016-12-30 has been computed or viewed by this session or by any agent (the auditor and the C2 certifier
truncated every series at 2016-12-30 and asserted it).

## Why unlock

- **Development passed by the registered rule** (`reports/commodity_roll/dev_results.json`):
  - base Sharpe 0.596 vs gate 0.557;
  - stress mean +3.1%/yr;
  - block-bootstrap p 0.0064;
  - P(pass | null) 0.006.
- **An independent adversarial audit** (`reports/audit_commodity_roll/`, verdict WEAKENED) found:
  - no bug or leak; exact reproduction;
  - the front-basket hedge (alpha t 1.04) is a biased test, because the front funds' own returns contain the roll
    bleed being measured;
  - against roll-free spot proxies (FRED WTI and Henry Hub spot, plus a broad composite), dev alpha is +7.2%/yr,
    NW t 3.09;
  - same-beta short spot fails the gate (Sharpe −0.20).
- **Fragilities, which the criteria below target:**
  - the tradable vol-matched version is t 1.6–1.8;
  - the top 5% of months make 50% of P&L;
  - borrow above about 1.4% breaks the Sharpe gate;
  - the 21-day block is the most favourable block length.
- The registered rule permits validation, since dev was selected. The protocol amendment allows adding stricter
  criteria before a locked window is opened. Nothing registered is loosened.

## Validation window and registered gate (unchanged)

- **Window:** 2017-01-03 → 2026-09-17.
- **Run:** `PYTHONPATH=. .venv/bin/python -m research.commodity_roll.evaluate validation`, once.
- **Registered gate (PLAN.md):** net base Sharpe ≥ 0.75, stress mean > 0, and block-bootstrap p < 0.025 (as
  computed by `evaluate.py`).

## Additional binding criteria (all must also pass)

Code: `research/commodity_roll/validation_checks.py`, run once with the argument `validation`. On dev it reproduces
the audit exactly (`reports/commodity_roll/dev_validation_checks.json`).

| # | Criterion | Dev value |
|---|---|---|
| V1 | Monthly base book regressed on the matched roll-free spot composite (WTI / Henry Hub / average of DBC- and GSCI-weighted broad proxy), NW(4): **alpha > 0 and t ≥ 2.0** | 7.2%/yr, t 3.09 |
| V2 | Rolling-252-day vol-matched pairs (base costs, excess of cash): **mean > 0** | Sharpe 0.38 |
| V3 | No short rebate (lose the T-bill yield on the short notional), on top of the 1% borrow: **mean > 0** | Sharpe 0.52 |
| V4 | Top 5% of months **< 50%** of P&L, **and ≥ 2 of 3** pairs with positive spot-hedged alpha | 49.8%; 3/3 |
| V5 | Block-bootstrap **p < 0.025 at both 21- and 63-day blocks** | 0.0064 / 0.0176 |
| V6 | V1 excluding the periods opened by the first sessions of March–June 2020: **alpha > 0 and t ≥ 1.65** | (no 2020 in dev) |

**Pre-specified data handling:**
- A non-positive FRED spot print (WTI on 2020-04-20) is replaced by the last positive price before returns are
  computed.
- FRED series are the files in `reports/commodity_roll/raw/`, fetched 2026-09-23. Only their coverage dates were
  printed.

**Disclosure of prior knowledge (why V6 exists).** From general market knowledge, the director knows:
- the 2020 oil super-contango and negative WTI;
- backwardated curves in 2021–22;
- that USO moved to multi-month holdings in April–May 2020.

The first would favour this book; the second would hurt it. V6 stops a single known 2020 episode from carrying the
result. Pre- and post-May-2020 results are reported descriptively only.

## Decision rule (fixed now)

- **All of the registered gate and V1–V6 pass:** `commodity_roll` becomes the project's first validated candidate.
  - Next: C2 promotion guards (`research/certify/guards.py`), a forward registry spec, and a user decision.
  - No capital without that user decision.
- **Anything fails:** recorded as a validation FAIL; the family is SPENT. No re-specification, i.e. no other pairs,
  hedges, windows or costs.
- **Power disclosure:**
  - the registered Sharpe gate (0.75) is above the dev Sharpe (0.60);
  - the auditor estimates V1 passes about 60% of the time if the 2010–16 alpha (4.1%/yr) persists, and about 20% at
    an academic 2%/yr premium.
  - A fail therefore does not show the premium is absent; it only means it is not certified.
