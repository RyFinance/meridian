# Frozen P1 source-transition forward audit

## Rule and boundary

This applies **exactly** the P1 rule frozen by the proxy study, without changing
the threshold, time convention, or execution assumptions:

- At 09:29 ET, if BTC's completed 15:59-previous-session to 09:28-today return
  is at least +2.0%, buy MSTR at the official open and sell at the official
  close.
- Otherwise hold cash.  There is no short, leverage, after-hours fill, or
  overlapping position.
- Each side pays 3 bp plus $0.005 per MSTR share.

The primary BTC minute file used by the frozen validation ends before the
2026-08-11 US pre-open.  This local forward audit uses the pre-existing Binance
BTCUSDT perpetual 1-minute archive for 2026-08-11 through 2026-09-30.  Because
this is a source change, it is not folded into the primary out-of-sample claim
or used to alter the rule.

## Source-transition check

On the six eligible MSTR sessions in the pre-tail overlap (2026-08-03 through
2026-08-10), the Binance and original BTC sources made the same >=2% selection
decision on all six sessions.  The largest absolute BTC off-hours-return
difference was 1.89 bp.  This supports, but does not prove, timing/source
compatibility for the tail audit.

## Locked forward result

| Period | Eligible sessions | Active trades | Mean net active return | Trade t-stat | Net compound | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-08-11 to 2026-09-30 | 36 | 5 | +285.4 bp | 1.14 | +14.46% | -1.24% |

The tail is directionally consistent with the primary P1 validation, but five
trades have almost no inferential power.  It **does not rescue** the primary
rule from its weak full-validation trade-level t-statistic (0.91) or make a
source-transition test a deployable-edge claim.  It is retained as transparent
forward evidence only; `audit_p1_forward.py`, `source_overlap.csv`,
`forward_sessions.csv`, and `summary.json` reproduce it.
