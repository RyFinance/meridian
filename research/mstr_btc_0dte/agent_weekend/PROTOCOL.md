# BTC weekly-trend → MSTR weekend-gap experiment

## Economic hypothesis

MSTR cannot trade during the BTC weekend, but its Monday opening auction
incorporates the intervening BTC movement.  A Friday-close MSTR position can
therefore monetize a **predictable** component of BTC's weekend move, if one
exists.  This is not the rejected same-day open-to-close signal: the position
is established before the weekend, and the signal is known at Friday 16:00 ET.

## Pre-registered development screen

Use only Friday sessions from 2020-08-11 through 2022-12-30.  At Friday 16:00,
calculate BTC's return over the prior 5, 10, or 20 MSTR trading sessions.  For
each of the three rules, buy MSTR at the official Friday close only when that
BTC return is positive, then sell at the next available official MSTR open
(usually Monday).  Otherwise stay in cash.

No short side is tested.  Every trade is charged 3 bp auction slippage plus
$0.005 per MSTR share at both entry and exit.  The stress case is 6 bp plus
$0.010 per share per side.  Cash interest is set to zero.

Before looking at post-2022 performance, freeze at most two candidates only if
the positive rules form a neighboring 5/10/20-session cluster, remain positive
under stress, and are not driven by one calendar year.  Frozen rules get one
2023-01-03 through 2026-08-10 validation run; no later tuning is permitted.
