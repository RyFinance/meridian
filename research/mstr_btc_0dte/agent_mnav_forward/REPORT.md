# Frozen M1 mNAV: strictly causal source-transition extension

## Result

The source transition itself is clean, and frozen M1 had a positive,
cost-inclusive post-transition return.  That is **not** enough evidence to
call it a confirmed alpha or deployable edge: the forward sample is only 36
source-observed sessions / four round trips, and it underperformed a
cost-consistent MSTR buy-and-hold benchmark over both reported windows.

| Forward window | MSTR sessions | M1 round trips | M1 time long | M1 net return | M1 maximum drawdown | MSTR buy-and-hold net return |
|---|---:|---:|---:|---:|---:|---:|
| 2026-08-11 to 2026-09-30, complete Binance 15:59 coverage | 36 | 4 | 83.3% | **+36.42%** | -9.43% | +65.07% |
| 2026-08-11 to 2026-10-16, all available MSTR daily opens | 48 | 4 | 87.5% | **+23.75%** | -17.79% | +49.74% |

Both M1 figures include a 3 bp adverse open fill on **every** entry and exit,
plus $0.005 per actual share on every entry and exit.  The standalone forward
segment starts from cash just before the 2026-08-11 open and charges a new
entry if its carried stance is long; this is conservative rather than quietly
inheriting an earlier entry cost.

The first window is the clean source-observed extension.  The second follows
the frozen rule's stated missing-BTC policy after the local Binance archive
ends: no BTC close is invented, no signal is recomputed, and the last known
long/cash stance is carried across the 12 MSTR sessions from 2026-10-01 to
2026-10-16.  That unobserved-BTC tail reduced the strategy's marked NAV by
9.32% from the 2026-09-30 open to the final forced liquidation open.

## Frozen rule and causal timing

This audit runs **only** frozen M1, without changing a parameter or ranking a
candidate:

```text
At MSTR close t:
  long for next regular-session open when
    log(gross_BTC_mNAV_proxy_t) - log(gross_BTC_mNAV_proxy_(t-10)) > 0
    AND log(gross_BTC_mNAV_proxy_t) > SMA_50(log(gross_BTC_mNAV_proxy))
Otherwise hold cash.
```

`gross_BTC_mNAV_proxy` is MSTR close times the latest causally usable,
split-basis-adjusted disclosed Class A+B share count, divided by the latest
causally usable disclosed BTC holding times BTC/USD.  It is deliberately a
**gross BTC mNAV proxy**, not Strategy's enterprise mNAV.

For each session, the BTC input is the **completed 15:59 ET minute bar**.  A
15:59-labelled bar closes at 15:59:59.999, no later than the MSTR 16:00 close;
the potentially unavailable 16:00-labelled BTC bar is never used.  Signals
formed after a close execute only at the next MSTR regular-session open.

The authoritative SEC ledger was used unchanged.  Each filing becomes usable
at the close of the first MSTR session strictly after its filing date.  The
last ledger update used in this extension is the 2026-08-03 10-Q, first usable
at the 2026-08-04 MSTR close.  No later holdings, shares, or BTC values were
invented.

## BTC source transition check

The primary minute dataset has a usable completed 15:59 bar through
2026-08-10.  Binance BTCUSDT perpetual 1-minute archives supply the input
beginning 2026-08-11.  Before switching, their direct overlap was:

| Check, 2026-02-02 to 2026-08-10 | Result |
|---|---:|
| MSTR sessions / joint exact-15:59 coverage | 131 / 131 |
| BTC close-to-close return correlation | 0.999988 |
| Median Binance minus primary price | -4.85 bp |
| 95th-percentile absolute price difference | 6.84 bp |
| Maximum absolute price difference | 8.73 bp |
| Frozen M1 signal agreement | 131 / 131 sessions |

The final 20 overlap sessions also had 20/20 signal agreement.  Every MSTR
session from 2026-08-11 through 2026-09-30 had an exact Binance 15:59 bar;
there were zero within-window BTC gaps.  The source transition therefore does
not appear to explain the forward result by changing M1's stance.

## Interpretation

This extension is a useful **mechanics and continuity check**:

- It verifies the source handoff with a conservative completed-bar cutoff.
- It records positive net M1 P&L under stated open costs.
- It does not use the local Binance data to search for or tune a rule.

It is **not** a meaningful standalone proof of a persistent edge:

- Four round trips is far too little for an inference about expected return.
- M1 was long most of the interval and still lagged buy-and-hold sharply, so
  this tail does not demonstrate incremental return versus simply owning MSTR.
- The final 12-session extension is a legitimate frozen-gap-policy result,
  but it has no fresh BTC observations and should be reported separately from
  the 36 fully source-observed sessions.
- Binance BTCUSDT perpetual and the primary BTC feed are close enough here to
  preserve every M1 signal, but they are not identical market instruments.

The appropriate conclusion is: **positive but statistically unpersuasive
forward extension; source transition passes; no deployment claim.**

## Reproducibility artifacts

- `mnav_forward_audit.py` — isolated reproducible audit script.
- `PROTOCOL.md` — fixed rule, cutoff, data, and cost contract.
- `source_transition_summary.json` and `source_overlap_1559.csv` — coverage,
  price-basis, return-correlation, and signal-agreement evidence.
- `forward_summary.json` — machine-readable metrics and source hashes.
- `forward_panel.parquet`, `forward_signals.csv`, `forward_daily_equity.csv`,
  and `forward_trades.csv` — full causal inputs, decisions, equity marks, and
  executed cost-adjusted trades.

Run from `quant_v7`:

```bash
PYTHONPATH=. .venv/bin/python \
  research/mstr_btc_0dte/agent_mnav_forward/mnav_forward_audit.py
```
