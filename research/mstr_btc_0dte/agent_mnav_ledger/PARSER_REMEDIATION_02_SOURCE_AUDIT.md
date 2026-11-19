# Source-only reconciliation before final remediation

This document records the independent source-level audit completed before the
single final corrected validation.  It contains **no strategy performance**.

## Parser scope

The BTC Update parser now accepts `BTC Acquired`, `BTC Purchased`, and
`BTC Sold` headers only when a structured `Aggregate BTC Holdings` field is
present.  It binds a candidate row to its nearest preceding `During Period`
label and stops at the next such label, so it selects the maximum disclosed
**As of** date in a multi-row filing.  Asterisked dates are treated as the
same calendar date.  It explicitly handles em-dash/zero no-purchase rows and
records activity type, signed sale quantity, period start/end, as-of date,
source order, and selection method.

## Independent audit result

The independent reconciliation of the local SEC event index and cached primary
documents was **CLEAN** for the parser version hash recorded in
`FROZEN_RULES_AMENDMENT_02.json`:

- 122 complete ledger rows from 2020-08-11 through 2026-08-10; 101 rows in
  the sealed 2023–2026 source period (63 purchase-table, 4 sale-table, and 34
  narrative records).
- Zero missing primary documents in the local requested-date range.
- Every local 2023–2026 disclosure with explicit current BTC-holdings wording
  is represented; all ledger availability sessions are strictly after the SEC
  filing date.
- No spurious one-BTC header-footnote purchases and no implausible totals.
- The five known multi-row/no-purchase cases select the correct source row.
- All four sales reconcile exactly: 32 / 843,706 (2026-06-01), latest 2,225 /
  843,775 as of 2026-07-05 (2026-07-06), 1,638 / 842,138 (2026-08-03), and
  1,690 / 840,447 (2026-08-10).  Holdings decrease only on these disclosed
  sale updates.

The scope is deliberately limited to the supplied local SEC index/cache; it
does not assert completeness beyond those source inputs.
