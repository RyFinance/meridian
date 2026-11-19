# C1/C2 one-shot validation result (2024-01-05 .. 2026-08-10): BOTH FAILED

Registered candidates and gates: `CANDIDATES.md` (unlock entries 2026-10-16T22:35:33 / 23:05:00 ET).
Runner: `run_validation.py` (hashes + two harness-fix amendments registered before any trade was computed;
see `research/preregistrations.jsonl`). Output: `validation_results_C1C2.json`, `run_validation_C1C2.log`.
Window: all 237 Mon/Fri vault sessions 2024-01-05..2026-08-10 (vault holds Mon/Fri only; 2026-08-10 is the last
session with a 24h BTC quote). Same code paths as the dev grids; no re-tuning.

## C1 — IC-v1 iron condor (BTC-agnostic, 2x1-wide put+call credit spreads/day)

| fills | n | win | mean % of risk | t | worst trade |
|---|---|---|---|---|---|
| base | 371 | 67.1% | **−3.71%** | **−1.62** | −101.5% |
| worst | 319 | 58.9% | **−14.0%** | **−5.78** | −101.3% |

Per-year net (base): 2024 **+12.9%**, 2025 **−7.8%**, 2026 **−9.1%**; (worst): 2024 +7.4%, 2025 **−21.8%**, 2026 **−18.3%**.
Dev was +24.6% of risk/trade, t 9.55, and positive in every dev year.

## C2 — NNV-v1 naked short premium on the BTC-safe side (hold to expiry)

| fills | n | win | mean % of premium | t | worst trade | p05 |
|---|---|---|---|---|---|---|
| base | 225 | 70.2% | **−14.06%** | **−0.83** | **−19.9x** | −2.65x |
| worst | 225 | 68.9% | **−17.8%** | **−1.00** | −22.3x | −3.15x |

Per-year net (base): 2024 **−14.5%**, 2025 **−33.8%**, 2026 **+20.5%**; (worst): 2024 −16.4%, 2025 **−40.0%**, 2026 +18.5%.
Dev was +24.7% of premium/trade, t 2.03.

## Gate outcomes (as registered)

- G1 mean net > 0 under both fill models: **C1 ✗, C2 ✗**.
- G2 one-sided base t ≥ 1.96: **C1 ✗ (−1.62), C2 ✗ (−0.83)**.
- G3 no calendar year ≤ −10% under any fill model: **C1 ✗ (worst-fill 2025 −21.8%, 2026 −18.3%), C2 ✗ (base 2024/2025, worst 2024/2025)**.
- Registered unlock note: only V1–V3 had already run in this file; C1/C2 were the two remaining, now consumed by this single run.

## What the numbers say

The dev-window short-volatility edge (2020-11..2023-12: rich MSTR IV, few bruises) did not persist on 2024-26.
Both structures kept the dev *win rate* (60-70% of trades green) but the average trade flipped negative: leaves
are still collected, the 2025-2026 tails give them back with interest. C2's worst single trade cost ~20x the
premium collected (dev's worst was −30.5x, so the tail behavior was foreseen — the dev point estimate was simply
too small to survive it). This closes the entire MSTR 0DTE/short-dated options family in this graveyard:
V1-V3 (Friday shorts), C1 (condor), C2 (naked side), plus the earlier spread/discovery grids — all FAIL on 2024+.
Do not re-run variants of any of these on this window. No live orders; the pending forward paper tests
(`FORWARD_PLAN.md`, `SHARES_FORWARD_PLAN.md`) remain the only live MSTR-options thread.
