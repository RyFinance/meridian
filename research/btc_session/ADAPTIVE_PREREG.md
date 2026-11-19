# Adaptive session rule (registered 2026-10-17, before any result of it is computed)

**Problem.** The fixed 17:00–18:00 ET BTC hour weakened in 2026 (+1.4 bp; −1 bp after the freeze). Choosing a new hour by looking at 2026 would be curve-fitting.

**Rule.** Walk-forward and causal: it uses only data before day d.
- Universe: the 24 ET clock hours of BTC on NYSE weekday sessions. The hour is labelled by its start; r = ln(P(h+1)/P(h)) from 1-minute closes.
- Each day d, for each hour h, compute the trailing-T-session mean m_h and its t-stat over sessions [d−T, d−1].
- Trade the single hour with the highest t, long if t ≥ +2.0, or short if the lowest t ≤ −2.0 and |t| is larger. No trade if neither.
- Candidates: T ∈ {60, 120, 250} sessions.
- Costs: 4 bp per round trip (base) and 8 bp (stress).

**Evaluation, run once.** 2019-01..2026-10-16, reported per year.
- **Primary:** net @4 bp sum > 0 in 2025 AND in 2026 YTD, AND full-period net t ≥ 1.65 (Bonferroni for 3: t ≥ 2.13).
- Data: BTC 1-minute from `btc_usd_1m_candles_polymarket_arb.parquet` up to 2026-08-10, then Binance BTCUSDT perp 1-minute (`data/binance_mstr_token`, plus the API for October).
