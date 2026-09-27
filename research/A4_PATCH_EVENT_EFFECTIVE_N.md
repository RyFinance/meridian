# Proposed Amendment 4 patch: effective observations for sparse event designs

**PROPOSED — not owner-registered and not an edit to Amendment 4.** This patch narrows A4 §4's effective-observations rule. It does not retroactively alter a verdict, the frozen wave-1 strategy, or A4's calibrated-p statistic.

## Rule

For a strategy whose exposure is concentrated on a finite set of discrete events, report both calendar-time observations and **event-effective observations**. Calendar-time `n/D` is not the number of independent economic bets. Before returns, declare (i) the event definition, (ii) non-overlapping dependence clusters such as announcement cycles, months or years, and (iii) any overlap multiplicity of payoff horizons. The event-effective count is

`N_event_eff = min(N_daily_eff, M, M / D_event)`, where `M` is the number of eligible development events and `D_event = max(1, D_event-HAC, D_cluster × overlap_multiplicity)`.

`D_event-HAC` is the Bartlett long-run-variance ratio of the ordered event P&L series, floored at one. `D_cluster` is the finite-cluster-corrected variance of sums of demeaned event P&L within the preregistered clusters, divided by `M` times event variance, also floored at one. An event does not become an extra independent observation because multiple non-event days lie between events. Cluster count and event count are disclosed separately. Fewer than three clusters is insufficient for an event-effective-N estimate and must be labelled power-infeasible. The implementation is [event_effective_n.py](amendment4/event_effective_n.py).

The cap is for sample-size, power and breadth claims. **It is not legitimate to alter A4's calendar-time calibrated p by mechanically plugging this N into a t-statistic.** A4's p-value does not use the previously reported effective-N figure. A separate cluster-aware p-value gate would require its own preregistered calibration under sparse, skewed, dependent event designs. Until that exists, report the A4 calendar-time p unchanged and do not claim event-level statistical certification from an inflated N.

## Synthetic operating characteristic

The [reproducible 40,000-path simulation](amendment4/sim_event_effective_n.py) uses zero-mean Gaussian events, 19 independent annual clusters of eight events, within-cluster correlation 0.35, and a one-sided nominal 5% normal event-mean test. Its deliberately erroneous comparator treats a calendar-time effective-N of 2,964.8634 as the event count. The actual A4 p algorithm is **not** that comparator. The simulation isolates why the count must not be used for an event-level power or test claim.

| Event-mean test's N | Null false passes / 40,000 | Rate |
|---|---:|---:|
| Uncapped daily N misread as events | 16,805 | 42.01% |
| Cap at 152 event dates only | 7,596 | 18.99% |
| Proposed estimated cluster/HAC cap | 2,252 | 5.63% |
| Oracle cluster cap (true design effect 3.45) | 2,045 | 5.11% |

The estimated cap is slightly liberal in this chosen Gaussian clustered null; it is a **power-reporting guard**, not a validated replacement significance test. Other cluster sizes, heavy tails and time-varying event premiums need calibration before any p-value change. The simulation artifact is `reports/sol_beyond_menu/event_n_simulation.json`; three unit tests in `tests/test_event_effective_n.py` check the event cap, overlap monotonicity, clustered reduction and invalid groups.

## Wave-1 FOMC re-report under this proposal

Using only the saved development series, the [new re-report artifact](../reports/sol_beyond_menu/fomc_event_n_rereport.json) finds 153 scheduled meetings in 19 year-clusters, event HAC `D=1.1935`, cluster `D=1.0136`, and **event-effective N=128.2**, rather than the earlier daily-series 2,964.9. This does not recalculate strategy returns or access 2013–2019 holdout returns. The A4 calibrated `p=0.0625` is **unchanged**, since effective N is not an input to that algorithm. It remains above the fixed wave-1 `0.0125` threshold; **FAIL** remains the verdict. This is a re-analysis, not a fifth wave-1 trial.
