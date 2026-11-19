# Forward paper test: MSTR Monday open→close, direction from BTC's weekend move

Registered 2026-10-16 (Friday) before the first decision (Monday 2026-10-19). Strategy id `mstr_btc_monday_v1`.
Frozen code: `research/mstr_btc_0dte/forward.py` and `costs.py` (their SHA-256 is in `forward_spec.json` and the registry).

## What is already known (no hidden hold-out)
The 2020-08..2026-08 history was fully examined in `REPORT.md`, so it is not out of sample.
- At 09:30, with 3 bp per side, this rule earned +42 bp per Monday (t 1.35).
- Under this exact spec (09:25 BTC sample, realistic costs), it earns **+21 bp net, t 0.67, Sharpe 0.27**, and about 0 with stress costs (`recheck_shares.py`).
- Net returns were negative in 2025 and 2026.
- Selection bias: MSTR was picked *because* it tracks BTC, and the Monday-only cut was chosen after looking at Mon/Fri splits. Survivorship in the usual sense does not apply (a single, pre-named, listed stock).

The prior is weak. The forward test is the only evidence that counts.

## Rule (fixed)
On every NYSE session that is a Monday (a Monday holiday means no trade):
1. P0 = Coinbase BTC-USD 1-minute close at the previous session's official close time (16:00 ET, or 13:00 on early-close days). P1 = Coinbase BTC-USD 1-minute close at 09:25 ET Monday.
2. Direction d = sign(ln(P1 / P0)); d = 0 means no trade.
3. Record the decision in `reports/forward/registry.jsonl` between 09:25:00 and 09:29:30 ET. It is not counted if recorded at or after 09:30:00.
4. Position: d × $100,000 of MSTR shares (long or short), entered at the official open and exited at the official close. Notional is fixed, with no compounding and no leverage.

## Costs (realistic; `costs.py`)
IBKR Pro Fixed: $0.005/share per side (min $1, max 1%); SEC fee $27.80/$1M on the sale side; FINRA TAF $0.000166/share sold (max $8.30); slippage 3 bp at the open and 1 bp at the close against official prices; no borrow fee (the short is intraday).
Stress: 10 bp slippage per side and 2× commission. Base cost is about 6.3 bp per round trip.

## Scoring
- Official returns use the official MSTR open and close (LSE 30m regular-session reconstruction, yfinance fallback), net of `costs.py`.
- The LSE sim account fills are logged as a separate execution check and are not used for the score.

## Gate (decided now)
- Final evaluation at 104 counted Mondays (about October 2028).
- **Pass** requires all three: mean base net return > 0 with one-sided t ≥ 1.65; stress-cost mean > 0; annualised Sharpe (Mondays only) ≥ 0.5.
- **Kill early** if cumulative base net P&L ≤ −$15,000 (−15% of notional).
- The look at 52 Mondays is for reporting only, with no early pass.
- Changing the time, the BTC source, the day or the instrument is a new strategy id.

## Power, stated honestly
At the historical Sharpe of 0.27, two years of Mondays gives an expected t of about 0.4. A pass needs the true edge to be several times what history shows. Expect "fail" or "inconclusive".

## Operations
`forward.py decide` runs Monday at 09:25 ET: it records the decision, then at 09:30:20 sends a market order to LSE sim account 1717158. `forward.py close` runs at 15:59 ET and flattens the position. `forward.py evaluate` scores the test. A missed run (Mac asleep, app closed) is a missed decision and stays in the count as missed.
