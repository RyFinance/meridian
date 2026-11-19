# Forward paper test: ETH during CME's daily break (17:00–18:00 ET)

Strategy id `eth_cme_break_v1`, registered 2026-10-17. It is the ETH twin of `btc_cme_break_v1`, and the two are evaluated together as the combined method. Frozen code: `research/btc_session/forward_eth.py`.

**Evidence.** The pre-registered one-shot test (`ETH_PREREG.md`) passed on data never examined before:
- 2019–26: +8.0 bp/trade, t 3.53.
- 2023–26: +10.3 bp, t 3.64.
- 2026 YTD: +3.2 bp.
- Placebo hours: 16:00–17:00 +1.2 bp (t 0.5); 18:00–19:00 +3.1 bp (t 1.5).

**Combined BTC+ETH (equal weight).**
- 2023–26: +6.9 bp, t 3.88.
- 2025–26: +6.3 bp, t 2.55.
- BTC–ETH correlation 0.82.

**Rule.** Every NYSE weekday: long $10k ETH from 17:00 to 18:00 ET. Score ln(P18/P17) on Coinbase ETH-USD 1-minute closes. LSE sim ETH/USD fills are an execution check only.

**Gate (combined with BTC v1).**
- Pass at 250 days: combined gross t ≥ 1.65 AND combined net at 4 bp > 0.
- Kill: combined cumulative net at 4 bp ≤ −8%.
