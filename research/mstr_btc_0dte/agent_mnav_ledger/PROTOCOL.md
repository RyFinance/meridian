# Causal 8-K holdings-ledger mNAV study

This workstream asks a narrowly defined question: does a **gross BTC mNAV
proxy**, made more timely by SEC-timestamped BTC-purchase 8-Ks, improve MSTR
long/cash timing after realistic stock costs?

It is not enterprise mNAV.  The proxy is:

`MSTR closing market capitalization / (causally disclosed BTC holdings × BTC 15:59 ET mark)`.

It does not subtract debt or preferreds and should not be interpreted as a
fundamental valuation estimate.

## Information and execution timing

- A BTC holding update in an 8-K is applied only from the **first MSTR regular
  session strictly after its filing date**, even when EDGAR accepted it before
  the close.  A reported Class A + B share count is applied the same way after
  its 10-Q/10-K filing date.
- BTC uses only the close of the exact minute labelled **15:59 ET**.  The bar
  ends at 16:00; a missing bar makes that signal invalid rather than using an
  earlier price.
- MSTR price and the resulting proxy are observed at the regular close.  A
  signal made then changes the MSTR position at the **following session's
  regular open**.
- The MSTR history is split-adjusted.  A pre-2024-08-01 reported share count
  is multiplied by ten based on its **share-as-of date**, not merely its filing
  date.

## Costs and tradability

The sole candidate is unlevered MSTR long/cash.  Each transition uses a 3 bp
open-auction slippage penalty per side plus `$0.005` per actual share.  Because
the prices are split-adjusted, the pre-split fee is `$0.0005` per adjusted
share.  A 6 bp/side stress case is reported separately.

No BTC hedge is promoted in this study: a real hedge would require a specific
available BTC futures/perpetual venue, margin treatment, funding/roll data and
execution costs.  Those are not present in the supplied data, so inventing a
hedged net P&L would be less realistic than omitting it.

## Research firewall

Development ends 2022-12-30.  The initial run evaluates seven small,
economically motivated premium-trend variants (5/10/20/40-session momentum,
with optional 50-session proxy-level filter), all with a 120-session maximum
age for the last filed share count.  At most two rules are chosen based only on
the development artifacts.  The selected rules and their canonical hash are
written to `FROZEN_RULES.json` before any 2023+ performance computation.

The one sealed validation window is 2023-01-03 through 2026-08-10, the final
full MSTR session before the stipulated BTC minute source ends.  Results must
also be compared with cost-matched MSTR buy-and-hold and a 50-session MSTR
price-trend long/cash benchmark.  A raw long-MSTR gain is never called alpha.

## Acceptance standard

A candidate is a research lead, not a deployable claim, only if the sealed
baseline and double-cost runs are net positive **and** it demonstrates a
positive point estimate against the matched MSTR price-trend benchmark.  We
also report a HAC daily excess-return t statistic and 5-day block-bootstrap
confidence bound.  Failure of those robust-inference checks means it is not a
statistically established edge even if its compounded return is positive.
