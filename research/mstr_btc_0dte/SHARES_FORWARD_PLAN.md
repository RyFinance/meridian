# Forward paper test: MSTR shares, direction from BTC's off-hours move when |move| >= 1%

Registered 2026-10-16 (Thursday) before the first decision (Monday 2026-10-19).
Strategy id `mstr_btc_offth_v1`. Frozen code: `research/mstr_btc_0dte/forward_off.py`
plus the shared `forward.py` (BTC sampling + sim client), `costs.py`, and
`research/forward/` modules (their SHA-256 is in `forward_off_spec.json` and the registry).

## What is already known (no hidden hold-out)
- The whole 2020-08..2026-08 daily history was fully examined in `REPORT.md`
  (mostly Monday-only for shares), so the DAILY level is not out of sample.
- Dev window (2020-08..2023-12), all weekdays, |btc_off| >= 1%: RAW direction
  open->close on $100k notional earns +50.2 bp net, t 2.28 (stress +31.3 bp),
  all dev years positive: 2021 +8.4, 2022 +52.3, 2023 +87.3 bp.
- No |off| filter: +25.3 bp, t 1.54 (n=827) — the filter halves the noise days.
- Quintile monotonicity dev: btc_off q(-424bp)->mstr_day -63.9bp ... q(+468bp)->+49.3bp.
- Not a 2020 artifact: 2021-23 alone +50.2 bp t 2.13; 2022-23 +77.7 bp t 2.60.
- Tuesday is the strongest dow cell (+105 bp, t 2.37, n=107) but no dow is excluded:
  the registered rule is dow-agnostic (Mon..Fri) to avoid a 5-cell cherry pick.
- Caveat: `signal_study.py` printed the all-weekday correlation table over the FULL
  sample (2020-2026) before today; the >=1% rule itself was only cut on the dev window.

The prior is weak-to-moderate (dev t ~2.3 on half the dev days). The forward test is
the only evidence that counts.

## Rule (fixed)
On every NYSE session (Monday included; a missing decision = missed, stays in the count):
1. P0 = Coinbase BTC-USD 1-minute close at the previous session's official close time
   (16:00 ET, or 13:00 early close). P1 = Coinbase BTC-USD 1-minute close at 09:25 ET.
2. r = ln(P1 / P0); d = sign(r); if |r| < 0.01 the decision is "no trade" (recorded,
   counted as a decision, excluded from trade stats).
3. Decision recorded in `reports/forward/registry.jsonl` between 09:25:00 and 09:29:30 ET.
4. Position: d x $100,000 of MSTR shares, entered at the official open, exited at the
   official close. Fixed notional, no compounding, no leverage, intraday short allowed
   (no borrow fee; same-session round trip).

## Costs (realistic; `costs.py` — shared with mstr_btc_monday_v1)
IBKR Pro Fixed $0.005/share per side (min $1, max 1%); SEC $27.80/$1M sale side;
FINRA TAF $0.000166/share sold (max $8.30); slippage 3 bp open / 1 bp close against
official prices. Stress: 10 bp per side, 2x commission.

## Gate (decided now)
- Final evaluation at 104 counted sessions (~Oct 2028).
- Pass requires all three: mean base net > 0 with one-sided t >= 1.65; stress-cost
  mean > 0; annualised Sharpe (sessions only) >= 0.5.
- Kill early if cumulative base net P&L <= -$15,000 on $100k notional.
- |off| threshold, BTC source, decision time, instrument are frozen; changing any is a
  new strategy id.

## Power, stated honestly
Dev t ~2.3 suggests a real but modest edge; two years at dev Sharpe (~0.2-0.3 annualised
on the filtered set) gives expected t ~1.3-2.0. Expect "inconclusive" if the edge is at
dev strength; a kill is plausible if the 2024-2026 regime differs from 2020-2023.

## Operations
`forward_off.py decide` every NYSE session at 09:25 ET (launchd agent, same pattern as
the Monday test); `forward_off.py close` at 15:59 ET; `forward_off.py evaluate` scores.
Sim orders go to the SAME LSE sim account used for observation only (sim fills are an
execution check, never the score). First session: Monday 2026-10-19 — both tests decide
that morning; the Monday RAW test recorded separately.
