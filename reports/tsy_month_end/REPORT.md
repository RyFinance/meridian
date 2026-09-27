# Treasury month-end index-extension flow: development PASS, validation near-miss (FAIL on the registered Sharpe gate)

- **Plan:** `research/tsy_month_end/PLAN.md`, registered with code hashes before any return.
- **Validation unlock:** `VALIDATION_UNLOCK.md`, registered after development with the code hashes
  re-verified.
- **Tests:** `tests/test_tsy_month_end.py` (3 pass).

**Book M:** long TLT over the last 3 sessions of each month, T-bills otherwise. It is measured
against C_EXP, a constant TLT weight equal to M's average (about 14%).

| | Development 2003–2014 | Validation 2015–2026-08 |
|---|---:|---:|
| Gross window return, bp per month | +38.1 | +28.5 |
| Active Sharpe, gross | 0.76 | 0.79 |
| **Active Sharpe, base (2 bp)** | **0.66** | **0.69** |
| Active return, base | +3.1%/yr | +3.2%/yr |
| Active Sharpe, stress (6 bp) | 0.46 (+2.2%/yr) | 0.49 (+2.3%/yr) |
| Block-bootstrap p | 0.008 | 0.004 |
| **Circular-shift null p (1,000)** | **0.006** | **0.005** |
| Null 95th / 99th percentile | 0.41 / 0.56 | 0.42 / 0.55 |
| P(pass gate \| null) | 2.0% | 1.7% |
| Years with positive active | 11 / 12 | 10 / 12 |
| IEF, same rule (descriptive) | 0.50 | 0.95 |
| **Gate** | ≥ 0.52: **PASS** | ≥ 0.75: **FAIL** (0.69) |

## Adversarial checks (development)

- **Year exclusions:** dropping 2010 gives 0.54; 2008–09, 0.71; 2010 and 2012, 0.49.
- **Quarter-end months:** 44.6 bp per window, against 34.9 bp for other months. This fits the larger
  quarter-end index extension.
- **Not risk-off:** SPY also rises in the same window (+21.7 bp; the equity turn-of-month); the
  correlation is −0.23. TLT keeps 42 bp per window after its SPY beta of −0.18.
- **Window-position placebos:**
  - in development, windows ending around mid-month (sessions 12–14) were also positive, with
    Sharpe 0.41–0.57;
  - in validation every non-month-end position was flat or negative (−0.95 to +0.04);
  - month-end is the only persistent window.
- **Dividends:** 7 of 143 TLT ex-dates fall on earning days; adjusted prices handle them.
- **Costs:** break-even is about 15 bp a side, against TLT's roughly 1 bp spread.

## Combined evidence and fragility

- **Two independent windows:** combined (Fisher) p = 0.00034. **Bonferroni over about 120
  project trials: 0.041.**
- The deflated-Sharpe probability on development alone was 0.014. Validation replicated the result.
- **Stationary bootstrap of 5-year paths** (fragility only): active Sharpe p5 / p50 / p95 =
  −0.01 / 0.68 / 1.36; P(5-year active < 0) = 5%.

## Verdict

- **By the registered rule: FAIL.** The validation active Sharpe was 0.69 against a 0.75 threshold.
  This specification cannot be promoted, and it will not be re-specified to clear the threshold.
- **Statistically, it is the strongest evidence the project has produced.** A pre-registered,
  mechanism-first flow effect sits outside its null in two independent 12-year windows, with the same
  size in both (+3.1% and +3.2%/yr active), and survives project-wide multiple-testing correction.
- **Economics:** a small, cheap-to-trade, equity-independent overlay. It is invested about 14% of
  the time and earns about 3%/yr active.

## Recommended status

**FORWARD OBSERVATION**, not a validated edge.
- Record the frozen rule prospectively in the forward registry (`reports/forward/`) before each
  month-end window.
- Anchor the head externally.
- Judge it with the registered monitoring rule.
- No capital.
