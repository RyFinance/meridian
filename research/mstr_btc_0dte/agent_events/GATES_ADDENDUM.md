# Gates addendum for the purchase-announcement rules (P1/P5)

Written and registered BEFORE `event_study.py` was first run to completion. No
2023+ event return has been computed. Disclosure: the earlier development event
study (`../events/dev_eventstudy.py`, 27 events, 2020-2022) was viewed; it used
the same acceptance-time entry convention and close-to-close windows, so dev
point estimates (P1-like −1.3%, P5-like +4.1%, t ≤ 1.2) are known. The holdout
is untouched.

## Universe and execution (per FROZEN_RULES.md)

Validated positive BTC-purchase 8-K events, entry at the close of the first
MSTR session at/after the EDGAR acceptance timestamp, exit at the close
`hold` sessions later, long-only, no leverage, costs 3 bp/side + $0.005/share
each side. Dev = entry date ≤ 2022-12-31; holdout = 2023-01-01 onward.

## Why an excess control

A long-only, sometime-in-the-market book earns whatever MSTR's drift is in the
sample. The honest question is whether event windows are better than ordinary
MSTR sessions. Control = the mean unconditional overlapping close-to-close
return of the same holding length over **all** sessions of the same sample
(no costs, since the control is "always long", not a traded alternative).

## Primary and secondary statistics (fixed before the run)

- Primary: **P5, holdout excess** = mean(net 5-session event return) −
  mean(unconditional 5-session return, holdout sessions).
- Secondary: **P1, holdout excess** (1-session form).
- Bootstrap: resample holdout event net returns with replacement, 10,000
  draws, seed 20261017 (the pipeline's `RNG`), subtract the fixed control mean
  from each draw; report the 2.5% quantile of the excess distribution.
- **PASS (primary) iff** the 2.5% quantile of P5 holdout excess > 0 AND the P5
  holdout net mean > 0. P1 is reported; it cannot substitute (one-sided 2.5%
  allocated to the single primary test of this 2-rule family).
- Additional reported-only: dev-sample equivalents, per-year splits,
  cost sensitivity (3/10/20 bp), BTC-regime splits, no-leverage episode
  portfolio totals and max drawdown. None of these enter the verdict.

## Outcome handling

PASS → forward paper-test registration only; no live orders. FAIL → recorded
in the graveyard (`../REPORT.md`); no re-runs on this window.

## Code and inputs (hashes registered before the run)

- Runner: `event_study.py` (fetches EDGAR primary documents live; no cache).
- Input universe snapshot: `sec_purchase_candidates_primary_only.csv`.
- Prices: `../mstr_daily_yf.parquet`; BTC regime: BTC-Acum 1-minute source.
