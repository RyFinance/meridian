# Forward paper test — mNAV M1 (prospective monitoring only)

Registered **after** the sealed validation failed (`HOLDOUT_RESULTS.md`,
2026-10-17). This is not a promotion: the registered gate (P ≥ 0.95) was not
met. This plan exists because the frozen rule's risk profile (≈ B&H return with
~half the drawdown, positive through the 2025–26 MSTR bear) is worth cheap
prospective monitoring. It commits no capital, can never convert the sealed
FAIL into a validation, and its window has not happened yet.

## Rules (identical to the frozen spec; no changes)

M1: long when `p_t − p_{t−10} > 0` and `p_t > SMA50(p_t)`, where
`p_t = log(gross_btc_mnav_proxy_t)` built exactly per `FROZEN_RULES.json` +
`FROZEN_RULES_AMENDMENT_01.json` (MSTR close × reported A+B shares on
split-adjusted basis ÷ (disclosed BTC held × 16:00 ET BTC spot); quarterly share
observations usable from the first session after filing; gap policy: no
interpolation, stance carried).

Execution: signal after close t, position set at open t+1; 100% MSTR / 100%
cash; base costs 3 bp/side + $0.005/share ($0.0005 pseudo-share pre-split).
Marks computed at each session close.

## Forward window

Sessions from **2026-10-19** (next Monday) onward. Registration date
2026-10-17. Any data before 2026-10-19 is in-sample for this rule and is used
only for signal warm-up (it must be, to compute the lookbacks), never for
reporting.

## Monitoring plan (descriptive; fixed in advance)

- Runner: `forward_m1.py` — recomputes the proxy/panel from the same sources
  and appends paper marks (position, NAV, benchmark NAV) to
  `forward_m1_marks.csv`; idempotent and re-runnable.
- Report at forward month 12 and month 24 (or on request): net Sharpe, CAGR,
  max drawdown, time long, vs MSTR B&H on the identical forward window, plus
  the same 21-session block-bootstrap Sharpe difference (2,000 draws, seed
  20260817).
- Kill/promote rules are NOT part of this plan; nothing is promoted without a
  separately registered validation-style gate and user sign-off.

## Data duties (manual, disclosed)

The BTC 16:00 ET quotes come from the BTC-Acum 1-minute file and the MSTR
daily closes from `../mstr_daily_yf.parquet`; both files must be refreshed
before scoring. Sessions whose 16:00 BTC quote is missing (>15 min stale) are
gap sessions under the frozen policy (stance carried; P&L still booked).
