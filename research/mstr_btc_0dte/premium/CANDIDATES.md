# MSTR-vs-BTC premium momentum: frozen candidates (registered before any 2023+ result is computed)
- Code: `research/mstr_btc_0dte/premium/momo.py`. It is `pairs.py` with the side flipped: z > Z → long MSTR / short β·BTC; z < −Z → the reverse.
- Execution and costs: as described in the `pairs.py` docstring.
- Dev 2020-08..2022-12: 80 grid cells; 71% had t > 0; the 40-day lookback was the best region.
- M1: L=40, Z=1.0, H=5 (dev n 45, +308 bp per trade, t 2.20).
- M2: L=40, Z=1.5, H=10 (dev n 25, +392 bp per trade, t 1.60).
- Validation: 2023-01-01..2026-08-10, run once.
- Pass requires: net mean > 0 under base and 2× stress costs; one-sided t ≥ 1.96 (Bonferroni for 2); no full year with net sum < −20%.
