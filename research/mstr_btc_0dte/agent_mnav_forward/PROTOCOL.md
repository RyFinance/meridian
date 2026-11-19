# Strictly causal mNAV M1 source-transition extension

This directory is isolated from `agent_mnav`; it changes neither that track's
code nor its outputs.  It tests only frozen M1:

```
long at next MSTR regular-session open iff, after the prior MSTR close,
log(gross BTC mNAV proxy_t) - log(gross BTC mNAV proxy_t-10) > 0
and log(gross BTC mNAV proxy_t) > 50-session SMA(log(gross BTC mNAV proxy)).
```

The proxy retains the frozen definition: MSTR close times disclosed Class A+B
shares, adjusted to the Yahoo split price basis, divided by disclosed BTC held
times BTC/USD.  The SEC ledger is the authoritative one already produced by
the mNAV run.  A filing becomes usable only on the first MSTR session strictly
after its filing date.

## Causality and source transition

For every MSTR session, the BTC input is the completed minute bar labelled
15:59 in `America/New_York`: its close occurs at 15:59:59.999, no later than
the MSTR 16:00 close.  A 16:00-labelled BTC bar is deliberately excluded.

- Through 2026-08-10, use the primary BTC minute source's exact 15:59 bar.
- Starting 2026-08-11, use exact 15:59 bars from locally archived Binance
  BTCUSDT perpetual data only after comparing it with the primary source on
  the pre-switch overlap.
- Do not substitute, interpolate, or forward-fill BTC.  Once the Binance
  archive ends, retain the frozen rule's existing gap policy: carry the last
  stance and continue recording MSTR open-to-open P&L.

P&L is a deliberately conservative, cash-rebased forward segment.  It charges
3 bp open slippage plus $0.005 per actual share on every entry and exit,
including a new opening entry if the pre-transition stance was already long.
It force-liquidates at the final included MSTR open with the same costs.

This is research-only.  It is not a new candidate search, an optimization, or
an authorization to trade.
