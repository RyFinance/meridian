# Out-of-sample mechanism test: ETH during the CME break (registered 2026-10-17, before any ETH data is fetched)

**Hypothesis.** If the BTC 17:00–18:00 ET effect comes from CME's daily crypto-futures break, ETH (whose CME futures break at the same time) should also rise in that hour. No ETH intraday data has been looked at in this project.

**Test, run once.**
- Data: Coinbase ETH-USD 1-minute closes at 17:00 and 18:00 ET on NYSE weekday sessions, 2019-01-02..2026-10-16.
- Statistic: r = ln(P18/P17).
- **Confirm:** mean > 0 with one-sided t ≥ 1.65 over the full period, AND mean > 0 in 2023–2026.
- Reported, not gated: the same r for 16:00–17:00 and 18:00–19:00 ET (placebo hours), and by year.
- If confirmed: a combined BTC+ETH version becomes a separate forward test (new id). The frozen BTC test is unchanged.
