# Cycle 7 addendum 1 (before any cycle-7 return)

2026-09-27. Implementation of the FRAMEWORK §3 FX exclusions (settled because the frozen engine filters whole
instruments only):
- For every excluded currency-month, **all** of that currency's inputs for the month are blanked (NaN) in the sample
  snapshot:
  - every daily excess return in the month;
  - `fx_foreign_rate`, `fx_spot` and `fx_cpi_pit` (and any other signal input) for that month.
- The frozen engine's own missing-data and eligibility rules then apply unchanged.
- A currency excluded for its whole history is FAIL in `candidate_list.csv`.
- No other change. Runner definitions adopted as built:
  - best-year share = best calendar-year active sum ÷ sum of positive year sums;
  - p_i clipped to [1/(B+1), B/(B+1)] in the Stouffer pool;
  - pooled series = w-weighted average over the samples present each month;
  - the 2×-cost control is derived exactly from the net and 3× stress series (cost = (net − stress)/2).
