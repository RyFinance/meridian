# Premium-momentum validation audit — negative result

## Scope and anti-data-mining boundary

This audit tests exactly the two candidates frozen in
`../premium/CANDIDATES.md`; it does not search any further parameter variants:

| Candidate | Lookback | Entry z | Maximum holding sessions |
| --- | ---: | ---: | ---: |
| M1 | 40 | 1.0 | 5 |
| M2 | 40 | 1.5 | 10 |

The original development interval was 2020-08 through 2022-12.  This audit uses
the sealed validation entries from 2023-01-01 through 2026-08-10.  The frozen
implementation creates the signal at the daily 16:00 close, enters both legs at
the next regular-session open, and takes the *momentum* direction: a high
MSTR-vs-BTC residual means long MSTR / short beta BTC, and vice versa.

## Costs and data-quality treatment

The frozen code charges, per round trip, MSTR auction costs of 3 bp per side plus
$0.005 per share, BTC costs of 5 bp per side, 2% annual MSTR short borrow when
applicable, and 5% annual BTC financing/borrow.  The `stress=2` rows double these
cost and carry assumptions.  That is already favorable compared with a period in
which MSTR short availability may be constrained, so it is not a claim of full
real-world executability.

`panel.parquet` has two missing BTC 09:30 prices; one affects an M1 validation
trade (2023-03-16 to 2023-03-24).  It is removed from all statistics rather than
filled with a non-executable substitute.  The M2 result has no missing execution
rows.

## Independent reproduction results

| Rule / cost case | Valid trades | Mean net return / trade | Trade t-stat | Sum of net trade returns | Compounded sequential return | Maximum drawdown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| M1 / base | 88 | -29.6 bp | -0.35 | -26.0% | -41.9% | -64.0% |
| M1 / 2x | 88 | -66.7 bp | -0.78 | -58.7% | -58.2% | -69.2% |
| M2 / base | 41 | +91.4 bp | +0.52 | +37.5% | +14.3% | -48.9% |
| M2 / 2x | 41 | +39.9 bp | +0.23 | +16.4% | -7.4% | -51.4% |

Annual net trade-return sums for M2 were **-43.5% (2023), +47.1% (2024),
+16.8% (2025), and +17.1% (through 2026-08-10)** at base costs.  It therefore
fails both preregistered acceptance conditions: its one-sided t-statistic is far
below 1.96 and it has a full year below -20%.  It also fails the doubled-cost
compounding check.

## Conclusion

The premium-momentum family is **rejected** as a credible tradable edge under the
registered rules.  Do not tune the lookback, threshold, exit, or cost setting
using this validation set.  The audit can be reproduced with
`audit_premium_validation.py`.
