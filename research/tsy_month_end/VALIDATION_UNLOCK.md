# Validation unlock: Treasury month-end book M

M passed the registered development gate (`reports/tsy_month_end/dev_results.json`):
- active Sharpe 0.66 against a gate of 0.52;
- stress active +2.2%/yr;
- shift-null p 0.006.

Adversarial development checks (descriptive; nothing re-specified):
- **Year exclusions:** 0.49–0.71.
- **Quarter-end vs other months:** 44.6 vs 34.9 bp per window.
- **SPY in the same window:** +21.7 bp, correlation −0.23.
- **Alpha after SPY beta:** 42 bp per window.
- **Mid-month window:** correlation with the month-end active return −0.16.
- **Dividends:** 7 ex-dates in 143 fall on earning days.
- **Deflated-Sharpe probability at 120 trials:** 0.014, too low on development alone.

Validation runs **once**, on 2015-01-02 → 2026-08-31, with the code frozen at the registered hashes
of `research/tsy_month_end/core.py` and `evaluate.py`.

M passes validation if all of these hold:
- active Sharpe ≥ 0.75;
- stress active mean > 0;
- shift-null p < 0.05;
- block-bootstrap p < 0.05.

A pass means a forward registry test only, never capital. A fail is final for this specification.
