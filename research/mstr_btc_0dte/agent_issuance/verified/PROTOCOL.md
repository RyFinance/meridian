# Protocol — MSTR issuance / convertible announcement drift

## Question

Do discrete, public announcements of a new MSTR/Strategy convertible-note
offering or a new at-the-market (ATM) sales program create a tradeable,
MSTR-specific post-announcement drift after realistic execution costs?

This is deliberately not a re-run of the BTC-purchase disclosure study.  The
event universe contains **only the initial announcement of a new offering or
new ATM program**.  Recurring weekly ATM-sale / BTC-holdings updates, later
purchase disclosures, ordinary earnings reports, and filings that merely
mention an existing capital program are excluded.

## Primary source and event clock

Every event must be supported by the relevant primary EDGAR filing (8-K,
prospectus, free-writing prospectus, or registration statement) and has its
EDGAR `acceptanceDateTime` retained in the ledger.  Each offering episode is
deduplicated to the earliest qualifying acceptance timestamp.  A prospectus or
closing document cannot replace an earlier announcement.

Trade availability is conservative:

| Acceptance time in New York | Earliest eligible entry |
| --- | --- |
| Before 09:25 on an MSTR session | That session's regular-hours open |
| 09:25 or later, or a non-session | The next MSTR regular-hours open |

The 09:25 cutoff provides five minutes before the auction; no extended-hours
execution is assumed.

## Development / holdout split

* Development: event entries through 2023-12-29 (prices through 2023-12-29).
  The 2023 endpoint is permitted by the project brief and supplies the minimum
  five discrete common-ATM programs needed to evaluate that family.
* Sealed holdout: entry dates from 2024-01-02 through the last available daily
  MSTR price.  The holdout price data are not read by the development program.

The collection script may build the filing **source ledger** for the entire
period without observing returns, so the same deterministic event definition
is applied in holdout.  Rule selection is based solely on development prices.

## Candidate families and economic signs

1. **Convertible initial announcement: long MSTR.**  A convertible raise can
   fund accretive BTC acquisition, extend the company's financing runway, and
   expand the market's valuation of its BTC-treasury vehicle.  Candidate holds
   are 1, 3, and 5 sessions from an eligible open to the corresponding close.
2. **New ATM program announcement: short MSTR.**  New common-equity capacity
   can imply dilution / supply pressure.  Candidate holds are 1, 3, and 5
   sessions.  This family is only eligible if a 30% annualized stock-borrow
   charge still leaves a positive result; unavailable borrow is treated as a
   failure rather than assumed away.

At most two rules may be frozen.  A candidate needs an economically coherent
sign, at least five development episodes, positive **net excess** return versus
matched ordinary MSTR episodes, and no single episode contributing more than
50% of its cumulative gross profit.  These are anti-fishing screens, not a
claim of statistical proof.

## Execution, costs, and evaluation

Entry is at daily Open with 3 bp adverse slippage; exit is at daily Close with
3 bp adverse slippage.  Commission is $0.005 per adjusted-data share on both
sides.  This is conservative for pre-2024 rows because the data are split
adjusted.  Short candidates also accrue 30% / 252 per held regular session,
and must disclose that historical borrow availability is unverified.

There is no leverage and overlapping signals are merged into non-overlapping
episodes; if two events would overlap, the first event owns the position and
the later event is recorded but not compounded separately.

The primary comparator is a same-horizon, same-weekday distribution of
ordinary MSTR Open-to-Close episodes that do not overlap any issuance event
window, charged with the identical **directional** costs (long for a long
candidate, borrow-inclusive short for a short candidate).  This prevents a
nominal gain in a volatile MSTR/BTC regime from being called an event edge.
For long rules, the report also shows an uncosted BTC-matched contextual
comparison when available, but the matched-MSTR benchmark is the pass/fail
comparator.

The sealed validation reports event-level means/medians, t statistic,
bootstrap confidence interval, compounded non-overlapping portfolio result,
cost stress (6 bp each side plus $0.01/share), annual splits, and matched-MSTR
excess.  A positive nominal return alone is not a pass.
