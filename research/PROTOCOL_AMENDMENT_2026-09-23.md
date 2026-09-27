# Research protocol amendment, 2026-09-23 (applies to registrations made after this file is registered)

Source: the null-world calibration in `reports/null_lab/REPORT.md`, the future lab in
`reports/future_lab/REPORT.md` and the PEAD attack in `reports/pead_attack/REPORT.md`. Past verdicts are
unchanged. This amends `research_protocol_2026-09-18.md`. It is registered so that it cannot be relaxed
quietly later.

## A. Gates

1. **Development gate.** Net base excess Sharpe ≥ **1.8/√T** for a single candidate, where T is the
   dev window in years. For each member of a family of k ≥ 4 candidates registered together it is
   ≥ **2.4/√T**. Stress mean > 0 as before.
   - The old 0.5 gate false-passed 10–19% of zero-mean nulls over 5.7 years.
2. **Long-biased books.** Gate on **active return against an exposure-matched benchmark or
   registered control**, never on absolute Sharpe.
   - Absolute Sharpe passed 87–89% of null long-only timing signals.
3. **Validation gate.** Unchanged: Sharpe ≥ 0.75, stress mean > 0, bootstrap p < 0.05/k.
4. **Null calibration is required.**
   - Every new registration states which null-lab engine or null it will be compared with.
   - Every result reports P(pass | null) ± its Monte-Carlo SE, from `research.null_lab.api.run_null`
     or an engine added to it with an exactness test.
5. **Shift nulls.** The minimum offset is at least lookback + holding + margin, and never under
   12 months.

## B. Controls that must be beaten

6. **Selection claims.** Any strategy that selects from an event set or candidate stream must beat
   a **random-selection placebo under its own portfolio rules**: same events, dates, capacity,
   sizing, costs and marking. Beating SPY or zero is not a selection claim.
   - PEAD's 0.70 was indistinguishable from random selection at 0.46 (p = 0.113).
7. **Concentration check.** Report the result with the best contiguous 12 and 24 months removed, and
   the stationary-bootstrap p for that concentration (`research/future_lab/ordering.py`).

## C. Re-measurement on corrected data

8. **A failed development result stays failed** unless it is re-measured with corrected data under a
   registration made **before** that re-run.
   - The spec must be unchanged; only the data changes, for example from a survivor-only to a
     delisted-inclusive universe.
   - A locked validation window opens only if the corrected development run passes the gate in
     force when the original plan was registered.
   - A corrected re-run is an audit, not a new trial.
   - **Example:** fundamentals F1–F3 failed dev on survivor-only data. A Sharadar-based re-run of
     their dev window is allowed. Their 2015+ validation is not, unless that corrected dev passes.

## D. Forward evidence

9. A forward observation counts only if all of these hold:
   - it is recorded in `reports/forward/registry.jsonl` before its intended execution;
   - the chain verifies;
   - the head is anchored externally before execution.
   Backfilled or replayed decisions never count.
10. Forward monitoring uses the registered rule `reports/future_lab/monitoring_rule_spec.json`, or a
    successor registered before that candidate's forward start. Its parameters are never re-estimated
    on forward data.
