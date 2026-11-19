# MSTR BTC-purchase disclosure event study

## Decision

**Do not promote a BTC-purchase-announcement trade rule.**  The one-session
rule is negative both before and after the development cutoff.  The five-session
rule has a positive *nominal* 2023–2026 total, but its median trade is negative,
its bootstrap interval includes zero, it suffers a 78.7% maximum drawdown, it
weakens materially in 2025–2026, and it underperforms ordinary MSTR held over
weekday-matched five-session windows.  It is not a robust, event-specific edge.

The five-session result may be retained only as an **unfunded paper-monitoring
statistic**; it should not be treated as an executable recommendation or live
order instruction.

## Scope and a navigation limitation

The project graphify command/wiki artifact was unavailable, so this study used
only targeted raw inputs: the supplied MSTR daily and BTC minute datasets plus
official SEC EDGAR materials.  No secondary purchase calendar was used as a
source of truth.

The development period is **2020-01-01 through 2022-12-31**.  Rules were
frozen in [`FROZEN_RULES.md`](FROZEN_RULES.md) before a single 2023–2026
holdout evaluation.  The last MSTR daily observation is 2026-10-16.  BTC
minute-path regime labels end on 2026-08-11, so nine later holdout events are
explicitly marked unavailable for that auxiliary split.

## Verifiable event source and availability convention

The issuer is SEC CIK 0001050446.  The event universe was built from the SEC
[submissions feed](https://data.sec.gov/submissions/CIK0001050446.json):

1. Scan 234 Form 8-K filings dated from 2020 onward; scan all relevant attached
   HTML exhibits for the 2020–2022 audit.
2. Retrieve each candidate's official SEC primary document and retain a row only
   when the filing reports a **positive** BTC purchase/acquisition.  Zero-purchase
   updates, BTC-sale-only updates, financing-only filings, and stale historical
   restatements are excluded.
3. Use EDGAR's `acceptanceDateTime` as the signal timestamp.  It is an auditable
   public-availability timestamp and deliberately does not assume that an
   earlier company press release, dashboard post, or newswire item was tradable.

This produced **106** source-linked purchase events: 21 in development and 85
in holdout.  The exact timestamp, quantity, accession, source link, funding
label, and executable entry date are in
[`validated_purchase_events.csv`](validated_purchase_events.csv).  There were
no source-retrieval failures (`event_source_failures.csv` contains only its
header).

Illustrative primary records:

- [2020-08-11 8-K](https://www.sec.gov/Archives/edgar/data/1050446/000119312520215604/d921849d8k.htm): EDGAR accepted at **11:12:54 EDT** and reports the first 21,454-BTC purchase.
- [2020-09-15 8-K](https://www.sec.gov/Archives/edgar/data/1050446/000119312520245835/d42524d8k.htm): accepted at **12:25:31 EDT** and reports the 16,796-BTC acquisition.
- [2022-12-28 8-K](https://www.sec.gov/Archives/edgar/data/1050446/000119312522313098/d398241d8k.htm): reports two positive purchases (2,395 and 810 BTC) alongside a sale; the event row records gross purchases, not a fictitious purchase-only narrative.
- [2024-11-25 8-K](https://www.sec.gov/Archives/edgar/data/1050446/000119312524264733/d844494d8k.htm) and [2025-03-31 8-K](https://www.sec.gov/Archives/edgar/data/1050446/000095017025047219/mstr-20250331.htm): examples of the recurring holdings updates that expressly mention ATM/equity and/or financing sources.

Of 106 events, 105 were accepted before 16:00 New York time and can use that
session's close under the stated convention.  The exception is the 2020-12-04
filing accepted at 22:26:54 EST; its entry is conservatively moved to the next
available close, 2020-12-07.  The later regime is strongly Monday-heavy (77 of
106 entry dates), which is why a weekday-matched benchmark is included.

## Frozen, executable rules

Both rules are long-only and use the first MSTR regular-hours **close** after
the EDGAR timestamp: the filing-date close if accepted before 16:00 ET,
otherwise the next MSTR trading-session close.  This is a market-on-close
convention that could be submitted after the public filing and before the
close; it makes no unsupported intraday-fill claim.

| Rule | Position | Exit |
| --- | --- | --- |
| `P1` | Buy MSTR at the executable entry close | Next trading-session close |
| `P5` | Buy MSTR at the executable entry close | Fifth subsequent trading-session close |

When a new signal arrives during an open position, the implementation does not
add leverage; it extends the exit to the later scheduled exit.  Execution uses
the supplied `mstr_daily_yf.parquet` close series and deducts **3 bp adverse
execution each side plus $0.005/share each side**.  There are no shorts or
borrow assumptions.  The historical close series is split-adjusted; applying
the full $0.005 to its adjusted pre-split prices is conservative rather than
cost-minimizing.

## Main results

Returns below are net of the baseline costs.  `Total net` is the no-leverage,
cash-between-episodes portfolio result; it is not the product of overlapping
event returns.  The t-statistic and 10,000-resample IID bootstrap are reported
as descriptive uncertainty only—weekly events share market regimes, so their
effective independence is weaker than the nominal event count.

| Rule / sample | N events | Mean | Median | t-stat | Bootstrap mean 95% CI | Episodes | Total net | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| P1 development | 21 | -1.235% | -1.189% | -0.96 | [-3.63%, +1.24%] | 21 | -25.68% | -34.69% |
| P1 holdout | 85 | -0.578% | -0.497% | -1.10 | [-1.57%, +0.43%] | 85 | -44.66% | -61.63% |
| P5 development | 21 | +3.849% | -1.086% | +0.80 | [-3.93%, +14.18%] | 18 | +58.07% | -47.09% |
| P5 holdout | 85 | +1.227% | -0.394% | +0.87 | [-1.34%, +4.03%] | 27 | +61.95% | -78.75% |

The P5 mean is visibly outlier-sensitive: its highest holdout trade is
**+67.37%** from the 2024-02-26 entry.  Its holdout win rate is only 47.1%,
and the median is negative.  That is not a credible payoff profile for a rule
claimed to monetize the disclosure itself.

### Annual event-return split

| Entry year | N | P1 mean net | P5 mean net |
| ---: | ---: | ---: | ---: |
| 2020 | 3 | -0.12% | -4.02% |
| 2021 | 13 | -0.15% | +3.69% |
| 2022 | 5 | -4.71% | +8.97% |
| 2023 | 6 | +1.65% | +11.60% |
| 2024 | 14 | +1.15% | +9.68% |
| 2025 | 40 | -0.62% | -1.37% |
| 2026 | 25 | -2.02% | -1.84% |

The positive P5 aggregate is concentrated in 2023–2024, then reverses across
the much more numerous 2025–2026 weekly-update regime.  This lack of annual
repeatability is a central reason for rejection.

## Benchmarks and conditioning checks

### Ordinary MSTR exposure

Full-period MSTR buy-and-hold was -1.90% in development and +843.53% in the
holdout (2023-01-03 through 2026-10-16).  Because purchase events become
mostly Monday filings, the more relevant comparator is non-event MSTR return
over the same holding horizon and weekday mix, using the **same** costs:

| Rule / sample | Event mean net | Weekday-matched non-event MSTR mean net | Matched bootstrap 95% CI |
| --- | ---: | ---: | ---: |
| P1 development | -1.235% | +0.171% | [-2.33%, +2.73%] |
| P1 holdout | -0.578% | -0.039% | [-1.16%, +1.05%] |
| P5 development | +3.849% | +0.710% | [-4.87%, +6.48%] |
| P5 holdout | +1.227% | +3.350% | [+0.71%, +6.08%] |

P5's holdout disclosure windows therefore underperform ordinary weekday-matched
MSTR windows by roughly 2.1 percentage points per five-session holding period,
despite the positive raw total.

### BTC five-day regime (descriptive, not a new rule)

The BTC value is the last minute available at the 16:00 New York entry close,
compared with the same clock time five calendar days earlier.  It is deliberately
not used to choose a rule.

| Rule / holdout BTC condition | N | Mean net | Bootstrap 95% CI |
| --- | ---: | ---: | ---: |
| P1, BTC down/flat | 40 | -0.327% | [-1.67%, +0.99%] |
| P1, BTC up | 36 | -0.741% | [-2.46%, +1.07%] |
| P5, BTC down/flat | 40 | +1.285% | [-1.45%, +4.21%] |
| P5, BTC up | 36 | +1.970% | [-2.99%, +7.62%] |

All intervals include zero, and the development split is inconsistent (notably,
P5 is negative after prior BTC weakness but positive after prior BTC strength).
The regime test supplies no defensible conditional rule.

### Financing/issuance disclosure labels

The source text labels 66 holdout events as explicitly mentioning ATM/equity,
13 as ATM/equity plus convertible funding, 2 as convertible-only, and 4 as
cash/unspecified.  This is useful provenance, not proof that a financing event
caused the observed return: current filings can discuss several capital sources
at once.  P5's large ATM/equity subset has a +0.859% mean but a -0.811% median
and a bootstrap interval crossing zero; the other groups are far too small to
support a separately tradable issuance-flow rule.

## Cost sensitivity

Increasing the adverse-fill assumption while retaining $0.005/share on each
fill does not rescue P1.  It makes the P1 holdout total -44.66%, -50.87%, and
-58.55% at 3, 10, and 20 bp per side, respectively.  P5 remains nominally
positive (+61.95%, +55.94%, +47.74%), but its confidence interval, benchmark
underperformance, and 78.7% drawdown already fail the robustness screen.  The
full table is in [`cost_sensitivity.csv`](cost_sensitivity.csv).

## Reproducibility and artifacts

- [`scan_sec_purchase_events.py`](scan_sec_purchase_events.py) — SEC 8-K scan;
  caches only derived candidate rows/snippets and source URLs.
- [`event_study.py`](event_study.py) — source validation, signal timing,
  backtest, bootstrap, benchmarks, cost and BTC-regime splits.
- [`validated_purchase_events.csv`](validated_purchase_events.csv) — final
  source-linked universe; no SEC filing bodies are cached.
- [`p1_event_trades.csv`](p1_event_trades.csv),
  [`p5_event_trades.csv`](p5_event_trades.csv), and their episode/equity files
  — individual net return and executable no-leverage portfolio accounting.
- [`rule_summary.csv`](rule_summary.csv), [`annual_splits.csv`](annual_splits.csv),
  [`weekday_matched_mstr_benchmark.csv`](weekday_matched_mstr_benchmark.csv),
  [`btc_regime_splits.csv`](btc_regime_splits.csv),
  [`funding_label_splits.csv`](funding_label_splits.csv), and
  [`ordinary_mstr_benchmark.csv`](ordinary_mstr_benchmark.csv) — reported
  aggregates.

To refresh:

```bash
cd /Users/rytty/CCP/quant_v7/research/mstr_btc_0dte/agent_events
python event_study.py
```

The script re-queries primary SEC documents rather than treating a mutable
third-party calendar as evidence.  It places no orders.
